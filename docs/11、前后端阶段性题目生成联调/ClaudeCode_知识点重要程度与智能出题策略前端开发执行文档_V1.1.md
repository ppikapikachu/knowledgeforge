# Claude Code 前端开发执行文档 V1.1

> 项目：AI 面试题库系统  
> 任务：知识点重要程度管理、题库知识库范围配置、智能出题分配、出题策略管理  
> 执行方：Claude Code  
> 修改范围：仅 `frontend/`（以当前仓库实际管理员 Web 前端目录为准；不得修改 `backend/`）  
> 后端依据：`后端完整API报告QUESTION_POINT_DEMAND_AND_POLICY_API.md`、`后端实现报告QUESTION_POINT_DEMAND_IMPLEMENTATION_REPORT.md`  
> 本文版本：V1.1；替代此前同主题的前端开发草案。  

---

## 0. 本次任务目标与强制边界

本次不是重做管理员 Web，而是在现有题库管理功能上增量增加以下能力：

1. 在知识点管理中展示、编辑知识点重要程度，并展示其来源。
2. 配置题库允许使用哪些知识库，为智能出题确定候选知识点范围。
3. 在 AI 出题页面增加“指定知识点”和“系统智能分配”两种模式。
4. 智能分配模式先请求后端预览，再由管理员确认创建任务。
5. 新增出题策略配置页面，支持全局策略和题库级覆盖策略。
6. 在任务列表、任务详情展示出题模式、分配数量和历史分配快照。

### 0.1 开发边界

- 只修改现有管理员 Web 前端目录，禁止修改 `backend/`、数据库、Alembic 迁移和 Agent 代码。
- 优先复用现有 Vue3、TypeScript、路由、布局、API Client、Token 拦截器、表格、表单、弹窗和通知组件。
- 不重写现有 AI 出题、生成任务、题目审核和题目列表页面。
- 所有业务数据必须来自真实后端 API，不允许使用 Mock、硬编码成功响应或前端伪造库存/需求评分。
- 前端只负责参数输入、结果呈现和用户确认；不在浏览器实现 `KnowledgePointDemandService` 算法。
- 不新增自动补题定时任务、用户答题页面、题目正确率统计、评论社区或 AI 解析生成页面。
- 不增加任意公式编辑器。管理员只修改后端允许的结构化策略参数。
- 不把 `knowledge_base_id`、`knowledge_id`、`question_bank_id` 混为一谈。

### 0.2 后端已完成内容（根据实现报告）

- 新增 `question_bank_knowledge_base` 题库-知识库映射表。
- 新增 `question_generation_policy` 策略表，支持全局默认和题库覆盖。
- `knowledge` 增加 `importance_level`、`importance_source`。
- `question_generation_task` 增加分配模式、分配计划快照、策略快照、请求/分配/未分配数量字段。
- 新增 `KnowledgePointDemandService`、`PolicyService`、知识库映射 API 和策略/预览 API。
- `KnowledgeExtractAgent` 已扩展重要程度输出；人工设置的 `manual` 来源不会被 Agent 覆盖。
- 后端单测 56 passed，Agent 测试 47 passed，Alembic 迁移成功。

**重要限制：实现报告注明 API 冒烟测试尚未执行、Swagger 尚未验证。** 因此前端不得直接声称新增 API 已经真实联调通过。开始功能集成前，必须执行第 1 节的契约核验。

---

## 1. 开发前必须进行 API 契约核验（不可跳过）

先只读检查后端，不修改后端文件：

1. 启动当前后端服务，确认服务能正常启动。
2. 打开 FastAPI `/docs`，核对新增路由和 Pydantic 请求/响应 Schema。
3. 对本文件第 8 节列出的接口执行最小真实请求；需要管理员 Bearer Token。
4. 对照后端实际 `app/api/v1/`、`app/schemas/`、`app/models/` 实现及 API 文档。
5. 将实际响应与本文件类型定义逐字段核对后再接入 UI。

### 1.1 报告中需要特别核对的契约差异

后端 API 报告已经给出主要示例，但有以下地方需要通过实际 Schema/响应确认：

**差异 A：请求字段以本次后端 API 报告中的新字段为准。**

本次新增智能分配预览和任务创建使用：

- `question_type`：示例为小写 `single_choice`。
- `difficulty`：示例为字符串 `medium`。
- `total_question_count`：总题量字段。

不得沿用旧版单知识点接口的 `question_type: "SINGLE_CHOICE"`、`difficulty: 2`、`count` 组合来调用新增的预览/智能分配请求。现有旧页面若仍使用旧字段，应通过独立 API DTO/转换层适配，不能混用两种请求结构。

题型其他值、难度其他值请从当前后端 Pydantic Enum/Literal 或 OpenAPI 核实。报告中的 `single_choice` / `medium` 是明确示例，但不能只凭示例擅自推导完整枚举列表。

**差异 B：预览响应以当前 API 报告第 4.2 节的字段为准。**

预览响应示例是 `requested_count`、`allocated_count`、`unallocated_count`、`policy_snapshot`、`items`。它没有承诺返回旧前端草案中的 `allocatable_count`、`is_fully_allocatable`、`summary`、`allocations`、`warnings`、`stock_score`、`usage_score`、`reason_codes` 等字段。

因此本次前端只展示当前正式 API 报告明确提供的字段。不能使用旧草案中未被后端 API 报告确认的字段。

**差异 C：此前前端草案中的任务详情 `allocation_plan` 结构与当前后端报告不一致。**

当前后端 API 报告明确说明任务列表/详情的 `allocation_plan` 是 JSON 数组，创建响应示例也使用数组；此前前端草案曾写成包含 `items` 的对象，该结构不应继续沿用。当前以前端最新开发所依据的后端 API 报告为准：将 `allocation_plan` 按数组处理，并在开发前通过 `GET /question-generation/tasks/{id}` 实际响应和后端 Schema 再核验一次。如果运行时确实返回对象，应输出契约差异，不要在页面层静默猜测。

**若实际 OpenAPI/响应与本文件或后端 API 报告冲突：**

- 暂停冲突接口的 UI 数据绑定；
- 输出 `FRONTEND_API_CONTRACT_DIFF.md`，记录路径、请求字段、响应差异和真实示例；
- 不要自行增加字段、猜测兼容多个未证实字段或修改后端；
- 将差异交回项目负责人/DSH 确认后再继续。

---

## 2. 数据枚举与中文展示规范

### 2.1 知识点重要程度

数据库/API 枚举必须保持原值：

| API 值 | Web 中文显示 | 解释 | 算法基础分 |
|---|---|---|---:|
| `core` | 核心必考 | 面试高频考点、必考知识、框架核心机制 | 1.00 |
| `important` | 重点掌握 | 常见考点、重要概念、常用技术 | 0.75 |
| `normal` | 常见考点 | 一般知识点、辅助理解内容 | 0.50 |
| `supplementary` | 扩展了解 | 补充说明、延伸阅读、冷门细节 | 0.25 |

说明：后端实现报告对枚举的语义描述是 `core=核心知识点`、`important=重要知识点`、`normal=普通知识点`、`supplementary=补充知识点`。Web 可以用上表更易理解的产品文案，但 API 值不得更改。若项目原有术语已统一为“核心知识点/重要知识点/普通知识点/补充知识点”，应保持全站一致，不要在不同页面对同一枚举显示不同含义。

`importance_source` 来源映射：

| API 值 | Web 显示 |
|---|---|
| `default` | 系统默认 |
| `agent` | AI 标注 |
| `manual` | 管理员调整 |

重要程度是知识点的教学/面试重要性，不是题目难度。题目难度仍由生成任务参数单独选择。

### 2.2 任务分配模式

| API 值 | Web 显示 |
|---|---|
| `manual` | 指定知识点 |
| `auto` | 系统智能分配 |

### 2.3 策略来源

`GET /question-generation/policies/effective` 的 `data.source`：

| API 值 | Web 显示 |
|---|---|
| `global` | 使用全局默认策略 |
| `question_bank` | 使用题库独立策略 |

请按当前后端 API 报告中的值处理，不要使用旧草案中的 `global_default`。

---

## 3. 页面与导航规划

在现有“题库管理”菜单下增量增加入口。保留当前已有：AI 生成题目、生成任务、题目审核、题目列表。

建议新增：

1. `出题策略`：全局策略和题库级策略设置。
2. `题库知识范围`：配置题库关联的知识库。

知识点重要程度直接集成到现有知识点列表/详情，不另建重复的知识点管理模块。

建议路由（若当前项目路由命名不同，以现有路由规则为准）：

- `/question-management/policies`
- `/question-management/knowledge-scope`

现有 AI 出题页面增加分配模式切换；现有生成任务列表与详情增加分配信息展示。

---

## 4. 页面一：知识点重要程度管理

### 4.1 列表展示

在现有知识点列表增加：

- 重要程度中文标签；
- 来源标签（系统默认/AI 标注/管理员调整）；
- 可操作的“修改重要程度”入口。

数据来自现有 `GET /api/v1/knowledge` 返回的知识点数据。后端实现报告说明 `KnowledgeResponse` 已增加 `importance_level` 和 `importance_source`。

不要假设 `/knowledge` 支持重要程度筛选参数；当前 API 报告未明确承诺该筛选能力。若实际 OpenAPI 有该参数再实现服务端筛选，否则不允许只对当前分页数据做筛选并将其伪装成全量筛选。

### 4.2 编辑交互

编辑控件为固定下拉枚举，不允许任意输入字符串。每项展示中文等级和解释。

调用：

`PATCH /api/v1/knowledge/{knowledge_id}/importance`

请求：

```json
{
  "importance_level": "core"
}
```

响应 `data`：

```json
{
  "knowledge_id": 1,
  "importance_level": "core",
  "importance_source": "manual",
  "updated_at": "2026-10-19T13:00:00"
}
```

处理规则：

1. 保存按钮提交前显示当前值与目标值。
2. 成功后以响应数据更新行数据，来源改为“管理员调整”。
3. 失败时保留原值，展示服务端错误信息。
4. 不仅在前端将来源改为 manual；以服务端响应为准。
5. 提示管理员：手动设置后，知识导入 Agent 不会覆盖该重要程度。

### 4.3 历史数据默认值

迁移后现有知识点默认 `importance_level=normal`、`importance_source=default`。前端应正常显示“常见考点/系统默认”，不能把空值擅自当成 `core`。

---

## 5. 页面二：题库知识范围配置

### 5.1 业务含义

`question_bank` 是练习/组卷分类；`knowledge_base` 是知识点来源集合。一个题库可以关联多个知识库，一个知识库也可能被多个题库使用。

智能分配只能从当前题库关联知识库所包含的知识点中选择。前端不按名称模糊匹配，也不在浏览器自行推导映射。

### 5.2 页面操作

1. 从现有 `GET /api/v1/question-banks` 获取题库列表，管理员选择一个题库。
2. 从 `GET /api/v1/knowledge-bases` 获取可关联知识库列表。
3. 调用 `GET /api/v1/question-banks/{question_bank_id}/knowledge-bases` 查询当前映射。
4. 用多选控件展示知识库名称、描述、知识点数量。
5. 管理员修改选择后，点击保存。
6. 保存前明确提示：本接口是全量替换，将以当前选择覆盖旧关联。
7. 调用 PUT 保存后，重新 GET 当前映射，以服务端数据为准。

### 5.3 API 契约

查询知识库列表：

`GET /api/v1/knowledge-bases?page=1&page_size=20&keyword=&status=1`

响应 `data`：

```json
{
  "items": [
    {
      "id": 1,
      "code": "android",
      "name": "Android 知识库",
      "description": "Android 相关知识点",
      "status": 1,
      "knowledge_count": 42,
      "created_at": "2026-10-01T00:00:00",
      "updated_at": "2026-10-19T13:00:00"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 5
}
```

注意：列表分页，不能假设一次请求就能拿到所有知识库。按服务端 `page/page_size/total` 加载；选择器建议有搜索和分页/逐页加载能力。

查询题库已关联知识库：

`GET /api/v1/question-banks/{question_bank_id}/knowledge-bases`

响应 `data`：

```json
{
  "question_bank_id": 1,
  "knowledge_bases": [
    {
      "id": 1,
      "code": "android",
      "name": "Android 知识库",
      "knowledge_count": 42
    }
  ]
}
```

当前映射列表字段名是 `knowledge_bases`，不是 `items`。若实际响应不同，按第 1 节处理契约差异。

全量替换保存：

`PUT /api/v1/question-banks/{question_bank_id}/knowledge-bases`

请求：

```json
{
  "knowledge_base_ids": [1, 3, 5]
}
```

响应 `data`：

```json
{
  "question_bank_id": 1,
  "knowledge_base_ids": [1, 3, 5],
  "updated_count": 3
}
```

规则：

- 每个 ID 必须存在。
- `[]` 表示清空该题库关联，属于有效操作，但必须二次确认。
- 题库没有关联知识库时，智能分配模式不可用；提示管理员先配置知识范围。
- 不应因一个知识库被多个题库关联而禁止重复使用。

---

## 6. 页面三：AI 生成题目升级

在现有 AI 生成页面保留题库、题型、难度、数量设置，增加两种分配模式。

### 6.1 模式 A：指定知识点（manual）

适用：管理员明确知道要针对哪个知识点补充题目。

表单：

- 题库；
- 知识点（单选，沿用当前真实知识点查询接口）；
- 题型；
- 难度；
- 总生成数量。

创建请求：

`POST /api/v1/question-generation/tasks`

```json
{
  "allocation_mode": "manual",
  "question_bank_id": 1,
  "question_type": "single_choice",
  "difficulty": "medium",
  "total_question_count": 10,
  "knowledge_id": 1,
  "explanation_requested": false
}
```

说明：此处请求字段采用本次后端 API 报告中的新模式字段，不要把旧版 `count` 与 `total_question_count` 混用。`question_type` 和 `difficulty` 的全部可选值必须在第 1 节通过当前后端 Enum/Schema 核实。

### 6.2 模式 B：系统智能分配（auto）

适用：管理员选择题库和总量，由后端根据库存、近期使用情况和知识点重要程度选择多个知识点。

表单：

- 题库；
- 分配方式：系统智能分配；
- 题型；
- 难度；
- 期望生成总量。

不显示单知识点选择器。

智能模式依赖题库已配置知识库范围。若题库没有关联知识库，禁用预览和生成，并提供“去配置知识范围”的导航入口。

### 6.3 分配预览 API

调用：

`POST /api/v1/question-generation/allocations/preview`

请求体（字段和枚举以当前后端 Schema 核实）：

```json
{
  "question_bank_id": 1,
  "question_type": "single_choice",
  "difficulty": "medium",
  "total_question_count": 30
}
```

API 报告第 4.2 节列出的响应 `data`：

```json
{
  "question_bank_id": 1,
  "requested_count": 30,
  "allocated_count": 28,
  "unallocated_count": 2,
  "policy_snapshot": {
    "stock_weight": 50,
    "usage_weight": 30,
    "importance_weight": 20,
    "target_stock": 20,
    "usage_window_days": 30,
    "recent_answers_per_question_target": 3,
    "max_per_knowledge_per_task": 10,
    "usage_extra_ratio": 0.5,
    "min_demand_score": 0.15
  },
  "items": [
    {
      "knowledge_id": 1,
      "knowledge_name": "Activity 生命周期",
      "importance_level": "core",
      "demand_score": 0.85,
      "demand_count": 8,
      "allocated_count": 8
    },
    {
      "knowledge_id": 3,
      "knowledge_name": "Intent 机制",
      "importance_level": "important",
      "demand_score": 0.62,
      "demand_count": 6,
      "allocated_count": 6
    }
  ]
}
```

前端预览 UI 只能依赖上述有明确契约的字段：

- 请求总量 `requested_count`；
- 实际分配总量 `allocated_count`；
- 未分配数量 `unallocated_count`；
- 策略快照 `policy_snapshot`；
- 每个知识点的 ID、名称、重要程度、需求分数、需求数量、实际分配数量。

不要显示 API 未承诺的库存明细、答题次数明细、分项评分、知识库名称、原因码或解释文案。若后端实际 Schema 额外返回这些字段，可以在核对后再增量展示，但不允许写死假数据。

### 6.4 预览交互规则

1. 用户选择题库、题型、难度、总题量后点击“预览分配”。
2. 展示 loading，防止重复发送同一预览请求。
3. 预览成功后显示：总需求、可分配、未分配、知识点计划列表和策略参数快照。
4. 每个知识点行显示：名称、重要程度中文标签、需求分数、需求数量、分配数量。
5. `demand_score` 以百分制展示时只在显示层乘 100，原始值仍保留；建议显示两位小数或百分比一位小数。
6. 分配条形图只用 `allocated_count` / `requested_count`，不在前端重算知识点需求分数。
7. 题型、难度、题库或总题量变化时，清空旧预览，要求重新预览。
8. 策略设置发生修改后，当前预览也应失效，重新请求。
9. 预览仅查询和计算，不创建生成任务、不调用 LLM。

### 6.5 部分分配确认

当 `unallocated_count > 0`：

- 明确展示“目标 N 道，当前可分配 M 道，尚有 K 道无法分配”。
- 不得将 30 道静默改成 28 道。
- 管理员点击创建任务时弹出确认，说明将按后端当前可分配数量创建任务。
- 只有管理员明确确认后，创建请求才设置 `allow_partial: true`。
- 用户取消则不调用创建接口。
- `allocated_count <= 0` 时禁用创建按钮。

当 `unallocated_count === 0`，可以创建；`allow_partial` 设置为 `false` 或按当前 Schema 可选字段省略，优先遵循后端实际默认值。不要未经 Schema 核实自行传 null。

### 6.6 自动分配任务创建 API

`POST /api/v1/question-generation/tasks`

请求：

```json
{
  "allocation_mode": "auto",
  "question_bank_id": 1,
  "question_type": "single_choice",
  "difficulty": "medium",
  "total_question_count": 30,
  "allow_partial": true,
  "explanation_requested": false
}
```

`explanation_requested` 本次固定传 `false`。当前这两个后端报告没有说明 AI 解析自动生成已实现，不要在前端展示“同时生成解析”可用开关。

创建响应示例 `data`：

```json
{
  "task_id": 42,
  "allocation_mode": "auto",
  "requested_count": 30,
  "allocated_count": 28,
  "unallocated_count": 2,
  "allocation_plan": [
    {
      "knowledge_id": 1,
      "knowledge_name": "Activity 生命周期",
      "importance_level": "core",
      "demand_score": 0.85,
      "demand_count": 8,
      "allocated_count": 8
    }
  ],
  "policy_snapshot": {},
  "status": "pending"
}
```

如果 `unallocated_count > 0` 且未传 `allow_partial=true`，后端可能返回 `ALLOCATION_INSUFFICIENT` 且不创建任务。发生该错误时提示管理员重新预览，不要自动再次 POST。

如果返回 `NO_ELIGIBLE_KNOWLEDGE_POINTS`，提示当前题库没有符合策略要求的候选知识点，并给出检查知识范围/策略配置的入口。

### 6.7 指定知识点任务创建 API

请求示例：

```json
{
  "allocation_mode": "manual",
  "question_bank_id": 1,
  "question_type": "single_choice",
  "difficulty": "medium",
  "total_question_count": 10,
  "knowledge_id": 1,
  "explanation_requested": false
}
```

manual 模式保持原来的单知识点业务体验，但请求字段必须与当前新接口 Schema 一致。

### 6.8 创建任务后页面行为

- 创建成功后使用响应中的 `task_id` 跳转现有任务详情页。
- 创建按钮在请求期间禁用。
- 创建 POST 网络超时不得自动重发。提示“请求结果暂不确定，请先到生成任务列表核实”，避免重复任务。
- 不要根据预览结果前端生成一个假的任务记录。

---

## 7. 页面四：出题策略管理

### 7.1 策略范围与加载

新增“出题策略”页面，支持：

- 全局默认策略；
- 指定题库的独立策略覆盖。

用户选择作用范围后调用：

`GET /api/v1/question-generation/policies/effective?question_bank_id={id}`

查询 `data.source`：

- `global`：题库继承全局默认策略；
- `question_bank`：该题库正在使用独立策略。

页面同时展示 `policy.version`、`policy.updated_at`（若响应有值）。

全局策略页面查询时可以不传 `question_bank_id`，但应核对实际后端是否要求该 query 参数。题库策略页面必须传当前题库 ID。

### 7.2 策略参数表（以 API 报告为准）

| 字段 | 中文名称 | 默认值 | 允许范围 | 控件 |
|---|---|---:|---:|---|
| `stock_weight` | 库存缺口权重 | 50 | 0–100 | 数字输入/滑块 |
| `usage_weight` | 使用频率权重 | 30 | 0–100 | 数字输入/滑块 |
| `importance_weight` | 重要程度权重 | 20 | 0–100 | 数字输入/滑块 |
| `target_stock` | 每个知识点目标库存 | 20 | 1–1000 | 整数输入 |
| `usage_window_days` | 使用频率统计窗口（天） | 30 | 1–365 | 整数输入 |
| `recent_answers_per_question_target` | 每道题目标答题次数 | 3 | 1–100 | 整数输入 |
| `max_per_knowledge_per_task` | 单次任务每个知识点最大出题数 | 10 | 1–100 | 整数输入 |
| `usage_extra_ratio` | 使用频率额外需求系数 | 0.5 | 0–1 | 数字输入/滑块 |
| `min_demand_score` | 最低需求分阈值 | 0.15 | 0–1 | 数字输入/滑块 |
| `is_enabled` | 启用智能分配 | 1 | 0/1 | 开关 |

**重点：** `usage_extra_ratio` 范围是 0–1，不是 0–2；`target_stock` 最大 1000；`max_per_knowledge_per_task` 最大 100。不得沿用此前草案中的错误范围。

### 7.3 权重校验

必须满足：

`stock_weight + usage_weight + importance_weight === 100`

- 实时显示权重合计。
- 不满足 100 时阻止保存并显示差额。
- 不允许前端自动归一化或静默修改管理员输入。
- 后端也会校验，收到 `INVALID_POLICY_WEIGHTS` 时展示服务端错误。

其他字段按上述最小值、最大值和整数/小数要求校验。`usage_extra_ratio` 最多保留合理的小数位（建议 2 位）；不得改变原始业务范围。

### 7.4 查询生效策略 API

`GET /api/v1/question-generation/policies/effective?question_bank_id=1`

响应 `data` 结构：

```json
{
  "source": "question_bank",
  "question_bank_id": 1,
  "policy": {
    "stock_weight": 50,
    "usage_weight": 30,
    "importance_weight": 20,
    "target_stock": 20,
    "usage_window_days": 30,
    "recent_answers_per_question_target": 3,
    "max_per_knowledge_per_task": 10,
    "usage_extra_ratio": 0.5,
    "min_demand_score": 0.15,
    "is_enabled": 1,
    "version": 3
  }
}
```

策略响应中可能包含 `updated_at`；按真实响应类型可选展示。`is_enabled` 以 API 实际类型为准，当前报告示例为数字 1。

### 7.5 保存全局策略

`PUT /api/v1/question-generation/policies/global`

请求体：

```json
{
  "stock_weight": 50,
  "usage_weight": 30,
  "importance_weight": 20,
  "target_stock": 20,
  "usage_window_days": 30,
  "recent_answers_per_question_target": 3,
  "max_per_knowledge_per_task": 10,
  "usage_extra_ratio": 0.5,
  "min_demand_score": 0.15,
  "is_enabled": 1
}
```

### 7.6 保存题库级策略

`PUT /api/v1/question-generation/policies/question-banks/{question_bank_id}`

请求体与全局策略完全相同。保存后该题库使用独立策略覆盖全局策略。

保存成功后重新调用 effective API，不能只靠本地表单认定保存成功。

### 7.7 删除题库覆盖策略

`DELETE /api/v1/question-generation/policies/question-banks/{question_bank_id}`

该操作删除题库覆盖并回退到全局默认。按钮文案建议“恢复使用全局策略”。必须二次确认。成功后重新 GET effective，确认 `source=global`。

### 7.8 策略说明面板

提供中文解释，但公式只读，不允许编辑算法代码：

```text
需求分 = 库存缺口分 × 库存权重
       + 使用压力分 × 使用权重
       + 重要程度分 × 重要程度权重

库存缺口分 = clamp((目标库存 - 已承诺数量) / 目标库存, 0, 1)
使用压力分 = 近期覆盖率与近期使用强度的综合值
重要程度分 = 由知识点 importance_level 映射得出
```

重要程度映射：`core=1.0`、`important=0.75`、`normal=0.5`、`supplementary=0.25`。

重要程度分值和解释可以在 UI 展示，但最终需求分和数量必须由后端计算，禁止浏览器复制算法后自行给出另一套结果。

---

## 8. 前后端共享 API 清单

统一 Base URL：现有 `/api/v1`。认证：管理员 Bearer Token。响应包装沿用项目现有 `ApiResponse { code, message, data }`。HTTP 400 校验错误按项目现有错误处理展示，不要假设所有错误都是 HTTP 200。

| 方法 | 路径 | 用途 |
|---|---|---|
| `PATCH` | `/knowledge/{knowledge_id}/importance` | 管理员修改重要程度 |
| `GET` | `/knowledge-bases` | 查询知识库分页列表 |
| `GET` | `/question-banks/{question_bank_id}/knowledge-bases` | 查询题库知识库关联 |
| `PUT` | `/question-banks/{question_bank_id}/knowledge-bases` | 全量替换题库知识库关联 |
| `GET` | `/question-generation/policies/effective` | 查询当前生效策略 |
| `PUT` | `/question-generation/policies/global` | 保存全局策略 |
| `PUT` | `/question-generation/policies/question-banks/{question_bank_id}` | 保存题库覆盖策略 |
| `DELETE` | `/question-generation/policies/question-banks/{question_bank_id}` | 删除题库覆盖策略 |
| `POST` | `/question-generation/allocations/preview` | 智能分配预览 |
| `POST` | `/question-generation/tasks` | 创建 manual/auto 任务 |

上述为相对 `/api/v1` 的路径。不得重复拼接 `/api/v1/api/v1`。

---

## 9. TypeScript 类型设计要求

在集中类型文件中定义 API DTO，不要在各页面散落接口响应类型。字段名必须与 JSON 精确一致。

建议至少定义：

```ts
type ImportanceLevel = 'core' | 'important' | 'normal' | 'supplementary';
type ImportanceSource = 'default' | 'agent' | 'manual';
type AllocationMode = 'manual' | 'auto';
type PolicySource = 'global' | 'question_bank';

interface KnowledgeImportanceUpdateRequest {
  importance_level: ImportanceLevel;
}

interface KnowledgeImportanceUpdateData {
  knowledge_id: number;
  importance_level: ImportanceLevel;
  importance_source: ImportanceSource;
  updated_at: string;
}

interface KnowledgeBaseItem {
  id: number;
  code: string;
  name: string;
  description: string;
  status: number;
  knowledge_count: number;
  created_at: string;
  updated_at: string;
}

interface QuestionBankKnowledgeBasesData {
  question_bank_id: number;
  knowledge_bases: Array<{
    id: number;
    code: string;
    name: string;
    knowledge_count: number;
  }>;
}

interface QuestionBankKnowledgeBasesUpdateRequest {
  knowledge_base_ids: number[];
}

interface GenerationPolicy {
  stock_weight: number;
  usage_weight: number;
  importance_weight: number;
  target_stock: number;
  usage_window_days: number;
  recent_answers_per_question_target: number;
  max_per_knowledge_per_task: number;
  usage_extra_ratio: number;
  min_demand_score: number;
  is_enabled: number | boolean;
  version?: number;
  updated_at?: string;
}

interface AllocationPreviewRequest {
  question_bank_id: number;
  question_type: string; // 具体枚举从当前后端 Schema/OpenAPI 核实
  difficulty: string | number; // 具体类型从当前后端 Schema/OpenAPI 核实；API 报告示例为 "medium"
  total_question_count: number;
}

interface AllocationPreviewItem {
  knowledge_id: number;
  knowledge_name: string;
  importance_level: ImportanceLevel;
  demand_score: number;
  demand_count: number;
  allocated_count: number;
}

interface AllocationPreviewData {
  question_bank_id: number;
  requested_count: number;
  allocated_count: number;
  unallocated_count: number;
  policy_snapshot: Omit<GenerationPolicy, 'is_enabled' | 'version' | 'updated_at'>;
  items: AllocationPreviewItem[];
}
```

注意：上面为与当前 API 报告对齐的核心 DTO。若实际 Pydantic Schema 的 `difficulty`、`is_enabled` 类型不同，应以实际 Schema 更新类型并记录差异。不要为了编译通过将核心字段设为 `any`。

任务创建响应与任务详情响应应分别定义 DTO，但当前后端 API 报告将任务列表/详情的 `allocation_plan` 定义为 JSON 数组，创建响应示例也使用数组。统一使用 `AllocationPlanItem[]` 类型；详情接口若实际返回的字段比创建响应更少，可将具体字段标为可选，但不能把数组擅自解释成对象。若运行时与报告冲突，按第 1 节输出契约差异。任何 adapter 只能映射真实响应里存在的字段，不得推算后端未返回的分项分数或理由。

---

## 10. UI 状态、错误和安全体验

### 10.1 状态

每个新页面均应有：首次加载、刷新加载、空状态、错误状态、无权限、保存中、保存成功、保存失败等状态。

### 10.2 防止重复操作

- PATCH/PUT/POST 提交时禁用当前提交按钮。
- 保存成功后重新 GET 服务端数据。
- POST 创建任务遇到网络超时不自动重发。
- preview 请求可在输入变化后失效；并发预览要防止旧响应覆盖新选择结果（request id 或取消请求）。

### 10.3 权限

- 新 API 继续使用现有管理员 Bearer Token。
- Token 失效按现有登录逻辑处理。
- 不在浏览器存储或日志打印密码、完整 Token。

### 10.4 不可用配置

- 策略 `is_enabled=0` 时，智能模式显示“智能分配策略已停用”，不允许进行智能预览/创建；manual 模式仍按后端实际规则处理。
- 题库未关联知识库时，提示先设置知识范围。
- 预览 `items` 为空或 `allocated_count=0` 时显示空候选结果，不允许创建 auto 任务。
- API 报错时优先显示后端 `message`，不要显示“生成失败”作为所有错误的统一文案。

---

## 11. 端到端验收用例

必须完成真实服务联调，不能只靠 TypeScript 构建结果。

### 11.1 知识点重要程度

1. 知识点列表正确显示四个等级和三种来源。
2. 将一个知识点改为 `core`，调用 PATCH 成功。
3. 刷新列表后仍显示新值。
4. 来源显示“管理员调整”。
5. API 返回失败时前端不提前更新成功状态。

### 11.2 题库知识范围

1. 知识库列表分页和搜索正常。
2. 选中一个题库，GET 显示当前知识库关联。
3. 关联多个知识库，PUT 保存成功。
4. 刷新后关联保持。
5. 保存空数组需二次确认，并正确清空。
6. 没有知识库关联的题库不能启动 auto 预览。

### 11.3 智能出题

1. manual 模式可以选择一个知识点并创建任务。
2. auto 模式不显示单知识点选择器。
3. auto 预览请求字段与后端 Schema 一致。
4. 预览只使用后端真实返回的 `items`、`demand_score`、`demand_count`、`allocated_count` 展示。
5. 部分分配时显示 requested/allocated/unallocated，并要求管理员确认。
6. 取消确认不会调用创建任务 POST。
7. 确认后仅创建一个任务，并传 `allow_partial=true`。
8. 无候选知识点时给出可理解提示。
9. 创建任务后进入任务详情，显示实际分配快照。
10. 修改策略或生成参数后旧预览失效，必须重新预览。

### 11.4 策略管理

1. 全局策略 GET/PUT 正常。
2. 题库级策略 GET/PUT 正常。
3. 权重和不为 100 时前端阻止保存。
4. 越界值前端阻止，后端仍能返回明确校验错误。
5. 删除题库覆盖策略后，effective `source` 回到 `global`。
6. 重新加载页面时策略值与服务端一致。

### 11.5 回归与质量

- 原有登录、题库列表、AI 生成任务、任务详情轮询、题目审核、题目列表功能不回归。
- `npm run type-check` 通过。
- `npm run build` 通过。
- 浏览器控制台无新增错误。
- API 联调必须实际访问后端；如果后端服务/接口不可用，报告标记为“未验证”，不得写成“联调通过”。

---

## 12. 交付报告

完成后输出：

`ADMIN_WEB_SMART_QUESTION_ALLOCATION_REPORT.md`

报告至少包含：

1. 修改/新增文件清单。
2. 新增路由、菜单和页面说明。
3. 知识点重要程度展示、编辑和来源展示实测。
4. 题库知识库映射配置实测。
5. 智能预览请求与实际响应示例（脱敏）。
6. manual/auto 任务请求体与实际响应示例（脱敏）。
7. 策略全局 GET/PUT、题库覆盖 GET/PUT/DELETE 的实测结果。
8. API 契约核验差异及处理。
9. `type-check`、`build` 和浏览器测试结果。
10. 未完成项和阻塞项。

禁止把只读代码检查写成 API 联调通过；禁止把 mock、fixture 或静态 JSON 写成真实后端结果。

---

## 13. 给 Claude Code 的最终执行要求

先检查当前 `frontend/` 结构和现有题库管理实现；再按第 1 节核验后端真实 API；之后分模块开发：

1. 知识点重要程度；
2. 题库知识库映射；
3. 出题策略管理；
4. AI 出题 manual/auto 模式与预览；
5. 任务列表/详情快照展示；
6. 真实接口回归测试。

每个模块完成后进行类型检查和基本页面验证。遇到后端接口差异先输出差异报告，不要自行修后端、不猜字段、不虚构响应。全程只修改前端目录。
