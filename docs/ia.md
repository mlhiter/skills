# Information Architecture

## Top-Level Documents

- `README.md`: what this repository contains and how to install skills.
- `PRODUCT.md`: product scope, users, core scenarios, and non-goals.
- `DESIGN.md`: instruction design standards for skills and documentation.
- `ROADMAP.md`: current priorities and out-of-scope work.
- `AGENTS.md`: operating rules for agents editing this repository.

## Skill Catalog

Skills are grouped in `skills.sh.json` for discovery:

- Writing: prose and publishing workflows.
- Codex: planning, debugging, review, git, PR, and workflow packaging.
- QA: issue creation and testing artifacts.
- Design: screenshot interpretation and UI contract extraction.

## Skill Directories

Every skill directory should answer three questions quickly:

- When should this skill trigger?
- What is the outcome contract?
- What evidence or verification is required before sign-off?

If the answer requires detail, put the detail in `references/` and link it from `SKILL.md`.

## Shared Rule References

Reusable guidance shared by more than one skill should still be bundled inside each published skill when single-skill installation must work. Prefer `skills/<skill-name>/references/<rule>.md` unless the installer is proven to include root-level files.
