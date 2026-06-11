---
name: intern-learning-recap
description: Use this skill after completing any coding, debugging, deployment, documentation, design, or analysis task when the user wants an intern-friendly learning recap. It summarizes the real implementation process, extracts the technical concepts and knowledge points involved, teaches them in vivid but lightweight blocks, and maintains a local knowledge ledger to avoid repeatedly explaining concepts interns already know. Trigger on requests like 实习生学习, 技术点总结, 知识点复盘, 任务结束教学, learning recap, mentor recap, or teach interns what we just did.
---

# Intern Learning Recap

## Purpose

Turn completed work into a short teaching recap for interns. Base the recap on what actually happened in the task, not a generic tutorial.

The output should help interns answer:

- What problem were we solving?
- What did we change or verify?
- Which technical ideas showed up?
- How can I explain those ideas at a high level?
- What should I look up next if I want to go deeper?

It should also avoid repeatedly teaching the same concept. Use the knowledge ledger below to remember which concepts have already been explained and how familiar they should be.

## When To Use

Use this skill near the end of a completed task when the user asks for a learning-oriented summary, or when the user has established that this skill should run after task completion.

Good triggers:

- "总结一下这次实现里的技术点"
- "给实习生讲一下"
- "任务做完后做个知识点复盘"
- "用块的形式教给实习生"
- "make an intern-friendly recap"
- "mentor recap"

Do not use it for ordinary final summaries unless the user wants a teaching artifact.

## Recap Workflow

1. Reconstruct the real task path.
   - Identify the user's goal, the important files/modules/tools touched, and the verification performed.
   - If the task involved investigation, include the key evidence path rather than only the final fix.

2. Check the knowledge ledger.
   - Default path: `~/.codex/state/intern-learning-recap/ledger.md`.
   - If the file exists, read it before choosing teaching blocks.
   - If the file does not exist, create it only after producing the recap and only when there is at least one useful concept to persist.
   - Do not fail the recap if the ledger cannot be read or written. Say briefly that persistence was skipped.

3. Pick 3 to 6 teaching blocks.
   - Each block should be one coherent concept from the actual work.
   - Prefer concepts that explain why the implementation was shaped that way.
   - Avoid stuffing in every minor API, import, or command.
   - Prefer new concepts, new angles on known concepts, and concepts that were important to this task.

4. Teach at intern depth.
   - Assume the intern knows basic programming but may not know this codebase, framework, or operational context.
   - Explain with concrete analogies only when they clarify the idea.
   - Keep it lively, but do not become cute at the expense of accuracy.
   - Do not dive into exhaustive internals unless the user asks.

5. Tie every concept back to the task.
   - Each block should say where the idea appeared in the implementation.
   - Mention representative files, commands, routes, components, or modules when useful.

6. Update the knowledge ledger after the recap.
   - Add new concept cards.
   - Update `last_used`, `times_mentioned`, `familiarity`, and `angles_covered` for existing cards.
   - Persist concepts, not task logs. The ledger is a map of reusable knowledge, not a diary.

7. End with a light learning path.
   - Add 2 to 4 "next things to understand" that would deepen the intern's knowledge.
   - Keep them practical and connected to the task.

## Knowledge Ledger

The ledger prevents annoying repetition across tasks and sessions.

Default ledger file:

```text
~/.codex/state/intern-learning-recap/ledger.md
```

Create parent directories if needed. Keep the file human-readable Markdown.

### Concept Card Format

Use one card per reusable concept:

```markdown
### <stable-concept-id>
- name: <human readable concept name>
- scope: global | project:<name> | repo:<absolute-or-short-path>
- familiarity: new | seen | familiar | owned
- first_taught: YYYY-MM-DD
- last_used: YYYY-MM-DD
- times_mentioned: <number>
- angles_covered: <short comma-separated angles>
- next_revisit_when: <when this concept deserves explanation again>
- notes: <one concise sentence, no secrets>
```

Stable concept IDs should be lowercase hyphen-case, such as `skill-frontmatter-triggering`, `linux-amd64-image-builds`, or `react-controlled-state`.

### Familiarity Rules

- `new`: not taught before. Give a normal teaching block.
- `seen`: taught once. Teach only if central to this task, and keep it shorter.
- `familiar`: taught multiple times. Usually mention as "已知，不展开" unless this task adds a new angle.
- `owned`: the intern should already recognize it. Skip by default unless the user asks, the concept caused a mistake, or there is a genuinely new pitfall.

Promote familiarity conservatively:

- `new` becomes `seen` after the first real teaching block.
- `seen` becomes `familiar` after it has appeared in multiple tasks or angles.
- `familiar` becomes `owned` only when it has been repeated enough that expanding it would be noise.

### What To Persist

Persist:

- Reusable engineering concepts.
- Debugging patterns.
- Deployment and verification lessons.
- Framework or tool concepts that are likely to recur.
- Product/design reasoning patterns that help future work.

Do not persist:

- Secrets, tokens, raw credentials, private keys, or full environment variable values.
- One-off command logs.
- Every file changed in a task.
- User-private business details that are not needed for teaching.
- Concepts so broad that they are useless, such as "programming" or "frontend".

### Deduplication Rule

Deduplicate by concept plus teaching angle, not by exact wording.

Example: `Docker image` can have separate useful angles like build context, multi-stage builds, platform architecture, and registry push. But if the same task only repeats why `linux/amd64` matters, treat it as already known and do not expand it again.

## Output Shape

Default language: match the user's language. For Chinese users, use Simplified Chinese.

Keep the output readable and compact. A good default structure is:

```markdown
**给实习生的复盘**

这次任务本质上是在做：...

**本次新增/值得展开**

**1. 知识块：<concept name>**
一句话讲清楚：...
这次怎么用到：...
可以这样理解：...

**2. 知识块：<concept name>**
一句话讲清楚：...
这次怎么用到：...
可以这样理解：...

**已知但这次不展开**
- <concept>: 之前讲过，本次只是用到。

**他们应该带走什么**
- ...
- ...

**后续可以浅浅补一下**
- ...
- ...

**知识账本更新**
- 新增：...
- 更新：...
- 跳过：...
```

For very small tasks, use 1 to 3 blocks and skip any section that would feel forced.

For larger engineering tasks, use this richer structure:

```markdown
**给实习生的复盘**

**先看全局**
...

**本次新增/值得展开**

**知识块 1：<concept>**
- 一句话：...
- 任务里的位置：...
- 为什么重要：...
- 容易误解：...

**知识块 2：<concept>**
...

**把整件事串起来**
...

**已知但不展开**
- ...

**后续学习路线**
- ...

**知识账本更新**
- ...
```

## Teaching Style

Prefer:

- "这次我们先确认问题在哪里，再改最小的一处，因为..."
- "可以把它理解成..."
- "这里真正重要的不是命令本身，而是..."
- "实习生需要记住的判断方式是..."

Avoid:

- Generic textbook definitions disconnected from the task.
- Overclaiming that interns now "掌握" a complex topic.
- Turning the recap into a full tutorial.
- Listing every file changed without explaining the idea.
- Mentioning hidden chain-of-thought or internal reasoning.
- Re-explaining familiar concepts just because they appeared again.

## Content Rules

- Be concrete about what was done, but do not expose secrets, tokens, private credentials, or sensitive environment details.
- If verification failed or was skipped, say that plainly and frame it as a learning point.
- If there was no code change, still teach the investigation method, source-reading path, or decision framework.
- If the work involved a bug, include the debugging lesson: symptom, root cause, fix, and prevention.
- If the work involved deployment, include the operational lesson: build target, rollout, runtime verification, and rollback or safety checks when relevant.
- If the work involved frontend/UI, include the product/design lesson: user goal, interaction, state, layout constraints, and visual verification.
- If the ledger marks an important concept as `familiar` or `owned`, mention it briefly only when needed to connect the story.

## Quality Bar

The recap is successful when an intern can retell the task in 2 minutes, name the main technical ideas, and know what to read next without pretending to be an expert.
