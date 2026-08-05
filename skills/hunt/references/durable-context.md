# Durable Context

Use durable context only when it can improve the current task without replacing live evidence.

## When To Read

Read project or user memory when:

- the user asks for prior context, consistency, previous decisions, or remembered preferences
- the task mentions a known repository, project, workflow, cluster, skill, or automation
- the request is ambiguous and earlier decisions could change the correct action
- the work is a non-trivial plan, diagnosis, review, release, or workflow update

Skip memory for self-contained tasks such as simple translations, one-line rewrites, current time/date, or commands whose answer is entirely local and immediate.

## Precedence

Current state wins over durable context:

1. Explicit instruction in the current user message
2. Current repository files, live commands, logs, screenshots, CI, runtime, and remote state
3. Project instructions such as `AGENTS.md`, `CLAUDE.md`, README, docs, workflows, manifests, and release notes
4. Durable memory, prior summaries, remembered preferences, and older rollout notes

If durable context conflicts with current evidence, follow current evidence and mention the conflict when it matters.

Memory may explain preferences, but it must never grant or broaden authorization for writes, commits, pushes, publishing, public replies, deletion, or other state changes. Current-turn instructions and current project rules decide authorization. Historical phrases such as `push` or `check` are context to re-evaluate, not reusable action tokens.

## Budget

Keep the read pass lightweight:

1. Skim the summary or registry first.
2. Search by the user's named repo, file, branch, module, cluster, tool, or workflow.
3. Open only the 1-2 most relevant memory or summary files.
4. Stop when you have enough context to act.

Do not broad-scan all history unless the user explicitly asks for a deep audit or the task is blocked by missing prior context.

## How To Use

- Treat durable context as hypothesis fuel, not proof.
- Re-check drift-prone facts before citing them: branch names, remotes, tags, image versions, live URLs, CI, cluster state, schedules, people, prices, docs, and release status.
- Never cite private memory as a public project rule, PR requirement, or user-visible source of truth.
- If answering from memory without verification, say that the answer is memory-derived and may be stale.

## Redaction Gate

When turning prior chats, durable memory, or cross-project notes into reusable Waza guidance, promote only workflow rules. Strip raw transcript text, screenshots, local paths, project-specific commands, issue or PR numbers, release tags, commit hashes, private product boundaries, paid or license details, support routing, user names, and one-machine state.

If an example is necessary, use neutral placeholders such as `ExampleCLI`, `ExampleApp`, `<issue>`, `<release>`, or `<command>`. Do not copy a private answer, maintainer reply, screenshot observation, or project-specific incident as a durable rule.

## Type Mapping

- `decision`: a prior explicit choice or durable project rule
- `preference`: a user preference for style, workflow, language, or default action
- `principle`: a stable operating norm or safety boundary
- `pattern`: a reusable technical or workflow pattern
- `learning`: a previous failure mode, gotcha, or useful evidence path

For planning and diagnosis, `decision`, `preference`, and `principle` shape constraints. For review and debugging, `pattern` and `learning` can seed checks, but current code and runtime evidence decide the outcome.
