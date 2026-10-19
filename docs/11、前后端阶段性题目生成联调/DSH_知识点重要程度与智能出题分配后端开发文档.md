# DSH 后端开发执行文档：知识点重要程度 + 智能出题分配 + 可配置出题策略

> 项目：AI 面试题库系统  
> 执行方：DSH  
> 修改范围：仅 `backend/` 及必要的数据库迁移  
> 前端配套文档：`ClaudeCode_知识点重要程度与智能出题策略前端开发文档.md`  
> 重要约束：两端必须严格采用本文第 10 节的 API 契约，不允许各自发明字段、枚举或响应结构。

---

## 0. 本次开发目标与边界

本次不是开发完整的自动补题系统，而是先建设可被“管理员主动智能出题”和“未来自动补题”共同复用的知识点需求评估及分配能力。

本次完成：

1. `Knowledge` 增加知识点重要程度字段。
2. 文档知识点提取 Agent 在提取知识点时，同时给出重要程度。
3. 管理员可以手动修改知识点重要程度；手动值不会被后续文档重复导入覆盖。
4. 明确 `question_bank` 与 `knowledge_base` 的可出题范围关系，不允许根据名称模糊匹配。
5. 实现纯业务服务 `KnowledgePointDemandService`：评估库存、使用压力、重要程度，输出需求分数和需求量。
6. 管理员主动出题支持两种模式：指定单个知识点（兼容旧流程）、系统智能分配多个知识点。
7. 智能出题支持生成前预览；预览不调用 LLM、不创建任务、不占用库存。
8. 出题策略可通过 API 配置：全局默认策略、题库级覆盖策略。
9. 任务保存当时使用的策略版本及知识点分配快照，确保历史任务可追溯。
10. 为后续自动补题复用同一个 DemandService，但本次不实现定时器、自动触发、每日自动预算任务。

本次不做：

- 不重写 `QuestionDecisionAgent`、`QuestionGenerateAgent`。
- 不在组卷时调用 LLM。
- 不实现定时自动补题。
- 不做知识点级单独策略覆盖（本次仅全局策略 + 题库级覆盖）。
- 不把 LLM 作为库存统计、准确率统计、需求分数或题量分配的计算器。
- 不修改 `frontend/`。

## 1. 开发前必须先审计现有实现

开始编码前，先检查当前代码，不可按文档盲目重复建表或接口：

1. `Knowledge` ORM、知识点 CRUD Schema/API、知识点导入和去重合并流程。
2. `KnowledgeExtractAgent` 的 Prompt、输出 Schema、批量去重及保存逻辑。
3. `knowledge_base`、`question_bank`、`knowledge` 三者目前的关系。
4. `Question`、`QuestionGenerationTask`、`QuestionAnswerRecord` 模型和索引。
5. `QuestionDecisionAgent` 输入输出结构及现有单知识点生成流程。
6. `QuestionGenerateAgent` 生成、校验、去重、保存和任务计数逻辑。
7. 当前分页响应、ApiResponse、管理员权限依赖、数据库事务规范。

如果已有字段、关系或接口已经满足下文要求，优先复用；只有缺失时才新增。完成审计后，在交付报告中列出复用项和新增项。

## 2. 知识点重要程度模型

### 2.1 枚举定义（前后端必须一致）

数据库和 API 存储稳定英文 code，前端显示中文 label：

| API/DB code | 中文名称 | 说明 | 算法基础分 |
|---|---|---|---:|
| `core` | 核心必考 | 所属领域的基础主干、关键原理、后续知识的必要前置，必须掌握 | 1.00 |
| `important` | 重点掌握 | 重要原理、常用机制或实践中经常需要理解和应用 | 0.75 |
| `normal` | 常见考点 | 有明确学习价值的常规知识点，优先级正常 | 0.50 |
| `supplementary` | 扩展了解 | 低频细节、边缘用法或补充性内容 | 0.25 |

新增及历史数据默认值：`normal`。不要使用 NULL 表示正常等级，不要用中文字符串入库。

注意：等级是知识点的内容重要程度/教学优先级判断，不等同于真实市场面试频率统计，也不等于题目难度。题目难度仍然使用原来的 `difficulty`。

### 2.2 Knowledge 字段

至少增加或确保存在：

- `importance_level`: VARCHAR，非空，默认 `normal`。
- `importance_source`: VARCHAR，非空，默认 `default`，取值 `default|agent|manual`。

如果项目已有等价字段，请映射复用，不要重复新增。

来源含义：

- `default`：旧数据迁移或系统默认值。
- `agent`：知识点提取 Agent 给出的初始等级。
- `manual`：管理员明确调整过。

### 2.3 知识点提取 Agent 的输出要求

知识点提取输出 Schema 增加 `importance_level`，只允许 `core|important|normal|supplementary`。

Prompt 应给 Agent 明确判定标准：

- `core`：文档明确体现为基础主干、核心机制、关键原理或多个知识点共同依赖的前置概念。
- `important`：文档重点讲解、反复强调，或包含重要机制、常用实践和关键限制。
- `normal`：常规知识点，内容明确且有学习/考查价值，但不属于主干或重点。
- `supplementary`：补充细节、冷门 API、边缘场景或拓展阅读。

约束：

1. 只根据输入文档内容和知识点本身判断，不得声称掌握了真实市场面试频率数据。
2. 不得因为内容长就必然标为 `core`，也不得因为内容短就必然标为 `supplementary`。
3. 若证据不足，返回 `normal`。
4. 输出非法枚举时，Schema/归一化层安全回退 `normal` 并记录警告，不得导致整批知识点静默丢失。
5. 不改变现有知识点提取数量、去重、关联关系和入库事务语义。

### 2.4 重复知识点合并时的覆盖规则

- 新知识点：保存 Agent 输出值，`importance_source=agent`。
- 匹配到已有 `importance_source=manual` 的知识点：保留管理员值，严禁被新导入文档覆盖。
- 匹配到已有 `importance_source=agent` 或 `default` 的知识点：允许按本次新证据更新等级；若本次结果缺失/非法，则保留已有等级。
- 管理员修改成功后，设置 `importance_source=manual`。
- 不允许通过重复导入把 `manual` 自动改回 `agent`。

### 2.5 迁移

为历史 Knowledge 记录设置 `importance_level='normal'`、`importance_source='default'`。迁移不得删除或重建知识点，不影响 `knowledge_base_id`、向量 ID、知识点关系和题目关联。

## 3. 题库与知识库范围关系（智能分配的前置条件）

`knowledge_base` 是资料/知识来源的大类；`question_bank` 是用户练习和组卷时选择的题目分类。二者不是同一概念：例如 Java 基础、JVM、Java 并发等多个题库可以共同来源于 Java 知识库。

智能分配必须知道一个题库允许使用哪些知识库中的知识点。禁止用题库名、知识库名或知识点名进行字符串猜测。

审计后处理：

- 若已有明确且可查询的多对多关系，复用。
- 若没有，新增 `question_bank_knowledge_base` 多对多关联表，包含主外键、唯一约束及必要索引。
- 一个题库可以关联多个知识库；一个知识库也可以供多个题库使用。
- 知识点候选集合 = 题库显式关联的知识库下，状态有效且允许出题的知识点。
- 关联变更只影响之后的新任务；已创建任务的分配快照不变。

如果题库尚未关联任何知识库，智能预览应返回明确的配置提示；不得退化为全库随机选择。旧的手动单知识点模式保持兼容，但创建任务时仍应校验该知识点与目标题库的归属规则；若旧项目原本没有该校验，需明确处理兼容性并在报告说明。

## 4. KnowledgePointDemandService 算法规范

### 4.1 职责分层

新建或复用纯业务服务 `KnowledgePointDemandService`，建议暴露：

- `evaluate(question_bank_id, question_type, difficulty, policy_snapshot)`：查询候选知识点统计并计算需求指标。
- `allocate(evaluations, requested_count, policy_snapshot)`：将总题量分配给多个知识点。
- `preview(...)`：返回可解释的预览结果，不写数据库、不调用 LLM。

自动补题未来可以调用同一个 `evaluate()` 和 `calculate_gap()`；当前不得把定时调度混入此 Service。

`QuestionDecisionAgent` 可以继续负责生成计划结构或对分配计划进行内容层校验，但不能更改算法确定的知识点集合和每个知识点的硬性分配数量。最终落库前由代码校验总数、知识点范围和数量。

### 4.2 库存口径

每个知识点分别统计：

- `published_count`：已发布、可用于组卷的题目数。
- `pending_review_count`：待审核题目数。
- `reserved_count`：其他 `pending/running` 任务已经分配给该知识点、尚未完成的预留题量。
- `recent_answer_count`：最近 `usage_window_days` 天的答题记录数。
- `recent_used_question_count`：上述窗口内至少被答过一次的不同题目数。

`committed_count = published_count + pending_review_count + reserved_count`。

注意：待审核题和预留题不计入用户可用库存，但在避免重复生产时作为承诺库存扣减。`rejected/disabled` 不计库存。对同一任务自身的 reservation 不能重复计入。

预留数量应从任务保存的 allocation snapshot 中可靠聚合；终态任务不再占用 reservation。必要时增加适当索引。统计查询应避免 N+1，应按候选知识点批量聚合。

### 4.3 指标公式（首版固定算法，参数可配置）

配置权重均为百分数，必须满足：

`stock_weight + usage_weight + importance_weight = 100`

默认值：`50 / 30 / 20`。

**库存不足分 `stock_score`：**

`stock_score = clamp((target_stock - committed_count) / target_stock, 0, 1)`

默认 `target_stock=20`。

**使用压力分 `usage_score`：**

- `recent_coverage = recent_used_question_count / max(published_count, 1)`，限制到 `[0,1]`。
- `recent_intensity = min(recent_answer_count / max(published_count * recent_answers_per_question_target, 1), 1)`。
- `usage_score = 0.5 * recent_coverage + 0.5 * recent_intensity`。

默认 `usage_window_days=30`，`recent_answers_per_question_target=3`。这两个参数都应可配置。

第一版只能把已经提交并落入 `question_answer_record` 的答题行为作为使用数据。不得把答题次数表述成真实展示次数；未提交就离开的题目展示量暂不统计。

**重要程度分 `importance_score`：**

- `core=1.00`
- `important=0.75`
- `normal=0.50`
- `supplementary=0.25`

**综合需求分 `demand_score`：**

`demand_score = stock_score * stock_weight/100 + usage_score * usage_weight/100 + importance_score * importance_weight/100`

结果限制 `[0,1]`，保存/返回时保留 4 位小数。

### 4.4 需求数量与“库存很多但使用压力高”的处理

不能只用 `target_stock - committed_count` 决定需求，否则库存已达标但使用压力很高的知识点永远不会补题，不符合业务目标。

使用以下可配置规则计算建议需求量：

- `base_gap = max(target_stock - committed_count, 0)`
- `usage_extra = ceil(target_stock * usage_score * usage_extra_ratio)`
- `demand_count = min(max(base_gap, usage_extra), max_per_knowledge_per_task)`

默认 `usage_extra_ratio=0.5`，`max_per_knowledge_per_task=10`。

含义：库存不足时按缺口优先；即使库存不少，近期使用压力高也允许有额外补充量；单个任务对单个知识点仍有上限。

若 `demand_score < min_demand_score`，该知识点不进入本次智能分配候选集。默认 `min_demand_score=0.15`。所有参数必须做服务端范围校验。

### 4.5 多知识点题量分配

1. 先按 `demand_score` 和 `demand_count` 过滤候选。
2. 按 demand_score 比例进行加权分配。
3. 每个知识点分配数不得超过 `demand_count` 和 `max_per_knowledge_per_task`。
4. 整数化采用最大余数法；某候选达到上限后，将剩余题量在其他候选中迭代分配。
5. 输出分配总数、未分配数量和原因。
6. `allocatable_count` 不得超过 requested_count，也不得超过所有候选 demand_count 的合计。
7. 如果候选容量不足，允许部分分配，但必须通过前端再次确认；不可虚报达到 requested_count。
8. 不得跨题库使用未关联知识库的知识点。

需求评分只决定数量分配优先级。若管理员指定单个知识点，保留原来的手动模式，不运行多知识点分配；仍需做基本范围校验。

## 5. 可配置策略

### 5.1 策略作用域

只支持：

- 全局默认策略。
- 题库级覆盖策略。

题库没有覆盖策略时继承全局策略。删除/重置题库覆盖后恢复继承。不要在本次做知识点级策略覆盖。

### 5.2 可编辑字段及默认值

| 字段 | 类型 | 默认值 | 校验 |
|---|---|---:|---|
| `stock_weight` | int | 50 | 0~100 |
| `usage_weight` | int | 30 | 0~100 |
| `importance_weight` | int | 20 | 0~100 |
| `target_stock` | int | 20 | 1~500 |
| `usage_window_days` | int | 30 | 1~365 |
| `recent_answers_per_question_target` | int | 3 | 1~100 |
| `usage_extra_ratio` | number | 0.5 | 0~2，最多 2 位小数 |
| `max_per_knowledge_per_task` | int | 10 | 1~50 |
| `min_demand_score` | number | 0.15 | 0~1，最多 4 位小数 |
| `is_enabled` | bool | true | boolean |

三个权重保存前必须合计 100。`is_enabled=false` 时禁止使用该策略进行智能自动分配，但不影响管理员指定单知识点模式。

每次更新版本号递增。建议保留修改人、修改时间；如已有操作日志能力则复用。任务创建时保存完整 policy snapshot，而不只是 policy_id。

## 6. 并发、快照和任务可靠性

### 6.1 分配预览

预览仅供显示，不保留库存、不创建任务；预览数据不是创建任务时的最终承诺。任务创建时必须重新评估。

### 6.2 任务创建原子性

智能分配的最终评估、分配、reservation 写入和 `QuestionGenerationTask` 创建必须在可靠事务内完成。应锁定涉及候选 Knowledge 的行（或使用经过验证的等价并发控制），避免两个并发管理员任务同时看到相同缺口并重复占用。

请勿用“先计算，事务外再写 task”造成竞态。

任务创建后记录：

- `allocation_mode` (`manual|auto`)
- `allocation_plan` JSON 快照（最终每个知识点实际分配量）
- `policy_snapshot` JSON（auto 模式）
- `requested_count`、`allocated_count`、`unallocated_count`

若已有 `request_config` JSON，可扩展保存；但任务详情 API 必须按第 10 节输出独立、稳定的 `allocation_plan` 字段。若需要新增数据库字段，使用 Alembic。

### 6.3 执行失败和预留释放

- 生成中的任务只预留尚未完成的计划数量。
- 题目成功生成后，已生成数量通过题目 `pending_review` 库存体现，不再重复作为 reservation 计算。
- 任务进入终态后，未完成的预留自动释放。
- 任务失败/部分成功必须保持实际成功、重复跳过和失败数量准确。
- 进程重启恢复本次不要求实现，但已有 running 任务的预留处理必须有明确规则，避免永不释放或重复占用。至少由现有异常/启动恢复机制将不可恢复的遗留任务转终态；若本次无法实现，必须在报告列为阻塞，并说明 reservation 如何过期/释放，不能静默永久占用库存。

## 7. 知识点重要程度 API

现有 `GET /knowledge` 列表及知识点详情响应增加：

- `importance_level`
- `importance_source`

增加独立更新接口：

`PATCH /api/v1/knowledge/{knowledge_id}/importance`

请求：

```json
{"importance_level":"core"}
```

响应 data：

```json
{
  "id": 101,
  "importance_level": "core",
  "importance_source": "manual",
  "updated_at": "2026-10-16T10:30:00"
}
```

权限：管理员。未知枚举返回统一业务校验错误。更新成功后将来源设为 `manual`。

## 8. 题库与知识库范围 API

如果项目已有等价 API，复用并确保契约字段一致；否则实现：

- `GET /api/v1/knowledge-bases?page=1&page_size=100&keyword=`：分页返回知识库列表，item 至少 `id,name,description,status,knowledge_count`。
- `GET /api/v1/question-banks/{question_bank_id}/knowledge-bases`：返回该题库已关联的知识库。
- `PUT /api/v1/question-banks/{question_bank_id}/knowledge-bases`：完整替换关联集合，请求 `{"knowledge_base_ids":[1,2]}`；响应返回已保存 ID 集合。

只有管理员可以修改关联。必须校验题库和所有知识库存在。更新时事务化替换映射。空数组表示明确清空映射；清空后智能预览不可用。

## 9. 智能出题与策略 API

所有接口沿用现有 `ApiResponse {code,message,data}` 和管理员 Bearer Token。分页继续沿用项目现有 `PaginatedData {items,page,page_size,total}`。

### 9.1 查询生效策略

`GET /api/v1/question-generation/policies/effective?question_bank_id=1`

返回字段见第 10 节契约。

### 9.2 保存全局策略

`PUT /api/v1/question-generation/policies/global`

### 9.3 保存题库级策略

`PUT /api/v1/question-generation/policies/question-banks/{question_bank_id}`

两个 PUT body 都使用同一个 policy request schema。题库级策略缺失时，GET effective 返回全局策略并标记 `source=global_default`；题库级策略存在时标记 `source=question_bank_override`。

### 9.4 删除题库级覆盖

`DELETE /api/v1/question-generation/policies/question-banks/{question_bank_id}`

删除覆盖后继承全局策略，不得删除全局策略。

### 9.5 智能分配预览

`POST /api/v1/question-generation/allocations/preview`

只计算、不创建任务、不调用模型、不占用 reservation。请求和响应严格按第 10 节。

### 9.6 创建生成任务（兼容旧接口）

继续使用：`POST /api/v1/question-generation/tasks`

新增字段：

- `allocation_mode`: `manual|auto`。
- `knowledge_id`: auto 模式必须省略或 null；manual 模式必填。
- `allow_partial`: 可选 bool，默认 false。只有预览显示分配不足时，管理员确认后才传 true。

兼容旧请求：如果未传 `allocation_mode` 且传了 `knowledge_id`，按 `manual` 处理。

auto 模式必须重新计算，不能直接信任前端预览中提交的知识点 ID 和数量。响应返回 task_id 和最终分配摘要。

### 9.7 任务列表和详情

现有任务列表字段兼容保留。新增 `allocation_mode`、`requested_count`、`allocated_count`、`unallocated_count`（如果现有字段不等价）。任务详情新增 `allocation_plan`。具体结构见第 10 节。

## 10. 前后端共享 API 契约（必须逐字对齐）

本节是 DSH 和 Claude Code 的共同事实来源。字段名、大小写、枚举、嵌套层级不可自行更改。

### 10.1 重要程度常量

```json
[
  {"value":"core","label":"核心必考","description":"基础主干、关键原理、必要前置概念"},
  {"value":"important","label":"重点掌握","description":"重要机制、常见实践和关键限制"},
  {"value":"normal","label":"常见考点","description":"常规且有学习价值的知识点"},
  {"value":"supplementary","label":"扩展了解","description":"低频细节、边缘用法和补充内容"}
]
```

`importance_source` 枚举：`default|agent|manual`；中文展示：系统默认、AI 标注、管理员调整。

### 10.2 Knowledge 列表项字段增加

```json
{
  "id": 101,
  "name": "HashMap 底层原理",
  "knowledge_base_id": 1,
  "importance_level": "important",
  "importance_source": "agent"
}
```

仅展示为示例；不得删除原有 KnowledgeResponse 字段。

### 10.3 知识库范围接口

`GET /knowledge-bases` data:

```json
{
  "items": [
    {"id":1,"name":"Java","description":"Java 语言与平台知识","status":"active","knowledge_count":120}
  ],
  "page": 1,
  "page_size": 100,
  "total": 1
}
```

`GET /question-banks/1/knowledge-bases` data:

```json
{
  "question_bank_id": 1,
  "items": [
    {"id":1,"name":"Java","description":"Java 语言与平台知识","knowledge_count":120}
  ],
  "knowledge_base_ids": [1]
}
```

`PUT /question-banks/1/knowledge-bases` request:

```json
{"knowledge_base_ids":[1,2]}
```

response data:

```json
{"question_bank_id":1,"knowledge_base_ids":[1,2],"updated_at":"2026-10-16T10:30:00"}
```

### 10.4 生效策略查询

`GET /question-generation/policies/effective?question_bank_id=1` data:

```json
{
  "question_bank_id": 1,
  "source": "global_default",
  "policy": {
    "stock_weight": 50,
    "usage_weight": 30,
    "importance_weight": 20,
    "target_stock": 20,
    "usage_window_days": 30,
    "recent_answers_per_question_target": 3,
    "usage_extra_ratio": 0.5,
    "max_per_knowledge_per_task": 10,
    "min_demand_score": 0.15,
    "is_enabled": true,
    "version": 1,
    "updated_at": "2026-10-16T10:30:00"
  },
  "importance_levels": [
    {"value":"core","label":"核心必考","description":"基础主干、关键原理、必要前置概念","score":1.0},
    {"value":"important","label":"重点掌握","description":"重要机制、常见实践和关键限制","score":0.75},
    {"value":"normal","label":"常见考点","description":"常规且有学习价值的知识点","score":0.5},
    {"value":"supplementary","label":"扩展了解","description":"低频细节、边缘用法和补充内容","score":0.25}
  ]
}
```

### 10.5 策略保存请求

`PUT /question-generation/policies/global` 和 `PUT /question-generation/policies/question-banks/1` request body：

```json
{
  "stock_weight": 50,
  "usage_weight": 30,
  "importance_weight": 20,
  "target_stock": 20,
  "usage_window_days": 30,
  "recent_answers_per_question_target": 3,
  "usage_extra_ratio": 0.5,
  "max_per_knowledge_per_task": 10,
  "min_demand_score": 0.15,
  "is_enabled": true
}
```

response data 为保存后的完整策略字段，包含 `version`、`updated_at`。权重合计不是 100 返回业务错误，不得静默归一化。

### 10.6 智能分配预览请求

`POST /question-generation/allocations/preview`：

```json
{
  "question_bank_id": 1,
  "question_type": "SINGLE_CHOICE",
  "difficulty": 2,
  "count": 20
}
```

response data：

```json
{
  "question_bank_id": 1,
  "allocation_mode": "auto",
  "requested_count": 20,
  "allocatable_count": 18,
  "unallocated_count": 2,
  "is_fully_allocatable": false,
  "policy_version": 3,
  "summary": {
    "candidate_knowledge_count": 12,
    "selected_knowledge_count": 4
  },
  "allocations": [
    {
      "knowledge_id": 101,
      "knowledge_name": "HashMap 底层原理",
      "knowledge_base_id": 1,
      "knowledge_base_name": "Java",
      "importance_level": "core",
      "importance_label": "核心必考",
      "published_count": 8,
      "pending_review_count": 2,
      "reserved_count": 0,
      "recent_used_question_count": 7,
      "recent_answer_count": 80,
      "stock_score": 0.5,
      "usage_score": 0.95,
      "importance_score": 1.0,
      "demand_score": 0.685,
      "demand_count": 10,
      "allocated_count": 8,
      "reason_codes": ["LOW_STOCK","HIGH_USAGE","HIGH_IMPORTANCE"],
      "reason_summary": "可用库存偏少，近期使用频繁，重要程度为核心必考"
    }
  ],
  "warnings": ["当前候选知识点最多可分配 18 道，少于目标 20 道"]
}
```

`allocations` 按实际分配数量降序，再按 demand_score 降序。若 `allocatable_count=0`，返回空数组及明确 warnings，不得返回成功的虚假分配。

### 10.7 创建任务请求

**自动分配模式：**

```json
{
  "allocation_mode": "auto",
  "question_bank_id": 1,
  "question_type": "SINGLE_CHOICE",
  "difficulty": 2,
  "count": 20,
  "allow_partial": true
}
```

**指定知识点模式：**

```json
{
  "allocation_mode": "manual",
  "knowledge_id": 101,
  "question_bank_id": 1,
  "question_type": "SINGLE_CHOICE",
  "difficulty": 2,
  "count": 5
}
```

旧版省略 `allocation_mode` 但传 `knowledge_id` 的请求必须继续按 manual 工作。

创建响应 data：

```json
{
  "task_id": 1001,
  "status": "pending",
  "allocation_mode": "auto",
  "requested_count": 20,
  "allocated_count": 18,
  "unallocated_count": 2,
  "message": "任务已创建，已按智能分配方案创建 18 道题目生成计划"
}
```

若 `allocatable_count < count` 且 `allow_partial=false`，返回明确业务错误 `ALLOCATION_INSUFFICIENT`，data 中包含 `allocatable_count` 和 `unallocated_count`，不创建任务、不占 reservation。用户确认后前端带 `allow_partial=true` 再提交；提交时重新计算。

### 10.8 任务详情分配快照

现有任务详情字段全部保留，新增：

```json
{
  "allocation_plan": {
    "allocation_mode": "auto",
    "requested_count": 20,
    "allocated_count": 18,
    "unallocated_count": 2,
    "policy_version": 3,
    "items": [
      {
        "knowledge_id": 101,
        "knowledge_name": "HashMap 底层原理",
        "knowledge_base_id": 1,
        "knowledge_base_name": "Java",
        "importance_level": "core",
        "importance_label": "核心必考",
        "planned_count": 8
      }
    ]
  }
}
```

手动模式也返回 `allocation_plan`，其中只包含一个知识点，`allocation_mode=manual`、`policy_version=null`。

## 11. 错误处理约定

沿用现有 `ApiResponse` 与 BusinessException code/message 风格。至少覆盖：

- 不存在的题库/知识库/知识点。
- 题库未配置知识库范围：`QUESTION_BANK_SCOPE_NOT_CONFIGURED`。
- 策略未启用：`QUESTION_DEMAND_POLICY_DISABLED`。
- 权重合计不等于 100：`INVALID_POLICY_WEIGHTS`。
- 无候选知识点：`NO_ELIGIBLE_KNOWLEDGE_POINTS`（预览优先返回 0 capacity + warnings；创建时拒绝）。
- 分配容量不足：`ALLOCATION_INSUFFICIENT`。
- 非法 importance enum。
- 候选知识点不属于题库允许范围。

不要向前端返回堆栈或数据库内部异常。

## 12. 测试要求

### 12.1 Knowledge importance

- 迁移旧数据均为 normal/default。
- 提取 Agent 输出四个等级均能通过 schema 并入库。
- 非法值安全回退 normal 并记录警告。
- 管理员改为 manual 后，重新导入相似文档不覆盖。
- GET knowledge 列表和详情返回 importance_level/source。

### 12.2 Mapping

- 一个题库可关联多个知识库。
- 一个知识库可被多个题库引用。
- 非法 ID 拒绝。
- 空映射后 auto preview 明确阻止。
- auto 候选严格限制在题库映射范围内。

### 12.3 算法

- 库存少时 stock_score 更高。
- recent coverage/answer 数增大时 usage_score 不下降。
- importance 等级越高 importance_score 越高。
- 库存充足但 usage_score 高时仍有 demand_count。
- 生成中 reservation 会降低重复分配。
- disabled/rejected 不计入库存。
- 分配总数、每点上限、最大余数分配正确。
- 总需求不足时返回 allocatable_count 与 unallocated_count。
- preview 不写库、不创建任务、不调用 LLM。

### 12.4 API/端到端

- manual 老请求不回归。
- auto preview 输出与同一数据下任务创建的最终分配规则一致（创建前数据发生改变时允许不同，必须以创建快照为准）。
- 创建 auto 任务后任务详情能回显分配快照。
- 两个并发 auto 请求不会重复超额占用同一批缺口。
- 生成 Agent 按快照中每个知识点 planned_count 生成，不能擅自更换知识点或总量。
- 题目入库字段保持现有正确的 `question_bank_id` 和 `question_knowledge` 关系。
- 全量原有测试通过。

建议至少覆盖单元测试、API 测试、并发测试，以及一次真实模型生成冒烟测试。真实模型不可用时，明确区分 Mock 单测与真实模型冒烟，不得声称真实生成成功。

## 13. 交付物

新增：

- `backend/docs/QUESTION_POINT_DEMAND_AND_POLICY_API.md`：最终 API 文档（应与本文第 10 节一致）。
- `backend/docs/QUESTION_POINT_DEMAND_IMPLEMENTATION_REPORT.md`：开发报告。

报告必须包含：

1. 修改/新增文件清单。
2. ORM 和 Alembic 变更。
3. knowledge importance 的提取、持久化、手动覆盖行为。
4. 题库-知识库映射实现及配置情况。
5. 算法公式、默认策略和并发 reservation 处理。
6. 所有新增/修改接口完整请求响应示例。
7. 单测、API、并发和真实模型测试结果。
8. 已知限制。

完成前请自行逐字段核对本文第 10 节 API 契约，不允许前端开始联调后才临时更改字段名或路径。若发现项目现有结构使某项契约无法实现，先在报告中明确指出并提供兼容方案，不要静默改变契约。
