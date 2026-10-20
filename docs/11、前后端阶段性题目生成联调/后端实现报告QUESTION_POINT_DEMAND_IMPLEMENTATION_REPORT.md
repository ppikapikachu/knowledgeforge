# 知识点重要程度与智能出题分配 实现报告

> 版本: V1.0 | 日期: 2026-10-19

---

## 1. 需求来源

根据 `docs/11、前后端阶段性题目生成联调/DSH_知识点重要程度与智能出题分配后端开发文档.md` 实现。

---

## 2. 数据库变更

### 2.1 新增表

| 表名 | 说明 |
|------|------|
| `question_bank_knowledge_base` | 题库-知识库 M2M 映射表 |
| `question_generation_policy` | 出题策略配置表（全局 + 题库覆盖） |

### 2.2 修改表

| 表名 | 新增字段 | 说明 |
|------|----------|------|
| `knowledge` | `importance_level` VARCHAR(20) | 重要程度: core/important/normal/supplementary |
| `knowledge` | `importance_source` VARCHAR(20) | 来源: default/agent/manual |
| `question_generation_task` | `allocation_mode` VARCHAR(20) | 分配模式: manual/auto |
| `question_generation_task` | `allocation_plan` JSON | 分配计划快照 |
| `question_generation_task` | `policy_snapshot` JSON | 策略快照 |
| `question_generation_task` | `requested_count` INT | 请求数量 |
| `question_generation_task` | `allocated_count` INT | 已分配数量 |
| `question_generation_task` | `unallocated_count` INT | 未分配数量 |

### 2.3 迁移文件

`migrations/versions/e5f6a7b8c9d0_add_importance_mapping_policy.py`

- 添加 `knowledge.importance_level` / `importance_source`（默认值 `normal` / `default`）
- 创建 `question_bank_knowledge_base` 表（UNIQUE(question_bank_id, knowledge_base_id)）
- 创建 `question_generation_policy` 表
- 添加 `question_generation_task` 6 个分配字段
- 插入默认全局策略

---

## 3. 新增文件

| 文件 | 说明 |
|------|------|
| `app/models/question_bank_knowledge_base.py` | 题库-知识库 M2M 模型 |
| `app/models/question_generation_policy.py` | 出题策略模型 |
| `app/schemas/question_demand.py` | 需求评估/分配/策略相关 Pydantic Schema |
| `app/services/knowledge_demand_service.py` | KnowledgePointDemandService（评估/分配/预览） |
| `app/services/policy_service.py` | PolicyService（策略 CRUD + 校验） |
| `app/api/v1/question_demand.py` | 策略 + 分配预览 API |
| `app/api/v1/knowledge_base_mapping.py` | 知识库映射 API |

---

## 4. 修改文件

| 文件 | 修改内容 |
|------|----------|
| `app/models/knowledge.py` | 添加 `importance_level` + `importance_source` 字段 |
| `app/models/question_generation_task.py` | 添加 6 个分配相关字段 |
| `app/schemas/knowledge.py` | KnowledgeResponse 添加重要程度字段；KnowledgeCreate/Update 支持可选 importance_level |
| `app/api/v1/knowledge.py` | 添加 `PATCH /{id}/importance` 端点 |
| `app/api/v1/question_generation.py` | 支持 auto 分配模式；任务详情/列表返回分配信息 |
| `app/api/router.py` | 注册新路由 |
| `agent/knowledge_extract/schemas.py` | KnowledgeCandidate 添加 `importance_level` |
| `agent/knowledge_extract/prompts.py` | 提示词升级 v4，添加重要程度判断标准 |
| `agent/knowledge_deduplicate/schemas.py` | MergedKnowledge 添加 `importance_level` |
| `app/services/knowledge_import_service.py` | 导入时写入 importance_level；合并时尊重 manual 来源 |

---

## 5. 核心算法

### 5.1 需求评估

```
demand_score = stock_score × 0.5 + usage_score × 0.3 + importance_score × 0.2

stock_score = clamp((target_stock - committed_count) / target_stock, 0, 1)
usage_score = 0.5 × recent_coverage + 0.5 × recent_intensity
importance_score = {core: 1.0, important: 0.75, normal: 0.5, supplementary: 0.25}
```

### 5.2 分配算法（最大余数法）

1. 计算每个知识点的 `demand_count`
2. 按 `demand_score` 加权分配目标数量
3. 取整后用最大余数法分配剩余数量
4. 尊重 `max_per_knowledge_per_task` 上限

### 5.3 预留数计算

从 `question_generation_task.allocation_plan` JSON 中聚合 `pending`/`running` 状态任务的分配数，避免额外表。

---

## 6. 手动优先规则

- `importance_source = "manual"` 的值永远不被 Agent 覆盖
- Agent 重新导入时只更新 `importance_source` 为 `default` 或 `agent` 的记录
- 合并已有知识点时，如果现有值是 `manual`，保留原值

---

## 7. 测试结果

### 7.1 后端测试

```
56 passed (tests/)
```

### 7.2 Agent 测试

```
47 passed (agent_tests/)
```

### 7.3 Alembic 迁移

```
alembic upgrade head → Running upgrade d4e5f6a7b8c9 -> e5f6a7b8c9d0
```

---

## 8. 待验证项

| 项目 | 状态 |
|------|------|
| 后端 API 测试 | ✅ 56/56 通过 |
| Agent 测试 | ✅ 47/47 通过 |
| Alembic 迁移 | ✅ 成功执行 |
| API 冒烟测试 | ⚠️ 未执行（需启动服务） |
| Swagger 访问 | ⚠️ 未验证（需启动服务） |

---

## 9. 设计决策

1. **预留数用 JSON 聚合** — 避免新增 `allocation_reservation` 表，V1.0 保持简单
2. **策略版本号** — 每次保存递增 `version`，便于审计
3. **全量替换映射** — `PUT /question-banks/{id}/knowledge-bases` 采用全量替换语义，避免增量同步的复杂性
4. **重要程度枚举固定** — 不支持自定义级别，保持与 Agent 输出一致
5. **ValidationException 而非 ApiResponse** — 校验错误返回 HTTP 400，而非 HTTP 200 + 错误码
