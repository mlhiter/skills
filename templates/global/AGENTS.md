# Global Instructions

- Never execute database write operations unless the user explicitly asks for a database modification.
- For container image builds and production deployments, always build and publish multi-platform container images for `linux/amd64` and `linux/arm64` by default. Do not publish other architectures unless the user explicitly asks for them.
- For test-time cloud image builds that need to be pushed to a remote registry, build and publish `linux/amd64` and `linux/arm64` images by default and use `<configured-private-registry>` when it is configured for local push access. Use a different registry only if the user explicitly asks for it.
- When browser automation or webpage interaction is needed, use the Codex app's built-in Browser Use / in-app browser when it is available. When running in a third-party Codex host (such as Conductor), or when the in-app browser is unavailable, use the `agent-browser` skill/CLI or Codex's supported browser control for Chrome and existing Chrome sessions. Do not use generic Computer Use to control an external browser unless the user explicitly asks for that.
- When the `check` skill is used for direct conversation with the user, default findings, summaries, status updates, and sign-offs to Simplified Chinese unless the user explicitly requests another language. Public issue/PR/release comments should still follow the thread language and project rules.

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
