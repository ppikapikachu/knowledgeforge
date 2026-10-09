# KnowledgeDeduplicateAgent V1.0 设计文档

## 一、项目概述

KnowledgeDeduplicateAgent 负责判断新提取的知识点与现有知识点之间是否重复、应该合并，还是应该作为新的知识点保存。

**核心原则**：先检索，再判断；能用确定性逻辑解决的问题，不调用 LLM。

**三个最终决策**：
- `NEW` — 新知识点，可独立保存
- `DUPLICATE` — 重复，不创建新记录
- `MERGE` — 需要合并，由 LLM 生成合并后内容

---

## 二、目录结构

```
backend/
├── agent/
│   ├── common/
│   │   ├── config.py           # 新增 Embedding + 去重阈值配置
│   │   ├── embedding.py        # 新增 Embedding 服务（文本→向量）
│   │   └── vector_store.py     # 新增 向量存储（FAISS 内存实现）
│   │
│   └── knowledge_deduplicate/  # 新增 去重模块
│       ├── __init__.py
│       ├── schemas.py          # Pydantic 数据模型
│       ├── normalizer.py       # 知识点标准化器
│       ├── prompts.py          # LLM Prompt 定义
│       ├── nodes.py            # LangGraph 节点函数
│       └── graph.py            # LangGraph 工作流定义
│
├── app/api/v1/
│   └── agent_dedup.py          # 新增 去重测试 API
│
└── agent_tests/                # 新增 去重测试
    └── test_dedup.py
```

---

## 三、文件功能说明

### 3.1 agent/common/embedding.py — Embedding 服务

| 功能 | 说明 |
|------|------|
| `EmbeddingService` | 封装 OpenAI 兼容的 Embedding API |
| `embed_text()` | 单条文本→向量 |
| `embed_texts()` | 批量文本→向量（减少网络往返） |
| `get_embedding_service()` | 获取单例 |

### 3.2 agent/common/vector_store.py — 向量存储

| 功能 | 说明 |
|------|------|
| `VectorRepository` | 抽象接口（Protocol） |
| `FaissVectorStore` | FAISS 内存实现 |
| `upsert()` | 插入/更新向量 |
| `search()` | cosine 相似度检索 TopK |
| `delete()` | 删除向量记录 |

**为什么用抽象接口**：未来可切换到 pgvector、Qdrant，只需新增实现类。

### 3.3 agent/knowledge_deduplicate/normalizer.py — 标准化器

| 方法 | 功能 |
|------|------|
| `normalize_name()` | 去空格、统一标点、转小写 |
| `normalize_summary()` | 同上 |
| `normalize_keywords()` | 去重、标准化 |
| `build_embedding_text()` | 拼接 name+summary+keywords 用于 Embedding |

**注意**：不改变语义，只减少无意义差异。

### 3.4 agent/knowledge_deduplicate/nodes.py — 工作流节点

| 节点 | 类型 | 功能 |
|------|------|------|
| `normalize_node` | Tool | 标准化候选知识点 |
| `exact_match_node` | Tool | 精确名称匹配 |
| `embedding_node` | Tool | 向量嵌入 |
| `vector_search_node` | Tool | 向量检索相似知识点 |
| `rule_decision_node` | Rule | 规则判定（不调 LLM） |
| `llm_decision_node` | LLM | 仅 AMBIGUOUS 时调用 |
| `finalize_node` | Merge | 整理最终结果 |

### 3.5 agent/knowledge_deduplicate/graph.py — LangGraph 工作流

```
START → normalize → exact_match → embedding → vector_search
  → rule_decision
    → NEW/DUPLICATE → finalize
    → AMBIGUOUS → llm_decision → finalize
                              → END
```

### 3.6 agent/knowledge_deduplicate/prompts.py — Prompt 管理

- `DEDUP_PROMPT_VERSION = "v1"`
- `DEDUP_SYSTEM_PROMPT` — 系统提示词（身份、判断规则、防过度合并）
- `DEDUP_USER_PROMPT_TEMPLATE` — 用户提示词模板
- `EXISTING_KNOWLEDGE_TEMPLATE` — 已有知识点格式模板

### 3.7 app/api/v1/agent_dedup.py — 测试 API

```
POST /api/v1/agent/knowledge-deduplicate/test
```
- 认证：需要 Bearer Token
- 参数：candidates[] + existing_knowledge[]
- 返回：total_candidates, new_count, duplicate_count, merge_count, llm_call_count, results[]

---

## 四、判定流程

```
候选知识点
    ↓
标准化（去空格、统一标点、转小写）
    ↓
精确匹配？→ YES → DUPLICATE（无需 Embedding/LLM）
    ↓ NO
批量 Embedding（name+summary+keywords）
    ↓
向量检索 TopK 相似知识点
    ↓
规则判定：
  相似度 < LOW_THRESHOLD (0.60) → NEW
  相似度 >= HIGH_THRESHOLD (0.88) → DUPLICATE
  中间区域 → AMBIGUOUS → LLM Agent
    ↓
LLM 判断：NEW / DUPLICATE / MERGE
```

---

## 五、配置说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding 模型 |
| `EMBEDDING_API_KEY` | - | API 密钥 |
| `EMBEDDING_BASE_URL` | `https://api.openai.com/v1` | API 地址 |
| `EMBEDDING_DIMENSION` | `1536` | 向量维度 |
| `DEDUP_LOW_THRESHOLD` | `0.60` | 低于此值→NEW |
| `DEDUP_HIGH_THRESHOLD` | `0.88` | 高于此值→DUPLICATE |
| `DEDUP_TOP_K` | `3` | 向量检索返回数量 |

---

## 六、新增依赖

```
faiss-cpu>=1.7.0    # 向量检索引擎
numpy>=1.24.0       # 数值计算
openai>=1.0.0       # Embedding API 客户端
```

---

## 七、测试结果

```
原有测试: 77 passed（无回归）
```

**未验证**：Embedding + 向量检索 + LLM 去重判定（需要配置真实的 Embedding API Key）。

---

## 八、已知限制

1. FAISS 为内存实现，重启后向量数据丢失
2. FAISS 不支持真正的原地更新（upsert 会追加新记录）
3. 未接入正式 ImportTask
4. 未接入正式 knowledge 表写入

---

## 九、当前不能做的事情

- ❌ 自动写入 knowledge 表
- ❌ 接入正式 ImportTask
- ❌ 知识关系生成
- ❌ AI 题目生成

---

## 十、后续演进

```
第一阶段（当前）：Candidate → Dedup Pipeline → NEW/DUPLICATE/MERGE
第二阶段：接入 ImportTask → ExtractAgent → Dedup → KnowledgeService → MySQL
第三阶段：KnowledgeRelationAgent
第四阶段：QuestionGenerateAgent
```
