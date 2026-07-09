---
name: quarterly-work-dashboard
description: |
  季度开发工作总结 skill。用于一站式只读采集 GitHub 开发活动和飞书协作证据，并生成面向老板/领导层可扫读的本地 HTML 总面板和 summary.json。包含 GitHub 模块、飞书模块和价值总览模块：GitHub 统计 commit、PR、issue、review、仓库、上季度环比、贡献画像、功能类 PR/修复类 PR 归类、PR 变更审计、项目组合、新建仓库、新启动项目、重点工作线索、项目价值归因和重点项目证据展开；飞书统计文档发现/内容读取、消息搜索、日历日程和权限缺口；总面板展示代码/PR 证据 -> 功能类/修复类 PR -> 项目结果 -> 价值主线的可追溯映射。默认不写入 GitHub 或飞书，不创建/修改/发送任何外部对象。
---

# Quarterly Work Dashboard

你正在生成一个季度开发工作总面板。目标是把 GitHub 的研发交付事实和飞书的协作证据做成一个可直接给老板/领导层看的网页，而不是分散成多个 skill 和多份产物。

核心叙事必须从价值出发：代码、commit、PR、代码区域和变更文件只是证据底座，不是领导层价值主指标。页面应把 GitHub 证据翻译成“哪些 PR 属于功能类 / 修复类、改善了什么工作流、对应什么价值”的链路，不展示抽象价值分、神秘评分、成果节点、能力节点或证据边。`feature_points` 和 `bug_fixes` 是合并 PR 的分类计数，不是需求系统里的真实功能点或缺陷数；HTML 应优先写成“功能类 PR / 修复类 PR”。页面应只保留可直接展示给老板/领导层的展示版，不再提供“全量 / 展示”切换，也不在 HTML 中输出低层级审计明细。

## 边界

- 本 skill 是一站式入口，内部包含 GitHub、飞书、总面板三个模块。
- 只读 GitHub 和飞书数据。不要创建、编辑、关闭、合并、评论、发送、上传、删除或修改任何外部对象。
- GitHub 和飞书模块内部独立失败：GitHub 失败不应伪造结果；飞书没有可用模块或权限尚未获批时，HTML 展示层默认全面隐藏飞书内容，`summary.json` 仍保留 `feishu` 原始节点和权限信息，方便后续恢复。
- 不把“相关关闭 issue”夸大成“亲自解决问题”。
- 不把“review 参与 PR”夸大成“review 次数”。
- 不把聊天命中数写成完成事项。
- 不编造业务影响。没有证据时，只展示已采集事实、推断口径和权限缺口。

## 默认产物

每次执行默认生成一个输出目录：

- `index.html`：季度工作总面板，默认就是展示版；飞书没有权限时展示为 GitHub-only 面板，不输出全量审计区、模式切换或低层级详情。
- `summary.json`：总面板稳定摘要，保留 `github` 和 `feishu` 两个完整节点，并提供展示层指标、深读工作拆解、证据链和可信度结构。
- `run.json`：本次 pipeline 每个内部步骤的命令、返回码和 stdout/stderr 摘要。
- `github/index.html`、`github/summary.json`：GitHub 子模块产物。
- `github/deep_work_analysis.json`：对本季度合并 authored PR 逐个读取 PR detail、正文、commit 标题和变更文件路径后形成的深读审计底稿；默认生成，除非显式传 `--skip-deep-github-analysis`。
- `feishu/index.html`、`feishu/summary.json`：飞书子模块产物。
- 可选 `github/raw/`、`feishu/raw/`：打开 `--save-raw` 时保留原始查询数据，方便审计和重跑。
- 可选 `annotations.yaml/json`：只用于项目卡片等展示层的人类校准，不修改 GitHub/飞书原始 summary 节点。

## 一站式运行

```bash
python3 scripts/run_quarterly_work_dashboard.py \
  --start 2026-04-01 \
  --end 2026-06-29 \
  --period-label "2026 Q2" \
  --github-user <github-login> \
  --include-calendar \
  --message-query "" \
  --message-page-limit 2 \
  --save-raw \
  --annotations /path/to/annotations.yaml \
  --output-dir /path/to/quarterly-work-dashboard-2026-q2
```

这个入口会顺序执行：

1. GitHub 模块：生成 `github/summary.json` 和 `github/index.html`。
2. 飞书模块：生成 `feishu/summary.json` 和 `feishu/index.html`。
3. 总面板模块：读取两个子模块 summary，生成根目录 `index.html` 和 `summary.json`。

## GitHub 模块

默认统计：

| 指标 | 口径 |
| --- | --- |
| 活跃仓库数 | 本季度有 commit、PR、issue、review 任一活动的仓库去重数 |
| commit 数 | authored commits |
| 创建 PR 数 | `author:<user>` 且 `created` 在季度范围内的 PR |
| 合并 PR 数 | `author:<user>` 且 `merged-at` 在季度范围内的 PR |
| review 参与 PR 数 | `reviewed-by:<user>` 命中的 PR 集合数，不是单次 review 次数 |
| 创建 issue 数 | `author:<user>` 且 `created` 在季度范围内的非 PR issue |
| 相关关闭 issue 数 | `involves:<user>` 且 `closed` 在季度范围内的非 PR issue |
| 功能类 PR 数量 | 在本季度合并 authored PR 中，按标题前缀、关键词和 label 归类出的 feature 类 PR；这是 PR 分类，不等同需求系统功能点 |
| 修复类 PR 数量 | 在本季度合并 authored PR 中，按 `fix:`、bug/regression/crash/error 等标题或 label 线索归类出的修复类 PR；这是 PR 分类，不等同缺陷系统条目 |
| 代码行数 | 对本季度合并 authored PR 调用 GitHub PR API 统计 additions、deletions、changed_files，并按文件路径拆分前端/后端/测试/文档/配置等区域 |
| 新建仓库 | GitHub repo `created_at` 落在本季度的仓库 |
| 新启动项目 | 上季度未进入活跃仓库集合，本季度出现 commit、PR、issue 或 review 证据的仓库 |
| 重点工作线索 | 根据仓库描述、README、PR/commit 标题抽取 IDE/DevBox、离线交付、权限链路、运维、测试质量、文档工作流等可汇报主题 |

可选参数：

- `--github-user <login>`：指定 GitHub 用户；不传时由内部脚本尝试读取 gh 登录用户。
- `--github-repo owner/name`：限定仓库，可重复。
- `--github-owner owner`：限定 owner/org，可重复。
- `--previous-start`、`--previous-end`：手动指定上季度对比范围。
- `--skip-code-stats`：跳过逐个合并 PR 的 GitHub API 代码增删行统计，仅保留 PR/issue/commit 搜索结果。
- `--skip-deep-github-analysis`：跳过逐个合并 PR 的正文、commit 和文件路径深读。默认不要跳过，因为展示层的“实际交付拆解”依赖它。
- `--deep-github-limit <N>`：只深读前 N 个合并 PR；默认为 0，即深读全部合并 PR。
- `--deep-github-concurrency <N>`：深读阶段并发读取 GitHub API 的 worker 数，默认 6。
- `--skip-project-portfolio`：跳过仓库 metadata、README、语言和项目组合采集。
- `--skip-github --github-summary /path/to/summary.json`：跳过 GitHub 采集，用已有 summary。
- `--annotations /path/to/annotations.yaml|json`：可选人工标注文件，覆盖项目展示名、用途、业务影响等展示层内容。

`annotations.yaml` 示例：

```yaml
projects:
  sealos-apps/devbox:
    display_name: "DevBox 研发体验"
    purpose: "云端开发环境与 IDE 工作流"
    business_impact: "降低开发环境启动和维护成本"
    customer_value: "让 IDE 接入、离线目录和配置迁移更稳定"
    role: "主推进"
    difficulty: "高复杂度"
    highlight: "持续推进 DevBox v2 体验、配置清理、IDE 接入和离线能力"
    narrative: "本季度持续推进 DevBox v2 体验、配置清理、IDE 接入和离线能力。"
    business_goal: "提升云端开发环境可用性和交付可控性"
    user_problem: "开发环境启动、IDE 接入和离线能力不稳定会拖慢团队交付"
    before_after: "从多链路配置维护转向更稳定的 IDE/离线工作流"
    impact_statement: "支撑研发效率和私有化交付链路稳定性"
    stakeholder: "研发团队 / 私有化交付团队"
    value_evidence:
      - "代表 PR 体现 IDE 接入和配置清理"
      - "项目持续高投入且与研发效率主线一致"
    primary_value: "研发效率"
    value_confidence: "manual"
    display_priority: 100
    value_attribution:
      - label: "研发效率"
        basis: "人工 annotation 校准"
        evidence: ["云端 IDE 接入链路更稳定", "配置清理减少环境维护成本"]
      - label: "交付能力"
    outcomes:
      - "推进 DevBox v2 体验和 IDE 接入"
      - "修复配置清理和离线能力相关问题"
    tags: ["IDE", "离线交付", "稳定性"]
  example-user/archive:
    include: false
```

人工标注只能影响项目卡片和 `manual_annotations` 元数据，不应删除或篡改 `github` / `feishu` 原始节点。
可选字段包括 `business_goal`、`user_problem`、`before_after`、`impact_statement`、`stakeholder`、`value_evidence`、`business_impact`、`customer_value`、`role`、`difficulty`、`highlight`、`primary_value`、`value_confidence`、`display_priority`、`value_attribution`、`outcomes`、`tags` 和 `signals`，用于增强项目卡片、价值归因和重点项目剖面展示，不参与原始统计。

## 飞书模块

默认包含：

| 模块 | 默认策略 | 常见 scope |
| --- | --- | --- |
| 文档发现 | `drive +search` 按季度编辑时间自动发现候选文档 | `search:docs:read` |
| 文档读取 | `docs +fetch` 读取发现到或手动传入的 doc/docx/wiki | `docx:document:readonly` |
| 消息 | 仅在传入 `--message-query`、`--chat-id`、`--sender` 等过滤器时查询 | `search:message` |
| 日历 | 传入 `--include-calendar` 后读取季度日程 | `calendar:calendar.event:read` |

可选参数：

- `--doc <url-or-token>`：指定文档 URL/token，可重复。
- `--skip-doc-discovery`：不自动发现文档。
- `--skip-doc-reading`：只发现，不读取正文。
- `--message-query <query>`：消息关键词，可重复；空字符串表示按时间窗口搜索。
- `--include-calendar`：开启日历读取。
- `--skip-feishu --feishu-summary /path/to/summary.json`：跳过飞书采集，用已有 summary。

权限不足时不要阻塞整次运行。飞书模块应把缺失 scope 写入 `feishu/summary.json`；若当前没有任何可用飞书模块，总面板 HTML 不展示飞书内容、飞书 tab、权限缺口或 0 值协作指标。

## 总面板结构

HTML 面板应包含：

- 顶部总览：季度、时间范围、生成时间和可展示数据源状态；飞书没有权限时只展示 GitHub。
- 价值首屏：有 `github/deep_work_analysis.json` 时，优先展示“实际交付拆解”：深读工作项数、工作流数、commit 线索数、文件路径覆盖数、14 类左右的工作流、代表 PR、涉及仓库、功能/修复构成、价值类别和推断边界。没有深读数据时才降级展示旧的价值主线证据链。不要把 commit、PR 或代码变更量作为价值本身，也不要展示抽象价值分。
- 深读口径：深读阶段把每个合并 PR 作为一条可审计工作项，并从 PR 标题、正文、commit 标题和变更文件路径聚类到工作流；它用于解释“做了哪些实际工作”，不等同需求系统或缺陷系统中的真实功能点/bug 条目。
- 工程审计指标：commit、合并 PR、review 参与 PR、相关关闭 issue 等只能作为证据底座或 summary.json 字段，不作为价值本身，也不要作为页面主区块重复展示；飞书没有权限时不展示飞书审计指标。
- 结论证据链：每条价值结论标记事实/推断/边界、可信度、来源、代表性 PR/issue/repo/scope 证据，并写清楚“PR/代码 -> 功能类/修复类 PR -> 项目结果 -> 价值”的映射关系。
- 可信度/覆盖率条：显性展示 GitHub 事实、PR 文件统计、项目画像和人工校准覆盖情况；飞书至少有一个模块可用时再展示飞书覆盖。
- 价值展示层：用代码/PR 证据 -> 功能类/修复类 PR -> 项目结果 -> 价值主线的路径、投入强度条、聚焦结构和项目象限帮助领导层快速判断价值，不新增采集口径，不在 HTML 中渲染 value_map 的内部节点名。
- 季度变化地图：把核心环比指标、新建/新启动/持续投入项目和项目变化边界放在同一块，避免只看单点数字。
- 项目价值归因：从项目用途、主题、代表 PR、commit、合并 PR、功能类 PR、修复类 PR 和变更文件等既有证据中，派生研发效率、稳定性与质量、交付能力、用户体验、平台治理、知识沉淀等展示层类别；只用于领导层扫读，不改写源数据。
- 重点项目剖面：按活动强度和人工 `display_priority` 选出重点项目，展示项目定位、价值类别、季度动作、业务/客户价值、关键指标和代表 PR。
- 工程成果：功能类 PR 数量、修复类 PR 数量、变更文件数、PR 新增/删除代码行细节和代码区域分布。新增/删除行属于细节审计数据，不应挤占首屏主指标。
- 项目组合：新建仓库、新启动/重新活跃项目、每个项目用途、代表性 PR、重点工作线索，以及可展开的项目证据层。展开层应包含项目定位、价值归因、季度证据指标、代表 PR 和来源/可信度边界。
- 领导层摘要：3-5 条基于证据和权限边界的可汇报结论。
- 总览图表：用交付构成、环比变化、成果结构、主题投入、工作类型、语言结构、季度周节奏、项目价值归因、项目象限、仓库矩阵、代码区域 treemap 等图表增强领导层扫读；不要把首屏核心指标再次包装成 GitHub/飞书强度榜。
- 单一展示版：HTML 只保留总览、价值结论、关键图表、结构与变化和重点项目剖面；不渲染全量/展示切换、详细模块、口径表、可展开审计细节或数据源大 tab。
- 口径说明：限制和审计口径保留在 `summary.json` 的 `confidence`、`claims.limitations`、`methodology` 等结构字段；HTML 只保留每条价值链必要的一行边界，不做长篇说明。
- 展示克制：不要渲染解释性副标题、页面使用说明、指标小字说明或重复口径提醒；页面应主要由数据、图表、证据、状态 badge 和必要限制组成。
- 视觉结构：采用克制的执行层分析台风格，首屏最多包含价值结论、价值类别、来源/可信度信号、价值路径和 2-3 张总览图；不要在首屏堆叠多组同质卡片。
- 证据结构：领导层摘要和证据链应合并为 `结论与证据`，左侧呈现 3-5 条结论，右侧呈现紧凑证据 rail；只有在详细审计上下文中才渲染完整证据卡片。
- 项目结构：重点项目剖面优先用排名行、表格行或 rail 展示，卡片只用于真正重复的对象；项目组合细节放在 GitHub 详细模块，不在总览重复。
- 图表层级：页面图表只解释核心指标，例如交付构成、环比变化、成果结构、投入强度、聚焦结构和项目象限；不要再额外输出 Top 仓库贡献强度、PR 代码变更 Top、代码区域 treemap 等审计图。
- 表面处理：优先使用分隔线、行、轨道和表格密度组织信息；减少阴影和白色卡片数量，避免每个模块都长成相同圆角卡片。

## 去重原则

- 每个指标只能有一个主展示位置。首屏负责价值结论、价值类别、能力/成果/证据计数和覆盖状态；commit、合并 PR、功能类 PR、修复类 PR、活跃仓库、新建仓库、review 参与 PR 和飞书可用模块只作为证据底座或 summary 字段，不在页面上重复包装。
- 领导层摘要只放 3-5 条结论，不再追加小指标宫格；需要数字支撑时引用首屏或证据链。
- 领导层摘要不要和证据链分成两个相邻大区块；默认合并为一个 `结论与证据` 区块。
- 跨来源结构只展示变化、结构、投入方向和项目归因，不重复首屏 KPI 条形图。
- 跨来源结构不要重复渲染主题投入、工作类型、语言结构这类细节图；这些图进入 GitHub 详细模块。
- 重点项目剖面是项目组合的主展示位置；页面不再重复项目地图、项目组合总览、工程成果、代码、PR、issue、commit 等审计明细。
- 飞书权限不足且无可用模块时，HTML 展示层和 `value_map` / `value_views` / `claims` / `evidence_chains` 等展示派生字段不出现飞书模块、缺失 scope 或 0 值指标；这些信息只保留在根 `feishu`、`modules.feishu`、`sources.feishu_summary` 和 `feishu/summary.json` 中。

根 `summary.json` 应额外包含：

- `executive_metrics`：稳定机器可读合同，固定包含 `delivery`、`outcomes`、`portfolio`、`collaboration`、`coverage`、`boundaries`，每项至少有 `label`、`value`、`source`、`confidence`、`status`。
- `claims`：结构化结论，每条包含 `id`、`text`、`type`、`confidence`、`source`、`evidence_refs`、`limitations`。
- `evidence_chains`：页面可展开的证据链，连接结论、代表性证据和口径限制。
- `value_views`：展示层派生视图，固定包含 `value_path`、`investment_lanes`、`project_quadrants`、`focus_mix`、`project_value_attribution`、`project_value_categories`、`project_profiles`、`quarter_change_map`、`data_quality` 和 `source_boundaries`；这些字段只能从 `github` / `feishu` summary 派生，不能改写原始源数据。
- `value_map`：领导层价值映射合同，固定包含 `schema_version`、`value_categories`、`capability_nodes`、`outcome_nodes`、`value_claims`、`evidence_items`、`evidence_edges` 和 `coverage`。它只能从 `github` / `feishu` summary 与可选 annotations 派生，表达代码/PR 证据如何映射到能力、成果和价值结论；不得编造业务收入、客户满意度或未采集到的协作内容。
- `confidence`：指标可信度表，说明哪些是 API 事实，哪些是标题/label/README 推断。

## 扩展性规则

- 新增数据源时，优先在本 skill 内新增独立模块，并让总面板读取该模块 summary。
- `summary.json` 中保留 `modules`、`github`、`feishu`，未来可加入 `jira`、`linear`、`slack` 等节点。
- 外部 API 采集模块只读且独立失败，总面板负责解释覆盖率和证据边界。

## 输出质量自检

交付前检查：

- `index.html` 是否存在且可打开？
- `summary.json` 是否包含 `github` 和 `feishu` 两个完整源？
- `github/summary.json`、`feishu/summary.json` 是否存在？
- HTML 是否没有 `全量` / `展示` 模式切换、详细模块、口径表、数据源 tab 和可展开审计细节？
- 缺少飞书权限且无可用模块时，HTML 是否完全隐藏飞书内容、缺失 scope 和 0 值协作指标？
- GitHub 的相关 issue 和 reviewed PR 口径是否被保留？
- 功能类 PR、修复类 PR 和代码行统计是否展示了覆盖率和推断口径？
- 项目组合是否展示新建仓库、新启动项目、项目用途、重点工作线索和可点击证据？
- 项目价值归因是否展示正式、可解释的价值类别，并在项目展开层里显示依据、指标、代表 PR 和边界？
- 重点项目剖面是否能把项目定位、价值类别、季度动作、指标和代表 PR 放在一张卡里？
- 季度变化地图是否同时展示核心环比、新建/新启动/持续项目和边界说明？
- 数据质量条是否显性展示 GitHub、代码统计、项目画像和人工校准状态，并仅在飞书有可用模块时展示飞书覆盖？
- 根 `summary.json` 是否存在 `executive_metrics`、`claims`、`evidence_chains`、`confidence`，且没有删除 `github`、`feishu` 完整节点？
- 根 `summary.json` 是否存在 `value_map.schema_version == 1`，且 `value_claims`、`outcome_nodes`、`capability_nodes`、`evidence_edges` 均非空？
- `claims` 中每条结论是否都有 `confidence`、`type`、`source`、`limitations` 和可解释的 `evidence_refs`？
- 首屏是否能被领导快速看懂：是否能直接看到“PR/代码证据 -> 功能/修复 -> 项目结果 -> 价值主线”，且每条价值判断都有代表 PR 或项目证据？
- HTML 是否没有 `价值分`、`成果节点`、`能力节点`、`证据边`、抽象 value score 或无法解释的小分数？
- 首屏是否足够克制：没有连续卡片墙，没有把 commit、PR、代码行数或变更文件作为价值主指标？
- 图表是否足够丰富但不失真：总览至少覆盖交付构成、环比、成果结构、季度周节奏、项目价值归因、项目象限和核心结构变化；飞书无可用模块时不包装成协作成果，也不展示缺口。
- 深读分析是否完整：`github/deep_work_analysis.json` 是否存在，`details_succeeded`、`files_succeeded`、`commits_succeeded` 是否等于本季度合并 PR 数；`summary.metrics.deep_work_items` 是否等于合并 PR 数；深读层的功能/修复合计是否与 GitHub 子模块的功能类 PR / 修复类 PR 口径一致？
- 同一数字是否只出现一次主展示？摘要、跨来源结构和详细模块是否没有重复首屏 KPI 或项目组合总览？
- 结论与证据是否合并展示，并以紧凑证据 rail 呈现，而不是两段重复的大卡片？
- 重点项目剖面是否像正式项目台账一样可扫读，而不是一组等权重的大卡片？
- 价值展示是否清楚：首屏是否有交付到协作的价值路径，跨来源结构是否有投入强度、聚焦结构和项目象限，并且这些内容不包含讲稿、使用说明或无证据业务承诺。
- 是否去掉了冗余副标题、描述文本和指标小字，只保留证据内容、真实状态和必要口径？
- 移动端是否无整页横向滚动？
