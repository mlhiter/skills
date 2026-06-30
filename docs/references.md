# References

## Repository Standards

- `skills.sh.json` uses the schema declared in the file itself: `https://skills.sh/schemas/skills.sh.schema.json`.
- Skill folders follow the `skills/<skill-name>/SKILL.md` publishing convention.
- Skill frontmatter must include at least `name` and `description`.

## Local Source Material

- `AGENTS.md`: global operating rules and closeout expectations.
- `skills/*/references/durable-context.md`: bundled memory and durable-context guidance used by lifecycle skills.
- `skills/check/references/project-context.md`: review context and release-gate template.
- `skills/check/references/persona-catalog.md`: specialist-review routing.

## External References

- `skills.sh`: public install and discovery surface for this repository.
- Codex skill conventions: skill metadata is the trigger surface; bundled resources should use progressive disclosure.

## Prior Art For This Change

The first-principles plus adversarial-review workflow was promoted into this repository as a reusable agent pattern:

- First-principles pass: identify invariant, source of truth, ownership boundary, assumptions, causal chain, and mechanism-level fix.
- Adversarial pass: attack malformed input, time skew, retries, concurrency, auth/tenant/path/shell/network sinks, cache fallback, package drift, deploy failure, and rollback.
