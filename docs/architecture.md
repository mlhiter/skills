# Architecture

## Repository Shape

```text
AGENTS.md
PRODUCT.md
DESIGN.md
ROADMAP.md
README.md
skills.sh.json
skills/
  <skill-name>/
    SKILL.md
    references/
    scripts/
    assets/
```

`skills.sh.json` is the catalog index. `README.md` is the human entrypoint. `AGENTS.md` is the agent operating guide for working in this repository.

## Skill Anatomy

Each skill is a self-contained directory. `SKILL.md` is required and must include frontmatter with `name` and `description`.

Optional bundled resources are local to the skill:

- `references/` for longer instructions that should be loaded only when needed.
- `scripts/` for deterministic helpers and validation scripts.
- `assets/` for templates or static files used as output material.
- `agents/` for optional UI metadata.

## Shared Rules

Shared reusable guidance should be copied into each skill that needs it when the skill must support single-skill installation. A root-level shared rule file is only appropriate if the packaging and install tool are proven to include it for single-skill installs.

`think`, `hunt`, and `check` each bundle `references/durable-context.md` so they work when installed individually.

## Lifecycle Skills

The main engineering lifecycle is:

1. `think`: plan from first principles before building.
2. `hunt`: diagnose root cause before fixing.
3. `check`: review the completed change with functional acceptance and adversarial gates.
4. `neat-freak`: sync durable project knowledge after meaningful changes.
5. `git-commit-push`: publish the session-scoped change safely.

`first-principles-review` is the standalone entrypoint when the user asks directly for a first-principles plus adversarial pass.

## Source And Runtime Boundary

This repository is the durable source of truth. Installed runtime copies under an agent home directory can be patched for immediate local use, but those patches should be promoted back here before relying on them long-term.

When updating a skill that is already installed locally, update the repository first, then sync the local runtime copy if immediate availability is needed.
