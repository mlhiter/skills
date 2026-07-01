#!/usr/bin/env python3
"""Generate a read-only quarterly Feishu collaboration dashboard as HTML and JSON."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
REQUIRED_SCOPES = {
    "messages": ["search:message"],
    "calendar": ["calendar:calendar.event:read"],
    "docs": ["search:docs:read", "docx:document:readonly"],
}
DEFAULT_KEYWORDS = [
    "需求",
    "上线",
    "发布",
    "修复",
    "问题",
    "方案",
    "设计",
    "评审",
    "交付",
    "故障",
    "优化",
    "迁移",
    "自动化",
    "会议",
    "总结",
    "计划",
    "复盘",
    "风险",
]
MODULE_LABELS = {
    "docs": "飞书文档",
    "messages": "聊天消息",
    "calendar": "日历日程",
}
STATUS_LABELS = {
    "ok": "可用",
    "partial": "部分可用",
    "skipped": "未配置",
    "permission_denied": "权限不足",
    "not_configured": "未登录/未配置",
    "failed": "采集失败",
}
STATUS_TONE = {
    "ok": "good",
    "partial": "warn",
    "skipped": "idle",
    "permission_denied": "bad",
    "not_configured": "bad",
    "failed": "bad",
}


@dataclass
class CommandResult:
    ok: bool
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    json_data: Any | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Feishu quarterly collaboration dashboard.")
    parser.add_argument("--start", required=True, help="Start date, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date, YYYY-MM-DD")
    parser.add_argument("--period-label", default="", help="Display label, e.g. 2026 Q2")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--doc", action="append", default=[], help="Feishu doc URL or token. Repeatable.")
    parser.add_argument("--skip-doc-discovery", action="store_true", help="Disable Drive search based document discovery.")
    parser.add_argument("--skip-doc-reading", action="store_true", help="Only discover documents, do not fetch document content.")
    parser.add_argument("--doc-search-query", default="", help="Drive search query for document discovery. Empty string means filter-only browsing.")
    parser.add_argument("--doc-types", default="docx,doc,wiki", help="Comma-separated Drive doc types for discovery.")
    parser.add_argument("--doc-search-page-limit", type=int, default=5, help="Max Drive search pages for document discovery.")
    parser.add_argument("--doc-search-page-size", type=int, default=20, help="Drive search page size, max 20.")
    parser.add_argument("--doc-read-limit", type=int, default=12, help="Max discovered documents to fetch for content reading.")
    parser.add_argument("--message-query", action="append", default=[], help="Message search query. Repeatable. Empty string allowed.")
    parser.add_argument("--chat-id", action="append", default=[], help="Restrict messages to chat IDs. Repeatable or comma-separated.")
    parser.add_argument("--sender", action="append", default=[], help="Restrict messages to sender open_ids. Repeatable or comma-separated.")
    parser.add_argument("--chat-type", choices=["group", "p2p"], default="")
    parser.add_argument("--sender-type", choices=["user", "bot"], default="")
    parser.add_argument("--exclude-sender-type", choices=["user", "bot"], default="")
    parser.add_argument("--include-attachment-type", choices=["file", "image", "video", "link"], default="")
    parser.add_argument("--is-at-me", action="store_true")
    parser.add_argument("--message-page-limit", type=int, default=5)
    parser.add_argument("--message-page-size", type=int, default=50)
    parser.add_argument("--include-calendar", action="store_true", help="Collect calendar agenda.")
    parser.add_argument("--skip-calendar", action="store_true", help="Disable calendar collection.")
    parser.add_argument("--keyword", action="append", default=[], help="Extra keyword for docs/messages topic counting.")
    parser.add_argument("--save-raw", action="store_true", help="Save raw lark-cli outputs under raw/.")
    parser.add_argument(
        "--attempt-with-missing-scopes",
        action="store_true",
        help="Attempt module commands even when auth scopes preflight suggests missing scopes.",
    )
    return parser.parse_args()


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def iso_now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def compact_list(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        for piece in str(value).split(","):
            clean = piece.strip()
            if clean and clean not in seen:
                seen.add(clean)
                out.append(clean)
    return out


def safe_filename(value: str, fallback: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return clean[:80] or fallback


def json_from_text(text: str) -> Any | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def run_command(args: list[str], timeout: int = 90) -> CommandResult:
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    data = json_from_text(proc.stdout) or json_from_text(proc.stderr)
    return CommandResult(
        ok=proc.returncode == 0,
        args=args,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        json_data=data,
    )


def write_raw(raw_dir: Path | None, name: str, result: CommandResult) -> None:
    if raw_dir is None:
        return
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "args": result.args,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "json": result.json_data,
    }
    (raw_dir / f"{safe_filename(name, 'command')}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def walk(value: Any) -> list[Any]:
    items = [value]
    if isinstance(value, dict):
        for child in value.values():
            items.extend(walk(child))
    elif isinstance(value, list):
        for child in value:
            items.extend(walk(child))
    return items


def find_dicts(value: Any, predicate: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for item in walk(value):
        if isinstance(item, dict) and predicate(item):
            found.append(item)
    return found


def extract_missing_scopes(data: Any, fallback: list[str] | None = None) -> list[str]:
    scopes: list[str] = []
    for item in walk(data):
        if isinstance(item, dict):
            for key, value in item.items():
                lowered = str(key).lower()
                if lowered in {"scope", "scopes", "missing_scope", "missing_scopes", "required_scope", "required_scopes"}:
                    if isinstance(value, str):
                        scopes.extend(re.split(r"[\s,]+", value))
                    elif isinstance(value, list):
                        scopes.extend(str(v) for v in value)
                if lowered == "permission_violations":
                    scopes.extend(re.findall(r"[a-z][a-z0-9_.:-]+:[a-z0-9_.:-]+", json.dumps(value, ensure_ascii=False)))
        elif isinstance(item, str):
            scopes.extend(re.findall(r"[a-z][a-z0-9_.:-]+:[a-z0-9_.:-]+", item))
    if not scopes and fallback:
        scopes.extend(fallback)
    return sorted({scope.strip().strip('"') for scope in scopes if ":" in scope})


def error_message(result: CommandResult) -> str:
    data = result.json_data
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("hint") or data.get("message") or "").strip()
        if error:
            return str(error)
        if data.get("message"):
            return str(data["message"])
    return (result.stderr or result.stdout).strip()[:1000]


def classify_error(result: CommandResult, fallback_scopes: list[str] | None = None) -> dict[str, Any]:
    text = f"{result.stdout}\n{result.stderr}".lower()
    missing_scopes = extract_missing_scopes(result.json_data or f"{result.stdout}\n{result.stderr}", fallback_scopes)
    if "permission" in text or "scope" in text or missing_scopes:
        status = "permission_denied"
    elif "not login" in text or "unauthorized" in text or "auth" in text or "token" in text:
        status = "not_configured"
    else:
        status = "failed"
    return {
        "ok": False,
        "status": status,
        "error": error_message(result),
        "missing_scopes": missing_scopes,
        "hint": authorization_hint(missing_scopes, status),
        "returncode": result.returncode,
    }


def authorization_hint(scopes: list[str], status: str = "permission_denied") -> str:
    if scopes:
        joined = " ".join(scopes)
        return f'lark-cli auth login --scope "{joined}" --no-wait --json'
    if status == "not_configured":
        return "先运行 lark-cli config init 和 lark-cli auth login 完成飞书配置。"
    return "检查飞书开发者后台 scope，并用 lark-cli auth login --scope 做用户增量授权。"


def collect_auth_scopes(lark_cli: str | None, raw_dir: Path | None) -> dict[str, Any]:
    if not lark_cli:
        return {
            "ok": False,
            "status": "not_configured",
            "user_scopes": [],
            "error": "lark-cli not found in PATH",
            "missing_scopes": [],
        }
    result = run_command([lark_cli, "auth", "scopes", "--format", "json"], timeout=45)
    write_raw(raw_dir, "auth-scopes", result)
    if not result.ok:
        detail = classify_error(result)
        return {"ok": False, "status": detail["status"], "user_scopes": [], "error": detail["error"], "missing_scopes": detail["missing_scopes"]}
    data = result.json_data if isinstance(result.json_data, dict) else {}
    scopes = data.get("userScopes") or data.get("user_scopes") or []
    return {
        "ok": True,
        "status": "ok",
        "app_id": data.get("appId") or data.get("app_id"),
        "brand": data.get("brand"),
        "token_type": data.get("tokenType") or data.get("token_type"),
        "user_scopes": sorted(str(scope) for scope in scopes),
    }


def missing_from_auth(auth: dict[str, Any], scopes: list[str]) -> list[str]:
    if not auth.get("ok"):
        return scopes
    current = set(auth.get("user_scopes") or [])
    return [scope for scope in scopes if scope not in current]


def strip_markup(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def infer_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        clean = strip_markup(line).strip("# ").strip()
        if clean:
            return clean[:120]
    return fallback


def keyword_counts(texts: list[str], keywords: list[str]) -> Counter[str]:
    counter: Counter[str] = Counter()
    joined = "\n".join(texts)
    for keyword in keywords:
        if keyword:
            counter[keyword] = joined.count(keyword)
    return Counter({key: value for key, value in counter.items() if value > 0})


def first_present(value: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in value and value.get(key) not in (None, ""):
            return value.get(key)
    return None


def discover_doc_item(item: dict[str, Any], index: int) -> dict[str, Any]:
    meta = item.get("result_meta") if isinstance(item.get("result_meta"), dict) else {}
    title = (
        first_present(item, ["title", "name", "docs_token_title", "title_highlighted"])
        or first_present(meta, ["title", "name"])
        or f"发现文档 {index}"
    )
    doc_type = (
        first_present(item, ["doc_type", "docType", "type", "file_type", "fileType"])
        or first_present(meta, ["doc_type", "docType", "type", "file_type", "fileType"])
        or ""
    )
    url = first_present(item, ["url", "link", "web_url", "webUrl"]) or first_present(meta, ["url", "link", "web_url", "webUrl"])
    token = (
        first_present(item, ["token", "file_token", "fileToken", "obj_token", "objToken", "doc_token", "docToken"])
        or first_present(meta, ["token", "file_token", "fileToken", "obj_token", "objToken", "doc_token", "docToken"])
    )
    edit_time = (
        first_present(item, ["edit_time_iso", "update_time_iso", "modified_time_iso", "my_edit_time_iso"])
        or first_present(meta, ["edit_time_iso", "update_time_iso", "modified_time_iso", "my_edit_time_iso"])
        or first_present(item, ["edit_time", "update_time", "modified_time", "my_edit_time"])
    )
    create_time = (
        first_present(item, ["create_time_iso", "created_time_iso"])
        or first_present(meta, ["create_time_iso", "created_time_iso"])
        or first_present(item, ["create_time", "created_time"])
    )
    summary = strip_markup(str(first_present(item, ["summary", "summary_highlighted", "snippet"]) or first_present(meta, ["summary", "summary_highlighted", "snippet"]) or ""))
    return {
        "title": strip_markup(str(title)),
        "doc_type": str(doc_type).lower() if doc_type else "",
        "url": url,
        "token": token,
        "edit_time": str(edit_time or ""),
        "create_time": str(create_time or ""),
        "summary": summary[:260],
        "raw_id": first_present(item, ["id", "document_id", "documentId", "file_id", "fileId"]) or token or url or f"discovered-{index}",
    }


def docs_status(discovery: dict[str, Any], reading: dict[str, Any]) -> str:
    statuses = {discovery.get("status"), reading.get("status")}
    if "ok" in statuses:
        if any(status in {"permission_denied", "not_configured", "failed"} for status in statuses):
            return "partial"
        return "ok"
    if "partial" in statuses:
        return "partial"
    for status in ("permission_denied", "not_configured", "failed"):
        if status in statuses:
            return status
    return "skipped"


def collect_docs(args: argparse.Namespace, lark_cli: str | None, auth: dict[str, Any], raw_dir: Path | None, keywords: list[str], start: dt.date, end: dt.date) -> dict[str, Any]:
    module = {
        "ok": False,
        "status": "skipped",
        "label": MODULE_LABELS["docs"],
        "required_scopes": REQUIRED_SCOPES["docs"],
        "missing_scopes": [],
        "inputs": args.doc,
        "discovered": [],
        "documents": [],
        "errors": [],
        "discovery": {
            "ok": False,
            "status": "skipped",
            "required_scopes": ["search:docs:read"],
            "missing_scopes": [],
            "results": [],
            "errors": [],
            "filters": {
                "query": args.doc_search_query,
                "edited_since": start.isoformat(),
                "edited_until": end.isoformat(),
                "doc_types": args.doc_types,
            },
            "hint": "自动发现已关闭。",
        },
        "reading": {
            "ok": False,
            "status": "skipped",
            "required_scopes": ["docx:document:readonly"],
            "missing_scopes": [],
            "documents": [],
            "errors": [],
            "hint": "没有可读取的文档。",
        },
        "totals": {"discovered": 0, "documents": 0, "characters": 0, "keyword_hits": 0},
    }
    if not lark_cli:
        module.update({"status": "not_configured", "error": "lark-cli not found in PATH", "hint": "安装并配置 lark-cli 后重试。"})
        module["discovery"].update({"status": "not_configured", "error": "lark-cli not found in PATH", "hint": "安装并配置 lark-cli 后重试。"})
        module["reading"].update({"status": "not_configured", "error": "lark-cli not found in PATH", "hint": "安装并配置 lark-cli 后重试。"})
        return module

    discovered: list[dict[str, Any]] = []
    discovery_errors: list[dict[str, Any]] = []
    if args.skip_doc_discovery:
        module["discovery"]["hint"] = "已按参数跳过文档发现。"
    else:
        preflight_missing = missing_from_auth(auth, ["search:docs:read"])
        if preflight_missing and not args.attempt_with_missing_scopes:
            module["discovery"].update(
                {
                    "status": "permission_denied",
                    "missing_scopes": preflight_missing,
                    "hint": authorization_hint(preflight_missing),
                    "error": "当前 user token 未包含文档搜索 scope，已跳过自动发现。",
                }
            )
        else:
            page_token = ""
            page_limit = max(1, min(args.doc_search_page_limit, 20))
            page_size = max(1, min(args.doc_search_page_size, 20))
            seen_discovered: set[str] = set()
            for page in range(1, page_limit + 1):
                cmd = [
                    lark_cli,
                    "drive",
                    "+search",
                    "--query",
                    args.doc_search_query,
                    "--edited-since",
                    start.isoformat(),
                    "--edited-until",
                    end.isoformat(),
                    "--doc-types",
                    args.doc_types,
                    "--page-size",
                    str(page_size),
                    "--format",
                    "json",
                    "--as",
                    "user",
                ]
                if page_token:
                    cmd.extend(["--page-token", page_token])
                result = run_command(cmd, timeout=90)
                write_raw(raw_dir, f"docs-discovery-{page}", result)
                if not result.ok:
                    detail = classify_error(result, ["search:docs:read"])
                    detail["page"] = page
                    discovery_errors.append(detail)
                    break
                data = result.json_data if isinstance(result.json_data, dict) else {}
                raw_results = data.get("results") if isinstance(data, dict) else []
                if not isinstance(raw_results, list):
                    raw_results = find_dicts(data, lambda item: bool(item.get("url") or item.get("token") or item.get("file_token") or item.get("doc_type")))
                for item in raw_results:
                    if not isinstance(item, dict):
                        continue
                    doc = discover_doc_item(item, len(discovered) + 1)
                    key = str(doc.get("url") or doc.get("token") or doc.get("raw_id"))
                    if key in seen_discovered:
                        continue
                    seen_discovered.add(key)
                    discovered.append(doc)
                if not data.get("has_more") or not data.get("page_token"):
                    break
                page_token = str(data.get("page_token"))
            module["discovery"].update(
                {
                    "ok": bool(discovered) and not discovery_errors,
                    "status": "partial" if discovered and discovery_errors else ("ok" if not discovery_errors else discovery_errors[0].get("status", "failed")),
                    "results": discovered,
                    "errors": discovery_errors,
                    "missing_scopes": sorted({scope for err in discovery_errors for scope in err.get("missing_scopes", [])} or set(preflight_missing)),
                    "hint": f"自动发现 {len(discovered)} 个季度文档候选。" if discovered else "未发现文档候选或权限不足。",
                }
            )
            if discovery_errors and not discovered:
                module["discovery"]["error"] = discovery_errors[0].get("error")

    read_inputs: list[dict[str, Any]] = []
    for doc in args.doc:
        read_inputs.append({"source": "manual", "input": doc, "title": doc})
    for doc in discovered:
        if len(read_inputs) >= max(0, args.doc_read_limit) + len(args.doc):
            break
        target = doc.get("url") or doc.get("token")
        if target and str(doc.get("doc_type") or "").lower() in {"", "doc", "docx", "wiki"}:
            read_inputs.append({"source": "discovered", "input": str(target), "title": doc.get("title"), "discovered": doc})

    documents: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if args.skip_doc_reading:
        module["reading"]["hint"] = "已按参数跳过文档内容读取。"
    elif not read_inputs:
        preflight_missing = missing_from_auth(auth, ["docx:document:readonly"])
        if preflight_missing:
            module["reading"].update(
                {
                    "status": "permission_denied",
                    "missing_scopes": preflight_missing,
                    "hint": authorization_hint(preflight_missing),
                    "error": "内容读取需要文档读取 scope；发现候选后会自动 fetch。",
                }
            )
        else:
            module["reading"]["hint"] = "没有手动文档，也没有发现可读取的 doc/docx/wiki 候选。"
    else:
        preflight_missing = missing_from_auth(auth, ["docx:document:readonly"])
        if preflight_missing and not args.attempt_with_missing_scopes:
            module["reading"].update(
                {
                    "status": "permission_denied",
                    "missing_scopes": preflight_missing,
                    "hint": authorization_hint(preflight_missing),
                    "error": "当前 user token 未包含文档内容读取 scope，已跳过 fetch。",
                }
            )
        else:
            for index, item in enumerate(read_inputs, start=1):
                doc = item["input"]
                result = run_command(
                    [lark_cli, "docs", "+fetch", "--doc", doc, "--doc-format", "markdown", "--format", "json", "--as", "user"],
                    timeout=90,
                )
                write_raw(raw_dir, f"docs-fetch-{index}", result)
                if not result.ok:
                    detail = classify_error(result, ["docx:document:readonly"])
                    detail["doc"] = doc
                    detail["source"] = item.get("source")
                    errors.append(detail)
                    continue
                data = result.json_data if isinstance(result.json_data, dict) else {}
                document = ((data.get("data") or {}).get("document") or {}) if isinstance(data, dict) else {}
                content = str(document.get("content") or "")
                plain = strip_markup(content)
                counts = keyword_counts([plain], keywords)
                documents.append(
                    {
                        "input": doc,
                        "source": item.get("source"),
                        "document_id": document.get("document_id") or document.get("documentId"),
                        "revision_id": document.get("revision_id") or document.get("revisionId"),
                        "title": infer_title(content, str(item.get("title") or f"文档 {index}")),
                        "characters": len(plain),
                        "keyword_hits": dict(counts.most_common()),
                        "excerpt": plain[:260],
                        "discovered": item.get("discovered"),
                    }
                )
            module["reading"].update(
                {
                    "ok": bool(documents) and not errors,
                    "status": "partial" if documents and errors else ("ok" if not errors else errors[0].get("status", "failed")),
                    "documents": documents,
                    "errors": errors,
                    "missing_scopes": sorted({scope for err in errors for scope in err.get("missing_scopes", [])} or set(preflight_missing)),
                    "hint": f"已读取 {len(documents)} 份文档内容。" if documents else "未能读取文档内容。",
                }
            )
            if errors and not documents:
                module["reading"]["error"] = errors[0].get("error")

    module["discovered"] = discovered
    module["documents"] = documents
    module["errors"] = [*discovery_errors, *errors]
    module["totals"] = {
        "discovered": len(discovered),
        "documents": len(documents),
        "characters": sum(int(doc.get("characters") or 0) for doc in documents),
        "keyword_hits": sum(sum((doc.get("keyword_hits") or {}).values()) for doc in documents),
    }
    module["missing_scopes"] = sorted(set((module["discovery"].get("missing_scopes") or []) + (module["reading"].get("missing_scopes") or [])))
    status = docs_status(module["discovery"], module["reading"])
    module["status"] = status
    module["ok"] = status in {"ok", "partial"}
    if documents and errors:
        module["ok"] = True
        module["status"] = "partial"
        module["hint"] = "文档发现或读取部分成功，失败项已列在权限缺口中。"
    elif documents:
        module["ok"] = True
        module["status"] = "ok"
        module["hint"] = "已完成文档发现和内容读取。"
    elif discovered:
        module["hint"] = "已发现文档候选，但内容读取未完成。"
    elif module["missing_scopes"]:
        module["hint"] = authorization_hint(module["missing_scopes"])
    else:
        module["hint"] = "未发现或未读取文档。"
    return module


def parse_any_datetime(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("date_time", "datetime", "timestamp", "start_time", "time", "date"):
            parsed = parse_any_datetime(value.get(key))
            if parsed:
                return parsed
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000
        return dt.datetime.fromtimestamp(number).astimezone()
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{13}", text):
        return dt.datetime.fromtimestamp(int(text) / 1000).astimezone()
    if re.fullmatch(r"\d{10}", text):
        return dt.datetime.fromtimestamp(int(text)).astimezone()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return dt.datetime.fromisoformat(text)
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def week_key(day: dt.date, start: dt.date) -> str:
    offset = max(0, (day - start).days)
    return f"W{offset // 7 + 1}"


def message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, dict):
        return strip_markup(json.dumps(content, ensure_ascii=False))
    return strip_markup(str(content or ""))


def sender_name(message: dict[str, Any]) -> str:
    sender = message.get("sender")
    if isinstance(sender, dict):
        return str(sender.get("name") or sender.get("id") or sender.get("open_id") or "")
    return str(sender or "")


def message_time(message: dict[str, Any]) -> dt.datetime | None:
    for key in ("create_time", "createTime", "created_at", "timestamp"):
        parsed = parse_any_datetime(message.get(key))
        if parsed:
            return parsed
    return None


def collect_messages(args: argparse.Namespace, lark_cli: str | None, auth: dict[str, Any], raw_dir: Path | None, start: dt.date, end: dt.date, keywords: list[str]) -> dict[str, Any]:
    chat_ids = compact_list(args.chat_id)
    senders = compact_list(args.sender)
    has_filter = bool(args.message_query or chat_ids or senders or args.chat_type or args.sender_type or args.exclude_sender_type or args.include_attachment_type or args.is_at_me)
    module = {
        "ok": False,
        "status": "skipped",
        "label": MODULE_LABELS["messages"],
        "required_scopes": REQUIRED_SCOPES["messages"],
        "missing_scopes": [],
        "filters": {
            "queries": args.message_query,
            "chat_ids": chat_ids,
            "senders": senders,
            "chat_type": args.chat_type,
            "sender_type": args.sender_type,
            "exclude_sender_type": args.exclude_sender_type,
            "include_attachment_type": args.include_attachment_type,
            "is_at_me": args.is_at_me,
        },
        "messages": [],
        "totals": {"messages": 0, "chats": 0, "senders": 0},
        "by_query": {},
        "by_chat": {},
        "by_type": {},
        "by_week": {},
        "keyword_hits": {},
        "errors": [],
    }
    if not has_filter:
        module["hint"] = '传入 --message-query、--chat-id 或 --sender 后可采集聊天证据；如需按时间全量搜索，可显式传 --message-query ""。'
        return module
    if not lark_cli:
        module.update({"status": "not_configured", "error": "lark-cli not found in PATH", "hint": "安装并配置 lark-cli 后重试。"})
        return module

    preflight_missing = missing_from_auth(auth, REQUIRED_SCOPES["messages"])
    if preflight_missing and not args.attempt_with_missing_scopes:
        module.update(
            {
                "status": "permission_denied",
                "missing_scopes": preflight_missing,
                "hint": authorization_hint(preflight_missing),
                "error": "当前 user token 未包含消息搜索 scope，已跳过真实查询。",
            }
        )
        return module

    queries = args.message_query or [""]
    messages: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    start_time = f"{start.isoformat()}T00:00:00+08:00"
    end_time = f"{end.isoformat()}T23:59:59+08:00"
    for index, query in enumerate(queries, start=1):
        cmd = [
            lark_cli,
            "im",
            "+messages-search",
            "--query",
            query,
            "--start",
            start_time,
            "--end",
            end_time,
            "--page-size",
            str(max(1, min(args.message_page_size, 50))),
            "--page-limit",
            str(max(1, min(args.message_page_limit, 40))),
            "--format",
            "json",
            "--as",
            "user",
            "--no-reactions",
        ]
        if chat_ids:
            cmd.extend(["--chat-id", ",".join(chat_ids)])
        if senders:
            cmd.extend(["--sender", ",".join(senders)])
        if args.chat_type:
            cmd.extend(["--chat-type", args.chat_type])
        if args.sender_type:
            cmd.extend(["--sender-type", args.sender_type])
        if args.exclude_sender_type:
            cmd.extend(["--exclude-sender-type", args.exclude_sender_type])
        if args.include_attachment_type:
            cmd.extend(["--include-attachment-type", args.include_attachment_type])
        if args.is_at_me:
            cmd.append("--is-at-me")
        result = run_command(cmd, timeout=120)
        write_raw(raw_dir, f"messages-search-{index}", result)
        if not result.ok:
            detail = classify_error(result, REQUIRED_SCOPES["messages"])
            detail["query"] = query
            errors.append(detail)
            continue
        found = find_dicts(result.json_data, lambda item: bool(item.get("message_id") or item.get("messageId")))
        for item in found:
            message_id = str(item.get("message_id") or item.get("messageId"))
            if message_id in seen:
                continue
            seen.add(message_id)
            created = message_time(item)
            text = message_text(item)
            messages.append(
                {
                    "message_id": message_id,
                    "query": query,
                    "chat_id": item.get("chat_id") or item.get("chatId"),
                    "chat_name": item.get("chat_name") or item.get("chatName") or item.get("chat_type") or "未知会话",
                    "msg_type": item.get("msg_type") or item.get("msgType") or "unknown",
                    "sender": sender_name(item),
                    "create_time": created.isoformat(timespec="seconds") if created else str(item.get("create_time") or ""),
                    "week": week_key(created.date(), start) if created else "未知",
                    "content_excerpt": text[:240],
                    "mentions": item.get("mentions") or [],
                    "thread_id": item.get("thread_id") or item.get("threadId"),
                }
            )

    texts = [msg["content_excerpt"] for msg in messages]
    by_query = Counter(msg["query"] if msg["query"] else "空关键词/过滤器" for msg in messages)
    by_chat = Counter(str(msg["chat_name"] or msg["chat_id"] or "未知会话") for msg in messages)
    by_type = Counter(str(msg["msg_type"] or "unknown") for msg in messages)
    by_week = Counter(str(msg["week"]) for msg in messages)
    module.update(
        {
            "messages": sorted(messages, key=lambda item: item.get("create_time") or "", reverse=True)[:80],
            "errors": errors,
            "totals": {"messages": len(messages), "chats": len(by_chat), "senders": len({msg.get("sender") for msg in messages if msg.get("sender")})},
            "by_query": dict(by_query.most_common()),
            "by_chat": dict(by_chat.most_common(12)),
            "by_type": dict(by_type.most_common()),
            "by_week": dict(sorted(by_week.items())),
            "keyword_hits": dict(keyword_counts(texts, keywords).most_common()),
            "missing_scopes": sorted({scope for err in errors for scope in err.get("missing_scopes", [])} or set(preflight_missing)),
        }
    )
    if messages and errors:
        module["ok"] = True
        module["status"] = "partial"
        module["hint"] = "部分消息查询成功，失败查询已列出。"
    elif messages or not errors:
        module["ok"] = True
        module["status"] = "ok"
        module["hint"] = "已完成消息搜索。"
    else:
        first = errors[0]
        module["status"] = first.get("status", "failed")
        module["error"] = first.get("error")
        module["hint"] = first.get("hint")
    return module


def calendar_title(event: dict[str, Any]) -> str:
    for key in ("summary", "title", "subject", "name"):
        if event.get(key):
            return str(event[key])
    return "未命名日程"


def calendar_start(event: dict[str, Any]) -> dt.datetime | None:
    for key in ("start_time", "startTime", "start", "start_at", "startAt"):
        parsed = parse_any_datetime(event.get(key))
        if parsed:
            return parsed
    return None


def calendar_end(event: dict[str, Any]) -> dt.datetime | None:
    for key in ("end_time", "endTime", "end", "end_at", "endAt"):
        parsed = parse_any_datetime(event.get(key))
        if parsed:
            return parsed
    return None


def event_category(title: str) -> str:
    lower = title.lower()
    if any(word in title for word in ("站会", "例会", "周会", "晨会", "daily", "weekly")) or "standup" in lower:
        return "例会节奏"
    if any(word in title for word in ("评审", "review", "方案", "设计")):
        return "评审讨论"
    if any(word in title for word in ("需求", "产品", "prd")):
        return "需求产品"
    if any(word in title for word in ("1:1", "one-on-one", "同步", "沟通")):
        return "同步沟通"
    if any(word in title for word in ("发布", "上线", "排期", "复盘", "故障")):
        return "交付运维"
    return "其他日程"


def collect_calendar(args: argparse.Namespace, lark_cli: str | None, auth: dict[str, Any], raw_dir: Path | None, start: dt.date, end: dt.date) -> dict[str, Any]:
    module = {
        "ok": False,
        "status": "skipped",
        "label": MODULE_LABELS["calendar"],
        "required_scopes": REQUIRED_SCOPES["calendar"],
        "missing_scopes": [],
        "events": [],
        "totals": {"events": 0, "hours": 0.0, "meeting_days": 0},
        "by_week": {},
        "by_category": {},
        "hint": "传入 --include-calendar 后读取主日历季度日程。",
    }
    if args.skip_calendar or not args.include_calendar:
        return module
    if not lark_cli:
        module.update({"status": "not_configured", "error": "lark-cli not found in PATH", "hint": "安装并配置 lark-cli 后重试。"})
        return module

    preflight_missing = missing_from_auth(auth, REQUIRED_SCOPES["calendar"])
    if preflight_missing and not args.attempt_with_missing_scopes:
        module.update(
            {
                "status": "permission_denied",
                "missing_scopes": preflight_missing,
                "hint": authorization_hint(preflight_missing),
                "error": "当前 user token 未包含日程读取 scope，已跳过真实查询。",
            }
        )
        return module

    result = run_command(
        [lark_cli, "calendar", "+agenda", "--start", start.isoformat(), "--end", end.isoformat(), "--format", "json", "--as", "user"],
        timeout=120,
    )
    write_raw(raw_dir, "calendar-agenda", result)
    if not result.ok:
        detail = classify_error(result, REQUIRED_SCOPES["calendar"])
        module.update(detail)
        return module

    event_dicts = find_dicts(
        result.json_data,
        lambda item: bool(item.get("event_id") or item.get("eventId") or item.get("summary") or item.get("title"))
        and any(key in item for key in ("start_time", "startTime", "start", "start_at", "startAt", "time")),
    )
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, event in enumerate(event_dicts, start=1):
        title = calendar_title(event)
        started = calendar_start(event) or parse_any_datetime(event.get("time"))
        ended = calendar_end(event)
        event_id = str(event.get("event_id") or event.get("eventId") or f"event-{index}")
        key = f"{event_id}-{started.isoformat() if started else index}"
        if key in seen:
            continue
        seen.add(key)
        duration = 0.0
        if started and ended and ended > started:
            duration = round((ended - started).total_seconds() / 3600, 2)
        events.append(
            {
                "event_id": event_id,
                "title": title,
                "start": started.isoformat(timespec="seconds") if started else "",
                "end": ended.isoformat(timespec="seconds") if ended else "",
                "week": week_key(started.date(), start) if started else "未知",
                "category": event_category(title),
                "duration_hours": duration,
            }
        )
    by_week = Counter(event["week"] for event in events)
    by_category = Counter(event["category"] for event in events)
    days = {event["start"][:10] for event in events if event.get("start")}
    module.update(
        {
            "ok": True,
            "status": "ok",
            "events": sorted(events, key=lambda item: item.get("start") or "")[:160],
            "totals": {"events": len(events), "hours": round(sum(event["duration_hours"] for event in events), 1), "meeting_days": len(days)},
            "by_week": dict(sorted(by_week.items())),
            "by_category": dict(by_category.most_common()),
            "hint": "已读取主日历日程。",
        }
    )
    return module


def build_metrics(modules: dict[str, dict[str, Any]], keywords: list[str]) -> dict[str, Any]:
    accessible = sum(1 for module in modules.values() if module.get("status") in {"ok", "partial"})
    blocked = sum(1 for module in modules.values() if module.get("status") in {"permission_denied", "not_configured", "failed"})
    skipped = sum(1 for module in modules.values() if module.get("status") == "skipped")
    docs = modules["docs"]
    messages = modules["messages"]
    calendar = modules["calendar"]
    merged_keywords = Counter()
    for doc in docs.get("documents", []):
        merged_keywords.update(doc.get("keyword_hits") or {})
    merged_keywords.update(messages.get("keyword_hits") or {})
    return {
        "documents_read": int(docs.get("totals", {}).get("documents") or 0),
        "documents_discovered": int(docs.get("totals", {}).get("discovered") or 0),
        "document_characters": int(docs.get("totals", {}).get("characters") or 0),
        "message_hits": int(messages.get("totals", {}).get("messages") or 0),
        "message_chats": int(messages.get("totals", {}).get("chats") or 0),
        "calendar_events": int(calendar.get("totals", {}).get("events") or 0),
        "calendar_hours": float(calendar.get("totals", {}).get("hours") or 0),
        "accessible_modules": accessible,
        "blocked_modules": blocked,
        "skipped_modules": skipped,
        "keyword_topics": len([key for key in keywords if merged_keywords.get(key, 0) > 0]),
        "top_keywords": dict(merged_keywords.most_common(10)),
    }


def leader_insights(metrics: dict[str, Any], modules: dict[str, dict[str, Any]]) -> list[str]:
    insights: list[str] = []
    if metrics["accessible_modules"]:
        insights.append(f"本次飞书面板已接入 {metrics['accessible_modules']} 个协作数据模块，可用于补充 GitHub 之外的过程证据。")
    else:
        insights.append("当前飞书授权覆盖较少，本次面板主要明确数据边界和下一步授权清单，避免把无权限误读为无产出。")
    if metrics.get("documents_discovered"):
        insights.append(f"飞书文档模块发现 {metrics['documents_discovered']} 个季度文档候选，其中已读取 {metrics['documents_read']} 份内容。")
    elif metrics["documents_read"]:
        insights.append(f"读取 {metrics['documents_read']} 份季度文档，累计约 {metrics['document_characters']} 个文本字符，可沉淀为需求、方案、复盘等书面证据。")
    if metrics["message_hits"]:
        insights.append(f"消息搜索命中 {metrics['message_hits']} 条，覆盖 {metrics['message_chats']} 个会话，可用于回看跨团队沟通和问题推进线索。")
    if metrics["calendar_events"]:
        insights.append(f"日历读取 {metrics['calendar_events']} 个日程，累计约 {metrics['calendar_hours']} 小时，可观察季度会议节奏和评审/同步投入。")
    blocked = [MODULE_LABELS[name] for name, module in modules.items() if module.get("status") in {"permission_denied", "not_configured", "failed"}]
    if blocked:
        insights.append(f"仍有 {len(blocked)} 个模块未完整接入：{'、'.join(blocked)}；补齐后可形成更完整的季度协作画像。")
    if len(insights) < 3:
        insights.append("建议下一步补充关键文档 URL、重点群聊 ID 和消息关键词，让飞书侧面板从覆盖率诊断升级为完整证据面板。")
    return insights[:5]


def metric_card(value: Any, label: str, hint: str) -> str:
    return f"""
      <div class="metric">
        <div class="metric-value">{esc(value)}</div>
        <div class="metric-label">{esc(label)}</div>
        <div class="metric-hint">{esc(hint)}</div>
      </div>
    """


def status_badge(status: str) -> str:
    tone = STATUS_TONE.get(status, "idle")
    return f'<span class="status status-{tone}">{esc(STATUS_LABELS.get(status, status))}</span>'


def bar_rows(counter: dict[str, int] | Counter[str], empty: str = "暂无数据", limit: int = 10) -> str:
    items = list(Counter(counter).most_common(limit))
    if not items:
        return f'<p class="empty">{esc(empty)}</p>'
    max_value = max(value for _, value in items) or 1
    rows = []
    for name, value in items:
        width = max(4, round(value / max_value * 100))
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-name">{esc(name)}</div>
              <div class="bar-track"><span style="width:{width}%"></span></div>
              <div class="bar-value">{esc(value)}</div>
            </div>
            """
        )
    return "\n".join(rows)


def week_chart(counter: dict[str, int], start: dt.date, end: dt.date) -> str:
    total_weeks = ((end - start).days // 7) + 1
    values = {f"W{i}": int(counter.get(f"W{i}", 0)) for i in range(1, total_weeks + 1)}
    max_value = max(values.values() or [0]) or 1
    bars = []
    for key, value in values.items():
        height = max(5, round(value / max_value * 100)) if value else 5
        bars.append(f'<div class="week-bar"><i style="height:{height}%"></i><span>{esc(key)}</span></div>')
    return f'<div class="week-chart">{"".join(bars)}</div>'


def module_cards(modules: dict[str, dict[str, Any]]) -> str:
    cards = []
    for name in ("docs", "messages", "calendar"):
        module = modules[name]
        missing = module.get("missing_scopes") or []
        hint = module.get("hint") or module.get("error") or ""
        if name == "docs":
            discovery = module.get("discovery") or {}
            reading = module.get("reading") or {}
            hint = f"发现：{STATUS_LABELS.get(str(discovery.get('status')), discovery.get('status'))}；读取：{STATUS_LABELS.get(str(reading.get('status')), reading.get('status'))}。{hint}"
        cards.append(
            f"""
            <div class="module-card module-{STATUS_TONE.get(module.get('status'), 'idle')}">
              <div class="module-top">
                <strong>{esc(module.get('label'))}</strong>
                {status_badge(str(module.get('status')))}
              </div>
              <p>{esc(hint)}</p>
              <div class="scope-list">{''.join(f'<code>{esc(scope)}</code>' for scope in missing) or '<span>无缺失 scope 记录</span>'}</div>
            </div>
            """
        )
    return "\n".join(cards)


def evidence_list(items: list[dict[str, Any]], kind: str) -> str:
    if not items:
        return '<p class="empty">暂无可展示证据。</p>'
    rows = []
    for item in items[:12]:
        if kind == "doc":
            rows.append(
                f"""
                <article class="evidence-card">
                  <div class="evidence-title">{esc(item.get('title'))}</div>
                  <p>{esc(item.get('excerpt'))}</p>
                  <div class="evidence-meta">字符 {esc(item.get('characters'))} · revision {esc(item.get('revision_id') or '-')} · {esc(item.get('document_id') or item.get('input'))}</div>
                </article>
                """
            )
        elif kind == "message":
            rows.append(
                f"""
                <article class="evidence-card">
                  <div class="evidence-title">{esc(item.get('chat_name'))} · {esc(item.get('sender') or '未知发送人')}</div>
                  <p>{esc(item.get('content_excerpt'))}</p>
                  <div class="evidence-meta">{esc(item.get('create_time'))} · {esc(item.get('msg_type'))} · {esc(item.get('message_id'))}</div>
                </article>
                """
            )
        else:
            rows.append(
                f"""
                <article class="evidence-card">
                  <div class="evidence-title">{esc(item.get('title'))}</div>
                  <p>{esc(item.get('category'))} · {esc(item.get('duration_hours'))} 小时</p>
                  <div class="evidence-meta">{esc(item.get('start'))} · {esc(item.get('event_id'))}</div>
                </article>
                """
            )
    return "\n".join(rows)


def doc_discovery_list(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="empty">暂无发现候选。缺少 <code>search:docs:read</code> 时这里会为空。</p>'
    rows = []
    for item in items[:18]:
        type_label = (item.get("doc_type") or "unknown").upper()
        title = item.get("title") or item.get("url") or item.get("token")
        link = item.get("url")
        title_html = f'<a href="{esc(link)}">{esc(title)}</a>' if link else esc(title)
        rows.append(
            f"""
            <article class="evidence-card">
              <div class="evidence-title">{title_html}</div>
              <p>{esc(item.get('summary') or '无摘要')}</p>
              <div class="evidence-meta">{esc(type_label)} · 编辑 {esc(item.get('edit_time') or '-')} · 创建 {esc(item.get('create_time') or '-')}</div>
            </article>
            """
        )
    return "\n".join(rows)


def doc_tabs(docs: dict[str, Any]) -> str:
    discovery = docs.get("discovery") or {}
    reading = docs.get("reading") or {}
    discovered = docs.get("discovered") or discovery.get("results") or []
    documents = docs.get("documents") or reading.get("documents") or []
    discovery_status = status_badge(str(discovery.get("status") or "skipped"))
    reading_status = status_badge(str(reading.get("status") or "skipped"))
    return f"""
      <div class="doc-tabs" data-tabs>
        <div class="tab-list" role="tablist" aria-label="飞书文档模块">
          <button class="tab-button is-active" type="button" role="tab" aria-selected="true" data-tab-target="discovery">文档发现 <span>{esc(len(discovered))}</span></button>
          <button class="tab-button" type="button" role="tab" aria-selected="false" data-tab-target="reading">内容读取 <span>{esc(len(documents))}</span></button>
        </div>
        <div class="tab-panel is-active" role="tabpanel" data-tab-panel="discovery">
          <div class="tab-summary">
            <div>{discovery_status}<strong>自动发现</strong></div>
            <p>{esc(discovery.get('hint') or '按季度时间窗口搜索飞书云空间文档候选。')}</p>
          </div>
          <div class="evidence-grid evidence-grid-2">{doc_discovery_list(discovered)}</div>
        </div>
        <div class="tab-panel" role="tabpanel" data-tab-panel="reading">
          <div class="tab-summary">
            <div>{reading_status}<strong>内容读取</strong></div>
            <p>{esc(reading.get('hint') or '对发现到或手动传入的 doc/docx/wiki 执行 docs +fetch。')}</p>
          </div>
          <div class="evidence-grid evidence-grid-2">{evidence_list(documents, "doc")}</div>
        </div>
      </div>
    """


def authorization_section(modules: dict[str, dict[str, Any]]) -> str:
    scopes: list[str] = []
    for module in modules.values():
        scopes.extend(module.get("missing_scopes") or [])
    unique = sorted(set(scopes))
    if not unique:
        return '<p class="empty">当前没有从采集结果中识别到明确缺失 scope。若数据仍偏少，请补充文档 URL、群聊 ID 或关键词后重跑。</p>'
    rows = []
    for scope in unique:
        rows.append(
            f"""
            <tr>
              <td><code>{esc(scope)}</code></td>
              <td><code>lark-cli auth login --scope "{esc(scope)}" --no-wait --json</code></td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead><tr><th>缺失 scope</th><th>建议的最小授权命令</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    """


def render_html(summary: dict[str, Any]) -> str:
    start = parse_date(summary["start"])
    end = parse_date(summary["end"])
    metrics = summary["metrics"]
    modules = summary["modules"]
    docs = modules["docs"]
    messages = modules["messages"]
    calendar = modules["calendar"]
    insights = leader_insights(metrics, modules)
    title = f"{summary['period_label']} 飞书协作面板".strip()
    top_keywords = metrics.get("top_keywords") or {}
    coverage_value = f"{metrics['accessible_modules']}/3"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #111827;
      --muted: #667085;
      --quiet: #8993a4;
      --line: #d9e0ea;
      --line-soft: #e8edf4;
      --canvas: #f3f0e8;
      --panel: #fffdfa;
      --panel-soft: #f8f5ee;
      --paper: #ffffff;
      --blue: #2656d9;
      --blue-deep: #123a8f;
      --teal: #0b7f79;
      --green: #147a52;
      --amber: #b06b1d;
      --red: #b83b45;
      --violet: #6950b8;
      --shadow-sm: 0 1px 2px rgba(17, 24, 39, 0.08);
      --shadow-md: 0 18px 46px rgba(36, 43, 58, 0.10);
      --radius: 8px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Noto Sans SC", sans-serif;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(17, 24, 39, 0.035) 1px, transparent 1px),
        linear-gradient(180deg, #faf8f2 0, var(--canvas) 430px, #eef2f6 100%);
      background-size: 40px 40px, auto;
      line-height: 1.7;
      font-variant-numeric: tabular-nums;
    }}
    a {{ color: var(--blue-deep); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .page {{ max-width: 1280px; margin: 0 auto; padding: 24px 22px 64px; }}
    .hero {{
      position: relative;
      overflow: hidden;
      padding: 22px 26px;
      background: var(--panel);
      border: 1px solid rgba(17, 24, 39, 0.10);
      border-radius: var(--radius);
      box-shadow: var(--shadow-md);
    }}
    .hero::before {{
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 7px;
      background: linear-gradient(180deg, var(--teal), var(--blue), var(--green));
    }}
    .hero-top {{ position: relative; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 18px; align-items: start; }}
    .kicker {{ margin: 0 0 8px; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }}
    h1 {{ margin: 0; font-size: clamp(32px, 4vw, 58px); line-height: .98; letter-spacing: 0; text-wrap: balance; }}
    h2 {{ margin: 0; font-size: 22px; line-height: 1.15; letter-spacing: 0; text-wrap: balance; }}
    h3 {{ margin: 0 0 12px; font-size: 15px; line-height: 1.35; letter-spacing: 0; }}
    .meta {{ color: var(--muted); font-size: 14px; }}
    .hero .meta {{ margin-top: 10px; max-width: 760px; }}
    .scope-pill {{
      min-height: 40px;
      display: inline-flex;
      align-items: center;
      padding: 8px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: #344054;
      background: var(--panel-soft);
      white-space: nowrap;
      font-size: 13px;
    }}
    .metrics {{
      position: relative;
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 0;
      margin-top: 18px;
      border-top: 1px solid var(--line);
      border-left: 1px solid var(--line);
      background: var(--paper);
    }}
    .metric {{ min-height: 122px; padding: 14px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }}
    .metric-value {{ font-size: clamp(28px, 3vw, 42px); font-weight: 820; color: var(--ink); line-height: 1; }}
    .metric-label {{ margin-top: 9px; font-weight: 720; }}
    .metric-hint {{ margin-top: 3px; color: var(--muted); font-size: 12px; line-height: 1.45; }}
    section {{
      margin-top: 16px;
      padding: 22px;
      background: rgba(255, 253, 250, 0.92);
      border: 1px solid rgba(17, 24, 39, 0.10);
      border-radius: var(--radius);
      box-shadow: var(--shadow-sm);
    }}
    .section-head {{ display: flex; justify-content: space-between; gap: 16px; align-items: baseline; flex-wrap: wrap; margin-bottom: 18px; }}
    .section-subtitle {{ color: var(--muted); font-size: 14px; margin: 0; max-width: 560px; }}
    .leader-grid {{ display: grid; grid-template-columns: minmax(300px, .85fr) minmax(420px, 1.15fr); gap: 16px; }}
    .panel-lite {{ padding: 18px; background: var(--panel-soft); border: 1px solid var(--line); border-radius: var(--radius); }}
    .insights {{ margin: 0; padding-left: 20px; }}
    .insights li {{ margin: 7px 0; }}
    .module-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .module-card {{ min-height: 154px; padding: 15px; border-radius: var(--radius); background: var(--paper); border: 1px solid var(--line-soft); box-shadow: 0 1px 2px rgba(17,24,39,.05); }}
    .module-good {{ box-shadow: inset 0 3px 0 var(--green), 0 1px 2px rgba(17,24,39,.05); }}
    .module-warn {{ box-shadow: inset 0 3px 0 var(--amber), 0 1px 2px rgba(17,24,39,.05); }}
    .module-bad {{ box-shadow: inset 0 3px 0 var(--red), 0 1px 2px rgba(17,24,39,.05); }}
    .module-idle {{ box-shadow: inset 0 3px 0 #aab3c2, 0 1px 2px rgba(17,24,39,.05); }}
    .module-top {{ display: flex; justify-content: space-between; gap: 10px; align-items: center; }}
    .module-card p {{ margin: 10px 0; color: var(--muted); font-size: 13px; line-height: 1.55; overflow-wrap: anywhere; }}
    .status {{ display: inline-flex; align-items: center; min-height: 24px; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 720; }}
    .status-good {{ color: #0f6b43; background: #e3f4ea; }}
    .status-warn {{ color: #7a4b0a; background: #fff0cc; }}
    .status-bad {{ color: #982f37; background: #fde9eb; }}
    .status-idle {{ color: #526071; background: #edf1f6; }}
    .scope-list {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; color: var(--quiet); font-size: 12px; }}
    code {{ max-width: 100%; padding: 2px 5px; background: #eef2f7; border-radius: 5px; color: #334155; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .92em; overflow-wrap: anywhere; word-break: break-word; }}
    .chart-grid {{ display: grid; grid-template-columns: minmax(340px, 1.15fr) minmax(300px, .85fr); gap: 16px; }}
    .chart-stack {{ display: grid; gap: 16px; }}
    .bar-chart {{ display: grid; gap: 10px; }}
    .bar-row {{ display: grid; grid-template-columns: minmax(140px, 220px) 1fr 48px; gap: 12px; align-items: center; }}
    .bar-name {{ min-width: 0; overflow-wrap: anywhere; font-size: 13px; }}
    .bar-track {{ height: 12px; background: #e5eaf2; border-radius: 999px; overflow: hidden; }}
    .bar-track span {{ display: block; height: 100%; background: linear-gradient(90deg, var(--teal), var(--blue)); border-radius: 999px; }}
    .bar-value {{ text-align: right; font-weight: 720; }}
    .week-chart {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(34px, 1fr)); gap: 8px; height: 172px; align-items: end; padding-top: 6px; }}
    .week-bar {{ min-width: 0; height: 100%; display: grid; grid-template-rows: 1fr auto; gap: 7px; align-items: end; }}
    .week-bar i {{ display: block; width: 100%; min-height: 5px; background: linear-gradient(180deg, var(--blue), var(--teal)); border-radius: 6px 6px 2px 2px; }}
    .week-bar span {{ color: var(--quiet); font-size: 10px; text-align: center; white-space: nowrap; }}
    .evidence-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .evidence-grid-2 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .evidence-column {{ display: grid; gap: 10px; align-content: start; }}
    .evidence-card {{ padding: 14px; background: var(--paper); border: 1px solid var(--line-soft); border-radius: var(--radius); box-shadow: 0 1px 2px rgba(17,24,39,.05); }}
    .evidence-title {{ font-weight: 760; line-height: 1.35; }}
    .evidence-card p {{ margin: 8px 0; color: #445065; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }}
    .evidence-meta {{ color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }}
    .doc-tabs {{ display: grid; gap: 12px; }}
    .tab-list {{ display: inline-flex; width: fit-content; max-width: 100%; gap: 4px; padding: 4px; border-radius: 999px; background: #eef2f7; border: 1px solid var(--line); overflow-x: auto; }}
    .tab-button {{ min-height: 36px; padding: 7px 12px; border: 0; border-radius: 999px; color: #526071; background: transparent; font: inherit; font-size: 13px; font-weight: 760; cursor: pointer; white-space: nowrap; transition-property: background-color, color, transform; transition-duration: 140ms; transition-timing-function: cubic-bezier(.16,1,.3,1); }}
    .tab-button span {{ margin-left: 6px; color: inherit; opacity: .72; }}
    .tab-button.is-active {{ color: var(--blue-deep); background: var(--paper); box-shadow: 0 1px 2px rgba(17,24,39,.10); }}
    .tab-button:active {{ transform: scale(.97); }}
    .tab-panel {{ display: none; }}
    .tab-panel.is-active {{ display: grid; gap: 12px; }}
    .tab-summary {{ display: flex; align-items: start; justify-content: space-between; gap: 14px; padding: 12px 14px; border-radius: var(--radius); background: var(--panel-soft); border: 1px solid var(--line); }}
    .tab-summary div {{ display: flex; align-items: center; gap: 8px; min-width: max-content; }}
    .tab-summary p {{ margin: 0; color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: var(--radius); background: var(--paper); }}
    table {{ width: 100%; border-collapse: collapse; min-width: 720px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line-soft); text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: var(--panel-soft); font-size: 12px; color: #475467; font-weight: 720; }}
    tr:last-child td {{ border-bottom: 0; }}
    .empty {{ color: var(--muted); }}
    .footer-note {{ margin-top: 18px; color: var(--muted); font-size: 13px; }}
    @media (max-width: 980px) {{
      .metrics {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .leader-grid, .chart-grid, .module-grid, .evidence-grid, .evidence-grid-2 {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 640px) {{
      .page {{ padding: 14px 10px 36px; }}
      .hero, section {{ padding: 16px; }}
      .hero-top {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 29px; }}
      h2 {{ font-size: 19px; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .metric {{ min-height: 130px; padding: 13px; }}
      .metric-value {{ font-size: 29px; }}
      .bar-row {{ grid-template-columns: 1fr 1fr 44px; }}
      .tab-list {{ width: 100%; }}
      .tab-button {{ flex: 1 0 auto; }}
      .tab-summary {{ display: grid; }}
      .week-chart {{ height: 180px; gap: 5px; }}
      .week-bar span {{ font-size: 9px; writing-mode: vertical-rl; justify-self: center; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header class="hero">
      <div class="hero-top">
        <div>
          <p class="kicker">Feishu Quarterly Collaboration Dashboard</p>
          <h1>{esc(title)}</h1>
          <div class="meta">范围：{esc(summary['start'])} 至 {esc(summary['end'])} · 生成：{esc(summary['generated_at'])}</div>
          <div class="meta">数据源：飞书文档、聊天消息搜索、主日历。模块独立采集，权限不足不影响页面生成。</div>
        </div>
        <div class="scope-pill">数据覆盖率 {esc(coverage_value)}</div>
      </div>
      <div class="metrics">
        {metric_card(coverage_value, "可用模块", "飞书模块覆盖率")}
        {metric_card(metrics["documents_discovered"], "发现文档", "Drive 搜索候选")}
        {metric_card(metrics["documents_read"], "读取文档", "已 fetch 的文档内容")}
        {metric_card(metrics["message_hits"], "消息命中", "搜索命中的聊天消息")}
        {metric_card(metrics["calendar_events"], "日程", "读取的季度日程")}
        {metric_card(metrics["blocked_modules"], "权限缺口", "被权限/配置挡住的模块")}
      </div>
    </header>

    <section>
      <div class="section-head">
        <h2>领导层摘要</h2>
        <p class="section-subtitle">优先呈现可证实协作事实，同时把未授权部分作为数据覆盖边界说明。</p>
      </div>
      <div class="leader-grid">
        <div class="panel-lite">
          <h3>本季度飞书协作信号</h3>
          <ol class="insights">{''.join(f'<li>{esc(item)}</li>' for item in insights)}</ol>
        </div>
        <div class="module-grid">
          {module_cards(modules)}
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>图表视图</h2>
        <p class="section-subtitle">用于快速判断飞书侧证据的结构、节奏和主题密度。</p>
      </div>
      <div class="chart-grid">
        <div class="panel-lite">
          <h3>主题词命中</h3>
          <div class="bar-chart">{bar_rows(top_keywords, "暂无主题词命中。传入文档或消息后这里会出现关键词结构。")}</div>
        </div>
        <div class="chart-stack">
          <div class="panel-lite">
            <h3>消息查询分布</h3>
            <div class="bar-chart">{bar_rows(messages.get("by_query") or {}, "暂无消息数据。")}</div>
          </div>
          <div class="panel-lite">
            <h3>日程类型结构</h3>
            <div class="bar-chart">{bar_rows(calendar.get("by_category") or {}, "暂无日历数据。")}</div>
          </div>
        </div>
      </div>
      <div class="chart-grid" style="margin-top:16px">
        <div class="panel-lite">
          <h3>日程周节奏</h3>
          {week_chart(calendar.get("by_week") or {}, start, end)}
        </div>
        <div class="panel-lite">
          <h3>会话分布</h3>
          <div class="bar-chart">{bar_rows(messages.get("by_chat") or {}, "暂无会话数据。")}</div>
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>证据抽样</h2>
        <p class="section-subtitle">保留可回查的文档、消息和日程线索，避免把统计数字变成无来源结论。</p>
      </div>
      {doc_tabs(docs)}
      <div class="evidence-grid" style="margin-top:16px">
        <div class="evidence-column">
          <h3>消息</h3>
          {evidence_list(messages.get("messages") or [], "message")}
        </div>
        <div class="evidence-column">
          <h3>日程</h3>
          {evidence_list(calendar.get("events") or [], "calendar")}
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>权限与口径</h2>
        <p class="section-subtitle">飞书权限少时，最重要的是把“未覆盖”标注清楚，后续可逐项补 scope 后重跑。</p>
      </div>
      {authorization_section(modules)}
      <p class="footer-note">口径：文档模块先用 Drive 搜索发现季度候选，再对可读取的 doc/docx/wiki 执行 docs +fetch；消息只按传入过滤器搜索，不等同完成事项；日历读取主日历日程，不包含视频会议妙记或任务。所有模块均为只读。</p>
    </section>
  </main>
  <script>
    document.querySelectorAll('[data-tabs]').forEach((root) => {{
      const buttons = Array.from(root.querySelectorAll('[data-tab-target]'));
      const panels = Array.from(root.querySelectorAll('[data-tab-panel]'));
      buttons.forEach((button) => {{
        button.addEventListener('click', () => {{
          const target = button.getAttribute('data-tab-target');
          buttons.forEach((item) => {{
            const active = item === button;
            item.classList.toggle('is-active', active);
            item.setAttribute('aria-selected', active ? 'true' : 'false');
          }});
          panels.forEach((panel) => {{
            panel.classList.toggle('is-active', panel.getAttribute('data-tab-panel') === target);
          }});
        }});
      }});
    }});
  </script>
</body>
</html>
"""


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    start = parse_date(args.start)
    end = parse_date(args.end)
    if end < start:
        raise ValueError("--end must be on or after --start")
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw" if args.save_raw else None
    lark_cli = shutil.which("lark-cli")
    keywords = list(dict.fromkeys([*DEFAULT_KEYWORDS, *args.keyword]))

    auth = collect_auth_scopes(lark_cli, raw_dir)
    modules = {
        "docs": collect_docs(args, lark_cli, auth, raw_dir, keywords, start, end),
        "messages": collect_messages(args, lark_cli, auth, raw_dir, start, end, keywords),
        "calendar": collect_calendar(args, lark_cli, auth, raw_dir, start, end),
    }
    metrics = build_metrics(modules, keywords)
    notes = []
    if not lark_cli:
        notes.append("未找到 lark-cli，飞书模块无法真实采集。")
    if not auth.get("ok"):
        notes.append(f"飞书授权状态不可用：{auth.get('error') or auth.get('status')}")
    if metrics["blocked_modules"]:
        notes.append("部分模块因权限或配置未接入，页面已列出最小授权建议。")
    if metrics["skipped_modules"]:
        notes.append("部分模块未配置输入或未开启，未纳入本次统计。")

    return {
        "kind": "quarterly-feishu-dashboard",
        "schema_version": SCHEMA_VERSION,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "period_label": args.period_label or f"{start.isoformat()}..{end.isoformat()}",
        "generated_at": iso_now(),
        "source": {"lark_cli": lark_cli, "auth": auth},
        "modules": modules,
        "metrics": metrics,
        "evidence": {
            "discovered_documents": modules["docs"].get("discovered", [])[:40],
            "documents": modules["docs"].get("documents", [])[:20],
            "messages": modules["messages"].get("messages", [])[:40],
            "calendar_events": modules["calendar"].get("events", [])[:40],
        },
        "notes": notes,
        "methodology": {
            "docs": "Discovers documents with drive +search by quarter edit window, then fetches manual or discovered doc/docx/wiki content with docs +fetch.",
            "messages": "Uses im +messages-search with explicit filters and date range; message hits are collaboration evidence, not completed work count.",
            "calendar": "Uses calendar +agenda for the primary calendar when --include-calendar is set.",
        },
    }


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    try:
        summary = build_summary(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "index.html").write_text(render_html(summary), encoding="utf-8")
    print(json.dumps({"ok": True, "output_dir": str(output_dir), "index": str(output_dir / "index.html"), "summary": str(output_dir / "summary.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
