#!/usr/bin/env python3
"""Run the full quarterly work dashboard pipeline in one command."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate GitHub, Feishu, and combined quarterly work dashboards.")
    parser.add_argument("--start", required=True, help="Start date, inclusive, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date, inclusive, YYYY-MM-DD")
    parser.add_argument("--period-label", default="", help="Display label, e.g. 2026 Q2")
    parser.add_argument("--output-dir", required=True, help="Output directory for the combined dashboard")
    parser.add_argument("--save-raw", action="store_true", help="Save raw data for GitHub and Feishu submodules")
    parser.add_argument("--annotations", default="", help="Optional JSON/YAML annotations for boss-facing wording and project notes.")

    github = parser.add_argument_group("GitHub")
    github.add_argument("--github-user", default="", help="GitHub login. Defaults to authenticated gh user.")
    github.add_argument("--github-repo", action="append", default=[], help="Limit GitHub stats to repo owner/name. Repeatable.")
    github.add_argument("--github-owner", action="append", default=[], help="Limit GitHub stats to owner/org. Repeatable.")
    github.add_argument("--github-limit", type=int, help="Maximum GitHub results per search query. Defaults to the GitHub module default.")
    github.add_argument("--skip-code-stats", action="store_true", help="Skip per-merged-PR GitHub API calls for additions/deletions/file breakdown.")
    github.add_argument("--skip-project-portfolio", action="store_true", help="Skip repo metadata/README/language collection for project portfolio analysis.")
    github.add_argument("--skip-deep-github-analysis", action="store_true", help="Skip deep PR/body/commit/file analysis for the leadership work breakdown.")
    github.add_argument("--deep-github-limit", type=int, default=0, help="Only deep-analyze first N merged PRs. Defaults to all merged PRs.")
    github.add_argument("--deep-github-concurrency", type=int, default=6, help="Concurrent gh api workers for deep GitHub analysis.")
    github.add_argument("--previous-start", default="", help="Previous comparison start date, YYYY-MM-DD")
    github.add_argument("--previous-end", default="", help="Previous comparison end date, YYYY-MM-DD")
    github.add_argument("--previous-period-label", default="", help="Previous period label, e.g. 2026 Q1")
    github.add_argument("--skip-github", action="store_true", help="Skip GitHub collection and use --github-summary.")
    github.add_argument("--github-summary", default="", help="Existing GitHub summary.json to use when --skip-github is set.")

    feishu = parser.add_argument_group("Feishu")
    feishu.add_argument("--doc", action="append", default=[], help="Feishu doc URL or token. Repeatable.")
    feishu.add_argument("--skip-doc-discovery", action="store_true", help="Disable Drive search based document discovery.")
    feishu.add_argument("--skip-doc-reading", action="store_true", help="Only discover documents, do not fetch document content.")
    feishu.add_argument("--doc-search-query", default="", help="Drive search query for document discovery.")
    feishu.add_argument("--doc-types", default="docx,doc,wiki", help="Comma-separated Drive doc types for discovery.")
    feishu.add_argument("--doc-search-page-limit", type=int, default=5, help="Max Drive search pages for document discovery.")
    feishu.add_argument("--doc-search-page-size", type=int, default=20, help="Drive search page size.")
    feishu.add_argument("--doc-read-limit", type=int, default=12, help="Max discovered documents to fetch.")
    feishu.add_argument("--message-query", action="append", default=[], help="Message search query. Repeatable.")
    feishu.add_argument("--chat-id", action="append", default=[], help="Restrict messages to chat IDs.")
    feishu.add_argument("--sender", action="append", default=[], help="Restrict messages to sender open_ids.")
    feishu.add_argument("--chat-type", choices=["group", "p2p"], default="")
    feishu.add_argument("--sender-type", choices=["user", "bot"], default="")
    feishu.add_argument("--exclude-sender-type", choices=["user", "bot"], default="")
    feishu.add_argument("--include-attachment-type", choices=["file", "image", "video", "link"], default="")
    feishu.add_argument("--is-at-me", action="store_true")
    feishu.add_argument("--message-page-limit", type=int, default=5)
    feishu.add_argument("--message-page-size", type=int, default=50)
    feishu.add_argument("--include-calendar", action="store_true", help="Collect calendar agenda.")
    feishu.add_argument("--skip-calendar", action="store_true", help="Disable calendar collection.")
    feishu.add_argument("--keyword", action="append", default=[], help="Extra keyword for Feishu topic counting.")
    feishu.add_argument("--attempt-with-missing-scopes", action="store_true")
    feishu.add_argument("--skip-feishu", action="store_true", help="Skip Feishu collection and use --feishu-summary.")
    feishu.add_argument("--feishu-summary", default="", help="Existing Feishu summary.json to use when --skip-feishu is set.")
    return parser.parse_args()


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def run_step(name: str, cmd: list[str]) -> dict[str, object]:
    started_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finished_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    return {
        "name": name,
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "started_at": started_at,
        "finished_at": finished_at,
    }


def extend_repeated(cmd: list[str], flag: str, values: list[str]) -> None:
    for value in values:
        cmd.extend([flag, value])


def copy_existing_module(summary_path: Path, module_dir: Path) -> tuple[Path, Path]:
    module_dir.mkdir(parents=True, exist_ok=True)
    target_summary = module_dir / "summary.json"
    target_index = module_dir / "index.html"
    if summary_path.resolve() != target_summary.resolve():
        shutil.copy2(summary_path, target_summary)
    source_index = summary_path.with_name("index.html")
    if source_index.exists() and source_index.resolve() != target_index.resolve():
        shutil.copy2(source_index, target_index)
    return target_summary, target_index


def main() -> int:
    args = parse_args()
    root = Path(args.output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    github_dir = root / "github"
    feishu_dir = root / "feishu"
    steps: list[dict[str, object]] = []

    if args.skip_github:
        if not args.github_summary:
            print("error: --skip-github requires --github-summary", file=sys.stderr)
            return 2
        github_summary = Path(args.github_summary).expanduser().resolve()
        github_summary, github_index = copy_existing_module(github_summary, github_dir)
    else:
        github_dir.mkdir(parents=True, exist_ok=True)
        github_cmd = [
            sys.executable,
            str(script_dir() / "generate_github_quarterly_dashboard.py"),
            "--start",
            args.start,
            "--end",
            args.end,
            "--output-dir",
            str(github_dir),
        ]
        if args.period_label:
            github_cmd.extend(["--period-label", args.period_label])
        if args.github_user:
            github_cmd.extend(["--user", args.github_user])
        if args.github_limit is not None:
            github_cmd.extend(["--limit", str(args.github_limit)])
        if args.skip_code_stats:
            github_cmd.append("--skip-code-stats")
        if args.skip_project_portfolio:
            github_cmd.append("--skip-project-portfolio")
        if args.previous_start:
            github_cmd.extend(["--previous-start", args.previous_start])
        if args.previous_end:
            github_cmd.extend(["--previous-end", args.previous_end])
        if args.previous_period_label:
            github_cmd.extend(["--previous-period-label", args.previous_period_label])
        extend_repeated(github_cmd, "--repo", args.github_repo)
        extend_repeated(github_cmd, "--owner", args.github_owner)
        if args.save_raw:
            github_cmd.append("--save-raw")
        github_step = run_step("github", github_cmd)
        steps.append(github_step)
        if github_step["returncode"] != 0:
            write_run_summary(root, steps)
            print(github_step["stderr"] or github_step["stdout"], file=sys.stderr)
            return int(github_step["returncode"])
        github_summary = github_dir / "summary.json"
        github_index = github_dir / "index.html"

    github_deep_analysis = ""
    if not args.skip_deep_github_analysis:
        github_deep_path = github_dir / "deep_work_analysis.json"
        deep_cmd = [
            sys.executable,
            str(script_dir() / "deep_github_work_analysis.py"),
            "--github-summary",
            str(github_summary),
            "--output",
            str(github_deep_path),
            "--concurrency",
            str(args.deep_github_concurrency),
        ]
        if args.deep_github_limit:
            deep_cmd.extend(["--limit", str(args.deep_github_limit)])
        deep_step = run_step("github-deep-analysis", deep_cmd)
        steps.append(deep_step)
        if deep_step["returncode"] != 0:
            write_run_summary(root, steps)
            print(deep_step["stderr"] or deep_step["stdout"], file=sys.stderr)
            return int(deep_step["returncode"])
        github_deep_analysis = str(github_deep_path)

    if args.skip_feishu:
        if not args.feishu_summary:
            print("error: --skip-feishu requires --feishu-summary", file=sys.stderr)
            return 2
        feishu_summary = Path(args.feishu_summary).expanduser().resolve()
        feishu_summary, feishu_index = copy_existing_module(feishu_summary, feishu_dir)
    else:
        feishu_dir.mkdir(parents=True, exist_ok=True)
        feishu_cmd = [
            sys.executable,
            str(script_dir() / "generate_feishu_quarterly_dashboard.py"),
            "--start",
            args.start,
            "--end",
            args.end,
            "--output-dir",
            str(feishu_dir),
        ]
        if args.period_label:
            feishu_cmd.extend(["--period-label", args.period_label])
        extend_repeated(feishu_cmd, "--doc", args.doc)
        if args.skip_doc_discovery:
            feishu_cmd.append("--skip-doc-discovery")
        if args.skip_doc_reading:
            feishu_cmd.append("--skip-doc-reading")
        if args.doc_search_query:
            feishu_cmd.extend(["--doc-search-query", args.doc_search_query])
        feishu_cmd.extend(["--doc-types", args.doc_types])
        feishu_cmd.extend(["--doc-search-page-limit", str(args.doc_search_page_limit)])
        feishu_cmd.extend(["--doc-search-page-size", str(args.doc_search_page_size)])
        feishu_cmd.extend(["--doc-read-limit", str(args.doc_read_limit)])
        extend_repeated(feishu_cmd, "--message-query", args.message_query)
        extend_repeated(feishu_cmd, "--chat-id", args.chat_id)
        extend_repeated(feishu_cmd, "--sender", args.sender)
        if args.chat_type:
            feishu_cmd.extend(["--chat-type", args.chat_type])
        if args.sender_type:
            feishu_cmd.extend(["--sender-type", args.sender_type])
        if args.exclude_sender_type:
            feishu_cmd.extend(["--exclude-sender-type", args.exclude_sender_type])
        if args.include_attachment_type:
            feishu_cmd.extend(["--include-attachment-type", args.include_attachment_type])
        if args.is_at_me:
            feishu_cmd.append("--is-at-me")
        feishu_cmd.extend(["--message-page-limit", str(args.message_page_limit)])
        feishu_cmd.extend(["--message-page-size", str(args.message_page_size)])
        if args.include_calendar:
            feishu_cmd.append("--include-calendar")
        if args.skip_calendar:
            feishu_cmd.append("--skip-calendar")
        extend_repeated(feishu_cmd, "--keyword", args.keyword)
        if args.save_raw:
            feishu_cmd.append("--save-raw")
        if args.attempt_with_missing_scopes:
            feishu_cmd.append("--attempt-with-missing-scopes")
        feishu_step = run_step("feishu", feishu_cmd)
        steps.append(feishu_step)
        if feishu_step["returncode"] != 0:
            write_run_summary(root, steps)
            print(feishu_step["stderr"] or feishu_step["stdout"], file=sys.stderr)
            return int(feishu_step["returncode"])
        feishu_summary = feishu_dir / "summary.json"
        feishu_index = feishu_dir / "index.html"

    combined_cmd = [
        sys.executable,
        str(script_dir() / "generate_work_quarterly_dashboard.py"),
        "--github-summary",
        str(github_summary),
        "--feishu-summary",
        str(feishu_summary),
        "--github-index",
        str(github_index),
        "--feishu-index",
        str(feishu_index),
        "--output-dir",
        str(root),
    ]
    if args.period_label:
        combined_cmd.extend(["--period-label", args.period_label])
    if args.annotations:
        combined_cmd.extend(["--annotations", args.annotations])
    if github_deep_analysis:
        combined_cmd.extend(["--github-deep-analysis", github_deep_analysis])
    combined_step = run_step("combined", combined_cmd)
    steps.append(combined_step)
    write_run_summary(root, steps)
    if combined_step["returncode"] != 0:
        print(combined_step["stderr"] or combined_step["stdout"], file=sys.stderr)
        return int(combined_step["returncode"])

    print(
        json.dumps(
            {
                "ok": True,
                "output_dir": str(root),
                "index": str(root / "index.html"),
                "summary": str(root / "summary.json"),
                "github": str(github_summary),
                "feishu": str(feishu_summary),
                "run": str(root / "run.json"),
            },
            ensure_ascii=False,
        )
    )
    return 0


def write_run_summary(root: Path, steps: list[dict[str, object]]) -> None:
    (root / "run.json").write_text(json.dumps({"steps": steps}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
