# Runbook

## Install

Preview available skills:

```bash
npx skills add mlhiter/skills --list
```

Install every skill:

```bash
npx skills add mlhiter/skills --all
```

Install one skill:

```bash
npx skills add mlhiter/skills --skill <skill-name>
```

## Add Or Update A Skill

1. Create or edit `skills/<skill-name>/SKILL.md`.
2. Keep required bundled files under that skill directory.
3. Add the skill to `skills.sh.json`.
4. Add a short entry to `README.md`.
5. If the skill shares reusable guidance with other skills, bundle that guidance under each skill's `references/` directory unless single-skill installation is proven to include root-level shared files.

## Validation

Run these checks before committing:

```bash
python3 -m json.tool skills.sh.json >/tmp/skills-sh-json-ok
git diff --check
```

Check skill frontmatter:

```bash
find skills -name SKILL.md -maxdepth 3 -print | sort | while read f; do
  python3 - "$f" <<'PY'
import re, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
assert s.startswith("---\n"), p + " missing frontmatter"
end = s.find("\n---\n", 4)
assert end != -1, p + " unclosed frontmatter"
fm = s[4:end]
assert re.search(r"^name:\s*[^\n]+", fm, re.M), p + " missing name"
assert re.search(r"^description:\s*[^\n]+", fm, re.M), p + " missing description"
print(p + ": ok")
PY
done
```

If a skill includes scripts, compile or run the smallest safe check for each script. For Python helpers:

```bash
python3 -m py_compile skills/<skill-name>/scripts/*.py
```

## Runtime Sync

The repository is the durable source of truth. If a local agent runtime needs the change immediately, copy or reinstall the changed skill into that runtime after updating this repository.

Do not treat local runtime copies as the long-term source of truth.

## Publish

Commit and push only the files attributable to the current change. Before pushing, confirm:

- `git status --short --branch -uall` has no unrelated staged files.
- `skills.sh.json` lists only skills that exist.
- `README.md` and `skills.sh.json` agree on added, removed, or renamed skills.
- New references and scripts are tracked by git.
