# Goal Patterns

Use this file for examples and task-type question banks. Keep final Goals compact; do not paste every field if it repeats the same idea.

## Strong Goal Shape

```text
/goal <outcome>, verified by <evidence>, while preserving <constraints>. Use <boundaries>. Between iterations, <iteration policy>. If blocked or budget-limited, stop with <attempts, evidence, blocker, and next input needed>.
```

## Code Bug Or Flaky Test

Draft:

```text
/goal Fix <failure> on the current branch, verified by <repro/test command>, while preserving existing public behavior and related tests. Use the affected package, nearby tests, and logs from the failing path. Between iterations, state the observed failure, the hypothesis tested, the change made, and the next smallest check. If the failure cannot be reproduced or no defensible fix remains, stop with attempted repros, evidence gathered, the blocker, and the next input needed.
```

Ask if missing:

- What exact command or scenario reproduces the failure?
- Which behavior or API must not change?
- Is there a branch, issue, log, or screenshot that defines the failing path?

## Performance Optimization

Draft:

```text
/goal Reduce <metric> below <threshold>, verified by <benchmark/profiling command>, while keeping <correctness suite> green and preserving the public API. Use only the relevant hot path, benchmark fixtures, and related tests. Between iterations, record the measurement, the suspected bottleneck, the change, and the next experiment. If the benchmark cannot run or the threshold is not reachable under current constraints, stop with the measurements, attempted paths, blocker, and next input needed.
```

Ask if missing:

- What metric and threshold define success?
- What benchmark or profiling command should be trusted?
- What correctness checks must stay green?

## Refactor Or Migration

Draft:

```text
/goal Complete <migration/refactor scope>, verified by <tests/build/typecheck/search checks>, while preserving user-facing behavior and compatibility constraints. Use <allowed modules> and avoid unrelated cleanup. Between iterations, migrate one coherent slice, run the relevant check, and choose the next slice from remaining references. If blocked, stop with the unmigrated surface, failed checks, blocker, and next input needed.
```

Ask if missing:

- What is in scope and explicitly out of scope?
- Which checks prove compatibility?
- Should Codex prioritize smallest safe slices or complete coverage in one pass?

## Research Or Audit

Draft:

```text
/goal Produce an evidence-backed <report/audit/reproduction> for <topic>, using <allowed sources/materials>. Verify each major claim against primary evidence where possible, and end with an artifact that separates confirmed findings, approximate/proxy support, blocked claims, and remaining uncertainty. Between iterations, build the claim inventory, map claims to evidence, investigate the highest-uncertainty item, and update the audit trail. If key evidence is unavailable, stop with the search paths tried, source gaps, and what would unlock stronger conclusions.
```

Ask if missing:

- What sources are allowed or authoritative?
- What final artifact should be produced?
- How should partial evidence or uncertainty be labeled?

## Documentation Or Generated Artifact

Draft:

```text
/goal Produce <artifact>, verified by <build/render/lint/review check>, while matching <style/source-of-truth constraints>. Use <source files/references> and avoid inventing unsupported claims. Between iterations, draft the smallest complete version, verify it, then tighten gaps against the source material. If blocked, stop with missing inputs, attempted checks, and the next decision needed.
```

Ask if missing:

- What file or artifact should exist at the end?
- What source material is authoritative?
- What check proves it renders/builds/reads correctly?

## Deployment Or Operations

Draft:

```text
/goal Deploy or repair <service/environment>, verified by <rollout status/health check/API/screenshot/log evidence>, while preserving rollback ability and avoiding unapproved data or production-risk changes. Use <cluster/namespace/repo/registry boundaries>. Between iterations, inspect current state, make the smallest reversible change, verify health, and record rollback notes. If blocked, stop with live state, commands run, evidence, risk, and the approval or credential needed.
```

Ask if missing:

- Which environment, namespace, or service is in scope?
- What health check proves success?
- What operations are forbidden without explicit approval?

## Active Goal Tooling

If `create_goal` is available and approved:

- Use the full objective text, without the leading `/goal`.
- Include token budget only when the user gives one.
- Do not call `create_goal` if another active Goal exists unless the user has cleared it or asked to replace it and the tool supports that replacement.

If only text output is appropriate, return the final command:

```text
/goal ...
```
