# Product

## Definition

This repository publishes reusable agent skills for Codex-compatible environments through the `skills.sh` repository layout.

The product is not an application UI. It is an installable skill catalog whose value is better agent behavior: safer git workflows, stronger planning, root-cause debugging, review gates, issue creation, screenshot interpretation, quarterly dashboard reporting, and reusable workflow packaging.

## Register

product

## Users

- Maintainers who want one public, installable source of truth for personal agent skills.
- Codex agents that need concise, task-specific operating procedures.
- Other developers or teammates who want to install a single skill or inspect the workflow rules before using them.

## Core Scenarios

- Install all skills with `npx skills add mlhiter/skills --all`.
- Install a single skill with `npx skills add mlhiter/skills --skill <name>`.
- Use `think`, `hunt`, and `check` as a lifecycle: plan from first principles, diagnose before fixing, then review completed changes through feature-intent risk modeling, functional acceptance, and adversarial gates.
- Use `first-principles-review` directly when the user asks for a focused first-principles plus adversarial pass.
- Use `quarterly-work-dashboard` to generate a local leadership-facing HTML dashboard from read-only GitHub and Feishu quarterly evidence.
- Keep public repository guidance sanitized so private registries, cluster names, and local-only paths do not leak into the published catalog.

## Product Decisions

- Skills live under `skills/<skill-name>/SKILL.md`.
- Each skill must be useful from its frontmatter alone: `name` and `description` are the trigger surface.
- Bundled resources belong next to the skill that uses them.
- Shared reusable rules live under `rules/` and must stay public-safe.
- `README.md` and `skills.sh.json` are the discovery surface and must be updated whenever a skill is added, removed, or renamed.

## Non-Goals

- This repository is not a private memory dump.
- This repository is not a place for project-specific commands from unrelated products.
- This repository does not publish credentials, private cluster details, local machine paths, or one-off rollout reports.
