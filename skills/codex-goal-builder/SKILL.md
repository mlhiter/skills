---
name: codex-goal-builder
description: Build strong Codex Goals from rough user objectives. Use when the user asks to create, write, generate, improve, expand, or refine a Codex `/goal`; mentions Codex Goals, goal mode, persistent objectives, "持续执行", "扩充目标", "生成 goal", "keep working until", or wants Codex to ask clarifying questions before starting a long-running objective. Helps draft evidence-based goal text and may start a goal only after explicit user approval.
---

# Codex Goal Builder

Turn a rough objective into a thread-scoped Codex Goal with a measurable finish line, concrete evidence, safe boundaries, and an honest blocked condition.

## Core Rule

Do not start a Goal merely because the user describes work. Draft and refine first. Call `create_goal` only when the user explicitly asks to start/create/activate the Goal or approves the final draft.

If an active Goal may already exist, call `get_goal` before creating another one.

## Workflow

1. Capture the user's rough objective in one sentence.
2. Decide whether a Goal is appropriate.
   - Use a Goal for multi-step work with a durable objective, uncertain path, and evidence-based completion.
   - Prefer a normal prompt for one-line edits, simple explanations, short reviews, or tasks with no durable finish line.
3. Draft a stronger Goal using this contract:

```text
<desired end state>, verified by <specific evidence>, while preserving <constraints>. Use <allowed inputs/tools/boundaries>. Between iterations, <how to choose and record the next action>. If blocked, budget-limited, or no defensible path remains, stop with <evidence gathered, attempted paths, blocker, and next input needed>.
```

4. Ask only the missing high-leverage questions.
   - Ask 1-3 questions at a time.
   - Infer safe defaults when the answer is obvious from repo context or the user's wording.
   - Prefer questions about evidence, constraints, and boundaries over vague preference questions.
5. Produce a final Goal in one of these forms:
   - CLI text: `/goal ...`
   - Active tool call: `create_goal(objective=...)`, only after explicit approval.
6. If the user provides a token budget, pass it to `create_goal`. Otherwise omit it.

## Goal Checklist

Every final Goal should cover:

- Outcome: what must be true when done.
- Verification surface: tests, benchmarks, logs, screenshots, artifacts, reports, or source evidence.
- Constraints: behavior, API, data, security, design, performance, or compatibility that must not regress.
- Boundaries: allowed repositories, files, commands, environments, services, or data sources.
- Iteration policy: how Codex should choose the next attempt after each result.
- Blocked stop condition: what counts as honestly blocked and what to report.

## Question Strategy

Start from the most incomplete part of the checklist:

- Missing verification: "What command, artifact, metric, or evidence should prove this is done?"
- Missing constraints: "What must not change while Codex works on this?"
- Missing boundaries: "Which repo/files/environment may Codex touch or inspect?"
- Missing blocked condition: "If this cannot be completed, what should the final report include?"

Avoid asking for all six fields if the user gave enough signal. Most rough goals need only verification and constraints.

## Output Style

When drafting in Chinese, keep the explanation short and put the usable `/goal` command in a fenced `text` block.

When the user wants iteration, show:

- "当前草案"
- "还差的问题"
- "确认后可启动"

When the user says "直接创建", "启动这个 goal", or otherwise approves, briefly state what is being started and call `create_goal`.

## Safety

- Remember that Codex Goals are thread-scoped persistent objectives, not global memory or project instructions.
- Never represent a budget limit as success.
- Never mark a Goal complete unless concrete evidence satisfies the objective.
- Do not use `update_goal` to rewrite, pause, resume, or clear Goals; those lifecycle controls belong to the user or system.
- For live systems, database writes, production deployment, payments, account changes, or destructive operations, include explicit boundaries and require explicit user approval before action.

## References

Read `references/goal-patterns.md` when the rough objective is broad, research-heavy, deployment-related, or needs task-type-specific examples.
