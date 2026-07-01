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
