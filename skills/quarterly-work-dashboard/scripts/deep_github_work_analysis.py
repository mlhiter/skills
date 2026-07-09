#!/usr/bin/env python3
"""Deep-read merged GitHub PRs into auditable quarterly work streams."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1

OUTCOME_LABELS = {
    "feature": "功能交付",
    "fix": "修复与稳定性",
    "operations": "工程治理",
    "architecture": "架构演进",
    "experience": "体验优化",
    "docs": "文档沉淀",
    "other": "其他交付",
}

FEATURE_WORDS = {
    "feat",
    "feature",
    "add",
    "support",
    "enable",
    "allow",
    "introduce",
    "create",
    "新增",
    "支持",
}

FIX_WORDS = {
    "fix",
    "bug",
    "restore",
    "prevent",
    "block",
    "stabilize",
    "correct",
    "tolerate",
    "rollback",
    "regression",
    "crash",
    "error",
    "修复",
}

STREAM_RULES: list[dict[str, Any]] = [
    {
        "id": "devbox-lifecycle-config",
        "title": "DevBox 生命周期、配置与元数据治理",
        "domain": "DevBox 研发体验",
        "value_category": "研发效率 / 稳定性",
        "repos": ["sealos-apps/devbox", "labring/sealos"],
        "keywords": [
            "devbox",
            "metadata",
            "postgres",
            "prisma",
            "config",
            "configmap",
            "crd",
            "v1alpha2",
            "dependencies",
            "patch",
            "pending",
            "deletion",
            "recreate",
            "external devboxes",
            "template",
            "custom scripts",
            "jwt",
        ],
        "user_problem": "开发环境创建、更新、删除和配置迁移链路一旦不稳定，会直接拖慢团队研发节奏。",
        "delivered": "推进 DevBox v2 元数据、配置清理、CRD 版本兼容和生命周期状态处理。",
        "business_value": "把云端开发环境从“能创建”推进到“可持续维护、可迁移、可恢复”。",
    },
    {
        "id": "devbox-ide-runtime",
        "title": "DevBox IDE、SSH、存储与运行时体验",
        "domain": "DevBox 研发体验",
        "value_category": "研发效率 / 用户体验",
        "repos": ["sealos-apps/devbox", "labring/sealos", "labring-actions/devbox-runtime"],
        "keywords": [
            "ide",
            "ssh",
            "sshgate",
            "port",
            "jetbrains",
            "vscode",
            "cursor",
            "runtime",
            "gpu",
            "image",
            "shared memory",
            "storage",
            "slider",
            "rw storage",
            "dropdown",
            "launch",
            "import command",
            "class name",
        ],
        "user_problem": "IDE 启动、端口、运行时镜像和资源配置问题会让开发者在真正写代码前被环境成本消耗。",
        "delivered": "补齐 IDE/SSH 启动前置检查、运行时配置、存储展示和镜像模板兼容能力。",
        "business_value": "降低开发者接入云端环境的等待和排障成本。",
    },
    {
        "id": "devbox-migration-cleanup",
        "title": "DevBox v2 迁移与旧链路收敛",
        "domain": "DevBox 研发体验",
        "value_category": "工程治理 / 交付能力",
        "repos": ["sealos-apps/devbox", "labring/sealos", "labring/sealos-pro"],
        "keywords": [
            "v2",
            "legacy devbox",
            "remove legacy",
            "remove frontend provider",
            "provider deploy configs",
            "helm",
            "service from go to nextjs",
            "base layer",
            "frontend v1",
            "runtime cache",
            "sealos-install",
        ],
        "user_problem": "新旧 DevBox 链路并存会抬高维护成本，并让私有化/升级路径更难解释。",
        "delivered": "迁移 v2 前端、移除旧 provider/extension、收敛 Helm 配置和安装工作流。",
        "business_value": "减少历史包袱，让后续 DevBox 能力迭代和交付更可控。",
    },
    {
        "id": "applaunchpad-domain-network",
        "title": "应用发布域名、证书与网络入口",
        "domain": "应用发布与网络域名",
        "value_category": "交付能力 / 稳定性",
        "repos": ["labring/sealos", "sealos-apps/admin"],
        "keywords": [
            "applaunchpad",
            "public domain",
            "custom domain",
            "domain",
            "dns",
            "certificate",
            "image port",
            "port flows",
            "truncation",
            "prefix",
            "dns labels",
            "http",
            "https",
        ],
        "user_problem": "应用公开访问依赖域名、证书、端口和 DNS 规则，任何细节错误都会变成部署失败或访问异常。",
        "delivered": "完善自定义域名证书管理、公共域名前缀校验、端口发现和协议兼容。",
        "business_value": "提升应用上线链路的成功率，减少部署后网络访问类问题。",
    },
    {
        "id": "admin-governance",
        "title": "Admin 租户、可用区与平台治理",
        "domain": "Admin 管理与租户治理",
        "value_category": "平台治理",
        "repos": ["sealos-apps/admin"],
        "keywords": [
            "tenant",
            "balance",
            "billing",
            "multi-az",
            "availability-zone",
            "provider",
            "gpu-management",
            "region",
            "user",
            "deactivation",
        ],
        "user_problem": "平台运营需要能看见租户状态、资源提供方和可用区结构，否则治理动作只能依赖人工排查。",
        "delivered": "补齐租户停用、余额/账单展示、多 AZ 管理、provider 下拉和 GPU 标签管理。",
        "business_value": "增强运营与平台治理能力，让管理后台能承接更多真实运营动作。",
    },
    {
        "id": "admin-assets-store",
        "title": "Admin 应用资产、模板与镜像同步",
        "domain": "Admin 管理与交付资产",
        "value_category": "交付能力 / 平台治理",
        "repos": ["sealos-apps/admin", "labring/sealos"],
        "keywords": [
            "app icon",
            "app-icon",
            "shared app ordering",
            "template-management",
            "app store",
            "registry-proxy",
            "image-sync",
            "cache object storage",
            "multiline cache",
            "gogs bootstrap",
            "bundled template",
            "workspace icon",
            "runtime icons",
            "bundled runtime",
            "icons",
        ],
        "user_problem": "应用商店、图标、模板仓库和镜像缓存链路不稳定，会影响平台应用交付的一致性。",
        "delivered": "建设 Git-backed 应用商店管理、应用图标管理、共享应用排序、镜像同步和 Gogs 模板启动。",
        "business_value": "把应用资产从零散配置推进到可管理、可同步、可复用的交付资产。",
    },
    {
        "id": "registry-delivery",
        "title": "Registry 上传下载、权限与离线模式",
        "domain": "Registry 镜像仓库",
        "value_category": "交付能力 / 稳定性",
        "repos": ["sealos-apps/registry"],
        "keywords": [
            "registry",
            "upload",
            "download",
            "progress",
            "offline app",
            "personal mode",
            "repository tree",
            "password",
            "tag delete",
            "auth",
            "tar",
            "async image upload",
            "staged progress",
            "download count",
            "tailwind",
        ],
        "user_problem": "镜像上传、下载、权限和离线应用管理是私有化交付的核心入口，反馈不清或权限不准会造成阻塞。",
        "delivered": "增强异步上传进度、下载进度、离线应用、个人模式权限、密码重建和仓库树体验。",
        "business_value": "提升镜像制品流转的可见性和稳定性，支撑私有化与离线交付。",
    },
    {
        "id": "kite-helm-ops",
        "title": "Kite / Helm / CRD 运维能力",
        "domain": "Kite / Helm / 运维能力",
        "value_category": "交付能力 / 可观测性",
        "repos": ["sealos-apps/kite"],
        "keywords": [
            "helm",
            "oci",
            "chart",
            "prometheus",
            "metric",
            "crd",
            "cr menu",
            "cr sidebar",
            "database",
            "resource history",
            "auth",
            "login",
            "namespace fallback",
            "cpu",
            "ai helm",
            "ops",
        ],
        "user_problem": "Helm、CRD、指标和数据库等运维能力不完整，会限制平台应用的可运维性。",
        "delivered": "补齐离线 OCI chart 源、内置 CR 菜单、Prometheus 查询兜底、数据库自动创建和资源历史。",
        "business_value": "增强应用交付后的运维闭环，让平台能力从安装走向可运行、可观测、可维护。",
    },
    {
        "id": "offline-desktop-agent",
        "title": "Offline Center 桌面离线资源与本地 agent",
        "domain": "平台应用与离线能力",
        "value_category": "离线交付 / 用户体验",
        "repos": ["sealos-apps/offline-center"],
        "keywords": ["offline", "offline-center", "local agent", "installer", "handoff", "resource workspace", "upgrade"],
        "user_problem": "离线安装和本地 agent 设置如果割裂，交付人员需要在多个工具之间人工串联。",
        "delivered": "建设离线资源工作区、本地 agent 设置和 installer handoff 升级流。",
        "business_value": "让离线交付链路更接近可操作的桌面工作台。",
    },
    {
        "id": "runtime-template-maintenance",
        "title": "DevBox runtime 镜像与模板兼容性",
        "domain": "运行时镜像与模板",
        "value_category": "稳定性 / 研发效率",
        "repos": ["labring-actions/devbox-runtime"],
        "keywords": [".net", "runtime", "go cache", "java decode", "arm", "content-length", "hello.sh", "express", "entrypoint"],
        "user_problem": "语言模板和 runtime 镜像问题会直接阻断开发环境启动或示例项目运行。",
        "delivered": "修复 Go/Java/ARM/Express/.NET 等 runtime 和模板兼容问题。",
        "business_value": "提升 DevBox 模板可用性，减少开发者从模板启动项目时的失败率。",
    },
    {
        "id": "install-tooling-quality",
        "title": "安装、测试集群与工作流工具",
        "domain": "安装与工程工具",
        "value_category": "工程治理 / 交付能力",
        "repos": ["labring/sealos-pro"],
        "keywords": ["sealos-install", "test-cluster-setup", "kubeconfig", "text plan", "workflow", "notes", "install"],
        "user_problem": "安装流程、测试集群配置和操作记录不清，会放大部署排障成本。",
        "delivered": "改造 sealos-install 文本计划流程，并补齐测试集群 kubeconfig 记录方式。",
        "business_value": "让交付和测试环境准备更可追踪，降低重复排障成本。",
    },
    {
        "id": "desktop-account-workspace",
        "title": "桌面账号、工作区与共享应用体验",
        "domain": "Sealos 桌面与账号体验",
        "value_category": "用户体验 / 平台治理",
        "repos": ["labring/sealos"],
        "keywords": [
            "desktop",
            "account",
            "workspace",
            "sign-in",
            "protocol",
            "shared app",
            "private workspace",
            "displaytype",
            "app ordering",
        ],
        "user_problem": "账号、工作区和共享应用入口是用户进入平台后的第一层体验，展示不一致会影响理解和操作。",
        "delivered": "更新账号与工作区设置、登录协议提示、私有工作区展示和共享应用排序。",
        "business_value": "提升平台桌面入口的一致性和可解释性。",
    },
    {
        "id": "platform-apps-ui-quality",
        "title": "平台应用本地开发与 UI 质量",
        "domain": "平台应用体验",
        "value_category": "用户体验 / 稳定性",
        "repos": ["sealos-apps/objectstorage", "sealos-apps/cronjob", "sealos-apps/maestro"],
        "keywords": ["objectstorage", "cronjob", "maestro", "local dev", "copy", "icon button", "validation", "logo"],
        "user_problem": "平台应用的基础交互和本地开发体验会影响应用维护效率和用户第一印象。",
        "delivered": "修复对象存储、定时任务和 Maestro 的本地开发、校验提示、按钮样式和品牌资产。",
        "business_value": "保持平台应用体验一致，降低小应用维护和调试成本。",
    },
    {
        "id": "security-auth-quality",
        "title": "认证、安全与兼容性修复",
        "domain": "安全与权限链路",
        "value_category": "安全 / 稳定性",
        "repos": ["labring/sealos", "sealos-apps/admin", "sealos-apps/kite", "sealos-apps/registry", "sealos-apps/devbox"],
        "keywords": [
            "jwt security",
            "auth bug",
            "auth",
            "login",
            "sdk status",
            "http and https",
            "bearer",
            "https",
            "http",
            "registry retag",
            "retag",
            "permission",
            "scope",
            "tag delete",
        ],
        "user_problem": "认证、安全和权限边界问题通常不是显眼功能，但会影响平台可信度和交付可控性。",
        "delivered": "修复 JWT、认证提示、HTTP/HTTPS 兼容、离线 tag 删除限制和 SDK 状态展示。",
        "business_value": "降低权限链路导致的平台不可用或误操作风险。",
    },
]

FALLBACK_STREAM_BY_REPO = {
    "sealos-apps/devbox": "devbox-lifecycle-config",
    "labring-actions/devbox-runtime": "runtime-template-maintenance",
    "sealos-apps/admin": "admin-assets-store",
    "sealos-apps/registry": "registry-delivery",
    "sealos-apps/kite": "kite-helm-ops",
    "sealos-apps/offline-center": "offline-desktop-agent",
    "sealos-apps/objectstorage": "platform-apps-ui-quality",
    "sealos-apps/cronjob": "platform-apps-ui-quality",
    "sealos-apps/maestro": "platform-apps-ui-quality",
    "labring/sealos-pro": "install-tooling-quality",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-summary", required=True, help="GitHub or combined quarterly summary.json")
    parser.add_argument("--output", required=True, help="Path to write deep_work_analysis.json")
    parser.add_argument("--limit", type=int, default=0, help="Only analyze first N merged PRs; 0 means all.")
    parser.add_argument("--concurrency", type=int, default=6, help="Concurrent gh api workers.")
    parser.add_argument("--keep-body", action="store_true", help="Keep full PR body in pr_details. Default stores excerpt only.")
    return parser.parse_args()


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def merged_prs_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    github = summary.get("github") if isinstance(summary.get("github"), dict) else summary
    prs = ((github.get("prs") or {}).get("merged") or []) if isinstance(github, dict) else []
    return [pr for pr in prs if isinstance(pr, dict) and pr.get("repo") and pr.get("number")]


def run_gh_api(endpoint: str, paginate: bool = False) -> tuple[Any | None, str]:
    cmd = ["gh", "api", endpoint]
    if paginate:
        cmd.extend(["--paginate", "--slurp"])
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if proc.returncode != 0:
        return None, proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
    text = proc.stdout.strip()
    if not text:
        return [], ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, str(exc)
    if paginate and isinstance(data, list) and data and all(isinstance(page, list) for page in data):
        flattened: list[Any] = []
        for page in data:
            flattened.extend(page)
        return flattened, ""
    return data, ""


def label_names(pr: dict[str, Any]) -> list[str]:
    labels = pr.get("labels") or []
    out = []
    for label in labels:
        if isinstance(label, dict):
            name = label.get("name")
        else:
            name = label
        if name:
            out.append(str(name))
    return out


def clean_subject(message: Any) -> str:
    if not isinstance(message, str):
        return ""
    return message.strip().splitlines()[0][:180]


def commit_subjects(commits: list[dict[str, Any]]) -> list[str]:
    subjects = []
    for commit in commits:
        data = commit.get("commit") if isinstance(commit, dict) else {}
        subject = clean_subject((data or {}).get("message") if isinstance(data, dict) else "")
        if subject:
            subjects.append(subject)
    return subjects


def conventional_scope(title: str) -> str:
    match = re.match(r"^\s*([a-zA-Z]+)(?:\(([^)]+)\))?!?\s*:\s*(.+)$", title)
    if not match:
        return ""
    return match.group(2) or match.group(1) or ""


def title_prefix(title: str) -> str:
    lowered = title.lower().strip()
    if ":" not in lowered:
        return ""
    prefix = lowered.split(":", 1)[0]
    return prefix.split("(", 1)[0].strip()


def normalized_intent(title: str) -> str:
    text = re.sub(r"^\s*[a-zA-Z]+(?:\([^)]+\))?!?\s*:\s*", "", title).strip()
    return text[:120] or title[:120]


def keyword_hit(text: str, words: set[str] | list[str]) -> bool:
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text.lower())
    split_words = set(normalized.split())
    for word in words:
        keyword = str(word).lower()
        if re.search(r"[\u4e00-\u9fff]", keyword):
            if keyword in normalized:
                return True
        elif " " in keyword:
            if keyword in f" {normalized} ":
                return True
        elif keyword in split_words:
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


def classify_outcome(title: str, labels: list[str], repo: str) -> str:
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
        return "fix"
    if prefix == "feat" or keyword_hit(text, feature_tokens):
        return "feature"
    return classify_work_type(title, repo)


def changes(file_item: dict[str, Any]) -> int:
    return int(file_item.get("additions") or 0) + int(file_item.get("deletions") or 0)


def top_files(files: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    rows = sorted([f for f in files if isinstance(f, dict)], key=changes, reverse=True)[:limit]
    out = []
    for item in rows:
        out.append(
            {
                "filename": item.get("filename") or "",
                "status": item.get("status") or "",
                "additions": int(item.get("additions") or 0),
                "deletions": int(item.get("deletions") or 0),
                "changes": changes(item),
            }
        )
    return out


def compact_file_paths(files: list[dict[str, Any]], limit: int = 40) -> list[str]:
    paths = [str(item.get("filename") or "") for item in files if isinstance(item, dict) and item.get("filename")]
    return paths[:limit]


def detail_text(pr: dict[str, Any], detail: dict[str, Any], files: list[dict[str, Any]], subjects: list[str]) -> str:
    filename_text = " ".join(str(item.get("filename") or "") for item in files if isinstance(item, dict))
    return " ".join(
        [
            str(pr.get("repo") or ""),
            str(pr.get("title") or ""),
            str(detail.get("title") or ""),
            str(detail.get("body") or ""),
            " ".join(label_names(pr)),
            " ".join(subjects),
            filename_text,
        ]
    ).lower()


def stream_score(rule: dict[str, Any], pr: dict[str, Any], text: str) -> int:
    repo = str(pr.get("repo") or "").lower()
    title = str(pr.get("title") or "").lower()
    score = 0
    repos = [str(item).lower() for item in rule.get("repos") or []]
    if repos:
        if repo in repos:
            score += 6
        elif not any(repo.startswith(item) or item.startswith(repo) for item in repos):
            score -= 30
    for keyword in rule.get("keywords") or []:
        key = str(keyword).lower()
        if key in title:
            score += 12
        elif key in text:
            score += 2
    return score


def fallback_stream(pr: dict[str, Any]) -> dict[str, Any]:
    repo = str(pr.get("repo") or "")
    rule_id = FALLBACK_STREAM_BY_REPO.get(repo)
    if rule_id:
        for rule in STREAM_RULES:
            if rule.get("id") == rule_id:
                return rule
    for rule in STREAM_RULES:
        if repo in set(rule.get("repos") or []):
            return rule
    return {
        "id": "other-delivery",
        "title": "其他可追溯研发交付",
        "domain": "其他 GitHub 活动",
        "value_category": "工程交付",
        "repos": [],
        "keywords": [],
        "user_problem": "这些 PR 不适合稳定归入主工作流，但仍是本季度合并交付的一部分。",
        "delivered": "保留为独立证据，等待人工补充业务语境。",
        "business_value": "不把无法确认的业务价值包装成确定结论。",
    }


def choose_stream(pr: dict[str, Any], detail: dict[str, Any], files: list[dict[str, Any]], subjects: list[str]) -> tuple[dict[str, Any], int]:
    text = detail_text(pr, detail, files, subjects)
    scored = [(stream_score(rule, pr, text), rule) for rule in STREAM_RULES]
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1], scored[0][0]
    return fallback_stream(pr), 0


def fetch_pr(pr: dict[str, Any], keep_body: bool) -> dict[str, Any]:
    repo = str(pr.get("repo") or "")
    number = int(pr.get("number") or 0)
    base = {
        "repo": repo,
        "number": number,
        "title": pr.get("title") or "",
        "url": pr.get("url") or "",
        "labels": label_names(pr),
    }
    detail, detail_error = run_gh_api(f"repos/{repo}/pulls/{number}")
    files, files_error = run_gh_api(f"repos/{repo}/pulls/{number}/files?per_page=100", paginate=True)
    commits, commits_error = run_gh_api(f"repos/{repo}/pulls/{number}/commits?per_page=100", paginate=True)
    detail_obj = detail if isinstance(detail, dict) else {}
    file_rows = files if isinstance(files, list) else []
    commit_rows = commits if isinstance(commits, list) else []
    subjects = commit_subjects([row for row in commit_rows if isinstance(row, dict)])
    body = str(detail_obj.get("body") or "")
    stream, stream_score_value = choose_stream(base, detail_obj, [row for row in file_rows if isinstance(row, dict)], subjects)
    outcome = classify_outcome(str(base.get("title") or ""), base["labels"], repo)
    compact = {
        **base,
        "merged_at": detail_obj.get("merged_at") or pr.get("closed_at") or "",
        "created_at": detail_obj.get("created_at") or pr.get("created_at") or "",
        "outcome": outcome,
        "outcome_label": OUTCOME_LABELS.get(outcome, outcome),
        "scope": conventional_scope(str(base.get("title") or "")),
        "intent": normalized_intent(str(base.get("title") or "")),
        "body_chars": len(body),
        "body_excerpt": body[:800],
        "commit_count": len(subjects),
        "commit_subjects": subjects[:12],
        "changed_files": int(detail_obj.get("changed_files") or len(file_rows) or 0),
        "additions": int(detail_obj.get("additions") or 0),
        "deletions": int(detail_obj.get("deletions") or 0),
        "top_files": top_files([row for row in file_rows if isinstance(row, dict)], 8),
        "file_paths_sample": compact_file_paths([row for row in file_rows if isinstance(row, dict)], 40),
        "work_stream_id": stream["id"],
        "work_stream_title": stream["title"],
        "domain": stream["domain"],
        "value_category": stream["value_category"],
        "stream_score": stream_score_value,
        "errors": {
            "detail": detail_error,
            "files": files_error,
            "commits": commits_error,
        },
    }
    if keep_body:
        compact["body"] = body
    return compact


def confidence_for_stream(pr_count: int, commit_count: int, file_count: int) -> str:
    if pr_count >= 3 and (commit_count or file_count):
        return "high"
    if pr_count >= 2 or file_count:
        return "medium"
    return "low"


def build_streams(pr_details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pr in pr_details:
        by_id[str(pr.get("work_stream_id") or "other-delivery")].append(pr)
    rules = {rule["id"]: rule for rule in STREAM_RULES}
    streams = []
    for stream_id, rows in by_id.items():
        rule = rules.get(stream_id) or fallback_stream(rows[0])
        outcomes = Counter(str(row.get("outcome") or "other") for row in rows)
        repos = sorted({str(row.get("repo")) for row in rows if row.get("repo")})
        additions = sum(int(row.get("additions") or 0) for row in rows)
        deletions = sum(int(row.get("deletions") or 0) for row in rows)
        changed_files = sum(int(row.get("changed_files") or 0) for row in rows)
        commit_count = sum(int(row.get("commit_count") or 0) for row in rows)
        top_evidence = sorted(
            rows,
            key=lambda row: (
                int(row.get("changed_files") or 0) + int(row.get("commit_count") or 0),
                int(row.get("additions") or 0) + int(row.get("deletions") or 0),
            ),
            reverse=True,
        )[:5]
        file_counter: Counter[str] = Counter()
        for row in rows:
            for file_item in row.get("top_files") or []:
                name = str(file_item.get("filename") or "")
                if name:
                    file_counter[name] += int(file_item.get("changes") or 1)
        commit_samples = []
        for row in rows:
            for subject in row.get("commit_subjects") or []:
                if subject and subject not in commit_samples:
                    commit_samples.append(subject)
                if len(commit_samples) >= 5:
                    break
            if len(commit_samples) >= 5:
                break
        streams.append(
            {
                "id": stream_id,
                "title": rule.get("title") or stream_id,
                "domain": rule.get("domain") or "",
                "value_category": rule.get("value_category") or "",
                "user_problem": rule.get("user_problem") or "",
                "delivered": rule.get("delivered") or "",
                "business_value": rule.get("business_value") or "",
                "pr_count": len(rows),
                "feature_prs": outcomes.get("feature", 0),
                "fix_prs": outcomes.get("fix", 0),
                "operations_prs": outcomes.get("operations", 0),
                "architecture_prs": outcomes.get("architecture", 0),
                "experience_prs": outcomes.get("experience", 0),
                "other_prs": outcomes.get("other", 0),
                "commit_subjects": commit_count,
                "changed_files": changed_files,
                "additions": additions,
                "deletions": deletions,
                "repos": repos,
                "confidence": confidence_for_stream(len(rows), commit_count, changed_files),
                "evidence_prs": [
                    {
                        "repo": row.get("repo"),
                        "number": row.get("number"),
                        "title": row.get("title"),
                        "url": row.get("url"),
                        "outcome": row.get("outcome"),
                        "outcome_label": row.get("outcome_label"),
                        "changed_files": row.get("changed_files"),
                        "commit_count": row.get("commit_count"),
                    }
                    for row in top_evidence
                ],
                "evidence_files": [{"filename": name, "changes": count} for name, count in file_counter.most_common(6)],
                "commit_samples": commit_samples,
                "boundary": "由 PR 标题、正文、commit 标题和变更文件路径推断；业务影响仍需要结合产品数据或人工标注校准。",
            }
        )
    streams.sort(key=lambda row: (int(row.get("pr_count") or 0), int(row.get("changed_files") or 0)), reverse=True)
    return streams


def build_project_breakdown(pr_details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pr_details:
        grouped[str(row.get("repo") or "unknown")].append(row)
    projects = []
    for repo, rows in grouped.items():
        streams = Counter(str(row.get("work_stream_title") or "") for row in rows)
        outcomes = Counter(str(row.get("outcome") or "other") for row in rows)
        projects.append(
            {
                "repo": repo,
                "pr_count": len(rows),
                "feature_prs": outcomes.get("feature", 0),
                "fix_prs": outcomes.get("fix", 0),
                "changed_files": sum(int(row.get("changed_files") or 0) for row in rows),
                "commit_subjects": sum(int(row.get("commit_count") or 0) for row in rows),
                "top_streams": [{"title": title, "count": count} for title, count in streams.most_common(4) if title],
                "representative_prs": [
                    {
                        "number": row.get("number"),
                        "title": row.get("title"),
                        "url": row.get("url"),
                        "work_stream_title": row.get("work_stream_title"),
                    }
                    for row in sorted(rows, key=lambda item: int(item.get("changed_files") or 0), reverse=True)[:4]
                ],
            }
        )
    projects.sort(key=lambda row: (int(row.get("pr_count") or 0), int(row.get("changed_files") or 0)), reverse=True)
    return projects


def build_summary(source_path: Path, output_path: Path, limit: int, concurrency: int, keep_body: bool) -> dict[str, Any]:
    source_summary = load_json(source_path)
    prs = merged_prs_from_summary(source_summary)
    if limit > 0:
        prs = prs[:limit]
    details: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    workers = max(1, min(12, concurrency))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(fetch_pr, pr, keep_body): pr for pr in prs}
        for future in as_completed(future_map):
            pr = future_map[future]
            try:
                details.append(future.result())
            except Exception as exc:
                failures.append({"repo": pr.get("repo"), "number": pr.get("number"), "error": str(exc)})
    order = {(str(pr.get("repo")), int(pr.get("number") or 0)): idx for idx, pr in enumerate(prs)}
    details.sort(key=lambda row: order.get((str(row.get("repo")), int(row.get("number") or 0)), 10**9))
    streams = build_streams(details)
    projects = build_project_breakdown(details)
    detail_errors = [row for row in details if (row.get("errors") or {}).get("detail")]
    file_errors = [row for row in details if (row.get("errors") or {}).get("files")]
    commit_errors = [row for row in details if (row.get("errors") or {}).get("commits")]
    outcomes = Counter(str(row.get("outcome") or "other") for row in details)
    totals = {
        "analyzed_prs": len(details),
        "work_items": len(details),
        "work_streams": len(streams),
        "projects": len(projects),
        "feature_prs": outcomes.get("feature", 0),
        "fix_prs": outcomes.get("fix", 0),
        "operations_prs": outcomes.get("operations", 0),
        "architecture_prs": outcomes.get("architecture", 0),
        "experience_prs": outcomes.get("experience", 0),
        "other_prs": outcomes.get("other", 0),
        "commit_subjects": sum(int(row.get("commit_count") or 0) for row in details),
        "changed_files": sum(int(row.get("changed_files") or 0) for row in details),
        "additions": sum(int(row.get("additions") or 0) for row in details),
        "deletions": sum(int(row.get("deletions") or 0) for row in details),
    }
    return {
        "kind": "quarterly-github-deep-work-analysis",
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "source_summary": str(source_path.resolve()),
        "artifact": str(output_path.resolve()),
        "coverage": {
            "merged_prs_total": len(merged_prs_from_summary(source_summary)),
            "requested_prs": len(prs),
            "details_attempted": len(prs),
            "details_succeeded": len(details) - len(detail_errors),
            "files_succeeded": len(details) - len(file_errors),
            "commits_succeeded": len(details) - len(commit_errors),
            "fetch_failures": len(failures),
            "method": "For each merged authored PR, read PR detail, PR files, and PR commits via GitHub REST API through gh api.",
        },
        "totals": totals,
        "outcome_mix": [{"key": key, "label": OUTCOME_LABELS.get(key, key), "count": count} for key, count in outcomes.most_common()],
        "work_streams": streams,
        "project_breakdown": projects,
        "pr_details": details,
        "failures": failures,
        "limitations": [
            "工作流由 PR 标题、正文、commit 标题和文件路径推断，不等同产品需求系统或缺陷系统中的条目。",
            "业务价值只表达代码证据可以支撑的工作流改善，不编造收入、客户满意度或线上效果。",
            "每个合并 PR 作为一个可审计工作项；一个 PR 内可能包含多个更小任务，需人工标注才能继续拆分。",
        ],
    }


def main() -> int:
    args = parse_args()
    source_path = Path(args.github_summary).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        summary = build_summary(source_path, output_path, args.limit, args.concurrency, args.keep_body)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output_path), "analyzed_prs": summary["totals"]["analyzed_prs"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
