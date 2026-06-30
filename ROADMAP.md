# Roadmap

## Current Focus

- Keep the Codex workflow lifecycle coherent: `think` for planning, `hunt` for root-cause diagnosis, `check` for acceptance and adversarial review, `neat-freak` for knowledge sync, and `git-commit-push` for safe publication.
- Maintain this repository as the durable public source for reusable personal skills.
- Keep install and discovery paths simple through `skills.sh.json` and `README.md`.

## Near-Term Priorities

1. Add lightweight validation for skill frontmatter, broken relative references, executable scripts, and `skills.sh.json` discovery.
2. Keep `check`, `hunt`, and `think` aligned with the first-principles plus adversarial-review workflow as real usage reveals gaps.
3. Add `agents/openai.yaml` metadata to newly promoted skills when it materially improves UI discovery.
4. Review public docs after each new skill to keep private machine context out of the repo.

## Later

- Add examples only for skills whose behavior is hard to infer from the instructions.
- Add small deterministic scripts when repeated manual validation becomes error-prone.
- Split large skills only when their body becomes too broad for progressive disclosure.

## Out Of Scope

- Project-specific deployment runbooks for unrelated repositories.
- Private memories or rollout transcripts.
- Generated docs that do not help installation, review, or skill maintenance.
