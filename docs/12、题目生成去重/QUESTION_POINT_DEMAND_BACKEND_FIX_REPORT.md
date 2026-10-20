# 智能出题策略与知识范围映射后端修复报告

> 执行依据：`docs/11、前后端阶段性题目生成联调/DSH修复后端_智能出题策略与知识范围映射后端问题修复执行文档.md`

---

## 1. 修复清单

| # | 问题 | 根因 | 修复 | 状态 |
|---|------|------|------|------|
| 1 | PUT /api/v1/question-banks/{id}/knowledge-bases 返回 500 | `TimestampMixin`（`app/models/base.py:19-31`）缺失 `default=func.now()` | 补充 `default=func.now()` + 保留 `server_default` | ✅ 已修复 |
| 2 | PUT 传入重复 ID 触发 IntegrityError | `set_question_bank_knowledge_bases()`（`app/api/v1/knowledge_base_mapping.py:124`）未去重 | `kb_ids = list(dict.fromkeys(request.knowledge_base_ids))` | ✅ 已修复 |
| 3 | 新建策略 `version += 1` 报 TypeError | `policy_service.py:65,83` 新建 policy 时 `version=None` | `policy.version = (policy.version or 0) + 1` | ✅ 已修复 |
| 4 | 预览 0 候选无 warning | `_get_knowledge_base_ids()` 返回空集时不区分场景 | 3 种场景 warning：`QUESTION_BANK_SCOPE_NOT_CONFIGURED` / `NO_KNOWLEDGE_IN_SCOPE` / `ALL_BELOW_MIN_DEMAND` | ✅ 已修复 |
| 5 | 自动出题任务 knowledge_id=None | `background_runner.py:46` 仅从 `request_config.get("knowledge_id")` 获取，auto 模式下为 None | 重写生成循环：auto 模式从 `task.allocation_plan.items[]` 提取 targets，逐 target 生成 | ✅ 已修复 |

---

## 2. API 契约一致性（前端零修改）

以下接口与 `frontend/src/types/questionDemand.ts`、`frontend/src/api/questionDemand.ts` 对齐：

| 接口 | 前端期望 | 后端响应 | 一致 |
|------|----------|----------|------|
| GET /question-generation/policies/effective | `{policy: {...}, source, policy_version}` | `data.policy` + `data.source` + `data.policy_version` | ✅ |
| PUT /question-generation/policies/global | PolicyRequest 8 字段 | 接收并返回 PolicyResponse | ✅ |
| PUT /policies/question-banks/{id} | 同上 | 同上 | ✅ |
| POST /allocations/preview | `{question_bank_id, question_type, difficulty, count}` | `{allocations[], warnings[], summary, ...}` | ✅ |
| POST /tasks (auto) | TaskCreateRequest with allocation_mode | TaskCreateResponseData with allocation_mode | ✅ |
| GET /tasks/{id} | 含 allocation_plan, questions[] | 完整返回 | ✅ |
| PATCH /knowledge/{id}/importance | ImportanceResponse with `id` | 返回 `id` | ✅ |

---

## 3. 算法与并发安全

### 3.1 分配算法

- **需求评分**：`demand_score = stock_score × stock_weight/100 + usage_score × usage_weight/100 + importance_score × importance_weight/100`
- **库存评分**：`stock_score = clamp((target_stock - committed_count) / target_stock, 0, 1)`
- **使用评分**：`usage_score = 0.5 × recent_coverage + 0.5 × recent_intensity`
- **分配数量**：`demand_count = min(max(base_gap, usage_extra), max_per_knowledge_per_task)`
- **最大余数法**：按比例取整分配，余数按小数部分降序补齐，受单知识点上限约束
- **权重校验**：3 权重之和必须 = 100，否则返回 `INVALID_POLICY_WEIGHTS`

### 3.2 并发安全

- **策略保存**：每次 PUT 递增 `version`，使用 `(policy.version or 0) + 1` 保证幂等
- **预分配计数**：从 `QuestionGenerationTask.allocation_plan` JSON 聚合 pending/running 任务的预留量，避免额外表
- **背景执行**：`background_runner.py` 使用 `Semaphore(1)` 限制并发生成数为 1，独立 `SessionLocal`，异常时 rollback + close
- **事务边界**：题目 + 选项 + 知识点关联在同一事务内，任一步失败回滚

---

## 4. 真实 API 冒烟测试结果

服务运行在 `http://127.0.0.1:8000`，通过 `Invoke-RestMethod` 逐接口测试：

| # | 测试 | 结果 | 说明 |
|---|------|------|------|
| 1 | GET /knowledge-bases | ✅ code:0 | 5 个知识库 |
| 2 | GET /question-banks | ✅ code:0 | 8 个题库 |
| 3 | PUT /question-banks/1/knowledge-bases [1,2,3] | ✅ code:0 | 映射保存成功 |
| 4 | GET /question-banks/1/knowledge-bases | ✅ code:0 | 返回 [1,2,3] |
| 5 | GET /policies/effective | ✅ code:0 | source:global_default, version:2 |
| 6 | POST /allocations/preview (count=10) | ✅ code:0 | 10/10 allocatable, 10 allocations |
| 7 | POST /tasks (auto, count=5) | ✅ code:0 | task_id=6, 5/5 allocated |
| 8 | GET /tasks/6 (detail) | ✅ code:0 | allocation_plan 5 items 正确保存 |
| 9 | PUT /policies/global (weights 40/35/25) | ✅ code:0 | version=3 |
| 10 | PUT /policies/global (weights sum=110) | ✅ code:40001 | INVALID_POLICY_WEIGHTS |
| 11 | PATCH /knowledge/1/importance | ✅ code:40401 | ID 1 不存在（预期） |
| 12 | DELETE /policies/question-banks/1 | ✅ code:40401 | 无 QB 级策略（预期） |
| 13 | POST /tasks (auto, count=5) **修复后** | ✅ code:0 | task_id=7 |
| 14 | GET /tasks/7 **修复后** | ✅ code:0 | **status:success, 5/5 generated** |

---

## 5. 测试覆盖

| 测试套件 | 数量 | 结果 |
|----------|------|------|
| test_question_demand.py | 19 | ✅ 全部通过 |
| test_knowledge_base_mapping.py | 12 | ✅ 全部通过 |
| 全量后端测试 | 87 | ✅ 全部通过 |
| Agent 测试 | 47 | ✅ 全部通过 |

### 测试场景覆盖

- 策略管理：CRUD、权重校验、版本递增、question_bank 级覆盖
- 分配预览：有/无映射、有/无知识点、低于 min_demand_score、数量一致性
- 自动出题：auto 模式创建、allow_partial、不足分配、allocation_plan 保存
- 知识范围映射：PUT 成功/替换/幂等/空/不存在题库/不存在知识库/部分回滚/重复 ID
- 认证：无 Token 403、错误 Token 403

---

## 6. 关键代码变更

| 文件 | 变更 |
|------|------|
| `app/models/base.py` | TimestampMixin 补充 `default=func.now()` |
| `app/api/v1/knowledge_base_mapping.py:124` | 去重 `kb_ids = list(dict.fromkeys(...))` |
| `app/services/policy_service.py:65,83` | `policy.version = (policy.version or 0) + 1` |
| `app/services/knowledge_demand_service.py` | preview() 区分 3 种 0 候选场景并生成 warning |
| `app/services/background_runner.py` | 支持 auto allocation：从 allocation_plan.items 提取 targets |

---

## 7. 已知限制

1. `datetime.utcnow()` 已弃用（Python 3.12+），后续应迁移至 `datetime.now(datetime.UTC)`
2. `question_bank.py` 使用了 Pydantic class-based config（已弃用），后续应迁移至 `ConfigDict`
3. 预分配计数基于 JSON 查询 pending/running 任务，大量并发任务时有轻微性能开销

---

## 8. V1.0 暂缓

- 策略变更审计日志
- 分配算法缓存
- 出题质量评估（QuestionEvaluateAgent）
- 解析结果向量去重
