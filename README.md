# KnowledgeForge —— AI 面试题库与知识库管理系统

> An AI-powered interview question bank & knowledge base management system. Backend built with FastAPI + MySQL + LLM Agents + local Embedding/FAISS vector retrieval, featuring multi-layer question deduplication and intelligent question-generation allocation. Frontend built with Vue 3 + TypeScript + Element Plus.
>
> 当前仓库包含**完整的后端实现**（API / Agent / 数据库 / 测试 / 部署）和**管理员 Web 前端**（题库/知识/任务/策略管理）；**做题（练习）体系与 Flutter 移动端 App 尚未开发**，详见[开发状态与路线图](#14-开发状态与路线图)。

---

## 目录

1. [项目简介](#1-项目简介)
2. [核心特性](#2-核心特性)
3. [技术栈](#3-技术栈)
4. [系统架构](#4-系统架构)
5. [核心算法](#5-核心算法)
6. [功能模块](#6-功能模块)（含 [Vue3 管理前端](#68-vue3-管理前端frontend)）
7. [项目结构](#7-项目结构)
8. [快速开始](#8-快速开始)（含 [前端启动](#6-启动前端管理后台)）
9. [API 概览](#9-api-概览)
10. [配置项](#10-配置项)
11. [测试与质量](#11-测试与质量)
12. [部署注意事项](#12-部署注意事项)
13. [文档索引](#13-文档索引)
14. [开发状态与路线图](#14-开发状态与路线图)（含 [前端待开发](#待开发明确未实现)）
15. [License](#15-license)

---

## 1. 项目简介

KnowledgeForge 解决的是**"从知识资料到面试题库"的全链路自动化**：

```
文档导入(pdf/docx/txt/md)
   → 知识抽取（LLM Agent）
   → 知识去重 / 知识关系构建
   → 题库管理与审核
   → 智能出题分配（按知识缺口自动配额）
   → LLM 生成题目 + 多层去重
   → 人工审核发布
```

系统以 **MySQL 为唯一事实源**，Agent 负责抽取/生成/去重等智能环节，向量检索（本地 Embedding + FAISS）支撑语义去重，所有 AI 产出都经过结构化校验与人工审核流程，且全程留有审计记录。

### 当前开发状态（一句话版）

✅ **已实现**：知识导入/抽取/去重/关系、题库管理与审核、AI 出题（智能分配 + 多层去重）、管理后台 API 与测试体系、**Vue3 管理前端**（登录/Dashboard/知识管理/题库管理/AI 出题/题目审核/任务管理/策略管理）；
🚧 **未开发**：面向用户的**做题（练习）体系**——组题/组卷、答题判分、评题与讲解、题目评论互动、练习记录与统计——以及依赖它的 **Flutter 移动端 App**。详见 [§14 开发状态与路线图](#14-开发状态与路线图)。

---

## 2. 核心特性

- **知识导入流水线**：文档解析 → 智能分块 → LLM 结构化抽取 → 合并 → 语义去重 → 知识关系（前置/相关/扩展/对比）自动构建，后台任务异步执行，状态全程可查。
- **题目多层去重**（本项目重点）：
  - 第 1 层：**版本化文本指纹**（精确去重，0 次 LLM 调用）；
  - 第 2 层：**关键词 + 向量语义召回**（FAISS 独立命名空间，Top-K）；
  - 第 3 层：**范围感知阈值**（同知识范围常规去重 / 跨题库严格过滤）；
  - 第 4 层：**LLM 批量复核**（结构化 JSON 裁决，只处理高相似候选，绝不全库比对）；
  - 并发安全（进程级写锁 + 数据库唯一键 + 入库前终验）、审计表、失败降级（uncertain）。
- **智能出题分配**：基于知识库存量 / 使用频率 / 重要程度的**需求评分模型**，最大余数法分配出题配额，支持策略全局默认与题库级覆盖。
- **LLM 生成 + 质量治理**：4 种题型（单选/多选/判断/简答）结构化生成，选项/答案严格校验，生成结果默认 `pending_review` 人工审核后发布。
- **运维友好**：JWT 管理员认证、统一响应体与错误码、Request ID 全链路日志（不记录密码/密钥）、Alembic 迁移、Docker 一键启动、175 项自动化测试。
- **Vue3 管理前端**：完整的管理后台 UI，覆盖知识管理、题库管理、AI 出题（manual/auto）、题目审核、生成任务管理、出题策略配置、知识范围配置；Design System 统一风格，TypeScript 类型安全，真实 API 联调。

---

## 3. 技术栈

### 后端

| 层 | 技术 | 用途 |
| --- | --- | --- |
| Web 框架 | **FastAPI** + Uvicorn | 异步 API、自动 OpenAPI/Swagger 文档 |
| 数据校验 | **Pydantic v2** / pydantic-settings | 请求/响应 Schema、`.env` 配置加载 |
| ORM / 迁移 | **SQLAlchemy 2.x** + **Alembic** | 数据建模与版本化迁移 |
| 数据库 | **MySQL 8.x**（PyMySQL） | 唯一事实源 |
| 认证 | **PyJWT** + **bcrypt** | 管理员登录、密码哈希、JWT 鉴权 |
| LLM 编排 | **LangChain** + **LangGraph** | Agent 流水线（状态机式多步编排） |
| LLM | **MiMo**（OpenAI 兼容接口，`mimo-v2.6-pro`） | 知识抽取、题目生成、去重复核；支持 thinking 模式按需启停并做实例缓存 |
| 文本向量 | **FlagEmbedding**（`BAAI/bge-small-zh-v1.5`，512 维，本地 fp16 推理） | 中文语义向量 |
| 向量检索 | **FAISS**（`faiss-cpu`，IndexFlatIP + numpy fallback） | 语义候选召回（内存态、可重建） |
| 文档解析 | **pdfplumber** / **python-docx** | PDF / DOCX 文本抽取 |
| 测试 | **pytest** + httpx（TestClient） | 单元/集成/真实模型冒烟测试 |
| 部署 | **Docker** / docker-compose | FastAPI + MySQL 一键编排 |

> 无 Redis / Celery / 消息队列 / 图数据库 / 向量数据库——后台任务使用线程 + 信号量实现，刻意保持 V1.0 轻量，避免过度设计。

### 前端

| 层 | 技术 | 用途 |
| --- | --- | --- |
| 框架 | **Vue 3**（Composition API + `<script setup>`） | 单页应用 |
| 构建 | **Vite** | 开发服务器、构建、代码分割 |
| 语言 | **TypeScript** | 类型安全 |
| UI 组件库 | **Element Plus**（zh-CN locale） | 表格、表单、弹窗、通知等 |
| 状态管理 | **Pinia** | 登录态、认证管理 |
| 路由 | **Vue Router 4** | 路由守卫、懒加载 |
| HTTP | **Axios** | 统一请求/响应拦截器 |
| 图标 | **Lucide Vue Next** | 一致的图标体系 |
| 样式 | **CSS 变量 + Design System** | 蓝色主色调（#1E40AF）、Fira Sans、瑞士极简风 |
| 类型检查 | **vue-tsc** | 构建前 TypeScript 类型校验 |

> 前端无路由级状态管理、无 UI 主题框架、无重型富文本编辑器——以轻量、一致、易维护为原则。

---

## 4. 系统架构

```
  ┌────────────────────────────────────┐
  │     Vue3 管理后台 (frontend/)       │
  │  Element Plus · Pinia · Axios      │
  │  知识管理 · 题库管理 · AI 出题       │
  └──────────────┬─────────────────────┘
                 │ HTTP (JWT Bearer)
                 ▼
                    ┌─────────────────────────────────────────────┐
                    │                FastAPI (app/)                │
   HTTP ──────────► │  Middleware: RequestID / CORS / 全局异常处理   │
   (JWT 鉴权)       │  api/v1: auth knowledge question generation… │
                    └───────────────┬─────────────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────────────┐
                    │          Service 业务层 (app/services)        │
                    │  导入 / 去重 / 出题分配 / 后台任务执行器        │
                    └───────┬───────────────────────┬─────────────┘
                            │                       │
              ┌─────────────▼─────────┐   ┌─────────▼─────────────────┐
              │ Repository (数据访问)  │   │  Agent 层 (agent/)         │
              │        MySQL          │   │  LangGraph 流水线:          │
              │  唯一事实源 + 唯一键兜底 │   │  extract·dedup·relation    │
              └───────────────────────┘   │  decision·generate·dedup   │
                                          └─────────┬─────────────────┘
                                                    │
                                    ┌───────────────▼───────────────┐
                                    │  Embedding (bge-small-zh)      │
                                    │  + FAISS 向量索引（独立命名空间） │
                                    │  知识库 / 题库 两套隔离索引      │
                                    └───────────────────────────────┘
```

- **分层约定**：`API → Service → Repository → MySQL`；Agent 层只负责智能计算，落库一律回到 Service/Repository，保证 MySQL 是唯一事实源。
- **扩展性**：Agent 以"Agent → Tool → Service → Repository"的顺序扩展，新增智能能力只需新增 Agent 模块并在 Service 编排。

---

## 5. 核心算法

### 5.1 文本指纹（精确去重，`hash_version = 2`）

对题型 + 题干 + 选项 + 答案做**结构化签名**后取 `SHA-256[:32]`：

- Unicode NFKC 归一 + 中英文标点统一（全角→半角）；
- **字符串 / 行内代码字面量原样保留**：`System.out.println("a b")` 与 `("ab")` 指纹不同；
- 中文段折叠空白并删除紧邻汉字的空格，**英文词边界保留**：`JDK 8` ≠ `JDK8`、`HashMap` ≠ `hashmap`；
- 技术标识符大小写、运算符（`==` vs `===`）、`C` vs `C++` 全部参与指纹；
- 选择题选项**剥离 `A.`/`B.` 标签**后按 `(内容, 是否正确)` 配对排序——选项顺序变化不影响指纹，答案映射变化则指纹不同；
- 指纹算法带版本字段（`hash_version`），新旧指纹不混比；`dedup_key` 唯一索引仅对 `pending_review`/`published` 题目登记，数据库层兜底精确重复。

> 设计原则：**宁可漏拦（交给语义层复核），不可误杀**（不为提升命中率破坏代码/字符串语义）。

### 5.2 语义相似度（向量召回 + 融合评分）

```
融合分 = 0.6 × 向量余弦(bge-small-zh) + 0.4 × 二元组(bigram)文本余弦
```

- 候选召回：关键词 LIKE 检索 ∪ FAISS 向量 Top-K（默认 15），批量载入 MySQL 校验状态；
- 向量文本 = `题型 | 题干 | 选项内容`（不含知识点名与解析，避免污染）；
- 任一通道不可用时退化为单通道评分并记录告警，**语义层不可用不会被静默当成"无重复"**（降级为 uncertain）。

### 5.3 范围感知的去重决策（四层）

| 场景 | 判定规则 | LLM 调用 |
| --- | --- | --- |
| 指纹精确命中（任意题库/知识范围） | 直接判重 | 0 |
| 同范围（同题库 ∩ 知识点相交） | 融合分 ≥ **0.65** 进入 LLM 复核 | 按需 |
| 跨范围（不同题库或知识点不相交） | 融合分 ≥ **0.75** 才进入 LLM 复核，更严格 | 仅极高相似 |
| 批次内新题相互比对 | 内存两两评分，同上规则 | 按需 |

- LLM 复核：多对候选**批量**提交，结构化输出 `{pair_id, verdict: duplicate|distinct|uncertain, reason}`；提示词明确"同一主题 ≠ 重复"（如"HashMap 底层结构" vs "HashMap 扩容机制"为 distinct）；
- 超时 / 非法 JSON / 缺字段 → 一律判 `uncertain`（保留题目 + 标记人工复核），**绝不静默放行**；
- 并发保护：进程级写锁内完成"校验→复核→入库→写向量索引"，LLM 调用期间不持有 MySQL 事务；入库前做精确指纹终验；跨进程由唯一键兜底。
- 审计：每次判定写入 `question_dedup_record`（双方题目/范围/各层分数/LLM 结论/原因/模型版本）。

### 5.4 知识去重（导入侧）

`normalize → 精确比对 → Embedding → 向量检索 → 规则决策 → LLM 仲裁`，双阈值 **0.60 / 0.88**（低于判不同、高于判重复、中间走 LLM，AMBIGUOUS 状态可人工裁决）。

### 5.5 智能出题分配（需求评分 + 最大余数法）

```
demand_score = stock_score × w1/100 + usage_score × w2/100 + importance_score × w3/100
（默认权重 w1/w2/w3 = 50/30/20，stock 按 target_stock=20 缺口归一，
 usage 取 30 天窗口，importance ∈ {core, important, normal, supplementary}）
```

- `demand_score ≥ min_demand_score(0.15)` 的知识点进入候选；
- 出题配额按**最大余数法**分配（小数部分从大到小补齐），单知识点受 `max_per_knowledge_per_task(10)` 上限约束；
- 策略支持全局默认 + 题库级覆盖（版本号递增，可审计）。

---

## 6. 功能模块

### 6.1 认证与权限
- 管理员登录 `POST /api/v1/auth/login`（bcrypt 密码哈希 + JWT）、`GET /auth/me`；
- 全部管理接口统一 `get_current_admin()` 依赖鉴权；提供 `scripts/create_admin.py` 初始化管理员（无明文密码落库/入库）。

### 6.2 知识库管理
- 知识点 CRUD（分页 / 关键词 / 难度 / 状态筛选，删除优先"停用"软删除）；
- 知识库（KnowledgeBase）分类、知识点↔知识库映射（M2M，可按题库圈定出题范围）；
- 知识点**重要程度**（core/important/normal/supplementary）与来源（default/agent/**manual**——人工标注永不被重新导入覆盖）；
- 知识关系 API（前置 prerequisite / 相关 related / 扩展 extension / 对比 contrast），目标存在性校验、禁止自环与重复。

### 6.3 文档导入与知识流水线
- 上传 pdf/docx/txt/md，服务端生成 UUID 文件名，按 `uploads/YYYY/MM/DD/` 落盘（数据库不存文件二进制）；
- 导入任务状态机：`PENDING → RUNNING → SUCCESS / PARTIAL_SUCCESS / FAILED / CANCELLED`，后台线程执行（导入并发=1），API 即时返回任务 ID；
- 流水线：解析 → 分块（质量治理：控制块数与粒度）→ LLM 结构化抽取 → 合并 → 知识去重 → 关系构建（可失败重试 `retry_relations`）。

### 6.4 题库与题目管理
- 4 种题型：`SINGLE_CHOICE / MULTIPLE_CHOICE / TRUE_FALSE / SHORT_ANSWER`；
- 题目 + 选项 + 题目-知识关联**同一事务**写入（失败整体回滚）；
- 审核流：`pending_review → published / rejected / disabled`，状态联动去重资格与向量索引（rejected/disabled 不阻断新题）；
- 题目质量统计（生成质量治理）；
- 答题提交/统计与题目评论**已有基础接口**（`/answers`、`/comments` 各若干端点），但完整的做题体验（组题、判分评题、评论生态）属待开发项，见 [§14](#14-开发状态与路线图)。

### 6.5 智能出题
- 手动模式（指定知识点/数量/难度/题型）与自动模式（按需求评分分配）；
- 出题任务统计口径完整：`requested / generated / passed / exact_duplicate / semantic_duplicate / uncertain / failed / unfulfilled`（受重试上限约束的缺口**如实上报**）；
- 生成去重：新增题与**历史题 + 待审核题 + 同批新题**全部参与比对；重复不计入产出，触发有限补生成（重试上限与生成倍率双重约束）。

### 6.6 题目去重专项能力（API 可观测）
- `GET /api/v1/question-dedup/status`：向量索引状态机（initializing/ready/degraded）+ 统计；
- `GET /question-dedup/records`：审计查询（按任务/题目/裁决/待人工复核过滤）；
- `POST /question-dedup/index/rebuild`：**服务进程内**幂等重建索引（含一致性检查）。

### 6.7 Dashboard
- MySQL 聚合统计（知识/题目/任务/审核量等总览），`GET /api/v1/dashboard/overview`。

### 6.8 Vue3 管理前端（`frontend/`）

前端是独立的 Vue3 单页应用，通过 Axios 调用后端 `/api/v1` 接口，使用 JWT Bearer Token 认证。

#### 页面与路由

| 路由 | 页面 | 功能 |
| --- | --- | --- |
| `/login` | 登录页 | 管理员登录，JWT Token 存储于 localStorage |
| `/dashboard` | Dashboard | 知识/题目/导入任务统计概览（7 项指标卡片） |
| `/knowledge-bases` | 知识库管理 | 知识库 CRUD、启用/停用、知识点数量统计，卡片式布局 |
| `/knowledge` | 知识点列表 | 分页/筛选（知识库/关键词/难度/状态）、**重要程度编辑**（core/important/normal/supplementary）、来源展示（系统默认/AI 标注/管理员调整） |
| `/knowledge/create` | 新增知识点 | 所属知识库选择、难度、来源、关键词 Tag 输入 |
| `/knowledge/:id` | 知识点详情 | 基本信息 + 详细内容 + 知识关系（前置/相关/扩展/对比） |
| `/knowledge/:id/edit` | 编辑知识点 | 同表单复用 |
| `/knowledge-relations` | 知识关系列表 | 按知识点查看/管理关联关系 |
| `/question-management/generate` | AI 生成题目 | **manual/auto 双模式**：指定知识点 or 系统智能分配；auto 支持分配预览（需求分数、配额明细、策略快照）、部分分配确认 |
| `/question-management/tasks` | 生成任务列表 | 分配模式（指定知识点/系统智能分配）、分配数量、状态筛选、分页 |
| `/question-management/tasks/:taskId` | 生成任务详情 | 任务状态/进度、**分配计划快照**（知识点/知识库/重要程度/计划数）、关联题目列表、错误摘要 |
| `/question-management/review` | 题目审核 | 待审核题目列表、筛选（题库/知识点/题型/难度/关键词）、审核详情 |
| `/question-management/questions` | 题目列表 | 全部状态题目管理、多条件筛选、下架操作 |
| `/question-management/questions/:questionId` | 题目详情/审核 | 题目预览（选项/答案/解析）、编辑、发布/驳回、下架、**历史答题保护提示** |
| `/question-management/policies` | 出题策略管理 | 全局默认策略 + 题库级覆盖策略、权重实时校验（合计=100）、策略说明面板、恢复全局策略 |
| `/question-management/knowledge-scope` | 题库知识范围 | 配置题库关联知识库（多选、搜索、分页）、全量替换保存 |
| `/import-tasks` | 导入任务列表 | 文件上传（PDF/DOCX/TXT/MD）、目标知识库选择、进度/状态筛选 |
| `/import-tasks/:taskId` | 导入任务详情 | 任务状态/阶段/进度、文件信息、知识库归属、轮询更新 |
| `/admin` | 管理员信息 | 当前登录管理员信息、退出登录 |

#### 核心交互设计

- **重要程度编辑**：下拉菜单 → 对话框（四级选项含说明）→ PATCH 更新 → 来源自动标记为"管理员调整"（Agent 不会覆盖）
- **智能出题 manual 模式**：选择题库/知识点/题型/难度/数量 → 确认 → 创建任务
- **智能出题 auto 模式**：选择题库/题型/难度/总量 → **预览分配**（展示知识点需求分数/配额明细）→ 部分分配确认（明确显示目标/可分配/无法分配）→ 创建任务（`allow_partial`）
- **分配计划快照**：任务详情展示分配的每个知识点（名称/知识库/重要程度/计划数），含策略版本号
- **策略管理**：权重输入实时校验合计=100、越界值阻止保存、策略说明面板（只读公式）、题库级策略"恢复使用全局策略"
- **题目审核**：发布（确认弹窗）/驳回（必须填原因，≥2 字）；已发布题目不显示发布/驳回按钮；历史答题记录保护（后端拒绝核心字段修改时前端展示提示并保留编辑内容）

#### Design System

- 主色：`#1E40AF`（蓝），状态色：success/error/warning/info/muted
- 字体：Fira Sans，瑞士极简风，卡片式布局
- 状态标签：`status-badge` 系统（文字 + 颜色，不单靠颜色传达信息）
- 难度标签：`difficulty-badge`（easy/medium/hard）
- 空状态/加载骨架屏/错误状态统一处理

### 6.9 工程规范
- 统一响应体 `{code, message, data}` + 分页信封 + 错误码体系（如 40401）；
- `BusinessException` 异常层级 + 全局处理器（未知异常返回"系统内部错误"并记录完整堆栈）；
- Request ID 中间件：记录 `request_id / method / path / status / duration`，**绝不记录密码、JWT 密钥、数据库口令、API Key**。

---

## 7. 项目结构

```
knowledgeforge/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI 入口（lifespan: 向量索引启动构建 + 单 worker 检查）
│   │   ├── api/v1/               # 路由层（auth/knowledge/question/generation/question-dedup/…）
│   │   ├── core/                 # 配置、数据库、安全、异常、日志
│   │   ├── middleware/           # RequestID、全局异常处理
│   │   ├── models/               # SQLAlchemy 模型（15 张表）
│   │   ├── schemas/              # Pydantic Schema
│   │   ├── repositories/         # 数据访问层
│   │   ├── services/             # 业务层（导入/去重/出题/向量同步/后台执行器…）
│   │   └── dependencies/         # FastAPI 依赖（get_current_admin 等）
│   ├── agent/                    # LangGraph Agent 层
│   │   ├── common/               # LLM(ThinkingMode 缓存)/Embedding/FAISS 向量库/配置
│   │   ├── knowledge_extract/    # 知识抽取流水线
│   │   ├── knowledge_deduplicate/# 知识去重（双阈值 + LLM 仲裁）
│   │   ├── knowledge_relation/   # 知识关系构建
│   │   ├── question_decision/    # 出题决策（需求评分/配额）
│   │   ├── question_generate/    # 题目生成（结构化输出 + 校验）
│   │   └── question_dedup/       # 题目去重复核（批量 LLM 裁决 Schema/提示词）
│   ├── migrations/               # Alembic 迁移
│   ├── scripts/                  # create_admin / rehash_questions /
│   │                             # build_question_embeddings /
│   │                             # calibrate_question_dedup_thresholds /
│   │                             # llm_review_smoke / smoke_test.sh(.ps1)
│   ├── tests/                    # 175 项自动化测试
│   ├── docs/                     # 部署文档等
│   ├── Dockerfile / docker-compose.yml
│   └── requirements.txt
├── frontend/                     # Vue3 管理后台（管理员 Web）
│   ├── src/
│   │   ├── api/                  # API 调用层（auth/knowledge/question/questionBank/questionGeneration/questionDemand/knowledgeBase/importTask/dashboard）
│   │   ├── views/                # 页面视图
│   │   │   ├── login/            # 登录页
│   │   │   ├── dashboard/        # Dashboard 统计概览
│   │   │   ├── knowledge/        # 知识点管理/知识库管理/知识关系
│   │   │   ├── question-management/ # 题库管理（AI出题/任务/审核/列表/策略/知识范围）
│   │   │   ├── question/         # 题目管理（旧版 CRUD）
│   │   │   ├── import-task/      # 导入任务管理
│   │   │   └── admin/            # 管理员信息
│   │   ├── components/           # 可复用组件
│   │   │   ├── knowledge/        # 知识关系列表组件
│   │   │   └── question-management/ # 题目预览/编辑表单/状态标签
│   │   ├── composables/          # 组合式函数（useQuestionLookups）
│   │   ├── constants/            # 枚举映射（题型/难度/状态/重要程度/策略）
│   │   ├── layouts/              # 布局组件（AdminLayout 侧边栏+顶栏）
│   │   ├── router/               # 路由配置（含路由守卫）
│   │   ├── stores/               # Pinia 状态管理（auth）
│   │   ├── types/                # TypeScript 类型定义
│   │   ├── utils/                # 工具函数（axios 封装/storage）
│   │   └── assets/               # 全局样式（CSS 变量 + Design System）
│   ├── docs/                     # 前端交付报告、API 契约差异报告
│   ├── .env.development          # 开发环境配置（API Base URL）
│   ├── index.html                # 入口 HTML
│   ├── vite.config.ts            # Vite 配置
│   └── package.json
├── docs/                         # 各阶段设计/执行/验收文档（中文）
└── README.md                     # 本文档
```

**主要数据表**：`admin_user`、`knowledge`、`knowledge_base`、`knowledge_relation`、`question_bank_knowledge_base`、`import_task`、`question`、`question_option`、`question_knowledge`、`question_bank`、`question_generation_task`、`question_generation_policy`、`question_answer_record`、`question_comment`、`question_dedup_record`（去重审计）。

---

## 8. 快速开始

### 环境要求

- Python **3.11+**（开发验证环境 3.14，见 `.python-version`）
- MySQL **8.0+**
- 可选：Docker / Docker Compose

### 1) 创建虚拟环境并安装依赖

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) 配置环境变量

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux / macOS
```

编辑 `.env`（详见 [配置项](#10-配置项)），至少配置 MySQL 连接与 LLM API Key。

### 3) 初始化数据库

```bash
# 创建数据库（utf8mb4）
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS interview_agent DEFAULT CHARACTER SET utf8mb4;"

# 执行迁移
alembic upgrade head

# 创建管理员账号
python scripts/create_admin.py
```

### 4) 启动服务（单 worker，见部署注意事项）

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

启动日志会输出题目向量索引初始化结果（`ready` / `degraded`）。Swagger 文档：**http://localhost:8000/docs**

### 5) 运行测试

```bash
python -m pytest tests/ -q
```

### 6) 启动前端（管理后台）

```bash
cd frontend
npm install
npm run dev        # 开发模式，http://localhost:5173
npm run type-check # TypeScript 类型检查
npm run build      # 生产构建
```

> 前端开发服务器默认连接 `http://127.0.0.1:8000`（`.env.development` 可修改）。生产构建产物在 `frontend/dist/`。

### Docker 一键启动

```bash
cd backend
docker compose up -d   # FastAPI + MySQL 编排
```

---

## 9. API 概览

全部接口以 `/api/v1` 为前缀，需 JWT 鉴权（登录接口除外）。完整交互式文档见 Swagger（`/docs`）。

| 分组 | 前缀 | 说明 | 前端页面 |
| --- | --- | --- | --- |
| 认证 | `/auth` | 登录、当前管理员信息 | 登录页 |
| 知识库 | `/knowledge-bases` | 知识库 CRUD | 知识库管理 |
| 知识点 | `/knowledge` | 知识点 CRUD、重要程度 | 知识点列表/详情 |
| 知识关系 | `/knowledge/{id}/relations` | 前置/相关/扩展/对比关系 | 知识点详情 |
| 题库 | `/question-banks` | 题库管理、知识库映射 | 题库知识范围 |
| 题目 | `/questions` | 题目 CRUD、审核 | 题目列表/审核 |
| 出题任务 | `/question-generation/tasks` | 创建/列表/详情（manual/auto） | AI 出题/任务管理 |
| 出题策略 | `/question-generation/policies` | 全局/题库级策略 CRUD | 出题策略 |
| 分配预览 | `/question-generation/allocations/preview` | 智能分配预览 | AI 出题 |
| 题目审核 | `/question-generation/questions/{id}/review` | 发布/驳回 | 题目审核 |
| 导入任务 | `/import-tasks` | 文件上传/任务查询/模拟 | 导入任务 |
| 统计 | `/dashboard` | 总览聚合 | Dashboard |

统一响应：

```json
{ "code": 0, "message": "success", "data": { "...": "..." } }
```

---

## 10. 配置项

完整清单见 `backend/.env.example`，核心配置：

| 变量 | 说明 | 默认/示例 |
| --- | --- | --- |
| `APP_ENV` / `DEBUG` | 运行环境 / 调试开关 | `development` / `false` |
| `MYSQL_HOST/PORT/DATABASE/USERNAME/PASSWORD` | MySQL 连接 | `127.0.0.1:3306/interview_agent` |
| `JWT_SECRET_KEY` / `JWT_*` | JWT 签发与过期 | — |
| `UPLOAD_DIR` / `MAX_UPLOAD_SIZE` | 上传目录 / 大小限制 | `uploads` |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | MiMo（OpenAI 兼容）接入 | `mimo-v2.6-pro` |
| `EMBEDDING_MODEL` / `EMBEDDING_VERSION` | 本地 Embedding 模型路径与版本 | `BAAI/bge-small-zh-v1.5` |
| `DEDUP_LOW_THRESHOLD` / `DEDUP_HIGH_THRESHOLD` | 知识去重双阈值 | `0.60` / `0.88` |
| `QUESTION_DEDUP_ENABLED` | 题目去重开关 | `true` |
| `QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD` | 同范围候选阈值 | `0.65` |
| `QUESTION_DEDUP_CROSS_SCOPE_HIGH_THRESHOLD` | 跨范围高相似阈值（更严格） | `0.75` |
| `QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD` | 入库前最终阻断阈值 | `0.85` |
| `QUESTION_DEDUP_VECTOR_TOP_K` / `KEYWORD_TOP_K` | 候选召回上限 | `15` / `15` |
| `QUESTION_DEDUP_LLM_MAX_CANDIDATES` / `LLM_BATCH_SIZE` | 每题复核上限 / 每次调用配对数 | `5` / `5` |
| `QUESTION_DEDUP_MAX_REGENERATION_ATTEMPTS` / `MAX_GENERATION_MULTIPLIER` | 补生成重试上限 / 生成倍率 | `2` / `1.5` |

> 阈值经 `scripts/calibrate_question_dedup_thresholds.py` 在标注样本上校准（误判/漏判双指标输出），调参请先跑校准脚本。

---

## 11. 测试与质量

```bash
python -m pytest tests/ -q        # 175 passed（约 3 分钟）
```

测试分层：

- **既有回归**（87 项）：认证、知识、题目、导入、映射、出题分配、Dashboard；
- **题目去重专项**（45 项）：四层判定、范围矩阵、LLM 调用次数断言（精确命中 0 次调用 / 跨范围低中相似 0 次 / 高相似 ≥1 次）、审计落库；
- **生成任务集成**（5 项）：补生成上限、统计口径、并发批次；
- **标准化 v2**（18 项）：代码块/字符串空白保真、大小写、运算符、选项顺序等指纹行为矩阵；
- **并发与生命周期专项**（16 项）：10 线程同题只存 1、语义改写并发不双存、门槛一致性、索引写失败降级、真实 Embedding 竞争；
- **真实模型冒烟**（4 项）：真实 FlagEmbedding + FAISS 语义召回（非 Mock）。

另外提供**真实 LLM 冒烟**脚本 `scripts/llm_review_smoke.py`（7 用例：同范围改写判重、不同角度不误杀、跨范围 0 调用、批量复核、非法 JSON/超时降级 uncertain、端到端生成）与**阈值校准**脚本 `scripts/calibrate_question_dedup_thresholds.py`。

---

## 12. 部署注意事项

1. **必须单 worker / 单进程启动**：题目向量索引为进程内存态（FAISS），写锁为进程级。多 worker 配置会在启动时直接报错拒绝（`RuntimeError`），跨进程仅精确指纹（数据库唯一键）可靠。
2. **启动自动构建索引**：`lifespan` 阶段幂等重建（实测 24 题约 2.8s，含 Embedding 模型首次加载约 40~60s）；构建完成前不对外提供服务，失败进入 `degraded` 并拒绝新出题任务（**绝不静默跳过语义去重**）。
3. **索引重建必须在服务进程内**：`POST /api/v1/question-dedup/index/rebuild`（脚本 `build_question_embeddings.py` 构建的是脚本进程的索引，用于一致性检查/离线修复，不会恢复服务进程索引）。
4. **状态同步**：审核驳回/下架会同步清除 `dedup_key` 并移除向量索引条目，不再阻断后续同内容新题。
5. **环境变量**：LLM 需 `LLM_API_KEY`（MiMo，OpenAI 兼容）；Embedding 模型本地加载（`EMBEDDING_MODEL` 指向模型快照路径）。任何密钥都不得提交入库，日志已做脱敏。
6. 详见 [docs/QUESTION_DEDUP_DEPLOYMENT.md](backend/docs/QUESTION_DEDUP_DEPLOYMENT.md)（部署十问）。

---

## 13. 文档索引

设计、执行与验收文档（中文）位于 [`docs/`](docs/)，按阶段组织：

| 主题 | 文档 |
| --- | --- |
| 总体/数据库/Agent 设计 | `docs/backend-design.md`、`docs/database-design.md`、`docs/agent设计提示方案.md` |
| 知识导入与去重 Agent | `docs/1~4 阶段`、`docs/后端阶段完成文档/` |
| 题库与题目生成 | `docs/8、DSH_题库基础能力与QuestionDecisionAgent执行文档.md` 等 |
| 智能出题分配 | `docs/11、前后端阶段性题目生成联调/` |
| **题目多层去重** | `docs/12、题目生成去重/去重总结QUESTION_DEDUPLICATION_IMPLEMENTATION_REPORT.md` |
| **去重专项加固与真实环境验收** | `docs/12、题目生成去重/QUESTION_DEDUPLICATION_HARDENING_REPORT.md` |
| **前端题库管理模块** | `frontend/docs/ADMIN_WEB_QUESTION_MANAGEMENT_REPORT.md` |
| **前端智能出题策略** | `frontend/docs/ADMIN_WEB_SMART_QUESTION_ALLOCATION_REPORT.md` |
| **前端 API 契约差异** | `frontend/docs/FRONTEND_API_CONTRACT_DIFF.md` |
| 部署说明 | [backend/docs/QUESTION_DEDUP_DEPLOYMENT.md](backend/docs/QUESTION_DEDUP_DEPLOYMENT.md) |

---

## 14. 开发状态与路线图

### 已实现（后端，V1.x）

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 知识导入流水线 | ✅ | 解析 → 分块 → LLM 抽取 → 合并 → 去重 → 关系构建 |
| 知识库管理 | ✅ | 知识点/知识库/映射/重要度/知识关系 |
| 题库与审核 | ✅ | 4 题型、选项、事务写入、审核状态机 |
| AI 出题 | ✅ | 智能出题分配（需求评分 + 最大余数法）、手动/自动任务 |
| 题目多层去重 | ✅ | 指纹 v2 + 语义召回 + 范围阈值 + LLM 批量复核 + 并发保护 + 审计 |
| 管理端基础设施 | ✅ | JWT、统一响应/错误码、Request ID、Dashboard、Docker |

### 已实现（前端 Vue3 管理后台）

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 登录 / 认证 | ✅ | JWT 登录、Token 持久化、路由守卫、401 自动跳转 |
| Dashboard 统计概览 | ✅ | 知识/题目/导入任务 7 项指标卡片 |
| 知识库管理 | ✅ | 知识库 CRUD、启用/停用、知识点数量、卡片式布局 |
| 知识点管理 | ✅ | 列表/详情/编辑、**重要程度**编辑（core/important/normal/supplementary）、来源标签、知识库筛选、关键词 Tag |
| 知识关系管理 | ✅ | 前置/相关/扩展/对比关系查看与添加删除 |
| AI 生成题目 | ✅ | **manual/auto 双模式**、分配预览（需求分数/配额明细）、部分分配确认、`allow_partial` |
| 生成任务管理 | ✅ | 列表（分配模式/数量/状态）、详情（**分配计划快照**/进度/关联题目）、轮询 |
| 题目审核 | ✅ | 待审核列表、审核详情（预览/编辑/发布/驳回）、历史答题保护提示 |
| 题目列表管理 | ✅ | 全部状态筛选、查看/编辑/下架（软删除确认） |
| 出题策略管理 | ✅ | 全局/题库级策略、权重实时校验、策略说明面板、恢复全局策略 |
| 题库知识范围 | ✅ | 题库-知识库映射配置、多选/搜索/分页、全量替换确认 |
| 导入任务管理 | ✅ | 文件上传（PDF/DOCX/TXT/MD）、目标知识库选择、任务状态/进度/阶段 |
| Design System | ✅ | 蓝色主色调、状态/难度标签、空状态/加载/错误态、响应式布局 |

### 待开发（明确未实现）

> 下列功能**均未开发**，部分仅有雏形接口。做题相关后端是 Flutter App 的前置依赖。

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| **做题（练习）功能** | 🚧 未开发 | 用户侧答题全流程：答题会话、判分（选择/判断客观题自动判、简答主观题待评）、答题回看、错题本、练习模式（顺序/随机/按知识点/按难度）。现有 `/answers` 仅有基础的提交与统计接口 |
| **组题 / 组卷** | 🚧 未开发 | 按知识点/难度/题型/数量自动组卷、套卷管理、考试/练习卷、组题时复用去重能力避免重复题 |
| **评题** | 🚧 未开发 | 简答题 AI 评分与讲评、人工评题工作台、题目难度与质量的作答数据反馈 |
| **题目评论（完整功能）** | 🚧 未开发 | 评论互动生态（回复、点赞、举报、审核工作流完善）。现有 `/comments` 仅基础的增删查与审核接口 |
| **用户体系（C 端）** | 🚧 未开发 | 注册/登录、个人中心、练习记录、正确率与薄弱知识点统计（当前仅有管理端 `admin_user`） |
| **Flutter 移动端 App** | 🚧 未开发 | 计划使用 Flutter 开发 iOS/Android 客户端；**依赖上述做题/组题/评题/评论/用户体系后端 API**，后端就绪后启动 |
| 题目解析生成 | 🚧 未开发 | AI 生成答案解析与考点讲解 |
| 向量索引持久化 | 🚧 未开发 | 持久化/共享向量存储以支持多进程部署（当前强制单 worker） |
| 重复题裁决工具 | 🚧 未开发 | 历史重复题的人工裁决与合并（当前仅报告保留） |
| **前端 — 题目批量操作** | 🚧 未开发 | 批量审核（发布/驳回）、批量下架（后端暂无批量接口） |
| **前端 — 题目复制/移动** | 🚧 未开发 | 复制/移动题目到其他题库（后端暂无接口） |
| **前端 — 题目版本历史** | 🚧 未开发 | 题目历史版本对比、差异高亮（后端暂无版本接口） |
| **前端 — 富文本/Markdown 编辑器** | 🚧 未开发 | 题目内容/解析的富文本编辑（当前纯 textarea） |
| **前端 — 数据统计图表** | 🚧 未开发 | 题目正确率/答题数/知识库分布等图表（后端暂无统计接口） |
| **前端 — AI 解析生成入口** | 🚧 未开发 | AI 自动生成解析按钮（后端解析生成能力未实现） |
| **前端 — 任务重试/取消** | 🚧 未开发 | 生成任务的重试/取消（后端暂无接口） |
| **前端 — 国际化** | 🚧 未开发 | 多语言支持（当前仅中文） |
| **前端 — 暗色主题** | 🚧 未开发 | 深色模式切换（当前仅亮色） |
| **前端 — 移动端适配** | 🚧 未开发 | 平板/手机响应式（当前桌面优先，1280px+） |

### 建议开发顺序

```
做题后端（答题/判分/练习记录） → 组题/组卷 → 评题 → 评论完整版 → 用户体系
        └──────────────────────────────┴──► Flutter App（并行启动 UI）

前端后续：批量操作 → 富文本编辑器 → 数据统计图表 → 暗色主题 → 移动端适配
```

---

## 15. License

暂未添加开源许可证。若你希望在生产或二次分发中使用本项目，请先与作者确认授权。
