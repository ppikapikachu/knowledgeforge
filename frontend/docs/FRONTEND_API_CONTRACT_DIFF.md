# 前端 API 契约差异报告

> 核验日期：2026-10-19
> 核验依据：`backend/app/api/v1/`、`backend/app/schemas/`、`backend/app/models/` 源码
> 结论：**开发文档中的多处示例/描述与后端实际代码不一致，以下以前端实际后端源码为准。**

---

## 1. 任务创建 `POST /api/v1/question-generation/tasks`

| 字段 | 开发文档 V1.1 | 后端实际 Schema | 处理 |
|---|---|---|---|
| `question_type` | `"single_choice"` 小写 | `"SINGLE_CHOICE"` 大写 | ✅ 以前端实际后端为准 |
| `difficulty` | `"medium"` 字符串 | `2` 整数（1/2/3） | ✅ 以前端实际后端为准 |
| `total_question_count` | 总题量字段名 | `count` | ✅ 以前端实际后端为准 |
| `explanation_requested` | 提及此字段 | **Schema 中不存在** | ✅ 不传此字段 |
| `allow_partial` | `bool` | `bool = False` | ✅ 一致 |
| `allocation_mode` | `"manual"`/`"auto"` | 同左 | ✅ 一致 |
| `knowledge_id` | manual 模式必填 | 同左 | ✅ 一致 |

**实际请求 Schema**（`TaskCreateWithAllocation`）：
```json
{
  "allocation_mode": "manual|auto",
  "knowledge_id": 1,          // manual 必填
  "question_bank_id": 1,
  "question_type": "SINGLE_CHOICE",
  "difficulty": 2,
  "count": 10,
  "allow_partial": false
}
```

---

## 2. 智能分配预览 `POST /api/v1/question-generation/allocations/preview`

### 2.1 请求字段

| 字段 | 开发文档 | 后端实际 | 处理 |
|---|---|---|---|
| `question_type` | `"single_choice"` | `"SINGLE_CHOICE"` | ✅ 以后端为准 |
| `difficulty` | `"medium"` | `2` (int) | ✅ 以后端为准 |
| `total_question_count` | 总题量 | `count` | ✅ 以后端为准 |

### 2.2 响应字段

| 字段 | 开发文档 | 后端实际 | 差异类型 |
|---|---|---|---|
| `allocated_count` | 有 | ❌ 无此字段，改为 `allocatable_count` | **字段名不同** |
| `items` | 有 | ❌ 改为 `allocations` | **字段名不同** |
| `policy_snapshot` | 有（对象含策略参数） | ❌ 改为 `policy_version`（仅 int） | **结构不同** |
| `unallocated_count` | 有 | ✅ 有 | 一致 |
| `is_fully_allocatable` | 无 | ✅ 有 | **新增字段** |
| `summary` | 无 | ✅ 有（dict） | **新增字段** |
| `warnings` | 无 | ✅ 有（List[str]） | **新增字段** |
| `allocation_mode` | 无 | ✅ 有 | **新增字段** |

### 2.3 `AllocationItem` 字段

后端实际返回 17 个字段，远多于文档的 6 个：

| 后端实际字段 | 文档是否提及 |
|---|---|
| `knowledge_id`, `knowledge_name`, `importance_level`, `demand_score`, `demand_count`, `allocated_count` | ✅ |
| `knowledge_base_id`, `knowledge_base_name` | ❌ |
| `importance_label` | ❌ |
| `published_count`, `pending_review_count`, `reserved_count` | ❌ |
| `recent_used_question_count`, `recent_answer_count` | ❌ |
| `stock_score`, `usage_score`, `importance_score` | ❌ |
| `reason_codes`, `reason_summary` | ❌ |

**处理**：以文档说明"只展示 API 报告明确提供的字段"为原则，但后端实际 Schema 更丰富；
本次按后端实际返回类型定义 DTO，UI 只展示核心字段，不展示后端未明确承诺的推荐字段。

---

## 3. 策略 API `GET/PUT /question-generation/policies/*`

### 3.1 `source` 值

| 文档 | 后端实际 |
|---|---|
| `global` | `global_default` |
| `question_bank` | `question_bank_override` |

### 3.2 字段约束差异

| 字段 | 文档范围 | 后端实际 | 差异 |
|---|---|---|---|
| `target_stock` | 1-1000 | 1-500 | 后端更严格 |
| `usage_extra_ratio` | 0-1 | 0-2 | 后端更宽松 |
| `max_per_knowledge_per_task` | 1-100 | 1-50 | 后端更严格 |
| `is_enabled` | int (0/1) | `bool` | 类型不同 |

### 3.3 `EffectivePolicyResponse`

后端额外返回 `importance_levels: List[ImportanceLevelInfo]`（含 value/label/description/score），可用于前端展示。

---

## 4. 题库知识库映射 `GET/PUT /question-banks/{id}/knowledge-bases`

### 4.1 GET 响应结构

| 文档 | 后端实际 |
|---|---|
| `knowledge_bases: [...]` | `items: [...]` + `knowledge_base_ids: [...]` |

### 4.2 GET 响应项字段

后端 `items[]` 含 `id, name, description, knowledge_count`，**无 `code`**（文档提到有 `code`）。

### 4.3 PUT 响应

后端返回 `{question_bank_id, knowledge_base_ids, updated_at}`，文档为 `{question_bank_id, knowledge_base_ids, updated_count}`。

---

## 5. 知识点重要程度 PATCH

### 5.1 响应字段

| 文档 | 后端实际 |
|---|---|
| `knowledge_id` | `id` |

---

## 6. 任务列表/详情

### 6.1 `allocation_plan` 结构

文档说是数组（`AllocationPlanItem[]`），后端实际是对象：

```json
{
  "allocation_mode": "auto",
  "requested_count": 30,
  "allocated_count": 28,
  "unallocated_count": 2,
  "policy_version": 3,
  "items": [...]
}
```

### 6.2 任务详情额外字段

后端任务详情返回 `allocation_mode`、`allocation_plan`、`requested_count`、`allocated_count`、`unallocated_count`，文档未提及这些。

---

## 7. 知识库列表

### 7.1 `status` 类型

文档说 `status: 1`（数字），后端实际返回 `status: "active"/"disabled"`（字符串）。

---

## 8. 处理原则

1. **以后端实际代码为准**（后端源码是唯一真实来源）。
2. 不猜测、不伪造、不混用两种请求结构。
3. 前端 TypeScript 类型以实际后端 Pydantic Schema 逐字段对齐。
4. 文档中的小写枚举、字符串难度、`total_question_count` 等旧草案字段不再使用。
5. 后端实际 Schema 中更丰富的字段（如 `AllocationItem` 的 17 个字段），UI 只展示核心字段，不展示未被文档承诺的推荐字段。
