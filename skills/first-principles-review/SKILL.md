---
name: first-principles-review
description: "Run a first-principles and adversarial review for plans, code changes, bugs, architecture, product decisions, documents, workflows, or operational risks. Use when users ask 从第一性原理出发, 对抗式审查, adversarial review, first principles, 深挖根因, 挑毛病, 找盲区, or want an independent stress test before building, shipping, publishing, or deciding."
---

# First-Principles Review

Use this skill when the user wants the two-step thinking loop as the main deliverable, or when an existing workflow needs a focused independent pass.

## Outcome Contract

- Outcome: the user gets a mechanism-level recommendation plus a concrete adversarial risk pass.
- Done when: the answer identifies the source of truth, core invariant, assumptions, failure modes, and the minimal next verification or fix.
- Evidence: current files, docs, logs, artifacts, commands, screenshots, fetched source, or clearly labeled reasoning-only assumptions.
- Output: concise recommendation, assumptions, attack paths, and next checks.

## Step 1: First-Principles Pass

Strip away analogies and inherited defaults.

Answer these in order:

1. What invariant, user outcome, or business result must be preserved?
2. What is the source of truth, and which boundary owns it?
3. What are the lowest-level facts we actually know from evidence?
4. Which assumptions are unverified, copied from precedent, or convenient but fragile?
5. What causal chain connects the decision or input to the observable result?
6. What is the smallest mechanism-level change, decision, or check that addresses the cause?

If the first answer is just "do what similar systems do", keep going until the mechanism is clear. If evidence is missing, say what evidence would change the conclusion.

## Step 2: Adversarial Review

Attack the result from the opposite side.

Pick the relevant surfaces:

- malformed or oversized input
- time skew, retries, duplicate delivery, cancellation, and partial failure
- concurrency, ordering, and cache fallback
- auth, tenant, workspace, permissions, path, shell, network, and secret boundaries
- dependency, deployment, package, generated artifact, and rollback drift
- user misunderstanding, empty state, locale, accessibility, and operational handoff

For each relevant surface, write:

- **Attack**: what would break this?
- **Path**: entrypoint -> validation -> authority check -> sink or state -> observable bad outcome.
- **Evidence**: command, file, artifact, or explicit assumption.
- **Disposition**: fix now, verify now, document residual risk, or out of scope.

Use subagents when the task is large, high-risk, or asks for multi-agent adversarial review. Give each subagent a narrow surface and verify their findings before reporting.

## Output Shape

For direct conversation:

```text
First-principles conclusion: ...

Core invariant: ...
Source of truth: ...
Fragile assumptions: ...

Adversarial findings:
1. [severity] attack path -> disposition
2. ...

Next verification:
- ...
```

For code or release work, feed the findings into `hunt` before fixing and `check` before shipping. Do not let this skill replace the repository's real tests, runtime checks, or release gates.
