#!/usr/bin/env python3
"""Generate a quarterly work dashboard from independent GitHub and Feishu summaries."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import html
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1

STATUS_LABELS = {
    "ok": "可用",
    "partial": "部分可用",
    "skipped": "未配置",
    "permission_denied": "权限不足",
    "not_configured": "未配置",
    "failed": "失败",
}

STATUS_TONE = {
    "ok": "good",
    "partial": "warn",
    "skipped": "idle",
    "permission_denied": "bad",
    "not_configured": "bad",
    "failed": "bad",
}

CHART_COLORS = [
    "#1f6feb",
    "#157b50",
    "#ae6817",
    "#6750b5",
    "#0f8f83",
    "#b83a45",
    "#647084",
    "#2656d9",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a combined quarterly work dashboard.")
    parser.add_argument("--github-summary", required=True, help="Path to quarterly-github-dashboard summary.json")
    parser.add_argument("--feishu-summary", required=True, help="Path to quarterly-feishu-dashboard summary.json")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--period-label", default="", help="Display period label, e.g. 2026 Q2")
    parser.add_argument("--github-index", default="", help="Optional path or URL to the GitHub dashboard index.html")
    parser.add_argument("--feishu-index", default="", help="Optional path or URL to the Feishu dashboard index.html")
    parser.add_argument("--annotations", default="", help="Optional JSON/YAML annotations for boss-facing wording and project notes.")
    return parser.parse_args()


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_json(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def load_annotations(path: str) -> dict[str, Any]:
    if not path:
        return {}
    annotation_path = Path(path).expanduser()
    text = annotation_path.read_text(encoding="utf-8")
    if annotation_path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ValueError("YAML annotations require PyYAML; use .json or install PyYAML.") from exc
        data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON/YAML object")
    return data


def apply_annotations(github: dict[str, Any], annotations: dict[str, Any]) -> dict[str, Any]:
    if not annotations:
        return github
    annotated = copy.deepcopy(github)
    project_annotations = annotations.get("projects") if isinstance(annotations.get("projects"), dict) else {}
    if project_annotations:
        portfolio = annotated.get("project_portfolio") or {}
        for group in ("new_repositories", "newly_active_projects", "interesting_projects", "projects"):
            projects = portfolio.get(group)
            if not isinstance(projects, list):
                continue
            filtered: list[dict[str, Any]] = []
            for project in projects:
                if not isinstance(project, dict):
                    continue
                repo = str(project.get("repo") or "")
                note = project_annotations.get(repo)
                if not isinstance(note, dict):
                    filtered.append(project)
                    continue
                if note.get("include") is False:
                    continue
                for source, target in (
                    ("display_name", "display_name"),
                    ("purpose", "purpose"),
                    ("business_impact", "business_impact"),
                    ("narrative", "narrative"),
                    ("theme", "theme"),
                    ("role", "role"),
                    ("customer_value", "customer_value"),
                    ("difficulty", "difficulty"),
                    ("highlight", "highlight"),
                    ("primary_value", "primary_value"),
                    ("value_confidence", "value_confidence"),
                    ("display_priority", "display_priority"),
                ):
                    if note.get(source):
                        project[target] = note[source]
                for source in ("tags", "signals", "value_attribution", "value_categories", "value_evidence", "outcomes"):
                    if isinstance(note.get(source), list):
                        project[source] = note[source]
                project["annotation"] = {k: v for k, v in note.items() if k != "include"}
                filtered.append(project)
            portfolio[group] = filtered
    annotated["manual_annotations"] = {
        "has_annotations": True,
        "project_overrides": sorted(str(key) for key in project_annotations.keys()),
    }
    return annotated


def iso_now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def pct_text(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return "0%"


def number(value: Any) -> int | float:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0


def fmt_num(value: Any) -> str:
    value = number(value)
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.1f}"
    return f"{int(value):,}"


def pct_ratio(numerator: Any, denominator: Any) -> str:
    denominator_value = number(denominator)
    if denominator_value <= 0:
        return "0%"
    return f"{number(numerator) / denominator_value * 100:.0f}%"


def confidence_level(ok: bool, partial: bool = False) -> str:
    if ok:
        return "high"
    if partial:
        return "medium"
    return "low"


def confidence_label(level: str) -> str:
    return {
        "high": "高可信",
        "medium": "中可信",
        "low": "需确认",
        "manual": "人工标注",
    }.get(level, level)


def metric_contract(label: str, value: Any, source: str, confidence: str, status: str = "ok", **extra: Any) -> dict[str, Any]:
    item = {
        "label": label,
        "value": value,
        "source": source,
        "confidence": confidence,
        "status": status,
    }
    item.update(extra)
    return item


def rel_link(path_or_url: str, current_output: Path) -> str:
    if not path_or_url:
        return ""
    if "://" in path_or_url or path_or_url.startswith("file:"):
        return path_or_url
    path = Path(path_or_url).expanduser()
    if not path.is_absolute():
        return path_or_url
    try:
        return Path(path).resolve().relative_to(current_output.resolve()).as_posix()
    except ValueError:
        return path.as_uri()


def infer_index(summary_path: str, explicit: str) -> str:
    if explicit:
        return explicit
    sibling = Path(summary_path).expanduser().resolve().with_name("index.html")
    return str(sibling) if sibling.exists() else ""


def module_status(module: dict[str, Any] | None) -> str:
    if not module:
        return "skipped"
    return str(module.get("status") or ("ok" if module.get("ok") else "failed"))


def status_badge(status: str) -> str:
    tone = STATUS_TONE.get(status, "idle")
    label = STATUS_LABELS.get(status, status)
    return f'<span class="status status-{tone}">{esc(label)}</span>'


def bar_width(value: Any, max_value: float) -> str:
    current = float(number(value))
    if max_value <= 0:
        return "0%"
    return f"{max(2, min(100, current / max_value * 100)):.1f}%"


def pct_float(part: Any, total: Any) -> float:
    total_value = float(number(total))
    if total_value <= 0:
        return 0.0
    return max(0.0, float(number(part)) / total_value * 100)


def format_pct(value: float) -> str:
    return f"{value:.0f}%"


def parse_pct(value: Any) -> float:
    text = str(value or "").strip().replace("%", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def short_label(value: Any, limit: int = 24) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)] + "…"


def formal_project_text(value: Any) -> str:
    return str(value or "").replace("有趣工作", "重点方向")


def parse_datetime(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text or text.startswith("0001-01-01"):
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(text)
    except ValueError:
        try:
            return dt.datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None


def item_date(item: dict[str, Any], *keys: str) -> dt.datetime | None:
    for key in keys:
        parsed = parse_datetime(item.get(key))
        if parsed:
            return parsed
    return None


def week_key(value: dt.datetime) -> str:
    year, week, _ = value.isocalendar()
    return f"{year}-W{week:02d}"


def project_bucket(project: dict[str, Any]) -> str:
    theme = str(project.get("theme") or project.get("purpose") or project.get("repo") or "").lower()
    repo = str(project.get("repo") or "").lower()
    haystack = f"{theme} {repo}"
    if any(token in haystack for token in ("devbox", "ide", "runtime")):
        return "DevBox / IDE"
    if any(token in haystack for token in ("registry", "offline", "kite", "infra", "install", "ops")):
        return "交付基础设施"
    if any(token in haystack for token in ("mspace", "maestro", "mbox", "orcai", "agent")):
        return "个人产品探索"
    if any(token in haystack for token in ("skill", "blog", "github.io", "doc", "workflow")):
        return "知识沉淀"
    if any(token in haystack for token in ("admin", "desktop", "account", "workspace", "tenant")):
        return "桌面与治理"
    return "其他推进"


def unique_strings(items: list[Any], limit: int = 8) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def project_haystack(project: dict[str, Any]) -> str:
    pieces: list[str] = []
    for key in ("repo", "name", "display_name", "purpose", "theme", "description", "narrative", "business_impact", "customer_value", "highlight"):
        if project.get(key):
            pieces.append(str(project.get(key)))
    for key in ("interesting_work", "tags", "signals"):
        value = project.get(key)
        if isinstance(value, list):
            pieces.extend(str(item) for item in value if item)
    for pr in project.get("representative_prs") or []:
        if isinstance(pr, dict) and pr.get("title"):
            pieces.append(str(pr.get("title")))
    return " ".join(pieces).lower()


def project_status_label(project: dict[str, Any]) -> str:
    if project.get("is_new_repo"):
        return "新建仓库"
    if project.get("is_newly_active"):
        return "新启动"
    return "持续项目"


def project_metric_text(project: dict[str, Any]) -> str:
    return (
        f"功能 {fmt_num(project.get('feature_points'))} / "
        f"修复 {fmt_num(project.get('bug_fixes'))} / "
        f"PR {fmt_num(project.get('merged_prs'))} / "
        f"Commit {fmt_num(project.get('commits'))}"
    )


def representative_pr_items(project: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for pr in project.get("representative_prs") or []:
        if not isinstance(pr, dict):
            continue
        key = (str(pr.get("url") or ""), str(pr.get("number") or pr.get("title") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(pr)
        if len(result) >= limit:
            break
    return result


def annotation_value_attribution(project: dict[str, Any]) -> list[dict[str, Any]]:
    annotation = project.get("annotation") if isinstance(project.get("annotation"), dict) else {}
    raw = project.get("value_attribution") or project.get("value_categories") or annotation.get("value_attribution") or annotation.get("value_categories")
    if not isinstance(raw, list):
        return []
    attrs: list[dict[str, Any]] = []
    evidence_default = project.get("value_evidence") or annotation.get("value_evidence") or []
    if not isinstance(evidence_default, list):
        evidence_default = [evidence_default] if evidence_default else []
    for idx, item in enumerate(raw):
        if isinstance(item, str):
            label = item
            attrs.append(
                {
                    "label": label,
                    "score": max(1, number(project.get("score"))) + (len(raw) - idx) * 2,
                    "basis": "人工 annotation 校准",
                    "evidence": [str(line) for line in evidence_default if line][:4],
                    "confidence": str(project.get("value_confidence") or annotation.get("value_confidence") or "manual"),
                    "source": "manual annotation",
                    "manual": True,
                }
            )
            continue
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("category") or item.get("value") or "").strip()
            if not label:
                continue
            evidence = item.get("evidence") if isinstance(item.get("evidence"), list) else evidence_default
            attrs.append(
                {
                    "label": label,
                    "score": number(item.get("score")) or (max(1, number(project.get("score"))) + (len(raw) - idx) * 2),
                    "basis": item.get("basis") or "人工 annotation 校准",
                    "evidence": [str(line) for line in evidence if line][:4],
                    "confidence": item.get("confidence") or project.get("value_confidence") or annotation.get("value_confidence") or "manual",
                    "source": "manual annotation",
                    "manual": True,
                }
            )
    return attrs[:3]


def infer_project_value_attribution(project: dict[str, Any]) -> list[dict[str, Any]]:
    """Infer leadership-facing value categories from existing project evidence only."""
    manual_attrs = annotation_value_attribution(project)
    if manual_attrs:
        return manual_attrs
    haystack = project_haystack(project)
    feature_points = number(project.get("feature_points"))
    bug_fixes = number(project.get("bug_fixes"))
    merged_prs = number(project.get("merged_prs"))
    commits = number(project.get("commits"))
    changed_files = number(project.get("changed_files"))
    score = number(project.get("score"))
    attrs: list[dict[str, Any]] = []

    def matches(tokens: list[str]) -> list[str]:
        return [token for token in tokens if token.lower() in haystack][:4]

    def add(label: str, base_score: float, tokens: list[str], metric_clues: list[str], basis: str) -> None:
        token_hits = matches(tokens)
        metric_clues = [str(clue) for clue in metric_clues if str(clue or "").strip()]
        if base_score <= 0 and not token_hits and not metric_clues:
            return
        evidence = []
        if token_hits:
            evidence.append("线索：" + "、".join(token_hits[:3]))
        evidence.extend(metric_clues[:3])
        attrs.append(
            {
                "label": label,
                "score": round(float(base_score) + len(token_hits) * 2.5, 1),
                "basis": basis,
                "evidence": evidence[:4],
                "confidence": "medium" if token_hits or metric_clues else "low",
                "source": "GitHub project portfolio presentation inference",
            }
        )

    add(
        "研发效率",
        commits * 0.08 + merged_prs * 1.4 + feature_points * 1.8,
        ["devbox", "ide", "runtime", "agent", "workspace", "coding", "workflow", "研发体验", "执行平台"],
        [text for value, text in ((commits, f"{fmt_num(commits)} commit"), (merged_prs, f"{fmt_num(merged_prs)} 个合并 PR")) if number(value) > 0],
        "仓库用途、主题和研发工具链关键词",
    )
    add(
        "稳定性与质量",
        bug_fixes * 4.0 + changed_files * 0.03,
        ["fix", "bug", "test", "quality", "stable", "stability", "observability", "ops", "测试", "质量", "稳定", "可观测", "运维"],
        [text for value, text in ((bug_fixes, f"{fmt_num(bug_fixes)} 个 Bug 修复"), (changed_files, f"{fmt_num(changed_files)} 个变更文件")) if number(value) > 0],
        "Bug 修复、测试质量和可观测线索",
    )
    add(
        "交付能力",
        feature_points * 4.2 + merged_prs * 1.8 + (5 if project.get("is_new_repo") else 0),
        ["offline", "registry", "install", "deploy", "release", "delivery", "私有化", "离线", "交付", "部署", "镜像"],
        [text for value, text in ((feature_points, f"{fmt_num(feature_points)} 个功能点"), (merged_prs, f"{fmt_num(merged_prs)} 个合并 PR")) if number(value) > 0],
        "功能交付、新项目和发布/离线链路线索",
    )
    add(
        "用户体验",
        feature_points * 1.2 + changed_files * 0.02,
        ["frontend", "ui", "ux", "desktop", "logo", "extension", "interaction", "前端", "交互", "桌面", "体验", "登录"],
        [text for value, text in ((feature_points, f"{fmt_num(feature_points)} 个功能点"), (changed_files, f"{fmt_num(changed_files)} 个变更文件")) if number(value) > 0],
        "前端、桌面、交互和体验相关线索",
    )
    add(
        "平台治理",
        merged_prs * 1.5 + commits * 0.04,
        ["permission", "auth", "account", "tenant", "admin", "policy", "kubernetes", "registry", "infra", "权限", "账号", "登录链路", "治理", "基础设施"],
        [text for value, text in ((commits, f"{fmt_num(commits)} commit"), (merged_prs, f"{fmt_num(merged_prs)} 个合并 PR")) if number(value) > 0],
        "权限、账号、基础设施和平台治理线索",
    )
    add(
        "知识沉淀",
        commits * 0.04 if matches(["skill", "doc", "docs", "readme", "blog", "knowledge", "summary", "文档", "知识", "工作流", "复用"]) else 0,
        ["skill", "doc", "docs", "readme", "blog", "knowledge", "summary", "文档", "知识", "工作流", "复用"],
        [f"{fmt_num(commits)} commit" if commits and matches(["skill", "doc", "docs", "readme", "blog", "knowledge", "summary", "文档", "知识", "工作流", "复用"]) else ""],
        "文档、skill、工作流和可复用资产线索",
    )

    if not attrs and score > 0:
        attrs.append(
            {
                "label": "交付能力",
                "score": round(float(score), 1),
                "basis": "本季度仓库活动",
                "evidence": [project_metric_text(project)],
                "confidence": "low",
                "source": "GitHub project activity score",
            }
        )
    attrs = sorted(attrs, key=lambda item: number(item.get("score")), reverse=True)
    return attrs[:3]


def build_project_value_attribution(projects: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    totals: dict[str, dict[str, Any]] = {}
    for project in sorted(projects, key=lambda item: number(item.get("score")), reverse=True):
        attrs = infer_project_value_attribution(project)
        if not attrs:
            continue
        metrics = {
            "score": number(project.get("score")),
            "feature_points": number(project.get("feature_points")),
            "bug_fixes": number(project.get("bug_fixes")),
            "commits": number(project.get("commits")),
            "merged_prs": number(project.get("merged_prs")),
            "changed_files": number(project.get("changed_files")),
        }
        row = {
            "repo": project.get("repo"),
            "name": project.get("display_name") or project.get("name") or project.get("repo"),
            "url": project.get("url") or "",
            "status": project_status_label(project),
            "theme": project.get("theme") or project_bucket(project),
            "purpose": project.get("purpose") or "",
            "primary_value": attrs[0].get("label"),
            "value_attribution": attrs,
            "metrics": metrics,
            "representative_prs": [
                {
                    "number": pr.get("number"),
                    "title": pr.get("title"),
                    "url": pr.get("url") or "",
                    "state": pr.get("state") or "",
                }
                for pr in representative_pr_items(project, 3)
            ],
        }
        rows.append(row)
        for attr in attrs:
            label = str(attr.get("label") or "")
            total = totals.setdefault(
                label,
                {
                    "label": label,
                    "score": 0.0,
                    "projects": 0,
                    "feature_points": 0,
                    "bug_fixes": 0,
                    "commits": 0,
                    "merged_prs": 0,
                    "changed_files": 0,
                    "sample_projects": [],
                },
            )
            total["score"] = round(float(number(total.get("score"))) + float(number(attr.get("score"))), 1)
            total["projects"] = number(total.get("projects")) + 1
            for metric_key in ("feature_points", "bug_fixes", "commits", "merged_prs", "changed_files"):
                total[metric_key] = number(total.get(metric_key)) + number(metrics.get(metric_key))
            total["sample_projects"] = unique_strings([*(total.get("sample_projects") or []), row["name"]], 4)
    category_totals = sorted(totals.values(), key=lambda item: (number(item.get("score")), number(item.get("projects"))), reverse=True)
    return rows[:36], category_totals


def project_display_priority(project: dict[str, Any]) -> float:
    priority = number(project.get("display_priority"))
    if priority:
        return float(priority) + float(number(project.get("score"))) * 0.01
    bonus = 0.0
    if project.get("annotation"):
        bonus += 60.0
    if project.get("business_impact") or project.get("customer_value"):
        bonus += 35.0
    if project.get("is_new_repo") or project.get("is_newly_active"):
        bonus += 18.0
    bonus += min(30.0, number(project.get("feature_points")) * 2 + number(project.get("bug_fixes")) * 1.5)
    return float(number(project.get("score"))) + bonus


def project_action_lines(project: dict[str, Any]) -> list[str]:
    outcomes = project.get("outcomes")
    if isinstance(outcomes, list) and outcomes:
        return unique_strings(outcomes, 4)
    lines: list[str] = []
    if project.get("highlight"):
        lines.append(str(project.get("highlight")))
    if number(project.get("feature_points")):
        lines.append(f"交付 {fmt_num(project.get('feature_points'))} 个功能点")
    if number(project.get("bug_fixes")):
        lines.append(f"完成 {fmt_num(project.get('bug_fixes'))} 个 Bug 修复")
    if number(project.get("changed_files")):
        lines.append(f"覆盖 {fmt_num(project.get('changed_files'))} 个变更文件")
    if number(project.get("merged_prs")):
        lines.append(f"合并 {fmt_num(project.get('merged_prs'))} 个 PR")
    if not lines and number(project.get("commits")):
        lines.append(f"形成 {fmt_num(project.get('commits'))} 次 commit")
    return unique_strings(lines, 4)


def build_project_profiles(projects: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for project in sorted(projects, key=project_display_priority, reverse=True)[:limit]:
        attrs = infer_project_value_attribution(project)
        pr_items = representative_pr_items(project, 3)
        annotation = project.get("annotation") if isinstance(project.get("annotation"), dict) else {}
        profiles.append(
            {
                "repo": project.get("repo"),
                "name": project.get("display_name") or project.get("name") or project.get("repo"),
                "url": project.get("url") or "",
                "status": project_status_label(project),
                "theme": project.get("theme") or project_bucket(project),
                "role": project.get("role") or annotation.get("role") or "",
                "difficulty": project.get("difficulty") or annotation.get("difficulty") or "",
                "purpose": project.get("purpose") or "",
                "actions": project_action_lines(project),
                "business_impact": project.get("business_impact") or "",
                "customer_value": project.get("customer_value") or "",
                "primary_value": attrs[0].get("label") if attrs else project.get("primary_value") or "",
                "value_attribution": attrs,
                "metrics": {
                    "score": number(project.get("score")),
                    "feature_points": number(project.get("feature_points")),
                    "bug_fixes": number(project.get("bug_fixes")),
                    "commits": number(project.get("commits")),
                    "merged_prs": number(project.get("merged_prs")),
                    "changed_files": number(project.get("changed_files")),
                },
                "representative_prs": [
                    {
                        "number": pr.get("number"),
                        "title": pr.get("title"),
                        "url": pr.get("url") or "",
                        "state": pr.get("state") or "",
                    }
                    for pr in pr_items
                ],
                "confidence": "manual" if annotation else ("medium" if attrs else "low"),
                "source": "manual annotation + GitHub portfolio" if annotation else "GitHub portfolio inference",
            }
        )
    return profiles


def build_quarter_change_map(github: dict[str, Any], projects: list[dict[str, Any]]) -> dict[str, Any]:
    comparison = github.get("comparison") or {}
    metrics = []
    for key in ("commits", "prs_merged", "prs_created", "active_repos", "prs_reviewed", "issues_closed_related"):
        item = comparison.get(key)
        if isinstance(item, dict):
            metrics.append(
                {
                    "key": key,
                    "label": item.get("label") or key,
                    "current": number(item.get("current")),
                    "previous": number(item.get("previous")),
                    "delta": number(item.get("delta")),
                    "pct": pct_text(item.get("pct")),
                    "direction": item.get("direction") or "flat",
                }
            )
    project_moves = []
    for project in sorted(projects, key=lambda item: number(item.get("score")), reverse=True)[:18]:
        attrs = infer_project_value_attribution(project)
        project_moves.append(
            {
                "repo": project.get("repo"),
                "name": project.get("display_name") or project.get("name") or project.get("repo"),
                "url": project.get("url") or "",
                "status": project_status_label(project),
                "score": number(project.get("score")),
                "primary_value": attrs[0].get("label") if attrs else "",
                "signal": "new_repo" if project.get("is_new_repo") else ("newly_active" if project.get("is_newly_active") else "sustained"),
            }
        )
    lanes = [
        {"label": "新增项目", "count": sum(1 for item in project_moves if item["signal"] == "new_repo")},
        {"label": "新启动", "count": sum(1 for item in project_moves if item["signal"] == "newly_active")},
        {"label": "持续高投入", "count": sum(1 for item in project_moves if item["signal"] == "sustained")},
    ]
    return {
        "metrics": metrics,
        "project_moves": project_moves,
        "lanes": lanes,
        "boundary": "项目层面变化基于本季度项目状态和强度推断；精确项目级环比需要上季度项目明细。",
    }


def build_data_quality(github: dict[str, Any], feishu: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    outcomes = github.get("engineering_outcomes") or {}
    coverage = outcomes.get("coverage") or {}
    code_total = number(coverage.get("merged_prs_total"))
    code_succeeded = number(coverage.get("code_stats_succeeded"))
    portfolio_total = number(((github.get("project_portfolio") or {}).get("totals") or {}).get("projects"))
    project_attrs = metrics.get("portfolio_projects")
    missing_scopes = collect_missing_scopes(feishu)
    feishu_accessible = number(metrics.get("feishu_accessible_modules"))
    return [
        {
            "label": "GitHub 事实",
            "value": 100 if github.get("kind") == "quarterly-github-dashboard" else 50,
            "status": "ok" if github.get("kind") == "quarterly-github-dashboard" else "partial",
            "text": "commit / PR / issue / review 来自 GitHub Search/API",
            "confidence": "high",
        },
        {
            "label": "PR 文件统计",
            "value": pct_float(code_succeeded, code_total) if code_total else 0,
            "status": "ok" if code_total and code_succeeded == code_total else "partial",
            "text": f"{fmt_num(code_succeeded)}/{fmt_num(code_total)} 个合并 PR",
            "confidence": confidence_level(bool(code_total) and code_succeeded == code_total, bool(coverage)),
        },
        {
            "label": "项目画像",
            "value": 100 if portfolio_total else 0,
            "status": "ok" if portfolio_total else "partial",
            "text": f"{fmt_num(project_attrs)} 个项目进入展示层",
            "confidence": confidence_level(bool(portfolio_total), bool(github.get("project_portfolio"))),
        },
        {
            "label": "飞书覆盖",
            "value": pct_float(feishu_accessible, 3),
            "status": "ok" if feishu_accessible == 3 else ("partial" if feishu_accessible else "permission_denied"),
            "text": f"{fmt_num(feishu_accessible)}/3 模块可用，{fmt_num(len(missing_scopes))} 个 scope 缺口",
            "confidence": "high" if feishu_accessible else "low",
        },
        {
            "label": "人工校准",
            "value": 100 if (github.get("manual_annotations") or {}).get("has_annotations") else 0,
            "status": "ok" if (github.get("manual_annotations") or {}).get("has_annotations") else "skipped",
            "text": "annotations 可覆盖价值类别、角色、结果和排序",
            "confidence": "manual" if (github.get("manual_annotations") or {}).get("has_annotations") else "low",
        },
    ]


def stacked_style(items: list[tuple[str, Any, str]]) -> str:
    total = sum(float(number(value)) for _, value, _ in items)
    if total <= 0:
        return "background:#e4eaf1"
    stops: list[str] = []
    cursor = 0.0
    for _, value, color in items:
        current = pct_float(value, total)
        if current <= 0:
            continue
        start = cursor
        cursor += current
        stops.append(f"{color} {start:.2f}% {cursor:.2f}%")
    return f"background:linear-gradient(90deg, {', '.join(stops)})" if stops else "background:#e4eaf1"


def conic_style(items: list[tuple[str, Any, str]]) -> str:
    total = sum(float(number(value)) for _, value, _ in items)
    if total <= 0:
        return "background:#e4eaf1"
    stops: list[str] = []
    cursor = 0.0
    for _, value, color in items:
        current = pct_float(value, total)
        if current <= 0:
            continue
        start = cursor
        cursor += current
        stops.append(f"{color} {start:.2f}% {cursor:.2f}%")
    return f"background:conic-gradient({', '.join(stops)})" if stops else "background:#e4eaf1"


def build_metrics(github: dict[str, Any], feishu: dict[str, Any]) -> dict[str, Any]:
    gm = github.get("metrics") or {}
    fm = feishu.get("metrics") or {}
    outcomes = github.get("engineering_outcomes") or {}
    outcome_totals = outcomes.get("totals") or {}
    portfolio = github.get("project_portfolio") or {}
    portfolio_totals = portfolio.get("totals") or {}
    comparison = github.get("comparison") or {}
    missing_scopes = collect_missing_scopes(feishu)
    return {
        "commits": number(gm.get("commits")),
        "prs_created": number(gm.get("prs_created")),
        "prs_merged": number(gm.get("prs_merged")),
        "prs_reviewed": number(gm.get("prs_reviewed")),
        "issues_created": number(gm.get("issues_created")),
        "issues_closed_related": number(gm.get("issues_closed_related")),
        "active_repos": number(gm.get("active_repos")),
        "feature_points": number(outcome_totals.get("feature_points")),
        "bug_fixes": number(outcome_totals.get("bug_fixes")),
        "bug_like_closed_issues": number(outcome_totals.get("bug_like_closed_issues")),
        "code_additions": number(outcome_totals.get("additions")),
        "code_deletions": number(outcome_totals.get("deletions")),
        "code_changed_files": number(outcome_totals.get("changed_files")),
        "code_net_lines": number(outcome_totals.get("net_lines")),
        "portfolio_projects": number(portfolio_totals.get("projects")),
        "new_repositories": number(portfolio_totals.get("new_repositories")),
        "newly_active_projects": number(portfolio_totals.get("newly_active_projects")),
        "interesting_projects": number(portfolio_totals.get("interesting_projects")),
        "github_growth": {
            "commits": pct_text((comparison.get("commits") or {}).get("pct")),
            "prs_merged": pct_text((comparison.get("prs_merged") or {}).get("pct")),
            "prs_created": pct_text((comparison.get("prs_created") or {}).get("pct")),
            "active_repos": pct_text((comparison.get("active_repos") or {}).get("pct")),
        },
        "feishu_accessible_modules": number(fm.get("accessible_modules")),
        "feishu_blocked_modules": number(fm.get("blocked_modules")),
        "feishu_missing_scopes": len(missing_scopes),
        "documents_discovered": number(fm.get("documents_discovered")),
        "documents_read": number(fm.get("documents_read")),
        "message_hits": number(fm.get("message_hits")),
        "calendar_events": number(fm.get("calendar_events")),
        "source_health": {
            "github": "ok" if github.get("kind") == "quarterly-github-dashboard" else "partial",
            "feishu": "ok" if number(fm.get("accessible_modules")) > 0 else ("permission_denied" if missing_scopes else "skipped"),
        },
    }


def build_executive_metrics(github: dict[str, Any], feishu: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    outcomes = github.get("engineering_outcomes") or {}
    coverage = outcomes.get("coverage") or {}
    portfolio = github.get("project_portfolio") or {}
    portfolio_totals = portfolio.get("totals") or {}
    comparison = github.get("comparison") or {}
    missing_scopes = collect_missing_scopes(feishu)
    code_stats_total = number(coverage.get("merged_prs_total"))
    code_stats_succeeded = number(coverage.get("code_stats_succeeded"))
    outcome_confidence = confidence_level(
        bool(metrics["feature_points"] or metrics["bug_fixes"]) and bool(code_stats_total) and code_stats_succeeded == code_stats_total,
        bool(metrics["feature_points"] or metrics["bug_fixes"]),
    )
    portfolio_confidence = confidence_level(bool(portfolio_totals), bool(portfolio))
    feishu_status = "permission_denied" if missing_scopes and not metrics["feishu_accessible_modules"] else ("partial" if missing_scopes else "ok")
    return {
        "schema_version": 1,
        "delivery": metric_contract(
            "研发交付事实",
            {
                "commits": metrics["commits"],
                "prs_created": metrics["prs_created"],
                "prs_merged": metrics["prs_merged"],
                "prs_reviewed": metrics["prs_reviewed"],
                "active_repos": metrics["active_repos"],
                "related_closed_issues": metrics["issues_closed_related"],
            },
            "GitHub Search/API summary",
            "high",
            quarter_over_quarter={
                "commits": (comparison.get("commits") or {}).get("pct") or "0%",
                "prs_merged": (comparison.get("prs_merged") or {}).get("pct") or "0%",
                "prs_created": (comparison.get("prs_created") or {}).get("pct") or "0%",
                "active_repos": (comparison.get("active_repos") or {}).get("pct") or "0%",
            },
        ),
        "outcomes": metric_contract(
            "功能与修复归类",
            {
                "feature_points": metrics["feature_points"],
                "bug_fixes": metrics["bug_fixes"],
                "bug_like_closed_issues": metrics["bug_like_closed_issues"],
                "changed_files": metrics["code_changed_files"],
                "code_stats_coverage": {
                    "succeeded": code_stats_succeeded,
                    "total": code_stats_total,
                    "ratio": pct_ratio(code_stats_succeeded, code_stats_total),
                },
            },
            coverage.get("classification_source") or "merged PR title, labels, and repository name",
            outcome_confidence,
            "ok" if outcome_confidence != "low" else "partial",
        ),
        "portfolio": metric_contract(
            "项目组合与新方向",
            {
                "projects": metrics["portfolio_projects"],
                "new_repositories": metrics["new_repositories"],
                "newly_active_projects": metrics["newly_active_projects"],
                "interesting_projects": metrics["interesting_projects"],
            },
            "GitHub repository metadata, README excerpts, PR titles, commit titles",
            portfolio_confidence,
            "ok" if portfolio_confidence != "low" else "partial",
        ),
        "collaboration": metric_contract(
            "飞书协作覆盖",
            {
                "feishu_accessible_modules": metrics["feishu_accessible_modules"],
                "feishu_blocked_modules": metrics["feishu_blocked_modules"],
                "feishu_missing_scopes": metrics["feishu_missing_scopes"],
                "documents_discovered": metrics["documents_discovered"],
                "documents_read": metrics["documents_read"],
                "message_hits": metrics["message_hits"],
                "calendar_events": metrics["calendar_events"],
            },
            "Feishu module summaries and permission preflight",
            "high" if metrics["feishu_accessible_modules"] else "low",
            feishu_status,
        ),
        "coverage": metric_contract(
            "数据覆盖率",
            {
                "github_code_stats": {
                    "succeeded": code_stats_succeeded,
                    "total": code_stats_total,
                    "ratio": pct_ratio(code_stats_succeeded, code_stats_total),
                    "direct_commit_line_stats_included": bool(coverage.get("direct_commit_line_stats_included")),
                },
                "feishu_modules": {
                    "accessible": metrics["feishu_accessible_modules"],
                    "blocked": metrics["feishu_blocked_modules"],
                    "total": 3,
                    "missing_scopes": missing_scopes,
                },
            },
            "GitHub PR API coverage and Feishu permission preflight",
            confidence_level(bool(code_stats_total) and code_stats_succeeded == code_stats_total, bool(coverage)),
            "partial" if missing_scopes else "ok",
        ),
        "boundaries": metric_contract(
            "汇报边界",
            [
                "相关关闭 issue 不是亲自解决问题数。",
                "Review 参与 PR 是 PR 集合数，不是单次 review 次数。",
                "功能点、Bug 修复、主题和项目用途是从 GitHub 证据推断的汇报口径。",
                "飞书权限不足代表协作证据未覆盖，不代表飞书侧没有产出。",
            ],
            "Skill methodology and module notes",
            "high",
            "ok",
        ),
    }


def evidence_item(item: dict[str, Any], kind: str, why: str = "") -> dict[str, Any]:
    title = item.get("title") or item.get("repo") or item.get("sha") or item.get("name") or "Untitled"
    return {
        "kind": kind,
        "title": title,
        "repo": item.get("repo"),
        "number": item.get("number"),
        "sha": item.get("sha"),
        "url": item.get("url") or item.get("html_url") or "",
        "date": item.get("closed_at") or item.get("created_at") or item.get("authored_at") or item.get("updated_at") or item.get("created_at"),
        "why": why,
    }


def unique_evidence(items: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = (str(item.get("kind") or ""), str(item.get("url") or ""), str(item.get("title") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def collect_theme_evidence(github: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for theme in ((github.get("contribution_portrait") or {}).get("themes") or [])[:3]:
        if not isinstance(theme, dict):
            continue
        theme_name = str(theme.get("theme") or "")
        for pr in (theme.get("representative_prs") or [])[:2]:
            if isinstance(pr, dict):
                evidence.append(evidence_item(pr, "pr", f"代表投入主题：{theme_name}"))
    return unique_evidence(evidence, 6)


def collect_project_evidence(github: dict[str, Any]) -> list[dict[str, Any]]:
    portfolio = github.get("project_portfolio") or {}
    evidence: list[dict[str, Any]] = []
    for group, why in (
        ("new_repositories", "本季度新建项目"),
        ("newly_active_projects", "本季度新启动/重新活跃项目"),
        ("interesting_projects", "重点工作线索项目"),
    ):
        for project in (portfolio.get(group) or [])[:3]:
            if isinstance(project, dict):
                evidence.append(evidence_item(project, "repo", why))
                for pr in (project.get("representative_prs") or [])[:1]:
                    if isinstance(pr, dict):
                        evidence.append(evidence_item(pr, "pr", f"{project.get('repo')} 的代表性 PR"))
    return unique_evidence(evidence, 8)


def build_evidence_chains(github: dict[str, Any], feishu: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    merged_prs = ((github.get("prs") or {}).get("merged") or [])
    closed_issues = ((github.get("issues") or {}).get("closed_related") or [])
    top_code_prs = ((github.get("engineering_outcomes") or {}).get("top_code_prs") or [])
    chains = [
        {
            "id": "delivery-volume",
            "title": "交付规模",
            "claim": f"{fmt_num(metrics['commits'])} 次 commit、{fmt_num(metrics['prs_merged'])} 个合并 PR，覆盖 {fmt_num(metrics['active_repos'])} 个活跃仓库。",
            "confidence": "high",
            "source": "GitHub Search/API",
            "evidence": unique_evidence([evidence_item(item, "pr", "本季度合并 PR") for item in merged_prs[:8]], 6),
            "caveat": "PR 和 commit 计数受 GitHub 搜索权限、索引和查询上限影响。",
        },
        {
            "id": "outcome-classification",
            "title": "功能与修复",
            "claim": f"从合并 PR 标题、label 和仓库线索识别 {fmt_num(metrics['feature_points'])} 个功能点、{fmt_num(metrics['bug_fixes'])} 个 bug 修复。",
            "confidence": "medium",
            "source": "Merged PR title/label classification",
            "evidence": unique_evidence([evidence_item(item, "pr", "高代码变更 PR，可辅助复核工作内容") for item in top_code_prs[:8]], 6),
            "caveat": "这是研发证据归类，不等同正式需求系统 story 数或线上 bug 全量。",
        },
        {
            "id": "theme-focus",
            "title": "投入方向",
            "claim": "投入方向由仓库、PR 标题、commit 标题和 README 线索综合归类。",
            "confidence": "medium",
            "source": "GitHub contribution portrait",
            "evidence": collect_theme_evidence(github),
            "caveat": "主题是汇报视角的归纳，不是组织级项目标签。",
        },
        {
            "id": "project-portfolio",
            "title": "项目组合",
            "claim": f"识别 {fmt_num(metrics['new_repositories'])} 个新建仓库、{fmt_num(metrics['newly_active_projects'])} 个新启动/重新活跃项目。",
            "confidence": "medium",
            "source": "GitHub repo metadata and activity evidence",
            "evidence": collect_project_evidence(github),
            "caveat": "新启动表示上季度未进入活跃集合，本季度出现开发证据。",
        },
        {
            "id": "feishu-coverage",
            "title": "飞书覆盖边界",
            "claim": f"飞书当前可用模块 {fmt_num(metrics['feishu_accessible_modules'])}/3，缺少 {fmt_num(metrics['feishu_missing_scopes'])} 个 scope。",
            "confidence": "high" if metrics["feishu_missing_scopes"] else "medium",
            "source": "Feishu module permission preflight",
            "evidence": [],
            "caveat": "权限不足代表协作证据未覆盖，不代表飞书侧没有产出。",
        },
    ]
    if closed_issues:
        chains[0]["evidence"].extend(unique_evidence([evidence_item(item, "issue", "相关关闭 issue，不能直接等同亲自解决") for item in closed_issues[:2]], 2))
        chains[0]["evidence"] = unique_evidence(chains[0]["evidence"], 8)
    return chains


def evidence_ref(chain: dict[str, Any], item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "chain_id": chain.get("id"),
        "path": f"evidence_chains[{chain.get('id')}].evidence[{index}]",
        "url": item.get("url") or "",
        "kind": item.get("kind") or "",
        "title": item.get("title") or "",
    }


def build_claims(evidence_chains: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    type_map = {
        "delivery-volume": "fact",
        "outcome-classification": "inference",
        "theme-focus": "inference",
        "project-portfolio": "inference",
        "feishu-coverage": "boundary",
    }
    for chain in evidence_chains:
        if not isinstance(chain, dict):
            continue
        evidence = chain.get("evidence") or []
        refs = [evidence_ref(chain, item, idx) for idx, item in enumerate(evidence) if isinstance(item, dict)]
        if not refs:
            refs = [{"chain_id": chain.get("id"), "path": f"evidence_chains[{chain.get('id')}]", "url": "", "kind": "summary", "title": "summary-level evidence"}]
        claims.append(
            {
                "id": chain.get("id"),
                "text": chain.get("claim"),
                "type": type_map.get(str(chain.get("id")), "inference"),
                "confidence": chain.get("confidence") or "low",
                "source": chain.get("source") or "",
                "evidence_refs": refs,
                "limitations": [chain.get("caveat") or ""],
            }
        )
    return claims


def build_confidence_model(github: dict[str, Any], feishu: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    outcomes = github.get("engineering_outcomes") or {}
    coverage = outcomes.get("coverage") or {}
    portfolio = github.get("project_portfolio") or {}
    return [
        {
            "metric": "Commit / PR / 活跃仓库",
            "confidence": "high",
            "basis": "GitHub Search/API 直接返回",
            "risk": "受 GitHub 权限、索引和 query limit 影响",
        },
        {
            "metric": "功能点 / Bug 修复",
            "confidence": confidence_level(number(coverage.get("code_stats_succeeded")) == number(coverage.get("merged_prs_total")) and bool(metrics["prs_merged"]), bool(metrics["feature_points"] or metrics["bug_fixes"])),
            "basis": coverage.get("classification_source") or "合并 PR 标题、label、仓库名归类",
            "risk": "不等同正式需求或线上缺陷系统统计",
        },
        {
            "metric": "代码区域 / 变更文件",
            "confidence": confidence_level(number(coverage.get("file_breakdown_succeeded")) == number(coverage.get("merged_prs_total")) and bool(metrics["prs_merged"]), bool(coverage)),
            "basis": coverage.get("code_stats_source") or "GitHub PR files API",
            "risk": "仅覆盖合并 PR，不含直接 commit 的逐文件增删",
        },
        {
            "metric": "项目用途 / 重点方向",
            "confidence": confidence_level(bool((portfolio.get("totals") or {}).get("projects")), bool(portfolio)),
            "basis": "仓库 metadata、README 摘要、PR/commit 标题",
            "risk": "业务意义需要人工 annotation 校准",
        },
        {
            "metric": "飞书协作证据",
            "confidence": "high" if metrics["feishu_accessible_modules"] else "low",
            "basis": "飞书模块结果和 scope 预检",
            "risk": "缺 scope 时只能说明未覆盖，不能说明没有协作",
        },
    ]


def build_value_views(github: dict[str, Any], feishu: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    """Build presentation-only views that help leaders scan value and evidence."""
    portfolio = github.get("project_portfolio") or {}
    projects = [project for project in (portfolio.get("projects") or []) if isinstance(project, dict)]
    project_value_attribution, project_value_categories = build_project_value_attribution(projects)
    project_profiles = build_project_profiles(projects)
    quarter_change_map = build_quarter_change_map(github, projects)
    data_quality = build_data_quality(github, feishu, metrics)
    by_work_type = [row for row in ((github.get("engineering_outcomes") or {}).get("by_work_type") or []) if isinstance(row, dict)]
    top_repos = [repo for repo in (github.get("top_repos") or []) if isinstance(repo, dict)]
    themes = [theme for theme in ((github.get("contribution_portrait") or {}).get("themes") or []) if isinstance(theme, dict)]

    value_path = [
        {
            "key": "delivery",
            "label": "交付",
            "value": metrics.get("prs_merged"),
            "unit": "合并 PR",
            "detail": f"{fmt_num(metrics.get('commits'))} commit / {fmt_num(metrics.get('active_repos'))} 活跃仓库",
            "source": "GitHub Search/API",
        },
        {
            "key": "outcome",
            "label": "成果",
            "value": number(metrics.get("feature_points")) + number(metrics.get("bug_fixes")),
            "unit": "功能与修复",
            "detail": f"{fmt_num(metrics.get('feature_points'))} 功能 / {fmt_num(metrics.get('bug_fixes'))} 修复",
            "source": "Merged PR classification",
        },
        {
            "key": "portfolio",
            "label": "项目",
            "value": metrics.get("portfolio_projects"),
            "unit": "项目画像",
            "detail": f"{fmt_num(metrics.get('new_repositories'))} 新建 / {fmt_num(metrics.get('newly_active_projects'))} 新启动",
            "source": "Repo metadata and activity",
        },
        {
            "key": "collaboration",
            "label": "协作",
            "value": metrics.get("feishu_accessible_modules"),
            "unit": "飞书模块",
            "detail": f"{fmt_num(metrics.get('feishu_missing_scopes'))} 个权限缺口",
            "source": "Feishu permission preflight",
        },
    ]

    investment_lanes = [
        {
            "label": "功能交付",
            "value": metrics.get("feature_points"),
            "source": "merged PR title/label",
        },
        {
            "label": "稳定性修复",
            "value": metrics.get("bug_fixes"),
            "source": "fix/bug/regression clues",
        },
        {
            "label": "代码审计覆盖",
            "value": metrics.get("code_changed_files"),
            "source": "GitHub PR files API",
        },
        {
            "label": "跨项目推进",
            "value": metrics.get("portfolio_projects"),
            "source": "repo activity portfolio",
        },
    ]

    project_quadrants = {
        "new_high": [],
        "new_low": [],
        "existing_high": [],
        "existing_low": [],
    }
    if projects:
        project_scores = sorted(float(number(project.get("score"))) for project in projects)
        score_cut = project_scores[max(0, int(len(project_scores) * 0.62) - 1)] if project_scores else 0.0
        for project in sorted(projects, key=lambda item: number(item.get("score")), reverse=True)[:36]:
            score = float(number(project.get("score")))
            is_new = bool(project.get("is_new_repo") or project.get("is_newly_active"))
            key = ("new_" if is_new else "existing_") + ("high" if score >= score_cut else "low")
            value_attrs = infer_project_value_attribution(project)
            project_quadrants[key].append(
                {
                    "repo": project.get("repo"),
                    "name": project.get("display_name") or project.get("name") or project.get("repo"),
                    "score": score,
                    "url": project.get("url") or "",
                    "feature_points": number(project.get("feature_points")),
                    "bug_fixes": number(project.get("bug_fixes")),
                    "commits": number(project.get("commits")),
                    "merged_prs": number(project.get("merged_prs")),
                    "theme": project.get("theme") or project_bucket(project),
                    "primary_value": value_attrs[0].get("label") if value_attrs else "",
                    "status": "new_repo" if project.get("is_new_repo") else ("newly_active" if project.get("is_newly_active") else "existing"),
                }
            )

    focus_mix = []
    focus_candidates = [
        ("主题", themes[:4], "theme", "score"),
        ("工作类型", by_work_type[:4], "label", "count"),
        ("仓库", top_repos[:4], "repo", "score"),
    ]
    for group_label, rows, label_key, value_key in focus_candidates:
        total = sum(number(row.get(value_key)) for row in rows)
        if total <= 0:
            continue
        for row in rows:
            focus_mix.append(
                {
                    "group": group_label,
                    "label": row.get(label_key) or row.get("key") or "",
                    "value": number(row.get(value_key)),
                    "share": pct_float(row.get(value_key), total),
                }
            )

    return {
        "schema_version": 3,
        "value_path": value_path,
        "investment_lanes": investment_lanes,
        "project_quadrants": project_quadrants,
        "focus_mix": focus_mix,
        "project_value_attribution": project_value_attribution,
        "project_value_categories": project_value_categories,
        "project_profiles": project_profiles,
        "quarter_change_map": quarter_change_map,
        "data_quality": data_quality,
        "source_boundaries": {
            "github": {
                "status": "ok" if github.get("kind") == "quarterly-github-dashboard" else "partial",
                "facts": ["commits", "prs", "issues", "reviews", "repo metadata"],
            },
            "feishu": {
                "status": "ok" if metrics.get("feishu_accessible_modules") else "permission_denied",
                "missing_scopes": collect_missing_scopes(feishu),
            },
        },
    }


def collect_missing_scopes(feishu: dict[str, Any]) -> list[str]:
    scopes: set[str] = set()
    modules = feishu.get("modules") or {}
    for module in modules.values():
        if isinstance(module, dict):
            for scope in module.get("missing_scopes") or []:
                scopes.add(str(scope))
            for subkey in ("discovery", "reading"):
                sub = module.get(subkey)
                if isinstance(sub, dict):
                    for scope in sub.get("missing_scopes") or []:
                        scopes.add(str(scope))
    return sorted(scopes)


def build_modules(github: dict[str, Any], feishu: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "github": {
            "kind": github.get("kind"),
            "status": metrics["source_health"]["github"],
            "label": "GitHub 开发",
            "metrics": github.get("metrics") or {},
            "notes": github.get("notes") or [],
        },
        "feishu": {
            "kind": feishu.get("kind"),
            "status": metrics["source_health"]["feishu"],
            "label": "飞书协作",
            "metrics": feishu.get("metrics") or {},
            "modules": feishu.get("modules") or {},
            "missing_scopes": collect_missing_scopes(feishu),
            "notes": feishu.get("notes") or [],
        },
    }


def build_insights(github: dict[str, Any], feishu: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    comparison = github.get("comparison") or {}
    outcomes = github.get("engineering_outcomes") or {}
    coverage = outcomes.get("coverage") or {}
    themes = ((github.get("contribution_portrait") or {}).get("themes") or [])[:3]
    portfolio = github.get("project_portfolio") or {}
    portfolio_totals = portfolio.get("totals") or {}
    new_project_names = [item.get("name") or item.get("repo") for item in (portfolio.get("new_repositories") or portfolio.get("newly_active_projects") or [])[:3] if isinstance(item, dict)]
    theme_text = "、".join(str(item.get("theme")) for item in themes if isinstance(item, dict) and item.get("theme"))
    insights = [
        f"GitHub 侧本季度形成 {fmt_num(metrics['commits'])} 次 commit、{fmt_num(metrics['prs_merged'])} 个合并 PR，覆盖 {fmt_num(metrics['active_repos'])} 个活跃仓库。",
    ]
    if metrics.get("feature_points") or metrics.get("bug_fixes"):
        insights.append(
            f"按合并 PR 标题和标签归类，本季度识别出 {fmt_num(metrics['feature_points'])} 个功能点、{fmt_num(metrics['bug_fixes'])} 个 bug 修复；代码变更统计覆盖 {fmt_num(coverage.get('code_stats_succeeded'))}/{fmt_num(coverage.get('merged_prs_total'))} 个合并 PR。"
        )
    merged_cmp = comparison.get("prs_merged") or {}
    commits_cmp = comparison.get("commits") or {}
    if merged_cmp or commits_cmp:
        insights.append(
            f"与上个可比区间相比，commit {pct_text(commits_cmp.get('pct'))}，合并 PR {pct_text(merged_cmp.get('pct'))}，研发交付强度有明确增长信号。"
        )
    if theme_text:
        insights.append(f"投入方向集中在 {theme_text}，这些主题由仓库、PR 标题和提交记录确定性归类得到。")
    if portfolio_totals:
        names = "、".join(str(name) for name in new_project_names if name)
        suffix = f"：{names}" if names else ""
        insights.append(
            f"项目组合层面识别到 {fmt_num(portfolio_totals.get('new_repositories'))} 个新建仓库、{fmt_num(portfolio_totals.get('newly_active_projects'))} 个本季度新启动/重新活跃项目{suffix}。"
        )
    insights.append(
        f"飞书侧当前可用模块 {fmt_num(metrics['feishu_accessible_modules'])}/3，权限缺口 {fmt_num(metrics['feishu_missing_scopes'])} 个；协作证据覆盖不足，应作为数据边界而不是业绩为零。"
    )
    if metrics["prs_reviewed"]:
        insights.append(f"协作参与上，GitHub 记录到 {fmt_num(metrics['prs_reviewed'])} 个参与 review 的 PR，口径是 PR 集合数，不是单次 review 次数。")
    return insights[:5]


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    annotations = load_annotations(args.annotations)
    github = apply_annotations(load_json(args.github_summary), annotations)
    feishu = load_json(args.feishu_summary)
    start = github.get("start") or feishu.get("start")
    end = github.get("end") or feishu.get("end")
    period_label = args.period_label or github.get("period_label") or feishu.get("period_label") or f"{start}..{end}"
    output_dir = Path(args.output_dir).expanduser().resolve()
    metrics = build_metrics(github, feishu)
    modules = build_modules(github, feishu, metrics)
    executive_metrics = build_executive_metrics(github, feishu, metrics)
    insights = build_insights(github, feishu, metrics)
    evidence_chains = build_evidence_chains(github, feishu, metrics)
    claims = build_claims(evidence_chains)
    confidence = build_confidence_model(github, feishu, metrics)
    value_views = build_value_views(github, feishu, metrics)
    return {
        "kind": "quarterly-work-dashboard",
        "schema_version": SCHEMA_VERSION + 1,
        "period_label": period_label,
        "start": start,
        "end": end,
        "generated_at": iso_now(),
        "metrics": metrics,
        "executive_metrics": executive_metrics,
        "modules": modules,
        "insights": insights,
        "claims": claims,
        "evidence_chains": evidence_chains,
        "value_views": value_views,
        "confidence": confidence,
        "sources": {
            "github_summary": str(Path(args.github_summary).expanduser().resolve()),
            "feishu_summary": str(Path(args.feishu_summary).expanduser().resolve()),
            "github_index": infer_index(args.github_summary, args.github_index),
            "feishu_index": infer_index(args.feishu_summary, args.feishu_index),
            "annotations": str(Path(args.annotations).expanduser().resolve()) if args.annotations else "",
        },
        "github": github,
        "feishu": feishu,
        "methodology": {
            "github": "Read quarterly-github-dashboard summary.json. GitHub metrics remain owned by the GitHub skill.",
            "feishu": "Read quarterly-feishu-dashboard summary.json. Feishu permissions and module failures remain owned by the Feishu skill.",
            "combined": "This dashboard is a presentation layer only; it does not query or mutate external systems.",
        },
        "output_dir": str(output_dir),
    }


def metric_card(value: Any, label: str, _hint: str = "", growth: str = "") -> str:
    growth_html = f'<span class="growth">{esc(growth)}</span>' if growth else ""
    return f"""
      <div class="metric">
        <div class="metric-value">{esc(fmt_num(value))}{growth_html}</div>
        <div class="metric-label">{esc(label)}</div>
      </div>
    """


def compact_metric_card(value: Any, label: str, tone: str = "") -> str:
    cls = f"mini {tone}".strip()
    return f'<div class="{esc(cls)}"><strong>{esc(fmt_num(value))}</strong><span>{esc(label)}</span></div>'


def confidence_badge(level: str) -> str:
    return f'<span class="confidence confidence-{esc(level)}">{esc(confidence_label(level))}</span>'


def executive_metric_strip(summary: dict[str, Any]) -> str:
    executive = summary.get("executive_metrics") or {}
    delivery = executive.get("delivery") or {}
    outcomes = executive.get("outcomes") or {}
    portfolio = executive.get("portfolio") or {}
    collaboration = executive.get("collaboration") or {}
    delivery_value = delivery.get("value") if isinstance(delivery.get("value"), dict) else {}
    outcome_value = outcomes.get("value") if isinstance(outcomes.get("value"), dict) else {}
    portfolio_value = portfolio.get("value") if isinstance(portfolio.get("value"), dict) else {}
    collaboration_value = collaboration.get("value") if isinstance(collaboration.get("value"), dict) else {}
    items = [
        ("交付事实", delivery.get("confidence"), f"{fmt_num(delivery_value.get('prs_merged'))} 合并 PR · {fmt_num(delivery_value.get('commits'))} commit", delivery.get("source")),
        ("成果推断", outcomes.get("confidence"), f"{fmt_num(outcome_value.get('feature_points'))} 功能 · {fmt_num(outcome_value.get('bug_fixes'))} 修复", outcomes.get("source")),
        ("项目组合", portfolio.get("confidence"), f"{fmt_num(portfolio_value.get('new_repositories'))} 新建 · {fmt_num(portfolio_value.get('newly_active_projects'))} 新启动", portfolio.get("source")),
        ("协作覆盖", collaboration.get("confidence"), f"{fmt_num(collaboration_value.get('feishu_accessible_modules'))}/3 飞书模块", collaboration.get("source")),
    ]
    rows = "".join(
        f"""
        <div class="signal-item">
          <strong>{esc(label)}</strong>
          <b>{esc(value)}</b>
          {confidence_badge(str(level or 'low'))}
        </div>
        """
        for label, level, value, source in items
    )
    return f'<div class="signal-rail">{rows}</div>'


def summary_evidence_section(summary: dict[str, Any]) -> str:
    chains = [chain for chain in (summary.get("evidence_chains") or []) if isinstance(chain, dict)]
    chain_type = {
        "delivery-volume": "事实",
        "outcome-classification": "推断",
        "theme-focus": "推断",
        "project-portfolio": "推断",
        "feishu-coverage": "边界",
    }
    chain_rows = []
    for chain in chains[:5]:
        evidence = chain.get("evidence") or []
        evidence_html = evidence_chain_items(evidence, 2)
        type_label = chain_type.get(str(chain.get("id") or ""), "证据")
        chain_rows.append(
            f"""
            <article class="chain-compact">
              <div class="chain-compact-top">
                <span>{esc(type_label)}</span>
                {confidence_badge(str(chain.get('confidence') or 'low'))}
              </div>
              <h3>{esc(chain.get('title') or '')}</h3>
              <p>{esc(chain.get('claim') or '')}</p>
              {evidence_html}
              <small>{esc(chain.get('caveat') or '')}</small>
            </article>
            """
        )
    if not chain_rows:
        chain_rows.append('<p class="empty">暂无可追溯证据链。</p>')
    insights = "".join(f'<li>{esc(item)}</li>' for item in summary.get("insights") or [])
    return f"""
      <div class="summary-evidence-grid">
        <div class="insight-panel">
          <ol class="insights">{insights}</ol>
        </div>
        <div class="evidence-rail">{''.join(chain_rows)}</div>
      </div>
    """


def evidence_chain_section(summary: dict[str, Any]) -> str:
    chains = summary.get("evidence_chains") or []
    if not chains:
        return '<p class="empty">暂无可追溯证据链。</p>'
    cards = []
    chain_type = {
        "delivery-volume": "事实",
        "outcome-classification": "推断",
        "theme-focus": "推断",
        "project-portfolio": "推断",
        "feishu-coverage": "边界",
    }
    for chain in chains:
        if not isinstance(chain, dict):
            continue
        evidence = chain.get("evidence") or []
        evidence_html = evidence_chain_items(evidence)
        type_label = chain_type.get(str(chain.get("id") or ""), "证据")
        cards.append(
            f"""
            <article class="chain-card">
              <div class="chain-head">
                <div>
                  <h3>{esc(chain.get('title') or '')}</h3>
                  <small>{esc(chain.get('source') or '')}</small>
                </div>
                {confidence_badge(str(chain.get('confidence') or 'low'))}
              </div>
              <div class="audit-path">
                <span>{esc(type_label)}</span>
                <i></i>
                <span>{esc(fmt_num(len(evidence)))} 条证据</span>
                <i></i>
                <span>边界</span>
              </div>
              <p>{esc(chain.get('claim') or '')}</p>
              {evidence_html}
              <div class="chain-caveat">{esc(chain.get('caveat') or '')}</div>
            </article>
            """
        )
    return '<div class="chain-grid">' + "".join(cards) + "</div>"


def evidence_chain_items(items: list[dict[str, Any]], limit: int = 5) -> str:
    if not items:
        return '<p class="empty compact">暂无可点击证据，当前结论依赖 summary 级统计或权限预检。</p>'
    rows = []
    for item in items[:limit]:
        title = item.get("title") or "Untitled"
        url = item.get("url") or ""
        kind = item.get("kind") or "evidence"
        repo = item.get("repo") or ""
        number_value = item.get("number")
        why = item.get("why") or ""
        title_html = f'<a href="{esc(url)}">{esc(title)}</a>' if url else esc(title)
        meta = " · ".join(str(x) for x in [kind, repo, f"#{number_value}" if number_value else ""] if x)
        rows.append(
            f"""
            <li>
              <span class="chain-kind">{esc(kind)}</span>
              <div>
                <strong>{title_html}</strong>
                <small>{esc(meta)}{esc(' · ' + why if why else '')}</small>
              </div>
            </li>
            """
        )
    return f'<ul class="chain-list">{"".join(rows)}</ul>'


def value_path(summary: dict[str, Any]) -> str:
    items = ((summary.get("value_views") or {}).get("value_path") or [])
    if not items:
        return ""
    max_value = max(float(number(item.get("value"))) for item in items if isinstance(item, dict)) or 1.0
    cards = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        value = number(item.get("value"))
        cards.append(
            f"""
            <div class="value-step" title="{esc(item.get('detail') or '')}">
              <span>{esc(str(idx + 1).zfill(2))}</span>
              <strong>{esc(item.get('label') or '')}</strong>
              <b>{esc(fmt_num(value))}</b>
              <em>{esc(item.get('unit') or '')}</em>
              <div class="value-bar"><b style="width:{bar_width(value, max_value)}"></b></div>
            </div>
            """
        )
    return f'<div class="value-rail">{"".join(cards)}</div>'


def investment_lanes(summary: dict[str, Any]) -> str:
    lanes = [lane for lane in (((summary.get("value_views") or {}).get("investment_lanes") or [])) if isinstance(lane, dict)]
    if not lanes:
        return '<p class="empty">暂无投入强度数据。</p>'
    max_value = max(float(number(lane.get("value"))) for lane in lanes) or 1.0
    rows = []
    for lane in lanes:
        value = number(lane.get("value"))
        rows.append(
            f"""
            <div class="lane-row">
              <div>
                <strong>{esc(lane.get('label') or '')}</strong>
                <small>{esc(lane.get('source') or '')}</small>
              </div>
              <div class="lane-track"><span style="width:{bar_width(value, max_value)}"></span></div>
              <b>{esc(fmt_num(value))}</b>
            </div>
            """
        )
    return '<div class="lane-grid">' + "".join(rows) + "</div>"


def focus_mix_board(summary: dict[str, Any]) -> str:
    focus = [row for row in (((summary.get("value_views") or {}).get("focus_mix") or [])) if isinstance(row, dict)]
    if not focus:
        return '<p class="empty">暂无聚焦结构数据。</p>'
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in focus:
        groups.setdefault(str(row.get("group") or "其他"), []).append(row)
    group_html = []
    for group, rows in groups.items():
        chips = []
        for row in rows[:4]:
            share = float(number(row.get("share")))
            chips.append(
                f"""
                <span class="focus-chip" style="--share:{max(8, min(100, share)):.1f}%">
                  <b>{esc(short_label(row.get('label'), 20))}</b>
                  <em>{esc(format_pct(share))}</em>
                </span>
                """
            )
        group_html.append(
            f"""
            <div class="focus-group">
              <strong>{esc(group)}</strong>
              <div>{''.join(chips)}</div>
            </div>
            """
        )
    return '<div class="focus-board">' + "".join(group_html) + "</div>"


def project_quadrant(summary: dict[str, Any]) -> str:
    quadrants = ((summary.get("value_views") or {}).get("project_quadrants") or {})
    if not isinstance(quadrants, dict) or not any(quadrants.values()):
        return '<p class="empty">暂无项目象限。</p>'
    specs = [
        ("new_high", "新方向 · 高强度"),
        ("existing_high", "持续项目 · 高强度"),
        ("new_low", "新方向 · 观察"),
        ("existing_low", "持续项目 · 维护"),
    ]
    cells = []
    for key, label in specs:
        rows = [row for row in (quadrants.get(key) or []) if isinstance(row, dict)]
        chips = []
        for row in rows[:6]:
            name = row.get("name") or row.get("repo") or ""
            url = row.get("url") or ""
            chip = f'<a href="{esc(url)}">{esc(short_label(name, 18))}<span>{esc(fmt_num(row.get("score")))}</span></a>' if url else f'<span>{esc(short_label(name, 18))}<span>{esc(fmt_num(row.get("score")))}</span></span>'
            chips.append(chip)
        cells.append(
            f"""
            <div class="quadrant-cell quadrant-{esc(key)}">
              <div class="quadrant-title"><strong>{esc(label)}</strong><em>{esc(fmt_num(len(rows)))}</em></div>
              <div class="quadrant-items">{''.join(chips) if chips else '<small>暂无</small>'}</div>
            </div>
            """
        )
    return '<div class="project-quadrant">' + "".join(cells) + "</div>"


def project_value_attribution_board(summary: dict[str, Any]) -> str:
    categories = [row for row in (((summary.get("value_views") or {}).get("project_value_categories") or [])) if isinstance(row, dict)]
    projects = [row for row in (((summary.get("value_views") or {}).get("project_value_attribution") or [])) if isinstance(row, dict)]
    if not categories:
        return '<p class="empty">暂无项目价值归因。</p>'
    max_score = max(float(number(row.get("score"))) for row in categories) or 1.0
    category_html = []
    for row in categories[:6]:
        samples = "、".join(str(item) for item in (row.get("sample_projects") or [])[:3] if item)
        category_html.append(
            f"""
            <div class="value-category">
              <div>
                <strong>{esc(row.get('label') or '')}</strong>
                <small>{esc(fmt_num(row.get('projects')))} 个项目{esc(' · ' + samples if samples else '')}</small>
              </div>
              <div class="value-category-track"><span style="width:{bar_width(row.get('score'), max_score)}"></span></div>
              <b>{esc(fmt_num(row.get('score')))}</b>
            </div>
            """
        )
    project_html = []
    for row in projects[:8]:
        attrs = [attr for attr in (row.get("value_attribution") or []) if isinstance(attr, dict)]
        chips = "".join(f'<span>{esc(attr.get("label") or "")}</span>' for attr in attrs[:3])
        project_html.append(
            f"""
            <a class="value-project" href="{esc(row.get('url') or '#')}">
              <strong>{esc(short_label(row.get('name') or row.get('repo'), 26))}</strong>
              <em>{esc(row.get('status') or '')}</em>
              <div>{chips}</div>
            </a>
            """
        )
    return f"""
      <div class="value-attribution-board">
        <div class="value-category-grid">{''.join(category_html)}</div>
        <div class="value-project-strip">{''.join(project_html)}</div>
      </div>
    """


def data_quality_strip(summary: dict[str, Any]) -> str:
    rows = [row for row in (((summary.get("value_views") or {}).get("data_quality") or [])) if isinstance(row, dict)]
    if not rows:
        return ""
    cards = []
    for row in rows:
        value = max(0.0, min(100.0, float(number(row.get("value")))))
        tone = STATUS_TONE.get(str(row.get("status") or ""), "idle")
        cards.append(
            f"""
            <div class="quality-item quality-{esc(tone)}">
              <strong>{esc(row.get('label') or '')}</strong>
              <div class="quality-meter"><span style="width:{value:.1f}%"></span></div>
              <b>{value:.0f}%</b>
              {confidence_badge(str(row.get('confidence') or 'low'))}
            </div>
            """
        )
    return '<div class="quality-rail">' + "".join(cards) + "</div>"


def quarter_change_map(summary: dict[str, Any]) -> str:
    data = (summary.get("value_views") or {}).get("quarter_change_map") or {}
    metrics = [row for row in (data.get("metrics") or []) if isinstance(row, dict)]
    moves = [row for row in (data.get("project_moves") or []) if isinstance(row, dict)]
    lanes = [row for row in (data.get("lanes") or []) if isinstance(row, dict)]
    metric_html = []
    for row in metrics[:6]:
        direction = str(row.get("direction") or "flat")
        metric_html.append(
            f"""
            <div class="change-metric change-{esc(direction)}">
              <span>{esc(row.get('label') or '')}</span>
              <strong>{esc(fmt_num(row.get('current')))}</strong>
              <em>{esc(row.get('pct') or '0%')}</em>
            </div>
            """
        )
    lane_html = []
    max_lane = max((number(row.get("count")) for row in lanes), default=1) or 1
    for row in lanes:
        lane_html.append(
            f"""
            <div class="change-lane">
              <span>{esc(row.get('label') or '')}</span>
              <div><b style="width:{bar_width(row.get('count'), float(max_lane))}"></b></div>
              <strong>{esc(fmt_num(row.get('count')))}</strong>
            </div>
            """
        )
    move_html = []
    for row in moves[:12]:
        signal = str(row.get("signal") or "sustained")
        label = {"new_repo": "新建", "newly_active": "启动", "sustained": "持续"}.get(signal, "项目")
        link = row.get("url") or ""
        name = short_label(row.get("name") or row.get("repo"), 22)
        content = f'<a href="{esc(link)}">{esc(name)}<span>{esc(label)}</span></a>' if link else f'<span>{esc(name)}<span>{esc(label)}</span></span>'
        move_html.append(content)
    boundary = data.get("boundary") or ""
    return f"""
      <div class="change-map">
        <div class="change-metrics">{''.join(metric_html)}</div>
        <div class="change-lanes">{''.join(lane_html)}</div>
        <div class="change-projects">{''.join(move_html)}</div>
        {f'<div class="change-boundary">{esc(boundary)}</div>' if boundary else ''}
      </div>
    """


def project_profile_cards(summary: dict[str, Any]) -> str:
    profiles = [row for row in (((summary.get("value_views") or {}).get("project_profiles") or [])) if isinstance(row, dict)]
    if not profiles:
        return '<p class="empty">暂无重点项目剖面。</p>'
    rows = []
    for idx, row in enumerate(profiles, start=1):
        attrs = [attr for attr in (row.get("value_attribution") or []) if isinstance(attr, dict)]
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        actions = row.get("actions") if isinstance(row.get("actions"), list) else []
        prs = row.get("representative_prs") if isinstance(row.get("representative_prs"), list) else []
        value_chips = "".join(f'<span>{esc(attr.get("label") or "")}</span>' for attr in attrs[:3])
        action_html = "".join(f"<span>{esc(item)}</span>" for item in actions[:2])
        pr_html = "".join(
            f'<a href="{esc(pr.get("url") or "#")}">#{esc(pr.get("number") or "")} {esc(short_label(pr.get("title"), 42))}</a>'
            for pr in prs[:3]
            if isinstance(pr, dict)
        )
        metric_html = "".join(
            f"<div><span>{esc(label)}</span><strong>{esc(fmt_num(value))}</strong></div>"
            for label, value in (
                ("功能", metrics.get("feature_points")),
                ("修复", metrics.get("bug_fixes")),
                ("PR", metrics.get("merged_prs")),
                ("Commit", metrics.get("commits")),
            )
        )
        impact_parts = [str(part) for part in [row.get("business_impact"), row.get("customer_value")] if part]
        impact_html = " · ".join(impact_parts[:2])
        rows.append(
            f"""
            <article class="profile-row">
              <div class="profile-index">{esc(str(idx).zfill(2))}</div>
              <div class="profile-main">
                <div class="profile-head">
                  <div>
                    <h3><a href="{esc(row.get('url') or '#')}">{esc(row.get('name') or row.get('repo') or '')}</a></h3>
                    <small>{esc(row.get('theme') or '')} · {esc(row.get('status') or '')}{esc(' · ' + str(row.get('role')) if row.get('role') else '')}</small>
                  </div>
                  {confidence_badge(str(row.get('confidence') or 'medium'))}
                </div>
                <p>{esc(row.get('purpose') or '')}</p>
                {f'<div class="profile-impact-line">{esc(impact_html)}</div>' if impact_html else ''}
                {f'<div class="profile-actions">{action_html}</div>' if action_html else ''}
                {f'<div class="profile-prs">{pr_html}</div>' if pr_html else ''}
              </div>
              <div class="profile-side">
                <div class="profile-values">{value_chips}</div>
                <div class="profile-metrics">{metric_html}</div>
              </div>
            </article>
            """
        )
    return '<div class="profile-list">' + "".join(rows) + "</div>"


def confidence_table(summary: dict[str, Any]) -> str:
    rows = []
    for item in summary.get("confidence") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            f"""
            <tr>
              <td>{esc(item.get('metric') or '')}</td>
              <td>{confidence_badge(str(item.get('confidence') or 'low'))}</td>
              <td>{esc(item.get('basis') or '')}</td>
              <td>{esc(item.get('risk') or '')}</td>
            </tr>
            """
        )
    if not rows:
        return '<p class="empty">暂无可信度模型。</p>'
    return f"""
      <div class="table-wrap">
        <table>
          <thead><tr><th>指标</th><th>可信度</th><th>依据</th><th>风险</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    """


def bar_rows(items: list[tuple[str, Any]], empty: str, color_class: str = "") -> str:
    cleaned = [(str(name), number(value)) for name, value in items if number(value) > 0]
    if not cleaned:
        return f'<p class="empty">{esc(empty)}</p>'
    max_value = max(value for _, value in cleaned) or 1
    rows = []
    for name, value in cleaned[:12]:
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-name">{esc(name)}</div>
              <div class="bar-track"><span class="{esc(color_class)}" style="width:{bar_width(value, max_value)}"></span></div>
              <div class="bar-value">{esc(fmt_num(value))}</div>
            </div>
            """
        )
    return "".join(rows)


def donut_chart(title: str, items: list[tuple[str, Any, str]]) -> str:
    cleaned = [(label, number(value), color) for label, value, color in items if number(value) > 0]
    if not cleaned:
        return '<p class="empty">暂无图表数据。</p>'
    total = sum(value for _, value, _ in cleaned)
    legend = "".join(
        f"""
        <li>
          <span class="legend-dot" style="background:{esc(color)}"></span>
          <span>{esc(label)}</span>
          <strong>{esc(fmt_num(value))}</strong>
        </li>
        """
        for label, value, color in cleaned
    )
    return f"""
      <div class="viz-card donut-card">
        <h3>{esc(title)}</h3>
        <div class="donut-wrap">
          <div class="donut" style="{esc(conic_style(cleaned))}">
            <div><strong>{esc(fmt_num(total))}</strong><span>总量</span></div>
          </div>
          <ul class="legend-list">{legend}</ul>
        </div>
      </div>
    """


def stacked_bar_card(title: str, items: list[tuple[str, Any, str]]) -> str:
    cleaned = [(label, number(value), color) for label, value, color in items if number(value) > 0]
    if not cleaned:
        return '<div class="viz-card"><h3>' + esc(title) + '</h3><p class="empty">暂无图表数据。</p></div>'
    total = sum(value for _, value, _ in cleaned)
    legend = "".join(
        f"""
        <li>
          <span class="legend-dot" style="background:{esc(color)}"></span>
          <span>{esc(label)}</span>
          <strong>{esc(fmt_num(value))}</strong>
        </li>
        """
        for label, value, color in cleaned
    )
    segments = "".join(
        f'<span style="width:{pct_float(value, total):.2f}%; background:{esc(color)}"></span>'
        for _, value, color in cleaned
    )
    return f"""
      <div class="viz-card">
        <h3>{esc(title)}</h3>
        <div class="stacked-bar">{segments}</div>
        <ul class="legend-list compact">{legend}</ul>
      </div>
    """


def overview_chart_grid(summary: dict[str, Any]) -> str:
    github = summary["github"]
    metrics = summary["metrics"]
    delivery_items = [
        ("Commit", metrics.get("commits"), "#1f6feb"),
        ("合并 PR", metrics.get("prs_merged"), "#157b50"),
        ("Review PR", metrics.get("prs_reviewed"), "#6750b5"),
        ("相关 issue", metrics.get("issues_closed_related"), "#ae6817"),
    ]
    outcome_items = [
        ("功能点", metrics.get("feature_points"), "#1f6feb"),
        ("Bug 修复", metrics.get("bug_fixes"), "#b83a45"),
        ("Bug-like issue", metrics.get("bug_like_closed_issues"), "#ae6817"),
    ]
    return f"""
      <div class="viz-grid overview-viz">
        {donut_chart('交付构成', delivery_items)}
        {comparison_tiles(github)}
        {stacked_bar_card('成果结构', outcome_items)}
      </div>
    """


def comparison_tiles(github: dict[str, Any]) -> str:
    comparison = github.get("comparison") or {}
    keys = ["commits", "prs_created", "prs_merged", "prs_reviewed", "active_repos", "issues_closed_related"]
    tiles = []
    for key in keys:
        item = comparison.get(key) or {}
        if not item:
            continue
        direction = str(item.get("direction") or "flat")
        pct = item.get("pct") or "0%"
        magnitude = min(100.0, abs(parse_pct(pct)))
        tiles.append(
            f"""
            <div class="delta-tile delta-{esc(direction)}">
              <span>{esc(item.get('label') or key)}</span>
              <strong>{esc(pct)}</strong>
              <i><b style="width:{magnitude:.1f}%"></b></i>
            </div>
            """
        )
    if not tiles:
        return '<div class="viz-card"><h3>环比变化</h3><p class="empty">暂无上季度对比数据。</p></div>'
    return f"""
      <div class="viz-card">
        <h3>环比变化</h3>
        <div class="delta-grid">{''.join(tiles)}</div>
      </div>
    """


def comparison_rows(github: dict[str, Any]) -> str:
    comparison = github.get("comparison") or {}
    keys = ["commits", "prs_created", "prs_merged", "prs_reviewed", "active_repos", "issues_closed_related"]
    rows = []
    for key in keys:
        item = comparison.get(key) or {}
        if not item:
            continue
        direction = str(item.get("direction") or "flat")
        rows.append(
            f"""
            <tr>
              <td>{esc(item.get('label') or key)}</td>
              <td class="num">{esc(fmt_num(item.get('current')))}</td>
              <td class="num">{esc(fmt_num(item.get('previous')))}</td>
              <td class="num delta-{esc(direction)}">{esc(item.get('pct') or '0%')}</td>
            </tr>
            """
        )
    if not rows:
        return '<p class="empty">暂无上季度对比数据。</p>'
    return f"""
      <div class="table-wrap">
        <table>
          <thead><tr><th>指标</th><th>本季度</th><th>上季度</th><th>环比</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    """


def top_repos_chart(github: dict[str, Any]) -> str:
    repos = github.get("top_repos") or []
    rows = []
    for repo in repos[:10]:
        if isinstance(repo, dict):
            score = number(repo.get("score") or repo.get("commits") or repo.get("prs_merged"))
            detail = (
                f"C {fmt_num(repo.get('commits'))} · "
                f"PR {fmt_num(repo.get('prs_created'))} · "
                f"M {fmt_num(repo.get('prs_merged'))} · "
                f"R {fmt_num(repo.get('prs_reviewed'))} · "
                f"I {fmt_num(number(repo.get('issues_created')) + number(repo.get('issues_closed_related')))} · "
                f"功能 {fmt_num(repo.get('feature_points'))} · "
                f"Bug {fmt_num(repo.get('bug_fixes'))}"
            )
            rows.append((str(repo.get("repo") or ""), score, detail))
    if not rows:
        return '<p class="empty">暂无仓库分布。</p>'
    max_value = max(value for _, value, _ in rows) or 1
    return "".join(
        f"""
        <div class="bar-row repo-row">
          <div class="bar-name"><strong>{esc(name)}</strong><small>{esc(detail)}</small></div>
          <div class="bar-track"><span style="width:{bar_width(value, max_value)}"></span></div>
          <div class="bar-value">{esc(fmt_num(value))}<small>分</small></div>
        </div>
        """
        for name, value, detail in rows
    )


def theme_rows(github: dict[str, Any]) -> str:
    themes = ((github.get("contribution_portrait") or {}).get("themes") or [])[:6]
    items = []
    for theme in themes:
        if isinstance(theme, dict):
            items.append((str(theme.get("theme") or ""), number(theme.get("score"))))
    return bar_rows(items, "暂无投入主题。", "alt")


def theme_stack_card(github: dict[str, Any]) -> str:
    themes = ((github.get("contribution_portrait") or {}).get("themes") or [])[:6]
    items = []
    for idx, theme in enumerate(themes):
        if isinstance(theme, dict) and number(theme.get("score")) > 0:
            items.append((str(theme.get("theme") or ""), theme.get("score"), CHART_COLORS[idx % len(CHART_COLORS)]))
    return stacked_bar_card("主题投入占比", items)


def repo_matrix(github: dict[str, Any]) -> str:
    repos = [repo for repo in (github.get("top_repos") or [])[:8] if isinstance(repo, dict)]
    metrics = [
        ("commits", "C"),
        ("prs_merged", "M"),
        ("prs_reviewed", "R"),
        ("feature_points", "F"),
        ("bug_fixes", "B"),
    ]
    if not repos:
        return '<p class="empty">暂无仓库矩阵。</p>'
    max_by_key = {key: max(float(number(repo.get(key))) for repo in repos) or 1 for key, _ in metrics}
    rows = []
    for repo in repos:
        cells = []
        for key, label in metrics:
            value = number(repo.get(key))
            intensity = max(0.08, min(1.0, float(value) / max_by_key[key])) if value else 0.04
            cells.append(
                f'<span title="{esc(label)} {esc(fmt_num(value))}" style="opacity:{intensity:.2f}">{esc(fmt_num(value))}</span>'
            )
        rows.append(
            f"""
            <div class="matrix-row">
              <strong>{esc(short_label(repo.get('repo'), 28))}</strong>
              <div class="matrix-cells">{''.join(cells)}</div>
            </div>
            """
        )
    header = "".join(f"<span>{esc(label)}</span>" for _, label in metrics)
    return f"""
      <div class="matrix">
        <div class="matrix-head"><strong>Repo</strong><div>{header}</div></div>
        {''.join(rows)}
      </div>
    """


def repo_matrix_card(github: dict[str, Any]) -> str:
    return f"""
      <div class="panel-lite">
        <h3>仓库多指标矩阵</h3>
        {repo_matrix(github)}
      </div>
    """


def code_area_treemap(github: dict[str, Any]) -> str:
    rows = [row for row in ((github.get("engineering_outcomes") or {}).get("code_areas") or []) if isinstance(row, dict)]
    if not rows:
        return '<p class="empty">暂无代码区域拆解。</p>'
    total = sum(number(row.get("files")) for row in rows) or 1
    cells = []
    for row in rows[:8]:
        files = number(row.get("files"))
        width = max(12, pct_float(files, total))
        cells.append(
            f"""
            <div class="treemap-cell" style="flex-basis:{width:.2f}%; background:{esc(row.get('color') or '#1f6feb')}">
              <strong>{esc(row.get('label') or row.get('key'))}</strong>
              <span>{esc(fmt_num(files))}</span>
            </div>
            """
        )
    return '<div class="treemap">' + "".join(cells) + "</div>"


def work_type_chart(github: dict[str, Any]) -> str:
    rows = (github.get("engineering_outcomes") or {}).get("by_work_type") or []
    items = []
    for idx, row in enumerate(rows[:6]):
        if isinstance(row, dict):
            items.append((str(row.get("label") or row.get("key") or ""), row.get("count"), CHART_COLORS[idx % len(CHART_COLORS)]))
    return stacked_bar_card("工作类型结构", items)


def language_mix_card(github: dict[str, Any]) -> str:
    portfolio = github.get("project_portfolio") or {}
    totals: dict[str, float] = {}
    for project in (portfolio.get("projects") or [])[:12]:
        if not isinstance(project, dict):
            continue
        score = max(1.0, float(number(project.get("score")) or 1))
        for item in (project.get("top_languages") or [])[:3]:
            if isinstance(item, dict):
                language = str(item.get("language") or "Other")
                totals[language] = totals.get(language, 0.0) + score * float(number(item.get("pct")))
    if not totals:
        return '<div class="viz-card"><h3>语言结构</h3><p class="empty">暂无语言数据。</p></div>'
    items = [
        (language, value, CHART_COLORS[idx % len(CHART_COLORS)])
        for idx, (language, value) in enumerate(sorted(totals.items(), key=lambda pair: pair[1], reverse=True)[:6])
    ]
    return stacked_bar_card("语言结构", items)


def weekly_activity(github: dict[str, Any]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}

    def bucket_for(date_value: dt.datetime) -> dict[str, Any]:
        key = week_key(date_value)
        bucket = buckets.setdefault(key, {"week": key, "commits": 0, "prs": 0, "issues": 0})
        return bucket

    for item in github.get("commits") or []:
        if isinstance(item, dict):
            parsed = item_date(item, "authored_at", "created_at", "updated_at")
            if parsed:
                bucket_for(parsed)["commits"] += 1
    for item in ((github.get("prs") or {}).get("merged") or []):
        if isinstance(item, dict):
            parsed = item_date(item, "closed_at", "created_at", "updated_at")
            if parsed:
                bucket_for(parsed)["prs"] += 1
    for item in ((github.get("issues") or {}).get("closed_related") or []):
        if isinstance(item, dict):
            parsed = item_date(item, "closed_at", "created_at", "updated_at")
            if parsed:
                bucket_for(parsed)["issues"] += 1
    return [buckets[key] for key in sorted(buckets.keys())]


def weekly_activity_card(github: dict[str, Any]) -> str:
    weeks = weekly_activity(github)[-13:]
    if not weeks:
        return '<div class="panel-lite"><h3>季度周节奏</h3><p class="empty">暂无周趋势数据。</p></div>'
    max_total = max(number(item.get("commits")) + number(item.get("prs")) + number(item.get("issues")) for item in weeks) or 1
    bars = []
    for item in weeks:
        commits = number(item.get("commits"))
        prs = number(item.get("prs"))
        issues = number(item.get("issues"))
        total = commits + prs + issues
        height = max(8, min(100, float(total) / float(max_total) * 100))
        bars.append(
            f"""
            <div class="week-bar" title="{esc(item.get('week'))}: C {esc(fmt_num(commits))}, PR {esc(fmt_num(prs))}, I {esc(fmt_num(issues))}">
              <div class="week-stack" style="height:{height:.1f}%">
                <span class="week-commits" style="height:{pct_float(commits, total):.2f}%"></span>
                <span class="week-prs" style="height:{pct_float(prs, total):.2f}%"></span>
                <span class="week-issues" style="height:{pct_float(issues, total):.2f}%"></span>
              </div>
              <strong>{esc(str(item.get('week') or '')[-3:])}</strong>
            </div>
            """
        )
    return f"""
      <div class="panel-lite">
        <h3>季度周节奏</h3>
        <div class="week-chart">{''.join(bars)}</div>
      </div>
    """


def project_map(github: dict[str, Any]) -> str:
    projects = [p for p in ((github.get("project_portfolio") or {}).get("projects") or []) if isinstance(p, dict)]
    if not projects:
        return '<p class="empty">暂无项目地图。</p>'
    buckets: dict[str, list[dict[str, Any]]] = {}
    for project in projects[:30]:
        buckets.setdefault(project_bucket(project), []).append(project)
    max_score = max(float(number(project.get("score"))) for project in projects) or 1.0
    legend = """
      <div class="project-map-legend">
        <span><i class="legend-existing"></i>持续项目</span>
        <span><i class="legend-new"></i>新建仓库</span>
        <span><i class="legend-active"></i>新启动</span>
      </div>
    """
    bucket_html = []
    for bucket, bucket_projects in sorted(buckets.items(), key=lambda pair: sum(number(p.get("score")) for p in pair[1]), reverse=True):
        nodes = []
        for project in sorted(bucket_projects, key=lambda p: number(p.get("score")), reverse=True)[:8]:
            score = float(number(project.get("score")))
            size = 34 + min(62, score / max_score * 62)
            cls = "project-node"
            if project.get("is_new_repo"):
                cls += " is-new"
            elif project.get("is_newly_active"):
                cls += " is-active"
            label = project.get("display_name") or project.get("name") or project.get("repo")
            nodes.append(
                f"""
                <a class="{esc(cls)}" href="{esc(project.get('url') or '#')}" style="width:{size:.1f}px;height:{size:.1f}px" title="{esc(project.get('repo') or '')}">
                  <span>{esc(short_label(label, 11))}</span>
                </a>
                """
            )
        bucket_html.append(
            f"""
            <div class="project-bucket">
              <h3>{esc(bucket)}</h3>
              <div class="project-nodes">{''.join(nodes)}</div>
            </div>
            """
        )
    return legend + '<div class="project-map">' + "".join(bucket_html) + "</div>"


def project_map_card(github: dict[str, Any]) -> str:
    return f"""
      <div class="panel-lite">
        <h3>项目地图</h3>
        {project_map(github)}
      </div>
    """


def outcome_summary_cards(github: dict[str, Any]) -> str:
    outcomes = github.get("engineering_outcomes") or {}
    totals = outcomes.get("totals") or {}
    items = [
        (totals.get("feature_points"), "功能点"),
        (totals.get("bug_fixes"), "Bug 修复"),
        (totals.get("bug_like_closed_issues"), "Bug-like issue"),
        (totals.get("changed_files"), "变更文件"),
    ]
    return "".join(
        f"""
        <div class="mini github">
          <strong>{esc(fmt_num(value))}</strong>
          <span>{esc(label)}</span>
        </div>
        """
        for value, label in items
    )


def outcome_bar_rows(github: dict[str, Any]) -> str:
    rows = (github.get("engineering_outcomes") or {}).get("by_repo") or []
    items = []
    for row in rows[:10]:
        if not isinstance(row, dict):
            continue
        value = number(row.get("feature_points")) + number(row.get("bug_fixes"))
        detail = (
            f"功能 {fmt_num(row.get('feature_points'))} · "
            f"Bug {fmt_num(row.get('bug_fixes'))} · "
            f"文件 {fmt_num(row.get('changed_files'))}"
        )
        items.append((str(row.get("repo") or ""), value, detail))
    if not items:
        return '<p class="empty">暂无功能点 / bug 修复拆解。可能是旧 summary 或跳过了 outcome 采集。</p>'
    max_value = max(value for _, value, _ in items) or 1
    return "".join(
        f"""
        <div class="bar-row repo-row">
          <div class="bar-name"><strong>{esc(name)}</strong><small>{esc(detail)}</small></div>
          <div class="bar-track"><span class="outcome" style="width:{bar_width(value, max_value)}"></span></div>
          <div class="bar-value">{esc(fmt_num(value))}<small>项</small></div>
        </div>
        """
        for name, value, detail in items
    )


def code_area_rows(github: dict[str, Any]) -> str:
    rows = (github.get("engineering_outcomes") or {}).get("code_areas") or []
    if not rows:
        return '<p class="empty">暂无代码区域拆解。需要成功读取 PR files API。</p>'
    max_value = max(number(row.get("files")) for row in rows) or 1
    return "".join(
        f"""
        <div class="bar-row">
          <div class="bar-name"><strong>{esc(row.get('label') or row.get('key'))}</strong><small>{esc(fmt_num(row.get('files')))} 个文件</small></div>
          <div class="bar-track"><span style="width:{bar_width(row.get('files'), max_value)}; background:{esc(row.get('color') or '#1f6feb')}"></span></div>
          <div class="bar-value">{esc(fmt_num(row.get('files')))}<small>文件</small></div>
        </div>
        """
        for row in rows[:8]
        if isinstance(row, dict)
    )


def top_code_pr_rows(github: dict[str, Any]) -> str:
    rows = (github.get("engineering_outcomes") or {}).get("top_code_prs") or []
    if not rows:
        return '<p class="empty">暂无 PR 代码变更排行。</p>'
    max_value = max(number(row.get("changed_files")) for row in rows[:8]) or 1
    rows_html = []
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "")
        url = str(row.get("url") or "")
        title_html = f'<a href="{esc(url)}">{esc(title)}</a>' if url else esc(title)
        rows_html.append(
        f"""
        <div class="bar-row code-pr-row">
          <div class="bar-name"><strong>{title_html}</strong><small>{esc(row.get('repo') or '')} #{esc(row.get('number') or '')} · {esc(row.get('work_type') or row.get('outcome') or '')}</small></div>
          <div class="bar-track"><span class="code" style="width:{bar_width(row.get('changed_files'), max_value)}"></span></div>
          <div class="bar-value">{esc(fmt_num(row.get('changed_files')))}<small>文件</small></div>
        </div>
        """
    )
    return "".join(rows_html)


def portfolio_cards(projects: list[dict[str, Any]], empty: str, limit: int = 6) -> str:
    if not projects:
        return f'<p class="empty">{esc(empty)}</p>'
    cards = []
    for project in projects[:limit]:
        badges = []
        if project.get("is_new_repo"):
            badges.append("新建仓库")
        elif project.get("is_newly_active"):
            badges.append("新启动")
        for key in ("role", "difficulty"):
            if project.get(key):
                badges.append(str(project.get(key)))
        badges.extend(project.get("interesting_work") or [])
        badges.extend(project.get("tags") or [])
        stats = [
            f"功能 {fmt_num(project.get('feature_points'))}",
            f"修复 {fmt_num(project.get('bug_fixes'))}",
            f"PR {fmt_num(project.get('merged_prs'))}",
            f"Commit {fmt_num(project.get('commits'))}",
        ]
        value_lines = []
        for key in ("business_impact", "customer_value", "highlight"):
            if project.get(key):
                value_lines.append(str(project.get(key)))
        pr_links = []
        for pr in representative_pr_items(project, 3):
            title = str(pr.get("title") or "")
            url = str(pr.get("url") or "")
            pr_links.append(f'<li><a href="{esc(url)}">#{esc(pr.get("number"))}</a><span>{esc(title)}</span></li>' if url else f'<li><span>{esc(title)}</span></li>')
        attribution = infer_project_value_attribution(project)
        attribution_chips = "".join(f'<span>{esc(item.get("label") or "")}</span>' for item in attribution[:3])
        attribution_rows = []
        for item in attribution[:3]:
            evidence = item.get("evidence") or []
            evidence_html = "".join(f"<li>{esc(line)}</li>" for line in evidence[:3])
            attribution_rows.append(
                f"""
                <div class="project-value-row">
                  <div>
                    <strong>{esc(item.get('label') or '')}</strong>
                    <small>{esc(item.get('basis') or '')}</small>
                  </div>
                  <b>{esc(fmt_num(item.get('score')))}</b>
                  {f'<ul>{evidence_html}</ul>' if evidence_html else ''}
                </div>
                """
            )
        evidence_metrics = [
            ("状态", project_status_label(project)),
            ("功能点", fmt_num(project.get("feature_points"))),
            ("Bug 修复", fmt_num(project.get("bug_fixes"))),
            ("合并 PR", fmt_num(project.get("merged_prs"))),
            ("Commit", fmt_num(project.get("commits"))),
            ("变更文件", fmt_num(project.get("changed_files"))),
        ]
        evidence_grid = "".join(
            f"""
            <div>
              <span>{esc(label)}</span>
              <strong>{esc(value)}</strong>
            </div>
            """
            for label, value in evidence_metrics
        )
        purpose = project.get("purpose") or "暂无项目定位。"
        narrative = formal_project_text(project.get("narrative") or "")
        cards.append(
            f"""
            <article class="project-card">
              <div class="project-head">
                <div>
                  <h3><a href="{esc(project.get('url') or '')}">{esc(project.get('repo') or '')}</a></h3>
                  <small>{esc(project.get('theme') or '')}</small>
                </div>
                <strong>{esc(fmt_num(project.get('score')))}</strong>
              </div>
              <p>{esc(purpose)}</p>
              {f'<div class="project-attribution">{attribution_chips}</div>' if attribution_chips else ''}
              <div class="project-badges">{''.join(f'<span>{esc(item)}</span>' for item in badges[:5])}</div>
              <div class="project-stats">{''.join(f'<b>{esc(item)}</b>' for item in stats)}</div>
              {f'<div class="project-value">{"".join(f"<strong>{esc(line)}</strong>" for line in value_lines[:2])}</div>' if value_lines else ''}
              {f'<div class="project-narrative">{esc(narrative)}</div>' if narrative else ''}
              <details class="project-detail">
                <summary><span>项目证据</span><i></i></summary>
                <div class="project-detail-body">
                  <div class="project-detail-block">
                    <h4>项目定位</h4>
                    <p>{esc(purpose)}</p>
                  </div>
                  <div class="project-evidence-grid">{evidence_grid}</div>
                  {f'<div class="project-detail-block"><h4>价值归因</h4><div class="project-value-rows">{"".join(attribution_rows)}</div></div>' if attribution_rows else ''}
                  {f'<div class="project-detail-block"><h4>代表 PR</h4><ul class="project-prs">{"".join(pr_links)}</ul></div>' if pr_links else ''}
                  <div class="project-boundary">来源：GitHub 仓库 metadata、README 摘要、PR/commit 标题和合并 PR 文件统计；价值归因为展示层推断，不改写原始 GitHub 数据。</div>
                </div>
              </details>
            </article>
            """
        )
    return '<div class="project-grid">' + "".join(cards) + "</div>"


def portfolio_section(github: dict[str, Any]) -> str:
    portfolio = github.get("project_portfolio") or {}
    totals = portfolio.get("totals") or {}
    cards = [
        (totals.get("projects"), "项目画像"),
        (totals.get("new_repositories"), "新建仓库"),
        (totals.get("newly_active_projects"), "新启动项目"),
        (totals.get("interesting_projects"), "重点线索"),
    ]
    metric_html = "".join(
        f"""
        <div class="mini github">
          <strong>{esc(fmt_num(value))}</strong>
          <span>{esc(label)}</span>
        </div>
        """
        for value, label in cards
    )
    return f"""
      <div class="mini-grid portfolio-metrics">{metric_html}</div>
      <div class="section-head" style="margin-top:14px">
        <h3>新建仓库</h3>
      </div>
      {portfolio_cards(portfolio.get("new_repositories") or [], "本季度没有识别到新建仓库。", 4)}
      <div class="section-head" style="margin-top:14px">
        <h3>新启动 / 重新活跃项目</h3>
      </div>
      {portfolio_cards(portfolio.get("newly_active_projects") or [], "本季度没有识别到新启动项目。", 6)}
      <div class="section-head" style="margin-top:14px">
        <h3>重点工作线索</h3>
      </div>
      {portfolio_cards(portfolio.get("interesting_projects") or [], "暂无可稳定抽取的重点工作线索。", 6)}
    """


def module_cards(feishu: dict[str, Any]) -> str:
    modules = feishu.get("modules") or {}
    labels = {"docs": "飞书文档", "messages": "聊天消息", "calendar": "日历日程"}
    cards = []
    for key in ("docs", "messages", "calendar"):
        module = modules.get(key) or {}
        status = module_status(module)
        missing = module.get("missing_scopes") or []
        hint = module.get("hint") or module.get("error") or ""
        cards.append(
            f"""
            <div class="module-card module-{esc(STATUS_TONE.get(status, 'idle'))}">
              <div class="module-top">
                <strong>{esc(labels[key])}</strong>
                {status_badge(status)}
              </div>
              {f'<p>{esc(hint)}</p>' if hint else ''}
              <div class="scope-list">{''.join(f'<code>{esc(scope)}</code>' for scope in missing)}</div>
            </div>
            """
        )
    return "".join(cards)


def evidence_cards(items: list[dict[str, Any]], empty: str, limit: int = 6) -> str:
    if not items:
        return f'<p class="empty">{esc(empty)}</p>'
    cards = []
    for item in items[:limit]:
        title = item.get("title") or item.get("repo") or item.get("sha") or "Untitled"
        repo = item.get("repo")
        number_value = item.get("number")
        when = item.get("closed_at") or item.get("created_at") or item.get("authored_at") or item.get("updated_at") or item.get("start_time")
        url = item.get("url") or item.get("html_url") or ""
        meta = " · ".join(str(x) for x in [repo, f"#{number_value}" if number_value else "", when] if x)
        title_html = f'<a href="{esc(url)}">{esc(title)}</a>' if url else esc(title)
        cards.append(
            f"""
            <div class="evidence-card">
              <div class="evidence-title">{title_html}</div>
              <div class="evidence-meta">{esc(meta)}</div>
            </div>
            """
        )
    return "".join(cards)


def feishu_doc_tabs(feishu: dict[str, Any]) -> str:
    docs = ((feishu.get("modules") or {}).get("docs") or {})
    discovery = docs.get("discovery") or {}
    reading = docs.get("reading") or {}
    discovered = docs.get("discovered") or discovery.get("results") or []
    documents = docs.get("documents") or reading.get("documents") or []
    discovery_message = discovery.get("hint") or discovery.get("error") or ""
    reading_message = reading.get("hint") or reading.get("error") or ""
    return f"""
      <div class="nested-tabs" data-tabs="feishu-docs">
        <div class="tab-list small" role="tablist" aria-label="飞书文档子模块">
          <button class="tab-button is-active" type="button" role="tab" aria-selected="true" data-tab-target="feishu-doc-discovery">文档发现 <span>{esc(len(discovered))}</span></button>
          <button class="tab-button" type="button" role="tab" aria-selected="false" data-tab-target="feishu-doc-reading">内容读取 <span>{esc(len(documents))}</span></button>
        </div>
        <div class="tab-panel is-active" role="tabpanel" data-tab-panel="feishu-doc-discovery">
          {f'<div class="callout">{status_badge(str(discovery.get("status") or "skipped"))}<span>{esc(discovery_message)}</span></div>' if discovery_message else ''}
          {evidence_cards(discovered, '暂无发现候选。缺少 search:docs:read 时这里会为空。', 4)}
        </div>
        <div class="tab-panel" role="tabpanel" data-tab-panel="feishu-doc-reading">
          {f'<div class="callout">{status_badge(str(reading.get("status") or "skipped"))}<span>{esc(reading_message)}</span></div>' if reading_message else ''}
          {evidence_cards(documents, '暂无读取内容。缺少 docx:document:readonly 时这里会为空。', 4)}
        </div>
      </div>
    """


def methodology(summary: dict[str, Any]) -> str:
    github = summary["github"]
    feishu = summary["feishu"]
    github_notes = github.get("notes") or []
    feishu_notes = feishu.get("notes") or []
    missing = summary["modules"]["feishu"].get("missing_scopes") or []
    items = [
        "总面板只读取两个独立 summary.json，不直接查询或写入 GitHub / 飞书。",
        "GitHub 的相关关闭 issue 是 involves 用户且在区间内关闭的 issue，不能直接等同亲自解决。",
        "GitHub 的 review 参与 PR 是 PR 集合数，不是单次 review 次数。",
    ]
    items.extend(str(note) for note in github_notes[:2])
    items.extend(str(note) for note in feishu_notes[:2])
    if missing:
        items.append(f"飞书仍缺少 scope：{', '.join(missing)}。")
    return "".join(f"<li>{esc(item)}</li>" for item in items)


def render_html(summary: dict[str, Any]) -> str:
    github = summary["github"]
    feishu = summary["feishu"]
    metrics = summary["metrics"]
    modules = summary["modules"]
    sources = summary["sources"]
    out = Path(summary["output_dir"])
    github_index = rel_link(sources.get("github_index") or "", out)
    feishu_index = rel_link(sources.get("feishu_index") or "", out)
    feishu_metrics = feishu.get("metrics") or {}
    title = f"{summary['period_label']} 季度工作总面板"
    source_items = [
        ("GitHub", modules["github"]["status"], github_index),
        ("飞书", modules["feishu"]["status"], feishu_index),
    ]
    source_html = "".join(
        f'<a class="source-pill" href="{esc(link)}"><span>{esc(label)}</span>{status_badge(status)}</a>' if link else f'<span class="source-pill"><span>{esc(label)}</span>{status_badge(status)}</span>'
        for label, status, link in source_items
    )
    mode_html = """
      <div class="mode-row" aria-label="展示模式">
        <button class="mode-button is-active" type="button" data-view-mode="normal">全量</button>
        <button class="mode-button" type="button" data-view-mode="presentation">展示</button>
      </div>
    """
    merged_prs = ((github.get("prs") or {}).get("merged") or [])
    created_issues = ((github.get("issues") or {}).get("created") or [])
    closed_issues = ((github.get("issues") or {}).get("closed_related") or [])
    commits = github.get("commits") or []
    feishu_modules = feishu.get("modules") or {}
    message_status_text = (feishu_modules.get("messages") or {}).get("hint") or (feishu_modules.get("messages") or {}).get("error") or ""
    calendar_status_text = (feishu_modules.get("calendar") or {}).get("hint") or (feishu_modules.get("calendar") or {}).get("error") or ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #657084;
      --quiet: #8b95a5;
      --canvas: #eef1f4;
      --panel: #fffdf8;
      --paper: #ffffff;
      --paper-soft: #f7f4ed;
      --line: #dce2ea;
      --line-soft: #e9edf3;
      --github: #1f6feb;
      --feishu: #0f8f83;
      --green: #157b50;
      --amber: #ae6817;
      --red: #b83a45;
      --violet: #6750b5;
      --shadow: 0 18px 48px rgba(31, 41, 55, 0.10);
      --shadow-sm: 0 1px 3px rgba(31, 41, 55, 0.10);
      --radius: 8px;
      --gap-section: 16px;
      --gap-card: 10px;
      --pad-section: 20px;
      --pad-card: 12px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }}
    body {{
      margin: 0;
      font-family: -apple-system, "SF Pro Text", "PingFang SC", "Noto Sans SC", sans-serif;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(23,32,51,.04) 1px, transparent 1px),
        linear-gradient(180deg, #fbf8f0 0, var(--canvas) 430px, #e7edf2 100%);
      background-size: 44px 44px, auto;
      line-height: 1.72;
      font-variant-numeric: tabular-nums;
    }}
    a {{ color: #174ea6; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .skip-link {{ position: absolute; left: -999px; top: 12px; padding: 8px 10px; background: var(--ink); color: white; z-index: 10; }}
    .skip-link:focus {{ left: 12px; }}
    .page {{ max-width: 1320px; margin: 0 auto; padding: 22px 20px 58px; }}
    .masthead {{
      background: var(--panel);
      border-radius: var(--radius);
      box-shadow: 0 14px 38px rgba(31, 41, 55, 0.09);
      border: 1px solid rgba(23,32,51,.10);
      padding: 24px;
    }}
    .masthead-grid {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 18px; align-items: start; }}
    h1 {{ margin: 0; font-size: clamp(32px, 4vw, 56px); line-height: 1.02; letter-spacing: 0; text-wrap: balance; }}
    h2 {{ margin: 0; font-size: 22px; line-height: 1.2; letter-spacing: 0; text-wrap: balance; }}
    h3 {{ margin: 0 0 12px; font-size: 15px; line-height: 1.35; letter-spacing: 0; }}
    .meta {{ color: var(--muted); font-size: 14px; margin-top: 9px; max-width: 780px; }}
    .source-tools {{ display: grid; justify-items: end; gap: 8px; min-width: 0; }}
    .source-row {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }}
    .source-pill {{ min-height: 38px; display: inline-flex; align-items: center; gap: 9px; padding: 7px 10px; border-radius: 999px; background: var(--paper-soft); box-shadow: inset 0 0 0 1px var(--line); color: var(--ink); white-space: nowrap; }}
    .mode-row {{ display: inline-flex; gap: 4px; padding: 4px; border-radius: 999px; background: #e8edf3; box-shadow: inset 0 0 0 1px var(--line); }}
    .mode-button {{ min-width: 50px; min-height: 32px; padding: 5px 10px; border: 0; border-radius: 999px; color: #526071; background: transparent; font: inherit; font-size: 12px; font-weight: 820; cursor: pointer; transition-property: transform, background-color, color, opacity; transition-duration: 140ms; transition-timing-function: cubic-bezier(.16,1,.3,1); }}
    .mode-button.is-active {{ color: var(--ink); background: var(--paper); box-shadow: 0 1px 3px rgba(31,41,55,.12); }}
    .mode-button:active {{ transform: scale(.96); }}
    .mode-button:focus-visible, .tab-button:focus-visible, .project-detail summary:focus-visible {{ outline: 2px solid rgba(31,111,235,.52); outline-offset: 2px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); margin-top: 18px; background: var(--paper); border-top: 1px solid var(--line); border-left: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; }}
    .metric {{ min-height: 112px; padding: 13px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }}
    .metric-value {{ font-size: clamp(27px, 3vw, 42px); font-weight: 830; line-height: 1; white-space: nowrap; }}
    .metric-label {{ margin-top: 9px; font-weight: 760; }}
    .growth {{ margin-left: 8px; color: var(--green); font-size: 13px; font-weight: 760; vertical-align: middle; }}
    section {{ margin-top: var(--gap-section); padding: var(--pad-section); background: rgba(255,253,248,.94); border-radius: var(--radius); border: 1px solid rgba(23,32,51,.10); box-shadow: var(--shadow-sm); }}
    .section-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }}
    .panel-lite {{ padding: 16px; background: var(--paper-soft); border-radius: var(--radius); box-shadow: inset 0 0 0 1px var(--line); }}
    .insights {{ margin: 0; padding-left: 20px; }}
    .insights li {{ margin: 7px 0; }}
    .signal-rail {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 12px; border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; background: var(--paper); }}
    .signal-item {{ min-height: 70px; display: grid; grid-template-columns: minmax(0, 1fr) auto; grid-template-rows: auto auto; gap: 6px 10px; align-content: center; padding: 10px 12px; border-right: 1px solid var(--line-soft); }}
    .signal-item:last-child {{ border-right: 0; }}
    .signal-item strong {{ color: var(--muted); font-size: 12px; line-height: 1.2; }}
    .signal-item b {{ grid-column: 1 / -1; color: var(--ink); font-size: 17px; line-height: 1.15; overflow-wrap: anywhere; }}
    .signal-item .confidence {{ grid-column: 2; grid-row: 1; justify-self: end; font-size: 10px; min-height: 20px; padding: 2px 6px; }}
    .quality-rail {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 1px; margin-top: 10px; overflow: hidden; border: 1px solid var(--line); border-radius: var(--radius); background: var(--line); }}
    .quality-item {{ min-height: 58px; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 5px 8px; align-items: center; padding: 8px 10px; background: #fbfcfd; }}
    .quality-item strong {{ color: var(--muted); font-size: 11px; line-height: 1.2; }}
    .quality-item b {{ text-align: right; font-size: 13px; line-height: 1; }}
    .quality-item .confidence {{ grid-column: 1 / -1; width: fit-content; font-size: 10px; min-height: 18px; padding: 1px 6px; }}
    .quality-meter {{ height: 6px; overflow: hidden; border-radius: 999px; background: #e4eaf1; }}
    .quality-meter span {{ display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--green), var(--github)); }}
    .confidence {{ display: inline-flex; align-items: center; min-height: 23px; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 780; white-space: nowrap; }}
    .confidence-high {{ color: #0f6b43; background: #e3f4ea; }}
    .confidence-medium {{ color: #7a4b0a; background: #fff0cc; }}
    .confidence-low {{ color: #982f37; background: #fde9eb; }}
    .confidence-manual {{ color: #4d3b8f; background: #ece8ff; }}
    .value-rail {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin-top: 10px; overflow: hidden; border: 1px solid var(--line); border-radius: var(--radius); background: var(--line); }}
    .value-step {{ min-height: 74px; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 4px 8px; align-content: center; padding: 10px 12px; background: #fbfcfd; }}
    .value-step > span {{ color: var(--quiet); font-size: 11px; font-weight: 820; line-height: 1; }}
    .value-step strong {{ color: var(--muted); font-size: 12px; line-height: 1.15; }}
    .value-step > b {{ color: var(--ink); font-size: 22px; line-height: .95; text-align: right; }}
    .value-step em {{ grid-column: 2 / -1; color: var(--ink); font-style: normal; font-size: 12px; font-weight: 760; }}
    .value-bar {{ grid-column: 1 / -1; height: 6px; overflow: hidden; border-radius: 999px; background: #e4eaf1; }}
    .value-bar b {{ display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--github), var(--green)); }}
    .summary-evidence-grid {{ display: grid; grid-template-columns: minmax(320px, .85fr) minmax(520px, 1.15fr); gap: 16px; align-items: start; }}
    .insight-panel {{ padding: 16px; border-radius: var(--radius); background: var(--paper); box-shadow: inset 0 0 0 1px var(--line); }}
    .insight-panel .insights {{ display: grid; gap: 10px; padding-left: 24px; }}
    .insight-panel .insights li {{ margin: 0; padding-bottom: 10px; border-bottom: 1px solid var(--line-soft); line-height: 1.58; }}
    .insight-panel .insights li:last-child {{ padding-bottom: 0; border-bottom: 0; }}
    .evidence-rail {{ display: grid; gap: 8px; }}
    .chain-compact {{ display: grid; grid-template-columns: minmax(0, 1fr); gap: 7px; padding: 12px; border-radius: var(--radius); background: #fbfcfd; box-shadow: inset 0 0 0 1px var(--line-soft); }}
    .chain-compact-top {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
    .chain-compact-top > span {{ min-height: 22px; display: inline-flex; align-items: center; padding: 2px 7px; border-radius: 999px; color: #344054; background: var(--paper-soft); font-size: 11px; font-weight: 780; }}
    .chain-compact h3 {{ margin: 0; font-size: 14px; }}
    .chain-compact p {{ margin: 0; color: #344054; font-size: 12px; line-height: 1.5; }}
    .chain-compact small {{ color: var(--muted); font-size: 11px; line-height: 1.35; overflow-wrap: anywhere; }}
    .chain-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
    .chain-card {{ padding: 15px; background: var(--paper); border-radius: var(--radius); box-shadow: 0 1px 3px rgba(31,41,55,.10); }}
    .chain-head {{ display: flex; justify-content: space-between; align-items: start; gap: 10px; }}
    .chain-head h3 {{ margin: 0; }}
    .chain-head small {{ color: var(--muted); font-size: 11px; }}
    .audit-path {{ display: grid; grid-template-columns: auto 1fr auto 1fr auto; gap: 8px; align-items: center; margin-top: 12px; }}
    .audit-path span {{ min-height: 24px; display: inline-flex; align-items: center; justify-content: center; padding: 3px 8px; border-radius: 999px; color: #344054; background: var(--paper-soft); box-shadow: inset 0 0 0 1px var(--line); font-size: 11px; font-weight: 760; white-space: nowrap; }}
    .audit-path i {{ height: 1px; background: var(--line); }}
    .chain-card p {{ margin: 12px 0 0; color: #344054; font-size: 13px; line-height: 1.65; }}
    .chain-list {{ list-style: none; margin: 12px 0 0; padding: 0; display: grid; gap: 7px; }}
    .chain-list li {{ display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px; align-items: start; padding: 8px; background: var(--paper-soft); border-radius: 7px; }}
    .chain-kind {{ padding: 2px 6px; border-radius: 999px; color: #174ea6; background: #e9efff; font-size: 11px; font-weight: 780; text-transform: uppercase; }}
    .chain-list strong {{ display: block; font-size: 12px; line-height: 1.35; overflow-wrap: anywhere; }}
    .chain-list small {{ display: block; margin-top: 3px; color: var(--muted); font-size: 11px; line-height: 1.35; overflow-wrap: anywhere; }}
    .chain-caveat {{ margin-top: 10px; padding-top: 9px; border-top: 1px solid var(--line-soft); color: var(--muted); font-size: 12px; line-height: 1.5; }}
    .mini-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }}
    .mini {{ min-height: 86px; padding: 11px; background: var(--paper); border-radius: var(--radius); box-shadow: 0 1px 3px rgba(31,41,55,.10); }}
    .mini strong {{ display: block; font-size: 25px; line-height: 1; }}
    .mini span {{ display: block; margin-top: 7px; color: var(--muted); font-size: 12px; line-height: 1.35; }}
    .mini small {{ display: block; margin-top: 6px; color: var(--quiet); font-size: 11px; line-height: 1.35; }}
    .mini.github {{ box-shadow: inset 0 3px 0 var(--github), 0 1px 3px rgba(31,41,55,.10); }}
    .mini.feishu {{ box-shadow: inset 0 3px 0 var(--feishu), 0 1px 3px rgba(31,41,55,.10); }}
    .chart-grid {{ display: grid; grid-template-columns: minmax(360px, 1.05fr) minmax(340px, .95fr); gap: 16px; }}
    .viz-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }}
    .viz-grid.three {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .viz-card {{ min-height: 188px; padding: 14px; background: var(--paper); border-radius: var(--radius); box-shadow: 0 1px 3px rgba(31,41,55,.10); }}
    .viz-card h3 {{ margin-bottom: 12px; }}
    .donut-wrap {{ display: grid; grid-template-columns: 104px minmax(0, 1fr); gap: 12px; align-items: center; }}
    .donut {{ width: 104px; aspect-ratio: 1; border-radius: 50%; display: grid; place-items: center; box-shadow: inset 0 0 0 1px rgba(23,32,51,.08); }}
    .donut > div {{ width: 64px; aspect-ratio: 1; border-radius: 50%; display: grid; place-items: center; align-content: center; background: var(--paper); box-shadow: 0 1px 3px rgba(31,41,55,.14); }}
    .donut strong {{ font-size: 17px; line-height: 1; }}
    .donut span {{ margin-top: 3px; color: var(--muted); font-size: 10px; line-height: 1; }}
    .legend-list {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 7px; }}
    .legend-list li {{ display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 7px; align-items: center; font-size: 12px; line-height: 1.25; }}
    .legend-list strong {{ text-align: right; }}
    .legend-dot {{ width: 8px; height: 8px; border-radius: 999px; }}
    .legend-list.compact {{ margin-top: 10px; }}
    .lane-grid {{ display: grid; gap: 9px; }}
    .lane-row {{ display: grid; grid-template-columns: minmax(140px, 190px) 1fr 68px; gap: 12px; align-items: center; padding: 10px; background: var(--paper); border-radius: 7px; box-shadow: inset 0 0 0 1px var(--line-soft); }}
    .lane-row strong {{ display: block; font-size: 13px; line-height: 1.25; }}
    .lane-row small {{ display: block; margin-top: 3px; color: var(--muted); font-size: 11px; line-height: 1.25; overflow-wrap: anywhere; }}
    .lane-row b {{ text-align: right; font-size: 18px; line-height: 1; }}
    .lane-track {{ height: 13px; border-radius: 999px; overflow: hidden; background: #e4eaf1; }}
    .lane-track span {{ display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--green), var(--github)); }}
    .focus-board {{ display: grid; gap: 10px; }}
    .focus-group {{ padding: 10px; border-radius: 7px; background: var(--paper); box-shadow: inset 0 0 0 1px var(--line-soft); }}
    .focus-group > strong {{ display: block; margin-bottom: 8px; font-size: 13px; }}
    .focus-group > div {{ display: flex; flex-wrap: wrap; gap: 7px; }}
    .focus-chip {{ --share: 20%; min-height: 31px; display: inline-flex; align-items: center; gap: 8px; padding: 5px 8px; border-radius: 999px; background: linear-gradient(90deg, rgba(31,111,235,.16) var(--share), #eef2f7 var(--share)); color: #174ea6; font-size: 12px; line-height: 1; box-shadow: inset 0 0 0 1px rgba(31,111,235,.12); }}
    .focus-chip b {{ max-width: 160px; overflow: hidden; text-overflow: clip; white-space: nowrap; }}
    .focus-chip em {{ color: var(--ink); font-style: normal; font-weight: 820; }}
    .stacked-bar {{ display: flex; height: 18px; overflow: hidden; border-radius: 999px; background: #e4eaf1; box-shadow: inset 0 0 0 1px rgba(23,32,51,.08); }}
    .stacked-bar span {{ min-width: 2px; }}
    .delta-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .delta-tile {{ min-height: 62px; padding: 9px; background: var(--paper-soft); border-radius: 7px; box-shadow: inset 0 0 0 1px var(--line); }}
    .delta-tile span {{ display: block; color: var(--muted); font-size: 11px; line-height: 1.2; }}
    .delta-tile strong {{ display: block; margin-top: 6px; font-size: 18px; line-height: 1; }}
    .delta-tile i {{ display: block; height: 5px; margin-top: 8px; overflow: hidden; border-radius: 999px; background: #e0e6ee; }}
    .delta-tile b {{ display: block; height: 100%; border-radius: inherit; background: var(--green); }}
    .delta-down b {{ background: var(--red); }}
    .delta-flat b {{ background: var(--quiet); }}
    .matrix {{ display: grid; gap: 6px; }}
    .matrix-head, .matrix-row {{ display: grid; grid-template-columns: minmax(160px, 1fr) minmax(220px, 1.25fr); gap: 10px; align-items: center; }}
    .matrix-head {{ color: var(--muted); font-size: 11px; font-weight: 760; }}
    .matrix-head div, .matrix-cells {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 5px; }}
    .matrix-row strong {{ min-width: 0; overflow-wrap: anywhere; font-size: 12px; line-height: 1.25; }}
    .matrix-cells span {{ min-height: 26px; display: grid; place-items: center; border-radius: 6px; background: var(--github); color: white; font-size: 11px; font-weight: 760; }}
    .treemap {{ display: flex; flex-wrap: wrap; gap: 6px; min-height: 190px; }}
    .treemap-cell {{ min-width: 112px; min-height: 82px; flex-grow: 1; padding: 9px; border-radius: 7px; color: white; display: grid; align-content: space-between; box-shadow: inset 0 0 0 1px rgba(255,255,255,.22); }}
    .treemap-cell strong {{ font-size: 12px; line-height: 1.25; }}
    .treemap-cell span {{ font-size: 22px; line-height: 1; font-weight: 820; }}
    .week-chart {{ height: 220px; display: grid; grid-template-columns: repeat(13, minmax(18px, 1fr)); gap: 7px; align-items: end; padding-top: 8px; }}
    .week-bar {{ height: 100%; min-width: 0; display: grid; grid-template-rows: 1fr auto; gap: 7px; align-items: end; }}
    .week-stack {{ width: 100%; min-height: 8px; align-self: end; display: flex; flex-direction: column-reverse; overflow: hidden; border-radius: 7px 7px 3px 3px; background: #dfe6ee; box-shadow: inset 0 0 0 1px rgba(23,32,51,.08); }}
    .week-stack span {{ min-height: 2px; }}
    .week-commits {{ background: var(--github); }}
    .week-prs {{ background: var(--green); }}
    .week-issues {{ background: var(--amber); }}
    .week-bar strong {{ color: var(--muted); font-size: 10px; line-height: 1; text-align: center; }}
    .project-map-legend {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; color: var(--muted); font-size: 12px; font-weight: 760; }}
    .project-map-legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
    .project-map-legend i {{ width: 9px; height: 9px; border-radius: 50%; background: #e9efff; box-shadow: inset 0 0 0 1px rgba(31,111,235,.16); }}
    .project-map-legend .legend-new {{ background: #e3f4ea; box-shadow: inset 0 0 0 1px rgba(21,123,80,.18); }}
    .project-map-legend .legend-active {{ background: #fff0cc; box-shadow: inset 0 0 0 1px rgba(174,104,23,.18); }}
    .project-map {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}
    .project-bucket {{ min-height: 152px; padding: 12px; background: var(--paper); border-radius: var(--radius); box-shadow: 0 1px 3px rgba(31,41,55,.10); }}
    .project-bucket h3 {{ margin-bottom: 10px; font-size: 13px; }}
    .project-nodes {{ min-height: 98px; display: flex; flex-wrap: wrap; align-items: center; gap: 7px; }}
    .project-node {{ display: grid; place-items: center; padding: 5px; border-radius: 50%; background: #e9efff; color: #174ea6; box-shadow: inset 0 0 0 1px rgba(31,111,235,.16); text-align: center; text-decoration: none; }}
    .project-node span {{ max-width: 100%; color: inherit; font-size: 10px; font-weight: 780; line-height: 1.05; overflow-wrap: anywhere; }}
    .project-node.is-new {{ background: #e3f4ea; color: #0f6b43; box-shadow: inset 0 0 0 1px rgba(21,123,80,.18); }}
    .project-node.is-active {{ background: #fff0cc; color: #7a4b0a; box-shadow: inset 0 0 0 1px rgba(174,104,23,.18); }}
    .change-map {{ display: grid; grid-template-columns: minmax(380px, 1.08fr) minmax(240px, .72fr); gap: 12px; align-items: start; }}
    .change-metrics {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }}
    .change-metric {{ min-height: 96px; padding: 11px; border-radius: 7px; background: var(--paper); box-shadow: inset 0 0 0 1px var(--line-soft); }}
    .change-metric span {{ display: block; color: var(--muted); font-size: 11px; line-height: 1.2; }}
    .change-metric strong {{ display: block; margin-top: 8px; font-size: 25px; line-height: 1; }}
    .change-metric em {{ display: inline-flex; align-items: center; min-height: 22px; margin-top: 8px; padding: 2px 7px; border-radius: 999px; color: #526071; background: #edf1f6; font-style: normal; font-size: 11px; font-weight: 820; }}
    .change-up em {{ color: #0f6b43; background: #e3f4ea; }}
    .change-down em {{ color: #982f37; background: #fde9eb; }}
    .change-lanes {{ display: grid; gap: 7px; }}
    .change-lane {{ display: grid; grid-template-columns: minmax(78px, 110px) 1fr 34px; gap: 8px; align-items: center; padding: 8px; border-radius: 7px; background: var(--paper); box-shadow: inset 0 0 0 1px var(--line-soft); }}
    .change-lane span {{ color: var(--muted); font-size: 12px; font-weight: 760; }}
    .change-lane div {{ height: 10px; overflow: hidden; border-radius: 999px; background: #e4eaf1; }}
    .change-lane b {{ display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--amber), var(--green)); }}
    .change-lane strong {{ text-align: right; font-size: 14px; line-height: 1; }}
    .change-projects {{ grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 7px; }}
    .change-projects a, .change-projects > span {{ max-width: 100%; display: inline-flex; align-items: center; gap: 7px; padding: 6px 8px; border-radius: 999px; background: #eef2f7; color: #344054; box-shadow: inset 0 0 0 1px var(--line-soft); font-size: 12px; font-weight: 760; overflow-wrap: anywhere; }}
    .change-projects a span, .change-projects > span span {{ color: #174ea6; font-size: 11px; font-weight: 820; }}
    .change-boundary {{ grid-column: 1 / -1; padding: 9px 10px; border-radius: 7px; color: var(--muted); background: #eef2f7; font-size: 11px; line-height: 1.45; }}
    .project-quadrant {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    .quadrant-cell {{ min-height: 152px; padding: 12px; border-radius: var(--radius); background: var(--paper); box-shadow: inset 0 0 0 1px var(--line-soft); }}
    .quadrant-title {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }}
    .quadrant-title strong {{ font-size: 13px; }}
    .quadrant-title em {{ min-width: 26px; height: 26px; display: grid; place-items: center; border-radius: 999px; color: white; background: var(--github); font-style: normal; font-size: 12px; font-weight: 820; }}
    .quadrant-items {{ display: flex; flex-wrap: wrap; gap: 7px; }}
    .quadrant-items a, .quadrant-items > span {{ max-width: 100%; display: inline-flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 999px; background: #eef2f7; color: #344054; box-shadow: inset 0 0 0 1px var(--line-soft); font-size: 12px; font-weight: 760; overflow-wrap: anywhere; }}
    .quadrant-items a span, .quadrant-items > span span {{ color: var(--github); font-weight: 820; }}
    .quadrant-items small {{ color: var(--muted); }}
    .quadrant-new_high .quadrant-title em {{ background: var(--green); }}
    .quadrant-existing_high .quadrant-title em {{ background: var(--github); }}
    .quadrant-new_low .quadrant-title em {{ background: var(--amber); }}
    .quadrant-existing_low .quadrant-title em {{ background: var(--quiet); }}
    .value-attribution-board {{ display: grid; gap: 12px; }}
    .value-category-grid {{ display: grid; gap: 8px; }}
    .value-category {{ display: grid; grid-template-columns: minmax(160px, 220px) 1fr 58px; gap: 12px; align-items: center; padding: 10px; border-radius: 7px; background: var(--paper); box-shadow: inset 0 0 0 1px var(--line-soft); }}
    .value-category strong {{ display: block; font-size: 13px; line-height: 1.25; }}
    .value-category small {{ display: block; margin-top: 3px; color: var(--muted); font-size: 11px; line-height: 1.3; overflow-wrap: anywhere; }}
    .value-category b {{ text-align: right; color: var(--ink); font-size: 18px; line-height: 1; }}
    .value-category-track {{ height: 12px; overflow: hidden; border-radius: 999px; background: #e4eaf1; }}
    .value-category-track span {{ display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--violet), var(--green)); }}
    .value-project-strip {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }}
    .value-project {{ min-height: 82px; display: grid; grid-template-rows: auto auto 1fr; gap: 5px; padding: 10px; border-radius: 7px; background: #f4f8ff; color: var(--ink); box-shadow: inset 0 0 0 1px rgba(31,111,235,.12); text-decoration: none; }}
    .value-project strong {{ min-width: 0; font-size: 12px; line-height: 1.3; overflow-wrap: anywhere; }}
    .value-project em {{ color: #174ea6; font-style: normal; font-size: 11px; font-weight: 780; line-height: 1.2; }}
    .value-project div {{ display: flex; flex-wrap: wrap; gap: 4px; align-content: end; }}
    .value-project div span {{ padding: 3px 5px; border-radius: 999px; background: var(--paper); color: #344054; box-shadow: inset 0 0 0 1px rgba(31,111,235,.10); font-size: 10px; line-height: 1.1; font-weight: 760; }}
    .bar-chart {{ display: grid; gap: 10px; }}
    .bar-row {{ display: grid; grid-template-columns: minmax(136px, 220px) 1fr 58px; gap: 12px; align-items: center; }}
    .bar-name {{ min-width: 0; overflow-wrap: anywhere; font-size: 13px; }}
    .bar-name strong {{ display: block; font-weight: 760; line-height: 1.3; }}
    .bar-name small {{ display: block; margin-top: 2px; color: var(--muted); font-size: 11px; line-height: 1.3; }}
    .bar-track {{ height: 12px; background: #e4eaf1; border-radius: 999px; overflow: hidden; }}
    .bar-track span {{ display: block; height: 100%; background: linear-gradient(90deg, var(--github), var(--feishu)); border-radius: 999px; }}
    .bar-track span.alt {{ background: linear-gradient(90deg, var(--violet), var(--github)); }}
    .bar-track span.outcome {{ background: linear-gradient(90deg, var(--green), var(--github)); }}
    .bar-track span.code {{ background: linear-gradient(90deg, var(--amber), var(--violet)); }}
    .bar-value {{ text-align: right; font-weight: 760; }}
    .bar-value small {{ display: block; color: var(--muted); font-size: 11px; font-weight: 650; line-height: 1.1; }}
    .repo-row {{ grid-template-columns: minmax(170px, 260px) 1fr 58px; }}
    .code-pr-row {{ grid-template-columns: minmax(220px, 330px) 1fr 70px; }}
    .tabs-root, .tab-panel, .tab-layout, .stack, .panel-lite {{ min-width: 0; }}
    .tabs-root {{ display: grid; gap: 14px; }}
    .tab-list {{ display: inline-flex; width: fit-content; max-width: 100%; gap: 4px; padding: 4px; border-radius: 999px; background: #e8edf3; box-shadow: inset 0 0 0 1px var(--line); overflow-x: auto; }}
    .tab-list.small {{ margin-bottom: 12px; }}
    .tab-button {{ min-width: 0; min-height: 38px; padding: 8px 14px; border: 0; border-radius: 999px; color: #526071; background: transparent; font: inherit; font-size: 13px; font-weight: 780; cursor: pointer; white-space: nowrap; transition-property: transform, background-color, color, opacity; transition-duration: 140ms; transition-timing-function: cubic-bezier(.16,1,.3,1); }}
    .tab-button span {{ margin-left: 6px; opacity: .7; }}
    .tab-button.is-active {{ color: var(--ink); background: var(--paper); box-shadow: 0 1px 3px rgba(31,41,55,.12); }}
    .tab-button:active {{ transform: scale(.96); }}
    .tab-panel {{ display: none; }}
    .tab-panel.is-active {{ display: block; }}
    .tab-layout {{ display: grid; grid-template-columns: minmax(420px, 1.1fr) minmax(320px, .9fr); gap: 16px; align-items: start; }}
    .stack {{ display: grid; gap: 16px; }}
    .evidence-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    .evidence-card {{ padding: 13px; background: var(--paper); border-radius: var(--radius); box-shadow: 0 1px 3px rgba(31,41,55,.10); }}
    .evidence-title {{ font-weight: 760; line-height: 1.38; overflow-wrap: anywhere; }}
    .evidence-meta {{ margin-top: 6px; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }}
    .module-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}
    .module-card {{ min-height: 150px; padding: 14px; background: var(--paper); border-radius: var(--radius); box-shadow: 0 1px 3px rgba(31,41,55,.10); }}
    .module-good {{ box-shadow: inset 0 3px 0 var(--green), 0 1px 3px rgba(31,41,55,.10); }}
    .module-warn {{ box-shadow: inset 0 3px 0 var(--amber), 0 1px 3px rgba(31,41,55,.10); }}
    .module-bad {{ box-shadow: inset 0 3px 0 var(--red), 0 1px 3px rgba(31,41,55,.10); }}
    .module-idle {{ box-shadow: inset 0 3px 0 #a5afbd, 0 1px 3px rgba(31,41,55,.10); }}
    .module-top {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; }}
    .module-card p {{ margin: 10px 0; color: var(--muted); font-size: 13px; line-height: 1.55; overflow-wrap: anywhere; }}
    .profile-list {{ display: grid; border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; background: var(--line); gap: 1px; }}
    .profile-row {{ display: grid; grid-template-columns: 44px minmax(0, 1fr) minmax(260px, 360px); gap: 14px; padding: 14px; background: var(--paper); }}
    .profile-row:first-child {{ background: linear-gradient(90deg, #ffffff 0, #f7fbff 100%); }}
    .profile-index {{ color: var(--quiet); font-size: 12px; font-weight: 860; letter-spacing: .04em; }}
    .profile-main {{ min-width: 0; display: grid; gap: 10px; align-content: start; }}
    .profile-head {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; align-items: start; }}
    .profile-head h3 {{ margin: 0; font-size: 18px; line-height: 1.25; }}
    .profile-head small {{ display: block; margin-top: 5px; color: var(--muted); font-size: 12px; line-height: 1.35; overflow-wrap: anywhere; }}
    .profile-main p {{ margin: 0; color: #344054; font-size: 13px; line-height: 1.55; overflow-wrap: anywhere; }}
    .profile-side {{ min-width: 0; display: grid; gap: 10px; align-content: start; }}
    .profile-values {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .profile-values span {{ padding: 4px 7px; color: #4d3b8f; background: #ece8ff; border-radius: 999px; font-size: 12px; font-weight: 780; }}
    .profile-impact-line {{ color: #174ea6; font-size: 12px; line-height: 1.45; }}
    .profile-actions {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .profile-actions span {{ padding: 5px 7px; border-radius: 999px; background: var(--paper-soft); color: #344054; box-shadow: inset 0 0 0 1px var(--line); font-size: 11px; line-height: 1.2; font-weight: 760; }}
    .profile-metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }}
    .profile-metrics div {{ min-height: 54px; padding: 8px; border-radius: 7px; background: var(--paper-soft); box-shadow: inset 0 0 0 1px var(--line); }}
    .profile-metrics span {{ display: block; color: var(--muted); font-size: 11px; line-height: 1.1; }}
    .profile-metrics strong {{ display: block; margin-top: 7px; color: var(--ink); font-size: 18px; line-height: 1; }}
    .profile-prs {{ display: grid; gap: 5px; }}
    .profile-prs a {{ color: #174ea6; font-size: 12px; line-height: 1.35; font-weight: 760; overflow-wrap: anywhere; }}
    .project-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap: 10px; }}
    .project-card {{ min-height: 238px; padding: 14px; background: var(--paper); border-radius: var(--radius); box-shadow: 0 1px 3px rgba(31,41,55,.10); }}
    .project-head {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; align-items: start; }}
    .project-head h3 {{ margin: 0; font-size: 15px; line-height: 1.35; }}
    .project-head small {{ display: block; margin-top: 4px; color: var(--muted); font-size: 12px; line-height: 1.35; }}
    .project-head strong {{ color: var(--github); font-size: 22px; line-height: 1; }}
    .project-card p {{ margin: 10px 0 0; color: #445065; font-size: 13px; line-height: 1.55; }}
    .project-attribution {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }}
    .project-attribution span {{ padding: 4px 7px; color: #4d3b8f; background: #ece8ff; border-radius: 999px; font-size: 12px; font-weight: 780; }}
    .project-badges, .project-stats {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }}
    .project-badges span {{ padding: 4px 7px; color: #174ea6; background: #e9efff; border-radius: 999px; font-size: 12px; font-weight: 760; }}
    .project-stats b {{ padding: 4px 7px; background: var(--paper-soft); box-shadow: inset 0 0 0 1px var(--line); border-radius: 999px; font-size: 12px; }}
    .project-value {{ display: grid; gap: 5px; margin-top: 10px; }}
    .project-value strong {{ padding: 7px 8px; border-radius: 7px; background: #f4f8ff; color: #174ea6; font-size: 12px; line-height: 1.35; }}
    .project-narrative {{ margin-top: 9px; color: #344054; font-size: 12px; line-height: 1.5; }}
    .project-detail {{ margin-top: 10px; border-radius: 7px; background: var(--paper-soft); box-shadow: inset 0 0 0 1px var(--line); overflow: hidden; }}
    .project-detail summary {{ min-height: 38px; display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 10px; color: #344054; font-size: 12px; font-weight: 820; cursor: pointer; list-style: none; }}
    .project-detail summary::-webkit-details-marker {{ display: none; }}
    .project-detail summary i {{ width: 9px; height: 9px; border-right: 2px solid #526071; border-bottom: 2px solid #526071; transform: rotate(45deg); transition-property: transform; transition-duration: 140ms; transition-timing-function: cubic-bezier(.16,1,.3,1); }}
    .project-detail[open] summary i {{ transform: rotate(225deg); }}
    .project-detail-body {{ display: grid; gap: 10px; padding: 0 10px 10px; }}
    .project-detail-block {{ padding: 10px; border-radius: 7px; background: var(--paper); box-shadow: inset 0 0 0 1px var(--line-soft); }}
    .project-detail-block h4 {{ margin: 0 0 7px; color: var(--muted); font-size: 11px; line-height: 1.2; font-weight: 820; }}
    .project-detail-block p {{ margin: 0; color: #344054; font-size: 12px; line-height: 1.55; }}
    .project-evidence-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 7px; }}
    .project-evidence-grid div {{ min-height: 58px; padding: 8px; border-radius: 7px; background: var(--paper); box-shadow: inset 0 0 0 1px var(--line-soft); }}
    .project-evidence-grid span {{ display: block; color: var(--muted); font-size: 11px; line-height: 1.2; }}
    .project-evidence-grid strong {{ display: block; margin-top: 7px; color: var(--ink); font-size: 16px; line-height: 1; overflow-wrap: anywhere; }}
    .project-value-rows {{ display: grid; gap: 7px; }}
    .project-value-row {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; padding: 8px; border-radius: 7px; background: #f4f8ff; box-shadow: inset 0 0 0 1px rgba(31,111,235,.10); }}
    .project-value-row strong {{ display: block; color: #174ea6; font-size: 12px; line-height: 1.2; }}
    .project-value-row small {{ display: block; margin-top: 3px; color: var(--muted); font-size: 11px; line-height: 1.3; }}
    .project-value-row b {{ color: var(--github); font-size: 16px; line-height: 1; }}
    .project-value-row ul {{ grid-column: 1 / -1; margin: 2px 0 0; padding-left: 16px; color: #425066; font-size: 11px; line-height: 1.45; }}
    .project-prs {{ margin: 9px 0 0; padding-left: 18px; color: var(--muted); font-size: 12px; }}
    .project-prs li {{ margin: 5px 0; }}
    .project-prs span {{ color: var(--ink); }}
    .project-detail .project-prs {{ margin-top: 0; }}
    .project-boundary {{ padding: 9px 10px; border-radius: 7px; color: var(--muted); background: #eef2f7; font-size: 11px; line-height: 1.45; }}
    .status {{ display: inline-flex; align-items: center; min-height: 24px; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 760; }}
    .status-good {{ color: #0f6b43; background: #e3f4ea; }}
    .status-warn {{ color: #7a4b0a; background: #fff0cc; }}
    .status-bad {{ color: #982f37; background: #fde9eb; }}
    .status-idle {{ color: #526071; background: #edf1f6; }}
    .scope-list {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
    code {{ max-width: 100%; padding: 2px 5px; border-radius: 5px; background: #eef2f7; color: #344054; overflow-wrap: anywhere; word-break: break-word; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .92em; }}
    .callout {{ display: flex; align-items: start; gap: 10px; padding: 11px 12px; margin-bottom: 10px; border-radius: var(--radius); background: var(--paper-soft); box-shadow: inset 0 0 0 1px var(--line); color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }}
    .outcome-note {{ margin-top: 12px; }}
    .subpanel {{ margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line); }}
    .table-wrap {{ overflow-x: auto; border-radius: var(--radius); box-shadow: inset 0 0 0 1px var(--line); background: var(--paper); }}
    table {{ width: 100%; min-width: 620px; border-collapse: collapse; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line-soft); text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: var(--paper-soft); color: #475467; font-size: 12px; font-weight: 760; }}
    tr:last-child td {{ border-bottom: 0; }}
    .num {{ text-align: right; }}
    .delta-up {{ color: var(--green); font-weight: 760; }}
    .delta-down {{ color: var(--red); font-weight: 760; }}
    .delta-flat {{ color: var(--muted); font-weight: 760; }}
    .empty {{ margin: 0; color: var(--muted); }}
    .empty.compact {{ font-size: 12px; line-height: 1.5; }}
    .method-list {{ margin: 0; padding-left: 20px; color: #425066; }}
    .method-list li {{ margin: 6px 0; }}
    body[data-view-mode="presentation"] .detail-section,
    body[data-view-mode="presentation"] .method-section,
    body[data-view-mode="presentation"] .project-detail,
    body[data-view-mode="presentation"] .subpanel {{ display: none; }}
    body[data-view-mode="presentation"] .masthead {{ box-shadow: 0 10px 30px rgba(31,41,55,.09); }}
    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{ transition-duration: .01ms !important; animation-duration: .01ms !important; }}
    }}
    @media (max-width: 1050px) {{
      .metrics {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
      .chart-grid, .tab-layout, .chain-grid, .change-map, .summary-evidence-grid {{ grid-template-columns: 1fr; }}
      .value-rail {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .viz-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .viz-grid.three {{ grid-template-columns: 1fr; }}
      .project-map {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .signal-rail, .quality-rail {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .signal-item:nth-child(2n) {{ border-right: 0; }}
      .module-grid {{ grid-template-columns: 1fr; }}
      .value-project-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .profile-row {{ grid-template-columns: 38px minmax(0, 1fr); }}
      .profile-side {{ grid-column: 2; }}
    }}
    @media (max-width: 680px) {{
      .page {{ padding: 12px 10px 34px; }}
      .masthead, section {{ padding: 15px; }}
      .masthead-grid {{ grid-template-columns: 1fr; }}
      .source-tools {{ justify-items: start; }}
      .source-row {{ justify-content: flex-start; }}
      h1 {{ font-size: 29px; }}
      h2 {{ font-size: 19px; }}
      .metrics, .mini-grid, .evidence-grid, .signal-rail, .quality-rail, .viz-grid, .change-metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .value-rail, .project-quadrant {{ grid-template-columns: 1fr; }}
      .metric {{ min-height: 130px; }}
      .metric-value {{ font-size: 28px; }}
      .bar-row {{ grid-template-columns: 1fr 1fr 48px; }}
      .lane-row {{ grid-template-columns: 1fr; }}
      .lane-row b {{ text-align: left; }}
      .value-category {{ grid-template-columns: 1fr; }}
      .value-category b {{ text-align: left; }}
      .project-evidence-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .audit-path {{ grid-template-columns: 1fr; }}
      .audit-path i {{ display: none; }}
      .donut-wrap {{ grid-template-columns: 1fr; }}
      .matrix-head, .matrix-row {{ grid-template-columns: 1fr; }}
      .matrix-head div, .matrix-cells {{ grid-template-columns: repeat(5, minmax(42px, 1fr)); }}
      .project-map {{ grid-template-columns: 1fr; }}
      .week-chart {{ gap: 4px; }}
      .change-projects, .change-boundary {{ grid-column: auto; }}
      .change-lane {{ grid-template-columns: 1fr; }}
      .change-lane strong {{ text-align: left; }}
      .profile-row {{ grid-template-columns: 1fr; }}
      .profile-side {{ grid-column: auto; }}
      .profile-metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .tab-list {{ width: 100%; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); }}
      .tab-button {{ width: 100%; padding-inline: 9px; overflow: hidden; text-overflow: clip; }}
      .callout {{ display: grid; }}
    }}
    @media (max-width: 380px) {{
      .metrics, .mini-grid, .evidence-grid, .signal-rail, .quality-rail, .viz-grid, .change-metrics, .profile-metrics {{ grid-template-columns: 1fr; }}
      .focus-chip {{ width: 100%; justify-content: space-between; }}
      .value-project-strip, .project-evidence-grid {{ grid-template-columns: 1fr; }}
    }}
    @media print {{
      body {{ background: #fff; color: #111827; }}
      a {{ color: inherit; text-decoration: none; }}
      .page {{ max-width: none; padding: 0; }}
      .masthead, section, .panel-lite, .viz-card, .chain-card, .chain-compact, .profile-row {{ box-shadow: none !important; }}
      .mode-row, .tab-list, .skip-link, .detail-section, .method-section, .project-detail, .subpanel {{ display: none !important; }}
      .masthead, section {{ break-inside: avoid; page-break-inside: avoid; border-color: #d1d5db; }}
      .metrics {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
      .chart-grid, .chain-grid, .change-map, .summary-evidence-grid {{ grid-template-columns: 1fr 1fr; }}
    }}
  </style>
</head>
<body data-view-mode="normal">
  <a href="#main-content" class="skip-link">跳到主要内容</a>
  <main class="page" id="main-content">
    <header class="masthead">
      <div class="masthead-grid">
        <div>
          <h1>{esc(title)}</h1>
          <div class="meta">范围：{esc(summary['start'])} 至 {esc(summary['end'])} · 生成：{esc(summary['generated_at'])}</div>
        </div>
        <div class="source-tools">
          <div class="source-row">{source_html}</div>
          {mode_html}
        </div>
      </div>
      <div class="metrics">
        {metric_card(metrics['commits'], 'Commit', 'GitHub authored commits', metrics['github_growth']['commits'])}
        {metric_card(metrics['prs_merged'], '合并 PR', '本季度 merge 的 authored PR', metrics['github_growth']['prs_merged'])}
        {metric_card(metrics['feature_points'], '功能点', '按 merged PR 归类')}
        {metric_card(metrics['bug_fixes'], 'Bug 修复', '按 fix/bug 线索归类')}
        {metric_card(metrics['active_repos'], '活跃仓库', '本季度有开发证据的仓库')}
        {metric_card(metrics['new_repositories'], '新建仓库', 'repo created_at 在本季度')}
        {metric_card(metrics['prs_reviewed'], 'Review 参与 PR', 'PR 集合数，不是 review 次数')}
        {metric_card(metrics['feishu_accessible_modules'], '飞书可用模块', '文档 / 消息 / 日历')}
      </div>
      {executive_metric_strip(summary)}
      {data_quality_strip(summary)}
      {value_path(summary)}
      {overview_chart_grid(summary)}
    </header>

    <section>
      <div class="section-head">
        <h2>结论与证据</h2>
      </div>
      {summary_evidence_section(summary)}
    </section>

    <section>
      <div class="section-head">
        <h2>跨来源结构</h2>
      </div>
      <div class="panel-lite">
        <h3>季度变化地图</h3>
        {quarter_change_map(summary)}
      </div>
      <div class="chart-grid" style="margin-top:14px">
        <div class="panel-lite">
          <h3>价值投入强度</h3>
          {investment_lanes(summary)}
        </div>
        <div class="panel-lite">
          <h3>聚焦结构</h3>
          {focus_mix_board(summary)}
        </div>
      </div>
      <div style="margin-top:14px">{weekly_activity_card(github)}</div>
      <div class="chart-grid" style="margin-top:14px">
        <div class="panel-lite">
          <h3>项目价值归因</h3>
          {project_value_attribution_board(summary)}
        </div>
        <div class="panel-lite">
          <h3>项目象限</h3>
          {project_quadrant(summary)}
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>重点项目剖面</h2>
      </div>
      {project_profile_cards(summary)}
    </section>

    <section class="detail-section">
      <div class="section-head">
        <h2>详细模块</h2>
      </div>
      <div class="tabs-root" data-tabs="sources">
        <div class="tab-list" role="tablist" aria-label="数据源模块">
          <button class="tab-button is-active" type="button" role="tab" aria-selected="true" data-tab-target="github-panel">GitHub 开发 <span>{esc(fmt_num(metrics['prs_merged']))}</span></button>
          <button class="tab-button" type="button" role="tab" aria-selected="false" data-tab-target="feishu-panel">飞书协作 <span>{esc(fmt_num(metrics['feishu_accessible_modules']))}/3</span></button>
        </div>

        <div class="tab-panel is-active" role="tabpanel" data-tab-panel="github-panel">
          <div class="stack">
            <div class="panel-lite">
              <div class="section-head" style="margin-bottom:12px">
                <h3>工程成果维度</h3>
              </div>
              <div class="mini-grid">{outcome_summary_cards(github)}</div>
              <div class="chart-grid" style="margin-top:14px">
                <div>
                  <h3>功能点 / Bug 修复按仓库</h3>
                  <div class="bar-chart">{outcome_bar_rows(github)}</div>
                </div>
                <div>
                  <h3>代码区域分布</h3>
                  <div class="bar-chart">{code_area_rows(github)}</div>
                </div>
              </div>
              <div class="chart-grid" style="margin-top:14px">
                {repo_matrix_card(github)}
                <div class="panel-lite">
                  <h3>代码区域 Treemap</h3>
                  {code_area_treemap(github)}
                </div>
              </div>
              <div class="subpanel">
                <h3>PR 代码变更 Top</h3>
                <div class="bar-chart">{top_code_pr_rows(github)}</div>
              </div>
            </div>
            <div class="tab-layout">
            <div class="stack">
              <div class="panel-lite">
                <h3>环比增长</h3>
                {comparison_rows(github)}
              </div>
              <div class="panel-lite">
                <h3>代表性合并 PR</h3>
                <div class="evidence-grid">{evidence_cards(merged_prs, '暂无合并 PR 明细。', 6)}</div>
              </div>
            </div>
            <div class="stack">
              <div class="panel-lite">
                <h3>投入主题</h3>
                <div class="bar-chart">{theme_rows(github)}</div>
              </div>
              <div class="panel-lite">
                <h3>Top 仓库贡献强度</h3>
                <div class="bar-chart">{top_repos_chart(github)}</div>
              </div>
              <div class="panel-lite">
                <h3>Issue 与 commit 抽样</h3>
                <div class="evidence-grid">{evidence_cards(closed_issues or created_issues, '暂无 issue 明细。', 4)}{evidence_cards(commits, '暂无 commit 明细。', 2)}</div>
              </div>
            </div>
          </div>
          </div>
        </div>

        <div class="tab-panel" role="tabpanel" data-tab-panel="feishu-panel">
          <div class="stack">
            <div class="module-grid">{module_cards(feishu)}</div>
            <div class="tab-layout">
              <div class="panel-lite">
                <h3>飞书文档</h3>
                {feishu_doc_tabs(feishu)}
              </div>
              <div class="panel-lite">
                <h3>消息与日历</h3>
                <div class="mini-grid">
                  {compact_metric_card(feishu_metrics.get('message_hits'), '消息命中', 'feishu')}
                  {compact_metric_card(feishu_metrics.get('message_chats'), '会话数', 'feishu')}
                  {compact_metric_card(feishu_metrics.get('calendar_events'), '日程数', 'feishu')}
                </div>
                {f'<div class="callout" style="margin-top:12px">{status_badge(module_status(feishu_modules.get("messages")))}<span>{esc(message_status_text)}</span></div>' if message_status_text else ''}
                {f'<div class="callout">{status_badge(module_status(feishu_modules.get("calendar")))}<span>{esc(calendar_status_text)}</span></div>' if calendar_status_text else ''}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="method-section">
      <div class="section-head">
        <h2>口径与限制</h2>
      </div>
      {confidence_table(summary)}
      <ul class="method-list">{methodology(summary)}</ul>
    </section>
  </main>
  <script>
    document.querySelectorAll('[data-tabs]').forEach((root) => {{
      const buttons = Array.from(root.querySelectorAll(':scope > .tab-list [data-tab-target], :scope > .tab-list.small [data-tab-target]'));
      const panels = Array.from(root.querySelectorAll(':scope > [data-tab-panel]'));
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
    document.querySelectorAll('.mode-button[data-view-mode]').forEach((button) => {{
      button.addEventListener('click', () => {{
        const mode = button.getAttribute('data-view-mode') || 'normal';
        document.body.dataset.viewMode = mode;
        document.querySelectorAll('.mode-button[data-view-mode]').forEach((item) => {{
          item.classList.toggle('is-active', item === button);
        }});
      }});
    }});
  </script>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        summary = build_summary(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    (output_dir / "summary.json").write_text(json.dumps({k: v for k, v in summary.items() if k != "output_dir"}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "index.html").write_text(render_html(summary), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "output_dir": str(output_dir),
                "index": str(output_dir / "index.html"),
                "summary": str(output_dir / "summary.json"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
