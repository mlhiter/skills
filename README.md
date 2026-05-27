# Skills

Reusable agent skills for practical writing, workflow packaging, Codex goal drafting, and Codex app run actions.

## Skills

- `logseq-writer` - turns topics, drafts, and notes into practical Logseq-style tutorial articles.
- `workflow-packager` - reviews recent work evidence and recommends minimal reusable workflow assets.
- `codex-goal-builder` - turns rough objectives into evidence-based Codex Goals.
- `codex-runner-creator` - creates or repairs `.codex/environments/environment.toml` run actions.
- `screenshot-interaction` - infers UI behavior and missing states from screenshots before implementation.

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

## Safety

These skills are instruction bundles. Read each `SKILL.md` before installing, especially skills that inspect local histories, write project files, or create automation assets.
