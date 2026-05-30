# Sealos Issues Reference

Use this reference for the centralized Sealos QA issue workflow.

## Default Repository

- Repository: `labring-sigs/sealos-issues`
- Purpose: record and track Sealos-related bugs and testing content.
- New tester-created issues should not receive `待测试`; that status is added after development finishes and deploys a fix.

## Issue Shape

Prefer this metadata split:

- Title: human-readable product/module prefix plus the specific problem.
- Body: environment, problem, reproduction, actual result, expected result, evidence.
- Milestone: release or testing batch when known.
- Native GitHub issue metadata: Issue Type and Issue Fields such as Priority/Effort.
- GitHub Project fields: optional duplicate tracking when a separate Project board is used.
- Labels: only status or special categories.

## Title Examples

Good:

- `Devbox: 公网地址协议为 grpcs/wss 时内网协议错误`
- `GPU Maestro: 创建沙箱后 VS Code 连接超时`
- `AppLaunchpad: PVC 扩容接口返回 500`
- `对象存储: 长桶名导致权限和更多操作按钮不可见`

Avoid:

- `Devbox bug`
- `Devbox: xxx bug`
- `GPU Maestro，缺少GPU型号设置，导致创建任务失败。`
- `样式不美观`

## Labels

Current repo labels observed:

- `P0`, `P1`, `P2`: historical priority labels. Do not add these for new issues created by this skill.
- `功能相关`: use only for functional bugs when a label is helpful.
- `待测试`: development-complete status; do not add on initial creation.
- `部署脚本`: use when a smoke/deployment script is available or requested.

## Milestones

Observed milestones:

- `Offline-v5.1`
- `public cloud`
- `v5.1.2`

Use a milestone when the tester names the release/test batch or the current test campaign makes it obvious.

## Sensitive Information

Public issue bodies must not include passwords, tokens, authorization headers, access keys, or private credentials. If the tester provides credentials, replace with `见内部渠道` and mention that credentials were redacted.

## Project Fields

Prefer native GitHub issue fields shown in the issue sidebar. Observed fields:

- `Priority`: single select with `Urgent`, `High`, `Medium`, `Low`
- `Effort`: single select with `High`, `Medium`, `Low`

Map internal priorities through the catalog:

- `P0` -> `Urgent`
- `P1` -> `High`
- `P2` -> `Low`

Expected Project field names, with aliases that the script may match when ProjectV2 is also configured:

- `Priority`: `Priority`, `优先级`
- `Type`: `Type`, `类型`
- `Effort`: `Effort`, `工作量`
- `Product`: `Product`, `产品`, `Module`, `模块`
- `Environment`: `Environment`, `环境`
- `Status`: `Status`, `状态`

If ProjectV2 field lookup fails because gh lacks Project scopes, do not fall back to priority labels. Native issue fields do not require `read:project`; set those first.

## Attachments

GitHub's public `gh issue create` / `gh issue comment` commands do not upload local image files into `user-attachments` URLs. When the tester supplies screenshots, use the skill script's `--image` flow so the files are uploaded through PicList, PicGo CLI, or a configured uploader command before issue creation.

Never publish local filesystem paths. If image upload is not configured, block creation and tell the tester to either enable PicList's local server, install/configure PicGo CLI with `npm install -g picgo && picgo set uploader`, or set `image_uploader.command` in `assets/catalog.json`.
