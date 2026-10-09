# AI 面试题库系统
## KnowledgeDeduplicateAgent 第二阶段设计与开发文档 V1.0

> 本文用于指导 DeepSeek Harness（DSH）完成本项目第二阶段 AI 能力：
>
> **KnowledgeDeduplicateAgent（知识点去重/合并 Agent）**
>
> 当前阶段的核心目标：
>
> **判断新提取的知识点与现有知识点之间是否重复、应该合并，还是应该作为新的知识点保存。**
>
> 本阶段重点解决：
>
> - 知识点名称不同但语义相同
> - 知识点内容部分重合
> - AI 提取产生的重复知识点
> - 避免每个候选知识点都直接调用 LLM
> - 降低 Token 消耗
> - 保证知识库长期不会因为导入文档不断产生大量重复数据

---

# 1. 当前项目状态

当前项目已经完成：

```text
✅ FastAPI 后端
✅ MySQL
✅ SQLAlchemy
✅ Alembic
✅ JWT
✅ Vue3 管理后台
✅ 前后端联调
✅ KnowledgeExtractAgent
✅ DocumentParser
✅ TextChunker
✅ KnowledgeExtractAgent 独立测试
```

当前已经验证：

```text
文件
↓
解析
↓
Chunk
↓
KnowledgeExtractAgent
↓
结构化知识点
```

下一阶段开始处理：

```text
候选知识点
↓
判断是否已经存在相同/近似知识点
```

---

# 2. 本阶段核心目标

建立：

```text
KnowledgeDeduplicatePipeline
```

整体流程：

```text
候选知识点
    ↓
标准化
    ↓
精确匹配
    ↓
关键词/文本预检查
    ↓
Embedding
    ↓
Vector Search TopK
    ↓
相似度判断
    ↓
是否需要 LLM？
    ├── 不需要 → NEW
    ├── 高度相似 → DUPLICATE
    └── 中间区域 → DeduplicateAgent
                         ↓
                 DUPLICATE / MERGE / NEW
```

核心原则：

> **先检索，再判断；能用确定性逻辑解决的问题，不调用 LLM。**

---

# 3. 本阶段的三个最终决策

对每一个候选知识点：

```text
NEW
DUPLICATE
MERGE
```

## NEW

表示：

> 当前候选知识点与现有知识点没有足够高的语义重合，可以作为新的独立知识点。

---

## DUPLICATE

表示：

> 候选知识点与已有某个知识点本质上是同一个知识主题，没有必要创建新知识点。

结果应指向：

```text
existing_knowledge_id
```

---

## MERGE

表示：

> 候选知识点与已有知识点高度相关，但两者包含的信息具有互补性，直接丢弃候选内容会损失信息，因此需要合并。

例如：

```text
已有：
Java线程池

候选：
ThreadPoolExecutor核心参数与线程池工作机制
```

这类情况需要进一步判断：

```text
已有知识点是否需要更新内容？
候选信息是否应该合并进去？
最终名称/摘要/内容是什么？
```

注意：

> **MERGE 不应该简单地把两段文本字符串直接拼起来。**

应该由 Agent 输出明确的合并结果。

---

# 4. 本阶段明确不做

不要在本阶段开发：

```text
KnowledgeRelationAgent
QuestionDecisionAgent
QuestionGenerateAgent
QuestionEvaluateAgent
用户练习
错题
知识图谱复杂遍历
```

也不要加入：

```text
Redis
Celery
RabbitMQ
```

---

# 5. 一个重要原则：不要让每个候选知识点直接调用 LLM

错误方案：

```text
25 个候选知识点
↓
25 次 LLM
```

正确方案：

```text
25 个候选知识点
↓
先批量 / 本地规则预处理
↓
Embedding
↓
Vector Search
↓
只让“无法确定”的候选进入 LLM
```

例如：

```text
25 个候选
↓
20 个明显 NEW / DUPLICATE
↓
只剩 5 个需要 Agent 判断
```

这样能够大幅降低 Token 和延迟。

---

# 6. 去重整体架构

推荐：

```text
                    KnowledgeCandidate
                           │
                           ▼
                  NormalizeKnowledge
                           │
                 ┌─────────┴─────────┐
                 ▼                   ▼
          Exact Match          Keyword/Text Check
                 │                   │
                 └─────────┬─────────┘
                           ▼
                      Embedding
                           │
                           ▼
                     Vector Search
                           │
                           ▼
                       Top K
                           │
                 ┌─────────┼─────────┐
                 ▼         ▼         ▼
               LOW      MIDDLE      HIGH
                 │         │          │
                NEW      LLM?      DUPLICATE
                           │
                           ▼
                KnowledgeDeduplicateAgent
                           │
                    ┌──────┼──────┐
                    ▼      ▼      ▼
                   NEW   DUPLICATE MERGE
```

---

# 7. 数据源

输入来自：

```text
KnowledgeExtractAgent
```

输出：

```python
KnowledgeCandidate
```

候选知识点至少包含：

```text
name
summary
content
difficulty
keywords
source_chunk_id
source_title
source_page_start
source_page_end
```

不要修改现有 KnowledgeExtractAgent 输出结构，除非确有必要。

---

# 8. Knowledge 标准化

在 Embedding 之前增加：

```text
KnowledgeNormalizer
```

负责：

```text
去除多余空格
统一中英文标点
统一大小写策略
去掉明显无意义字符
清理重复关键词
```

例如：

```text
Java 线程池
Java线程池
java线程池
```

标准化后可以得到相近结果。

---

# 9. 不允许过度标准化

不要把：

```text
Java线程池
```

改成：

```text
线程池
```

也不要删除具有语义意义的信息。

标准化的目的是：

> 减少无意义的文本差异，而不是改变知识点语义。

---

# 10. 精确匹配

第一层：

```text
exact match
```

优先检查：

```text
normalized_name
```

例如：

```text
Java线程池
Java线程池
```

可以直接：

```text
DUPLICATE
```

无需 Embedding，更无需 LLM。

---

# 11. Text Similarity 预检查

第二层可以使用：

```text
关键词重合
名称文本相似度
```

只作为预筛选。

不能仅凭字符串相似度决定最终语义重复。

例如：

```text
Java线程池
Java线程安全
```

字符串很像，但不是同一个知识点。

---

# 12. Embedding

第三层：

```text
KnowledgeEmbeddingService
```

负责：

```text
KnowledgeCandidate
↓
Embedding
```

建议用于：

```text
name
+
summary
+
keywords
```

必要时加入部分：

```text
content
```

不要默认把超长 content 全部用于 Embedding。

推荐文本：

```text
name + summary + keywords
```

例如：

```text
Java线程池
|
Java线程池用于管理和复用线程...
|
ThreadPoolExecutor, 核心线程数, 最大线程数
```

这样通常比直接使用一大段内容更稳定，也更省计算。

---

# 13. Embedding 服务必须独立

建立：

```text
agent/common/embedding.py
```

提供：

```python
get_embedding_service()
```

统一封装：

```text
模型
API Key
Base URL
批量 embedding
```

不要在 Agent 里直接创建具体厂商 SDK。

---

# 14. Embedding 配置

从环境变量读取：

```text
EMBEDDING_MODEL
EMBEDDING_API_KEY
EMBEDDING_BASE_URL
EMBEDDING_DIMENSION
```

具体变量名可以根据现有配置规范调整。

禁止：

```python
api_key = "sk-xxx"
```

---

# 15. Vector DB 选择

当前项目优先：

> **不要为了向量检索立刻引入复杂独立服务。**

第一阶段可以选择一个与当前项目复杂度匹配的方案。

推荐优先评估：

```text
方案 A：MySQL 当前环境是否已有可用向量能力
方案 B：PostgreSQL + pgvector
方案 C：项目已有的向量服务
```

如果当前项目必须使用独立 Vector DB，再单独引入。

不要同时支持：

```text
Milvus
Qdrant
pgvector
```

多个实现。

本阶段只选一个。

---

# 16. Vector Repository

建立独立接口：

```text
VectorRepository
```

至少提供：

```python
search_similar(...)
upsert(...)
delete(...)
```

Agent 不应该直接调用具体 Vector DB SDK。

架构：

```text
DeduplicateService
    ↓
VectorRepository
    ↓
Vector DB
```

---

# 17. 为什么需要 Vector Repository

因为未来可能从：

```text
Qdrant
```

切换到：

```text
pgvector
```

不应该修改：

```text
KnowledgeDeduplicateAgent
```

只修改：

```text
VectorRepository
```

---

# 18. 向量检索输出

Top K：

```text
candidate knowledge
+
similarity score
```

例如：

```json
{
  "knowledge_id": 123,
  "name": "Java线程池",
  "similarity": 0.94
}
```

建议第一阶段：

```text
TOP_K = 3
```

之后根据实际效果再调整。

---

# 19. 相似度阈值不要直接拍死

必须将：

```text
DUPLICATE_THRESHOLD
MERGE_THRESHOLD
```

配置化。

例如可以先进行实验：

```text
HIGH_THRESHOLD
MIDDLE_THRESHOLD
LOW_THRESHOLD
```

不要在代码中大量出现：

```python
if score > 0.92:
```

---

# 20. 第一版建议使用三段区间

不要只有：

```text
相似
不相似
```

建议：

```text
低相似
中间区域
高相似
```

例如概念：

```text
LOW
MIDDLE
HIGH
```

具体数值必须通过真实数据测试后确定。

不要把示例阈值直接视为最终生产阈值。

---

# 21. 推荐判定逻辑

例如：

```text
score < LOW_THRESHOLD
        ↓
NEW
```

```text
LOW_THRESHOLD <= score < HIGH_THRESHOLD
        ↓
进入 LLM Agent 判断
```

```text
score >= HIGH_THRESHOLD
        ↓
优先判断为 DUPLICATE
```

但必须注意：

> **高相似度也不代表 100% 重复。**

例如：

```text
Java线程池
Java线程池核心参数
```

可能非常相似，但存在粒度差异。

因此如果实际测试发现误判较多，可以把高相似区域也交给 Agent。

---

# 22. 去重 Agent 的职责

`KnowledgeDeduplicateAgent` 只负责：

> 根据候选知识点和已有 Top K 相似知识点，判断两者属于 NEW、DUPLICATE 还是 MERGE。

输入：

```text
candidate
existing_candidates[]
similarity_scores[]
```

输出：

```text
decision
target_knowledge_id
reason
merged_knowledge
```

---

# 23. Agent 输入 Schema

建议：

```python
class DeduplicateInput(BaseModel):
    candidate: KnowledgeCandidate
    existing_knowledge: list[ExistingKnowledgeCandidate]
```

其中：

```python
class ExistingKnowledgeCandidate(BaseModel):
    id: int
    name: str
    summary: str
    content: str
    difficulty: int
    keywords: list[str]
    similarity: float
```

---

# 24. Agent 输出 Schema

```python
class DeduplicateDecision(BaseModel):
    decision: Literal["NEW", "DUPLICATE", "MERGE"]
    target_knowledge_id: int | None
    confidence: float
    reason: str
    merged_knowledge: MergedKnowledge | None
```

---

# 25. decision 规则

## NEW

```text
target_knowledge_id = null
merged_knowledge = null
```

---

## DUPLICATE

```text
target_knowledge_id != null
merged_knowledge = null
```

表示：

> 候选知识点可以被已有知识点覆盖。

---

## MERGE

```text
target_knowledge_id != null
merged_knowledge != null
```

表示：

> 已有知识点和候选知识点都包含有效内容，应该合并。

---

# 26. MERGE 的特殊要求

MERGE 最危险。

必须保证：

```text
不能凭空增加知识
不能丢失重要信息
不能改变原知识语义
```

merged_knowledge 至少包含：

```text
name
summary
content
difficulty
keywords
```

---

# 27. 为什么 MERGE 不能简单字符串拼接

错误：

```text
existing.content + candidate.content
```

容易产生：

```text
重复段落
顺序混乱
语义冲突
```

正确：

```text
Existing
+
Candidate
↓
LLM
↓
结构化合并
```

---

# 28. Agent Prompt 设计

System Prompt 必须告诉 Agent：

你是一个：

> 技术知识库去重与合并专家。

你的任务：

```text
1. 判断是否同一个知识主题
2. 判断知识粒度是否一致
3. 判断内容是否互补
4. 判断是否应该新增
5. 判断是否应该标记重复
6. 判断是否应该合并
```

---

# 29. 防止 Agent 过度合并

必须强调：

```text
相似不等于重复。
```

例如：

```text
Java线程池
Java线程安全
```

不能因为都包含：

```text
Java + 线程
```

就合并。

---

# 30. 粒度一致性

尤其关注：

```text
大知识点
小知识点
```

例如：

```text
Activity生命周期
Activity.onCreate回调
```

可能属于上下级关系，而不是重复。

这时：

```text
DUPLICATE
```

可能不是最佳答案。

当前阶段：

> 如果明显不是重复，也不确定应该建立关系，则优先 `NEW`。

知识关系由后续 `KnowledgeRelationAgent` 负责。

---

# 31. 不要让 DeduplicateAgent 负责知识图谱

例如：

```text
Activity生命周期
Activity.onCreate
```

如果判断它们存在：

```text
related
prerequisite
extension
```

不要在本 Agent 写入关系。

只负责：

```text
NEW / DUPLICATE / MERGE
```

---

# 32. 批量处理候选知识点

如果一个 ExtractAgent 产生：

```text
25 个候选知识点
```

不要简单：

```text
25 × 向量搜索
25 × LLM
```

可以：

```text
批量 Embedding
批量 Vector Search
```

然后只有中间区域进入 LLM。

---

# 33. Embedding 批量化

推荐：

```text
25 个候选
↓
一次批量 Embedding
↓
25 个 Vector
```

而不是：

```text
1 → embedding
2 → embedding
3 → embedding
```

这样可以减少网络往返。

---

# 34. LLM Deduplicate 批量化

第一版建议：

> 可以先保持一个候选知识点对应一次 Agent 判断，保证逻辑简单。

不要一开始就做：

```text
25 candidates
↓
一个超大 Prompt
```

原因：

```text
上下文变大
解析复杂
失败重试复杂
结果定位复杂
```

等单条逻辑稳定后，再考虑批量。

---

# 35. 去重工作流

建议 LangGraph：

```text
START
  ↓
normalize_candidates
  ↓
exact_match
  ↓
embedding
  ↓
vector_search
  ↓
rule_decision
  ↓
conditional
  ├── NEW → finalize
  ├── DUPLICATE → finalize
  └── AMBIGUOUS
          ↓
   KnowledgeDeduplicateAgent
          ↓
       finalize
          ↓
         END
```

---

# 36. rule_decision

这个节点不使用 LLM。

根据：

```text
exact match
similarity
```

判断：

```text
NEW
DUPLICATE
AMBIGUOUS
```

只有：

```text
AMBIGUOUS
```

进入 LLM。

---

# 37. 为什么叫 AMBIGUOUS

不要直接在 Rule 节点决定：

```text
MERGE
```

因为：

> MERGE 需要语义理解。

规则层只负责：

```text
明显不相似
明显重复
不确定
```

最终：

```text
AMBIGUOUS
→ Agent
```

---

# 38. 最终决策流程

```text
候选知识点
     ↓
Exact Match?
     ├── YES → DUPLICATE
     └── NO
           ↓
      Embedding Search
           ↓
       similarity
           ↓
    ┌──────┼───────┐
    ▼      ▼       ▼
   LOW   MIDDLE   HIGH
    │      │        │
   NEW   Agent    DUPLICATE*
           │
           ├── NEW
           ├── DUPLICATE
           └── MERGE
```

`HIGH → DUPLICATE` 只是默认策略。

如果测试发现高相似误判，应允许进入 Agent。

---

# 39. 数据库落库

本阶段经过验证以后才允许进入正式知识库。

建议：

```text
NEW
↓
KnowledgeService.create()

DUPLICATE
↓
不创建新知识点

MERGE
↓
KnowledgeService.update()
```

注意：

> Agent 本身不要直接操作数据库。

---

# 40. 正式流程

在独立测试验证通过以后：

```text
ImportTask
 ↓
DocumentParser
 ↓
TextChunker
 ↓
KnowledgeExtractAgent
 ↓
KnowledgeDeduplicatePipeline
 ↓
KnowledgeService
 ↓
MySQL
```

---

# 41. ImportTask 的结果统计

导入任务最终应该能够知道：

```text
候选知识点
新增
重复
合并
失败
```

例如：

```json
{
  "candidate_count": 25,
  "new_count": 12,
  "duplicate_count": 9,
  "merge_count": 4,
  "failed_count": 0
}
```

第一版可以先记录日志或返回结果。

如果现有 `knowledge_import_task` 结构无法保存这些信息：

> 先不要大改数据库。

优先通过现有任务扩展机制解决，确实需要再新增字段或结果表。

---

# 42. 不要重复建立向量记录

一个正式 Knowledge：

```text
knowledge_id = 1001
```

应该对应稳定的 embedding。

后续知识更新：

```text
content 更新
```

需要重新生成 embedding。

因此 Vector Repository 必须考虑：

```text
upsert
```

而不是每次导入重复插入。

---

# 43. Embedding 更新策略

建议：

```text
knowledge 创建
→ embedding

knowledge 更新
→ embedding 重新生成
```

如果知识被：

```text
DISABLED
```

可以删除或标记其向量。

具体实现取决于 Vector DB。

---

# 44. 来源信息保留

即使：

```text
candidate → DUPLICATE
```

也不要直接把来源完全丢弃。

后续知识库需要知道：

> 哪些文档曾经提到过这个知识点。

但是这一阶段暂时不要为了来源追踪设计复杂的多表结构。

可以先保留：

```text
source_import_task
source_chunk
```

扩展设计留待正式接入阶段确认。

---

# 45. 测试 API

第二阶段必须先提供独立测试接口：

```text
POST /api/v1/agent/knowledge-deduplicate/test
```

用途：

> 输入一个候选知识点 + 模拟现有知识点集合，测试 DeduplicateAgent 的判断结果。

不要一开始就依赖真实导入任务。

---

# 46. 测试输入示例

候选：

```json
{
  "name": "Java线程池",
  "summary": "线程池用于复用线程并管理任务执行",
  "content": "...",
  "difficulty": 2,
  "keywords": [
    "Java",
    "线程池",
    "ThreadPoolExecutor"
  ]
}
```

已有：

```json
[
  {
    "id": 1001,
    "name": "Java线程池",
    "summary": "Java线程池的概念和使用",
    "content": "...",
    "difficulty": 2,
    "keywords": [
      "Java",
      "线程池"
    ],
    "similarity": 0.96
  }
]
```

期望：

```text
DUPLICATE
```

---

# 47. 第二组测试

候选：

```text
Java线程池核心参数
```

已有：

```text
Java线程池
```

要求 Agent 判断：

> 不能仅根据相似度直接认定 DUPLICATE。

需要根据：

```text
知识粒度
内容覆盖范围
```

判断是否：

```text
NEW
MERGE
DUPLICATE
```

---

# 48. 第三组测试

候选：

```text
Android Handler 消息机制
```

已有：

```text
Java线程池
```

应该：

```text
NEW
```

---

# 49. MERGE 测试

构造两个内容互补的知识：

已有：

```text
Java线程池基础概念
```

候选：

```text
ThreadPoolExecutor核心参数与工作流程
```

检查：

```text
MERGE
```

并检查：

```text
merged_knowledge
```

是否：

```text
内容完整
没有明显重复
没有凭空扩展
关键词合理
```

---

# 50. 自动化测试

必须测试：

## Normalize

```text
空格
大小写
标点
重复关键词
```

## Exact Match

```text
完全相同
大小写不同
空格不同
```

## Similarity

至少准备：

```text
明显相同
高度相似
相关但不同
完全不同
```

## Agent

测试：

```text
NEW
DUPLICATE
MERGE
```

---

# 51. 不要要求 LLM 测试完全固定

对于 Agent：

不要求：

```text
每次都输出一模一样的 reason
```

只验证：

```text
decision ∈ {NEW,DUPLICATE,MERGE}
target_knowledge_id 合法
confidence 合法
MERGE 时 merged_knowledge 非空
DUPLICATE 时 target 非空
NEW 时 target 为空
```

---

# 52. 性能要求

必须统计：

```text
candidate_count
embedding_count
vector_search_count
llm_deduplicate_count
```

尤其关注：

```text
25 个候选
```

最终：

```text
多少进入 Embedding
多少进入 Vector Search
多少最终进入 LLM
```

目标：

> **绝大多数明显 NEW / DUPLICATE 不应该调用 LLM。**

---

# 53. 成本统计

尽可能记录：

```text
embedding_tokens
embedding_latency
llm_tokens
llm_latency
```

如果 API 无法提供 Token 使用量：

> 记录可获得的指标，不要伪造。

---

# 54. 阈值调优

第一版不要假设一个“神奇的正确阈值”。

应该准备一组人工标注测试数据：

```text
candidate
existing
人工判断
similarity
```

例如：

```text
A → A
DUPLICATE

A → A增强版
MERGE

A → B相关知识
NEW
```

通过测试集合调整：

```text
LOW_THRESHOLD
HIGH_THRESHOLD
```

---

# 55. 阈值不要写死

配置：

```text
DEDUP_LOW_THRESHOLD
DEDUP_HIGH_THRESHOLD
DEDUP_TOP_K
```

未来可以调整 `.env`。

---

# 56. 第一阶段不做复杂知识版本管理

MERGE 后如果：

```text
KnowledgeService.update()
```

暂时直接更新即可。

但是必须记录：

```text
是谁触发的
候选来自哪个导入任务
```

如果当前数据库没有字段：

> 暂时不要为版本系统大改数据库。

版本历史可以作为后续独立功能。

---

# 57. Agent 和 Service 边界

最终：

```text
KnowledgeDeduplicateAgent
       ↓
DeduplicateDecision
       ↓
KnowledgeDeduplicateService
       ↓
KnowledgeService
       ↓
Repository
       ↓
MySQL
```

Agent：

```text
负责判断
```

Service：

```text
负责业务执行
```

Repository：

```text
负责数据库
```

---

# 58. 不允许的设计

禁止：

```text
Agent → SQL
Agent → Session
Agent → Repository
```

Agent 不知道：

```text
MySQL
SQLAlchemy
```

---

# 59. 不允许的过度设计

当前不要：

```text
多个 Vector DB
复杂 RAG
Neo4j
多 Agent 协作框架
分布式锁
Redis
消息队列
微服务
```

保持：

```text
FastAPI
+
LangGraph
+
Embedding
+
一个 Vector Repository
+
MySQL
```

---

# 60. 开发顺序

严格：

```text
1. 阅读现有 KnowledgeExtractAgent

2. 设计 EmbeddingService

3. 选择一种 Vector DB

4. 实现 VectorRepository

5. 实现 KnowledgeNormalizer

6. 实现 Exact Match

7. 实现 Embedding

8. 实现 Vector Search

9. 实现 Rule Decision

10. 实现 KnowledgeDeduplicateAgent

11. 实现 LangGraph

12. 实现测试 API

13. 自动化测试

14. 性能测试

15. 人工测试

16. 验证通过后才接 ImportTask
```

---

# 61. 本阶段不要直接接正式 ImportTask

先完成：

```text
Candidate
↓
Deduplicate Pipeline
↓
Result
```

通过测试以后，再做：

```text
ImportTask
↓
ExtractAgent
↓
Dedup
↓
Save
```

---

# 62. 最终测试流程

测试：

```text
Android / Java 面试测试资料
        ↓
KnowledgeExtractAgent
        ↓
获得 20~30 个候选知识点
        ↓
KnowledgeDeduplicatePipeline
        ↓
输出：

NEW
DUPLICATE
MERGE
```

检查：

```text
新增数量
重复数量
合并数量
Agent调用数量
Embedding数量
总耗时
```

---

# 63. 本阶段完成标准

```text
[ ] Normalize 正常
[ ] Exact Match 正常
[ ] Embedding 正常
[ ] Vector Search 正常
[ ] TopK 正常
[ ] Rule Decision 正常
[ ] KnowledgeDeduplicateAgent 正常
[ ] NEW 正常
[ ] DUPLICATE 正常
[ ] MERGE 正常
[ ] 结构化输出正常
[ ] 单个候选失败不影响其他候选
[ ] 原有 KnowledgeExtractAgent 不受影响
[ ] 原有后端 pytest 通过
[ ] Deduplicate 测试通过
[ ] 性能指标正常
[ ] 尚未验证的部分明确标记
```

---

# 64. 第一阶段与正式接入的边界

当前：

```text
KnowledgeExtractAgent
        ↓
KnowledgeCandidate
        ↓
Deduplicate Test API
        ↓
JSON
```

验证完成以后：

```text
正式：

ImportTask
        ↓
KnowledgeExtractAgent
        ↓
KnowledgeCandidate
        ↓
DeduplicatePipeline
        ↓
KnowledgeService
        ↓
MySQL
```

---

# 65. 最终目标架构

目前：

```text
                   Document
                      ↓
             KnowledgeExtractAgent
                      ↓
              KnowledgeCandidate
                      ↓
             KnowledgeDeduplicate
                      ↓
                NEW / DUP / MERGE
```

下一阶段扩展：

```text
Knowledge
    ↓
KnowledgeRelationAgent
    ↓
knowledge_relation
```

最终：

```text
ImportTask
    ↓
DocumentParser
    ↓
TextChunker
    ↓
KnowledgeExtractAgent
    ↓
Embedding
    ↓
KnowledgeDeduplicateAgent
    ↓
KnowledgeRelationAgent
    ↓
Knowledge
    ↓
QuestionDecisionAgent
    ↓
QuestionGenerateAgent
    ↓
QuestionEvaluateAgent
    ↓
Question
```

---

# 66. 给 DSH 的最终开发要求

你是本项目后端 AI 工程师。

请：

1. 先读取现有后端代码。
2. 重点读取 KnowledgeExtractAgent。
3. 不破坏现有功能。
4. 不修改 Vue3 前端目录。
5. 当前先完成独立 Deduplicate Pipeline。
6. 先完成 Embedding + Vector Search。
7. 再完成 KnowledgeDeduplicateAgent。
8. 提供测试 API。
9. 提供自动化测试。
10. 做性能测试。
11. **暂时不要接入正式 ImportTask。**
12. 验证完成后再给出后续接入方案。

---

# 67. 最终报告要求

最终报告必须包含：

```text
1. 架构设计
2. 新增文件
3. 新增依赖
4. Embedding 方案
5. Vector DB 方案
6. 相似度阈值方案
7. Rule Decision
8. Agent Prompt
9. LangGraph Workflow
10. 测试 API
11. 自动化测试
12. 性能结果
13. LLM 调用数量
14. Embedding 调用数量
15. 已知问题
16. 尚未完成内容
17. 后续正式接入 ImportTask 的方案
```

如果某项没有真实验证：

```text
必须写“未验证”。
```

不要伪造测试通过。

---

# 68. 开始执行

现在开始：

```text
读取现有项目
↓
实现 Normalizer
↓
实现 Embedding
↓
实现 Vector Repository
↓
实现相似度检索
↓
实现 Rule Decision
↓
实现 KnowledgeDeduplicateAgent
↓
实现 LangGraph
↓
实现测试 API
↓
测试
↓
性能分析
↓
修复
↓
最终报告
```

**当前阶段不要把 DeduplicatePipeline 接入正式 ImportTask。**