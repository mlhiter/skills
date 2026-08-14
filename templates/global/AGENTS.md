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

<!-- context7 -->
Use the `ctx7` CLI to fetch current documentation whenever the user asks about a library, framework, SDK, API, CLI tool, or cloud service -- even well-known ones like React, Next.js, Prisma, Express, Tailwind, Django, or Spring Boot. This includes API syntax, configuration, version migration, library-specific debugging, setup instructions, and CLI tool usage. Use even when you think you know the answer -- your training data may not reflect recent changes. Prefer this over web search.

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

Use a documentation baseline that matches the repository's real shape. Do not force every active repository into the same software-product template.

First classify the repository:

- Application, service, library, product UI, deployable system, or operational tool: maintain the normal project knowledge set when there is enough concrete code or product direction: `README.md`, `AGENTS.md`, `PRODUCT.md`, `DESIGN.md`, `ROADMAP.md`, `docs/architecture.md`, `docs/ia.md`, `docs/references.md`, and `docs/runbook.md`.
- Skill catalog, prompt/rules repository, template bundle, or other instruction-only repository: do not create or maintain `PRODUCT.md`, `DESIGN.md`, `ROADMAP.md`, or a top-level `docs/` folder merely to satisfy a generic baseline. Keep durable context in the catalog README, publish metadata, and the owning skill/rule/template directories unless the user explicitly asks for broader docs or the repository has a concrete reason for them.
- Scratch, research, or early exploratory repository: keep documentation minimal and useful. Prefer `README.md` and local agent guidance only when they reduce future confusion.

When invoking the `neat-freak` skill, treat repo-local instructions as authoritative. During the inventory, check what documentation the repository already declares as its source of truth, then sync that surface instead of mechanically creating missing baseline files. If the repository explicitly says not to maintain a class of docs, honor that rule.

For app/product repositories, `PRODUCT.md`, `DESIGN.md`, and `README.md` are not generic Markdown chores. If `impeccable` is available, use its context expectations and relevant commands (`teach` for product context, `document` for design context) to draft or refine `PRODUCT.md` and `DESIGN.md`; if `create-readme` is available, use it to create or substantially rewrite `README.md` after reviewing the project. For instruction-only repositories, use those skills only when their output is genuinely relevant to that repository's published surface.

<!-- test-cluster-setup:start -->


## Test Cluster Access
- Cluster A kubeconfig: `<cluster-a-kubeconfig>`; access it with `kubectl --kubeconfig <cluster-a-kubeconfig> ...`.
- Cluster B kubeconfig: `<cluster-b-kubeconfig>`; access it with `kubectl --kubeconfig <cluster-b-kubeconfig> ...`.
- Cluster C kubeconfig: `<cluster-c-kubeconfig>`; access it with `kubectl --kubeconfig <cluster-c-kubeconfig> ...`.
- Cluster D kubeconfig: `<cluster-d-kubeconfig>`; access it with `kubectl --kubeconfig <cluster-d-kubeconfig> ...`.
<!-- test-cluster-setup:end -->
