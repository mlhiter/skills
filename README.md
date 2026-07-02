# Skills

[![skills.sh](https://skills.sh/b/mlhiter/skills)](https://skills.sh/mlhiter/skills)

Reusable agent skills for practical writing, workflow packaging, Codex goal drafting, dashboard reporting, and Codex app run actions.

This repository also includes a sanitized root `AGENTS.md` derived from my global Codex instructions, with private registry and cluster details replaced by placeholders.

For maintainers, the project context lives in `PRODUCT.md`, `DESIGN.md`, `ROADMAP.md`, and `docs/`.

<div align="center">
  <img src="assets/mlhiter-skills.svg" width="1000" alt="Visual overview of the mlhiter skills catalog">
</div>

## Skills

| Group | Skill | Use it when |
| :--- | :--- | :--- |
| Writing | [`logseq-writer`](skills/logseq-writer/SKILL.md) | Turning topics, drafts, and notes into practical Logseq-style tutorial articles. |
| Writing | [`intern-learning-recap`](skills/intern-learning-recap/SKILL.md) | Teaching interns the concepts and implementation path behind completed work. |
| Codex | [`think`](skills/think/SKILL.md) | Turning rough ideas into decision-complete plans before coding. |
| Codex | [`hunt`](skills/hunt/SKILL.md) | Finding root cause before fixing bugs, regressions, and broken behavior. |
| Codex | [`check`](skills/check/SKILL.md) | Reviewing completed changes with functional acceptance, adversarial review, and release gates. |
| Codex | [`first-principles-review`](skills/first-principles-review/SKILL.md) | Stress-testing plans, bugs, architecture, releases, or decisions from first principles. |
| Codex | [`codex-goal-builder`](skills/codex-goal-builder/SKILL.md) | Turning rough objectives into evidence-based Codex Goals. |
| Codex | [`codex-runner-creator`](skills/codex-runner-creator/SKILL.md) | Creating or repairing `.codex/environments/environment.toml` run actions. |
| Codex | [`workflow-packager`](skills/workflow-packager/SKILL.md) | Reviewing recent work evidence and recommending minimal reusable workflow assets. |
| Codex | [`quarterly-work-dashboard`](skills/quarterly-work-dashboard/SKILL.md) | Generating a leadership-facing quarterly dashboard from read-only GitHub and Feishu evidence. |
| Codex | [`git-commit-push`](skills/git-commit-push/SKILL.md) | Creating session-scoped Conventional Commits and safely pushing them. |
| Codex | [`pr-creator`](skills/pr-creator/SKILL.md) | Creating pull requests with template compliance and explicit fork/upstream head safety. |
| QA | [`issue-creator`](skills/issue-creator/SKILL.md) | Turning terse QA notes into structured GitHub issues with safe metadata handling. |
| Design | [`screenshot-interaction`](skills/screenshot-interaction/SKILL.md) | Inferring UI behavior and missing states from screenshots before implementation. |

## Provenance

Some skills are original playbooks from my own workflows. Some are adapted from, or inspired by, public skill repositories and engineering habits. Attribution is kept here so the lineage is explicit.

| Skill | Provenance |
| :--- | :--- |
| `think` | Adapted from [`tw93/Waza`](https://github.com/tw93/Waza)'s `think` workflow, then extended for Codex, durable context, first-principles planning, and Chinese workflow usage. |
| `hunt` | Adapted from [`tw93/Waza`](https://github.com/tw93/Waza)'s `hunt` workflow, then extended with first-principles root-cause gates, runtime evidence ladders, and local debugging failure patterns. |
| `check` | Adapted from [`tw93/Waza`](https://github.com/tw93/Waza)'s `check` workflow, then heavily extended with feature-intent risk modeling, functional acceptance, adversarial review, release gates, and specialist reviewers. |
| `first-principles-review` | Original extraction of the first-principles plus adversarial-review loop used across this repository. |
| `logseq-writer` | Original personal writing workflow for practical Logseq tutorial articles. |
| `workflow-packager` | Original workflow-mining playbook for turning repeated agent work into reusable skills, subagents, or automations. |
| `quarterly-work-dashboard` | Original dashboard-generation workflow for read-only GitHub and Feishu quarterly evidence. |
| `codex-goal-builder` | Original Codex Goal drafting workflow. |
| `codex-runner-creator` | Original Codex app environment-action workflow. |
| `git-commit-push` | Original session-scoped git commit and safe-push workflow, based on Conventional Commits. |
| `pr-creator` | Original PR-creation workflow focused on explicit fork/upstream head and base safety. |
| `intern-learning-recap` | Original intern-friendly teaching recap workflow. |
| `issue-creator` | Original QA issue drafting workflow for structured GitHub issue creation. |
| `screenshot-interaction` | Original screenshot-to-interaction-contract workflow, with interaction defaults informed by public accessibility and design-system conventions. |

External repositories such as [`mattpocock/skills`](https://github.com/mattpocock/skills) have also been reviewed as pattern sources, especially for tighter bug feedback loops and public-interface discipline, but the skills above are not wholesale copies of that repository.

## Install

Install all skills:

```bash
npx skills add mlhiter/skills --all
```

Install one skill:

```bash
npx skills add mlhiter/skills --skill logseq-writer
```

Preview the repository first:

```bash
npx skills add mlhiter/skills --list
```

## Repository layout

Skills are published under the canonical `skills/<skill-name>/SKILL.md` structure used by `skills.sh`. The root `AGENTS.md` documents the shared agent operating rules for this repository:

```text
AGENTS.md
PRODUCT.md
DESIGN.md
ROADMAP.md
docs/
  architecture.md
  ia.md
  references.md
  runbook.md
skills/
  logseq-writer/SKILL.md
  workflow-packager/SKILL.md
  quarterly-work-dashboard/SKILL.md
  first-principles-review/SKILL.md
  think/SKILL.md
  hunt/SKILL.md
  check/SKILL.md
  codex-goal-builder/SKILL.md
  codex-runner-creator/SKILL.md
  git-commit-push/SKILL.md
  intern-learning-recap/SKILL.md
  pr-creator/SKILL.md
  screenshot-interaction/SKILL.md
  issue-creator/SKILL.md
```

## Safety

These skills are instruction bundles. Read each `SKILL.md` before installing, especially skills that inspect local histories, write project files, or create automation assets.
