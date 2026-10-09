# AI 面试题库系统

# KnowledgeRelationAgent 开发与独立测试指导文档 V1.0

> **执行工具：DeepSeek Harness（DSH）**  
> **代码范围：仅 `backend/`**  
> **当前阶段：独立开发、验证关系判断质量；暂不接入正式导入流程，暂不写入 `knowledge_relation` 表。**

## 0. 给 DSH 的执行指令

请先阅读本文档，再检查当前项目代码结构和现有实现，完成 `KnowledgeRelationAgent` 的独立开发与测试。

必须遵守以下要求：

1. 只允许修改 `backend/` 目录，不修改 `admin-web/`、Flutter 客户端或其他前端代码。
2. 先检查现有 ORM 模型、Repository、Service、关系 CRUD API、向量检索和 Agent 实现，再决定具体文件位置；不得假设字段名或重写已有能力。
3. **本阶段只生成关系判断结果，不自动新增、更新或删除正式知识关系。** 测试接口必须是只读/无副作用的，不能写入 `knowledge_relation`。
4. 复用项目当前的 LLM、Pydantic、LangChain/LangGraph、Embedding 和 Vector DB 能力；不要新增另一套向量数据库或模型服务。
5. 不要为了本任务引入 Redis、Celery、RabbitMQ 或新的复杂基础设施。
6. 不修改现有表结构，不创建 Alembic 迁移，除非检查后发现完成测试确实不可避免；如有必要，先说明具体原因，优先采用不改表的方案。
7. 必须实际执行测试并提交真实测试结果。没有运行过的测试不得声称通过。
8. 先完成独立测试和验收报告，本次不要顺手接入 `ImportTask`。集成属于下一阶段。

## 1. 项目背景与当前状态

当前系统已经包含基础后端能力和知识导入链路，已实现并接入：

- FastAPI、MySQL、SQLAlchemy 2.x、Alembic、Pydantic。
- `KnowledgeExtractAgent`：从文档中抽取候选知识点。
- `KnowledgeDeduplicatePipeline`：判断候选知识是新增、重复还是需要合并。
- 知识点经过现有业务 Service 保存到 MySQL，并同步 Embedding / Vector DB。
- 现有数据表包含 `knowledge` 和 `knowledge_relation`。
- 现有知识管理 API 已包含查看、创建、删除知识关系的能力；具体实现以当前代码为准。

下一步要实现的是：**根据知识点内容，建议知识点之间存在什么关系。**

整体方向如下：

```text
Knowledge 已保存到 MySQL
          │
          ▼
根据某个知识点检索候选知识
          │
          ▼
KnowledgeRelationAgent
          │
          ▼
输出关系建议 + 关系类型 + 置信度 + 判断理由
          │
          ▼
测试人员检查结果
          │
          ▼
本阶段结束：不自动写正式关系表
```

MySQL 仍然是正式数据的事实来源，Vector DB 仍然只是检索索引。Agent 不得直接操作 ORM Session 或绕过 Service/Repository 修改正式数据。

## 2. 本阶段目标

### 2.1 必须实现

1. 定义稳定、可校验的关系判断输入输出模型。
2. 复用已有向量检索能力，为一个待分析知识点找出一组可能相关的候选知识点。
3. 使用 LLM 判断知识点对之间是否存在关系；没有关系时必须允许返回 `NO_RELATION`。
4. 正确区分 `prerequisite`、`related`、`extension`、`contrast` 四种关系。
5. 做确定性的结果校验：过滤自关联、无效 ID、重复候选、非法关系类型和无效方向。
6. 提供独立测试 API，能够传入人工指定的候选知识列表，绕开向量检索单独验证 LLM 的判断质量。
7. 支持使用现有向量检索自动找候选的测试路径；向量服务不可用时明确报告错误或降级状态，不能伪造候选或静默输出“无关系”。
8. 提供单元测试、接口测试和人工验收用例，并记录真实执行结果。

### 2.2 本阶段不做

- 不将 Agent 接入 `KnowledgeImportService` 或 `ImportTask`。
- 不将模型输出自动写入 `knowledge_relation`。
- 不重做 `KnowledgeExtractAgent`、`KnowledgeDeduplicatePipeline`、Embedding 或 Vector DB。
- 不重新实现知识点 CRUD，不修改现有前端页面。
- 不遍历整个知识库做全量两两比较，避免知识点数量增加后产生平方级比较成本。
- 不新增知识图谱平台、图数据库或其他独立基础设施。

## 3. 开始编码前必须检查的现有代码

请先定位并检查下列能力在当前仓库中的真实路径和实现：

| 检查项 | 必须确认的内容 |
|---|---|
| Knowledge ORM 模型 | 主键、名称、摘要/内容、关键词、状态字段及可用字段；不要假设每个字段都存在 |
| `knowledge_relation` ORM 模型 | 两端知识点 ID 字段、关系类型字段、唯一约束、外键和级联行为 |
| 关系 Repository / Service | 当前的关系创建和删除是否做重复校验；是否有统一事务入口 |
| 关系查询 API | 查询是否只查出边；是否也查入边；现有响应格式和权限依赖是什么 |
| Vector DB 检索封装 | 如何执行 Top-K 相似检索，如何过滤禁用知识点、如何排除自身 |
| Embedding Service | 现有知识点如何生成向量，文本查询是否已经支持 |
| Agent 目录 | 已有 Agent 的状态定义、图结构、LLM 获取方式、结构化输出、重试及日志约定 |
| API 统一响应 | 当前成功/失败响应封装、异常处理和认证方式 |
| 测试框架 | `pytest`、测试数据库、测试依赖覆盖方式和现有 fixtures |

检查后沿用当前项目的命名和分层。不要为了和本文示例路径一致而强行移动现有文件，也不要创建第二套 Vector Repository 或 LLM 初始化模块。

## 4. 四种关系的定义和方向

当前设计沿用项目已有关系类型：`prerequisite`、`related`、`extension`、`contrast`。落库字段和历史数据的实际约定仍以 ORM、Service 和现有 API 为准。

| 类型 | 含义 | 方向约定 | 示例 |
|---|---|---|---|
| `prerequisite` | 学习或理解目标知识前需要掌握的前置知识 | `from` 是前置知识，`to` 是依赖该知识的后续知识 | Java 多线程 → Java 线程池 |
| `extension` | 从基础、通用概念到更具体、更深入的扩展概念 | `from` 是基础/通用知识，`to` 是扩展/具体知识 | Java 线程池 → ThreadPoolExecutor 核心参数 |
| `related` | 存在明确概念联系，但不足以归为前置、扩展或对比 | 逻辑上通常无方向 | Java 内存模型 ↔ volatile 关键字 |
| `contrast` | 两个概念或方案有明确的对照、差异比较意义 | 逻辑上通常无方向 | synchronized 与 ReentrantLock |

### 4.1 方向判断必须遵守

1. 不得根据传入列表的前后顺序决定关系方向。
2. 若输入锚点是“Java 线程池”，候选是“Java 多线程”，且判断二者是前置关系，则输出方向仍应为：`Java 多线程 → Java 线程池`，而不是反向。
3. `extension` 同样按“基础/通用 → 扩展/具体”的方向输出。
4. `related` 和 `contrast` 的方向不代表语义先后；它们可在结果中按锚点、候选的次序展示，但持久化去重规则要遵循现有表和 Service 的约定。
5. 一对知识点 V1.0 默认只输出一个最主要的关系类型，避免同时输出 `related`、`extension` 等相互泛化的标签。只有现有业务模型明确允许多关系且样例验证有必要时，才扩展。
6. 如果没有足够证据确定关系，必须返回 `NO_RELATION`，不能为了提高关系数量而强行分类。

## 5. 推荐的处理流程

```text
输入待分析知识点
        │
        ├── 请求已提供 candidates ──► 跳过 Vector DB，直接判断
        │
        └── 未提供 candidates
                    │
                    ▼
          复用现有 Embedding / Vector Search
                    │
                    ▼
       Top-K 候选（默认建议 10，可配置）
                    │
                    ▼
        去掉自身、重复项和不可用知识
                    │
                    ▼
       LLM 对候选对进行关系判定
                    │
                    ▼
         Pydantic 校验结构化输出
                    │
                    ▼
        确定性校验、去重、方向标准化
                    │
                    ▼
          返回关系建议及诊断信息
                    │
                    ▼
       本阶段不写入 knowledge_relation
```

### 5.1 候选检索

- 优先使用现有向量检索服务；建议先从 `Top-K = 10` 开始，并做成可配置参数，不要在多处散落硬编码。
- 候选必须来自真实的知识记录，默认只检索当前系统中可参与正常检索的知识状态。
- 排除锚点自身，排除重复 ID；可根据现有模型排除软删除或禁用记录。
- 候选文本应尽量提供名称和摘要；如果现有知识模型有内容、关键词等字段，可按合理长度补充。不要将整个知识库所有全文无上限塞进一个 Prompt。
- 如果当前 Vector DB 只能按已有向量 ID 检索，请检查现有 Embedding Service 是否支持文本生成向量，再复用现有 Repository 实现最小适配。不得再建一套向量服务。
- 人工指定候选模式必须可以完全绕开 Vector DB。这样即使向量服务暂时不可用，也能独立测试 Agent 判断能力。
- 如果自动检索失败，响应应说明是 `retrieval_failed` 或返回项目统一错误；不要把检索失败误报成“0 个候选，因此无关系”。

### 5.2 LLM 判断策略

- 尽可能把一组候选放在一次结构化请求中进行批量判断，避免每个候选固定调用一次 LLM。
- 候选数量过大时，可分批调用；批次大小可配置，并记录真实 LLM 调用次数和耗时。
- 沿用现有 `get_llm()` 等缓存初始化方式，不要在每个节点、每一对知识点上重复创建模型客户端。
- 使用当前项目的 Pydantic 结构化输出习惯，输出无法解析时做有限重试；重试耗尽后将本次判断标记为失败，不得伪造默认关系。
- Prompt 必须同时提供关系定义、方向规则、候选内容和“无关系”判断规则。
- 只有存在有意义的概念依赖、知识层次、明确关联或可对比关系时才输出关系。共同出现某个词、同属 IT 领域或者语义向量相似，不足以单独证明关系成立。

## 6. 输入和输出模型建议

下列字段用于统一接口语义；具体 Python 类名和字段类型请适配现有项目。不得为了照搬示例而修改已有数据库表结构。

### 6.1 输入模型

建议创建类似 `KnowledgeRelationTestRequest` 的 Pydantic 模型：

| 字段 | 类型/默认值 | 含义 |
|---|---|---|
| `source_knowledge_id` | 可选整数 | 从 MySQL 读取正式知识作为锚点；与 `source_knowledge` 二选一 |
| `source_knowledge` | 可选对象 | 用于独立测试的知识文本对象，至少有 `name`，可带 `summary`、`content`、`keywords` 和测试 ID |
| `candidates` | 可选数组 | 人工提供候选；提供后跳过 Vector DB，数组中的候选 ID 必须在本次测试中唯一 |
| `candidate_knowledge_ids` | 可选整数数组 | 可选的候选 ID 列表；使用时从数据库读取候选详情 |
| `top_k` | 整数，建议默认 10 | 自动检索候选数量，设置合理上限 |
| `min_confidence` | 数值，范围 0–1 | 测试过滤/展示阈值；初始值仅作为可调参数，不把它当作模型准确性的保证 |

校验规则：

- `source_knowledge_id` 与 `source_knowledge` 必须且只能提供一个。
- `candidates` 和 `candidate_knowledge_ids` 不得同时提供，避免两套候选来源冲突。
- `candidates` 有值时直接用于 LLM 测试，不调用 Vector DB。
- 没有提供任何候选来源时才尝试调用自动检索。
- 无候选时允许返回空关系列表，同时明确 `candidate_count = 0` 和 `retrieval_mode`。
- 测试接口不需要、也不应提供 `persist=true` 一类落库开关，确保其没有写入能力。

### 6.2 单个判断结果

建议定义类似 `KnowledgeRelationJudgement` 的模型：

| 字段 | 类型 | 含义 |
|---|---|---|
| `candidate_knowledge_id` | 整数 | 本次被判断的候选知识 ID |
| `decision` | 枚举 | `RELATION` 或 `NO_RELATION` |
| `relation_type` | 可空枚举 | `prerequisite` / `related` / `extension` / `contrast`；无关系时为空 |
| `from_knowledge_id` | 可空整数 | 有方向关系中的语义起点；`prerequisite` 为前置知识，`extension` 为基础知识 |
| `to_knowledge_id` | 可空整数 | 有方向关系中的语义终点 |
| `confidence` | 0–1 数值 | 模型对本次判断的置信度估计，仅供辅助评估，不能视为经过校准的概率 |
| `reason` | 字符串 | 简短说明两者为什么存在关系，或为什么不应建立关系 |

如果现有 ORM 或 API 对 `source/target` 的命名不同，应在 Agent 输出到现有 Service 之间做映射，不要为了示例字段改表。

### 6.3 接口总响应

建议返回以下信息（可适配项目统一响应包装）：

```json
{
  "source_knowledge_id": 1001,
  "retrieval_mode": "provided_candidates",
  "candidate_count": 4,
  "relation_count": 2,
  "no_relation_count": 2,
  "llm_call_count": 1,
  "elapsed_ms": 1350,
  "saved": false,
  "evaluations": [
    {
      "candidate_knowledge_id": 1002,
      "decision": "RELATION",
      "relation_type": "prerequisite",
      "from_knowledge_id": 1002,
      "to_knowledge_id": 1001,
      "confidence": 0.86,
      "reason": "线程池建立在多线程并发执行机制之上。"
    },
    {
      "candidate_knowledge_id": 1003,
      "decision": "NO_RELATION",
      "relation_type": null,
      "from_knowledge_id": null,
      "to_knowledge_id": null,
      "confidence": 0.91,
      "reason": "主题缺乏直接的知识依赖、扩展或对比关系。"
    }
  ]
}
```

以上 JSON 只用于说明字段含义；`elapsed_ms`、ID、置信度和判断理由均为示例值，不是项目实际运行结果。

`"saved": false` 是本阶段的硬性要求，必须由服务端固定返回，不能由调用方传入覆盖。

## 7. LLM Prompt 约束

System Prompt 至少要明确：

1. 你是面试题库的知识关系判定器，不负责生成新知识点，也不负责写数据库。
2. 仅根据输入提供的名称、摘要、正文等证据进行判断；证据不足时选择 `NO_RELATION`。
3. 只允许使用四种关系类型，不能自创新的类型。
4. `prerequisite`：`from` 是前置知识，`to` 是后续知识。
5. `extension`：`from` 是更基础或通用知识，`to` 是更深入或更具体的知识。
6. `related` 用于明确相关但不能合理归类为前三者的情况；`contrast` 用于有实际比较意义的不同方案、概念或机制。
7. 不得因关键词重合、同属某个编程领域或向量相似就直接建立关系。
8. 不得编造候选 ID，也不得输出候选数组以外的知识点。
9. 每对知识点最多返回一个最主要的关系类型；允许没有关系。
10. 必须按关系语义确定方向，而不是简单沿用输入顺序。
11. 必须返回符合 Pydantic Schema 的结构化结果；不要输出额外 Markdown。

Prompt 要保持清楚、可测试，不要加入大量互相重复的长篇说明。通过正反例验证 Prompt 是否有效。

## 8. 确定性校验和防重复

LLM 输出后必须经过普通 Python 代码校验，不能完全信任模型输出：

- `decision=NO_RELATION` 时，清空关系类型和两个方向 ID，保留理由用于测试分析。
- `decision=RELATION` 时，`relation_type` 必须属于四个允许值，两个端点都必须是当前锚点或候选列表中的有效 ID。
- 不允许 `from_knowledge_id == to_knowledge_id`。
- 不允许指向候选列表之外的 ID，不允许一个候选被模型映射成虚构 ID。
- `prerequisite` 和 `extension` 必须按第 4 节的语义规则标准化方向；不要只按数字大小排序。
- `related` 和 `contrast` 可在展示结果中保留本次锚点与候选的顺序。正式落库时是否使用规范化无向 pair、唯一约束或双向查询，须在下一阶段结合现有表约束和 API 行为决定；本阶段不得擅自改变历史存储约定。
- 同一候选不能因为批次重复、LLM 重复输出而在响应中出现多条相同关系建议。
- 置信度必须在 0–1 范围内；缺失或非法置信度应按结构校验处理，不要悄悄转换成 1。
- 对不可信、格式错误或无法映射的模型结果，要产生可诊断的错误日志；不能将校验失败变成随意生成的关系。

## 9. 独立测试 API

新增一个只用于测试的后台 API，建议路径：

```http
POST /api/v1/agent/knowledge-relation/test
```

如果项目已有 Agent 测试路由命名规范，按现有规范调整，但接口必须具备同等能力。

要求：

- 使用项目现有管理员认证与统一响应格式，不得变成未认证的公开接口。
- 支持人工传候选的模式，必须不访问 Vector DB。
- 支持自动检索候选的模式，复用现有向量检索服务。
- 返回每个候选的判断结果、关系建议、简短理由、置信度、耗时、候选数量、LLM 调用次数和候选来源模式。
- 测试 API 不写 `knowledge_relation`，也不改动知识点内容或 Embedding。
- 不使用“先写库再删除”模拟只读测试；代码路径本身就不能调用创建关系的 Service。
- 如果项目现有 API 测试都使用 `interview_agent_test`，本任务继续使用测试数据库，不得直接使用生产数据修改。

### 9.1 人工候选请求示例

下面示例字段需要根据实际 `Knowledge` schema 做最终适配。ID 只作为示例：

```json
{
  "source_knowledge": {
    "id": 1001,
    "name": "Java 线程池",
    "summary": "线程池用于复用线程并管理并发任务执行。",
    "content": "线程池通过任务队列、线程复用和拒绝策略等机制管理任务。",
    "keywords": ["Java", "并发", "线程池"]
  },
  "candidates": [
    {
      "id": 1002,
      "name": "Java 多线程",
      "summary": "多个线程并发执行任务的机制。",
      "content": "介绍线程创建、调度和并发执行基础。",
      "keywords": ["Java", "线程", "并发"]
    },
    {
      "id": 1003,
      "name": "SQL 索引优化",
      "summary": "通过索引改善数据库查询性能。",
      "content": "介绍索引结构与查询计划。",
      "keywords": ["SQL", "索引", "数据库"]
    }
  ],
  "top_k": 10,
  "min_confidence": 0.65
}
```

人工候选模式预期：Agent 对 Java 多线程可能判断为线程池的前置知识；对 SQL 索引优化应倾向于 `NO_RELATION`。测试评价时应看实际模型返回，不要直接把预期写死成接口的伪造结果。

### 9.2 自动检索请求示例

```json
{
  "source_knowledge_id": 1001,
  "top_k": 10,
  "min_confidence": 0.65
}
```

接口从数据库读取锚点知识，调用已有 Vector DB 检索候选并返回关系建议；仍然不落库。如果现有向量服务不支持该查询路径，先复用项目 Embedding + Vector Repository 做最小适配，或者清晰地报告当前能力限制，不可绕开现有架构另建一套服务。

## 10. 建议的实现分层

具体目录以仓库约定为准，职责建议如下：

| 模块 | 职责 |
|---|---|
| `KnowledgeRelationAgent` | 编排关系判定流程；不直接写数据库 |
| Relation Graph / Nodes（若沿用 LangGraph） | 输入校验、候选处理、LLM 判断、结果校验和汇总 |
| Relation Pydantic Schemas | 请求、单条判定和总响应的结构化定义 |
| Candidate Retrieval Service | 复用现有 Embedding / Vector Search，生成候选列表 |
| Relation Prompt | 集中维护系统提示词和候选判断提示词 |
| Agent Test API / Router | 负责鉴权、参数校验、调用 Agent 和返回统一响应 |
| Tests | 使用 Fake/Mock LLM、Fake Vector Search 做稳定的自动化测试 |

`KnowledgeRelationAgent` 负责推理与结果提议；数据库访问由已有 Service / Repository 负责。本阶段可为自动检索读取数据，但不得写关系数据。

## 11. 自动化测试要求

必须同时覆盖单元测试与 API 行为测试。尽量使用 Fake/Mock LLM 和 Fake Vector Search 使 CI 测试不依赖真实模型 API、真实向量服务或外部网络。

### 11.1 规则与结构测试

| 编号 | 场景 | 验收点 |
|---|---|---|
| T01 | `prerequisite` 正向关系 | 输出方向为前置知识 → 后续知识 |
| T02 | `extension` 正向关系 | 输出方向为基础知识 → 扩展知识 |
| T03 | `related` 关系 | 关系类型合法，有理由，不伪造方向语义 |
| T04 | `contrast` 关系 | 关系类型合法，有明确可对比理由 |
| T05 | 无关系候选 | 正确返回 `NO_RELATION`，不生成关系记录 |
| T06 | 自关联 | 相同知识 ID 不生成关系 |
| T07 | 非法 relation_type | 被结构校验拒绝或标记为失败，不流入结果 |
| T08 | 不存在的候选 ID | 不允许模型引用候选集合外的知识 ID |
| T09 | 重复候选 | 相同候选 ID 只评估/输出一次，或按清晰规则去重 |
| T10 | 空候选数组 | 正常返回 0 条关系建议，不进行无意义 LLM 调用 |
| T11 | 错误的 from/to 方向 | 由确定性校验修正或拒绝，并有测试覆盖 |
| T12 | LLM 超时/输出无效 | 有限重试，最终给出可诊断失败；不伪造关系 |

### 11.2 候选检索和接口测试

| 编号 | 场景 | 验收点 |
|---|---|---|
| T13 | 人工 candidates 模式 | 不调用 Vector DB，返回结构化结果 |
| T14 | 自动检索模式 | 使用当前检索服务；排除自身、重复和不可用知识 |
| T15 | Vector DB 不可用 | 明确报告检索失败/降级，不冒充正常的无关系判断 |
| T16 | 未认证请求 | 沿用后台接口认证规范，拒绝未授权调用 |
| T17 | 测试接口调用后数据库快照 | `knowledge_relation` 行数及相关数据保持不变 |
| T18 | 现有回归测试 | 原有 Auth、Knowledge、Question、ImportTask、Dashboard 等测试不回归失败 |

### 11.3 人工模型质量测试集

除单测外，准备至少 20 对人工标注的知识对，覆盖四种关系和无关系场景。建议包含：

| 锚点/知识 A | 候选/知识 B | 预期判断 | 重点检查 |
|---|---|---|---|
| Java 线程池 | Java 多线程 | prerequisite（多线程 → 线程池） | 方向不能颠倒 |
| Java 线程池 | ThreadPoolExecutor 核心参数 | extension（线程池 → 核心参数） | 基础与具体层级 |
| synchronized | ReentrantLock | contrast | 是否有真实对比意义 |
| Java 内存模型 | volatile 关键字 | related 或经人工标注的更具体关系 | 结合当前定义检查是否过度使用 related |
| Java 线程池 | SQL 索引优化 | NO_RELATION | 同属技术领域不等于有关联 |
| Android Activity 生命周期 | SQL 索引优化 | NO_RELATION | 避免把无关概念强行连接 |

上表只是部分示例，不足 20 对。开发时请补全人工标注集，覆盖正例、反向输入、近似但无关系、相关但方向不明和完全无关等场景。记录期望结果、实际结果和误判原因，不要只展示模型挑选出的正确案例。

阶段性质量建议：20 对样例的人工检查结果应至少达到 80% 的整体判断正确率，同时重点统计无关系样例的误报数。该数值是本阶段建议的验收目标，不是模型准确率承诺；达不到时优先调整候选范围、Prompt 和输出校验，未达到可接受质量前不要接入正式导入。

## 12. 性能、日志和错误处理

每次测试至少记录以下信息：

- 总耗时和 LLM 判断耗时。
- 检索方式、候选数量、实际送入 LLM 的候选数量。
- LLM 调用次数、重试次数及错误类型。
- 输出关系数、`NO_RELATION` 数量、校验丢弃数。
- 发生异常时的当前步骤和可定位错误信息。

注意事项：

- 10 个候选不应在没有理由的情况下固定产生 10 次串行 LLM 请求。优先批量判断，必要时再分批。
- 不记录密钥、Authorization Token 或完整敏感配置。
- 单批 LLM 失败不能被当作“所有候选都无关系”。应区分 `NO_RELATION` 和 `FAILED`。
- `confidence` 只是模型给出的自评信号，不是经过统计校准的概率。不要只凭置信度就认定判断一定正确。
- 不要为追求更多关系而降低标准。关系质量优先于关系数量。

## 13. 实现步骤

请按以下顺序执行，不要跳过检查直接大范围重构：

1. 阅读当前 Knowledge/Relation ORM、关系 Service/Repository、关系 API、Vector Search、Embedding Service 和已有 Agent 目录。
2. 在 DSH 的执行结果中先简要记录真实文件路径、当前可复用的向量检索接口、当前关系类型和数据库约束；完成检查后继续实现，无需等待用户逐条确认。
3. 定义 Pydantic 请求、单条关系判定和响应 Schema。
4. 实现人工候选模式和结果验证逻辑，先让 Agent 不依赖 Vector DB 也能跑通。
5. 实现批量 LLM 判断和 Prompt；复用当前模型初始化、结构化输出、日志和重试规范。
6. 实现自动检索模式，严格复用现有 Embedding/Vector DB。
7. 新增只读测试 API，沿用已有认证和响应风格。
8. 编写 Fake/Mock LLM 单元测试、检索测试、API 测试以及“不写关系表”的测试。
9. 运行相关新测试，再运行完整后端回归测试。
10. 使用不少于 20 对的人工标注样例做一次真实模型测试（若当前环境无 LLM 凭据，明确标注未运行，不得假报通过）。
11. 输出开发总结、修改文件清单、测试命令和结果、人工样例质量统计、已知限制。
12. 停止在独立 Agent 测试阶段，不接入 `ImportTask`。

## 14. 本阶段最终验收标准

- [ ] 已检查并复用了当前 Knowledge、Relation、Embedding、Vector Search 和 Agent 基础设施。
- [ ] 支持人工提供候选的独立测试模式。
- [ ] 支持自动检索候选的测试模式，或者明确记录当前阻塞和最小缺口。
- [ ] 正确使用四种现有关系类型。
- [ ] `prerequisite` 和 `extension` 的方向符合定义，不依赖输入顺序。
- [ ] 支持明确输出 `NO_RELATION`。
- [ ] 模型输出由 Pydantic 和确定性规则校验。
- [ ] 有候选外 ID、自关联、重复候选、非法类型、超时/坏输出等测试。
- [ ] 测试 API 使用现有认证和统一响应格式。
- [ ] 测试 API 的代码路径不写 `knowledge_relation`；已通过数据库快照或 Mock 验证无写入。
- [ ] 没有修改前端、没有另建向量服务、没有引入 Redis/Celery/RabbitMQ。
- [ ] 新增测试已真实执行，完整回归测试已执行并报告结果。
- [ ] 已人工检查至少 20 对知识对，记录整体判断正确率和无关系误报情况；环境不满足时如实说明。
- [ ] 输出修改文件清单、运行方式、API 请求示例、测试报告及遗留问题。
- [ ] 未接入 `ImportTask`，没有将关系建议写入正式数据库。

## 15. 下一阶段边界（本次不要执行）

待 `KnowledgeRelationAgent` 的人工样例质量达到可接受水平后，再单独开展关系持久化与导入集成。下一阶段需要结合当前真实表结构和已有 Service 再决定保存策略，原则上是：

```text
ImportTask 保存新知识 / 更新知识成功
                ↓
          得到真实 knowledge_id
                ↓
      只处理本次新增或变更的知识点
                ↓
      复用 Vector DB 检索候选关系
                ↓
      KnowledgeRelationAgent 输出建议
                ↓
      关系去重、方向校验和幂等检查
                ↓
      通过现有 Relation Service 写入
```

后续集成必须处理重复运行、已有关系、双向查询、失败恢复和部分成功；不能在本次独立测试任务中提前实现。

---

**交付要求：** 完成后请在 DSH 中给出真实的实现说明与测试结果，并明确区分“自动化测试通过”“真实 LLM 样例通过”“由于环境原因未执行”的部分。不要只返回代码变更摘要，也不要宣称未执行的测试已经通过。
