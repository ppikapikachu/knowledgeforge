# 管理员 Web 题库管理模块 — 前端交付报告

> 执行方：Claude Code（仅修改 `frontend/`，未修改 `backend/`）
> 真实后端：FastAPI + MySQL，运行于 `http://127.0.0.1:8000`
> 报告日期：2026-10-16

---

## 1. 新增 / 修改文件清单

### 新增

| 文件 | 用途 |
|---|---|
| `src/types/questionManagement.ts` | 题库、生成任务、审核请求/响应类型 |
| `src/constants/questionManagement.ts` | 题型/难度/题目状态/任务状态集中映射、归一化工具 |
| `src/api/questionBank.ts` | 题库列表/详情 API |
| `src/api/questionGeneration.ts` | 生成任务创建/列表/详情、题目审核 API |
| `src/composables/useQuestionLookups.ts` | 题库与知识点下拉数据源、ID→名称映射 |
| `src/components/question-management/QuestionPreview.vue` | 题目预览（审核/详情共用） |
| `src/components/question-management/QuestionForm.vue` | 题目编辑表单（审核/列表共用） |
| `src/components/question-management/QuestionStatusTag.vue` | 题目状态标签（大小写容错） |
| `src/components/question-management/TaskStatusTag.vue` | 任务状态标签 |
| `src/views/question-management/GenerateQuestionView.vue` | AI 生成题目 |
| `src/views/question-management/GenerationTaskListView.vue` | 生成任务列表 |
| `src/views/question-management/GenerationTaskDetailView.vue` | 生成任务详情（含轮询） |
| `src/views/question-management/QuestionReviewView.vue` | 题目审核（待审核列表） |
| `src/views/question-management/QuestionListView.vue` | 正式题目列表 |
| `src/views/question-management/QuestionDetailView.vue` | 题目详情/审核/下架 |

### 修改

| 文件 | 修改内容 |
|---|---|
| `src/types/question.ts` | `Question` 增加 `question_bank_id`；`QuestionQueryParams` 增加 `question_bank_id`（后端真实返回/支持字段） |
| `src/router/index.ts` | 新增 6 条 `question-management/*` 路由 |
| `src/layouts/AdminLayout.vue` | 新增「题库管理」菜单组（4 个子项），默认展开 |

---

## 2. 路由与页面

| 路由 | 页面 | 职责 |
|---|---|---|
| `/question-management/generate` | GenerateQuestionView | 配置参数创建 AI 出题任务 |
| `/question-management/tasks` | GenerationTaskListView | 任务列表 + 状态筛选 |
| `/question-management/tasks/:taskId` | GenerationTaskDetailView | 任务详情 + 进度轮询 + 关联题目 |
| `/question-management/review` | QuestionReviewView | 待审核题目列表 |
| `/question-management/questions` | QuestionListView | 全部题目管理（查看/编辑/下架） |
| `/question-management/questions/:questionId` | QuestionDetailView | 题目详情 + 编辑 + 发布/驳回/下架 |

侧边栏「题库管理」组：AI 生成题目 / 生成任务 / 题目审核 / 题目列表。

---

## 3. 实际接入的 API（全部真实后端）

| 方法 | 路径 | 用途 | 验证 |
|---|---|---|---|
| POST | `/api/v1/auth/login` | 登录取 token | ✅ 实测 |
| GET | `/api/v1/question-banks` | 题库列表（含 `question_count`） | ✅ 实测 |
| GET | `/api/v1/knowledge` | 知识点列表/搜索 | ✅ 实测 |
| POST | `/api/v1/question-generation/tasks` | 创建生成任务 | ✅ 实测 |
| GET | `/api/v1/question-generation/tasks` | 任务列表 | ✅ 实测 |
| GET | `/api/v1/question-generation/tasks/{id}` | 任务详情 | ✅ 实测 |
| GET | `/api/v1/questions` | 题目列表/筛选 | ✅ 实测 |
| GET | `/api/v1/questions/{id}` | 题目详情 | ✅ 实测 |
| PUT | `/api/v1/questions/{id}` | 编辑题目 | ✅ 实测 |
| DELETE | `/api/v1/questions/{id}` | 下架（软删除） | ✅ 实测 |
| POST | `/api/v1/question-generation/questions/{id}/review` | 发布/驳回 | ✅ 实测 |

---

## 4. API 字段映射依据

以 `backend/app/api/v1/*.py` 路由实现 + `backend/app/models/*.py` 模型注释为准（只读核对）：

- **QuestionResponse**：`id, question_bank_id, question_type, content, answer, analysis, difficulty, status, source_type, quality_score, used_count, correct_count, options[], knowledge_ids[], created_at, updated_at` — 与 `schemas/question.py::QuestionResponse` 一致。
- **任务列表项**：`id, status, total_count, success_count, duplicate_count, failed_count, request_config, error_summary, started_at, completed_at, created_at` — 与 `question_generation.py` 列表路由逐字段核对。
- **任务详情**：上表 + `task_id, created_by, progress, questions[]`；`questions[]` 项含 `id, question_type, content(后端截断100字), difficulty, status, knowledge_ids, option_count`。
- **创建任务请求**：`knowledge_id, question_bank_id, question_type, difficulty, count`；count 1~50、difficulty 1/2/3、题型四值，均为后端显式校验规则。
- **分页**：`PaginatedData { items, page, page_size, total }`。

任务列表的题库/知识点名称不直接返回，前端从 `request_config` 快照中取 `question_bank_id`/`knowledge_id`，再经题库/知识点真实接口映射为名称，**不伪造名称**。

---

## 5. 支持的题型与难度枚举

| 枚举 | 值 | 中文 | 依据 |
|---|---|---|---|
| 题型 | `SINGLE_CHOICE` | 单选题 | `question_generation.py:54` 白名单 |
| 题型 | `MULTIPLE_CHOICE` | 多选题 | 同上 |
| 题型 | `TRUE_FALSE` | 判断题 | 同上 |
| 题型 | `SHORT_ANSWER` | 简答题 | 同上 |
| 难度 | `1` / `2` / `3` | 简单 / 中等 / 困难 | `question_generation.py:56` + `schemas/question.py` 注释 |
| 题目状态 | `pending_review` | 待审核 | `models/question.py:64-65` |
| 题目状态 | `published` | 已发布 | 审核接口写入 |
| 题目状态 | `rejected` | 已驳回 | 审核接口写入 |
| 题目状态 | `disabled` / `DISABLED` | 已下架 | 模型注释为小写；`question_repository.py:97` 实际写入大写（见第 10 节） |
| 任务状态 | `pending` | 等待执行 | `models/question_generation_task.py:38-39` |
| 任务状态 | `running` | 执行中 | 同上 |
| 任务状态 | `success` | 全部成功 | 同上 |
| 任务状态 | `partial_success` | 部分成功 | 同上 |
| 任务状态 | `failed` | 生成失败 | 同上 |
| 任务状态 | `cancelled` | 已取消 | 同上 |

**题型兼容**：单选/多选显示选项与正确答案标识；判断题显示「判断题以答案形式存储，无选项」并将 `TRUE/FALSE` 映射为 正确/错误；简答题展示参考答案。未知题型显示后端原始值，不做错误映射。

---

## 6. 页面业务流程

### AI 生成题目
选题库（真实题库下拉，含题目数）→ 知识点（远程搜索，服务端分页）→ 题型/难度/数量 → 参数摘要确认弹窗 → `POST /question-generation/tasks` → 成功跳转任务详情；提交中禁用按钮防重复；**网络超时不自动重发 POST**，提示先去任务列表核实。不显示「同时生成解析」选项（后端未实现）。

### 生成任务
列表服务端分页 + 状态筛选；展示计划/成功/跳过/失败数（均来自服务端字段）。详情页对 `pending/running` 每 3 秒轮询，终态（success/partial_success/failed/cancelled）停止；离开页面清理定时器；`isPolling` 防止请求重叠；刷新后按 URL 中 taskId 重新请求，不重复触发执行。`partial_success` 与 `failed` 分开文案，失败展示 `error_summary`。任务成功不等于题目已发布——页面明确提示需逐道审核。

### 题目审核
待审核列表固定 `status=pending_review`，支持题库/知识点/题型/难度/关键词筛选（关键词 400ms 防抖）。详情左预览右操作：发布（确认弹窗）→ `review action=publish`；驳回（必须填 ≥2 字原因）→ `action=reject`；成功后重新 GET 详情确认状态。编辑用同一 QuestionForm；保存后重新 GET 详情以服务端内容为准。已发布/已驳回题目不显示发布/驳回按钮。

### 题目列表与下架
全部状态可筛选（默认全部，可切换任一状态）；仅 `published` 显示「下架」；下架确认文案为「下架后，该题目将不再作为正常可组卷题目使用。系统保留历史记录，是否继续？」，按钮文案为**下架题目**（非删除）；已下架不提供「恢复上架」（后端无恢复接口）。

### 历史答题保护
`QuestionResponse` 无 `has_answer_records` 字段，前端不猜测是否有答题记录，正常展示编辑入口；提交后若后端拒绝核心字段修改，原样展示后端业务提示并**保留用户编辑内容**（不拆分请求绕过保护）。实测后端返回：
`code=40001, message="题目已有 1 条答题记录，不能修改核心内容: content。如需修改核心内容，请下架旧题并创建新题。"`

---

## 7. 本地启动与测试命令

```bash
# 后端（需 MySQL 与 .env）
cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run type-check # vue-tsc --build
npm run build      # 生产构建
```

---

## 8. 构建结果

| 命令 | 结果 |
|---|---|
| `npm run type-check` | ✅ 通过（0 error） |
| `npm run build` | ✅ `built in 3.66s` |

---

## 9. 真实后端联调测试场景与结果

### 9.1 接口层（curl + 真实后端）

| 场景 | 结果 |
|---|---|
| 登录取 Bearer Token | ✅ token 有效 |
| 题库列表返回 `id/code/name/description/status/question_count/created_at/updated_at` | ✅ 与前端类型一致 |
| 知识点列表（31 条）字段一致 | ✅ |
| 创建任务：`knowledge_id` 不存在 → `code=40401` 明确报错 | ✅ |
| 创建任务：`count=99` → `code=40001 "count 范围 1~50"` | ✅ |
| 创建任务：非法题型 → `code=40001 "无效的题型"` | ✅ |
| 创建任务成功 → `{task_id, status:"pending", message}` | ✅ |
| 任务状态流转 `pending → running → failed`，`error_summary` 返回真实错误 | ✅ |
| 任务详情字段与前端 `GenerationTaskDetail` 完全一致 | ✅ |
| 题目筛选 `question_bank_id/question_type/difficulty/keyword` 均可用 | ✅ |
| 创建题目返回 `question_bank_id` 等完整字段 | ✅ |
| 审核发布 → `status="published"` | ✅ |
| 对已发布题目驳回 → `code=40001 "已发布题目不能驳回，请使用下架"` | ✅ |
| 下架 → `status` 变为 `DISABLED` | ✅（大小写不一致，见第 10 节） |
| `status=disabled` 与 `status=DISABLED` 筛选结果一致（后端不区分大小写） | ✅ |
| 答题记录生成后，修改题干 → 后端拒绝并给出可读提示 | ✅ |
| 有答题记录时修改解析+难度 → 成功且持久化 | ✅ |

### 9.2 浏览器实测（Chrome headless + CDP 截图，0 控制台错误）

截图文件位于 `frontend/_smoke/*.png`：

| 页面 | 验证点 | 结果 |
|---|---|---|
| `login.png` | 登录页渲染 | ✅ |
| `generate.png` | 表单、必填标记、题型/难度/数量控件、提示文案 | ✅ |
| `tasks.png` | 真实任务行：题库「Java 基础」、知识点名称、单选题、中等、生成失败标签 | ✅ |
| `task-detail.png` | 状态标签、进度条、计划/成功/跳过/失败、任务参数、错误摘要 | ✅ |
| `review.png` | 无待审核时空状态文案 | ✅ |
| `review-list.png` | 待审核题目行、待审核标签、审核按钮 | ✅ |
| `review-detail-3.png` | 判断题无选项说明、TRUE/FALSE→正确/错误、解析、归属、审核操作 | ✅ |
| `questions.png` | 两道真实题目、已发布/已下架标签、解析有无、更新时间 | ✅ |
| `question-detail.png` | 单选题选项+正确答案标识、答案、解析、归属 | ✅ |

侧边栏「题库管理」菜单组渲染正常，四个子项齐全。

### 9.3 后端修复后复测（2026-10-16，真实后端）

后端修复 `knowledge_base_id` 误传与状态大小写后，重新跑完整闭环：

| 场景 | 结果 |
|---|---|
| 创建生成任务（count=2, 单选题, 中等） | ✅ `task_id=2, status=pending` |
| 后台执行 | ✅ `pending → running → success`，`progress=100` |
| 生成结果 | ✅ `success_count=2, failed=0`，2 道 `pending_review` 题目 |
| 题目内容质量 | ✅ AI 围绕「自定义View机型适配」知识点生成，选项合理 |
| 单选题选项与正确答案 | ✅ 4 选项，`is_correct` 标记正确 |
| 审核发布 | ✅ `status=published` |
| 审核驳回 | ✅ `status=rejected` |
| 下架 | ✅ `status='disabled'`（小写，大小写修复确认） |
| 浏览器实测 | ✅ 任务详情显示「全部成功 / 100% / 计划2 成功2」；题目列表 5 道题、4 种状态标签全部正确 |
| 控制台错误 | ✅ 0 |

![task-detail-success](../_smoke/task-detail-success.png)

---

## 10. 未完成事项、接口缺口与阻塞项

### 10.1 后端缺陷（已由后端修复，2026-10-16 复测通过）

1. **AI 生成链路崩溃（已修复）**：`background_runner.py` 曾向 `Question` 模型传入其不支持的
   `knowledge_base_id` 字段导致生成失败。后端已移除该参数（见
   `后端修复报告QUESTION_GENERATION_HOTFIX_REPORT.md`）。**复测：任务 `success`、
   `progress=100`、成功生成 2 道 `pending_review` 题目，选项/答案完整。**
2. **题目状态大小写不一致（已修复）**：`question_repository.py` 下架曾写入大写 `"DISABLED"`。
   后端已统一为小写。**复测：下架返回 `status='disabled'`。**
   前端保留了大小写容错映射，历史数据中的大写 `DISABLED` 仍能正确显示为「已下架」。

### 10.2 接口缺口（导致前端功能留白，未伪造）

| 缺口 | 影响 | 前端处理 |
|---|---|---|
| `QuestionResponse` 无 `has_answer_records` | 无法预知编辑保护 | 通过后端业务错误提示，保留编辑内容 |
| `QuestionResponse` 无 `explanation_source` | 无法展示解析来源 | 不展示 |
| `GET /questions` 无 `generation_task_id` 筛选 | 无法按任务过滤题目 | 任务详情按返回的 `questions[].id` 逐个跳转 |
| 任务列表/详情不返回题库、知识点名称 | 无法直接显示名称 | 用 `request_config` 的 ID 经真实接口映射 |
| 无任务重试/取消接口 | 无重试/取消按钮 | 不提供（不伪造） |
| 无批量审核/下架接口 | 无批量操作 | 不提供 |
| 无题目复制/移动接口 | 无该操作 | 不提供 |
| 无 AI 解析生成接口 | 无「生成解析」按钮 | 仅手动编辑解析 |
| 无题目统计接口 | 无正确率/答题人数等 | 不展示、不填 0 占位 |

### 10.3 测试数据说明

联调期间创建了 3 道真实题目（ID 1/2/3）、1 条答题记录、1 个生成任务（ID 1，执行失败）。
这些是真实后端数据，非 Mock，可用于继续验证编辑保护（题目 1 有答题记录）与下架状态（题目 2）。

---

## 11. Mock 使用声明

**业务运行链路零 Mock。** 前端全部数据来自真实后端 API；未使用本地模拟任务状态、假统计数字或伪造成功状态。
唯一的非业务脚本是 `_smoke/drive.cjs`（Chrome CDP 截图验证工具），不参与应用运行，未引入新运行时依赖。

---

## 12. 其他说明

- 未修改 `backend/` 任何文件、未修改数据库、未重构无关页面。
- 旧「题库 > 题目」模块（`/questions`）保持原样未改动，其状态枚举仍是早期的 `DRAFT/PUBLISHED/DISABLED`，
  与后端当前真实的 `pending_review/published/rejected/disabled` 不一致，建议后续统一（本次范围外）。
