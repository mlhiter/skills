<!-- prettier-ignore -->
<div align="center">

<img src="assets/mlhiter-skills.svg" width="820" alt="Visual overview of the mlhiter skills catalog" />

# mlhiter skills

Reusable Codex agent skills for planning, debugging, review, writing, workflow packaging, and safe project follow-through.

[![skills.sh](https://skills.sh/b/mlhiter/skills)](https://skills.sh/mlhiter/skills)

[Browse on skills.sh](https://skills.sh/mlhiter/skills) | [Install](#install) | [Catalog](#catalog) | [Maintain](#maintaining-this-catalog)

Languages: [en](README.md) | [zh](README.zh-CN.md)

</div>

`mlhiter/skills` is a public catalog of installable agent skills. Each skill is a portable instruction bundle under `skills/<skill-name>/SKILL.md`, with any references, scripts, or assets kept inside the owning skill directory.

Use this repository when you want Codex to follow a durable workflow instead of a one-off prompt: think through a feature, hunt down a regression, review before shipping, create a clean commit, package repeated work into a reusable skill, or turn rough notes into a useful artifact.

> [!IMPORTANT]
> This is an instruction-only skill catalog, not an application codebase. Keep published content public-safe: no credentials, private registry URLs, private cluster names, personal machine paths, or one-off project facts.

## Install

Preview the catalog:

```bash
npx skills add mlhiter/skills --list
```

Install every skill:

```bash
npx skills add mlhiter/skills --all
```

Install one skill:

```bash
npx skills add mlhiter/skills --skill check
```

> [!TIP]
> Start with one skill if you only need a specific workflow. Each installed skill is self-contained enough to be read and audited before use.

## Prompting tips

These small prompts make skill-driven work more reliable:

1. Ask the agent to `restate my request` before it starts. A clear restatement exposes mismatched assumptions early.
2. Ask the agent to `use first principles` when designing a plan. It should identify the invariant, source of truth, ownership boundary, causal chain, and smallest mechanism that solves the problem.
3. Ask the agent to `use adversarial review` when reviewing code. It should actively look for malformed input, concurrency issues, tenant or auth boundary mistakes, unsafe sinks, cache surprises, deploy risks, and rollback gaps.

The second and third prompts are credited to Khazix.

## Catalog

| Area | Skill | Use it when |
| :--- | :--- | :--- |
| Writing | [`logseq-writer`](skills/logseq-writer/SKILL.md) | Turning topics, drafts, and notes into practical Logseq-style tutorial articles. |
| Writing | [`intern-learning-recap`](skills/intern-learning-recap/SKILL.md) | Explaining completed work as an intern-friendly technical learning recap. |
| Planning | [`think`](skills/think/SKILL.md) | Turning rough ideas into decision-complete plans before coding. |
| Debugging | [`hunt`](skills/hunt/SKILL.md) | Finding root cause before fixing errors, regressions, crashes, and broken behavior. |
| Review | [`check`](skills/check/SKILL.md) | Reviewing completed work with feature-intent modeling, functional acceptance, adversarial review, and release gates. |
| Codex | [`codex-goal-builder`](skills/codex-goal-builder/SKILL.md) | Drafting evidence-based Codex Goals from rough long-running objectives. |
| Codex | [`codex-runner-creator`](skills/codex-runner-creator/SKILL.md) | Creating or repairing Codex app environment run actions. |
| Codex | [`workflow-packager`](skills/workflow-packager/SKILL.md) | Mining repeated agent work and turning it into skills, subagents, automations, or templates. |
| Git | [`git-commit-push`](skills/git-commit-push/SKILL.md) | Creating session-scoped Conventional Commits and safely publishing them. |
| Git | [`pr-creator`](skills/pr-creator/SKILL.md) | Creating pull requests with explicit base/head resolution and fork/upstream safety. |
| Reporting | [`quarterly-work-dashboard`](skills/quarterly-work-dashboard/SKILL.md) | Generating leadership-facing quarterly dashboards from read-only GitHub and Feishu evidence. |
| QA | [`issue-creator`](skills/issue-creator/SKILL.md) | Turning terse tester notes into structured GitHub issues. |
| Design | [`screenshot-interaction`](skills/screenshot-interaction/SKILL.md) | Inferring expected UI behavior, states, and interactions from screenshots. |

## Repository layout

```text
.
|-- AGENTS.md
|-- README.md
|-- README.zh-CN.md
|-- assets/
|   `-- mlhiter-skills.svg
|-- skills.sh.json
`-- skills/
    `-- <skill-name>/
        |-- SKILL.md
        |-- references/
        |-- scripts/
        `-- assets/
```

`README.md` and `README.zh-CN.md` are the discovery surfaces, `skills.sh.json` is the publishable catalog metadata, and each `skills/<skill-name>/` directory owns the instructions and bundled materials for that skill.

## Maintaining this catalog

When adding, removing, or renaming a skill:

1. Put the skill at `skills/<skill-name>/SKILL.md`.
2. Keep skill-specific references, scripts, and assets inside that skill directory.
3. Update `skills.sh.json` so the published catalog stays accurate.
4. Update both README files so users can discover the skill.
5. Keep root `AGENTS.md` sanitized for public use.

Suggested checks before publishing:

```bash
python3 -m json.tool skills.sh.json >/dev/null
git diff --check
```

> [!NOTE]
> Do not create generic product docs such as `PRODUCT.md`, `DESIGN.md`, `ROADMAP.md`, or a top-level `docs/` folder just to satisfy a software-project template. This repository's durable context belongs in these README files, `skills.sh.json`, and the owning skill directories.

## Provenance

Some skills are original playbooks from personal workflows. Some are adapted from public skill repositories and then extended for Codex, durable context, runtime evidence, and Chinese/English workflow usage.

| Skill | Provenance |
| :--- | :--- |
| `think` | Adapted from [`tw93/Waza`](https://github.com/tw93/Waza)'s `think` workflow, then extended for Codex planning and durable context. |
| `hunt` | Adapted from [`tw93/Waza`](https://github.com/tw93/Waza)'s `hunt` workflow, then extended with root-cause gates and runtime evidence ladders. |
| `check` | Adapted from [`tw93/Waza`](https://github.com/tw93/Waza)'s `check` workflow, then extended with feature-intent risk modeling, acceptance gates, and release checks. |
| `logseq-writer` | Original personal writing workflow for practical Logseq tutorial articles. |
| `workflow-packager` | Original workflow-mining playbook for turning repeated agent work into reusable assets. |
| `quarterly-work-dashboard` | Original dashboard-generation workflow for read-only GitHub and Feishu quarterly evidence. |
| `codex-goal-builder` | Original Codex Goal drafting workflow. |
| `codex-runner-creator` | Original Codex app environment-action workflow. |
| `git-commit-push` | Original session-scoped git commit and safe-push workflow based on Conventional Commits. |
| `pr-creator` | Original PR-creation workflow focused on explicit fork/upstream head and base safety. |
| `intern-learning-recap` | Original intern-friendly teaching recap workflow. |
| `issue-creator` | Original QA issue drafting workflow for structured GitHub issue creation. |
| `screenshot-interaction` | Original screenshot-to-interaction-contract workflow. |

External repositories such as [`mattpocock/skills`](https://github.com/mattpocock/skills) have also been reviewed as pattern sources, especially for public-interface discipline and tighter feedback loops. The skills in this catalog are not wholesale copies of that repository.

## Safety

These skills are instruction bundles that can influence how an agent reads files, writes project changes, creates commits, or interacts with external tools. Read the relevant `SKILL.md` before installing or invoking a workflow, especially for skills that inspect local histories, change project files, or publish artifacts.
