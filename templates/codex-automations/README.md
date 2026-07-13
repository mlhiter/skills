# Codex automation templates

These are public-safe versions of recurring Codex tasks used by the repository author. They are templates for an agent to read and create with the Codex app's automation tool; they are not installable skills and should not be copied directly into `~/.codex/automations`.

| Template | Default schedule | Purpose |
| :--- | :--- | :--- |
| [`github-trending-daily`](github-trending-daily/automation.toml) | Daily at 09:30 | Chinese briefing from GitHub Trending daily. |
| [`ai-hot-daily`](ai-hot-daily/automation.toml) | Daily at 14:00 | Chinese briefing from the latest selected AI HOT stories. |
| [`weekly-work-review`](weekly-work-review/automation.toml) | Monday at 10:00 | Evidence-based review of the previous full calendar week. |

## Use with your agent

Ask your agent to create one or more templates in the current Codex task:

```text
Read templates/codex-automations/github-trending-daily/automation.toml from this repository, show me the schedule and prompt, then create it as an active automation attached to this Codex task.
```

Or ask it to review all three first:

```text
Read the Codex automation templates in this repository. Recommend which ones fit my environment, adapt any project-specific wording, and only create the ones I approve.
```

Each template intentionally omits instance-specific fields such as the automation ID, target thread ID, project ID, local paths, and timestamps. The agent should use the Codex app's native automation tool so those values are assigned for the user's environment. Schedules run in the Codex app's local timezone unless the user requests another schedule.

Review the prompt and data sources before enabling a template. The work-review template inspects local repositories in read-only mode. The news templates access public network sources and may depend on source availability.

## 中文说明

这里收录的是仓库作者日常实际使用的 Codex 定时任务脱敏模板。它们不是可安装 skill，也不应直接复制到 `~/.codex/automations`；请让 agent 读取模板，并通过 Codex app 原生的 automation 工具在当前任务中创建。

可以直接对 agent 说：

```text
读取当前仓库中 templates/codex-automations 下的定时任务模板，先告诉我调度时间和执行内容，再把我确认的任务创建到当前 Codex 任务中。
```

模板刻意省略了 automation ID、目标任务 ID、项目 ID、本机路径和时间戳。调度默认按 Codex app 的本地时区执行。启用前应检查提示词和数据来源；工作回顾模板只读检查本地仓库，新闻类模板会访问公开网络来源。
