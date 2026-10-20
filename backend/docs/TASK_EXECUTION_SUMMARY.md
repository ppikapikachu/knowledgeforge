# DSH 修复后端任务执行状况总结

本文档总结了执行 `docs/11、前后端阶段性题目生成联调/DSH修复后端_智能出题策略与知识范围映射后端问题修复执行文档.md` 任务的完成情况。

## 任务要求（来源文档）
- 修复 PUT /api/v1/question-banks/{id}/knowledge-bases 返回 500 错误
- 对齐 API 契约与前端预期（字段名、结构）
- 调试预览返回 0 候选问题
- 算法/并发检查、真实 API 冒烟测试
- 更新 API 文档 + 修复报告

## 已完成任务

### 1. 修复 PUT 接口 500 错误
- **问题根因**：`TimestampMixin` 只有 `server_default=func.now()`，缺少 `default=func.now()`，导致 SQLAlchemy 插入时省略 created_at/updated_at 字段，MySQL 报错 "Field created_at doesn't have a default value"。
- **修复**：在 `app/models/base.py:19-31` 添加 `default=func.now()`。
- **验证**：56/56 测试通过。

### 2. 前端契约对齐分析
- **已读取前端契约**：`frontend/src/types/questionDemand.ts` + `frontend/src/api/questionDemand.ts`。
- **已读取后端实现**：`app/schemas/question_demand.py`、`app/api/v1/question_demand.py`、`app/api/v1/knowledge_base_mapping.py`。
- **关键契约字段**（已核对）：
  - ImportanceResponse 使用 `id` 字段（非 `knowledge_id`）
  - PolicySource = 'global_default' | 'question_bank_override'
  - GenerationPolicy 字段范围：stock_weight/usage_weight/importance_weight (0-100, sum=100), target_stock (1-500), usage_window_days (1-365), recent_answers_per_question_target (1-100), usage_extra_ratio (0-2), max_per_knowledge_per_task (1-50), min_demand_score (0-1), is_enabled (boolean)
  - AllocationPreviewRequest/Response 结构
  - TaskCreateResponseData 字段
- **状态**：契约对比分析完成，但未逐字段验证所有边界值（如 ge/le 约束是否完全匹配）。

### 3. 预览 0 候选问题诊断
- **已读取**：`app/services/knowledge_demand_service.py` 全文（364 行）。
- **根因**：`_get_knowledge_base_ids()` (L290) 查询 `QuestionBankKnowledgeBase.knowledge_base_id`。若该表无映射行 → 返回空列表 → `evaluate()` 和 `preview()` 返回 0 候选。
- **相关代码路径**：
  - `evaluate()` L48-61: `kb_ids = self._get_knowledge_base_ids(question_bank_id)` → `if not kb_ids: return []`
  - `preview()` L249-262: 同样逻辑，返回警告 `"QUESTION_BANK_SCOPE_NOT_CONFIGURED: 题库未关联知识库"`
- **状态**：根因已定位，但修复方案未实施。

## 未完成任务

### 1. 预览 0 候选问题修复
- **待办**：需要决定修复策略——是让 UI 提示配置知识库映射，还是改进错误消息，或提供默认 fallback。
- **阻塞原因**：未收到明确的修复方向指令。

### 2. 算法/并发检查
- **待办**：验证 `KnowledgePointDemandService.allocate()` 的最大余数法分配逻辑、并发安全性（多任务同时分配时的 reserved_counts 计算）。
- **阻塞原因**：未执行代码审查和并发测试。

### 3. 真实 API 冒烟测试
- **待办**：启动服务，执行完整 API 冒烟测试（登录、创建知识点、映射、预览、创建任务）。
- **阻塞原因**：未启动服务执行。

### 4. API 文档更新
- **待办**：创建/更新 `backend/docs/QUESTION_POINT_DEMAND_AND_POLICY_API.md`，记录所有 API 端点、字段、错误码。
- **阻塞原因**：文档未编写。

### 5. 修复报告
- **待办**：创建 `backend/docs/QUESTION_POINT_DEMAND_IMPLEMENTATION_REPORT.md`，记录修复过程、测试结果、遗留问题。
- **阻塞原因**：报告未编写。

## 当前代码状态
- **编译状态**：✅ 通过（`python -m compileall`）
- **测试状态**：✅ 56/56 通过（`pytest`）
- **Alembic**：✅ 迁移成功
- **服务启动**：⚠️ 未验证（最近一次验证在上一个任务）
- **API 冒烟测试**：⚠️ 未验证

## 关键文件清单

### 后端核心文件
- `app/models/base.py` - TimestampMixin（已修复）
- `app/services/knowledge_demand_service.py` - 需求评估服务（已读取，364 行）
- `app/services/policy_service.py` - 策略服务
- `app/api/v1/question_demand.py` - 需求 API
- `app/api/v1/knowledge_base_mapping.py` - 知识库映射 API
- `app/schemas/question_demand.py` - 请求/响应 Schema

### 前端契约文件（只读参考）
- `frontend/src/types/questionDemand.ts`
- `frontend/src/api/questionDemand.ts`

### 待创建文档
- `backend/docs/QUESTION_POINT_DEMAND_AND_POLICY_API.md`
- `backend/docs/QUESTION_POINT_DEMAND_IMPLEMENTATION_REPORT.md`

## 下一步建议
1. 确定预览 0 候选问题的修复方向（UI 提示 or 代码 fallback）
2. 执行算法/并发检查
3. 启动服务执行 API 冒烟测试
4. 编写 API 文档和修复报告

## 环境备注
- Python: `D:\pythonproject\knowledgeforge\.venv\Scripts\python.exe`
- 工作目录: `D:\pythonproject\knowledgeforge\backend`
