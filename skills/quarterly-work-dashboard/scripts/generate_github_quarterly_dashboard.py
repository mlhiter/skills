#!/usr/bin/env python3
"""Generate a read-only quarterly GitHub activity dashboard as HTML and JSON."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


JSON_FIELDS_PRS = "assignees,author,closedAt,commentsCount,createdAt,id,isDraft,labels,number,repository,state,title,updatedAt,url"
JSON_FIELDS_ISSUES = "assignees,author,closedAt,commentsCount,createdAt,id,labels,number,repository,state,title,updatedAt,url"
JSON_FIELDS_COMMITS = "author,commit,committer,id,repository,sha,url"
COMPARABLE_METRICS = [
    ("active_repos", "活跃仓库"),
    ("commits", "Commit"),
    ("prs_created", "创建 PR"),
    ("prs_merged", "合并 PR"),
    ("prs_reviewed", "Review 参与 PR"),
    ("issues_created", "创建 Issue"),
    ("issues_closed_related", "相关关闭 Issue"),
    ("releases", "Release"),
]
THEME_DESCRIPTIONS = {
    "Devbox 研发体验": "围绕 Devbox 创建、配置、IDE、存储、迁移和本地开发体验的持续交付。",
    "Sealos 桌面与账号体验": "围绕桌面、账号、工作区、登录协议和用户入口的体验建设。",
    "应用发布与网络域名": "围绕 app launchpad、公开域名、镜像端口、DNS 标签等发布链路的稳定性与体验。",
    "Admin 管理与租户治理": "围绕管理后台、租户、可用区、模板管理和治理能力的交付。",
    "Registry 镜像仓库": "围绕镜像仓库、上传下载、兼容性和进度反馈的能力建设。",
    "Kite / Helm / 运维能力": "围绕 Helm、离线 OCI、指标、认证和运维功能的补齐。",
    "平台应用与离线能力": "围绕 objectstorage、cronjob、offline-center、sealos-pro 等平台应用和离线能力。",
    "个人产品与执行平台探索": "围绕 mspace、maestro、mbox 等个人产品和执行平台方向的探索。",
    "知识沉淀与工作流": "围绕个人站点、skills、文档和工作流资产的沉淀。",
    "问题跟进与支持": "围绕 issue 处理、问题跟进和支持性工作的 GitHub 证据。",
    "其他 GitHub 活动": "无法稳定归入主线主题的其他 GitHub 活动。",
}
WORK_TYPE_DEFINITIONS = {
    "feature": {"label": "功能交付", "color": "#2754c5"},
    "fix": {"label": "修复与稳定性", "color": "#168a5b"},
    "experience": {"label": "体验与前端质量", "color": "#0d7c8b"},
    "architecture": {"label": "架构与质量", "color": "#6d4bc2"},
    "operations": {"label": "工程与运维", "color": "#0f766e"},
    "docs": {"label": "文档与知识", "color": "#b7791f"},
    "review": {"label": "Review 协作", "color": "#647084"},
    "issue": {"label": "问题跟进", "color": "#c24141"},
    "other": {"label": "其他", "color": "#8b95a5"},
}
WORK_TYPE_PRIORITY = ["feature", "fix", "operations", "experience", "architecture", "docs", "other"]
CODE_AREA_DEFINITIONS = {
    "frontend": {"label": "前端 / UI", "color": "#2656d9"},
    "backend": {"label": "后端 / API", "color": "#168a5b"},
    "infra": {"label": "基础设施 / 运维", "color": "#0f766e"},
    "tests": {"label": "测试", "color": "#6d4bc2"},
    "docs": {"label": "文档", "color": "#b7791f"},
    "config": {"label": "配置 / 构建", "color": "#647084"},
    "other": {"label": "其他代码", "color": "#8b95a5"},
}


def run_json(args: list[str]) -> Any:
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(args)}\n{proc.stderr.strip()}")
    text = proc.stdout.strip()
    if not text:
        return []
    return json.loads(text)


def try_run_json(args: list[str]) -> tuple[Any | None, str]:
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return None, proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
    text = proc.stdout.strip()
    if not text:
        return [], ""
    try:
        return json.loads(text), ""
    except json.JSONDecodeError as exc:
        return None, str(exc)


def run_text(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(args)}\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def add_months(day: dt.date, months: int) -> dt.date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    month_lengths = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return dt.date(year, month, min(day.day, month_lengths[month - 1]))


def quarter_start(day: dt.date) -> dt.date:
    month = ((day.month - 1) // 3) * 3 + 1
    return dt.date(day.year, month, 1)


def quarter_end(day: dt.date) -> dt.date:
    start = quarter_start(day)
    next_start = add_months(start, 3)
    return next_start - dt.timedelta(days=1)


def previous_period_for(start: dt.date, end: dt.date) -> tuple[dt.date, dt.date]:
    prev_start = add_months(start, -3)
    if start == quarter_start(start) and end == quarter_end(start):
        return prev_start, quarter_end(prev_start)
    return prev_start, prev_start + (end - start)


def repo_name(item: dict[str, Any]) -> str:
    repo = item.get("repository") or {}
    if isinstance(repo, dict):
        full = repo.get("fullName") or repo.get("nameWithOwner")
        if full:
            return full
        owner = repo.get("owner")
        name = repo.get("name")
        if isinstance(owner, dict):
            owner = owner.get("login")
        if owner and name:
            return f"{owner}/{name}"
        if name:
            return str(name)
    return "unknown"


def item_author(item: dict[str, Any]) -> str:
    author = item.get("author") or {}
    if isinstance(author, dict):
        return author.get("login") or author.get("name") or ""
    return ""


def normalize_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def build_repo_flags(repos: list[str], owners: list[str]) -> list[str]:
    flags: list[str] = []
    for repo in repos:
        flags.extend(["--repo", repo])
    for owner in owners:
        flags.extend(["--owner", owner])
    return flags


def date_range_query(start: dt.date, end: dt.date) -> str:
    return f"{start.isoformat()}..{end.isoformat()}"


def search_prs(user: str, start: dt.date, end: dt.date, repos: list[str], owners: list[str], kind: str, limit: int) -> list[dict[str, Any]]:
    flags = build_repo_flags(repos, owners)
    date_range = date_range_query(start, end)
    base = ["gh", "search", "prs", "--json", JSON_FIELDS_PRS, "--limit", str(limit), *flags]
    if kind == "created":
        cmd = [*base, "--author", user, "--created", date_range, "--sort", "created", "--order", "desc"]
    elif kind == "merged":
        cmd = [*base, "--author", user, "--merged", "--merged-at", date_range, "--sort", "updated", "--order", "desc"]
    elif kind == "closed":
        cmd = [*base, "--author", user, "--closed", date_range, "--state", "closed", "--sort", "updated", "--order", "desc"]
    elif kind == "reviewed":
        cmd = [*base, "--reviewed-by", user, "--updated", date_range, "--sort", "updated", "--order", "desc"]
    else:
        raise ValueError(kind)
    return normalize_items(run_json(cmd))


def search_issues(user: str, start: dt.date, end: dt.date, repos: list[str], owners: list[str], kind: str, limit: int) -> list[dict[str, Any]]:
    flags = build_repo_flags(repos, owners)
    date_range = date_range_query(start, end)
    base = ["gh", "search", "issues", "--json", JSON_FIELDS_ISSUES, "--limit", str(limit), *flags]
    if kind == "created":
        cmd = [*base, "--author", user, "--created", date_range, "--sort", "created", "--order", "desc"]
    elif kind == "closed_related":
        cmd = [*base, "--involves", user, "--closed", date_range, "--state", "closed", "--sort", "updated", "--order", "desc"]
    else:
        raise ValueError(kind)
    return normalize_items(run_json(cmd))


def search_commits(user: str, start: dt.date, end: dt.date, repos: list[str], owners: list[str], limit: int) -> list[dict[str, Any]]:
    flags = build_repo_flags(repos, owners)
    cmd = [
        "gh",
        "search",
        "commits",
        "--author",
        user,
        "--author-date",
        date_range_query(start, end),
        "--json",
        JSON_FIELDS_COMMITS,
        "--limit",
        str(limit),
        "--sort",
        "author-date",
        "--order",
        "desc",
        *flags,
    ]
    return normalize_items(run_json(cmd))


def fetch_releases(repos: list[str], start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    releases: list[dict[str, Any]] = []
    for repo in repos:
        try:
            data = run_json(["gh", "api", f"repos/{repo}/releases", "--paginate"])
        except RuntimeError:
            continue
        for item in normalize_items(data):
            published = item.get("published_at") or item.get("created_at")
            if not published:
                continue
            day = dt.date.fromisoformat(published[:10])
            if start <= day <= end:
                releases.append(
                    {
                        "repo": repo,
                        "name": item.get("name") or item.get("tag_name"),
                        "tag": item.get("tag_name"),
                        "published_at": published,
                        "url": item.get("html_url"),
                    }
                )
    return releases


def dedupe_by_url(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = item.get("url") or item.get("id") or json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def aggregate_by_repo(datasets: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, int]]:
    repos: dict[str, Counter[str]] = defaultdict(Counter)
    mapping = {
        "commits": "commits",
        "prs_created": "prs_created",
        "prs_merged": "prs_merged",
        "prs_reviewed": "prs_reviewed",
        "issues_created": "issues_created",
        "issues_closed_related": "issues_closed_related",
    }
    for dataset_name, metric_name in mapping.items():
        for item in datasets.get(dataset_name, []):
            repos[repo_name(item)][metric_name] += 1
    return {repo: dict(counter) for repo, counter in sorted(repos.items())}


def top_repos(repo_metrics: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    rows = []
    for repo, metrics in repo_metrics.items():
        score = (
            metrics.get("commits", 0)
            + metrics.get("prs_created", 0) * 3
            + metrics.get("prs_merged", 0) * 4
            + metrics.get("prs_reviewed", 0) * 2
            + metrics.get("issues_created", 0)
            + metrics.get("issues_closed_related", 0)
        )
        rows.append({"repo": repo, "score": score, **metrics})
    return sorted(rows, key=lambda row: row["score"], reverse=True)


def collect_period(user: str, start: dt.date, end: dt.date, repos: list[str], owners: list[str], limit: int) -> dict[str, Any]:
    datasets: dict[str, list[dict[str, Any]]] = {}
    datasets["commits"] = dedupe_by_url(search_commits(user, start, end, repos, owners, limit))
    datasets["prs_created"] = dedupe_by_url(search_prs(user, start, end, repos, owners, "created", limit))
    datasets["prs_merged"] = dedupe_by_url(search_prs(user, start, end, repos, owners, "merged", limit))
    datasets["prs_closed"] = dedupe_by_url(search_prs(user, start, end, repos, owners, "closed", limit))
    datasets["prs_reviewed"] = dedupe_by_url(search_prs(user, start, end, repos, owners, "reviewed", limit))
    datasets["issues_created"] = dedupe_by_url(search_issues(user, start, end, repos, owners, "created", limit))
    datasets["issues_closed_related"] = dedupe_by_url(search_issues(user, start, end, repos, owners, "closed_related", limit))
    releases = fetch_releases(repos, start, end) if repos else []
    repo_metrics = aggregate_by_repo(datasets)
    top = top_repos(repo_metrics)
    active_repos = len([row for row in top if row["repo"] != "unknown"])
    metrics = {
        "active_repos": active_repos,
        "commits": len(datasets["commits"]),
        "prs_created": len(datasets["prs_created"]),
        "prs_merged": len(datasets["prs_merged"]),
        "prs_closed": len(datasets["prs_closed"]),
        "prs_reviewed": len(datasets["prs_reviewed"]),
        "issues_created": len(datasets["issues_created"]),
        "issues_closed_related": len(datasets["issues_closed_related"]),
        "releases": len(releases),
    }
    return {
        "datasets": datasets,
        "releases": releases,
        "repo_metrics": repo_metrics,
        "top_repos": top,
        "metrics": metrics,
    }


def classify_theme(repo: str, title: str = "") -> str:
    text = f"{repo} {title}".lower()
    if "devbox" in text or "devbox-runtime" in text or "sshgate" in text or "jetbrains" in text:
        return "Devbox 研发体验"
    if repo == "labring/sealos" or "desktop" in text or "workspace" in text or "account" in text or "sign-in" in text:
        if "applaunchpad" not in text and "domain" not in text:
            return "Sealos 桌面与账号体验"
    if "applaunchpad" in text or "domain" in text or "image port" in text or "public domain" in text:
        return "应用发布与网络域名"
    if "admin" in repo or "tenant" in text or "availability-zone" in text or "template-management" in text:
        return "Admin 管理与租户治理"
    if "registry" in repo or "repository" in text or "upload" in text or "download progress" in text:
        return "Registry 镜像仓库"
    if "kite" in repo or "helm" in text or "prometheus" in text or "metric" in text:
        return "Kite / Helm / 运维能力"
    if any(token in text for token in ["objectstorage", "cronjob", "offline-center", "sealos-pro", "offline", "oci"]):
        return "平台应用与离线能力"
    if any(token in text for token in ["mspace", "maestro", "mbox", "sandbox", "workspace runtime"]):
        return "个人产品与执行平台探索"
    if any(token in text for token in ["github.io", "skills", "typora-images", "sealos-app-dev-bridge", "docs", "readme"]):
        return "知识沉淀与工作流"
    if "sealos-issues" in repo or "issue" in text:
        return "问题跟进与支持"
    return "其他 GitHub 活动"


def title_prefix(title: str) -> str:
    lowered = title.lower().strip()
    if ":" not in lowered:
        return ""
    prefix = lowered.split(":", 1)[0]
    return prefix.split("(", 1)[0].strip()


def keyword_hit(text: str, keywords: list[str]) -> bool:
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text.lower())
    words = set(normalized.split())
    for keyword in keywords:
        keyword = keyword.lower()
        if re.search(r"[\u4e00-\u9fff]", keyword):
            if keyword in normalized:
                return True
        elif " " in keyword:
            if keyword in f" {normalized} ":
                return True
        elif keyword in words:
            return True
    return False


def classify_work_type(title: str, repo: str = "") -> str:
    lowered = f"{title} {repo}".lower()
    prefix = title_prefix(title)
    if prefix == "fix" or keyword_hit(lowered, ["restore", "stabilize", "prevent", "tolerate", "block", "compatibility", "rollback", "roll back"]):
        return "fix"
    if prefix == "feat" or keyword_hit(lowered, ["support", "add", "enable", "allow", "manage"]):
        return "feature"
    if keyword_hit(lowered, ["frontend", "ui", "dialog", "dropdown", "slider", "progress", "validation", "copy", "brand", "empty state"]):
        return "experience"
    if prefix in {"refactor", "perf", "test"} or keyword_hit(lowered, ["refactor", "migration", "migrate", "prisma", "crd", "v1alpha2"]):
        return "architecture"
    if prefix in {"chore", "build", "ci"} or keyword_hit(lowered, ["helm", "deploy", "chart", "oci", "prometheus", "runtime", "configurable", "provider", "bootstrap"]):
        return "operations"
    if prefix == "docs" or keyword_hit(lowered, ["docs", "readme", "manual"]):
        return "docs"
    return "other"


def label_names(item: dict[str, Any]) -> list[str]:
    labels = item.get("labels") or []
    names: list[str] = []
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, dict):
                name = label.get("name")
                if name:
                    names.append(str(name))
            elif isinstance(label, str):
                names.append(label)
    return names


def classify_outcome(title: str, labels: list[str], repo: str = "") -> str:
    text = " ".join([title, repo, *labels]).lower()
    prefix = title_prefix(title)
    bug_tokens = [
        "bug",
        "fix",
        "regression",
        "crash",
        "error",
        "failure",
        "broken",
        "修复",
        "问题",
        "故障",
        "异常",
    ]
    feature_tokens = [
        "feat",
        "feature",
        "add",
        "support",
        "enable",
        "allow",
        "implement",
        "新增",
        "支持",
        "功能",
    ]
    if prefix == "fix" or keyword_hit(text, bug_tokens):
        return "bug_fix"
    if prefix == "feat" or keyword_hit(text, feature_tokens):
        return "feature"
    return classify_work_type(title, repo)


def code_area_for_path(path: str) -> str:
    lowered = path.lower()
    parts = [part for part in lowered.replace("\\", "/").split("/") if part]
    suffix = Path(lowered).suffix
    if any(part in {"test", "tests", "__tests__", "spec", "e2e", "playwright", "cypress"} for part in parts):
        return "tests"
    if suffix in {".md", ".mdx", ".rst", ".adoc"} or any(part in {"docs", "doc"} for part in parts):
        return "docs"
    if any(part in {".github", "deploy", "charts", "chart", "helm", "k8s", "kubernetes", "terraform", "scripts"} for part in parts):
        return "infra"
    if Path(lowered).name in {
        "dockerfile",
        "makefile",
        "package.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "go.mod",
        "go.sum",
        "requirements.txt",
        "pyproject.toml",
        "tsconfig.json",
        "vite.config.ts",
    } or suffix in {".yaml", ".yml", ".toml", ".json", ".env"}:
        return "config"
    if suffix in {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".sass", ".less"} or any(part in {"components", "pages", "app", "views", "styles"} for part in parts):
        return "frontend"
    if suffix in {".go", ".py", ".rs", ".java", ".kt", ".rb", ".php", ".cs"}:
        return "backend"
    if suffix in {".ts", ".js"}:
        if any(part in {"server", "api", "backend", "service", "services"} for part in parts):
            return "backend"
        return "frontend"
    return "other"


def parse_pr_url(url: str) -> tuple[str, int] | None:
    marker = "github.com/"
    if marker not in url:
        return None
    tail = url.split(marker, 1)[1].strip("/")
    parts = tail.split("/")
    if len(parts) < 4 or parts[2] != "pull":
        return None
    try:
        return f"{parts[0]}/{parts[1]}", int(parts[3])
    except ValueError:
        return None


def fetch_pr_detail(repo: str, number: int) -> tuple[dict[str, Any] | None, str]:
    data, error = try_run_json(["gh", "api", f"repos/{repo}/pulls/{number}"])
    if error or not isinstance(data, dict):
        return None, error or "unexpected response"
    return data, ""


def fetch_pr_files(repo: str, number: int) -> tuple[list[dict[str, Any]], str]:
    data, error = try_run_json(["gh", "api", f"repos/{repo}/pulls/{number}/files", "--paginate"])
    if error:
        return [], error
    return normalize_items(data), ""


def fetch_repo_metadata(repo: str) -> tuple[dict[str, Any] | None, str]:
    data, error = try_run_json(["gh", "api", f"repos/{repo}"])
    if error or not isinstance(data, dict):
        return None, error or "unexpected response"
    return data, ""


def fetch_repo_languages(repo: str) -> dict[str, int]:
    data, error = try_run_json(["gh", "api", f"repos/{repo}/languages"])
    if error or not isinstance(data, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in data.items():
        try:
            out[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return out


def fetch_repo_readme_excerpt(repo: str, max_chars: int = 700) -> str:
    data, error = try_run_json(["gh", "api", f"repos/{repo}/readme"])
    if error or not isinstance(data, dict):
        return ""
    content = data.get("content")
    if not isinstance(content, str):
        return ""
    try:
        decoded = base64.b64decode(content, validate=False).decode("utf-8", errors="ignore")
    except Exception:
        return ""
    lines = []
    for raw in decoded.splitlines():
        line = raw.strip()
        if not line or line.startswith("[!") or line.startswith("<!--"):
            continue
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        line = line.strip("#-*` ")
        if line:
            lines.append(line)
        if sum(len(item) for item in lines) >= max_chars:
            break
    return " ".join(lines)[:max_chars]


def list_recent_user_repos(user: str, start: dt.date, end: dt.date, limit: int = 100) -> list[dict[str, Any]]:
    data, error = try_run_json(
        [
            "gh",
            "repo",
            "list",
            user,
            "--json",
            "nameWithOwner,description,createdAt,updatedAt,isPrivate,isArchived,isFork,primaryLanguage,url",
            "--limit",
            str(limit),
        ]
    )
    if error:
        return []
    rows = []
    for item in normalize_items(data):
        created = str(item.get("createdAt") or "")
        try:
            created_day = dt.date.fromisoformat(created[:10])
        except ValueError:
            continue
        if start <= created_day <= end:
            rows.append(item)
    return rows


def sum_numeric(items: list[dict[str, Any]], key: str) -> int:
    total = 0
    for item in items:
        value = item.get(key)
        if isinstance(value, int):
            total += value
        elif isinstance(value, float):
            total += int(value)
        else:
            try:
                total += int(value)
            except (TypeError, ValueError):
                pass
    return total


def issue_is_bug_like(issue: dict[str, Any]) -> bool:
    text = " ".join([issue.get("title", ""), *label_names(issue)]).lower()
    return keyword_hit(text, ["bug", "fix", "regression", "crash", "error", "failure", "broken", "修复", "故障", "异常"])


def build_engineering_outcomes(summary: dict[str, Any], fetch_code_stats: bool = True) -> dict[str, Any]:
    merged_prs = list(summary.get("prs", {}).get("merged", []))
    closed_issues = list(summary.get("issues", {}).get("closed_related", []))
    by_repo: dict[str, dict[str, Any]] = {}
    by_type: dict[str, dict[str, Any]] = {
        key: {"key": key, "label": meta["label"], "count": 0}
        for key, meta in WORK_TYPE_DEFINITIONS.items()
    }
    area_rows: dict[str, dict[str, Any]] = {
        key: {"key": key, "label": meta["label"], "color": meta["color"], "files": 0, "additions": 0, "deletions": 0}
        for key, meta in CODE_AREA_DEFINITIONS.items()
    }
    representative_features: list[dict[str, Any]] = []
    representative_bugs: list[dict[str, Any]] = []
    pr_stats_rows: list[dict[str, Any]] = []
    stats_failures: list[dict[str, Any]] = []

    def ensure_repo(repo: str) -> dict[str, Any]:
        if repo not in by_repo:
            by_repo[repo] = {
                "repo": repo,
                "feature_points": 0,
                "bug_fixes": 0,
                "merged_prs": 0,
                "bug_like_closed_issues": 0,
                "additions": 0,
                "deletions": 0,
                "changed_files": 0,
                "net_lines": 0,
            }
        return by_repo[repo]

    for pr in merged_prs:
        repo = pr.get("repo", "unknown") or "unknown"
        labels = label_names(pr)
        work_type = classify_work_type(pr.get("title", ""), repo)
        outcome = classify_outcome(pr.get("title", ""), labels, repo)
        row = ensure_repo(repo)
        row["merged_prs"] += 1
        by_type.setdefault(work_type, {"key": work_type, "label": work_type, "count": 0})["count"] += 1
        enriched_pr = {
            **pr,
            "work_type": work_type,
            "work_type_label": WORK_TYPE_DEFINITIONS.get(work_type, {}).get("label", work_type),
            "outcome": outcome,
        }
        if outcome == "bug_fix":
            row["bug_fixes"] += 1
            representative_bugs.append(enriched_pr)
        elif outcome == "feature":
            row["feature_points"] += 1
            representative_features.append(enriched_pr)

    for issue in closed_issues:
        if not issue_is_bug_like(issue):
            continue
        repo = issue.get("repo", "unknown") or "unknown"
        ensure_repo(repo)["bug_like_closed_issues"] += 1

    totals = {
        "feature_points": sum(row["feature_points"] for row in by_repo.values()),
        "bug_fixes": sum(row["bug_fixes"] for row in by_repo.values()),
        "bug_like_closed_issues": sum(row["bug_like_closed_issues"] for row in by_repo.values()),
        "additions": 0,
        "deletions": 0,
        "changed_files": 0,
        "net_lines": 0,
    }

    stats_attempted = 0
    stats_succeeded = 0
    files_succeeded = 0
    if fetch_code_stats:
        for pr in merged_prs:
            parsed = parse_pr_url(pr.get("url", ""))
            if not parsed:
                stats_failures.append({"repo": pr.get("repo", "unknown"), "number": pr.get("number"), "error": "cannot parse PR URL"})
                continue
            repo, number = parsed
            stats_attempted += 1
            detail, detail_error = fetch_pr_detail(repo, number)
            files, files_error = fetch_pr_files(repo, number)
            if detail_error:
                stats_failures.append({"repo": repo, "number": number, "error": detail_error})
                continue

            stats_succeeded += 1
            additions = int(detail.get("additions") or 0)
            deletions = int(detail.get("deletions") or 0)
            changed_files = int(detail.get("changed_files") or len(files) or 0)
            row = ensure_repo(repo)
            row["additions"] += additions
            row["deletions"] += deletions
            row["changed_files"] += changed_files
            row["net_lines"] += additions - deletions
            totals["additions"] += additions
            totals["deletions"] += deletions
            totals["changed_files"] += changed_files
            totals["net_lines"] += additions - deletions

            if files:
                files_succeeded += 1
                for file_item in files:
                    area = code_area_for_path(str(file_item.get("filename") or ""))
                    area_rows[area]["files"] += 1
                    area_rows[area]["additions"] += int(file_item.get("additions") or 0)
                    area_rows[area]["deletions"] += int(file_item.get("deletions") or 0)
            elif files_error:
                stats_failures.append({"repo": repo, "number": number, "error": f"files: {files_error}"})

            pr_stats_rows.append(
                {
                    "repo": repo,
                    "number": number,
                    "title": pr.get("title", ""),
                    "url": pr.get("url", ""),
                    "additions": additions,
                    "deletions": deletions,
                    "changed_files": changed_files,
                    "net_lines": additions - deletions,
                    "work_type": classify_work_type(pr.get("title", ""), repo),
                    "outcome": classify_outcome(pr.get("title", ""), label_names(pr), repo),
                }
            )

    repo_rows = sorted(
        by_repo.values(),
        key=lambda row: (
            int(row.get("feature_points", 0)) * 4
            + int(row.get("bug_fixes", 0)) * 4
            + int(row.get("bug_like_closed_issues", 0)) * 2
            + int(row.get("changed_files", 0)),
            int(row.get("additions", 0)) + int(row.get("deletions", 0)),
        ),
        reverse=True,
    )
    type_rows = sorted([item for item in by_type.values() if item.get("count")], key=lambda item: item["count"], reverse=True)
    code_area_rows = sorted([item for item in area_rows.values() if item.get("files")], key=lambda item: item["additions"] + item["deletions"], reverse=True)
    pr_stats_rows = sorted(pr_stats_rows, key=lambda item: int(item.get("additions", 0)) + int(item.get("deletions", 0)), reverse=True)

    coverage = {
        "merged_prs_total": len(merged_prs),
        "classification_source": "merged PR title, labels, and repository name",
        "code_stats_source": "GitHub REST API repos/{repo}/pulls/{number} and pull files",
        "code_stats_attempted": stats_attempted,
        "code_stats_succeeded": stats_succeeded,
        "code_stats_failed": len([item for item in stats_failures if not str(item.get("error", "")).startswith("files:")]),
        "file_breakdown_succeeded": files_succeeded,
        "direct_commit_line_stats_included": False,
    }

    return {
        "method": "Feature points and bug fixes are deterministic classifications over merged authored PRs. Code lines come from merged PR additions/deletions when the GitHub API is available; they are not a business-value proxy and exclude direct commit line stats.",
        "coverage": coverage,
        "totals": totals,
        "by_repo": repo_rows[:20],
        "by_work_type": type_rows,
        "code_areas": code_area_rows,
        "top_code_prs": pr_stats_rows[:20],
        "representative_features": representative_features[:12],
        "representative_bugs": representative_bugs[:12],
        "stats_failures": stats_failures[:20],
    }


def enrich_top_repos_with_outcomes(top_rows: list[dict[str, Any]], outcomes: dict[str, Any]) -> list[dict[str, Any]]:
    outcome_by_repo = {
        str(row.get("repo")): row
        for row in outcomes.get("by_repo", [])
        if isinstance(row, dict) and row.get("repo")
    }
    enriched: list[dict[str, Any]] = []
    for row in top_rows:
        repo = str(row.get("repo", ""))
        outcome = outcome_by_repo.get(repo, {})
        enriched.append(
            {
                **row,
                "feature_points": int(outcome.get("feature_points", 0) or 0),
                "bug_fixes": int(outcome.get("bug_fixes", 0) or 0),
                "bug_like_closed_issues": int(outcome.get("bug_like_closed_issues", 0) or 0),
                "additions": int(outcome.get("additions", 0) or 0),
                "deletions": int(outcome.get("deletions", 0) or 0),
                "changed_files": int(outcome.get("changed_files", 0) or 0),
                "net_lines": int(outcome.get("net_lines", 0) or 0),
            }
        )
    for repo, outcome in outcome_by_repo.items():
        if any(row.get("repo") == repo for row in enriched):
            continue
        enriched.append(
            {
                "repo": repo,
                "score": 0,
                "feature_points": int(outcome.get("feature_points", 0) or 0),
                "bug_fixes": int(outcome.get("bug_fixes", 0) or 0),
                "bug_like_closed_issues": int(outcome.get("bug_like_closed_issues", 0) or 0),
                "additions": int(outcome.get("additions", 0) or 0),
                "deletions": int(outcome.get("deletions", 0) or 0),
                "changed_files": int(outcome.get("changed_files", 0) or 0),
                "net_lines": int(outcome.get("net_lines", 0) or 0),
            }
        )
    return enriched


def first_day_from_items(items: list[dict[str, Any]], keys: list[str]) -> str:
    days: list[str] = []
    for item in items:
        for key in keys:
            value = item.get(key)
            if value:
                days.append(str(value)[:10])
                break
    return min(days) if days else ""


def top_languages(languages: dict[str, int], limit: int = 3) -> list[dict[str, Any]]:
    total = sum(languages.values()) or 1
    rows = []
    for name, value in sorted(languages.items(), key=lambda item: item[1], reverse=True)[:limit]:
        rows.append({"language": name, "bytes": value, "pct": round(value / total * 100, 1)})
    return rows


def repo_display_name(repo: str) -> str:
    return repo.split("/", 1)[-1] if "/" in repo else repo


def infer_project_purpose(repo: str, metadata: dict[str, Any], readme: str, evidence_titles: list[str]) -> str:
    repo_lower = repo.lower()
    text = " ".join([repo, str(metadata.get("description") or ""), readme, *evidence_titles]).lower()
    description = str(metadata.get("description") or "").strip()
    if description:
        return description[:180]
    if "sealos-ui" in repo_lower:
        return "围绕 Sealos 前端 UI 组件、样式体系和复用界面资产的基础项目。"
    if "admin" in repo_lower or "tenant" in repo_lower:
        return "围绕管理后台、租户治理和平台运营能力的项目。"
    if "registry" in repo_lower:
        return "围绕镜像仓库、上传下载、兼容性和镜像管理体验的项目。"
    if "kite" in repo_lower:
        return "围绕 Helm、应用交付和平台运维能力的项目。"
    if "offline" in repo_lower:
        return "围绕离线交付、镜像/制品分发和私有化部署链路的项目。"
    if "objectstorage" in repo_lower:
        return "围绕对象存储应用能力和平台应用交付的项目。"
    if "cronjob" in repo_lower:
        return "围绕定时任务应用能力和平台应用交付的项目。"
    if "devbox" in repo_lower or "devbox-runtime" in repo_lower:
        return "围绕 DevBox 开发环境、IDE、配置和运行时体验的研发效率项目。"
    if any(token in repo_lower for token in ["mspace", "maestro", "mbox"]):
        return "围绕 AI 工作空间、执行平台和项目协作形态的个人产品探索。"
    if "github.io" in repo_lower or "skills" in repo_lower or "typora" in repo_lower:
        return "围绕个人知识沉淀、文档资产和工作流工具化的项目。"
    if "devbox" in text or "jetbrains" in text or "ssh" in text:
        return "围绕 DevBox 开发环境、IDE、配置和运行时体验的研发效率项目。"
    if "mspace" in text or "maestro" in text or "mbox" in text or "sandbox" in text:
        return "围绕 AI 工作空间、执行平台和项目协作形态的个人产品探索。"
    if "registry" in text:
        return "围绕镜像仓库、上传下载、兼容性和镜像管理体验的项目。"
    if "admin" in text or "tenant" in text:
        return "围绕管理后台、租户治理和平台运营能力的项目。"
    if "kite" in text or "helm" in text:
        return "围绕 Helm、应用交付和平台运维能力的项目。"
    if "offline" in text or "oci" in text:
        return "围绕离线交付、镜像/制品分发和私有化部署链路的项目。"
    if readme:
        return readme[:180]
    return "根据仓库名、提交和 PR 线索识别出的本季度活跃项目，暂无足够 README/描述说明。"


def interesting_work_tags(titles: list[str], repo: str, theme: str) -> list[str]:
    text = " ".join([repo, theme, *titles]).lower()
    tags: list[str] = []
    checks = [
        ("IDE / DevBox 体验", ["jetbrains", "cursor", "vscode", "ssh", "devbox"]),
        ("离线与私有化交付", ["offline", "oci", "airgap", "private", "registry"]),
        ("权限与登录链路", ["login", "sign-in", "auth", "account", "workspace"]),
        ("可观测和运维", ["metric", "prometheus", "monitor", "helm", "runtime"]),
        ("前端交互体验", ["ui", "dialog", "progress", "empty", "dropdown", "frontend"]),
        ("迁移和兼容性", ["migrate", "migration", "compat", "v1alpha2", "rollback"]),
        ("测试与质量", ["test", "e2e", "playwright", "coverage"]),
        ("文档/知识产品化", ["docs", "readme", "skill", "github.io"]),
    ]
    for label, keywords in checks:
        if any(keyword in text for keyword in keywords):
            tags.append(label)
    return tags[:4]


def project_narrative(row: dict[str, Any]) -> str:
    bits = []
    if row.get("is_new_repo"):
        bits.append("本季度新建仓库")
    elif row.get("is_newly_active"):
        bits.append("本季度新启动/重新活跃")
    else:
        bits.append("持续推进")
    metrics = []
    if row.get("merged_prs"):
        metrics.append(f"{row['merged_prs']} 个合并 PR")
    if row.get("commits"):
        metrics.append(f"{row['commits']} 次 commit")
    if row.get("feature_points"):
        metrics.append(f"{row['feature_points']} 个功能点")
    if row.get("bug_fixes"):
        metrics.append(f"{row['bug_fixes']} 个修复")
    if metrics:
        bits.append("，".join(metrics))
    if row.get("interesting_work"):
        bits.append("重点方向：" + "、".join(row["interesting_work"][:3]))
    return "；".join(bits) + "。"


def build_project_portfolio(summary: dict[str, Any], previous_summary: dict[str, Any] | None = None, user_recent_repos: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    start = parse_date(summary["start"])
    end = parse_date(summary["end"])
    previous_repos = set()
    if previous_summary:
        previous_repos = {str(row.get("repo")) for row in previous_summary.get("top_repos", []) if isinstance(row, dict) and row.get("repo")}

    repo_items: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for repo in {row.get("repo") for row in summary.get("top_repos", []) if row.get("repo") and row.get("repo") != "unknown"}:
        repo_items[str(repo)] = {"prs": [], "commits": [], "issues": []}
    for pr in summary.get("prs", {}).get("merged", []) + summary.get("prs", {}).get("created", []):
        repo_items.setdefault(pr.get("repo", "unknown"), {"prs": [], "commits": [], "issues": []})["prs"].append(pr)
    for commit in summary.get("commits", []):
        repo_items.setdefault(commit.get("repo", "unknown"), {"prs": [], "commits": [], "issues": []})["commits"].append(commit)
    for issue in summary.get("issues", {}).get("closed_related", []) + summary.get("issues", {}).get("created", []):
        repo_items.setdefault(issue.get("repo", "unknown"), {"prs": [], "commits": [], "issues": []})["issues"].append(issue)

    top_by_repo = {row.get("repo"): row for row in summary.get("top_repos", []) if isinstance(row, dict)}
    outcome_by_repo = {
        row.get("repo"): row
        for row in (summary.get("engineering_outcomes") or {}).get("by_repo", [])
        if isinstance(row, dict)
    }
    candidate_repos = {repo for repo, items in repo_items.items() if repo and repo != "unknown" and (items["prs"] or items["commits"] or items["issues"])}
    for item in user_recent_repos or []:
        repo = item.get("nameWithOwner")
        if repo:
            candidate_repos.add(str(repo))

    projects: list[dict[str, Any]] = []
    fetch_failures: list[dict[str, Any]] = []
    for repo in sorted(candidate_repos):
        items = repo_items.get(repo, {"prs": [], "commits": [], "issues": []})
        metadata, metadata_error = fetch_repo_metadata(repo)
        if metadata_error:
            fetch_failures.append({"repo": repo, "error": metadata_error})
            metadata = {}
        languages = fetch_repo_languages(repo)
        readme = fetch_repo_readme_excerpt(repo)
        top_row = top_by_repo.get(repo, {})
        outcome = outcome_by_repo.get(repo, {})
        created_at = str(metadata.get("created_at") or metadata.get("createdAt") or "")
        created_day = ""
        try:
            created_day = dt.date.fromisoformat(created_at[:10]).isoformat() if created_at else ""
        except ValueError:
            created_day = ""
        is_new_repo = bool(created_day and start <= dt.date.fromisoformat(created_day) <= end)
        is_newly_active = repo not in previous_repos and not is_new_repo
        prs = items.get("prs", [])
        commits = items.get("commits", [])
        issues = items.get("issues", [])
        evidence_titles = [str(item.get("title") or "") for item in prs[:8]] + [str(item.get("title") or "") for item in commits[:8]]
        theme = classify_theme(repo, " ".join(evidence_titles))
        interesting = interesting_work_tags(evidence_titles, repo, theme)
        representative = sorted(
            prs,
            key=lambda pr: (
                0 if classify_outcome(pr.get("title", ""), label_names(pr), repo) == "feature" else 1,
                -int(pr.get("comments", 0) or 0),
                str(pr.get("closed_at") or pr.get("created_at") or ""),
            ),
        )[:4]
        row = {
            "repo": repo,
            "name": repo_display_name(repo),
            "url": metadata.get("html_url") or f"https://github.com/{repo}",
            "description": metadata.get("description") or "",
            "purpose": infer_project_purpose(repo, metadata, readme, evidence_titles),
            "theme": theme,
            "created_at": created_day,
            "updated_at": str(metadata.get("updated_at") or "")[:10],
            "is_private": bool(metadata.get("private")),
            "is_archived": bool(metadata.get("archived")),
            "is_fork": bool(metadata.get("fork")),
            "is_new_repo": is_new_repo,
            "is_newly_active": is_newly_active,
            "first_activity_at": first_day_from_items(prs + commits + issues, ["created_at", "closed_at", "authored_at", "updated_at"]),
            "score": int(top_row.get("score", 0) or 0),
            "commits": int(top_row.get("commits", 0) or 0),
            "prs_created": int(top_row.get("prs_created", 0) or 0),
            "merged_prs": int(top_row.get("prs_merged", 0) or 0),
            "reviewed_prs": int(top_row.get("prs_reviewed", 0) or 0),
            "issues": int(top_row.get("issues_created", 0) or 0) + int(top_row.get("issues_closed_related", 0) or 0),
            "feature_points": int(outcome.get("feature_points", top_row.get("feature_points", 0)) or 0),
            "bug_fixes": int(outcome.get("bug_fixes", top_row.get("bug_fixes", 0)) or 0),
            "additions": int(outcome.get("additions", top_row.get("additions", 0)) or 0),
            "deletions": int(outcome.get("deletions", top_row.get("deletions", 0)) or 0),
            "changed_files": int(outcome.get("changed_files", top_row.get("changed_files", 0)) or 0),
            "top_languages": top_languages(languages),
            "interesting_work": interesting,
            "representative_prs": representative,
            "readme_excerpt": readme,
        }
        row["narrative"] = project_narrative(row)
        projects.append(row)

    projects = sorted(
        projects,
        key=lambda row: (
            1 if row.get("is_new_repo") else 0,
            1 if row.get("is_newly_active") else 0,
            int(row.get("score", 0)) + int(row.get("feature_points", 0)) * 5 + int(row.get("bug_fixes", 0)) * 3,
        ),
        reverse=True,
    )
    new_repos = [row for row in projects if row.get("is_new_repo")]
    newly_active = [row for row in projects if row.get("is_newly_active")]
    interesting = sorted(
        [row for row in projects if row.get("interesting_work")],
        key=lambda row: (len(row.get("interesting_work", [])), row.get("score", 0)),
        reverse=True,
    )
    return {
        "method": "Portfolio rows combine GitHub repo metadata, README excerpts, quarterly PR/commit/issue evidence, previous-period activity, and deterministic keyword tags. Purpose text is repo description first, then README/title inference.",
        "totals": {
            "projects": len(projects),
            "new_repositories": len(new_repos),
            "newly_active_projects": len(newly_active),
            "interesting_projects": len(interesting),
        },
        "new_repositories": new_repos[:12],
        "newly_active_projects": newly_active[:12],
        "interesting_projects": interesting[:12],
        "projects": projects[:30],
        "fetch_failures": fetch_failures[:20],
    }


def theme_score(item: dict[str, Any]) -> int:
    return (
        int(item.get("merged_prs", 0)) * 5
        + int(item.get("created_prs", 0)) * 3
        + int(item.get("reviewed_prs", 0)) * 2
        + int(item.get("commits", 0))
        + int(item.get("issues", 0))
    )


def build_contribution_portrait(summary: dict[str, Any]) -> dict[str, Any]:
    themes: dict[str, dict[str, Any]] = {}
    work_types: dict[str, dict[str, Any]] = {
        key: {"key": key, "label": meta["label"], "color": meta["color"], "merged_prs": 0, "created_prs": 0, "commits": 0, "reviewed_prs": 0, "issues": 0}
        for key, meta in WORK_TYPE_DEFINITIONS.items()
    }

    def ensure_theme(name: str) -> dict[str, Any]:
        if name not in themes:
            themes[name] = {
                "theme": name,
                "description": THEME_DESCRIPTIONS.get(name, THEME_DESCRIPTIONS["其他 GitHub 活动"]),
                "repos": Counter(),
                "merged_prs": 0,
                "created_prs": 0,
                "commits": 0,
                "reviewed_prs": 0,
                "issues": 0,
                "representative_prs": [],
            }
        return themes[name]

    for pr in summary.get("prs", {}).get("merged", []):
        theme = ensure_theme(classify_theme(pr.get("repo", ""), pr.get("title", "")))
        work_type = classify_work_type(pr.get("title", ""), pr.get("repo", ""))
        theme["merged_prs"] += 1
        theme["repos"][pr.get("repo", "unknown")] += 1
        work_types[work_type]["merged_prs"] += 1
        theme["representative_prs"].append({**pr, "work_type": work_type, "work_type_label": WORK_TYPE_DEFINITIONS[work_type]["label"]})

    for pr in summary.get("prs", {}).get("created", []):
        theme = ensure_theme(classify_theme(pr.get("repo", ""), pr.get("title", "")))
        work_type = classify_work_type(pr.get("title", ""), pr.get("repo", ""))
        theme["created_prs"] += 1
        theme["repos"][pr.get("repo", "unknown")] += 1
        work_types[work_type]["created_prs"] += 1

    for pr in summary.get("prs", {}).get("reviewed", []):
        theme = ensure_theme(classify_theme(pr.get("repo", ""), pr.get("title", "")))
        theme["reviewed_prs"] += 1
        theme["repos"][pr.get("repo", "unknown")] += 1
        work_types["review"]["reviewed_prs"] += 1

    for commit in summary.get("commits", []):
        theme = ensure_theme(classify_theme(commit.get("repo", ""), commit.get("title", "")))
        work_type = classify_work_type(commit.get("title", ""), commit.get("repo", ""))
        theme["commits"] += 1
        theme["repos"][commit.get("repo", "unknown")] += 1
        work_types[work_type]["commits"] += 1

    for issue in summary.get("issues", {}).get("closed_related", []):
        theme = ensure_theme(classify_theme(issue.get("repo", ""), issue.get("title", "")))
        theme["issues"] += 1
        theme["repos"][issue.get("repo", "unknown")] += 1
        work_types["issue"]["issues"] += 1

    theme_rows = []
    for theme in themes.values():
        reps = sorted(
            theme["representative_prs"],
            key=lambda pr: (
                WORK_TYPE_PRIORITY.index(pr["work_type"]) if pr["work_type"] in WORK_TYPE_PRIORITY else 99,
                -int(pr.get("comments", 0)),
                str(pr.get("closed_at") or pr.get("updated_at") or ""),
            ),
        )
        unique_reps = []
        seen_signatures: set[tuple[str, str]] = set()
        for pr in reps:
            signature_words = [word for word in pr.get("title", "").lower().replace(":", " ").replace("(", " ").replace(")", " ").split() if word not in {"feat", "fix", "frontend", "desktop"}]
            signature = (pr.get("repo", ""), " ".join(signature_words[:3]))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            unique_reps.append(pr)
            if len(unique_reps) >= 3:
                break
        repo_counts = theme["repos"]
        row = {
            "theme": theme["theme"],
            "description": theme["description"],
            "score": theme_score(theme),
            "primary_repos": [{"repo": repo, "count": count} for repo, count in repo_counts.most_common(3)],
            "merged_prs": theme["merged_prs"],
            "created_prs": theme["created_prs"],
            "commits": theme["commits"],
            "reviewed_prs": theme["reviewed_prs"],
            "issues": theme["issues"],
            "representative_prs": unique_reps,
        }
        theme_rows.append(row)

    theme_rows = sorted(theme_rows, key=lambda row: row["score"], reverse=True)
    work_type_rows = []
    for key, item in work_types.items():
        total = item["merged_prs"] * 4 + item["created_prs"] * 2 + item["commits"] + item["reviewed_prs"] * 2 + item["issues"]
        if total <= 0:
            continue
        work_type_rows.append({**item, "score": total})
    work_type_rows = sorted(work_type_rows, key=lambda row: row["score"], reverse=True)

    metrics = summary.get("metrics", {})
    comparison = summary.get("comparison", {})
    top_theme = theme_rows[0]["theme"] if theme_rows else "暂无稳定主题"
    growth_lines = []
    if comparison.get("prs_merged", {}).get("delta", 0) > 0:
        growth_lines.append(f"合并 PR 较上季增加 {comparison['prs_merged']['delta']} 个，已合入交付密度提升。")
    if comparison.get("commits", {}).get("delta", 0) > 0:
        growth_lines.append(f"Commit 较上季增加 {comparison['commits']['delta']} 次，代码活动覆盖 {metrics.get('active_repos', 0)} 个仓库。")
    if comparison.get("prs_reviewed", {}).get("delta", 0) > 0:
        growth_lines.append(f"Review 参与 PR 较上季增加 {comparison['prs_reviewed']['delta']} 个，协作参与度上升。")
    if theme_rows:
        growth_lines.append(f"本季度最集中的投入方向是“{top_theme}”，该主题沉淀了 {theme_rows[0]['merged_prs']} 个合并 PR 和 {theme_rows[0]['commits']} 次 commit。")
    if metrics.get("issues_closed_related", 0):
        growth_lines.append("Issue 使用相关关闭口径统计，适合表达问题跟进参与，不直接等同于亲自解决数量。")

    return {
        "method": "themes are inferred from repo names and titles; work types are inferred from PR title prefixes and keywords; verify important conclusions via links",
        "themes": theme_rows[:8],
        "work_types": work_type_rows,
        "representative_prs": [pr for theme in theme_rows[:5] for pr in theme["representative_prs"][:2]][:10],
        "growth_narrative": growth_lines[:5],
    }


def short_sha(item: dict[str, Any]) -> str:
    sha = item.get("sha") or item.get("id") or ""
    return str(sha)[:8]


def commit_message(item: dict[str, Any]) -> str:
    commit = item.get("commit") or {}
    if isinstance(commit, dict):
        message = commit.get("message") or ""
        return message.splitlines()[0]
    return ""


def pr_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "repo": repo_name(item),
        "number": item.get("number"),
        "title": item.get("title") or "",
        "labels": label_names(item),
        "state": item.get("state") or "",
        "created_at": item.get("createdAt"),
        "closed_at": item.get("closedAt"),
        "updated_at": item.get("updatedAt"),
        "comments": item.get("commentsCount") or 0,
        "url": item.get("url") or "",
    }


def issue_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "repo": repo_name(item),
        "number": item.get("number"),
        "title": item.get("title") or "",
        "labels": label_names(item),
        "state": item.get("state") or "",
        "created_at": item.get("createdAt"),
        "closed_at": item.get("closedAt"),
        "updated_at": item.get("updatedAt"),
        "comments": item.get("commentsCount") or 0,
        "url": item.get("url") or "",
    }


def commit_row(item: dict[str, Any]) -> dict[str, Any]:
    commit = item.get("commit") or {}
    authored = ""
    if isinstance(commit, dict):
        authored = ((commit.get("author") or {}).get("date") if isinstance(commit.get("author"), dict) else "") or ""
    return {
        "repo": repo_name(item),
        "sha": short_sha(item),
        "title": commit_message(item),
        "authored_at": authored,
        "url": item.get("url") or "",
    }


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def format_signed(value: int) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


def pct_change(current: int, previous: int) -> str:
    if previous == 0:
        if current == 0:
            return "0%"
        return "新增"
    pct = (current - previous) / previous * 100
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.0f}%"


def compare_metrics(current: dict[str, int], previous: dict[str, int]) -> dict[str, dict[str, Any]]:
    comparisons = {}
    for key, label in COMPARABLE_METRICS:
        now = int(current.get(key, 0))
        before = int(previous.get(key, 0))
        delta = now - before
        comparisons[key] = {
            "label": label,
            "current": now,
            "previous": before,
            "delta": delta,
            "pct": pct_change(now, before),
            "direction": "up" if delta > 0 else "down" if delta < 0 else "flat",
        }
    return comparisons


def link(url: str, text: str) -> str:
    if not url:
        return esc(text)
    return f'<a href="{esc(url)}" target="_blank" rel="noreferrer">{esc(text)}</a>'


def render_metric_card(key: str, label: str, value: Any, hint: str, comparison: dict[str, Any] | None) -> str:
    delta_html = ""
    if comparison:
        direction = comparison["direction"]
        delta_html = f"""
          <div class="metric-delta delta-{esc(direction)}">
            <span>{esc(format_signed(comparison['delta']))}</span>
            <span>{esc(comparison['pct'])}</span>
            <span>较上季</span>
          </div>
        """
    return f"""
      <div class="metric metric-{esc(key)}">
        <div class="metric-value">{esc(value)}</div>
        <div class="metric-label">{esc(label)}</div>
        <div class="metric-hint">{esc(hint)}</div>
        {delta_html}
      </div>
    """


def render_table(headers: list[str], rows: list[list[str]], empty: str) -> str:
    if not rows:
        return f'<p class="empty">{esc(empty)}</p>'
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "\n".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render_bar_chart(rows: list[dict[str, Any]], metric: str, label: str, limit: int = 10) -> str:
    selected = [row for row in rows if int(row.get(metric, 0)) > 0][:limit]
    if not selected:
        return f'<p class="empty">没有可展示的 {esc(label)} 数据。</p>'
    max_value = max(int(row.get(metric, 0)) for row in selected) or 1
    bars = []
    for row in selected:
        value = int(row.get(metric, 0))
        width = max(4, round(value / max_value * 100))
        bars.append(
            f"""
            <div class="bar-row">
              <div class="bar-name">{link(f"https://github.com/{row['repo']}", row["repo"])}</div>
              <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
              <div class="bar-value">{esc(value)}</div>
            </div>
            """
        )
    return f'<div class="bar-chart" aria-label="{esc(label)}">' + "\n".join(bars) + "</div>"


def render_comparison_bars(comparison: dict[str, dict[str, Any]]) -> str:
    keys = ["commits", "prs_created", "prs_merged", "prs_reviewed", "issues_closed_related"]
    max_value = max([comparison[key]["current"] for key in keys] + [comparison[key]["previous"] for key in keys] + [1])
    rows = []
    for key in keys:
        item = comparison[key]
        current_width = round(item["current"] / max_value * 100)
        previous_width = round(item["previous"] / max_value * 100)
        rows.append(
            f"""
            <div class="compare-row">
              <div class="compare-label">{esc(item['label'])}</div>
              <div class="compare-bars">
                <div class="compare-line"><span>本季度</span><div><i class="now" style="width:{current_width}%"></i></div><strong>{esc(item['current'])}</strong></div>
                <div class="compare-line"><span>上季度</span><div><i class="prev" style="width:{previous_width}%"></i></div><strong>{esc(item['previous'])}</strong></div>
              </div>
              <div class="compare-change delta-{esc(item['direction'])}">{esc(format_signed(item['delta']))} · {esc(item['pct'])}</div>
            </div>
            """
        )
    return '<div class="compare-chart">' + "\n".join(rows) + "</div>"


def render_activity_mix(metrics: dict[str, int]) -> str:
    items = [
        ("commits", "Commit", metrics.get("commits", 0), "#3b82f6"),
        ("prs_merged", "合并 PR", metrics.get("prs_merged", 0), "#16a34a"),
        ("prs_reviewed", "Review PR", metrics.get("prs_reviewed", 0), "#7c3aed"),
        ("issues_closed_related", "相关关闭 Issue", metrics.get("issues_closed_related", 0), "#d97706"),
    ]
    total = sum(value for _, _, value, _ in items)
    if total <= 0:
        return '<p class="empty">没有可展示的活动构成数据。</p>'
    segments = []
    legend = []
    for key, label, value, color in items:
        width = value / total * 100
        segments.append(f'<span class="mix-segment mix-{esc(key)}" style="width:{width:.2f}%; background:{color}"></span>')
        legend.append(f'<li><i style="background:{color}"></i><span>{esc(label)}</span><strong>{esc(value)}</strong></li>')
    return f"""
      <div class="mix-chart">
        <div class="mix-bar">{"".join(segments)}</div>
        <ul class="mix-legend">{"".join(legend)}</ul>
      </div>
    """


def render_leadership_insights(summary: dict[str, Any]) -> str:
    metrics = summary["metrics"]
    comparison = summary.get("comparison", {})
    top_repos = summary["top_repos"][:3]
    best_growth = sorted(
        [item for item in comparison.values() if item["delta"] > 0],
        key=lambda item: item["delta"],
        reverse=True,
    )[:3]
    bullets = []
    if top_repos:
        bullets.append("重点投入集中在 " + "、".join(row["repo"] for row in top_repos) + "。")
    if metrics.get("prs_merged", 0):
        bullets.append(f"本季度合并 PR {metrics['prs_merged']} 个，代码交付有明确合入记录。")
    if metrics.get("commits", 0):
        bullets.append(f"本季度 authored commit {metrics['commits']} 次，覆盖 {metrics.get('active_repos', 0)} 个活跃仓库。")
    if metrics.get("prs_reviewed", 0):
        bullets.append(f"参与 review 的 PR {metrics['prs_reviewed']} 个，体现跨仓库协作和质量把关。")
    if best_growth:
        growth_text = "、".join(f"{item['label']} {format_signed(item['delta'])}" for item in best_growth)
        bullets.append(f"环比增长最明显的是 {growth_text}。")
    if not bullets:
        bullets.append("当前数据不足以提炼稳定结论，建议缩小仓库范围或补充本地仓库扫描。")
    return "<ul class=\"insights\">" + "".join(f"<li>{esc(text)}</li>" for text in bullets[:5]) + "</ul>"


def render_work_type_mix(portrait: dict[str, Any]) -> str:
    rows = portrait.get("work_types", [])
    if not rows:
        return '<p class="empty">没有足够数据生成贡献类型画像。</p>'
    max_score = max([int(row.get("score", 0)) for row in rows] + [1])
    parts = []
    for row in rows:
        width = max(4, round(int(row.get("score", 0)) / max_score * 100))
        label = row.get("label", row.get("key", ""))
        detail = []
        if row.get("merged_prs"):
            detail.append(f"合并 PR {row['merged_prs']}")
        if row.get("commits"):
            detail.append(f"Commit {row['commits']}")
        if row.get("reviewed_prs"):
            detail.append(f"Review PR {row['reviewed_prs']}")
        if row.get("issues"):
            detail.append(f"Issue {row['issues']}")
        parts.append(
            f"""
            <div class="type-row">
              <div class="type-label"><i style="background:{esc(row.get('color', '#647084'))}"></i>{esc(label)}</div>
              <div class="type-track"><span style="width:{width}%; background:{esc(row.get('color', '#647084'))}"></span></div>
              <div class="type-detail">{esc(' · '.join(detail) or row.get('score', 0))}</div>
            </div>
            """
        )
    return '<div class="type-chart">' + "\n".join(parts) + "</div>"


def render_theme_cards(portrait: dict[str, Any]) -> str:
    themes = portrait.get("themes", [])[:6]
    if not themes:
        return '<p class="empty">没有足够数据生成季度主题。</p>'
    cards = []
    for theme in themes:
        repos = "、".join(repo["repo"] for repo in theme.get("primary_repos", []) if repo.get("repo")) or "暂无主仓库"
        metrics = [
            f"{theme.get('merged_prs', 0)} 合并 PR",
            f"{theme.get('commits', 0)} commit",
        ]
        if theme.get("reviewed_prs"):
            metrics.append(f"{theme['reviewed_prs']} review PR")
        reps = []
        for pr in theme.get("representative_prs", [])[:2]:
            reps.append(
                f"""
                <li>
                  {link(pr.get("url", ""), f"#{pr.get('number')}")}
                  <span>{esc(pr.get("title", ""))}</span>
                </li>
                """
            )
        rep_html = "<ul class=\"theme-prs\">" + "".join(reps) + "</ul>" if reps else '<p class="theme-empty">该主题主要来自 commit / issue / review 证据。</p>'
        cards.append(
            f"""
            <article class="theme-card">
              <div class="theme-card-head">
                <h3>{esc(theme.get('theme', ''))}</h3>
                <span>{esc(theme.get('score', 0))}</span>
              </div>
              <p>{esc(theme.get('description', ''))}</p>
              <div class="theme-meta">{esc(repos)}</div>
              <div class="theme-stats">{''.join(f'<b>{esc(item)}</b>' for item in metrics)}</div>
              {rep_html}
            </article>
            """
        )
    return '<div class="theme-grid">' + "\n".join(cards) + "</div>"


def render_representative_prs(portrait: dict[str, Any]) -> str:
    prs = portrait.get("representative_prs", [])[:8]
    if not prs:
        return '<p class="empty">没有可展示的代表性合并 PR。</p>'
    items = []
    for pr in prs:
        items.append(
            f"""
            <article class="pr-card">
              <div class="pr-card-top">
                <span>{esc(pr.get('work_type_label', '合并 PR'))}</span>
                <small>{esc((pr.get('closed_at') or pr.get('updated_at') or '')[:10])}</small>
              </div>
              <h3>{link(pr.get("url", ""), pr.get("title", ""))}</h3>
              <p>{link(f"https://github.com/{pr.get('repo', '')}", pr.get("repo", ""))} · PR #{esc(pr.get("number", ""))}</p>
            </article>
            """
        )
    return '<div class="pr-card-grid">' + "\n".join(items) + "</div>"


def render_growth_narrative(portrait: dict[str, Any]) -> str:
    lines = portrait.get("growth_narrative", [])
    if not lines:
        return '<p class="empty">暂无足够数据生成成长叙事。</p>'
    return "<ul class=\"narrative-list\">" + "".join(f"<li>{esc(line)}</li>" for line in lines) + "</ul>"


def parse_day(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def week_label(day: dt.date) -> str:
    monday = day - dt.timedelta(days=day.weekday())
    return f"{monday.month}/{monday.day}"


def render_pr_flow(metrics: dict[str, int]) -> str:
    rows = [
        ("prs_created", "创建 PR", metrics.get("prs_created", 0), "需求进入交付漏斗", "flow-blue"),
        ("prs_merged", "合并 PR", metrics.get("prs_merged", 0), "已进入主干或目标分支", "flow-green"),
        ("prs_reviewed", "Review 参与 PR", metrics.get("prs_reviewed", 0), "协作与质量把关", "flow-violet"),
        ("issues_closed_related", "相关关闭 Issue", metrics.get("issues_closed_related", 0), "问题跟进参与", "flow-amber"),
    ]
    max_value = max([value for _, _, value, _, _ in rows] + [1])
    parts = []
    for key, label, value, caption, tone in rows:
        width = max(3, round(value / max_value * 100))
        parts.append(
            f"""
            <div class="flow-row flow-row-{esc(key)}">
              <div>
                <strong>{esc(label)}</strong>
                <span>{esc(caption)}</span>
              </div>
              <div class="flow-track"><i class="{esc(tone)}" style="width:{width}%"></i></div>
              <b>{esc(value)}</b>
            </div>
            """
        )
    return '<div class="flow-chart">' + "\n".join(parts) + "</div>"


def render_weekly_activity(summary: dict[str, Any]) -> str:
    start = parse_date(summary["start"])
    end = parse_date(summary["end"])
    first_monday = start - dt.timedelta(days=start.weekday())
    weeks: list[dt.date] = []
    cursor = first_monday
    while cursor <= end:
        weeks.append(cursor)
        cursor += dt.timedelta(days=7)
    buckets: dict[dt.date, dict[str, int]] = {
        monday: {"commits": 0, "merged": 0, "reviewed": 0, "issues": 0}
        for monday in weeks
    }

    def add_event(day: dt.date | None, key: str) -> None:
        if not day or day < start or day > end:
            return
        monday = day - dt.timedelta(days=day.weekday())
        if monday in buckets:
            buckets[monday][key] += 1

    for item in summary.get("commits", []):
        add_event(parse_day(item.get("authored_at")), "commits")
    for item in summary.get("prs", {}).get("merged", []):
        add_event(parse_day(item.get("closed_at") or item.get("updated_at")), "merged")
    for item in summary.get("prs", {}).get("reviewed", []):
        add_event(parse_day(item.get("updated_at") or item.get("closed_at")), "reviewed")
    for item in summary.get("issues", {}).get("closed_related", []):
        add_event(parse_day(item.get("closed_at") or item.get("updated_at")), "issues")

    scores = []
    for monday in weeks:
        item = buckets[monday]
        scores.append(item["commits"] + item["merged"] * 4 + item["reviewed"] * 2 + item["issues"] * 2)
    max_score = max(scores + [1])
    bars = []
    for monday, score in zip(weeks, scores, strict=False):
        item = buckets[monday]
        height = max(5, round(score / max_score * 100))
        title = f"{week_label(monday)}：commit {item['commits']}，合并 PR {item['merged']}，review PR {item['reviewed']}，相关 issue {item['issues']}"
        bars.append(
            f"""
            <div class="week-bar" title="{esc(title)}">
              <i style="height:{height}%"></i>
              <span>{esc(week_label(monday))}</span>
            </div>
            """
        )
    return '<div class="week-chart" aria-label="周度活动节奏">' + "\n".join(bars) + "</div>"


def render_repo_heatmap(rows: list[dict[str, Any]]) -> str:
    selected = rows[:8]
    if not selected:
        return '<p class="empty">没有仓库活动数据。</p>'
    columns = [
        ("commits", "Commit"),
        ("prs_created", "创建 PR"),
        ("prs_merged", "合并 PR"),
        ("prs_reviewed", "Review PR"),
        ("issues_closed_related", "相关 Issue"),
    ]
    max_by_column = {
        key: max([int(row.get(key, 0)) for row in selected] + [1])
        for key, _ in columns
    }
    head = "".join(f'<span class="heat-head">{esc(label)}</span>' for _, label in columns)
    body = []
    for row in selected:
        cells = []
        for key, _ in columns:
            value = int(row.get(key, 0))
            opacity = 0.10 + (value / max_by_column[key] * 0.72 if value else 0)
            cells.append(
                f'<span class="heat-cell" style="background:rgba(38, 86, 217, {opacity:.2f})">{esc(value)}</span>'
            )
        body.append(
            f"""
            <div class="heat-row">
              <div class="heat-repo">{link(f"https://github.com/{row['repo']}", row["repo"])}</div>
              {''.join(cells)}
            </div>
            """
        )
    return f"""
      <div class="repo-heatmap" aria-label="仓库贡献热力图">
        <div class="heat-row heat-row-head"><div></div>{head}</div>
        {"".join(body)}
      </div>
    """


def render_theme_treemap(portrait: dict[str, Any]) -> str:
    themes = portrait.get("themes", [])[:7]
    if not themes:
        return '<p class="empty">没有足够数据生成主题占比图。</p>'
    max_score = max([int(item.get("score", 0)) for item in themes] + [1])
    tiles = []
    for index, theme in enumerate(themes, start=1):
        score = int(theme.get("score", 0))
        basis = max(18, round(score / max_score * 42))
        tiles.append(
            f"""
            <article class="theme-tile theme-tile-{index}" style="flex-basis:{basis}%">
              <strong>{esc(theme.get('theme', ''))}</strong>
              <span>{esc(score)} 分</span>
              <small>{esc(theme.get('merged_prs', 0))} 合并 PR · {esc(theme.get('commits', 0))} commit</small>
            </article>
            """
        )
    return '<div class="theme-map" aria-label="主题占比图">' + "\n".join(tiles) + "</div>"


def render_engineering_outcomes(summary: dict[str, Any]) -> str:
    outcomes = summary.get("engineering_outcomes") or {}
    totals = outcomes.get("totals") or {}
    coverage = outcomes.get("coverage") or {}
    by_repo = outcomes.get("by_repo") or []
    areas = outcomes.get("code_areas") or []
    top_prs = outcomes.get("top_code_prs") or []

    cards = [
        ("功能点", totals.get("feature_points", 0), "按 merged PR 标题/标签归类"),
        ("Bug 修复", totals.get("bug_fixes", 0), "fix/bug/regression 等线索"),
        ("Bug-like issue", totals.get("bug_like_closed_issues", 0), "相关关闭 issue 辅助口径"),
        ("新增行", totals.get("additions", 0), "PR additions"),
        ("删除行", totals.get("deletions", 0), "PR deletions"),
        ("变更文件", totals.get("changed_files", 0), "PR changed_files"),
    ]
    card_html = "".join(
        f"""
        <div class="outcome-card">
          <strong>{esc(value)}</strong>
          <span>{esc(label)}</span>
          <small>{esc(hint)}</small>
        </div>
        """
        for label, value, hint in cards
    )

    repo_rows = []
    max_repo = max([int(row.get("feature_points", 0)) + int(row.get("bug_fixes", 0)) for row in by_repo[:10]] + [1])
    for row in by_repo[:10]:
        value = int(row.get("feature_points", 0)) + int(row.get("bug_fixes", 0))
        width = max(4, round(value / max_repo * 100))
        repo_rows.append(
            f"""
            <div class="bar-row repo-row">
              <div class="bar-name"><strong>{link(f"https://github.com/{row.get('repo', '')}", row.get("repo", ""))}</strong><small>功能 {esc(row.get('feature_points', 0))} · Bug {esc(row.get('bug_fixes', 0))} · +{esc(row.get('additions', 0))} / -{esc(row.get('deletions', 0))}</small></div>
              <div class="bar-track"><div class="bar-fill outcome-fill" style="width:{width}%"></div></div>
              <div class="bar-value">{esc(value)}</div>
            </div>
            """
        )

    area_rows = []
    max_area = max([int(row.get("additions", 0)) + int(row.get("deletions", 0)) for row in areas] + [1])
    for row in areas[:8]:
        value = int(row.get("additions", 0)) + int(row.get("deletions", 0))
        width = max(4, round(value / max_area * 100))
        area_rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-name"><strong>{esc(row.get('label') or row.get('key'))}</strong><small>{esc(row.get('files', 0))} 个文件</small></div>
              <div class="bar-track"><div class="bar-fill" style="width:{width}%; background:{esc(row.get('color', '#2656d9'))}"></div></div>
              <div class="bar-value">+{esc(row.get('additions', 0))}<small>-{esc(row.get('deletions', 0))}</small></div>
            </div>
            """
        )

    pr_rows = [
        [
            link(row.get("url", ""), f"#{row.get('number')}"),
            link(f"https://github.com/{row.get('repo', '')}", row.get("repo", "")),
            esc(row.get("title", "")),
            esc(f"+{row.get('additions', 0)} / -{row.get('deletions', 0)}"),
            esc(row.get("changed_files", 0)),
        ]
        for row in top_prs[:12]
    ]

    coverage_line = (
        f"代码行统计覆盖 {coverage.get('code_stats_succeeded', 0)} / {coverage.get('merged_prs_total', 0)} 个合并 PR；"
        "不包含直接 commit 的逐提交行数。"
    )
    return f"""
      <div class="outcome-grid">{card_html}</div>
      <div class="chart-grid" style="margin-top:16px;">
        <div class="panel-lite">
          <h3>功能点 / Bug 修复按仓库</h3>
          <div class="bar-chart">{''.join(repo_rows) or '<p class="empty">暂无 outcome 拆解。</p>'}</div>
        </div>
        <div class="panel-lite">
          <h3>代码区域分布</h3>
          <div class="bar-chart">{''.join(area_rows) or '<p class="empty">暂无代码区域拆解。</p>'}</div>
        </div>
      </div>
      <h3 style="margin-top:18px;">PR 代码变更 Top</h3>
      {render_table(["PR", "仓库", "标题", "新增/删除", "文件"], pr_rows, "暂无 PR 代码变更排行。")}
      <div class="callout">{esc(coverage_line)} 功能点和 Bug 修复是确定性归类，关键述职口径建议点击 PR 复核。</div>
    """


def render_project_cards(projects: list[dict[str, Any]], empty: str, limit: int = 8) -> str:
    selected = projects[:limit]
    if not selected:
        return f'<p class="empty">{esc(empty)}</p>'
    cards = []
    for project in selected:
        badges = []
        if project.get("is_new_repo"):
            badges.append("新建仓库")
        elif project.get("is_newly_active"):
            badges.append("新启动")
        badges.extend(project.get("interesting_work") or [])
        languages = "、".join(f"{item.get('language')} {item.get('pct')}%" for item in project.get("top_languages", [])[:2]) or "语言未知"
        pr_items = []
        for pr in project.get("representative_prs", [])[:3]:
            pr_items.append(
                f"""
                <li>
                  {link(pr.get("url", ""), f"#{pr.get('number')}")}
                  <span>{esc(pr.get("title", ""))}</span>
                </li>
                """
            )
        pr_html = f'<ul class="project-prs">{"".join(pr_items)}</ul>' if pr_items else '<p class="project-empty">该项目主要由 commit/issue 线索识别，暂无代表性 PR。</p>'
        stats = [
            f"{project.get('feature_points', 0)} 功能",
            f"{project.get('bug_fixes', 0)} 修复",
            f"{project.get('merged_prs', 0)} 合并 PR",
            f"{project.get('commits', 0)} commit",
        ]
        cards.append(
            f"""
            <article class="project-card">
              <div class="project-head">
                <div>
                  <h3>{link(project.get("url", ""), project.get("repo", ""))}</h3>
                  <small>{esc(project.get("theme", ""))} · {esc(languages)}</small>
                </div>
                <strong>{esc(project.get("score", 0))}</strong>
              </div>
              <p>{esc(project.get("purpose", ""))}</p>
              <div class="project-badges">{''.join(f'<span>{esc(badge)}</span>' for badge in badges[:5])}</div>
              <div class="project-stats">{''.join(f'<b>{esc(item)}</b>' for item in stats)}</div>
              <div class="project-narrative">{esc(project.get("narrative", ""))}</div>
              {pr_html}
            </article>
            """
        )
    return '<div class="project-grid">' + "\n".join(cards) + "</div>"


def render_project_portfolio(summary: dict[str, Any]) -> str:
    portfolio = summary.get("project_portfolio") or {}
    totals = portfolio.get("totals") or {}
    interesting = portfolio.get("interesting_projects") or []
    method = portfolio.get("method") or "通过仓库元数据和季度活动识别项目画像。"
    overview = [
        ("项目画像", totals.get("projects", 0), "活跃/新建/新启动仓库"),
        ("新建仓库", totals.get("new_repositories", 0), "created_at 在本季度"),
        ("新启动项目", totals.get("newly_active_projects", 0), "上季未活跃，本季出现活动"),
        ("重点线索", totals.get("interesting_projects", 0), "可用于述职展开的主题"),
    ]
    overview_html = "".join(
        f"""
        <div class="outcome-card">
          <strong>{esc(value)}</strong>
          <span>{esc(label)}</span>
          <small>{esc(hint)}</small>
        </div>
        """
        for label, value, hint in overview
    )
    return f"""
      <div class="outcome-grid project-overview">{overview_html}</div>
      <div class="section-head" style="margin-top:18px;">
        <h3>新建仓库</h3>
        <p class="section-subtitle">真正按 GitHub repo created_at 落在本季度识别。</p>
      </div>
      {render_project_cards(portfolio.get("new_repositories") or [], "本季度没有识别到新建仓库。", 6)}
      <div class="section-head" style="margin-top:18px;">
        <h3>本季度新启动 / 重新活跃</h3>
        <p class="section-subtitle">上季度没有进入活跃仓库集合，本季度出现 commit、PR、issue 或 review 证据。</p>
      </div>
      {render_project_cards(portfolio.get("newly_active_projects") or [], "本季度没有识别到新启动项目。", 8)}
      <div class="section-head" style="margin-top:18px;">
        <h3>重点工作线索</h3>
        <p class="section-subtitle">根据 PR/commit 标题里的 IDE、离线交付、权限链路、测试质量等主题抽取。</p>
      </div>
      {render_project_cards(interesting, "暂无可稳定抽取的重点工作线索。", 8)}
      <div class="callout">{esc(method)} 这不是产品立项系统，关键项目定义建议结合 README 和 PR 链接复核。</div>
    """


def render_html(summary: dict[str, Any]) -> str:
    metrics = summary["metrics"]
    comparison = summary.get("comparison", {})
    portrait = summary.get("contribution_portrait", {})
    repo_rows = [
        [
            link(f"https://github.com/{row['repo']}", row["repo"]),
            esc(row.get("commits", 0)),
            esc(row.get("prs_created", 0)),
            esc(row.get("prs_merged", 0)),
            esc(row.get("prs_reviewed", 0)),
            esc(row.get("issues_created", 0)),
            esc(row.get("issues_closed_related", 0)),
        ]
        for row in summary["top_repos"]
    ]
    merged_rows = [
        [
            link(row["url"], f"#{row['number']}"),
            link(f"https://github.com/{row['repo']}", row["repo"]),
            esc(row["title"]),
            esc((row.get("closed_at") or row.get("updated_at") or "")[:10]),
        ]
        for row in summary["prs"]["merged"][:50]
    ]
    created_pr_rows = [
        [
            link(row["url"], f"#{row['number']}"),
            link(f"https://github.com/{row['repo']}", row["repo"]),
            esc(row["title"]),
            esc((row.get("created_at") or "")[:10]),
        ]
        for row in summary["prs"]["created"][:50]
    ]
    issue_rows = [
        [
            link(row["url"], f"#{row['number']}"),
            link(f"https://github.com/{row['repo']}", row["repo"]),
            esc(row["title"]),
            esc((row.get("closed_at") or row.get("updated_at") or "")[:10]),
        ]
        for row in summary["issues"]["closed_related"][:50]
    ]
    commit_rows = [
        [
            link(row["url"], row["sha"]),
            link(f"https://github.com/{row['repo']}", row["repo"]),
            esc(row["title"]),
            esc((row.get("authored_at") or "")[:10]),
        ]
        for row in summary["commits"][:80]
    ]
    release_rows = [
        [
            link(row.get("url") or "", row.get("tag") or row.get("name") or ""),
            link(f"https://github.com/{row['repo']}", row["repo"]),
            esc((row.get("published_at") or "")[:10]),
        ]
        for row in summary["releases"][:50]
    ]

    cards = "\n".join(
        [
            render_metric_card("active_repos", "活跃仓库", metrics["active_repos"], "任一 GitHub 活动去重", comparison.get("active_repos")),
            render_metric_card("commits", "Commit", metrics["commits"], "authored commits", comparison.get("commits")),
            render_metric_card("prs_created", "创建 PR", metrics["prs_created"], "author + created", comparison.get("prs_created")),
            render_metric_card("prs_merged", "合并 PR", metrics["prs_merged"], "author + merged-at", comparison.get("prs_merged")),
            render_metric_card("prs_reviewed", "Review 参与 PR", metrics["prs_reviewed"], "reviewed-by + updated", comparison.get("prs_reviewed")),
            render_metric_card("issues_created", "创建 Issue", metrics["issues_created"], "author + created", comparison.get("issues_created")),
            render_metric_card("issues_closed_related", "相关关闭 Issue", metrics["issues_closed_related"], "involves + closed", comparison.get("issues_closed_related")),
            render_metric_card("releases", "Release", metrics["releases"], "指定 repo 的 releases", comparison.get("releases")),
        ]
    )

    scope_bits = []
    if summary["scope"]["repos"]:
        scope_bits.append("Repos: " + ", ".join(summary["scope"]["repos"]))
    if summary["scope"]["owners"]:
        scope_bits.append("Owners: " + ", ".join(summary["scope"]["owners"]))
    if not scope_bits:
        scope_bits.append("Global GitHub search")

    previous = summary.get("previous_period") or {}
    previous_label = previous.get("period_label") or "上季度"
    current_window = f"{summary['start']} 至 {summary['end']}"
    previous_window = f"{previous.get('start', '')} 至 {previous.get('end', '')}"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(summary['period_label'])} GitHub 开发面板</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #111827;
      --muted: #667085;
      --quiet: #8a94a6;
      --line: #d8dee8;
      --line-soft: #e8edf4;
      --canvas: #f4f1ea;
      --panel: #fffdfa;
      --panel-soft: #f8f5ee;
      --paper: #ffffff;
      --blue: #2656d9;
      --blue-deep: #123a8f;
      --cyan: #0b7f8c;
      --green: #13845b;
      --amber: #b06b1d;
      --red: #bf3f42;
      --violet: #6a4bc3;
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
    .page {{ max-width: 1280px; margin: 0 auto; padding: 24px 22px 64px; }}
    a {{ color: var(--blue-deep); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .hero {{
      position: relative;
      overflow: hidden;
      padding: 22px 26px 22px;
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
      background: linear-gradient(180deg, var(--blue), var(--cyan), var(--green));
    }}
    .hero-top {{ position: relative; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 18px; align-items: start; }}
    .kicker {{ margin: 0 0 8px; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }}
    h1 {{ margin: 0; font-size: clamp(32px, 4vw, 58px); line-height: .98; letter-spacing: 0; text-wrap: balance; }}
    .hero .meta {{ margin-top: 10px; max-width: 760px; color: #4b5565; font-size: 14px; }}
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
      grid-template-columns: repeat(8, minmax(0, 1fr));
      gap: 0;
      margin-top: 18px;
      border-top: 1px solid var(--line);
      border-left: 1px solid var(--line);
      background: var(--paper);
    }}
    .metric {{ min-height: 122px; padding: 14px 14px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }}
    .metric-value {{ font-size: clamp(28px, 3vw, 42px); font-weight: 820; color: var(--ink); line-height: 1; }}
    .metric-label {{ margin-top: 9px; font-weight: 720; }}
    .metric-hint {{ margin-top: 3px; color: var(--muted); font-size: 12px; line-height: 1.45; }}
    .metric-delta {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 13px; font-size: 12px; font-weight: 720; }}
    .metric-delta span {{ display: inline-flex; align-items: center; min-height: 22px; padding: 3px 6px; border-radius: 999px; }}
    .delta-up span {{ color: #0f6b43; background: #e3f4ea; }}
    .delta-down span {{ color: #9f2f2f; background: #fde9e9; }}
    .delta-flat span {{ color: #526071; background: #edf1f6; }}
    h2 {{ margin: 0; font-size: 22px; line-height: 1.15; letter-spacing: 0; text-wrap: balance; }}
    h3 {{ margin: 0 0 12px; font-size: 15px; line-height: 1.35; letter-spacing: 0; }}
    .meta {{ color: var(--muted); font-size: 14px; }}
    section {{
      margin-top: 16px;
      padding: 22px;
      background: rgba(255, 253, 250, 0.92);
      border: 1px solid rgba(17, 24, 39, 0.10);
      border-radius: var(--radius);
      box-shadow: var(--shadow-sm);
    }}
    .section-head {{ display: flex; justify-content: space-between; gap: 16px; align-items: baseline; flex-wrap: wrap; margin-bottom: 18px; }}
    .section-subtitle {{ color: var(--muted); font-size: 14px; margin: 0; max-width: 520px; }}
    .leader-grid {{ display: grid; grid-template-columns: minmax(300px, 0.85fr) minmax(420px, 1.15fr); gap: 16px; }}
    .panel-lite {{ padding: 18px; background: var(--panel-soft); border: 1px solid var(--line); border-radius: var(--radius); }}
    .insights {{ margin: 0; padding-left: 20px; }}
    .insights li {{ margin: 7px 0; }}
    .chart-lab {{ display: grid; grid-template-columns: minmax(380px, 1.08fr) minmax(320px, .92fr); gap: 16px; align-items: stretch; }}
    .chart-stack {{ display: grid; gap: 16px; }}
    .wide-card {{ min-height: 100%; }}
    .flow-chart {{ display: grid; gap: 13px; }}
    .flow-row {{ display: grid; grid-template-columns: minmax(120px, .58fr) minmax(160px, 1fr) 54px; gap: 12px; align-items: center; }}
    .flow-row strong {{ display: block; font-size: 14px; }}
    .flow-row span {{ display: block; color: var(--muted); font-size: 12px; line-height: 1.35; }}
    .flow-track {{ height: 14px; background: #e5eaf2; border-radius: 999px; overflow: hidden; }}
    .flow-track i {{ display: block; height: 100%; border-radius: 999px; }}
    .flow-blue {{ background: var(--blue); }}
    .flow-green {{ background: var(--green); }}
    .flow-violet {{ background: var(--violet); }}
    .flow-amber {{ background: var(--amber); }}
    .flow-row b {{ text-align: right; font-size: 18px; }}
    .week-chart {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(34px, 1fr)); gap: 8px; height: 172px; align-items: end; padding: 6px 0 0; }}
    .week-bar {{ min-width: 0; height: 100%; display: grid; grid-template-rows: 1fr auto; gap: 7px; align-items: end; }}
    .week-bar i {{ display: block; width: 100%; min-height: 5px; background: linear-gradient(180deg, var(--blue), var(--cyan)); border-radius: 6px 6px 2px 2px; }}
    .week-bar span {{ color: var(--quiet); font-size: 10px; text-align: center; white-space: nowrap; }}
    .theme-map {{ display: flex; flex-wrap: wrap; gap: 8px; align-content: stretch; min-height: 230px; }}
    .theme-tile {{ flex-grow: 1; min-width: 150px; padding: 14px; border-radius: var(--radius); color: white; background: #253858; display: flex; flex-direction: column; justify-content: space-between; gap: 10px; }}
    .theme-tile strong {{ font-size: 15px; line-height: 1.3; }}
    .theme-tile span {{ font-size: 24px; font-weight: 820; line-height: 1; }}
    .theme-tile small {{ color: rgba(255,255,255,.78); line-height: 1.35; }}
    .theme-tile-1 {{ background: #173a75; }}
    .theme-tile-2 {{ background: #166470; }}
    .theme-tile-3 {{ background: #245b48; }}
    .theme-tile-4 {{ background: #6c4a18; }}
    .theme-tile-5 {{ background: #513b8c; }}
    .theme-tile-6 {{ background: #7a3340; }}
    .theme-tile-7 {{ background: #3e4a5e; }}
    .repo-heatmap {{ overflow-x: auto; }}
    .heat-row {{ min-width: 760px; display: grid; grid-template-columns: minmax(220px, 1.4fr) repeat(5, minmax(92px, .8fr)); gap: 6px; align-items: center; margin-bottom: 6px; }}
    .heat-row-head {{ color: var(--muted); font-size: 12px; }}
    .heat-repo {{ overflow-wrap: anywhere; font-size: 13px; }}
    .heat-cell, .heat-head {{ min-height: 36px; display: flex; align-items: center; justify-content: flex-end; padding: 6px 8px; border-radius: 6px; font-weight: 720; }}
    .heat-head {{ justify-content: flex-end; min-height: auto; padding-top: 0; padding-bottom: 0; font-weight: 650; }}
    .heat-cell {{ color: #0d2358; }}
    .compare-chart {{ display: grid; gap: 13px; }}
    .compare-row {{ display: grid; grid-template-columns: 112px 1fr 100px; gap: 13px; align-items: center; }}
    .compare-label {{ font-weight: 720; }}
    .compare-bars {{ display: grid; gap: 5px; }}
    .compare-line {{ display: grid; grid-template-columns: 50px 1fr 52px; gap: 8px; align-items: center; color: var(--muted); font-size: 12px; }}
    .compare-line div {{ height: 9px; background: #e5eaf2; border-radius: 999px; overflow: hidden; }}
    .compare-line i {{ display: block; height: 100%; border-radius: 999px; }}
    .compare-line .now {{ background: var(--blue); }}
    .compare-line .prev {{ background: #9aa8bc; }}
    .compare-line strong {{ color: var(--ink); text-align: right; }}
    .compare-change {{ width: fit-content; padding: 5px 8px; border-radius: 999px; font-size: 12px; font-weight: 720; justify-self: end; }}
    .bar-chart {{ display: grid; gap: 10px; }}
    .bar-row {{ display: grid; grid-template-columns: minmax(150px, 230px) 1fr 48px; gap: 12px; align-items: center; }}
    .bar-name {{ min-width: 0; overflow-wrap: anywhere; font-size: 13px; }}
    .bar-track {{ height: 12px; background: #e5eaf2; border-radius: 999px; overflow: hidden; }}
    .bar-fill {{ height: 100%; background: linear-gradient(90deg, var(--blue), var(--cyan)); border-radius: 999px; }}
    .outcome-fill {{ background: linear-gradient(90deg, var(--green), var(--blue)); }}
    .bar-value {{ text-align: right; font-weight: 720; }}
    .bar-value small {{ display: block; color: var(--muted); font-size: 11px; line-height: 1.15; }}
    .mix-chart {{ display: grid; gap: 14px; }}
    .mix-bar {{ display: flex; height: 24px; overflow: hidden; border-radius: 999px; background: #e5eaf2; }}
    .mix-segment {{ min-width: 2px; }}
    .mix-legend {{ display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }}
    .mix-legend li {{ display: grid; grid-template-columns: 12px 1fr auto; gap: 8px; align-items: center; font-size: 14px; }}
    .mix-legend i {{ width: 12px; height: 12px; border-radius: 999px; }}
    .mix-legend strong {{ text-align: right; }}
    .outcome-grid {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }}
    .outcome-card {{ min-height: 104px; padding: 13px; background: var(--paper); border: 1px solid var(--line-soft); border-radius: var(--radius); box-shadow: 0 1px 2px rgba(17,24,39,.05); }}
    .outcome-card strong {{ display: block; font-size: 28px; line-height: 1; }}
    .outcome-card span {{ display: block; margin-top: 8px; font-weight: 720; }}
    .outcome-card small {{ display: block; margin-top: 5px; color: var(--muted); font-size: 11px; line-height: 1.35; }}
    .project-overview {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
    .portrait-layout {{ display: grid; grid-template-columns: minmax(0, 1.28fr) minmax(300px, .72fr); gap: 16px; }}
    .theme-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px; }}
    .theme-card {{ min-height: 214px; padding: 15px; background: var(--paper); border: 1px solid var(--line-soft); border-radius: var(--radius); box-shadow: 0 1px 2px rgba(17,24,39,.05); }}
    .theme-card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; }}
    .theme-card h3, .pr-card h3 {{ margin: 0; font-size: 15px; line-height: 1.35; }}
    .theme-card-head span {{ min-width: 34px; text-align: right; color: var(--blue); font-weight: 820; }}
    .theme-card p {{ margin: 8px 0 0; color: #445065; font-size: 13px; line-height: 1.6; }}
    .theme-meta {{ margin-top: 10px; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }}
    .theme-stats {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }}
    .theme-stats b {{ padding: 4px 7px; background: var(--panel-soft); border: 1px solid var(--line); border-radius: 999px; font-size: 12px; }}
    .theme-prs {{ margin: 12px 0 0; padding-left: 18px; color: var(--muted); font-size: 12px; }}
    .theme-prs li {{ margin: 6px 0; }}
    .theme-prs span {{ color: var(--ink); }}
    .theme-empty {{ color: var(--muted); font-size: 12px; }}
    .type-chart {{ display: grid; gap: 11px; }}
    .type-row {{ display: grid; grid-template-columns: minmax(112px, .65fr) minmax(110px, 1fr); gap: 9px 12px; align-items: center; }}
    .type-label {{ display: flex; gap: 7px; align-items: center; font-weight: 720; font-size: 13px; }}
    .type-label i {{ width: 10px; height: 10px; border-radius: 999px; flex: 0 0 auto; }}
    .type-track {{ height: 10px; background: #e5eaf2; border-radius: 999px; overflow: hidden; }}
    .type-track span {{ display: block; height: 100%; border-radius: 999px; }}
    .type-detail {{ grid-column: 1 / -1; color: var(--muted); font-size: 12px; }}
    .narrative-list {{ margin: 0; padding-left: 19px; }}
    .narrative-list li {{ margin: 7px 0; }}
    .pr-card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(235px, 1fr)); gap: 10px; margin-top: 14px; }}
    .pr-card {{ padding: 14px; background: var(--paper); border: 1px solid var(--line-soft); border-radius: var(--radius); box-shadow: 0 1px 2px rgba(17,24,39,.05); }}
    .pr-card-top {{ display: flex; justify-content: space-between; gap: 10px; align-items: center; margin-bottom: 9px; }}
    .pr-card-top span {{ padding: 4px 7px; background: #e9efff; color: var(--blue-deep); border-radius: 999px; font-size: 12px; font-weight: 720; }}
    .pr-card-top small, .pr-card p {{ color: var(--muted); }}
    .pr-card p {{ margin: 9px 0 0; font-size: 12px; }}
    .project-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; }}
    .project-card {{ min-height: 264px; padding: 15px; background: var(--paper); border: 1px solid var(--line-soft); border-radius: var(--radius); box-shadow: 0 1px 2px rgba(17,24,39,.05); }}
    .project-head {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; align-items: start; }}
    .project-head h3 {{ margin: 0; font-size: 15px; line-height: 1.35; }}
    .project-head small {{ display: block; margin-top: 4px; color: var(--muted); font-size: 12px; line-height: 1.35; }}
    .project-head strong {{ color: var(--blue); font-size: 22px; line-height: 1; }}
    .project-card p {{ margin: 10px 0 0; color: #445065; font-size: 13px; line-height: 1.6; }}
    .project-badges, .project-stats {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }}
    .project-badges span {{ padding: 4px 7px; color: var(--blue-deep); background: #e9efff; border-radius: 999px; font-size: 12px; font-weight: 720; }}
    .project-stats b {{ padding: 4px 7px; background: var(--panel-soft); border: 1px solid var(--line); border-radius: 999px; font-size: 12px; }}
    .project-narrative {{ margin-top: 10px; color: #344054; font-size: 12px; line-height: 1.55; }}
    .project-prs {{ margin: 10px 0 0; padding-left: 18px; color: var(--muted); font-size: 12px; }}
    .project-prs li {{ margin: 6px 0; }}
    .project-prs span {{ color: var(--ink); }}
    .project-empty {{ color: var(--muted); font-size: 12px; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: var(--radius); background: var(--paper); }}
    table {{ width: 100%; border-collapse: collapse; min-width: 720px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line-soft); text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: var(--panel-soft); font-size: 12px; color: #475467; font-weight: 720; }}
    tr:last-child td {{ border-bottom: 0; }}
    .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
    .chart-grid {{ display: grid; grid-template-columns: minmax(320px, 1.18fr) minmax(280px, .82fr); gap: 16px; }}
    .note, .empty {{ color: var(--muted); }}
    .callout {{ margin-top: 14px; padding: 12px 14px; background: #fff6e3; color: #65410f; border: 1px solid #efd49b; border-radius: 6px; }}
    ul {{ margin: 10px 0 0; padding-left: 20px; }}
    .footer-note {{ margin-top: 18px; color: var(--muted); font-size: 13px; }}
    @media (max-width: 980px) {{
      .metrics {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
      .outcome-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .project-overview {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .leader-grid, .chart-lab, .portrait-layout, .chart-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 640px) {{
      .page {{ padding: 14px 10px 36px; }}
      .hero, section {{ padding: 16px; }}
      .hero-top {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 29px; }}
      h2 {{ font-size: 19px; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .outcome-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .metric {{ min-height: 130px; padding: 13px; }}
      .metric-value {{ font-size: 29px; }}
      .compare-row {{ grid-template-columns: 1fr; }}
      .compare-change {{ justify-self: start; }}
      .bar-row {{ grid-template-columns: 1fr 1fr 44px; }}
      .flow-row {{ grid-template-columns: 1fr; }}
      .flow-row b {{ text-align: left; }}
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
          <p class="kicker">GitHub Quarterly Engineering Dashboard</p>
          <h1>{esc(summary['period_label'])} GitHub 开发面板</h1>
          <div class="meta">用户：{esc(summary['user'])} · 本季度：{esc(current_window)} · 对比：{esc(previous_label)}（{esc(previous_window)}）</div>
          <div class="meta">生成：{esc(summary['generated_at'])}</div>
        </div>
        <div class="scope-pill">{esc(' | '.join(scope_bits))}</div>
      </div>
      <div class="metrics">{cards}</div>
    </header>

    <section>
      <div class="section-head">
        <h2>增长与结构</h2>
        <p class="section-subtitle">把核心数字转成可扫读的趋势、漏斗、主题占比和仓库热力。</p>
      </div>
      <div class="chart-lab">
        <div class="panel-lite wide-card">
          <h3>周度活动节奏</h3>
          {render_weekly_activity(summary)}
        </div>
        <div class="chart-stack">
          <div class="panel-lite">
            <h3>PR 与协作漏斗</h3>
            {render_pr_flow(metrics)}
          </div>
          <div class="panel-lite">
            <h3>活动构成</h3>
            {render_activity_mix(metrics)}
          </div>
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>领导层摘要</h2>
        <p class="section-subtitle">把图表里的增长、交付和协作线索提炼成可汇报结论。</p>
      </div>
      <div class="leader-grid">
        <div class="panel-lite">
          <h3>可汇报结论</h3>
          {render_leadership_insights(summary)}
        </div>
        <div class="panel-lite">
          <h3>本季度 vs 上季度</h3>
          {render_comparison_bars(comparison)}
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>工程成果维度</h2>
        <p class="section-subtitle">按合并 PR 仔细归类功能点、Bug 修复和代码变更量，让季度汇报不只停留在 commit/PR 个数。</p>
      </div>
      {render_engineering_outcomes(summary)}
    </section>

    <section>
      <div class="section-head">
        <h2>项目组合与新方向</h2>
        <p class="section-subtitle">把这个季度创建/启动/推进的项目逐个讲清楚：项目做什么、证据在哪里、哪些工作值得展开。</p>
      </div>
      {render_project_portfolio(summary)}
    </section>

    <section>
      <div class="section-head">
        <h2>季度贡献画像</h2>
        <p class="section-subtitle">把 GitHub 活动翻译成投入方向、贡献类型和可点击证据。</p>
      </div>
      <div class="chart-lab">
        <div class="panel-lite wide-card">
          <h3>主题占比</h3>
          {render_theme_treemap(portrait)}
        </div>
        <div class="chart-stack">
          <div class="panel-lite">
            <h3>贡献类型</h3>
            {render_work_type_mix(portrait)}
          </div>
          <div class="panel-lite">
            <h3>成长叙事</h3>
            {render_growth_narrative(portrait)}
          </div>
        </div>
      </div>
      <div class="portrait-layout" style="margin-top: 16px;">
        <div>
          <h3>主要投入方向</h3>
          {render_theme_cards(portrait)}
        </div>
        <div>
          <h3>Top 仓库贡献强度</h3>
          <div class="panel-lite">{render_bar_chart(summary["top_repos"], "score", "仓库贡献强度")}</div>
        </div>
      </div>
      <h3 style="margin-top: 18px;">代表性合并 PR</h3>
      {render_representative_prs(portrait)}
      <div class="callout">贡献画像由仓库名、PR 标题前缀和关键词确定性推断，适合做述职线索；关键业务影响仍需要结合项目背景人工复核。</div>
    </section>

    <section>
      <div class="section-head">
        <h2>仓库热力</h2>
        <p class="section-subtitle">比普通表格更快看出主要仓库的投入结构，深色表示该列相对更高。</p>
      </div>
      {render_repo_heatmap(summary["top_repos"])}
    </section>

    <section>
      <div class="section-head">
        <h2>仓库明细</h2>
        <p class="section-subtitle">保留完整可追溯的仓库聚合数据。</p>
      </div>
      {render_table(["仓库", "Commit", "创建 PR", "合并 PR", "Review PR", "创建 Issue", "相关关闭 Issue"], repo_rows, "没有仓库活动数据。")}
    </section>

    <section>
      <div class="section-head">
        <h2>PR 面板</h2>
        <p class="section-subtitle">合并 PR 表示已进入主干或目标分支的交付记录。</p>
      </div>
      <div class="grid-2">
        <div>
          <h3>合并 PR</h3>
          {render_table(["PR", "仓库", "标题", "日期"], merged_rows, "本范围内没有找到合并 PR。")}
        </div>
        <div>
          <h3>创建 PR</h3>
          {render_table(["PR", "仓库", "标题", "日期"], created_pr_rows, "本范围内没有找到创建 PR。")}
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>Issue 面板</h2>
        <p class="section-subtitle">这里使用“相关关闭 issue”口径，避免夸大成亲自解决数。</p>
      </div>
      {render_table(["Issue", "仓库", "标题", "关闭/更新日期"], issue_rows, "本范围内没有找到相关关闭 issue。")}
    </section>

    <section>
      <div class="section-head">
        <h2>Commit 面板</h2>
        <p class="section-subtitle">展示 authored commit 的代表性样本。</p>
      </div>
      {render_table(["Commit", "仓库", "标题", "日期"], commit_rows, "本范围内没有找到 commit。")}
    </section>

    <section>
      <div class="section-head">
        <h2>Release 面板</h2>
        <p class="section-subtitle">Release 当前只统计显式传入仓库的发布记录。</p>
      </div>
      {render_table(["Release", "仓库", "发布日期"], release_rows, "没有 release 数据。只有明确传入 --repo 时才统计 release。")}
    </section>

    <section>
      <h2>统计口径</h2>
      <ul>
        <li>Commit：搜索 authored commits，按 author-date 过滤季度范围。</li>
        <li>创建 PR：PR author 为用户，created 在季度范围内。</li>
        <li>合并 PR：PR author 为用户，merged-at 在季度范围内。</li>
        <li>Review 参与 PR：reviewed-by 为用户，updated 在季度范围内；这是参与过 review 的 PR 数，不等同于 review 次数。</li>
        <li>创建 Issue：issue author 为用户，created 在季度范围内。</li>
        <li>相关关闭 Issue：issue involves 用户，closed 在季度范围内；这是相关关闭 issue，不直接等同于用户亲自解决的问题。</li>
        <li>Release：仅对明确传入的仓库调用 releases API 后按发布时间过滤。</li>
      </ul>
      <div class="callout">GitHub 搜索结果可能受权限、搜索索引和 --limit 限制影响。面板适合做季度复盘证据入口，重要结论应点击链接复核。</div>
      <p class="footer-note">本面板保持 GitHub 独立口径。飞书、会议、聊天、文档等协作证据应由独立面板补充，不混入本页指标。</p>
    </section>
  </main>
</body>
</html>
"""


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    start = parse_date(args.start)
    end = parse_date(args.end)
    if start > end:
        raise ValueError("--start must be before --end")
    if args.previous_start or args.previous_end:
        if not (args.previous_start and args.previous_end):
            raise ValueError("--previous-start and --previous-end must be used together")
        previous_start = parse_date(args.previous_start)
        previous_end = parse_date(args.previous_end)
    else:
        previous_start, previous_end = previous_period_for(start, end)
    if previous_start > previous_end:
        raise ValueError("--previous-start must be before --previous-end")

    user = args.user or run_text(["gh", "api", "user", "--jq", ".login"])
    current = collect_period(user, start, end, args.repo, args.owner, args.limit)
    previous = collect_period(user, previous_start, previous_end, args.repo, args.owner, args.previous_limit or args.limit)
    recent_user_repos = [] if args.skip_project_portfolio else list_recent_user_repos(user, start, end)
    datasets = current["datasets"]
    releases = current["releases"]
    repo_metrics = current["repo_metrics"]
    top = current["top_repos"]
    metrics = current["metrics"]
    previous_metrics = previous["metrics"]

    summary = {
        "schema_version": 1,
        "kind": "quarterly-github-dashboard",
        "user": user,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "period_label": args.period_label or f"{start.isoformat()} - {end.isoformat()}",
        "generated_at": iso_now(),
        "scope": {"repos": args.repo, "owners": args.owner},
        "metrics": metrics,
        "previous_period": {
            "start": previous_start.isoformat(),
            "end": previous_end.isoformat(),
            "period_label": args.previous_period_label or f"{previous_start.isoformat()} - {previous_end.isoformat()}",
            "metrics": previous_metrics,
        },
        "comparison": compare_metrics(metrics, previous_metrics),
        "repo_metrics": repo_metrics,
        "top_repos": top,
        "prs": {
            "created": [pr_row(item) for item in datasets["prs_created"]],
            "merged": [pr_row(item) for item in datasets["prs_merged"]],
            "closed": [pr_row(item) for item in datasets["prs_closed"]],
            "reviewed": [pr_row(item) for item in datasets["prs_reviewed"]],
        },
        "issues": {
            "created": [issue_row(item) for item in datasets["issues_created"]],
            "closed_related": [issue_row(item) for item in datasets["issues_closed_related"]],
        },
        "commits": [commit_row(item) for item in datasets["commits"]],
        "releases": releases,
        "notes": [
            "issues_closed_related means issues involving the user that closed in range; verify before calling them personally solved issues.",
            "prs_reviewed counts PRs reviewed by the user, not individual review events.",
            "GitHub search can be affected by permissions, indexing, and limit caps.",
        ],
    }
    summary["engineering_outcomes"] = build_engineering_outcomes(summary, fetch_code_stats=not args.skip_code_stats)
    summary["top_repos"] = enrich_top_repos_with_outcomes(summary["top_repos"], summary["engineering_outcomes"])
    if not args.skip_project_portfolio:
        previous_summary = {
            "top_repos": previous["top_repos"],
            "metrics": previous["metrics"],
        }
        summary["project_portfolio"] = build_project_portfolio(summary, previous_summary=previous_summary, user_recent_repos=recent_user_repos)
    summary["contribution_portrait"] = build_contribution_portrait(summary)
    return summary


def write_outputs(summary: dict[str, Any], output_dir: Path, raw: dict[str, Any] | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "index.html").write_text(render_html(summary), encoding="utf-8")
    if raw is not None:
        raw_dir = output_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        (raw_dir / "summary-with-normalized-items.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", help="GitHub login. Defaults to the authenticated gh user.")
    parser.add_argument("--start", required=True, help="Start date, inclusive, YYYY-MM-DD.")
    parser.add_argument("--end", required=True, help="End date, inclusive, YYYY-MM-DD.")
    parser.add_argument("--period-label", help="Display label, for example '2026 Q2'.")
    parser.add_argument("--previous-start", help="Previous comparison start date, inclusive, YYYY-MM-DD. Defaults to previous quarter aligned with current range.")
    parser.add_argument("--previous-end", help="Previous comparison end date, inclusive, YYYY-MM-DD. Defaults to previous quarter aligned with current range.")
    parser.add_argument("--previous-period-label", help="Previous period display label, for example '2026 Q1'.")
    parser.add_argument("--repo", action="append", default=[], help="Limit to repo owner/name. Can be passed multiple times.")
    parser.add_argument("--owner", action="append", default=[], help="Limit to repository owner/org. Can be passed multiple times.")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum results per search query.")
    parser.add_argument("--previous-limit", type=int, help="Maximum results per previous-period search query. Defaults to --limit.")
    parser.add_argument("--skip-code-stats", action="store_true", help="Skip per-merged-PR GitHub API calls for additions/deletions/file breakdown.")
    parser.add_argument("--skip-project-portfolio", action="store_true", help="Skip repo metadata/README/language collection for project portfolio analysis.")
    parser.add_argument("--output-dir", required=True, help="Directory for index.html and summary.json.")
    parser.add_argument("--save-raw", action="store_true", help="Save normalized raw-ish data for audit.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        summary = build_summary(args)
        raw = summary if args.save_raw else None
        write_outputs(summary, Path(args.output_dir), raw)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(Path(args.output_dir, "index.html"))
    print(Path(args.output_dir, "summary.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
