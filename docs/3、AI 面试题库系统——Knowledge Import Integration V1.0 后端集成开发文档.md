# AI 面试题库系统
## Knowledge Import Integration V1.0

> 本文用于指导 DeepSeek Harness（DSH）完成知识导入链路的正式集成。
>
> 当前阶段目标：
>
> **将已经验证的 KnowledgeExtractAgent、已经完成的 KnowledgeDeduplicatePipeline、MySQL 正式知识库、Vector DB 正式串联起来。**
>
> 最终实现：
>
> ```text
> 管理员上传文档
>       ↓
> ImportTask
>       ↓
> DocumentParser
>       ↓
> TextChunker
>       ↓
> KnowledgeExtractAgent
>       ↓
> KnowledgeCandidate
>       ↓
> Batch 内部去重
>       ↓
> 与数据库已有 Knowledge 去重
>       ↓
> NEW / DUPLICATE / MERGE
>       ↓
> KnowledgeService
>       ↓
> MySQL
>       ↓
> Embedding 同步
>       ↓
> Vector DB
> ```
>
> 当前阶段不是开发新的 Agent。
>
> 当前阶段重点是：
>
> **把已经完成的两个 AI 能力正式接入业务流程。**

---

# 1. 当前项目状态

当前项目已经完成：

```text
FastAPI
MySQL
SQLAlchemy
Alembic
JWT
Vue3 管理后台
ImportTask 基础功能
DocumentParser
TextChunker
KnowledgeExtractAgent
KnowledgeDeduplicatePipeline
```

其中：

### KnowledgeExtractAgent

已经能够：

```text
文件
↓
解析
↓
Chunk
↓
LLM
↓
KnowledgeCandidate
```

并已经独立测试。

### KnowledgeDeduplicatePipeline

已经完成：

```text
Candidate
↓
标准化
↓
Embedding / Vector Search
↓
规则判断
↓
必要时 Agent 判断
↓
NEW / DUPLICATE / MERGE
```

本次任务不是重新实现这些能力。

---

# 2. 本阶段最核心的问题

目前：

```text
KnowledgeExtractAgent
```

只产生：

```text
KnowledgeCandidate
```

还没有正式进入：

```text
knowledge
```

而 DeduplicatePipeline 又需要：

```text
已有知识点
```

进行比较。

因此需要建立一个完整的业务链：

```text
Candidate
       ↓
DeduplicatePipeline
       ↓
KnowledgeService
       ↓
MySQL
```

同时还要保证：

```text
MySQL knowledge
       ↕
Vector DB
```

中的数据保持基本一致。

---

# 3. 数据所有权原则

本阶段必须明确：

> **MySQL 是正式知识库的最终事实来源。**

Vector DB 只是：

> **用于相似知识检索的辅助索引。**

因此：

```text
MySQL
    = Source of Truth
```

Vector DB：

```text
    = Search Index
```

不能反过来。

不要设计成：

```text
Vector DB 数据才是真实知识
```

---

# 4. 正式导入流程

最终 ImportTask 流程：

```text
PENDING
  ↓
RUNNING
  ↓
PARSING
  ↓
EXTRACTING_KNOWLEDGE
  ↓
DEDUPLICATING_KNOWLEDGE
  ↓
SAVING_KNOWLEDGE
  ↓
SYNCING_EMBEDDINGS
  ↓
SUCCESS
```

异常情况下：

```text
PARTIAL_SUCCESS
```

或者：

```text
FAILED
```

具体根据实际失败位置决定。

---

# 5. ImportTask 不再只是模拟

现有：

```text
POST /api/v1/import-tasks/{id}/simulate
```

是之前用于测试前端任务 UI 的模拟接口。

本阶段：

> **不要删除现有 simulate 接口。**

但是正式业务不能继续依赖它。

新增正式处理入口，例如：

```text
POST /api/v1/import-tasks/{id}/run
```

或者由 Service 内部触发。

具体 API 设计根据当前项目结构选择。

---

# 6. 现有前端暂时不要修改

本阶段：

> **只修改 backend。**

不要修改：

```text
admin-web/
```

因为前端和后端由不同 CLI 会话维护。

如果发现前端以后需要新的字段：

只记录：

```text
需要前端适配
```

不要直接修改前端。

---

# 7. 第一阶段：已有 Knowledge 的 Embedding 初始化

正式去重之前，必须先解决：

> 数据库中以前已经存在的知识点没有 Embedding。

所以先增加：

```text
KnowledgeEmbeddingSync
```

---

# 8. Embedding 初始化

实现一个批量初始化能力：

```text
MySQL knowledge
       ↓
读取正常知识点
       ↓
构建 Embedding 文本
       ↓
批量生成 Embedding
       ↓
Vector DB upsert
```

只处理：

```text
status = 正常
```

的知识点。

禁用知识点默认不进入检索。

---

# 9. Embedding 文本

默认使用：

```text
name
+
summary
+
keywords
```

例如：

```text
Java线程池

Java线程池用于管理和复用线程。

关键词：
ThreadPoolExecutor
线程池
核心线程数
最大线程数
```

不要默认把完整 `content` 全部发送给 Embedding。

除非现有 DeduplicatePipeline 已经证明必须使用 content。

---

# 10. Embedding 必须批量执行

禁止：

```text
知识点1 → Embedding API
知识点2 → Embedding API
知识点3 → Embedding API
```

优先：

```text
知识点1
知识点2
知识点3
...
知识点N
        ↓
批量 Embedding
```

批量大小可配置。

例如：

```text
EMBEDDING_BATCH_SIZE=32
```

实际值根据模型 API 限制调整。

---

# 11. Vector DB Upsert

使用：

```text
knowledge_id
```

作为稳定标识。

例如：

```text
knowledge_id = 1001
```

对应：

```text
Vector ID = knowledge_1001
```

这样可以保证：

```text
重复同步
```

不会创建多个向量。

必须使用：

```text
upsert
```

而不是每次：

```text
insert
```

---

# 12. 初始化命令

必须提供一个开发/运维脚本：

```bash
python scripts/sync_knowledge_embeddings.py
```

作用：

```text
读取 MySQL 正常知识点
↓
Embedding
↓
Vector DB
```

脚本必须支持：

```text
重复执行
```

重复执行不会产生重复 Vector。

---

# 13. 初始化脚本输出

至少输出：

```text
总知识点：
待处理：
成功：
失败：
耗时：
```

例如：

```text
知识点总数：1000
需要同步：1000
成功：997
失败：3
耗时：12.5s
```

---

# 14. 部分失败

例如：

```text
1000 个知识点
998 成功
2 失败
```

不要让整个任务直接丢失结果。

输出失败 ID：

```text
knowledge_id=1005
knowledge_id=1099
```

方便重新同步。

---

# 15. 新增 Knowledge 后同步 Embedding

正式业务：

```text
NEW
↓
KnowledgeService.create()
↓
MySQL
↓
Embedding
↓
Vector DB
```

推荐顺序：

> **先提交 MySQL，再同步 Vector DB。**

原因：

MySQL 是最终事实来源。

---

# 16. 为什么不先 Vector DB 再 MySQL

因为如果：

```text
Vector DB 成功
MySQL 失败
```

就会出现：

```text
Vector 中存在不存在于正式知识库的数据
```

更难处理。

所以优先：

```text
MySQL
↓
Vector DB
```

---

# 17. Vector DB 同步失败怎么办

Vector DB 属于外部系统。

MySQL 和 Vector DB 不能使用普通数据库事务保证完全一致。

所以：

```text
MySQL 成功
Vector DB 失败
```

不能回滚 MySQL。

应该：

```text
记录同步失败
任务标记 PARTIAL_SUCCESS
记录失败 knowledge_id
```

然后允许重新同步。

---

# 18. Vector 同步必须支持重试

提供：

```text
sync_knowledge_embedding(knowledge_id)
```

可以重复执行。

同一个：

```text
knowledge_id
```

最终只应该存在一份有效向量。

---

# 19. Knowledge 更新后的 Embedding

如果：

```text
Knowledge MERGE
```

导致：

```text
name
summary
content
keywords
```

发生变化。

必须：

```text
MySQL UPDATE
↓
重新 Embedding
↓
Vector DB upsert
```

不能继续使用旧向量。

---

# 20. Knowledge 禁用后的 Embedding

如果：

```text
knowledge.status = DISABLED
```

则该知识点：

> 默认不应该被新的去重搜索使用。

因此 Vector DB 可以：

```text
删除
```

或者：

```text
标记 inactive
```

具体根据当前 Vector DB 实现决定。

---

# 21. 第二阶段：Candidate 批次内部去重

这是正式流程中非常重要的一步。

例如 ExtractAgent 得到：

```text
候选1：Java线程池
候选2：Java线程池机制
候选3：Java线程池
候选4：ThreadPoolExecutor
```

数据库此时可能还没有：

```text
Java线程池
```

如果逐个查数据库：

```text
候选1 → NEW
候选2 → NEW
候选3 → NEW
候选4 → NEW
```

仍然会产生重复。

因此必须：

> **先对本次导入产生的 Candidate 进行内部去重。**

---

# 22. Batch 内部去重

流程：

```text
ExtractAgent
     ↓
Candidates
     ↓
Normalize
     ↓
Exact Duplicate
     ↓
Embedding Similarity
     ↓
必要时 DeduplicateAgent
     ↓
Unique Candidate List
```

最终得到：

```text
Candidate A
Candidate B
Candidate C
```

再进入数据库去重。

---

# 23. Candidate 内部去重不写 MySQL

这一阶段所有候选仍然只是：

```text
内存对象
```

不要写：

```text
knowledge
```

表。

等整个去重流程结束后才写入。

---

# 24. Candidate 与数据库已有 Knowledge 对比

内部去重完成后：

```text
Unique Candidates
        ↓
对于每一个 Candidate
        ↓
查询 Vector DB
        ↓
Top K 已有 Knowledge
        ↓
DeduplicatePipeline
```

---

# 25. 数据库 Knowledge 查询范围

默认只搜索：

```text
status = NORMAL
```

的知识点。

不要把：

```text
DISABLED
```

知识点作为正常候选。

---

# 26. DeduplicatePipeline 不重新实现

如果当前项目已经有：

```text
KnowledgeDeduplicatePipeline
```

本阶段：

> **优先复用现有 Pipeline。**

不要重新写一个第二套去重逻辑。

如果现有 Pipeline 接口不支持：

```text
候选内部去重
数据库知识点去重
```

则：

> 最小范围扩展现有 Pipeline。

不要重构整个 Agent。

---

# 27. 正式去重流程

最终：

```text
Candidate
    ↓
Batch 内部去重
    ↓
数据库已有 Knowledge 搜索
    ↓
Top K
    ↓
DeduplicatePipeline
    ↓
NEW
DUPLICATE
MERGE
```

---

# 28. NEW

如果：

```text
NEW
```

执行：

```text
KnowledgeService.create()
```

写入：

```text
knowledge
```

成功后：

```text
Embedding
↓
Vector DB upsert
```

---

# 29. DUPLICATE

如果：

```text
DUPLICATE
```

则：

> 不创建新的 Knowledge。

记录：

```text
candidate
target_knowledge_id
decision = DUPLICATE
```

不要删除候选的来源信息。

---

# 30. MERGE

如果：

```text
MERGE
```

执行：

```text
已有 Knowledge
+
merged_knowledge
↓
KnowledgeService.update()
```

然后：

```text
重新 Embedding
↓
Vector DB upsert
```

---

# 31. MERGE 必须通过 Service

禁止：

```text
DeduplicateAgent
↓
直接 UPDATE MySQL
```

正确：

```text
DeduplicateAgent
↓
DeduplicateDecision
↓
KnowledgeService
↓
Repository
↓
MySQL
```

---

# 32. 事务原则

对于：

```text
NEW
```

数据库写入必须在事务中。

例如：

```text
BEGIN
↓
create knowledge
↓
commit
```

---

# 33. MERGE 事务

例如：

```text
BEGIN
↓
update knowledge
↓
commit
```

Embedding 不属于 MySQL 事务。

因此：

```text
MySQL commit
↓
Vector sync
```

---

# 34. 不允许 Agent 直接写数据库

所有 Agent：

```text
只负责判断
```

业务 Service：

```text
负责执行
```

Repository：

```text
负责数据库
```

---

# 35. ImportTask 状态

建议正式执行阶段至少使用：

```text
PENDING
RUNNING
PARSING
EXTRACTING_KNOWLEDGE
DEduplicating_KNOWLEDGE
SAVING_KNOWLEDGE
SYNCING_EMBEDDINGS
SUCCESS
PARTIAL_SUCCESS
FAILED
CANCELLED
```

状态名字必须与项目实际枚举保持一致。

不要同时出现：

```text
DEDUPLICATING
DE_DUP
DEDUP
```

等多套命名。

---

# 36. ImportTask 进度

建议划分：

```text
PARSING                 0~10
EXTRACTING_KNOWLEDGE   10~50
DEDUPLICATING           50~75
SAVING                  75~90
SYNCING_EMBEDDINGS      90~100
```

这是初始方案。

实际根据运行情况可以调整。

---

# 37. 不要伪造进度

进度必须根据真实阶段更新。

不能：

```text
上传后直接 80%
```

然后等待很久。

用户看到的进度应该能反映：

```text
当前真正正在做什么。
```

---

# 38. ImportTask 最终统计

建议增加：

```text
candidate_count
new_count
duplicate_count
merge_count
failed_count
```

如果当前数据库表没有这些字段：

> 可以通过最小数据库 Migration 增加。

不要重新设计整张表。

---

# 39. ImportTask 最终结果

最终返回：

```json
{
  "candidate_count": 25,
  "new_count": 12,
  "duplicate_count": 9,
  "merge_count": 4,
  "failed_count": 0
}
```

这样管理员可以知道：

> 这次导入真正给知识库增加了多少东西。

---

# 40. 任务失败策略

例如：

```text
25 candidates
12 NEW
7 DUPLICATE
2 MERGE
4 failed
```

不要：

```text
整个任务 FAILED
```

而应该：

```text
PARTIAL_SUCCESS
```

并记录具体失败内容。

---

# 41. 单个 Candidate 失败

例如：

```text
Candidate 17
```

Embedding 失败或者 DeduplicateAgent 失败。

不能让：

```text
Candidate 1~16
```

全部回滚。

应该：

```text
记录 candidate 17 错误
继续处理其他 Candidate
```

---

# 42. 但是数据库事务仍然要保证单条数据的一致性

例如：

```text
Candidate A
```

创建 Knowledge 时：

```text
Knowledge INSERT 失败
```

则：

```text
A = failed
```

不要留下半条数据。

---

# 43. ImportTask 重试

任务需要支持：

```text
FAILED / PARTIAL_SUCCESS
```

重新执行。

重新执行时：

> 不能因为重复运行同一个任务而生成大量重复 Knowledge。

依赖：

```text
Exact Match
+
Embedding
+
DeduplicatePipeline
```

保障幂等。

---

# 44. 已有 Knowledge 的 Embedding 初始化必须先完成

在正式启用：

```text
Database Knowledge Deduplication
```

之前，必须至少执行：

```bash
python scripts/sync_knowledge_embeddings.py
```

并确认：

```text
正常 Knowledge
```

已经进入 Vector DB。

否则：

```text
数据库里明明有“Java线程池”
```

但 Vector DB 里没有。

最终：

```text
新候选“Java线程池机制”
→ 搜不到
→ 错误判定 NEW
→ 创建重复知识
```

这是必须避免的问题。

---

# 45. Embedding 一致性检查

增加一个检查脚本：

```bash
python scripts/check_knowledge_embeddings.py
```

检查：

```text
MySQL 正常知识数
Vector DB Knowledge 数
缺失 embedding 的 Knowledge
多余 Vector
```

示例：

```text
MySQL normal knowledge: 1000
Vector indexed: 998
Missing: 2
Extra: 0
```

---

# 46. Embedding 数据不足时怎么办

如果当前 Vector DB：

```text
连接失败
```

正式导入：

> 不应该偷偷把所有数据当 NEW。

正确策略：

```text
Vector DB 不可用
↓
Dedup 无法可靠完成
↓
任务进入 FAILED / PARTIAL_SUCCESS
```

除非当前任务有非常明确的安全降级策略。

**不能因为向量库挂了就把重复知识大量写进 MySQL。**

---

# 47. MySQL 正常、Vector DB 故障

已有知识库仍然正常。

但是：

```text
新的 AI 导入
```

应该暂停在：

```text
DEDUPLICATING
```

或者：

```text
FAILED
```

并记录：

```text
Vector DB unavailable
```

---

# 48. Embedding 服务故障

如果：

```text
Embedding API
```

不可用：

不要继续：

```text
Candidate → NEW
```

避免大量重复数据。

---

# 49. LLM 去重服务故障

如果只有某个 Candidate：

```text
Embedding → ambiguous
↓
需要 LLM
↓
LLM 失败
```

则：

```text
该 Candidate = failed
```

继续其他 Candidate。

---

# 50. 结果状态模型

建议内部使用：

```text
CandidateProcessingResult
```

包含：

```text
candidate
decision
target_knowledge_id
status
error
```

例如：

```text
SUCCESS
FAILED
SKIPPED
```

---

# 51. 性能要求

必须统计：

```text
document parse time
chunk time
extract time
deduplicate time
save time
embedding time
vector search time
LLM deduplicate count
```

尤其需要：

```text
candidate_count
vector_search_count
llm_deduplicate_count
```

---

# 52. 目标

假设：

```text
100 candidates
```

不要出现：

```text
100 candidates
→ 100 LLM deduplicate calls
```

应该尽量：

```text
100 candidates
↓
100 embeddings
↓
Vector Search
↓
只有少量 ambiguous
↓
少量 LLM calls
```

---

# 53. 本批次内部去重性能

不要：

```text
100 candidates
×
100 candidates
```

做暴力两两比较。

如果已经使用 Embedding：

> 优先使用批量 Embedding + 相似搜索。

如果当前批量规模很小，可以接受简单比较，但代码不要设计成无法扩展。

---

# 54. Candidate 与 DB 的处理顺序

推荐：

```text
阶段 1：
整个 Candidate Batch 内部去重

阶段 2：
每个 Unique Candidate 与数据库比较

阶段 3：
得到最终决策

阶段 4：
批量 / 顺序落库
```

不要：

```text
Candidate1 → 立即写数据库
Candidate2 → 再查询数据库
Candidate3 → 再查询数据库
```

这样逻辑容易混乱。

---

# 55. 正式落库策略

建议：

```text
先完成一批去重决策
↓
得到：

NEW
DUPLICATE
MERGE
FAILED
↓
执行数据库操作
```

这样更容易统计结果。

---

# 56. Merge 顺序问题

一个批次中可能出现：

```text
Candidate A
Candidate B
```

它们都应该 MERGE 到：

```text
Knowledge X
```

处理时必须避免：

```text
A 更新 X
B 又基于旧版 X 更新
```

导致内容覆盖。

推荐：

```text
按目标 knowledge_id 分组
↓
合并多个 candidate
↓
一次 update
↓
重新 embedding
```

这是 MERGE 实现中非常重要的注意事项。

---

# 57. 新知识之间互相合并

例如：

```text
Candidate A
Candidate B
```

本批次判断：

```text
B DUPLICATE A
```

但 A 还没有数据库 ID。

此时：

```text
A
```

先成为本批次 canonical candidate。

最终：

```text
A → NEW → knowledge_id=1005

B → DUPLICATE → target=1005
```

不能让 B 变成一个孤立的“重复候选”。

---

# 58. Canonical Candidate

批次内部如果发生重复：

选择一个：

```text
canonical candidate
```

一般优先：

```text
信息更完整
内容更长但不是冗余
来源更清晰
```

不要简单依赖随机顺序。

第一版可以：

> 保留第一个合理候选作为 canonical，其余作为重复候选。

复杂质量比较后续再做。

---

# 59. 来源信息

最终保存的 Knowledge 应该尽量保留：

```text
来源文件
来源 Chunk
```

但是不要为了这个阶段大规模修改数据库。

如果当前结构还没有可靠的 source 字段：

> 先记录在 ImportTask 结果或日志中，并把正式来源追踪作为后续版本。

---

# 60. 本阶段暂时不加入 KnowledgeRelationAgent

当前：

```text
NEW
DUPLICATE
MERGE
```

完成以后：

> 先保存 Knowledge。

暂时不建立：

```text
knowledge_relation
```

下一阶段再处理知识关系。

---

# 61. 正式流程架构

本阶段完成后：

```text
                         ImportTask
                              │
                              ▼
                      DocumentParser
                              │
                              ▼
                         TextChunker
                              │
                              ▼
                    KnowledgeExtractAgent
                              │
                              ▼
                    KnowledgeCandidate[]
                              │
                              ▼
                    Batch Internal Dedup
                              │
                              ▼
                 Existing Knowledge Search
                              │
                              ▼
                 KnowledgeDeduplicatePipeline
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                   NEW    DUPLICATE    MERGE
                    │         │         │
                    └─────────┼─────────┘
                              ▼
                     KnowledgeService
                              │
                     ┌────────┴────────┐
                     ▼                 ▼
                  MySQL            Embedding
                                       │
                                       ▼
                                   Vector DB
```

---

# 62. MySQL 与 Vector DB 的关系

牢记：

```text
MySQL = 正式数据
Vector DB = 搜索索引
```

因此：

```text
创建 Knowledge
→ MySQL
→ Vector

更新 Knowledge
→ MySQL
→ Vector

禁用 Knowledge
→ MySQL
→ Vector delete/inactive
```

---

# 63. 代码分层

推荐：

```text
app/
├── services/
│   ├── knowledge_service.py
│   ├── import_task_service.py
│   ├── embedding_service.py
│   └── knowledge_import_service.py
│
├── repositories/
│   ├── knowledge_repository.py
│   └── import_task_repository.py
│
agent/
├── knowledge_extract/
└── knowledge_deduplicate/
```

不要把：

```text
ImportTask
Embedding
Deduplicate
Knowledge CRUD
```

全部塞入一个 Service。

---

# 64. KnowledgeImportService

推荐新增：

```text
KnowledgeImportService
```

它负责协调：

```text
ExtractAgent
DeduplicatePipeline
KnowledgeService
EmbeddingService
ImportTaskService
```

它属于：

> 业务流程编排层。

但它本身不负责 LLM 判断。

---

# 65. ImportTaskService

负责：

```text
创建任务
更新状态
更新进度
记录错误
完成任务
```

---

# 66. KnowledgeImportService

负责：

```text
读取 Task
↓
Parser
↓
Chunker
↓
ExtractAgent
↓
Candidate Dedup
↓
Database Dedup
↓
KnowledgeService
↓
EmbeddingSync
```

---

# 67. Agent 边界

```text
KnowledgeExtractAgent
= 从文本提取候选知识

KnowledgeDeduplicatePipeline
= 判断候选知识是否重复/合并

KnowledgeImportService
= 把整个流程串起来

KnowledgeService
= 真正保存 Knowledge
```

职责不要混在一起。

---

# 68. 测试 API

保留之前的：

```text
POST /api/v1/agent/knowledge-extract/test
```

以及 Deduplicate 测试 API。

它们用于：

```text
单独测试 Agent
```

不要因为正式 ImportTask 接入后就删除。

---

# 69. 正式 ImportTask 测试

至少准备：

```text
android_sample_1.pdf
android_sample_2.pdf
```

第一次：

```text
导入 android_sample_1.pdf
```

预期：

```text
大量 NEW
```

第二次：

```text
再次导入相同文件
```

预期：

```text
绝大多数 DUPLICATE
```

这一步非常重要。

---

# 70. 重复导入测试

同一个文件连续导入两次。

必须验证：

```text
第一次：
NEW > 0

第二次：
NEW 接近 0
DUPLICATE 很高
```

如果第二次还大量 NEW：

> 去重系统有问题，暂时不要进入下一阶段。

---

# 71. 部分相似文档

再准备一个：

```text
android_sample_update.pdf
```

内容：

```text
与旧文档部分重复
+
增加新知识
+
修改部分旧知识
```

预期：

```text
DUPLICATE
NEW
MERGE
```

三种结果都能够实际出现。

---

# 72. 测试数据库

继续使用：

```text
interview_agent_test
```

不要直接使用生产数据库测试 Agent 导入。

---

# 73. 自动化测试

至少：

```text
test_embedding_sync.py
test_candidate_dedup.py
test_import_knowledge.py
test_import_task_flow.py
```

测试：

```text
重复导入
新增导入
Merge
失败
Vector DB 不可用
Embedding 不可用
```

---

# 74. 回归测试

完成后必须：

```bash
python -m pytest tests/ -v
```

确保：

```text
Auth
Knowledge
Question
ImportTask
Dashboard
```

原功能都没有被破坏。

---

# 75. 性能测试

使用一个：

```text
25~100 个候选知识点
```

的测试文档。

记录：

```text
Parser
Extract
Dedup
Embedding
Vector Search
Save
Total
```

以及：

```text
候选数量
NEW
DUPLICATE
MERGE
LLM调用数
Embedding调用数
```

---

# 76. 关注 Token 成本

重点检查：

```text
100 个候选
```

是否变成：

```text
100 次 LLM Deduplicate
```

理想：

```text
100 embeddings
+
少量 LLM 判断
```

如果几乎所有候选都进入 LLM：

> 需要重新检查相似度阈值和规则层。

---

# 77. 失败恢复

如果：

```text
ExtractAgent
```

成功了一半后失败：

不能让任务数据完全丢失。

至少记录：

```text
当前阶段
错误
```

如果正式流程无法安全恢复：

```text
FAILED
```

等待人工重试。

不要默默重新跑整个流程导致数据重复。

---

# 78. 幂等性

本阶段必须保证：

```text
同一个 Candidate
重复处理
```

不会造成：

```text
同一个 Knowledge 多次插入
```

依靠：

```text
Exact Match
+
Vector Search
+
DeduplicatePipeline
+
数据库唯一约束
```

共同保证。

---

# 79. 数据库唯一约束

继续依赖现有：

```text
knowledge_relation
question_knowledge
```

等已有约束。

对于 `knowledge`：

> 不要简单增加 `name UNIQUE`。

因为：

```text
Java线程池
Java线程池机制
```

可能合法共存，不能用数据库字符串唯一性代替语义去重。

---

# 80. 不要为了这个阶段新增复杂的 Redis 缓存

当前：

```text
MySQL
+
Vector DB
```

足够。

不要增加：

```text
Redis
Celery
RabbitMQ
```

---

# 81. 不要修改前端

DSH 当前任务只修改：

```text
backend/
```

不要：

```text
admin-web/
```

---

# 82. 完成后的最终结果

本阶段完成后，管理员应该能完成：

```text
上传 Android 面试资料
        ↓
ImportTask
        ↓
AI 自动提取知识点
        ↓
自动判断已有知识
        ↓
重复的不创建
        ↓
需要合并的更新
        ↓
新的才创建
        ↓
Embedding 同步
        ↓
ImportTask SUCCESS
```

这就是第一个真正完整的 AI 业务链。

---

# 83. 最终验收标准

必须全部满足：

```text
[ ] 已有 Knowledge 能初始化 Embedding
[ ] Vector DB 中存在正常 Knowledge
[ ] Knowledge 新增能同步 Embedding
[ ] Knowledge 更新能重新 Embedding
[ ] Knowledge 禁用不会参与正常检索
[ ] ExtractAgent 能输出 Candidate
[ ] Candidate 能进行批次内部去重
[ ] Candidate 能检索已有 Knowledge
[ ] DeduplicatePipeline 能输出 NEW
[ ] DeduplicatePipeline 能输出 DUPLICATE
[ ] DeduplicatePipeline 能输出 MERGE
[ ] NEW 正确写入 MySQL
[ ] DUPLICATE 不重复创建
[ ] MERGE 正确更新已有 Knowledge
[ ] 更新后 Embedding 正确同步
[ ] ImportTask 状态正确
[ ] ImportTask 进度正确
[ ] ImportTask 能统计 NEW/DUPLICATE/MERGE
[ ] 单个 Candidate 失败不会导致全部失败
[ ] Vector DB 故障不会偷偷创建大量 NEW
[ ] 重复导入不会产生大量重复 Knowledge
[ ] 原有 pytest 全部通过
```

---

# 84. 最终开发顺序

严格按照：

```text
1. 阅读现有 KnowledgeExtractAgent
2. 阅读现有 KnowledgeDeduplicatePipeline
3. 检查当前 Vector DB 实现
4. 实现已有 Knowledge Embedding 回填
5. 实现 Embedding 一致性检查
6. 实现 Candidate Batch 内部去重
7. 实现数据库 Knowledge 检索
8. 正式串联 DeduplicatePipeline
9. 实现 NEW / DUPLICATE / MERGE 落库
10. 实现 Embedding 同步
11. 接入 ImportTask
12. 完成状态与进度
13. 完成统计
14. 测试失败恢复
15. 回归测试
16. 性能测试
17. 完成最终报告
```

---

# 85. 关于修改数据库的要求

如果现有数据库无法支持本阶段：

```text
candidate_count
new_count
duplicate_count
merge_count
failed_count
```

等必要信息：

可以通过 Alembic 增加最小字段。

但：

> 不允许重新设计整个数据库。

所有数据库修改必须：

```text
Model
↓
Alembic
↓
Migration
```

不能直接修改线上表结构。

---

# 86. 关于 Vector DB 选择

如果现有项目已经确定了 Vector DB：

> 直接复用现有实现。

如果尚未确定：

> 先检查当前代码和开发环境，再选择一种最轻量、可稳定运行的方案。

不要一次引入多个 Vector DB。

最终必须只有：

```text
一个 VectorRepository
+
一个实际 Vector DB
```

---

# 87. 最终交付报告

完成后必须告诉我：

## 1. 最终架构

## 2. 实际使用的 Vector DB

## 3. Embedding 模型

## 4. 新增文件

## 5. 修改文件

## 6. 数据库 Migration

## 7. ImportTask 流程

## 8. NEW / DUPLICATE / MERGE 流程

## 9. Embedding 同步机制

## 10. 测试结果

## 11. 重复导入结果

## 12. 性能数据

至少：

```text
候选数
NEW
DUPLICATE
MERGE
LLM调用数
Embedding调用数
总耗时
```

## 13. 已知问题

## 14. 尚未完成内容

## 15. 下一阶段建议

---

# 88. 最终硬性要求

不要伪造结果。

如果：

```text
Vector DB 没有真实运行
LLM 没有真实调用
测试没有实际执行
```

必须明确：

```text
未验证
```

不要写：

```text
测试通过
```

除非确实执行过。

---

# 89. 当前阶段不要开发第三个 Agent

本阶段完成后：

```text
KnowledgeExtractAgent
        ↓
KnowledgeDeduplicatePipeline
        ↓
KnowledgeService
        ↓
Knowledge
```

先稳定这个流程。

**不要在本阶段开发 KnowledgeRelationAgent。**

只有：

```text
上传文档
→ 提取
→ 去重
→ 入库
→ 重复导入稳定
```

全部通过之后，才进入下一个阶段：

```text
KnowledgeRelationAgent
```

---

# 90. 开始执行

现在直接在 backend 项目中执行：

```text
读取现有代码
↓
检查 ExtractAgent
↓
检查 DeduplicatePipeline
↓
检查 Vector DB
↓
完成 Knowledge Embedding 初始化
↓
整合 Candidate 内部去重
↓
整合数据库去重
↓
实现 NEW / DUPLICATE / MERGE
↓
正式接入 ImportTask
↓
运行测试
↓
运行重复导入测试
↓
性能测试
↓
修复问题
↓
最终报告
```

**只修改 backend，不修改 admin-web。**