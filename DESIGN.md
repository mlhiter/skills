# Design

## Design Register

This repository uses an instruction-design register: precise, operational, and low-ceremony. The design surface is Markdown, skill frontmatter, and repository organization rather than a visual interface.

## Voice

- Direct and procedural.
- Short enough to load into an agent context without wasting tokens.
- Specific about trigger conditions, evidence, and stop conditions.
- Public-safe: avoid private paths, credentials, internal cluster names, and personal-only context.

## Visual Assets

- Keep README visuals lightweight and repo-local, preferably SVG under `assets/`.
- Use visuals as orientation, not as a second skill catalog. Show the core lifecycle or category shape; leave detailed skill lists to Markdown tables.
- Avoid dense cards, long descriptions, external image hosts, screenshots of private tools, and decorative imagery that does not clarify installation or skill selection.
- Verify generated SVGs render without clipped text or overlapping labels before committing.

## Skill Writing Principles

- Put trigger logic in frontmatter `description`; the body is loaded only after the skill triggers.
- Start with the outcome contract: what done means, what evidence is needed, and what output shape is expected.
- Prefer imperative workflow steps over essays.
- Keep reusable detail in `references/`, deterministic helpers in `scripts/`, and templates or static resources in `assets/`.
- Do not create auxiliary files inside a skill unless they directly support execution.

## Review Gates

- New skills must have valid YAML frontmatter with `name` and `description`.
- New references or scripts must be included in the skill folder and reachable from the instructions that mention them.
- Public documentation must mention newly published skills in both `README.md` and `skills.sh.json`.
- Workflow skills should include explicit safety boundaries, verification expectations, and residual-risk reporting.

## Anti-Patterns

- Generic advice that a strong model already knows.
- Long philosophical explanations without a concrete action.
- Private local facts promoted into public instructions.
- Broken relative references to rules, scripts, or bundled resources.
- Adding a new skill when a small extension to an existing lifecycle skill would do.
