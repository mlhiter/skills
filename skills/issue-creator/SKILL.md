---
name: issue-creator
description: Create high-quality GitHub issues for QA and product testing from terse tester notes. Use when a user wants to report, draft, polish, normalize, or create a bug/feature issue in GitHub, especially for the centralized labring-sigs/sealos-issues workflow with minimal tester input, gh CLI preflight, sensitive-info checks, GitHub Project fields such as Priority/Effort/Type/Product/Environment, and controlled updates to reusable issue catalogs.
---

# Issue Creator

Turn a short tester note into a complete GitHub issue with low friction for the tester and high signal for developers.

Default target: `labring-sigs/sealos-issues`. Load `assets/catalog.json` for current products, environments, labels, milestones, GitHub Issue fields, Project field names, and priority rules. Read `references/sealos-issues.md` when working on Sealos issues or updating the catalog. Read `references/issue-template.md` when drafting the final body.

## Core Rule

Ask the tester for as little as possible. Infer structure from their note, then preview the draft and ask only for missing information that blocks a useful issue.

Do not create a live GitHub issue until the user confirms the preview. Use `scripts/sealos_issue.py draft` for dry-runs and `scripts/sealos_issue.py draft --create` only after confirmation.

## Minimal Input

A tester may provide only:

- Environment: `10.70`, `12.38`, `bja`, `public cloud`, a URL, or a cluster name.
- Product/page: approximate names such as `maestro`, `devbox`, `对象存储`, `应用管理`, or a screenshot context.
- Action: what they did.
- Actual result: what went wrong.
- Evidence: screenshot, log, API URL, payload, response, or recording if available.

If one of these is missing but the issue is still understandable, proceed and mark the field as inferred or unknown. Ask at most 1-2 concise questions when the missing information would make the issue unusable, usually product or environment.

## Workflow

1. Run a preflight if creation is likely:

   ```bash
   python3 skills/issue-creator/scripts/sealos_issue.py preflight
   ```

   If `gh` is missing, tell the user to install GitHub CLI. On macOS, recommend `brew install gh`. If `gh` is not logged in, recommend `gh auth login`. If Project fields are needed and permissions fail, recommend `gh auth refresh -s project` or the exact scope from the gh error.
   The preflight also checks for a usable image uploader: PicList local server, PicGo CLI, or `image_uploader.command` in the catalog.

2. Draft from the raw note:

   ```bash
   python3 skills/issue-creator/scripts/sealos_issue.py draft --note "<tester note>"
   ```

3. Review the generated title, body, labels, milestone, native GitHub issue metadata, and optional project fields. Correct obvious inference mistakes yourself. Use the catalog for known aliases and the template for body shape.

4. Block or redact sensitive information before creating:
   - passwords, tokens, access keys, authorization headers, private credentials, or long credential-looking values
   - replace with `见内部渠道` or `[REDACTED]`
   - never publish test passwords into public issues

5. Create only after the user confirms:

   ```bash
   python3 skills/issue-creator/scripts/sealos_issue.py draft --note "<tester note>" --create
   ```

   The script sets native GitHub Issue Type and Issue Fields after creation when possible. Add `--project-number <number>` only when a separate GitHub Project also needs to be updated.

   If the tester supplied local screenshots, pass them with repeated `--image` flags:

   ```bash
   python3 skills/issue-creator/scripts/sealos_issue.py draft --note "<tester note>" --image "/path/to/screenshot.png" --create
   ```

   The script uploads images before issue creation and inserts Markdown image URLs into `## 证据`. It never publishes local filesystem paths. For dry-run image upload testing, add `--upload-images`; otherwise previews show `本地截图待上传：<filename>`.

   If the screenshot is on the macOS clipboard and PicList's local server is running, use `--clipboard-image` instead of saving a temporary file:

   ```bash
   python3 skills/issue-creator/scripts/sealos_issue.py draft --note "<tester note>" --clipboard-image --upload-images
   python3 skills/issue-creator/scripts/sealos_issue.py draft --note "<tester note>" --clipboard-image --create
   ```

   Without `--upload-images` or `--create`, clipboard previews show `剪贴板截图待上传` and do not call PicList. PicList uploads clipboard content through `POST /upload` with an empty JSON body, so the system clipboard must contain actual image data.

6. If a new product, environment, milestone, or Project field option is confirmed as durable, update the catalog in a controlled way:

   ```bash
   python3 skills/issue-creator/scripts/sealos_issue.py draft --note "<tester note>" --learn
   ```

   Prefer asking before learning. Do not learn typos, temporary environments, or one-off wording.

## Title Rules

Use:

```text
<Product or module>: <specific user-visible problem>
```

Examples:

- `Devbox: 公网地址协议为 grpcs/wss 时内网协议错误`
- `GPU Maestro: 创建沙箱后 VS Code 连接超时`
- `AppLaunchpad: PVC 扩容接口返回 500`
- `对象存储: 长桶名导致权限和更多操作按钮不可见`

Do not add `bug` to the title. Put Bug/Feature in Issue Type or Project `Type`. Do not use comma-style titles such as `Devbox，xxx`.

## Field Policy

Use native GitHub issue metadata first:

- Issue Type: `Bug`, `Feature`, `Task`
- Issue Fields: `Priority`, `Effort`, and other repo-level fields shown in the issue sidebar

Use GitHub Projects fields only when a separate Project board needs a duplicate value:

- `Priority`: `P0`, `P1`, `P2`
- `Type`: `Bug`, `Feature`, `Task`
- `Effort`: leave unset unless explicit or confidently suggested; development may own final effort
- `Product`: normalized product/module
- `Environment`: normalized test environment

Use issue labels only for status or special categories:

- allowed: `待测试`, `功能相关`, `部署脚本`
- do not add priority labels: `P0`, `P1`, `P2`
- do not add `待测试` when a tester first creates the issue; that label means development has finished and deployed for test

Use milestones for release or test batch such as `v5.1.2`, `Offline-v5.1`, or `public cloud` when the tester mentions it or the current task clearly belongs there.

Map internal priority to GitHub's current repo field options through the catalog. For `labring-sigs/sealos-issues`, the observed native Priority options are `Urgent`, `High`, `Medium`, and `Low`; use the catalog mapping instead of labels.

## Priority Heuristics

- `P0`: blocker, core flow unusable, data loss/corruption, security risk, cannot create/connect/deploy on a critical path.
- `P1`: important product bug, API/server error, broken feature, incorrect data, behavior that affects normal use but has a workaround or narrower scope.
- `P2`: copy, localization, visual polish, small-screen layout, minor edge compatibility, low-risk improvement.

When in doubt, suggest `P1` and show the reasoning. Do not force testers to become release managers.

## Catalog Updates

Keep stable knowledge in `assets/catalog.json`. Use controlled learning:

- If a new product/environment is detected, preview it as `catalog_suggestions`.
- Ask whether to add it when it looks durable.
- When adding, include aliases and source issue URL/date if available.
- Do not add misspellings, one-off test URLs, personal accounts, or temporary passwords.

## Image Uploaders

Prefer PicList or PicGo so testers do not need to operate GitHub's attachment UI:

- PicList: enable its local server and keep PicList running. The script reads `~/Library/Application Support/piclist/data.json` by default and uploads through `POST /upload`.
- Clipboard screenshots: if PicList local server is enabled, pass `--clipboard-image`; the script asks PicList to upload the current system clipboard image.
- PicGo CLI: install/configure with `npm install -g picgo` and `picgo set uploader`; the script uses `picgo upload <files...>`.
- Custom command: set `image_uploader.command` in `assets/catalog.json`, using `{files}` for all paths or `{file}` for the first path. The command must print final public image URLs or Markdown image links.

If upload fails during `--create`, stop instead of creating an issue with unusable local paths.

## Output Expectations

When answering the user, show a short preview:

- title
- body summary or full body when asked
- inferred fields and confidence
- sensitive-info warnings
- exact action status: dry-run only, created URL, or blocked by missing gh/project permission

Keep Chinese issue drafts natural and concise. Developers should be able to reproduce the problem without asking the tester to rewrite the report.
