#!/usr/bin/env python3
"""Draft and optionally create Sealos QA GitHub issues.

The default mode is safe: it prints a preview and performs no GitHub writes.
Use --create only after the user confirms the generated issue.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "assets" / "catalog.json"


@dataclass
class Inference:
    value: str | None
    confidence: str
    reason: str


@dataclass
class IssueDraft:
    repo: str
    title: str
    body: str
    product: Inference
    environment: Inference
    issue_type: Inference
    priority: Inference
    effort: Inference
    milestone: Inference
    labels: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    sensitive_warnings: list[str] = field(default_factory=list)
    catalog_suggestions: list[str] = field(default_factory=list)


@dataclass
class ProjectUpdateResult:
    item_url: str
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


@dataclass
class NativeMetadataResult:
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


@dataclass
class UploadResult:
    evidence: list[str] = field(default_factory=list)
    provider: str | None = None
    warnings: list[str] = field(default_factory=list)


class UploadError(RuntimeError):
    pass


def run(cmd: list[str], *, check: bool = False, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def save_catalog(catalog: dict[str, Any]) -> None:
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(text: str) -> str:
    text = text.replace("\\n", "\n")
    return re.sub(r"\s+", " ", text.strip())


def lower(text: str) -> str:
    return text.casefold()


def first_match_from_catalog(note: str, items: list[dict[str, Any]]) -> Inference:
    note_l = lower(note)
    for item in items:
        names = [item.get("name", "")] + item.get("aliases", [])
        for alias in names:
            if alias and lower(alias) in note_l:
                confidence = "high" if lower(item["name"]) in note_l else "medium"
                return Inference(item["name"], confidence, f"matched alias `{alias}`")
    return Inference(None, "low", "no known alias matched")


def infer_environment(note: str, catalog: dict[str, Any]) -> Inference:
    env = first_match_from_catalog(note, catalog["environments"])
    if env.value:
        return env

    url = re.search(r"https?://[^\s)）]+", note)
    if url:
        host = re.sub(r"^https?://", "", url.group(0)).split("/")[0]
        return Inference(host, "medium", "found URL host")

    ip = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:\.nip\.io)?\b", note)
    if ip:
        return Inference(ip.group(0), "medium", "found IP-like environment")

    return Inference(None, "low", "environment missing")


def infer_milestone(note: str, catalog: dict[str, Any]) -> Inference:
    note_l = lower(note)
    for milestone in catalog.get("milestones", []):
        if lower(milestone) in note_l:
            return Inference(milestone, "high", "mentioned in note")
    version = re.search(r"\bv\d+(?:\.\d+){1,3}\b", note, flags=re.IGNORECASE)
    if version:
        return Inference(version.group(0), "medium", "found version-like text")
    return Inference(None, "low", "milestone not specified")


def infer_type(note: str) -> Inference:
    feature_words = ["需求", "建议", "希望", "新增", "支持", "feature", "request"]
    if any(word in lower(note) for word in feature_words):
        return Inference("Feature", "medium", "feature-like wording")
    return Inference("Bug", "high", "QA issue defaults to Bug")


def infer_priority(note: str, catalog: dict[str, Any]) -> Inference:
    note_l = lower(note)
    rules = catalog.get("priority_rules", {})
    for priority in ["P0", "P1", "P2"]:
        for keyword in rules.get(priority, []):
            if lower(keyword) in note_l:
                return Inference(priority, "medium", f"matched priority keyword `{keyword}`")
    return Inference("P1", "low", "default for unclassified product bug")


def infer_effort(note: str) -> Inference:
    note_l = lower(note)
    if any(word in note_l for word in ["文案", "错别字", "样式", "颜色", "间距"]):
        return Inference("S", "low", "small UI/copy issue; developer should confirm")
    if any(word in note_l for word in ["架构", "重构", "多个模块", "全局", "兼容"]):
        return Inference("L", "low", "broad wording; developer should confirm")
    return Inference(None, "low", "effort is developer-owned")


def extract_evidence(note: str) -> list[str]:
    evidence: list[str] = []
    for url in re.findall(r"https?://[^\s)）]+", note):
        evidence.append(url)
    if "```" in note:
        evidence.append("包含代码块/接口片段")
    if re.search(r"\b(?:payload|preview|response|接口|报错|日志|截图|录屏)\b", note, re.IGNORECASE):
        evidence.append("包含测试证据描述")
    return list(dict.fromkeys(evidence))


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".avif"}
URL_RE = re.compile(r"https?://[^\s<>)\"'，。；;]+")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")


def validate_image_paths(paths: list[str]) -> list[Path]:
    images: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if not path.exists():
            raise UploadError(f"image not found: {path}")
        if not path.is_file():
            raise UploadError(f"image is not a file: {path}")
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise UploadError(f"unsupported image type `{path.suffix}` for {path}")
        images.append(path.resolve())
    return images


def image_placeholder_evidence(paths: list[str]) -> list[str]:
    try:
        images = validate_image_paths(paths)
    except UploadError as exc:
        return [f"本地截图待处理：{exc}"]
    return [f"本地截图待上传：{path.name}" for path in images]


def parse_upload_urls(output: str) -> list[str]:
    urls: list[str] = []
    for markdown_url in MARKDOWN_IMAGE_RE.findall(output):
        urls.append(markdown_url)
    for url in URL_RE.findall(output):
        urls.append(url.rstrip(".,]"))
    return list(dict.fromkeys(urls))


def format_uploaded_evidence(urls: list[str]) -> list[str]:
    return [f"![screenshot-{index}]({url})" for index, url in enumerate(urls, start=1)]


def clipboard_image_placeholder_evidence() -> list[str]:
    return ["剪贴板截图待上传"]


def has_configured_upload_command(catalog: dict[str, Any]) -> bool:
    command = catalog.get("image_uploader", {}).get("command")
    return isinstance(command, str) and bool(command.strip())


def render_upload_command(command_template: str, images: list[Path]) -> list[str]:
    files = " ".join(shlex.quote(str(path)) for path in images)
    first_file = shlex.quote(str(images[0])) if images else ""
    rendered = command_template.format(files=files, file=first_file)
    return shlex.split(rendered)


def configured_upload_command(catalog: dict[str, Any], images: list[Path]) -> list[str] | None:
    uploader = catalog.get("image_uploader", {})
    command_template = uploader.get("command")
    if isinstance(command_template, str) and command_template.strip():
        return render_upload_command(command_template, images)
    return None


def piclist_config_path(catalog: dict[str, Any]) -> Path | None:
    uploader = catalog.get("image_uploader", {})
    configured = uploader.get("piclist_config")
    if configured:
        return Path(str(configured)).expanduser()

    support_dir = Path.home() / "Library" / "Application Support" / "piclist"
    data_json = support_dir / "data.json"
    if data_json.exists():
        return data_json

    legacy = Path.home() / ".piclist" / "config.json"
    return legacy if legacy.exists() else None


def piclist_server(catalog: dict[str, Any]) -> dict[str, Any] | None:
    config_path = piclist_config_path(catalog)
    if not config_path or not config_path.exists():
        return None
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    server = config.get("settings", {}).get("server", {})
    if not isinstance(server, dict) or not server.get("enable"):
        return None
    key = config.get("settings", {}).get("serverKey")
    host = str(server.get("host") or "127.0.0.1")
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    port = int(server.get("port") or 36677)
    return {"host": host, "port": port, "key": key, "config_path": str(config_path)}


def upload_json_with_piclist_server(
    catalog: dict[str, Any],
    payload: dict[str, Any],
    *,
    expected_count: int,
    provider: str,
) -> UploadResult | None:
    server = piclist_server(catalog)
    if not server:
        return None
    curl = shutil.which("curl")
    if not curl:
        raise UploadError("PicList server is configured, but `curl` is not available.")

    url = f"http://{server['host']}:{server['port']}/upload"
    if server.get("key"):
        url = f"{url}?key={quote(str(server['key']))}"
    payload_text = json.dumps(payload, ensure_ascii=False)
    proc = run([curl, "-sS", "-X", "POST", url, "-H", "Content-Type: application/json", "-d", payload_text])
    if proc.returncode != 0:
        raise UploadError(f"PicList upload failed: {(proc.stderr or proc.stdout).strip()}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise UploadError(f"PicList upload returned non-JSON output: {proc.stdout[:200]}") from exc

    if not data.get("success"):
        raise UploadError(f"PicList upload failed: {json.dumps(data, ensure_ascii=False)[:500]}")

    urls: list[str] = []
    result = data.get("result")
    if isinstance(result, list):
        urls.extend(str(item) for item in result if isinstance(item, str) and item.startswith("http"))
    for item in data.get("fullResult", []) or []:
        if isinstance(item, dict):
            url_value = item.get("imgUrl") or item.get("url")
            if isinstance(url_value, str) and url_value.startswith("http"):
                urls.append(url_value)
    urls = list(dict.fromkeys(urls))
    if len(urls) < expected_count:
        raise UploadError("PicList upload succeeded but did not return enough image URLs.")
    return UploadResult(evidence=format_uploaded_evidence(urls), provider=provider)


def upload_with_piclist_server(images: list[Path], catalog: dict[str, Any]) -> UploadResult | None:
    return upload_json_with_piclist_server(
        catalog,
        {"list": [str(path) for path in images]},
        expected_count=len(images),
        provider="PicList server",
    )


def upload_clipboard_with_piclist_server(catalog: dict[str, Any]) -> UploadResult | None:
    return upload_json_with_piclist_server(
        catalog,
        {},
        expected_count=1,
        provider="PicList server clipboard",
    )


def upload_with_picgo_cli(images: list[Path], catalog: dict[str, Any]) -> UploadResult | None:
    command = configured_upload_command(catalog, images)
    provider = "configured uploader"
    if command is None:
        picgo = shutil.which("picgo")
        if not picgo:
            return None
        config_path = catalog.get("image_uploader", {}).get("picgo_config")
        command = [picgo]
        if config_path:
            command.extend(["-c", str(Path(str(config_path)).expanduser())])
        command.extend(["upload", *[str(path) for path in images]])
        provider = "PicGo CLI"

    proc = run(command)
    output = "\n".join(part for part in [proc.stdout, proc.stderr] if part)
    if proc.returncode != 0:
        raise UploadError(f"{provider} failed: {output.strip()}")
    urls = parse_upload_urls(output)
    if len(urls) < len(images):
        raise UploadError(f"{provider} did not return enough image URLs. Output: {output[:500]}")
    return UploadResult(evidence=format_uploaded_evidence(urls), provider=provider)


def upload_images(paths: list[str], catalog: dict[str, Any]) -> UploadResult:
    if not paths:
        return UploadResult()
    images = validate_image_paths(paths)

    uploaders = [upload_with_piclist_server, upload_with_picgo_cli]
    if has_configured_upload_command(catalog):
        uploaders = [upload_with_picgo_cli, upload_with_piclist_server]

    errors: list[str] = []
    for uploader in uploaders:
        try:
            result = uploader(images, catalog)
            if result:
                return result
        except UploadError as exc:
            errors.append(str(exc))
            continue

    if errors:
        raise UploadError("; ".join(errors))

    raise UploadError(
        "No image uploader found. Start PicList with local server enabled, or install/configure PicGo CLI with "
        "`npm install -g picgo && picgo set uploader`, or set `image_uploader.command` in assets/catalog.json."
    )


def upload_clipboard_image(catalog: dict[str, Any]) -> UploadResult:
    try:
        result = upload_clipboard_with_piclist_server(catalog)
        if result:
            return result
    except UploadError:
        raise

    raise UploadError(
        "No clipboard image uploader found. Start PicList with local server enabled, then copy an image to the "
        "system clipboard."
    )


def merge_upload_result(base: UploadResult, extra: UploadResult) -> UploadResult:
    providers = [provider for provider in [base.provider, extra.provider] if provider]
    return UploadResult(
        evidence=[*base.evidence, *extra.evidence],
        provider=", ".join(providers) if providers else None,
        warnings=[*base.warnings, *extra.warnings],
    )


SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("authorization", re.compile(r"authorization\s*[:：=]\s*(?:bearer\s+)?[^\s\n]+", re.IGNORECASE)),
    ("password", re.compile(r"(密码|password|passwd|pwd)\s*[:：=]\s*\S+", re.IGNORECASE)),
    ("token", re.compile(r"(token|secret|access[_-]?key|api[_-]?key)\s*[:：=]\s*\S+", re.IGNORECASE)),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}")),
]


def redact_sensitive(text: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    redacted = text.replace("\\n", "\n")
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(redacted):
            warnings.append(f"redacted possible {label}")
            redacted = pattern.sub(redact_match, redacted)

    # Dedicated, readable redaction for Chinese password lines.
    redacted = re.sub(r"(密码\s*[:：]\s*)[^\s\n]+", r"\1[REDACTED]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(账户\s*[:：]\s*)[^\s\n]+", r"\1见内部渠道", redacted, flags=re.IGNORECASE)
    return redacted, list(dict.fromkeys(warnings))


def redact_match(match: re.Match[str]) -> str:
    text = match.group(0)
    separator = re.search(r"[:：=]", text)
    if not separator:
        return "[REDACTED]"
    return text[: separator.end()] + " [REDACTED]"


def split_steps(note: str) -> list[str]:
    note = note.replace("\\n", "\n")
    lines = [line.strip(" -\t") for line in note.splitlines() if line.strip()]
    steps: list[str] = []
    in_steps = False
    for line in lines:
        if "复现" in line or "步骤" in line:
            in_steps = True
            content = re.sub(r"^.*?(复现步骤|步骤)\s*[:：]?\s*", "", line)
            if content:
                steps.append(content)
            continue
        if in_steps:
            if re.match(r"^(环境|情况描述|问题|实际|预期|评估|payload|preview|截图|日志)\s*[:：]", line, re.IGNORECASE):
                in_steps = False
            else:
                steps.append(re.sub(r"^\d+[.)、]\s*", "", line))
    if not steps:
        for line in lines:
            if any(secret.search(line) for _, secret in SECRET_PATTERNS):
                continue
            action_match = re.search(r"(创建|打开|点击|部署|变更|删除|重置|连接|扩容|添加|使用)[^。；;\n]*", line)
            if action_match:
                steps.append(action_match.group(0))
                break
    return steps[:6]


def extract_actual(note: str) -> str:
    note = note.replace("\\n", "\n")
    step_content = re.search(r"(?:复现步骤|步骤)\s*[:：]\s*(.+)", note, flags=re.IGNORECASE)
    if step_content:
        return normalize_text(step_content.group(1))

    patterns = [
        r"(?:实际结果|实际|结果|报错|情况描述|问题描述)\s*[:：]\s*(.+)",
        r"(?:导致|会|出现|提示|返回)\s*([^。；;\n]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, note, flags=re.IGNORECASE)
        if m:
            return normalize_text(m.group(1))
    return normalize_text(note.splitlines()[0] if note.splitlines() else note)[:120]


def make_summary(note: str, product: str | None) -> str:
    note = note.replace("\\n", "\n")
    actual = extract_actual(note)
    actual = re.sub(r"^(环境|复现步骤|情况描述|问题描述)\s*[:：]\s*", "", actual)
    actual = re.sub(r"[。.!！]+$", "", actual)
    actual = actual.replace("，", "，")
    actual = re.sub(r"\b(?:\d{1,3}\.){1,3}\d{1,3}(?:\.nip\.io)?\b", "", actual)
    actual = re.sub(r"\b\d{1,2}\.\d{1,3}\b", "", actual)

    # Remove leading product text if the tester already wrote it.
    if product:
        actual = re.sub(rf"^{re.escape(product)}[，,:：\s]+", "", actual, flags=re.IGNORECASE)

    # Remove known product aliases and filler evidence wording from compact tester notes.
    for token in ["maestro", "gpu maestro", "devbox", "applaunchpad", "对象存储", "镜像同步"]:
        actual = re.sub(rf"^\s*{re.escape(token)}\s*", "", actual, flags=re.IGNORECASE)
    actual = re.sub(r"(，|,)?\s*截图如下$", "", actual)
    actual = re.sub(r"^\s*[，,:：、-]+\s*", "", actual)
    actual = re.sub(r"报错提示，但", "报错但", actual)
    actual = actual.replace("使用数字开头命名应用", "数字开头应用名")

    if len(actual) > 46:
        actual = actual[:46].rstrip("，,、 ") + "..."
    return actual or "待补充问题现象"


def suggest_labels(note: str, issue_type: str, catalog: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    note_l = lower(note)
    allowed = set(catalog.get("labels", {}).get("allowed_on_create", []))
    never = set(catalog.get("labels", {}).get("never_add", []))
    if issue_type == "Bug" and "功能相关" in allowed and any(word in note_l for word in ["功能", "无法", "失败", "错误", "报错", "异常", "500"]):
        labels.append("功能相关")
    if "脚本" in note_l and "部署脚本" in allowed:
        labels.append("部署脚本")
    return [label for label in labels if label not in never]


def build_body(
    note: str,
    product: Inference,
    env: Inference,
    milestone: Inference,
    issue_type: Inference,
    priority: Inference,
    effort: Inference,
    evidence: list[str],
) -> tuple[str, list[str]]:
    redacted_note, warnings = redact_sensitive(note)
    steps = split_steps(redacted_note)
    actual = extract_actual(redacted_note)
    expected = "相关操作应成功完成，并给出与实际状态一致的反馈。"
    if issue_type.value == "Feature":
        expected = "应支持该场景，或给出清晰的产品限制说明。"

    lines = [
        "## 环境",
        "",
        f"- 环境：{env.value or '未确认'}",
        f"- 产品/模块：{product.value or '未确认'}",
        f"- 版本/批次：{milestone.value or '未确认'}",
        "",
        "## 问题描述",
        "",
        actual,
        "",
        "## 复现步骤",
        "",
    ]
    if steps:
        lines.extend(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    else:
        lines.append("1. 按测试描述中的路径操作。")
    lines.extend(
        [
            "",
            "## 实际结果",
            "",
            actual,
            "",
            "## 预期结果",
            "",
            expected,
            "",
            "## 影响判断",
            "",
            f"- Type: {issue_type.value}",
            f"- Priority: {priority.value}（{priority.reason}）",
            f"- Effort: {effort.value or '未评估'}",
            "",
            "## 证据",
            "",
        ]
    )
    if evidence:
        lines.extend(f"- {item}" for item in evidence)
    else:
        lines.append("- 暂无额外证据；如有截图、录屏、接口 payload/response，可追加到 issue。")

    lines.extend(["", "## 原始描述（已脱敏）", "", redacted_note])
    return "\n".join(lines).strip() + "\n", warnings


def build_catalog_suggestions(note: str, product: Inference, env: Inference, catalog: dict[str, Any]) -> list[str]:
    suggestions: list[str] = []
    if product.value is None:
        maybe_product = re.search(r"(?:产品|模块|页面)\s*[:：]\s*([^\s，,。；;]+)", note)
        if maybe_product:
            suggestions.append(f"new product candidate: {maybe_product.group(1)}")
    known_envs = {env_item["name"] for env_item in catalog.get("environments", [])}
    if env.value and env.value not in known_envs and env.confidence != "low":
        suggestions.append(f"new environment candidate: {env.value}")
    return suggestions


def draft_issue(
    note: str,
    catalog: dict[str, Any],
    repo: str | None = None,
    extra_evidence: list[str] | None = None,
) -> IssueDraft:
    product = first_match_from_catalog(note, catalog["products"])
    env = infer_environment(note, catalog)
    milestone = infer_milestone(note, catalog)
    issue_type = infer_type(note)
    priority = infer_priority(note, catalog)
    effort = infer_effort(note)
    evidence = extract_evidence(note)
    if extra_evidence:
        evidence.extend(extra_evidence)
        evidence = list(dict.fromkeys(evidence))
    body, warnings = build_body(note, product, env, milestone, issue_type, priority, effort, evidence)
    summary = make_summary(note, product.value)
    title_product = product.value or "未确认产品"
    title = catalog.get("title_format", "{product}: {summary}").format(product=title_product, summary=summary)
    title = title.replace("，", ": ", 1) if "，" in title.split(":")[0] else title
    labels = suggest_labels(note, issue_type.value or "Bug", catalog)
    suggestions = build_catalog_suggestions(note, product, env, catalog)
    return IssueDraft(
        repo=repo or catalog["default_repo"],
        title=title,
        body=body,
        product=product,
        environment=env,
        issue_type=issue_type,
        priority=priority,
        effort=effort,
        milestone=milestone,
        labels=labels,
        evidence=evidence,
        sensitive_warnings=warnings,
        catalog_suggestions=suggestions,
    )


def preflight(repo: str, catalog: dict[str, Any], project_owner: str | None = None, project_number: int | None = None) -> int:
    ok = True
    print(f"Repo: {repo}")
    gh = shutil.which("gh")
    if not gh:
        print("FAIL gh: GitHub CLI not found. Install with `brew install gh` on macOS.")
        return 1
    print(f"OK gh: {gh}")

    auth = run(["gh", "auth", "status"])
    if auth.returncode != 0:
        print("FAIL auth: `gh auth status` failed.")
        print(auth.stderr.strip() or auth.stdout.strip())
        print("Run `gh auth login`.")
        ok = False
    else:
        print("OK auth: logged in")

    labels = run(["gh", "api", f"repos/{repo}/labels", "--paginate", "--jq", ".[].name"])
    if labels.returncode != 0:
        print("WARN labels: could not read repo labels")
        print(labels.stderr.strip())
    else:
        names = set(labels.stdout.splitlines())
        print(f"OK labels: {', '.join(sorted(names))}")
        for bad in ["P0", "P1", "P2"]:
            if bad in names:
                print(f"NOTE label `{bad}` exists historically; this skill will not add it.")

    milestones = run(["gh", "api", f"repos/{repo}/milestones", "--jq", ".[].title"])
    if milestones.returncode == 0:
        print(f"OK milestones: {', '.join(milestones.stdout.splitlines()) or 'none'}")
    else:
        print("WARN milestones: could not read milestones")

    if project_owner and project_number:
        project = run(["gh", "project", "field-list", str(project_number), "--owner", project_owner, "--format", "json"])
        if project.returncode == 0:
            print("OK project fields: readable")
        else:
            print("WARN project fields: not readable")
            print((project.stderr or project.stdout).strip())
            print("Run `gh auth refresh -s project` or the exact scope requested by gh.")
            ok = False
    else:
        print("SKIP project fields: no project owner/number configured")

    print()
    preflight_uploader(catalog)

    return 0 if ok else 2


def preflight_uploader(catalog: dict[str, Any]) -> bool:
    ok = False
    server = piclist_server(catalog)
    if server:
        key_status = "with server key" if server.get("key") else "without server key"
        print(f"OK PicList config: server enabled at {server['host']}:{server['port']} ({key_status})")
        ok = True
    elif piclist_config_path(catalog):
        print("WARN PicList config: found, but local server is not enabled")
    else:
        print("SKIP PicList config: not found")

    if has_configured_upload_command(catalog):
        print(f"OK configured uploader: {catalog['image_uploader']['command']}")
        ok = True
    else:
        print("SKIP configured uploader: image_uploader.command not set")

    picgo = shutil.which("picgo")
    if picgo:
        print(f"OK PicGo CLI: {picgo}")
        ok = True
    else:
        print("SKIP PicGo CLI: not found on PATH")

    if not ok:
        print("Image upload setup needed:")
        print("- PicList: enable Settings > Server and keep PicList running, or")
        print("- PicGo CLI: `npm install -g picgo && picgo set uploader`, or")
        print("- Configure `image_uploader.command` in assets/catalog.json.")
    return ok


def issue_node_id(issue_url: str) -> str | None:
    proc = run(["gh", "issue", "view", issue_url, "--json", "id", "--jq", ".id"])
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def create_issue(draft: IssueDraft) -> str:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as body_file:
        body_file.write(draft.body)
        body_path = body_file.name

    cmd = ["gh", "issue", "create", "-R", draft.repo, "--title", draft.title, "--body-file", body_path]
    for label in draft.labels:
        cmd.extend(["--label", label])
    if draft.milestone.value:
        cmd.extend(["--milestone", draft.milestone.value])

    try:
        proc = run(cmd)
    finally:
        os.unlink(body_path)

    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    return proc.stdout.strip()


def repo_parts(repo: str) -> tuple[str, str]:
    if "/" not in repo:
        raise ValueError(f"repo must be OWNER/NAME, got {repo}")
    owner, name = repo.split("/", 1)
    return owner, name


def issue_number_from_url(issue_url: str) -> int | None:
    match = re.search(r"/issues/(\d+)", issue_url)
    return int(match.group(1)) if match else None


def repository_issue_metadata(repo: str, issue_number: int | None = None) -> dict[str, Any]:
    owner, name = repo_parts(repo)
    if issue_number:
        query = """
        query($owner:String!,$name:String!,$number:Int!){
          repository(owner:$owner,name:$name){
            id
            issue(number:$number){ id viewerCanSetFields issueType { id name } }
            issueTypes(first:20){ nodes{ id name } }
            issueFields(first:50){
              nodes{
                __typename
                ... on IssueFieldSingleSelect { id name dataType options { id name } }
                ... on IssueFieldText { id name dataType }
                ... on IssueFieldNumber { id name dataType }
                ... on IssueFieldDate { id name dataType }
              }
            }
          }
        }
        """
        proc = run(["gh", "api", "graphql", "-f", f"query={query}", "-f", f"owner={owner}", "-f", f"name={name}", "-F", f"number={issue_number}"])
    else:
        query = """
        query($owner:String!,$name:String!){
          repository(owner:$owner,name:$name){
            id
            issueTypes(first:20){ nodes{ id name } }
            issueFields(first:50){
              nodes{
                __typename
                ... on IssueFieldSingleSelect { id name dataType options { id name } }
                ... on IssueFieldText { id name dataType }
                ... on IssueFieldNumber { id name dataType }
                ... on IssueFieldDate { id name dataType }
              }
            }
          }
        }
        """
        proc = run(["gh", "api", "graphql", "-f", f"query={query}", "-f", f"owner={owner}", "-f", f"name={name}"])
    data = parse_json_output(proc, "repository metadata query")
    return data["data"]["repository"]


def update_issue_type(issue_id: str, issue_type_id: str) -> None:
    query = """
    mutation($issue:ID!,$type:ID!){
      updateIssue(input:{id:$issue, issueTypeId:$type}) { issue { id } }
    }
    """
    proc = run(["gh", "api", "graphql", "-f", f"query={query}", "-f", f"issue={issue_id}", "-f", f"type={issue_type_id}"])
    parse_json_output(proc, "update issue type")


def native_field_option_id(field: dict[str, Any], value: str) -> str | None:
    for option in field.get("options", []) or []:
        if str(option.get("name", "")).casefold() == value.casefold():
            return option.get("id")
    return None


def set_native_issue_field(issue_id: str, field: dict[str, Any], value: str) -> tuple[bool, str]:
    field_id = field.get("id")
    field_name_value = field.get("name", "field")
    if not field_id:
        return False, f"{field_name_value} has no field id"

    field_input = {"fieldId": field_id}
    data_type = str(field.get("dataType") or "").upper()
    if data_type == "SINGLE_SELECT" or field.get("options"):
        selected = native_field_option_id(field, value)
        if not selected:
            return False, f"{field_name_value} has no option `{value}`"
        field_input["singleSelectOptionId"] = selected
    elif data_type == "NUMBER":
        try:
            field_input["numberValue"] = float(value)
        except ValueError:
            return False, f"{field_name_value} expects a number, got `{value}`"
    elif data_type == "DATE":
        field_input["dateValue"] = value
    else:
        field_input["textValue"] = value

    query = """
    mutation($issue:ID!,$fields:[IssueFieldCreateOrUpdateInput!]!){
      setIssueFieldValue(input:{issueId:$issue, issueFields:$fields}) { issue { id } }
    }
    """
    proc = run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-f",
            f"issue={issue_id}",
            "-F",
            f"fields={json.dumps([field_input], ensure_ascii=False)}",
        ]
    )
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()
    return True, field_name_value


def github_priority_value(priority: str | None, catalog: dict[str, Any]) -> str | None:
    if not priority:
        return None
    mapping = catalog.get("field_options", {}).get("priority_to_github", {})
    return mapping.get(priority, priority)


def github_effort_value(effort: str | None, catalog: dict[str, Any]) -> str | None:
    if not effort:
        return None
    mapping = catalog.get("field_options", {}).get("effort_to_github", {})
    return mapping.get(effort, effort)


def apply_native_issue_metadata(draft: IssueDraft, issue_url: str, catalog: dict[str, Any]) -> NativeMetadataResult:
    number = issue_number_from_url(issue_url)
    if number is None:
        raise RuntimeError(f"could not parse issue number from {issue_url}")
    metadata = repository_issue_metadata(draft.repo, number)
    issue = metadata.get("issue") or {}
    issue_id = issue.get("id")
    if not issue_id:
        raise RuntimeError("metadata query did not return issue id")

    result = NativeMetadataResult()
    desired_type = draft.issue_type.value
    if desired_type:
        issue_type = next(
            (item for item in metadata.get("issueTypes", {}).get("nodes", []) if item.get("name", "").casefold() == desired_type.casefold()),
            None,
        )
        if issue_type and issue_type.get("id"):
            try:
                update_issue_type(issue_id, issue_type["id"])
                result.updated.append(f"Type={desired_type}")
            except RuntimeError as exc:
                result.skipped.append(f"Type: {exc}")
        else:
            result.skipped.append(f"Type: option `{desired_type}` not found")

    fields = metadata.get("issueFields", {}).get("nodes", [])
    field_values = {
        "Priority": github_priority_value(draft.priority.value, catalog),
        "Effort": github_effort_value(draft.effort.value, catalog),
    }
    for field_name_value, value in field_values.items():
        if not value:
            result.skipped.append(f"{field_name_value}: no value")
            continue
        field = next((item for item in fields if item.get("name", "").casefold() == field_name_value.casefold()), None)
        if not field:
            result.skipped.append(f"{field_name_value}: field not found")
            continue
        ok, message = set_native_issue_field(issue_id, field, value)
        if ok:
            result.updated.append(f"{field_name_value}={value}")
        else:
            result.skipped.append(f"{field_name_value}: {message}")
    return result


def first_id(data: Any, preferred_prefixes: tuple[str, ...] = ()) -> str | None:
    if isinstance(data, dict):
        value = data.get("id")
        if isinstance(value, str):
            if not preferred_prefixes or value.startswith(preferred_prefixes):
                return value
        for child in data.values():
            found = first_id(child, preferred_prefixes)
            if found:
                return found
    if isinstance(data, list):
        for child in data:
            found = first_id(child, preferred_prefixes)
            if found:
                return found
    return None


def parse_json_output(proc: subprocess.CompletedProcess[str], context: str) -> Any:
    if proc.returncode != 0:
        raise RuntimeError(f"{context} failed: {(proc.stderr or proc.stdout).strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{context} returned non-JSON output: {proc.stdout[:200]}") from exc


def project_field_list(owner: str, number: int) -> list[dict[str, Any]]:
    proc = run(["gh", "project", "field-list", str(number), "--owner", owner, "--format", "json"])
    data = parse_json_output(proc, "gh project field-list")
    fields = data.get("fields") if isinstance(data, dict) else data
    if not isinstance(fields, list):
        raise RuntimeError("gh project field-list JSON did not include a fields list")
    return fields


def field_name(field: dict[str, Any]) -> str:
    return str(field.get("name") or field.get("Name") or "")


def field_kind(field: dict[str, Any]) -> str:
    return str(field.get("type") or field.get("dataType") or field.get("__typename") or "").upper()


def find_field(fields: list[dict[str, Any]], aliases: list[str]) -> dict[str, Any] | None:
    alias_set = {alias.casefold() for alias in aliases}
    for field in fields:
        if field_name(field).casefold() in alias_set:
            return field
    return None


def option_id(field: dict[str, Any], value: str) -> str | None:
    for option in field.get("options", []) or []:
        if str(option.get("name", "")).casefold() == value.casefold():
            return option.get("id")
    return None


def set_project_field(
    *,
    project_id: str,
    item_id: str,
    field: dict[str, Any],
    value: str,
) -> tuple[bool, str]:
    field_id = field.get("id")
    if not field_id:
        return False, f"{field_name(field)} has no field id"

    kind = field_kind(field)
    cmd = [
        "gh",
        "project",
        "item-edit",
        "--id",
        item_id,
        "--project-id",
        project_id,
        "--field-id",
        field_id,
    ]
    if "SINGLE_SELECT" in kind or field.get("options"):
        selected = option_id(field, value)
        if not selected:
            return False, f"{field_name(field)} has no option `{value}`"
        cmd.extend(["--single-select-option-id", selected])
    elif "NUMBER" in kind:
        try:
            float(value)
        except ValueError:
            return False, f"{field_name(field)} expects a number, got `{value}`"
        cmd.extend(["--number", value])
    else:
        cmd.extend(["--text", value])

    proc = run(cmd)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()
    return True, field_name(field)


def apply_project_fields(draft: IssueDraft, issue_url: str, owner: str, number: int, catalog: dict[str, Any]) -> ProjectUpdateResult:
    view = parse_json_output(
        run(["gh", "project", "view", str(number), "--owner", owner, "--format", "json"]),
        "gh project view",
    )
    project_id = view.get("id") if isinstance(view, dict) else None
    if not project_id:
        raise RuntimeError("gh project view did not return a project id")

    item = parse_json_output(
        run(["gh", "project", "item-add", str(number), "--owner", owner, "--url", issue_url, "--format", "json"]),
        "gh project item-add",
    )
    item_id = first_id(item, ("PVTI_",)) or first_id(item)
    if not item_id:
        raise RuntimeError("gh project item-add did not return an item id")

    fields = project_field_list(owner, number)
    field_aliases = catalog.get("project_fields", {})
    values = {
        "priority": draft.priority.value,
        "type": draft.issue_type.value,
        "effort": draft.effort.value,
        "product": draft.product.value,
        "environment": draft.environment.value,
    }
    result = ProjectUpdateResult(item_url=issue_url)
    for key, value in values.items():
        if not value:
            result.skipped.append(f"{key}: no value")
            continue
        field = find_field(fields, field_aliases.get(key, [key]))
        if not field:
            result.skipped.append(f"{key}: field not found")
            continue
        ok, message = set_project_field(project_id=project_id, item_id=item_id, field=field, value=value)
        if ok:
            result.updated.append(f"{field_name(field)}={value}")
        else:
            result.skipped.append(f"{key}: {message}")
    return result


def format_inference(name: str, item: Inference) -> str:
    return f"- {name}: {item.value or '未确认'} ({item.confidence}; {item.reason})"


def print_preview(draft: IssueDraft) -> None:
    print("# Issue Preview")
    print()
    print(f"Repo: {draft.repo}")
    print(f"Title: {draft.title}")
    print()
    print("## Fields")
    print(format_inference("Product", draft.product))
    print(format_inference("Environment", draft.environment))
    print(format_inference("Type", draft.issue_type))
    print(format_inference("Priority", draft.priority))
    print(format_inference("Effort", draft.effort))
    print(format_inference("Milestone", draft.milestone))
    print(f"- Labels: {', '.join(draft.labels) if draft.labels else 'none'}")
    print()
    if draft.sensitive_warnings:
        print("## Sensitive Info")
        for warning in draft.sensitive_warnings:
            print(f"- {warning}")
        print()
    if draft.catalog_suggestions:
        print("## Catalog Suggestions")
        for suggestion in draft.catalog_suggestions:
            print(f"- {suggestion}")
        print()
    print("## Body")
    print()
    print(draft.body)


def learn_catalog(draft: IssueDraft, catalog: dict[str, Any], source_url: str | None = None) -> bool:
    changed = False
    today = date.today().isoformat()
    if draft.environment.value:
        known = {item["name"] for item in catalog.get("environments", [])}
        if draft.environment.value not in known and draft.environment.confidence != "low":
            catalog.setdefault("environments", []).append(
                {
                    "name": draft.environment.value,
                    "aliases": [draft.environment.value],
                    "source": source_url or "manual",
                    "added": today,
                }
            )
            changed = True
    if changed:
        save_catalog(catalog)
    return changed


def note_from_args(args: argparse.Namespace) -> str:
    if args.note:
        return args.note
    if args.note_file:
        return Path(args.note_file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Provide --note, --note-file, or stdin.")


def main(argv: list[str] | None = None) -> int:
    catalog = load_catalog()
    parser = argparse.ArgumentParser(description="Draft or create Sealos QA GitHub issues.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pre = sub.add_parser("preflight", help="Check gh, auth, repo labels, milestones, and optional project fields.")
    p_pre.add_argument("--repo", default=catalog["default_repo"])
    p_pre.add_argument("--project-owner", default=catalog.get("default_project", {}).get("owner"))
    p_pre.add_argument("--project-number", type=int, default=catalog.get("default_project", {}).get("number"))

    p_draft = sub.add_parser("draft", help="Draft an issue from a tester note.")
    p_draft.add_argument("--note")
    p_draft.add_argument("--note-file")
    p_draft.add_argument("--repo", default=catalog["default_repo"])
    p_draft.add_argument("--image", action="append", default=[], help="Local screenshot/image path. Repeat for multiple files.")
    p_draft.add_argument("--clipboard-image", action="store_true", help="Upload the current clipboard image through PicList server.")
    p_draft.add_argument("--upload-images", action="store_true", help="Upload --image files during dry-run preview.")
    p_draft.add_argument("--allow-local-image-placeholders", action="store_true", help="Create even if image upload fails; body will list placeholders.")
    p_draft.add_argument("--json", action="store_true", help="Print JSON instead of Markdown preview.")
    p_draft.add_argument("--create", action="store_true", help="Create the GitHub issue. Requires prior user confirmation.")
    p_draft.add_argument("--learn", action="store_true", help="Persist durable new catalog items after confirmation.")
    p_draft.add_argument("--project-owner", default=catalog.get("default_project", {}).get("owner"))
    p_draft.add_argument("--project-number", type=int, default=catalog.get("default_project", {}).get("number"))

    args = parser.parse_args(argv)
    if args.command == "preflight":
        return preflight(args.repo, catalog, args.project_owner, args.project_number)

    note = note_from_args(args)
    upload_result = UploadResult()
    image_evidence: list[str] = []
    if args.image:
        if args.create or args.upload_images:
            try:
                upload_result = upload_images(args.image, catalog)
                image_evidence = upload_result.evidence
            except UploadError as exc:
                if args.allow_local_image_placeholders:
                    image_evidence = image_placeholder_evidence(args.image)
                    upload_result.warnings.append(str(exc))
                else:
                    raise SystemExit(
                        f"Image upload failed: {exc}\n"
                        "Refusing to create an issue with local image paths. Fix the uploader or add "
                        "`--allow-local-image-placeholders` for a draft without uploaded images."
                    ) from exc
        else:
            image_evidence = image_placeholder_evidence(args.image)
    if args.clipboard_image:
        if args.create or args.upload_images:
            try:
                clipboard_upload_result = upload_clipboard_image(catalog)
                upload_result = merge_upload_result(upload_result, clipboard_upload_result)
                image_evidence.extend(clipboard_upload_result.evidence)
            except UploadError as exc:
                if args.allow_local_image_placeholders:
                    image_evidence.extend(clipboard_image_placeholder_evidence())
                    upload_result.warnings.append(str(exc))
                else:
                    raise SystemExit(
                        f"Clipboard image upload failed: {exc}\n"
                        "Refusing to create an issue without the clipboard image. Copy an image to the clipboard, "
                        "fix PicList server, or add `--allow-local-image-placeholders` for a draft without uploaded images."
                    ) from exc
        else:
            image_evidence.extend(clipboard_image_placeholder_evidence())
    draft = draft_issue(note, catalog, args.repo, extra_evidence=image_evidence)
    if args.json:
        payload = draft.__dict__.copy()
        payload["upload"] = upload_result.__dict__
        print(json.dumps(payload, default=lambda obj: obj.__dict__, ensure_ascii=False, indent=2))
    else:
        if upload_result.provider:
            print(f"Image upload: {upload_result.provider}")
            print()
        if upload_result.warnings:
            print("Image upload warnings:")
            for warning in upload_result.warnings:
                print(f"- {warning}")
            print()
        print_preview(draft)

    created_url = None
    if args.create:
        if draft.product.value is None or draft.environment.value is None:
            raise SystemExit("Refusing to create: product or environment is not confirmed.")
        created_url = create_issue(draft)
        print(f"\nCreated: {created_url}")
        try:
            native_result = apply_native_issue_metadata(draft, created_url, catalog)
            print("Native issue metadata updated:")
            for item in native_result.updated:
                print(f"- {item}")
            if native_result.skipped:
                print("Native issue metadata skipped:")
                for item in native_result.skipped:
                    print(f"- {item}")
        except RuntimeError as exc:
            print(f"Native issue metadata skipped: {exc}")
        if args.project_owner and args.project_number:
            try:
                project_result = apply_project_fields(draft, created_url, args.project_owner, args.project_number, catalog)
                print("Project fields updated:")
                for item in project_result.updated:
                    print(f"- {item}")
                if project_result.skipped:
                    print("Project fields skipped:")
                    for item in project_result.skipped:
                        print(f"- {item}")
            except RuntimeError as exc:
                print(f"Project update skipped: {exc}")
                print("Run `gh auth refresh -s project` or the exact scope requested by gh, then add fields manually or rerun project update.")
        else:
            print("Project update skipped: no --project-number configured.")

    if args.learn:
        changed = learn_catalog(draft, catalog, created_url)
        print(f"\nCatalog updated: {'yes' if changed else 'no'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
