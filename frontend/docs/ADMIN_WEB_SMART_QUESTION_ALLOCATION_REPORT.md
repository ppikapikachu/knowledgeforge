# 知识点重要程度与智能出题策略 前端交付报告

> 执行方：Claude Code（仅修改 `frontend/`）
> 日期：2026-10-19
> 后端依据：`backend/app/api/v1/`、`backend/app/schemas/` 源码逐字段核对

---

## 1. 修改/新增文件清单

### 新增

| 文件 | 用途 |
|---|---|
| `src/types/questionDemand.ts` | 智能出题、策略、分配预览完整 DTO |
| `src/api/questionDemand.ts` | 重要程度、映射、策略、预览、任务创建 API |
| `src/constants/questionDemand.ts` | 重要程度/来源/策略来源/分配模式映射、策略约束 |
| `src/views/question-management/PolicyView.vue` | 出题策略管理（全局/题库级） |
| `src/views/question-management/KnowledgeScopeView.vue` | 题库知识范围配置 |
| `docs/FRONTEND_API_CONTRACT_DIFF.md` | API 契约差异报告 |

### 修改

| 文件 | 修改内容 |
|---|---|
| `src/types/knowledge.ts` | `Knowledge` 增加 `importance_level`, `importance_source` |
| `src/types/knowledgeBase.ts` | `KnowledgeBaseQueryParams` 增加 `keyword` |
| `src/types/questionManagement.ts` | `GenerationTask` 增加分配字段；`GenerationTaskDetail` 增加 `allocation_plan`, `allocation_mode` |
| `src/views/knowledge/KnowledgeList.vue` | 增加重要程度/来源列、修改重要程度对话框 |
| `src/views/question-management/GenerateQuestionView.vue` | manual/auto 双模式、分配预览、部分分配确认 |
| `src/views/question-management/GenerationTaskListView.vue` | 增加分配模式、分配数量列 |
| `src/views/question-management/GenerationTaskDetailView.vue` | 增加分配计划快照展示 |
| `src/router/index.ts` | 新增 `/question-management/policies`、`/question-management/knowledge-scope` |
| `src/layouts/AdminLayout.vue` | 新增「出题策略」「题库知识范围」菜单 |

---

## 2. 新增路由与菜单

| 路由 | 页面 | 菜单 |
|---|---|---|
| `/question-management/policies` | PolicyView | 题库管理 > 出题策略 |
| `/question-management/knowledge-scope` | KnowledgeScopeView | 题库管理 > 题库知识范围 |

---

## 3. 知识点重要程度

- **列表**：新增"重要程度"列（核心必考/重点掌握/常见考点/扩展了解，彩色标签）和"程度来源"列（系统默认/AI 标注/管理员调整）
- **编辑**：下拉菜单 → "修改重要程度"对话框，展示四级选项及说明，保存后来源自动更新为"管理员调整"
- **实测**：`PATCH /knowledge/133/importance` → `{"id":133,"importance_level":"core","importance_source":"manual"}` ✅
- **来源展示**：截图确认 `核心必考 + 管理员调整` 正确显示（API 更新的记录）

---

## 4. 题库知识库映射

- **GET**：`GET /question-banks/1/knowledge-bases` → `{"question_bank_id":1,"items":[],"knowledge_base_ids":[]}` ✅
- **PUT**：`PUT /question-banks/1/knowledge-bases` → **后端 500 错误**（`{"code":50000,"message":"系统内部错误"}`）
- **原因**：后端 `knowledge_base_mapping.py` PUT 端点存在内部错误（GET/POST 正常）
- **前端处理**：保留 UI 和调用逻辑，错误展示后端 `message`；修复后无需前端改动

---

## 5. 智能预览请求与响应

### 请求
```json
POST /question-generation/allocations/preview
{"question_bank_id":1,"question_type":"SINGLE_CHOICE","difficulty":2,"count":3}
```

### 响应（实测）
```json
{
  "code": 0,
  "data": {
    "question_bank_id": 1,
    "allocation_mode": "...",
    "requested_count": 3,
    "allocatable_count": 0,
    "unallocated_count": 3,
    "is_fully_allocatable": false,
    "policy_version": 2,
    "summary": {...},
    "allocations": [],
    "warnings": []
  }
}
```

**注意**：`allocatable_count` ≠ 文档的 `allocated_count`；`allocations` ≠ `items`；`policy_version` ≠ `policy_snapshot`。

---

## 6. 任务创建

### manual 模式（实测）
```json
POST /question-generation/tasks
{"allocation_mode":"manual","knowledge_id":133,"question_bank_id":1,
 "question_type":"SINGLE_CHOICE","difficulty":2,"count":2}

→ {"task_id":5,"status":"pending","allocation_mode":"manual",
   "requested_count":2,"allocated_count":2,"unallocated_count":0}
```

### 任务详情（实测）
分配模式"指定知识点"、分配数量 2/2/0，浏览器截图确认正确显示。

---

## 7. 策略管理 API 实测

| 操作 | 结果 |
|---|---|
| `PUT /policies/global` | ✅ 返回完整策略含 `version:2` |
| `GET /policies/effective` | ✅ `source=global_default` |
| `GET /policies/effective?question_bank_id=1` | ✅ `source=global_default` |

`source` 实际值为 `global_default`/`question_bank_override`（非文档的 `global`/`question_bank`），前端已适配。

---

## 8. API 契约核验差异

详见 `docs/FRONTEND_API_CONTRACT_DIFF.md`，主要差异：

| 项目 | 文档 | 后端实际 | 处理 |
|---|---|---|---|
| `question_type` | `"single_choice"` | `"SINGLE_CHOICE"` | 以后端为准 |
| `difficulty` | `"medium"` (string) | `2` (int) | 以后端为准 |
| `total_question_count` | 总题量字段 | `count` | 以后端为准 |
| 预览响应 | `items`, `allocated_count`, `policy_snapshot` | `allocations`, `allocatable_count`, `policy_version` | 以后端为准 |
| `source` | `global`/`question_bank` | `global_default`/`question_bank_override` | 以后端为准 |
| `is_enabled` | int | bool | 以后端为准 |
| `target_stock` max | 1000 | 500 | 以后端为准 |
| `usage_extra_ratio` | 0-1 | 0-2 | 以后端为准 |
| 知识库列表 `status` | string | int | 以后端为准 |

---

## 9. 构建与测试结果

| 项目 | 结果 |
|---|---|
| `npm run type-check` | ✅ 通过 |
| `npm run build` | ✅ `built in 4.79s` |
| 浏览器控制台错误 | ✅ 0 |
| 后端 API 真实联调 | ✅ 部分通过（见下） |

### 浏览器截图（`_smoke/`）

| 页面 | 结果 |
|---|---|
| `knowledge-list-importance.png` | ✅ 重要程度/来源列正确渲染 |
| `generate-auto.png` | ✅ manual/auto 切换、表单正确 |
| `knowledge-scope.png` | ✅ 题库选择器、空状态正确 |
| `task-detail-5.png` | ✅ 分配模式"指定知识点"、分配数量 2/2/0 |
| `policies.png` | ✅ 菜单渲染正确（截图时数据仍在加载） |

---

## 10. 未完成项和阻塞项

### 后端缺陷（不改后端，记录）

1. **PUT `/question-banks/{id}/knowledge-bases` 返回 500**：后端事务处理异常（GET/POST 正常）。前端 UI 已就绪，后端修复后无需改动。

### 后端契约差异（已按后端实际代码适配）

2. 预览响应字段名与文档示例不一致（`allocations`/`allocatable_count`）
3. `difficulty` 为整数（1/2/3），非文档说的字符串 `"medium"`
4. `source` 为 `global_default`/`question_bank_override`，非文档说的 `global`/`question_bank`
5. `is_enabled` 为 `bool`，非文档说的 `int`
6. `usage_extra_ratio` 范围 0-2，非文档说的 0-1

### 未实现（文档明确排除）

- AI 解析生成、批量审核、题目统计、自动补题——均不在本次范围

---

## 11. Mock 使用声明

**业务链路零 Mock。** 全部数据来自真实后端 API。未使用模拟状态或伪造数据。
