# Issue Body Template

Use this shape for Sealos QA issues. Keep sections concise and remove empty details when they add no value.

```markdown
## 环境

- 环境：<normalized environment or 未确认>
- 产品/模块：<product>
- 版本/批次：<milestone or 未确认>

## 问题描述

<one or two sentences describing what is wrong>

## 复现步骤

1. <step>
2. <step>
3. <step>

## 实际结果

<what happened>

## 预期结果

<what should happen>

## 影响判断

- Type: <Bug/Feature/Task>
- Priority: <P0/P1/P2>（<short reason>）
- Effort: <unset or suggested>

## 证据

<screenshots, logs, API URL, payload, response, recording links>
```

When the tester gives raw logs or API responses, preserve exact error codes and relevant request/response snippets, but redact secrets.
