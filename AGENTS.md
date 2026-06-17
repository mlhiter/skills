# Global Instructions

- Never execute database write operations unless the user explicitly asks for a database modification.
- For production deployments, always build and publish container images for `linux/amd64` by default. Do not publish ARM images unless the user explicitly asks for ARM.
- For test-time cloud image builds that need to be pushed to a remote registry, default to `<configured-private-registry>` because local push permissions are already configured there. Use a different registry only if the user explicitly asks for it.
- When browser automation or webpage interaction is needed, use the Codex app's built-in Browser Use / in-app browser. Do not use Computer Use to control an external browser unless the user explicitly asks for that.
- When the `check` skill is used for direct conversation with the user, default findings, summaries, status updates, and sign-offs to Simplified Chinese unless the user explicitly requests another language. Public issue/PR/release comments should still follow the thread language and project rules.

## Outcome-First Execution

- When the user's goal is clear and no explicit time/token/budget limit is given, prioritize completing the task end-to-end over minimizing time or token usage.
- Do not stop early, skip necessary verification, or hand back partial work merely to save time or tokens.
- Treat time and token cost as secondary operational signals, not primary decision criteria.
- Still obey explicit user limits, system/tool constraints, safety rules, approval requirements, and cases where the user only asked for discussion, planning, or analysis.
- For simple tasks, stay concise and avoid unnecessary expansion; "outcome-first" means fit-for-purpose, not overbuilding.

## Subagent Delegation

- The user explicitly authorizes Codex to use subagents without asking first when a task can benefit from parallel work.
- Prefer subagents for well-scoped, independent exploration, implementation, or verification tasks that materially advance the main goal.
- Keep work local for small tasks, urgent critical-path blockers, tightly coupled changes, overlapping write scopes, sensitive context, or cases where subagent tools are unavailable.
- When using subagents for code changes, assign disjoint file/module ownership and integrate the results before final verification.

## Automatic Task Closeout

When a task, feature implementation, bug fix, documentation update, or deploy-affecting change is complete and the session changed project files, automatically run the closeout flow before the final response. Do not wait for the user to ask for this follow-through unless they explicitly said not to commit, not to sync docs/memory, or only wanted analysis/planning/review.

Closeout order is mandatory:

1. Invoke the `check` skill to verify the work is complete, look for regressions or missed requirements, and run the appropriate project verification commands. If `check` finds a real issue, fix it and rerun the relevant verification before continuing.
2. Invoke the `neat-freak` skill to sync project docs, runbooks, agent guidance, and memory-relevant knowledge with the completed change. If the change produced no durable knowledge or documentation impact, record that explicitly in the final summary rather than inventing placeholder docs.
3. Invoke the `git-commit-push` skill to stage and commit only the changes attributable to the current session, then push the new commit(s) when the repository has a clear upstream and the safe-push checks pass. Preserve unrelated dirty work, split independent changes into logical commits, and stop instead of pushing when publication would require force, ambiguous remotes, protected-branch workarounds, or other unsafe git operations.

Stop the closeout flow and report the blocker instead of guessing when ownership of dirty files is ambiguous, verification fails repeatedly, a commit would include secrets or credentials, the worktree is not a Git repository, or the next step requires a database write, production mutation, force push, destructive cleanup, or other action that these global rules require explicit user approval for.

The final response after closeout should include the verification performed, documentation/memory sync result, commit hash(es), and any intentionally uncommitted or out-of-scope changes.

## Pull Request Creation Preflight

Before creating a pull request, ensure the PR creation workflow invokes the `check` skill for a PR-preflight code review of the final diff that will appear in the PR. Resolve the intended base/head before review, and review against that exact PR range. If `check` finds real issues introduced by the current work, fix them and rerun the relevant verification before calling `gh pr create`.

Do not create the PR when PR-preflight review is blocked by unresolved verification failures, ambiguous dirty work ownership, unsafe base/head selection, secrets, missing generated artifacts, or issues that require product/architecture approval.

If the same final diff and same base/head were already reviewed by `check` in this session and neither HEAD nor worktree state changed, reuse that review result instead of rerunning it. When using `pr-creator`, its workflow owns this preflight and must not skip it. If the user explicitly requests a draft/WIP PR without review, create it only if safe and state that PR-preflight review was intentionally skipped.

<!-- context7 -->
Use the `ctx7` CLI to fetch current documentation whenever the user asks about a library, framework, SDK, API, CLI tool, or cloud service -- even well-known ones like React, Next.js, Prisma, Express, Tailwind, Django, or Spring Boot. This includes API syntax, configuration, version migration, library-specific debugging, setup instructions, and CLI tool usage. Use even when you think you know the answer -- your training data may not reflect recent changes. Prefer this over web search for library docs.

Do not use for: refactoring, writing scripts from scratch, debugging business logic, code review, or general programming concepts.

## Steps

1. Resolve library: `npx ctx7@latest library <name> "<user's question>"` — use the official library name with proper punctuation (e.g., "Next.js" not "nextjs", "Customer.io" not "customerio", "Three.js" not "threejs")
2. Pick the best match (ID format: `/org/project`) by: exact name match, description relevance, code snippet count, source reputation (High/Medium preferred), and benchmark score (higher is better). If results don't look right, try alternate names or queries (e.g., "next.js" not "nextjs", or rephrase the question)
3. Fetch docs: `npx ctx7@latest docs <libraryId> "<user's question>"`
4. Answer using the fetched documentation

You MUST call `library` first to get a valid ID unless the user provides one directly in `/org/project` format. Use the user's full question as the query -- specific and detailed queries return better results than vague single words. Do not run more than 3 commands per question. Do not include sensitive information (API keys, passwords, credentials) in queries.

For version-specific docs, use `/org/project/version` from the `library` output (e.g., `/vercel/next.js/v14.3.0`).

If a command fails with a quota error, inform the user and suggest `npx ctx7@latest login` or setting `CONTEXT7_API_KEY` env var for higher limits. Do not silently fall back to training data.
Run Context7 CLI requests outside Codex's default sandbox. If a Context7 CLI command fails with DNS or network errors such as ENOTFOUND, host resolution failures, or fetch failed, rerun it outside the sandbox instead of retrying inside the sandbox.
<!-- context7 -->

## Project Knowledge Baseline

Every sufficiently active project should maintain this minimum documentation set:

- `DESIGN.md` — design style, visual language, UX principles, and UI tone. When creating or improving this file, prefer using the `impeccable` skill's design-document workflow so the output becomes actionable UI guidance, not generic taste notes.
- `PRODUCT.md` — product definition, target users, core scenarios, feature scope, and product decisions. When creating or improving this file, prefer using the `impeccable` skill's product-context workflow so it captures users, brand, tone, anti-references, strategic principles, and the design register expected by that skill.
- `README.md` — the classic project introduction: what it is, how to install/run it, and where to start. When creating or substantially improving this file, prefer using the `create-readme` skill so the README is based on a full project review and stays concise, useful, and well structured.
- `ROADMAP.md` — roadmap and priority framing so Codex can judge what to do first.
- `AGENTS.md` — Codex rules for the project: project overview, basic rules, "do not" constraints, run commands, environment notes, and other project-specific operating guidance.
- `docs/` — supporting documentation folder.
- `docs/architecture.md` — architecture, major modules, data/control flow, and important technical tradeoffs.
- `docs/ia.md` — information architecture and page/route structure.
- `docs/references.md` — external references, prior art, comparable projects, and source links used by this project.
- `docs/runbook.md` — detailed run, build, test, deploy, debug, and operational commands.

When invoking the `neat-freak` skill for a project, treat this baseline as part of the cleanup contract. During the initial documentation inventory, check whether each item exists. If any item is missing and the project has enough concrete code or product direction to document it, create the missing file or folder with useful project-specific starter content instead of leaving empty placeholders. If the project is still too early for a specific document, note that explicitly in the final cleanup summary.

For the `PRODUCT.md`, `DESIGN.md`, and `README.md` baseline files specifically, do not treat them as generic Markdown chores. If `impeccable` is available in the project or globally, use its context expectations and relevant commands (`teach` for product context, `document` for design context) to draft or refine `PRODUCT.md` and `DESIGN.md` before continuing with broader `neat-freak` cleanup. If `create-readme` is available, use it to create or substantially rewrite `README.md` after reviewing the project instead of producing a shallow placeholder.

<!-- test-cluster-setup:start -->

## Test Cluster Access
- Cluster A kubeconfig: `<cluster-a-kubeconfig>`; access it with `kubectl --kubeconfig <cluster-a-kubeconfig> ...`.
- Cluster B kubeconfig: `<cluster-b-kubeconfig>`; access it with `kubectl --kubeconfig <cluster-b-kubeconfig> ...`.
<!-- test-cluster-setup:end -->
