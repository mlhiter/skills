<!-- prettier-ignore -->
<div align="center">

<img src="assets/mlhiter-skills.svg" width="820" alt="mlhiter skills 资产目录概览" />

# mlhiter skills

可复用的 Codex agent 技能和模板，覆盖规划、调试、审查、写作、工作流打包和安全收尾。

[![skills.sh](https://skills.sh/b/mlhiter/skills)](https://skills.sh/mlhiter/skills)

[在 skills.sh 浏览](https://skills.sh/mlhiter/skills) | [安装](#安装) | [资产目录](#资产目录) | [维护这个目录](#维护这个目录)

语言：[zh](README.zh-CN.md) | [en](README.md)

</div>

`mlhiter/skills` 是一个公开的可安装 agent 技能和可复用 agent 模板目录。每个技能都是一个可移植的指令包，放在 `skills/<skill-name>/SKILL.md`，对应的参考资料、脚本和资源都放在该技能自己的目录里。

当你希望 Codex 遵循一套稳定工作流，而不是只靠一次性提示词时，可以用这个仓库：先想清楚一个功能、追查回归原因、发布前审查、创建干净的提交、把重复工作打包成可复用技能、借用一份适合公开分享的全局 `AGENTS.md` 基线，或者把粗糙笔记整理成有用的产物。

> [!IMPORTANT]
> 这是一个纯指令型资产目录，不是应用代码库。公开内容必须保持安全：不要写入凭据、私有 registry URL、私有集群名称、个人机器路径或一次性的项目事实。

## 安装

预览目录：

```bash
npx skills add mlhiter/skills --list
```

安装全部技能：

```bash
npx skills add mlhiter/skills --all
```

安装单个技能：

```bash
npx skills add mlhiter/skills --skill check
```

> [!TIP]
> 如果只需要某个具体工作流，可以先安装一个技能。每个已安装技能都足够自包含，便于使用前阅读和审查。

## 提示词技巧

这几个小提示词可以让技能驱动的工作更可靠：

1. 开始前，让 agent `复述我的需求`。清晰复述能提前暴露理解偏差。
2. 设计方案时，让 agent `使用第一性原理`。它应该识别不变量、事实源、所有权边界、因果链，以及解决问题所需的最小机制。
3. 审查代码时，让 agent `使用对抗性审查`。它应该主动检查畸形输入、并发问题、租户或权限边界错误、不安全的 sink、缓存意外、部署风险和回滚缺口。

第二和第三个提示词来自 Khazix。

## 资产目录

| 领域 | 资产 | 适用场景 |
| :--- | :--- | :--- |
| 写作 | [`logseq-writer`](skills/logseq-writer/SKILL.md) | 把主题、草稿和笔记写成实用的 Logseq 风格教程文章。 |
| 写作 | [`intern-learning-recap`](skills/intern-learning-recap/SKILL.md) | 把已完成的工作讲成适合实习生理解的技术学习复盘。 |
| 规划 | [`think`](skills/think/SKILL.md) | 在编码前，把粗糙想法整理成决策完整的方案。 |
| 调试 | [`hunt`](skills/hunt/SKILL.md) | 在修复错误、回归、崩溃和异常行为前先找到根因。 |
| 审查 | [`check`](skills/check/SKILL.md) | 用功能意图建模、功能验收、对抗性审查和发布门禁来审查已完成的工作。 |
| Codex | [`codex-goal-builder`](skills/codex-goal-builder/SKILL.md) | 根据粗略的长期目标，起草有证据支撑的 Codex Goal。 |
| Codex | [`codex-runner-creator`](skills/codex-runner-creator/SKILL.md) | 创建或修复 Codex app 的本地环境运行入口。 |
| Codex | [`workflow-packager`](skills/workflow-packager/SKILL.md) | 从重复的 agent 工作中提炼技能、子 agent、自动化或模板。 |
| Git | [`git-commit-push`](skills/git-commit-push/SKILL.md) | 创建会话级 Conventional Commit，并安全发布到远端。 |
| Git | [`pr-creator`](skills/pr-creator/SKILL.md) | 创建 pull request，并显式处理 base/head 和 fork/upstream 安全性。 |
| 报告 | [`quarterly-work-dashboard`](skills/quarterly-work-dashboard/SKILL.md) | 基于只读的 GitHub 和飞书证据，生成面向领导层的季度工作面板。 |
| QA | [`issue-creator`](skills/issue-creator/SKILL.md) | 把简短测试反馈整理成结构化 GitHub issue。 |
| 设计 | [`screenshot-interaction`](skills/screenshot-interaction/SKILL.md) | 从截图推断预期 UI 行为、状态和交互。 |
| 模板 | [`global AGENTS.md`](templates/global/AGENTS.md) | 从一份适合公开分享的全局 agent 指令基线开始，而不是把它放在仓库根目录。 |

## 仓库结构

```text
.
|-- README.md
|-- README.zh-CN.md
|-- assets/
|   `-- mlhiter-skills.svg
|-- skills.sh.json
|-- templates/
|   `-- global/
|       `-- AGENTS.md
`-- skills/
    `-- <skill-name>/
        |-- SKILL.md
        |-- references/
        |-- scripts/
        `-- assets/
```

`README.md` 和 `README.zh-CN.md` 是发现入口，`skills.sh.json` 是可发布的目录元数据，每个 `skills/<skill-name>/` 目录负责存放该技能的指令和配套材料。`templates/global/AGENTS.md` 是可分享的全局 agents 模板，不是这个仓库的项目级说明。

## 维护这个目录

新增、移除或重命名技能或模板时：

1. 把技能放在 `skills/<skill-name>/SKILL.md`。
2. 把可复用模板放在 `templates/<template-name>/`。
3. 把该技能专用的参考资料、脚本和资源放在它自己的技能目录里。
4. 当可安装技能变化时，更新 `skills.sh.json`。
5. 更新英文和中文 README，让用户能找到这个资产。
6. 保持 `templates/global/AGENTS.md` 适合公开发布。

发布前建议检查：

```bash
python3 -m json.tool skills.sh.json >/dev/null
git diff --check
```

> [!NOTE]
> 不要为了套用软件项目模板而创建通用的 `PRODUCT.md`、`DESIGN.md`、`ROADMAP.md` 或顶层 `docs/` 目录。这个仓库的长期上下文应该放在两个 README、`skills.sh.json` 和各技能自己的目录里。

## 来源

有些资产来自个人工作流。有些资产改编自公开技能仓库，并针对 Codex、长期上下文、运行时证据和中英文工作流做了扩展。

| 资产 | 来源 |
| :--- | :--- |
| `think` | 改编自 [`tw93/Waza`](https://github.com/tw93/Waza) 的 `think` 工作流，并扩展了 Codex 规划和长期上下文能力。 |
| `hunt` | 改编自 [`tw93/Waza`](https://github.com/tw93/Waza) 的 `hunt` 工作流，并加入根因门禁和运行时证据路径。 |
| `check` | 改编自 [`tw93/Waza`](https://github.com/tw93/Waza) 的 `check` 工作流，并扩展了功能意图风险建模、验收门禁和发布检查。 |
| `logseq-writer` | 原创个人写作工作流，用于输出实用的 Logseq 教程文章。 |
| `workflow-packager` | 原创工作流挖掘 playbook，用于把重复工作转成可复用资产。 |
| `quarterly-work-dashboard` | 原创季度面板生成工作流，用于基于只读 GitHub 和飞书证据生成工作总结。 |
| `codex-goal-builder` | 原创 Codex Goal 起草工作流。 |
| `codex-runner-creator` | 原创 Codex app 环境运行入口工作流。 |
| `git-commit-push` | 原创会话级 git 提交和安全推送工作流，基于 Conventional Commits。 |
| `pr-creator` | 原创 PR 创建工作流，重点处理 fork/upstream head 和 base 的显式安全性。 |
| `intern-learning-recap` | 原创面向实习生的技术学习复盘工作流。 |
| `issue-creator` | 原创 QA issue 起草工作流，用于创建结构化 GitHub issue。 |
| `screenshot-interaction` | 原创截图到交互契约工作流。 |
| `global AGENTS.md` | 原创的公开安全全局 agent 指令基线，用于在仓库根目录之外分享可复用指导。 |

[`mattpocock/skills`](https://github.com/mattpocock/skills) 等外部仓库也作为模式来源被审阅过，尤其适合借鉴公开接口纪律和更紧的反馈循环。这个目录里的资产不是对该仓库的整体复制。

## 安全

这些技能和模板都是指令包，会影响 agent 如何读取文件、写入项目变更、创建提交或调用外部工具。安装、复制或调用某个工作流之前，请先阅读对应的 `SKILL.md` 或模板，尤其是会检查本地历史、修改项目文件或发布产物的资产。
