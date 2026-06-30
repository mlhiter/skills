# Skills

[![skills.sh](https://skills.sh/b/mlhiter/skills)](https://skills.sh/mlhiter/skills)

Reusable agent skills for practical writing, workflow packaging, Codex goal drafting, and Codex app run actions.

This repository also includes a sanitized root `AGENTS.md` derived from my global Codex instructions, with private registry and cluster details replaced by placeholders.

For maintainers, the project context lives in `PRODUCT.md`, `DESIGN.md`, `ROADMAP.md`, and `docs/`.

## Skills

- `logseq-writer` - turns topics, drafts, and notes into practical Logseq-style tutorial articles.
- `workflow-packager` - reviews recent work evidence and recommends minimal reusable workflow assets.
- `first-principles-review` - runs a first-principles diagnosis plus adversarial stress review for plans, bugs, releases, and decisions.
- `think` - turns rough ideas into decision-complete plans, now with a first-principles pass for non-trivial work.
- `hunt` - finds root cause before fixing bugs, now with a first-principles root-cause gate.
- `check` - reviews completed changes with feature-intent risk modeling, functional acceptance, adversarial review, and release gates.
- `codex-goal-builder` - turns rough objectives into evidence-based Codex Goals.
- `codex-runner-creator` - creates or repairs `.codex/environments/environment.toml` run actions.
- `git-commit-push` - creates session-scoped Conventional Commits and safely pushes the new commit(s) to the tracked remote branch.
- `intern-learning-recap` - turns completed work into intern-friendly learning recaps while avoiding repeated explanations via a local knowledge ledger.
- `pr-creator` - creates pull requests with template compliance and explicit fork/upstream head safety.
- `screenshot-interaction` - infers UI behavior and missing states from screenshots before implementation.
- `issue-creator` - turns terse QA notes into structured GitHub issues with gh preflight, safe metadata, and sensitive-info checks.

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
