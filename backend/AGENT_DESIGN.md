# KnowledgeExtractAgent V1.0 设计文档

## 一、项目概述

KnowledgeExtractAgent 是本项目的第一个 AI Agent，负责从面试/技术文档中自动提取结构化知识点。

**核心职责**：文件 → 解析 → 分块 → LLM 提取 → 结构化 JSON 结果

**重要约束**：当前阶段不会写入正式 `knowledge` 表，仅返回测试结果。

---

## 二、目录结构

```
backend/
├── agent/                              # Agent 模块（独立于 app 业务层）
│   ├── __init__.py
│   ├── common/                         # 公共模块
│   │   ├── __init__.py
│   │   ├── config.py                   # Agent 配置（LLM/分块/重试参数）
│   │   └── llm.py                      # LLM Provider 抽象（统一获取 ChatModel）
│   └── knowledge_extract/              # 知识点提取 Agent
│       ├── __init__.py
│       ├── chunker.py                  # 文本分块器（语义分块）
│       └── graph.py                    # LangGraph 工作流定义
│       ├── nodes.py                    # LangGraph 节点函数
│       ├── parser.py                   # 文档解析器（PDF/DOCX/TXT/MD）
│       ├── prompts.py                  # Prompt 定义（版本化管理）
│       ├── schemas.py                  # Pydantic 数据模型定义
│       ├── validator.py                # 提取结果校验器
│
├── app/api/v1/
│   └── agent.py                        # Agent 测试 API 端点
│
└── agent_tests/                        # Agent 测试
    ├── fixtures/                       # 测试数据
    │   └── android_sample.txt          # Android 面试知识点样本
    ├── __init__.py
    ├── test_chunker.py                 # 分块器测试（6 个用例）
    ├── test_parser.py                  # 解析器测试（5 个用例）
    └── test_schemas.py                 # Schema + Validator 测试（10 个用例）
```

---

## 三、文件功能说明

### 3.1 agent/common/config.py — Agent 配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LLM_PROVIDER` | `openai` | LLM 提供商标识 |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名称 |
| `LLM_API_KEY` | `""` | API 密钥（从 .env 读取） |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | API 基础地址 |
| `LLM_TEMPERATURE` | `0.1` | 温度参数（越低越确定） |
| `LLM_MAX_TOKENS` | `4096` | 最大输出 Token 数 |
| `CHUNK_SIZE` | `6000` | 每个 Chunk 目标字符数 |
| `CHUNK_OVERLAP` | `500` | 相邻 Chunk 重叠字符数 |
| `AGENT_MAX_RETRIES` | `2` | LLM 返回非法结构时最大重试次数 |

### 3.2 agent/common/llm.py — LLM Provider

- 提供 `get_llm()` 函数，返回 ChatOpenAI 实例（单例模式）
- 通过 `LLM_BASE_URL` 切换不同服务商（OpenAI、DeepSeek、智谱等）
- 切换模型只需修改 .env，无需改动 Agent 代码

### 3.3 agent/knowledge_extract/parser.py — 文档解析器

| 文件格式 | 解析策略 | 特殊处理 |
|----------|----------|----------|
| TXT | 按双换行符分割段落 | 自动检测编码（UTF-8/GBK） |
| MD | 按标题层级分割章节 | 保留 # ## ### 标题结构 |
| DOCX | 提取段落和标题样式 | 同时提取表格内容 |
| PDF | 逐页提取文本 | 检测扫描型 PDF 并报错 |

### 3.4 agent/knowledge_extract/chunker.py — 文本分块器

分块策略优先级：
1. **标题边界** — 优先按文档标题/章节切分
2. **段落边界** — 其次按段落（双换行符）切分
3. **句子边界** — 再次按句子切分（兜底策略）
4. **字符长度** — 最后按 chunk_size 强制切分

相邻 Chunk 之间有 overlap 重叠，保证上下文连续性。

### 3.5 agent/knowledge_extract/schemas.py — 数据模型

| 模型 | 用途 |
|------|------|
| `DocumentPage` | 文档的一个页面/章节 |
| `StructuredDocument` | 解析后的结构化文档 |
| `DocumentChunk` | 分块后的单个块 |
| `KnowledgeCandidate` | LLM 提取的单个知识点 |
| `KnowledgeExtractResult` | LLM 对单个 Chunk 的输出 |
| `ExtractRunResult` | 整个提取任务的最终结果 |

### 3.6 agent/knowledge_extract/prompts.py — Prompt 管理

- `KNOWLEDGE_EXTRACT_PROMPT_VERSION = "v1"` — 版本号
- `SYSTEM_PROMPT` — 系统提示词（身份、规则、约束）
- `USER_PROMPT_TEMPLATE` — 用户提示词模板
- `RETRY_PROMPT_TEMPLATE` — 重试提示词模板

### 3.7 agent/knowledge_extract/validator.py — 结果校验器

校验规则：
- name 非空，长度 ≤ 200
- summary 非空
- content 非空
- difficulty 必须为 1/2/3
- keywords 非空，1~15 个，不含空值
- source_chunk_id 非空

### 3.8 agent/knowledge_extract/nodes.py — LangGraph 节点

| 节点 | 类型 | 功能 |
|------|------|------|
| `parse_document_node` | Tool | 解析文档文件 |
| `chunk_document_node` | Tool | 文本分块 |
| `extract_current_chunk_node` | LLM Node | 调用 LLM 提取知识点 |
| `should_continue_node` | 条件边 | 判断是否还有更多 Chunk |
| `merge_results_node` | 合并 | 合并所有 Chunk 结果 |

### 3.9 agent/knowledge_extract/graph.py — LangGraph 工作流

```
START → parse_document → chunk_document → extract_current_chunk
        → should_continue?
            → YES: extract_current_chunk（循环）
            → NO: merge_results → END
```

### 3.10 app/api/v1/agent.py — 测试 API

```
POST /api/v1/agent/knowledge-extract/test
```
- 认证：需要 Bearer Token
- 参数：file（multipart/form-data）
- 返回：run_id, file_name, chunk_count, knowledge_count, knowledge_points[], errors[]
- **不写入正式 knowledge 表**

---

## 四、数据流

```
上传文件
  ↓
DocumentParser（解析为 StructuredDocument）
  ↓
TextChunker（切分为 DocumentChunk 列表）
  ↓
逐个 Chunk 调用 LLM（extract_current_chunk_node）
  ↓
KnowledgeValidator（校验提取结果）
  ↓
merge_results（合并所有 Chunk 结果）
  ↓
返回 ExtractRunResult（JSON）
```

---

## 五、新增依赖

```
langchain>=0.3.0           # LLM 编排框架
langchain-openai>=0.2.0    # OpenAI 兼容 API
langgraph>=0.2.0           # 工作流编排
pdfplumber>=0.11.0         # PDF 解析
python-docx>=1.1.0         # DOCX 解析
```

---

## 六、配置说明

在 `.env` 文件中添加以下配置：

```env
# LLM 配置
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4096

# 分块配置
CHUNK_SIZE=6000
CHUNK_OVERLAP=500

# Agent 配置
AGENT_MAX_RETRIES=2
```

---

## 七、测试结果

```
原有测试: 56 passed（无回归）
Parser:    5 passed
Chunker:   6 passed
Schema:   10 passed
总计:     77 passed, 0 failed
```

---

## 八、已知限制

1. 扫描型 PDF 不支持 OCR（明确返回错误）
2. 复杂 DOCX 表格解析有限
3. 未配置 LLM API Key 时无法执行提取
4. 当前串行处理 Chunk（不并行）

---

## 九、当前不能做的事情

- ❌ 自动写入 knowledge 表
- ❌ 接入正式 ImportTask
- ❌ 知识点去重
- ❌ 知识关系生成
- ❌ AI 题目生成

---

## 十、后续演进

```
第一阶段（当前）：Agent → JSON 结果
第二阶段：Agent → KnowledgeService → MySQL
第三阶段：+ KnowledgeDeduplicateAgent
第四阶段：+ KnowledgeRelationAgent
第五阶段：+ QuestionGenerateAgent
```
