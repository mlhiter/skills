---
name: git-commit-push
description: 'Execute git commit-and-push workflows with conventional commit message analysis, session-scoped staging, logical change grouping, and safe publication to the tracked remote branch. Use when the user asks to commit changes, commit and push, push committed work, publish local changes, or mentions "/commit". Supports auto-detecting type/scope, generating conventional commit messages from diffs, avoiding unrelated dirty worktree changes, splitting independent work into multiple clean commits, and pushing after commit when safety checks pass.'
license: MIT
allowed-tools: Bash
---

# Git Commit and Push with Conventional Commits

Create standardized, semantic git commits using the Conventional Commits specification, then publish the new commit(s) to the tracked remote branch when the safe-push checks pass. Analyze the actual diff to determine appropriate type, scope, and message.

## Conventional Commit Format

```text
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Commit Types

| Type       | Purpose                        |
| ---------- | ------------------------------ |
| `feat`     | New feature                    |
| `fix`      | Bug fix                        |
| `docs`     | Documentation only             |
| `style`    | Formatting/style (no logic)    |
| `refactor` | Code refactor (no feature/fix) |
| `perf`     | Performance improvement        |
| `test`     | Add/update tests               |
| `build`    | Build system/dependencies      |
| `ci`       | CI/config changes              |
| `chore`    | Maintenance/misc               |
| `revert`   | Revert commit                  |

## Breaking Changes

```text
# Exclamation mark after type/scope
feat!: remove deprecated endpoint

# BREAKING CHANGE footer
feat: allow config to extend other configs

BREAKING CHANGE: `extends` key behavior changed
```

## Workflow

### 1. Analyze Diff

```bash
# If files are staged, use staged diff
git diff --staged

# If nothing staged, use working tree diff
git diff

# Also check status
git status --porcelain
```

### 2. Establish Session Scope

In a shared or already-dirty worktree, interpret a request like "commit code", "提交代码", or `/commit` as "commit the changes attributable to this conversation/session". Do not stage or commit unrelated work from other sessions just because it is present in the current git worktree.

Before grouping commits, identify the session-scoped candidate set:

- Include files and hunks edited by the current session.
- Include files the user explicitly asked this session to change.
- Include generated files, lockfiles, migrations, snapshots, or docs that were produced by commands in this session and belong to the same change.
- Include pre-existing staged changes only if they clearly belong to this session or the user explicitly says to keep them.
- Exclude dirty files, untracked files, and staged changes that were not touched or requested in this session, unless the user explicitly asks to commit the whole worktree.

Use status and diff inspection to separate ownership:

```bash
git status --short
git diff --name-status
git diff --staged --name-status
git ls-files --others --exclude-standard
```

When the worktree contains out-of-scope changes, leave them unstaged and mention them in the final response as intentionally not committed. If a file contains both in-scope and out-of-scope hunks, use precise staging such as `git add -p`, `git apply --cached`, or an equivalent patch-based method. If hunk ownership is still ambiguous after inspection and committing could capture another session's work, ask the user for confirmation instead of broad-staging.

Only commit the entire dirty worktree when the user explicitly says so, for example "commit all changes", "提交整个工作区", "把所有改动都提交", or after the user confirms the broader scope.

### 3. Split Into Logical Commit Groups

Default to creating multiple commits when the diff contains multiple independent features, fixes, refactors, docs changes, tests, config changes, or generated artifacts. A user request such as "commit code", "提交代码", or `/commit` means "commit all appropriate changes as clean logical commits", not "force everything into one commit".

Before staging, inspect the session-scoped candidate set, then decide commit groups by behavior and ownership:

- Keep one logical change per commit.
- Separate unrelated features, fixes, refactors, docs, tests, build/CI, and formatting-only changes.
- Keep tests with the code they verify when they belong to the same behavioral change.
- Keep generated lockfiles, migrations, schema snapshots, and build metadata with the source/config change that produced them.
- Do not split files mechanically when a single file contains one coherent change.
- If unrelated changes are mixed inside one file, prefer `git add -p` or another precise staging method.
- If the safe grouping is unclear, inspect more context and make the smallest defensible grouping; ask only when committing risks including user work, secrets, or an unintended change.
- Use a single commit only when the whole diff is genuinely one logical change or the user explicitly asks for one commit.

### 4. Stage Files

If nothing is staged or you want to group changes differently:

```bash
# Stage specific files
git add path/to/file1 path/to/file2

# Stage by pattern
git add '*.test.*'
git add src/components/*

# Interactive staging
git add -p
```

Never commit secrets such as `.env`, `credentials.json`, private keys, tokens, or local credentials.

### 5. Generate Commit Message

Analyze the diff to determine:

- **Type**: What kind of change is this?
- **Scope**: What area/module is affected?
- **Description**: One-line summary of what changed, in present tense and imperative mood, ideally under 72 characters.

### 6. Execute Commit

```bash
# Single line
git commit -m "<type>[scope]: <description>"

# Multi-line with body/footer
git commit -m "$(cat <<'EOF'
<type>[scope]: <description>

<optional body>

<optional footer>
EOF
)"
```

### 7. Push When Safe

After all session-scoped commits are created, push them automatically when the repository has a clear upstream and the push can be done without destructive or surprising behavior. Treat a commit-only result as incomplete unless the user explicitly asked not to push or a safety blocker prevents publication.

Before pushing, inspect the current branch and upstream:

```bash
git status --short --branch
git branch --show-current
git branch -vv
```

Push automatically only when all of these are true:

- The user did not explicitly say not to push.
- The current branch has a configured upstream, or the push target is obvious from the user's request.
- The push is a normal fast-forward publication of the commits just created.
- The command does not require force, lease-force, deleting refs, changing remotes, changing git config, or bypassing hooks.
- There are no uncommitted in-scope changes left from the current session.

Use the tracked upstream when it exists:

```bash
git push
```

If the branch has no upstream but the intended remote is obvious and safe, set the upstream while pushing:

```bash
git push -u origin "$(git branch --show-current)"
```

If `git push` fails because the remote has new commits, try the safe update path once:

```bash
git fetch origin "$(git branch --show-current)"
git rebase "origin/$(git branch --show-current)"
git push
```

Stop and report the blocker instead of pushing when the branch has diverged, rebase conflicts occur, the target branch is protected, credentials are unavailable, the remote is ambiguous, or the push would require force. Never force-push unless the user explicitly asks for that exact operation.

## Best Practices

- Default to committing only the current session's attributable changes in dirty shared worktrees.
- Default to multiple decoupled commits when multiple logical changes are present.
- After committing, default to pushing the new commit(s) when the safe-push checks pass.
- Present tense: "add" not "added".
- Imperative mood: "fix bug" not "fixes bug".
- Reference issues when relevant, such as `Closes #123` or `Refs #456`.
- Keep the description concise, ideally under 72 characters.

## Git Safety Protocol

- Never update git config.
- Never run destructive commands such as `--force` or hard reset without explicit request.
- Never skip hooks with `--no-verify` unless the user asks.
- Never force-push to `main` or `master`.
- Never push when the target remote or branch is ambiguous.
- If commit fails due to hooks, fix the issue and create a new commit instead of amending by default.
