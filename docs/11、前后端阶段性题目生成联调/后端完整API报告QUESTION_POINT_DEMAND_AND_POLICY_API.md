# 知识点重要程度与智能出题分配 API 文档

> 版本: V1.0 | 更新日期: 2026-10-19

---

## 1. 知识点重要程度

### 1.1 枚举值

| 枚举值 | 含义 | 分值 |
|--------|------|------|
| `core` | 核心知识点 | 1.0 |
| `important` | 重要知识点 | 0.75 |
| `normal` | 普通知识点 | 0.5 |
| `supplementary` | 补充知识点 | 0.25 |

### 1.2 来源枚举

| 枚举值 | 含义 |
|--------|------|
| `default` | 系统默认值 |
| `agent` | AI Agent 自动判断 |
| `manual` | 人工手动设置（优先级最高） |

### 1.3 手动更新知识点重要程度

```
PATCH /api/v1/knowledge/{knowledge_id}/importance
```

**请求体:**
```json
{
  "importance_level": "core"
}
```

**响应:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "knowledge_id": 1,
    "importance_level": "core",
    "importance_source": "manual",
    "updated_at": "2026-10-19T13:00:00"
  }
}
```

**规则:**
- 手动设置后 `importance_source` 变为 `manual`
- 后续 Agent 重新导入不会覆盖 `manual` 来源的值
- 只有 `default` 或 `agent` 来源的值才能被 Agent 更新

---

## 2. 题库-知识库映射

### 2.1 查询知识库列表（含知识点数量）

```
GET /api/v1/knowledge-bases?page=1&page_size=20&keyword=&status=1
```

**响应:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
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
}
```

### 2.2 查询题库关联的知识库

```
GET /api/v1/question-banks/{question_bank_id}/knowledge-bases
```

**响应:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
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
}
```

### 2.3 设置题库关联的知识库（全量替换）

```
PUT /api/v1/question-banks/{question_bank_id}/knowledge-bases
```

**请求体:**
```json
{
  "knowledge_base_ids": [1, 3, 5]
}
```

**响应:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "question_bank_id": 1,
    "knowledge_base_ids": [1, 3, 5],
    "updated_count": 3
  }
}
```

**规则:**
- 全量替换：先删除旧关联，再创建新关联
- 所有 `knowledge_base_ids` 必须存在
- 空数组表示清空关联

---

## 3. 出题策略配置

### 3.1 策略参数说明

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| `stock_weight` | int | 50 | 0-100 | 库存缺口权重 |
| `usage_weight` | int | 30 | 0-100 | 使用频率权重 |
| `importance_weight` | int | 20 | 0-100 | 重要程度权重 |
| `target_stock` | int | 20 | 1-1000 | 每个知识点目标题目数 |
| `usage_window_days` | int | 30 | 1-365 | 使用频率统计窗口（天） |
| `recent_answers_per_question_target` | int | 3 | 1-100 | 每题目标题目答题次数 |
| `max_per_knowledge_per_task` | int | 10 | 1-100 | 单次任务每知识点最大出题数 |
| `usage_extra_ratio` | float | 0.5 | 0-1 | 使用频率额外需求系数 |
| `min_demand_score` | float | 0.15 | 0-1 | 最低需求分阈值 |

**约束:** `stock_weight + usage_weight + importance_weight = 100`

### 3.2 查询全局策略

```
GET /api/v1/question-generation/policies/effective?question_bank_id=1
```

**响应:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
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
}
```

`source` 取值: `global`（全局默认）| `question_bank`（题库覆盖）

### 3.3 更新全局策略

```
PUT /api/v1/question-generation/policies/global
```

**请求体:**
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

**错误码:**
- `INVALID_POLICY_WEIGHTS` — 权重之和不等于 100

### 3.4 更新题库策略（覆盖全局）

```
PUT /api/v1/question-generation/policies/question-banks/{question_bank_id}
```

请求体同全局策略。保存后该题库使用此策略覆盖全局默认。

### 3.5 删除题库策略（回退到全局）

```
DELETE /api/v1/question-generation/policies/question-banks/{question_bank_id}
```

---

## 4. 智能出题分配

### 4.1 需求评估公式

```
demand_score = stock_score × stock_weight/100
             + usage_score × usage_weight/100
             + importance_score × importance_weight/100

stock_score = clamp((target_stock - committed_count) / target_stock, 0, 1)

usage_score = 0.5 × recent_coverage + 0.5 × recent_intensity

demand_count = min(max(base_gap, usage_extra), max_per_knowledge_per_task)

base_gap = max(0, target_stock - committed_count)
usage_extra = ceil(target_stock × usage_score × usage_extra_ratio)
```

其中:
- `committed_count` = 已有题目数 + 进行中任务预留数
- `recent_coverage` = 窗口期内有答题记录的知识点覆盖率
- `recent_intensity` = 窗口期内平均答题次数 / 目标答题次数（clamped 0-1）

### 4.2 分配预览

```
POST /api/v1/question-generation/allocations/preview
```

**请求体:**
```json
{
  "question_bank_id": 1,
  "question_type": "single_choice",
  "difficulty": "medium",
  "total_question_count": 30
}
```

**响应:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
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
}
```

### 4.3 自动分配创建出题任务

```
POST /api/v1/question-generation/tasks
```

**请求体（自动分配模式）:**
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

**请求体（手动分配模式）:**
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

**响应:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
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
    "policy_snapshot": { ... },
    "status": "pending"
  }
}
```

**错误码:**
- `ALLOCATION_INSUFFICIENT` — 可分配数不足且 `allow_partial=false`
- `NO_ELIGIBLE_KNOWLEDGE_POINTS` — 无符合条件的知识点

---

## 5. 任务列表 / 详情（新增字段）

任务响应新增字段:
- `allocation_mode`: `"manual"` | `"auto"`
- `allocation_plan`: 分配计划 JSON 数组
- `policy_snapshot`: 使用的策略快照 JSON
- `requested_count`: 请求数量
- `allocated_count`: 已分配数量
- `unallocated_count`: 未分配数量

---

## 6. KnowledgeExtractAgent 重要程度输出

Agent 提取知识点时自动判断 `importance_level`:

| 级别 | 判断依据 |
|------|----------|
| `core` | 面试高频考点、必考知识、框架核心机制 |
| `important` | 常见考点、重要概念、常用技术 |
| `normal` | 一般知识点、辅助理解内容 |
| `supplementary` | 补充说明、延伸阅读、冷门细节 |

Agent 输出写入数据库时 `importance_source = "agent"`。

---

## 7. 完整 API 列表

| 方法 | 路径 | 说明 |
|------|------|------|
| PATCH | `/api/v1/knowledge/{id}/importance` | 更新知识点重要程度 |
| GET | `/api/v1/knowledge-bases` | 知识库列表（含知识点数量） |
| GET | `/api/v1/question-banks/{id}/knowledge-bases` | 题库关联知识库 |
| PUT | `/api/v1/question-banks/{id}/knowledge-bases` | 设置题库关联知识库 |
| GET | `/api/v1/question-generation/policies/effective` | 查询生效策略 |
| PUT | `/api/v1/question-generation/policies/global` | 更新全局策略 |
| PUT | `/api/v1/question-generation/policies/question-banks/{id}` | 更新题库策略 |
| DELETE | `/api/v1/question-generation/policies/question-banks/{id}` | 删除题库策略 |
| POST | `/api/v1/question-generation/allocations/preview` | 分配预览 |
| POST | `/api/v1/question-generation/tasks` | 创建出题任务（支持 auto 分配） |
