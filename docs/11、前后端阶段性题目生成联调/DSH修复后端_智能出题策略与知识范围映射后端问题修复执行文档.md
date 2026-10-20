# DSH：智能出题策略与知识范围映射后端问题修复执行文档

> 任务类型：后端缺陷修复、API 契约核对、真实接口联调  
> 执行方：DeepSeek Harness（DSH）  
> 修改范围：仅 `backend/`  
> 前端状态：Claude Code 已完成相关页面，不允许修改 `frontend/`  
> 依据：`ADMIN_WEB_SMART_QUESTION_ALLOCATION_REPORT.md` 及当前后端实际 Schema、Router、Service、Model

---

## 0. 本次任务目标

管理员 Web 已完成以下页面和功能：

- 知识点重要程度展示与修改；
- 题库知识范围（题库关联知识库）配置；
- 全局/题库级出题策略管理；
- 指定知识点（manual）出题；
- 智能分配（auto）出题表单与分配预览；
- 任务列表和任务详情中的分配信息展示。

前端已通过 TypeScript 检查和生产构建，但真实 API 联调发现：

1. `PUT /api/v1/question-banks/{id}/knowledge-bases` 返回 HTTP 500，导致管理员无法保存题库的知识范围映射。
2. 后端 API 文档与真实运行接口存在多处字段、枚举和值域差异，容易导致后续维护或其他调用端再次接错。
3. 当前需要补足 auto 模式从知识范围映射、策略读取、分配预览、任务创建到实际任务快照的完整真实 API 验证。不能只以单元测试通过作为功能完成依据。

**本次目标：修复上述后端问题，让现有前端不改代码即可完成：**

配置题库知识范围 → 查询生效策略 → 模拟智能分配 → 创建 auto 任务 → 查看任务分配快照。

本次不开发自动补题定时器，不改前端，不重做 Agent，不扩展无关功能。

---

## 1. 前端报告确认的现状与问题

### 1.1 已经正常的功能

前端报告记录以下接口已有真实请求或页面联调：

- `PATCH /api/v1/knowledge/{id}/importance`：重要程度更新成功，返回 `importance_source=manual`。
- `GET /api/v1/knowledge-bases`：知识库列表正常。
- `GET /api/v1/question-banks/{id}/knowledge-bases`：查询成功。
- `PUT /api/v1/question-generation/policies/global`：保存全局策略成功。
- `GET /api/v1/question-generation/policies/effective`：读取全局策略成功。
- `POST /api/v1/question-generation/allocations/preview`：请求可以返回，但本次样例为 0 个可分配知识点。
- manual 模式任务创建成功，当前前端请求字段包括 `knowledge_id`、`question_bank_id`、`question_type`、`difficulty`、`count`。

具体响应结构以 `frontend/src/api/questionDemand.ts` 和 `frontend/src/types/questionDemand.ts` 当前实现为准。执行前请只读检查这两个文件及相关页面请求，不得修改前端。

### 1.2 必须修复的问题：知识范围 PUT 返回 500

前端实测：

```http
PUT /api/v1/question-banks/1/knowledge-bases
Content-Type: application/json
Authorization: Bearer <token>
```

请求体：

```json
{
  "knowledge_base_ids": [1, 3, 5]
}
```

实际响应：

```json
{
  "code": 50000,
  "message": "系统内部错误"
}
```

GET 接口正常，但 PUT 失败。需要追查真实 traceback 和数据库事务异常，不能只在 API 层捕获异常并返回成功，也不能用前端假数据绕过。

### 1.3 当前实际 API 契约与旧文档不一致

前端已按真实后端运行结果适配。报告确认的主要差异如下：

| 项目 | 旧文档写法 | 前端实测后端行为 |
|---|---|---|
| `question_type` | 小写形式 | 大写，如 `SINGLE_CHOICE` |
| `difficulty` | 字符串 `medium` | 整数 `1/2/3` |
| 生成数量字段 | `total_question_count` | 当前 manual 请求使用 `count`；auto 请求需核对前端实际发送内容 |
| 预览数量 | `allocated_count` | `allocatable_count` |
| 预览数组 | `items` | `allocations` |
| 策略来源 | `global` / `question_bank` | `global_default` / `question_bank_override` |
| `is_enabled` | 整数 | Boolean |
| `target_stock` 最大值 | 1000 | 500 |
| `usage_extra_ratio` 范围 | 0～1 | 0～2 |
| 知识库 `status` | 字符串 | 整数 |

这些差异必须写入唯一、准确的后端 API 文档，并由 OpenAPI 与真实请求测试验证。

---

## 2. 任务 A：修复题库—知识库映射 PUT 接口

### 2.1 需要检查的代码

优先检查：

- `app/api/v1/knowledge_base_mapping.py`
- `app/models/question_bank_knowledge_base.py`
- `app/models/question_bank.py`
- `app/models/knowledge_base.py`
- 题库、知识库相关 Repository / Service
- `app/api/router.py` 路由注册
- SQLAlchemy Session 生命周期和事务处理
- Alembic migration 中映射表定义

重点核对：

1. ORM 表名、列名是否与数据库实际结构一致。
2. 映射表主键、外键和唯一约束是否正确。
3. ORM relationship 的 `back_populates`、cascade、secondary 配置是否一致。
4. PUT 端点是否同时使用 ORM relationship 修改和显式 delete/insert，导致重复操作或 Session 状态冲突。
5. 是否先删除旧关联后，在同一事务中插入新关联；异常时是否正确 rollback。
6. Pydantic 请求 Schema 的字段是否与前端请求 `knowledge_base_ids` 一致。
7. `knowledge_base_ids` 中是否存在不存在、重复、停用的 ID。
8. 数据库连接、外键约束、唯一约束或 flush/commit 是否触发异常。

**必须查看服务端真实异常日志/traceback，定位根因。禁止仅把 500 改成 200 或吞掉异常。**

### 2.2 PUT 应遵循的行为

接口：

```http
PUT /api/v1/question-banks/{question_bank_id}/knowledge-bases
```

请求：

```json
{
  "knowledge_base_ids": [1, 3, 5]
}
```

业务语义为全量替换：

- 先验证题库存在。
- 验证所有知识库 ID 均存在且符合项目当前启用状态规则。
- 拒绝非法 ID 时返回明确业务错误，不得部分写入。
- 对重复 ID 应按项目统一策略去重或明确拒绝，行为必须稳定并写入 API 文档。
- 在单个事务中完成旧映射替换。
- 成功后 commit，再返回真实保存结果。
- 中间任何一步失败必须 rollback，原有映射保持不变。
- `knowledge_base_ids: []` 表示清空该题库关联；返回 `updated_count=0`。
- 重复提交同样的 ID 集合应保持幂等，不应制造重复行。
- 数据库唯一约束 `(question_bank_id, knowledge_base_id)` 必须保留。

建议成功响应保持与前端类型一致；若当前前端读取的是 `items` 和 `knowledge_base_ids`，不要随意改名。请以 `frontend/src/api/questionDemand.ts` 及其 DTO 为准，检查 GET 和 PUT 是否使用一致的结构。

### 2.3 必须添加的测试

至少覆盖：

1. 首次设置多个知识库成功。
2. 再次 PUT 不同 ID 集合，旧关联被完整替换。
3. PUT 相同集合多次，结果不重复。
4. PUT 空数组，正确清空关系。
5. 题库 ID 不存在，返回明确 404/业务错误。
6. 知识库 ID 不存在，返回明确 400/业务错误。
7. ID 集合中一个合法、一个非法，整个事务不应部分提交。
8. 重复 ID 的处理符合文档约定。
9. GET 能读回 PUT 保存的真实关系。
10. 数据库异常时事务回滚，原关联未丢失。

---

## 3. 任务 B：统一并固化真实 API 契约

### 3.1 原则

本次前端已经依据真实后端请求进行了适配。因此：

- 先只读检查前端 API 文件和 DTO，掌握现有前端真正发送和读取的字段。
- 再检查后端 Pydantic Schema、Router、Service 和响应模型。
- 对齐后端当前实现与已完成前端，不要为了符合旧版 Markdown 而破坏前端。
- 如果确实需要改动前端正在使用的路径、字段或枚举，必须先评估兼容性；本次原则上不做破坏性变更。
- 更新 API 文档，让文档准确反映最终运行行为。

### 3.2 重要程度接口

确认：

```http
PATCH /api/v1/knowledge/{knowledge_id}/importance
```

请求：

```json
{
  "importance_level": "core"
}
```

枚举：

| 值 | 含义 | 重要度分值 |
|---|---|---:|
| `core` | 核心知识点 | 1.0 |
| `important` | 重要知识点 | 0.75 |
| `normal` | 普通知识点 | 0.5 |
| `supplementary` | 补充知识点 | 0.25 |

来源枚举：`default`、`agent`、`manual`。

必须确认：

- 手动设置后 source 变为 `manual`。
- 后续导入或知识点合并不会覆盖 `manual`。
- Knowledge 列表及详情响应均返回 `importance_level`、`importance_source`。
- 非法枚举有明确 4xx 响应。

### 3.3 题库知识库映射接口

确认以下接口与上述字段行为一致：

```http
GET /api/v1/knowledge-bases
GET /api/v1/question-banks/{question_bank_id}/knowledge-bases
PUT /api/v1/question-banks/{question_bank_id}/knowledge-bases
```

重点：`GET /question-banks/{id}/knowledge-bases` 和 PUT 成功响应的字段形状应稳定，并完整写入 API 文档。

### 3.4 策略接口

确认：

```http
GET /api/v1/question-generation/policies/effective?question_bank_id={id}
PUT /api/v1/question-generation/policies/global
PUT /api/v1/question-generation/policies/question-banks/{id}
DELETE /api/v1/question-generation/policies/question-banks/{id}
```

当前前端实测的 source 值为：

- `global_default`
- `question_bank_override`

策略字段和值域必须以实际 Pydantic Schema 为准，并确保 OpenAPI、API 文档、验证逻辑一致。前端报告实测的关键约束：

| 字段 | 前端观察到的实际约束 |
|---|---|
| `stock_weight` | 0～100 |
| `usage_weight` | 0～100 |
| `importance_weight` | 0～100 |
| 三个权重之和 | 必须为 100 |
| `target_stock` | 1～500 |
| `usage_window_days` | 1～365 |
| `recent_answers_per_question_target` | 1～100 |
| `max_per_knowledge_per_task` | 1～100 |
| `usage_extra_ratio` | 0～2 |
| `min_demand_score` | 0～1 |
| `is_enabled` | Boolean |

请核对以上值域是否为代码真实实现。如果不同，不能静默改变，应在报告中给出源码依据、实际值域和对前端的影响，并以一个最终契约为准。

### 3.5 分配预览接口

接口：

```http
POST /api/v1/question-generation/allocations/preview
```

前端报告中实测请求：

```json
{
  "question_bank_id": 1,
  "question_type": "SINGLE_CHOICE",
  "difficulty": 2,
  "count": 3
}
```

实测响应关键字段：

```json
{
  "code": 0,
  "data": {
    "question_bank_id": 1,
    "allocation_mode": "auto",
    "requested_count": 3,
    "allocatable_count": 0,
    "unallocated_count": 3,
    "is_fully_allocatable": false,
    "policy_version": 2,
    "summary": {},
    "allocations": [],
    "warnings": []
  }
}
```

上面是字段形状示意；`summary`、`allocations[]`、`warnings[]` 的完整字段必须以当前 Schema/真实接口为准，不能照抄空对象作为实际实现。

必须确认：

- `count` 与创建任务接口的总数参数语义一致。
- `question_type` 与当前前端实际使用的大小写一致。
- `difficulty` 使用整数 1/2/3（若源码确认如此）。
- 无知识点映射时返回可理解的 warnings 或明确业务错误，不能返回无说明的空数组。
- 有映射但没有符合阈值的知识点时，要区分“没有关联知识库”和“当前无知识点达到需求阈值”。
- `allocatable_count`、`unallocated_count`、`is_fully_allocatable` 三者逻辑一致。
- 预览不创建任务、不调用 QuestionGenerateAgent、不写入题目。
- 预览与后续创建任务使用同一套需求评估/分配实现，不能出现预览分配 8 道、创建后变成完全不同计划的情况；若因库存变化导致计划调整，要明确返回实际计划及原因。

### 3.6 出题任务创建接口

接口：

```http
POST /api/v1/question-generation/tasks
```

前端已实测 manual 模式请求：

```json
{
  "allocation_mode": "manual",
  "knowledge_id": 133,
  "question_bank_id": 1,
  "question_type": "SINGLE_CHOICE",
  "difficulty": 2,
  "count": 2
}
```

成功响应实测关键字段：

```json
{
  "task_id": 5,
  "status": "pending",
  "allocation_mode": "manual",
  "requested_count": 2,
  "allocated_count": 2,
  "unallocated_count": 0
}
```

auto 模式必须检查前端真实请求代码后核对。期望语义为：

- `allocation_mode: "auto"`
- `question_bank_id`
- `question_type`
- `difficulty`
- `count`
- 前端实际提交的允许部分分配字段（如果存在）
- 不提交 `knowledge_id`，因为知识点由后端算法分配

不要根据旧 API Markdown 自行创造 `total_question_count` 或 `explanation_requested` 字段。字段是否接受，以当前运行代码和前端请求为准。

创建任务时必须保存：

- allocation_mode
- requested_count
- allocated_count
- unallocated_count
- allocation_plan
- policy_snapshot 或当前模型实际使用的策略快照字段

任务列表/详情返回的字段结构要和前端 `GenerationTask`、`GenerationTaskDetail` 类型一致。任务详情必须返回创建时的分配快照，不能根据当前策略重新计算历史任务。

---

## 4. 任务 C：排查智能预览为什么返回 0 个候选

前端此次预览样例：题库 ID 1、单选题、难度 2、目标 3 道，结果 `allocatable_count=0`、`allocations=[]`。

同时题库知识库 GET 返回空映射，且 PUT 当前 500。因此首先修复 PUT 并配置有效映射，再判断算法是否正常。

按以下顺序排查：

1. 题库是否存在且处于可用状态。
2. 题库是否正确关联至少一个知识库。
3. 被关联知识库是否存在有效知识点。
4. Knowledge 记录是否有正确的 `knowledge_base_id`。
5. Knowledge 是否处于允许参与出题的状态。
6. 该知识点的重要程度是否有效。
7. 当前生效策略是否启用、权重总和是否合法。
8. 知识点库存统计是否正确排除 rejected/disabled 等不可用题目。
9. pending_review 题目和 pending/running 任务预留数量是否按设计扣减。
10. demand_score 是否低于 `min_demand_score`。
11. 当前题型/难度条件是否被错误地用于筛掉知识点（除非算法明确设计该过滤）。

API 需要区分以下情况：

- 题库未配置知识库范围；
- 题库关联知识库没有知识点；
- 有知识点，但全部低于最低需求分；
- 有符合条件知识点，但库存/单知识点上限导致可分配数少于请求数；
- 完全没有可分配知识点。

不要简单地将以上所有情况统一返回 `allocatable_count=0` 且 `warnings=[]`。

---

## 5. 任务 D：检查算法口径和任务并发安全

当前实现报告说明：

```text
demand_score = stock_score * 0.5
             + usage_score * 0.3
             + importance_score * 0.2

stock_score = clamp((target_stock - committed_count) / target_stock, 0, 1)
usage_score = 0.5 * recent_coverage + 0.5 * recent_intensity
```

请核对源码实际实现，并补充测试：

- committed_count 对题目状态的统计口径准确；待审核、已发布、驳回、下架不得不加区分地全部算作正式库存。
- 进行中任务的预留量不会重复计算，也不会永久残留。
- recent_coverage 和 recent_intensity 在无答题记录、无发布题目、窗口边界等情况下不会除零或产生 NaN。
- importance_level 到分值的映射稳定。
- `min_demand_score` 筛选边界明确。
- 每个知识点不超过 `max_per_knowledge_per_task`。
- `allocated_count + unallocated_count == requested_count`。
- 所有 allocations 的 allocated_count 求和等于 allocatable_count。
- `allow_partial`（若接口存在）为 false 时，分配不足的任务不能进入后台生成；为 true 时按明确规则创建部分任务。

并发方面：当前实现从 `question_generation_task.allocation_plan` JSON 聚合 pending/running 预留量。请评估并测试两个 auto 任务同时创建时是否可能读取相同旧库存、重复分配超额。若现有事务不能保证，至少需要采用合理的事务隔离/锁或服务层防重机制。不要未经评估就引入 Redis/Celery 或增加复杂基础设施。

---

## 6. 真实 API 冒烟与端到端测试（本次必须完成）

后端实现报告此前标记 API 冒烟测试和 Swagger 验证未执行。本次必须启动真实服务完成，不得只跑 pytest。

使用测试库或可清理的测试数据，记录具体请求和响应。不得在报告中泄露真实密码、Token 或密钥。

### 6.1 推荐验证顺序

1. 登录管理员账号获取 Token。
2. 查询题库列表。
3. 查询知识库列表。
4. 对测试题库设置知识库映射（PUT）。
5. 再 GET 映射接口确认读回正确。
6. 修改测试知识点重要程度，再 GET Knowledge 确认 `importance_source=manual`。
7. 查询该题库生效策略。
8. 保存一份题库级策略覆盖，读取确认 source 与 version。
9. 调用 allocations preview，确认有候选知识点时返回 allocations。
10. 使用相同参数创建 auto 任务。
11. 查询任务详情，确认 allocation_plan 与创建响应一致。
12. 确认任务后台执行和实际生成逻辑未被本次修复破坏。
13. 删除题库级策略覆盖，确认回退至全局策略。
14. PUT 空知识库数组，确认映射可以清空；随后恢复测试数据或明确清理。

### 6.2 必须测试的异常场景

- PUT 映射包含不存在的知识库 ID。
- PUT 清空数组。
- 题库未配置知识范围时执行 auto preview。
- 没有候选知识点时创建 auto 任务。
- 目标题量超过可分配量且不允许部分分配。
- 策略权重总和不等于 100。
- 无效 question_type、difficulty、count。
- 题库级策略删除后有效策略正确回退。
- 同一个任务参数预览与创建分配的一致性。

---

## 7. API 文档与 Swagger 交付要求

必须更新或重写：

`backend/docs/API_QUESTION_POINT_DEMAND_AND_POLICY.md`

要求：

1. 以最终后端 Pydantic Schema / Router 实现为准。
2. 每个接口写清 Method、完整路径、Query、Path、Request JSON、Response JSON、错误码、权限。
3. 给出实际的 auto preview 请求和完整响应示例。
4. 给出实际的 auto task create 请求和响应示例。
5. 给出映射 GET/PUT 完整响应。
6. 写清楚 enum 的大小写、类型、默认值和值域。
7. 写清楚 `source` 的真实取值。
8. 写清楚 `is_enabled` 的真实类型。
9. 写清楚部分分配行为和零候选行为。
10. 不允许文档继续出现与 Schema 不一致的字段名。

启动服务后验证 Swagger/OpenAPI 中上述接口均可见，Schema 与文档一致。

---

## 8. 开发约束

- 只修改 `backend/`。
- 允许只读检查 `frontend/` 中相关 API client、DTO 和页面，以确认兼容契约；严禁修改 `frontend/`。
- 不重做 KnowledgePointDemandService 算法，除非排查确认存在算法 Bug。
- 不改变已经被前端使用的请求字段/响应字段，除非先提供兼容方案并说明理由。
- 不把 HTTP 500 吞掉或伪装为成功。
- 不通过 mock、固定返回值或硬编码示例数据通过测试。
- 不引入 Redis、Celery 等新基础设施。
- 不删库、不清理用户真实数据。
- 需要数据库变更时使用 Alembic，并说明兼容性。
- 保留现有普通单元测试和 Agent 测试。

---

## 9. 验收标准

全部满足才算完成：

- [ ] PUT 题库知识库映射不再返回 500。
- [ ] PUT 成功后 GET 能读回准确映射。
- [ ] 空数组清空、非法 ID 回滚等事务测试通过。
- [ ] 全局策略与题库级策略读写、回退正常。
- [ ] 知识点重要程度更新和 Agent/manual 优先规则正常。
- [ ] auto preview 在配置有效知识范围后能返回符合实际数据的分配结果。
- [ ] preview 无候选时返回明确原因，不是无信息空结果。
- [ ] auto task create 请求与前端当前实现兼容。
- [ ] 任务分配计划和策略快照可以保存并在详情读回。
- [ ] preview 与 task create 使用同一分配算法。
- [ ] 任务预留量不会被重复计算或永久占用。
- [ ] Swagger 和 API Markdown 与实际代码一致。
- [ ] 相关后端测试通过。
- [ ] 完成真实服务 API 冒烟测试。
- [ ] 未修改 `frontend/`。

---

## 10. 交付报告

生成：

`backend/docs/QUESTION_POINT_DEMAND_BACKEND_FIX_REPORT.md`

报告必须包含：

1. PUT 映射 500 的根因、修复方式和涉及文件。
2. 事务和异常处理规则。
3. API 契约差异清单：修复前、最终真实行为、是否改变前端兼容性。
4. auto preview 实际请求/响应（使用脱敏测试数据）。
5. auto task create 实际请求/响应。
6. 配置知识范围后，为什么能/不能选出候选知识点的验证过程。
7. 任务 allocation_plan、policy_snapshot 的持久化和查询结果。
8. 策略边界、部分分配、零候选和并发预留测试结果。
9. pytest 和 Agent 测试结果。
10. Alembic 是否变更及迁移结果。
11. Swagger 验证结果。
12. 明确列出未解决问题，不能把未测项目写成已完成。

**完成定义：管理员现有 Web 可以在不改前端代码的前提下，配置题库知识范围、保存策略、看到真实智能分配预览，并成功创建一个具有正确分配快照的 auto 任务。**
