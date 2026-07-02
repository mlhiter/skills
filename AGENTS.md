# AGENTS.md

Project-level instructions for agents working in this repository.

This file is active guidance for `mlhiter/skills`. The shareable global agents template lives at `templates/global/AGENTS.md`; do not treat that template as project-level guidance for this repository.

## Repository Rules

- This repository is an instruction-only asset catalog, not an application codebase.
- Keep published instructions public-safe: no credentials, private registry URLs, private cluster names, personal machine paths, or one-off project facts.
- Put skills under `skills/<skill-name>/SKILL.md`; keep bundled references, scripts, and assets inside the owning skill directory.
- Put reusable templates under `templates/<template-name>/`.
- Update `skills.sh.json` when installable skills are added, removed, or renamed.
- Do not add non-installable templates to `skills.sh.json` unless the user explicitly asks for that catalog behavior.
- Update both `README.md` and `README.zh-CN.md` when a skill or template should be discoverable by users.
- Keep `templates/global/AGENTS.md` sanitized for public use.

## Documentation Scope

- Do not create generic product docs such as `PRODUCT.md`, `DESIGN.md`, `ROADMAP.md`, or a top-level `docs/` folder just to satisfy a software-project template.
- This repository's durable context belongs in this file, the two README files, `skills.sh.json`, and the owning skill or template directories.

## Suggested Checks

Run these before publishing documentation or catalog metadata changes:

```bash
python3 -m json.tool skills.sh.json >/dev/null
git diff --check
```
