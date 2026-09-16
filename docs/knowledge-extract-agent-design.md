# AI 面试题库系统
## KnowledgeExtractAgent 第一阶段设计与开发文档 V1.0

> 本文用于指导 开发本项目第一个 AI Agent：
>
> **KnowledgeExtractAgent（知识点提取 Agent）**
>
> 当前阶段的目标不是完成整个 AI 导入系统，而是：
>
> **独立实现 → 独立测试 → 评估提取结果 → 修正 → 验证稳定 → 最后再接入正式 ImportTask。**
>
> 当前阶段禁止让该 Agent 自动修改正式知识库。

---

# 1. 当前项目阶段

当前项目已经完成：

```text
Vue3 管理后台
FastAPI 后端
MySQL
SQLAlchemy
Alembic
JWT
知识点管理
知识关系管理
题目管理
导入任务管理
Dashboard
前后端联调
```

现有 Web 功能已经能够正常使用。

因此：

> 不要破坏当前 V1.0 已经正常运行的功能。

本阶段只增加：

```text
KnowledgeExtractAgent
```

用于验证：

> 能否从 PDF / DOCX / TXT / MD 等面试资料中，自动提取结构化知识点。

---

# 2. 本阶段目标

实现一个独立的知识点提取 Workflow：

```text
输入文件
  ↓
DocumentParser
  ↓
StructuredDocument
  ↓
TextChunker
  ↓
TextChunk[]
  ↓
KnowledgeExtractAgent
  ↓
KnowledgeCandidate[]
  ↓
KnowledgeValidator
  ↓
ExtractResult
```

最终能够实现：

```text
Android面试题.pdf
        ↓
解析文本
        ↓
切分文本
        ↓
LLM理解
        ↓
提取知识点
        ↓
输出结构化 JSON
```

---

# 3. 非目标

当前阶段明确不实现：

```text
知识点去重
知识点合并
知识点向量搜索
知识图谱
知识关系生成
AI题目生成
AI题目评价
用户练习
Redis
Celery
RabbitMQ
Milvus
Qdrant
Neo4j
RAG
```

尤其是：

> **当前阶段不将提取出来的知识点自动写入正式 knowledge 表。**

---

# 4. 第一阶段的核心原则

必须遵守：

```text
解析 ≠ Agent
分块 ≠ Agent
校验 ≠ Agent
保存 ≠ Agent
```

真正需要 LLM 的部分：

```text
“理解文本，并识别其中有哪些独立知识点”
```

才是：

```text
KnowledgeExtractAgent
```

---

# 5. 文件解析是否属于 Agent？

答案：

> 可以属于 Agent Workflow，但不是 LLM Agent。

推荐最终架构：

```text
LangGraph Workflow

START
  ↓
parse_document
  ↓
chunk_document
  ↓
extract_knowledge
  ↓
validate_result
  ↓
END
```

其中：

```text
parse_document
```

是普通 Service / Tool。

```text
chunk_document
```

是普通 Service / Tool。

```text
extract_knowledge
```

才是真正的 Agent / LLM Node。

因此：

> **从系统功能上，它们属于“知识提取 Agent Workflow”；从技术实现上，只有知识提取节点是真正的 LLM Agent。**

---

# 6. 为什么必须把解析和 Agent 分开

因为：

```text
PDF → 文本
```

属于确定性问题。

而：

```text
文本 → 知识点
```

属于语义理解问题。

例如：

```text
Activity 是 Android 四大组件之一。
Activity 具有完整生命周期，包括 onCreate、
onStart、onResume、onPause、onStop、onDestroy。
```

程序只能比较容易得到：

```text
若干段文本
```

但它不能可靠判断：

```text
Activity

Activity生命周期

Activity生命周期回调方法
```

这些不同层级的知识边界。

这个工作交给 LLM。

---

# 7. 第一阶段技术栈

使用：

```text
Python
FastAPI
LangChain
LangGraph
Pydantic
SQLAlchemy
MySQL
```

当前不需要：

```text
Redis
Celery
Vector DB
Neo4j
```

---

# 8. Agent 目录

在现有 backend 中增加：

```text
backend/
├── app/
│
├── agent/
│   ├── __init__.py
│   │
│   ├── knowledge_extract/
│   │   ├── __init__.py
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── nodes.py
│   │   ├── prompts.py
│   │   ├── schemas.py
│   │   ├── parser.py
│   │   ├── chunker.py
│   │   └── validator.py
│   │
│   └── common/
│       ├── llm.py
│       └── config.py
│
├── ...
```

不要把 Agent 代码散落到：

```text
services/
api/
repositories/
```

Agent 应该独立出来。

---

# 9. Agent 与业务 Service 的边界

最终结构：

```text
Agent
  ↓
Tool / Service
  ↓
Repository
  ↓
MySQL
```

而当前阶段：

```text
Agent
  ↓
ExtractResult
```

暂时不要：

```text
Agent
  ↓
knowledge_service.create()
  ↓
MySQL
```

因为现在要先验证 Agent。

---

# 10. 第一阶段不写数据库

这是硬性要求。

KnowledgeExtractAgent 当前运行：

```text
文件
 ↓
Agent
 ↓
JSON结果
```

不要：

```text
Agent
 ↓
INSERT knowledge
```

这样我们可以非常方便地反复调整：

```text
Prompt
模型
chunk大小
输出格式
temperature
```

而不用不断删除错误知识点。

---

# 11. DocumentParser

建立：

```text
agent/knowledge_extract/parser.py
```

负责：

```text
PDF
DOCX
TXT
MD
```

解析为统一结构。

建议：

```python
class DocumentParser:
    def parse(file_path) -> StructuredDocument:
        ...
```

---

# 12. StructuredDocument

定义：

```python
class StructuredDocument(BaseModel):
    file_name: str
    file_type: str
    pages: list[DocumentPage]
    full_text: str
```

其中：

```python
class DocumentPage(BaseModel):
    page_number: int | None
    title: str | None
    text: str
```

注意：

TXT / MD 没有真实 page_number 时：

```text
page_number = null
```

不要伪造页码。

---

# 13. PDF 解析

第一阶段使用普通 PDF 文本解析库。

目标：

```text
PDF
 ↓
文本
```

如果 PDF 是普通文字型 PDF：

```text
正常解析
```

如果发现是扫描图片 PDF：

```text
当前阶段返回：

UNSUPPORTED_SCANNED_PDF
```

不要偷偷进行 OCR。

OCR 可以放到后续版本。

---

# 14. DOCX 解析

DOCX：

```text
Paragraph
Heading
Table
```

第一阶段至少提取：

```text
paragraph
heading
```

如果表格内容容易可靠解析，可以一起提取。

不要为了支持复杂 Word 排版而过度开发。

---

# 15. TXT

直接读取：

```text
UTF-8
```

如果 UTF-8 失败，可以尝试常见中文编码。

必须避免：

```text
解析乱码
```

---

# 16. Markdown

Markdown：

```text
标题
二级标题
正文
列表
代码块
```

第一阶段至少保留：

```text
标题层级
正文
```

不要简单删除所有 Markdown 结构。

因为：

```text
# Activity

## Activity生命周期

### onCreate
```

这些标题对于知识点提取非常重要。

---

# 17. DocumentParser 输出

例如：

```json
{
  "file_name": "android-interview.md",
  "file_type": "md",
  "pages": [
    {
      "page_number": null,
      "title": "Activity生命周期",
      "text": "Activity具有完整生命周期..."
    }
  ],
  "full_text": "..."
}
```

---

# 18. TextChunker

建立：

```text
agent/knowledge_extract/chunker.py
```

负责：

```text
StructuredDocument
        ↓
Chunk[]
```

---

# 19. 为什么需要 Chunk

不能把 1000 页 PDF：

```text
一次性发送给 LLM
```

必须：

```text
文本
 ↓
Chunk 1
Chunk 2
Chunk 3
...
```

否则：

```text
Token过大
成本高
上下文超限
理解质量下降
```

---

# 20. Chunk 设计目标

第一版建议：

```text
chunk_size
chunk_overlap
```

可配置。

例如：

```text
chunk_size = 5000~8000 中文字符
chunk_overlap = 500~800
```

具体值不要硬编码在业务逻辑里。

放配置。

---

# 21. 优先按语义边界分块

不能简单：

```python
text[i:i+5000]
```

优先：

```text
文档标题
↓
章节
↓
段落
↓
必要时才按长度切分
```

例如：

```text
# Activity

内容...

## Activity生命周期

内容...

## onCreate

内容...
```

优先保持完整章节。

---

# 22. Chunk Schema

```python
class DocumentChunk(BaseModel):
    chunk_id: str
    text: str
    title: str | None
    page_start: int | None
    page_end: int | None
    char_start: int
    char_end: int
```

---

# 23. 为什么必须保存来源位置

以后管理员发现：

> 这个知识点是怎么来的？

需要能够追溯：

```text
Knowledge
 ↓
Source Chunk
 ↓
原始文件
```

因此每个 Chunk 必须有：

```text
chunk_id
file_name
page
title
```

---

# 24. KnowledgeExtractAgent

真正的 Agent：

```text
KnowledgeExtractAgent
```

职责只有一个：

> **从一个文本 Chunk 中提取结构化知识点候选。**

不要让它：

```text
去重
存数据库
建立关系
生成题目
```

---

# 25. Agent 输入

输入：

```python
class KnowledgeExtractInput(BaseModel):
    chunk_id: str
    text: str
    title: str | None
    source_file: str
    page_start: int | None
    page_end: int | None
```

---

# 26. Agent 输出

```python
class KnowledgeCandidate(BaseModel):
    name: str
    summary: str
    content: str
    difficulty: int
    keywords: list[str]
    source_chunk_id: str
    source_title: str | None
    source_page_start: int | None
    source_page_end: int | None
```

多个：

```python
class KnowledgeExtractResult(BaseModel):
    chunk_id: str
    knowledge_points: list[KnowledgeCandidate]
```

---

# 27. name 规则

name 必须：

```text
短
明确
可以独立理解
```

例如：

```text
Activity生命周期
Java线程池
ThreadLocal
Handler消息机制
Android ANR
```

不要：

```text
Activity是Android四大组件之一并且具有生命周期
```

这种应该属于：

```text
summary / content
```

---

# 28. summary 规则

用于管理员快速查看。

应该：

```text
1~3句话
```

解释：

> 这个知识点是什么。

---

# 29. content 规则

必须基于原始文本整理。

可以：

```text
总结
结构化
去除重复表达
```

但是禁止：

```text
凭空补充
虚构原文不存在的知识
```

---

# 30. difficulty

统一：

```text
1 = 简单
2 = 中等
3 = 困难
```

LLM 根据内容判断。

但是必须要求：

> 没有明显依据时默认使用 2。

不要输出：

```text
0
4
5
```

---

# 31. keywords

提取：

```text
3~8 个
```

例如：

```json
[
  "Activity",
  "生命周期",
  "onCreate",
  "onStart",
  "onResume"
]
```

不要输出整句话。

---

# 32. 知识点粒度要求

这是 Agent Prompt 最重要的部分之一。

要求：

> 一个 Knowledge Candidate 应该代表一个相对独立、可学习、可出题的知识主题。

不要过粗：

```text
Android
```

不要过细：

```text
onCreate
```

除非文本明确在讲：

> onCreate 回调方法本身。

理想：

```text
Activity生命周期
```

---

# 33. 不要强制每个 Chunk 输出固定数量

禁止：

```text
每个 Chunk 必须生成 5 个知识点
```

应该：

```text
没有知识点 → []
一个核心主题 → 1
多个独立主题 → 多个
```

这样可以避免为了数量而生成垃圾知识点。

---

# 34. 允许输出空数组

例如一个 Chunk 只是：

```text
目录
版权声明
页眉
页脚
```

Agent 必须可以：

```json
{
  "knowledge_points": []
}
```

---

# 35. 防止幻觉

Prompt 必须明确：

```text
只能基于输入文本提取知识点。

不得使用输入文本之外的知识补充不存在的内容。

如果文本信息不足，不要自行扩展。
```

这是第一 Agent 最重要的约束之一。

---

# 36. 知识点必须能够追溯原文

每个：

```text
KnowledgeCandidate
```

必须记录：

```text
source_chunk_id
source_title
source_page_start
source_page_end
```

以后管理员可以追溯来源。

---

# 37. Prompt 结构

Prompt 建议：

```text
System Prompt
+
Structured Output Schema
+
Chunk Text
```

System Prompt 负责：

```text
身份
任务
知识点定义
粒度规则
禁止事项
输出要求
```

User Prompt：

```text
文件标题
章节标题
Chunk
```

---

# 38. LLM 输出必须结构化

不要接受：

```text
以下是知识点：

1. Activity
2. Activity生命周期
...
```

要求：

```text
Structured Output
```

解析成：

```python
KnowledgeExtractResult
```

如果模型返回非法结构：

```text
Validation
 ↓
Retry
```

---

# 39. Retry

第一版允许：

```text
最多 2 次
```

例如：

```text
LLM
 ↓
Pydantic validation failed
 ↓
重新请求
```

但是不要无限 retry。

---

# 40. Token 控制

不要发送：

```text
整个文件
```

只发送：

```text
当前 Chunk
```

并且：

```text
chunk_size
```

配置化。

---

# 41. 并发策略

第一版：

> 默认串行处理 Chunk。

即：

```text
Chunk 1
 ↓
LLM
 ↓
Chunk 2
 ↓
LLM
```

不要第一版直接做几十个并发请求。

原因：

```text
容易触发限流
成本不可控
调试困难
```

稳定后再增加并发。

---

# 42. Agent State

LangGraph State 建议：

```python
class KnowledgeExtractState(TypedDict):
    file_path: str
    file_name: str
    document: StructuredDocument | None
    chunks: list[DocumentChunk]
    current_chunk_index: int
    results: list[KnowledgeExtractResult]
    errors: list[str]
```

第一阶段不需要：

```text
knowledge_list
question_list
graph
vector_results
```

保持简单。

---

# 43. LangGraph Workflow

第一版：

```text
START
  ↓
parse_document
  ↓
chunk_document
  ↓
extract_current_chunk
  ↓
validate_current_result
  ↓
more_chunks?
  ├── YES → extract_current_chunk
  └── NO
       ↓
     merge_results
       ↓
      END
```

---

# 44. 为什么这里使用 LangGraph

因为后面一定会扩展：

```text
DocumentParse
 ↓
KnowledgeExtract
 ↓
KnowledgeDeduplicate
 ↓
KnowledgeRelation
 ↓
QuestionDecision
 ↓
QuestionGenerate
 ↓
QuestionEvaluate
```

所以现在直接使用 LangGraph，可以让后面自然扩展。

但是：

> **第一版 Graph 仍然要保持简单。**

不要因为使用 LangGraph 就把整个项目搞复杂。

---

# 45. Extract 节点

`extract_current_chunk`：

```text
获取当前 Chunk
 ↓
调用 LLM
 ↓
结构化输出
 ↓
保存到 State.results
```

注意：

这个 Node 不负责 MySQL。

---

# 46. Validate 节点

验证：

```text
name 非空
summary 合法
content 非空
difficulty ∈ [1,3]
keywords 数量合理
source_chunk_id 正确
```

错误：

```text
记录 errors
```

不要直接让整个任务崩溃。

---

# 47. 单个 Chunk 失败

例如：

```text
Chunk 17
LLM调用失败
```

不能让：

```text
Chunk 1~16
```

全部丢失。

应该：

```text
Chunk 17
→ error

继续

Chunk 18
→ 正常
```

最终：

```text
partial success
```

---

# 48. Agent Run 日志

虽然第一版不建立数据库 Agent 表，但至少要记录日志：

```text
run_id
chunk_id
start_time
duration
model
input_tokens
output_tokens
error
```

如果 LLM SDK 能提供 Token Usage：

必须保存到日志。

---

# 49. 为什么现在记录 Token

因为以后你非常关注：

> Agent 每处理一本 Android 面试题 PDF 到底花多少 Token？

第一阶段就应该开始观察：

```text
一个 Chunk
→ 输入 Token
→ 输出 Token
→ 成本
→ 时间
```

---

# 50. Agent 测试接口

当前不能自动接入正式 ImportTask。

应该新增一个**开发测试接口**。

例如：

```text
POST /api/v1/agent/knowledge-extract/test
```

权限：

```text
管理员
```

用途：

> 上传一个测试文件，运行 KnowledgeExtractAgent，直接查看提取结果。

注意：

这个 API：

**不能写入正式 knowledge 表。**

---

# 51. 测试接口返回

例如：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "run_id": "xxx",
    "file_name": "android.txt",
    "chunk_count": 10,
    "knowledge_count": 26,
    "knowledge_points": [
      {
        "name": "Activity生命周期",
        "summary": "...",
        "content": "...",
        "difficulty": 2,
        "keywords": [
          "Activity",
          "生命周期"
        ],
        "source_chunk_id": "chunk_001",
        "source_title": "Activity",
        "source_page_start": 10,
        "source_page_end": 12
      }
    ],
    "errors": []
  }
}
```

---

# 52. 不要把测试结果保存到 knowledge

开发测试接口：

```text
上传
 ↓
Agent
 ↓
返回 JSON
```

不：

```text
Agent
 ↓
MySQL knowledge
```

---

# 53. 测试文件目录

增加：

```text
backend/
└── agent_tests/
    └── fixtures/
```

可以放：

```text
android_sample.txt
android_sample.md
```

第一阶段建议准备一个：

```text
20~50KB
```

左右的人工测试文本。

内容最好包含：

```text
多个明显知识点
多个容易混淆知识点
一些非知识内容
重复内容
章节标题
```

---

# 54. 自动化测试

至少测试：

## parser

```text
TXT
MD
DOCX
PDF
```

## chunker

测试：

```text
短文本
长文本
标题
超长段落
空文档
```

## schema

测试：

```text
正常 JSON
非法 difficulty
空 name
非法 keywords
```

## Agent

可以使用一个固定测试文本。

重点不是测试：

> LLM 每次一定返回完全相同结果。

而是测试：

```text
输出结构合法
字段完整
来源正确
difficulty 合法
没有异常
```

---

# 55. LLM 测试的原则

不要要求：

```text
LLM 输出必须完全等于固定 JSON 内容
```

因为模型本身存在一定随机性。

应该验证：

```text
schema
范围
必要字段
来源关系
知识点数量合理
```

---

# 56. Agent 提取质量人工测试

除了自动化测试，还必须提供：

```text
人工评估流程
```

测试一个真实 Android 面试资料。

检查：

### 1. 有没有漏掉明显知识点

### 2. 有没有生成垃圾知识点

### 3. 知识点粒度是否合适

### 4. 是否出现幻觉

### 5. summary 是否准确

### 6. content 是否忠于原文

### 7. difficulty 是否基本合理

---

# 57. 第一版不要做自动质量评分

不要第一阶段再加入：

```text
QuestionEvaluateAgent
KnowledgeEvaluateAgent
```

人工观察即可。

因为我们现在首先要回答：

> **KnowledgeExtractAgent 到底能不能稳定提取知识点？**

---

# 58. Prompt 版本化

Prompt 不要直接散落在 Python 代码里。

建立：

```text
agent/knowledge_extract/prompts.py
```

或者：

```text
agent/knowledge_extract/prompts/
    extract_system.txt
    extract_user.txt
```

至少保留：

```text
KNOWLEDGE_EXTRACT_PROMPT_VERSION = "v1"
```

---

# 59. 为什么需要 Prompt Version

以后你调整：

```text
v1
 ↓
v2
 ↓
v3
```

才能知道：

> 哪个 Prompt 生成的数据。

后期 Agent 生成正式知识点后尤其重要。

---

# 60. 模型配置

不要把模型名称写死：

```python
model = "xxx"
```

从配置读取：

```text
LLM_PROVIDER
LLM_MODEL
LLM_API_KEY
LLM_BASE_URL
```

实际变量名根据项目配置统一。

---

# 61. API Key

禁止：

```python
api_key = "sk-xxxx"
```

必须：

```text
.env
```

读取。

`.env`：

```text
不提交 Git
```

---

# 62. LLM Provider 抽象

第一版不要实现非常复杂的 Provider 系统。

但至少建立：

```text
agent/common/llm.py
```

提供：

```python
get_llm()
```

这样未来更换：

```text
OpenAI
DeepSeek
通义
豆包
其他兼容 OpenAI API 的模型
```

时不会修改 Agent 核心逻辑。

---

# 63. 第一版推荐不要锁死具体厂商

Agent 应该依赖：

```text
ChatModel
```

而不是：

```text
某一个厂商 SDK
```

这样后面切模型方便。

---

# 64. 测试结果保存

第一版不需要数据库表。

可以保存：

```text
agent_runs/
    run_xxx/
        input.json
        chunks.json
        result.json
        logs.json
```

用于开发阶段调试。

如果觉得文件太复杂，也可以只通过 API 返回并记录日志。

---

# 65. Agent 测试页面

当前第一阶段：

**不要开发正式 Web Agent 页面。**

先使用：

```text
Swagger
```

或者：

```text
curl
Postman
```

测试。

正式页面等 Agent 验证通过以后再做。

这样不会让前端跟着一个还没稳定的 Agent 反复修改。

---

# 66. 手动测试流程

准备：

```text
android_sample.pdf
```

执行：

```text
POST /api/v1/agent/knowledge-extract/test
```

得到：

```text
run_id
```

检查：

```text
chunk_count
knowledge_count
knowledge_points
errors
```

---

# 67. 第一阶段成功标准

KnowledgeExtractAgent 必须至少满足：

```text
[ ] PDF 可以解析
[ ] DOCX 可以解析
[ ] TXT 可以解析
[ ] MD 可以解析

[ ] 文本能够合理切块

[ ] 每个 Chunk 能调用 LLM

[ ] 输出结构稳定

[ ] Pydantic 验证正常

[ ] 支持失败重试

[ ] 单个 Chunk 失败不影响全部任务

[ ] 能追溯来源 Chunk

[ ] difficulty 合法

[ ] 无需手工修改 JSON

[ ] 测试结果不污染正式 knowledge 表
```

---

# 68. 暂时不要接入 ImportTask

这是硬性要求：

当前：

```text
POST /api/v1/import-tasks
```

仍然保持现有 V1.0 行为。

不要修改为：

```text
upload
 ↓
KnowledgeExtractAgent
```

当前 Agent 只通过：

```text
/api/v1/agent/knowledge-extract/test
```

进行测试。

---

# 69. 为什么先不接入

因为需要先观察：

```text
Prompt 是否合理
Chunk 是否合理
LLM 是否稳定
Token 是否合理
知识粒度是否合理
解析是否正常
```

如果直接接入正式 ImportTask：

```text
每次测试都会产生正式知识点
```

数据库很快会被垃圾数据污染。

---

# 70. 第二阶段才接入正式流程

只有当第一阶段通过人工与自动测试以后，才开始：

```text
ImportTask
 ↓
DocumentParser
 ↓
Chunker
 ↓
KnowledgeExtractAgent
 ↓
KnowledgeService
 ↓
MySQL
```

而这一步另写一份开发任务。

---

# 71. 后续 KnowledgeDeduplicateAgent

当前不实现。

后续：

```text
KnowledgeExtractAgent
 ↓
候选知识点
 ↓
Embedding
 ↓
Vector Search
 ↓
Top K
 ↓
KnowledgeDeduplicateAgent
```

判断：

```text
NEW
DUPLICATE
MERGE
```

---

# 72. 后续 KnowledgeRelationAgent

再下一阶段：

```text
Knowledge
 ↓
KnowledgeRelationAgent
 ↓
prerequisite
related
extension
contrast
```

---

# 73. 后续 Question Agent

最后：

```text
Knowledge
 ↓
QuestionDecisionAgent
 ↓
需要生成？
 ↓
QuestionGenerateAgent
 ↓
QuestionEvaluateAgent
 ↓
QuestionService
```

---

# 74. 当前 Agent 的最终架构

第一阶段只实现：

```text
               Test API
                  │
                  ▼
        KnowledgeExtractGraph
                  │
          ┌───────┴────────┐
          ▼                ▼
  DocumentParser       TextChunker
       Tool                Tool
          │                │
          └───────┬────────┘
                  ▼
       KnowledgeExtractAgent
                  │
                  ▼
          Structured Output
                  │
                  ▼
         KnowledgeValidator
                  │
                  ▼
             JSON Result
```

---

# 75. 后续演进

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
KnowledgeDeduplicateAgent
    ↓
KnowledgeRelationAgent
    ↓
QuestionDecisionAgent
    ↓
QuestionGenerateAgent
    ↓
QuestionEvaluateAgent
    ↓
Knowledge / Question
```

---

# 76. 开发纪律

必须遵守：

1. 不修改现有已经正常运行的 V1.0 业务逻辑。
2. 不自动把 Agent 接入正式 ImportTask。
3. 不自动写入正式 knowledge 表。
4. 不引入 Redis。
5. 不引入 Vector DB。
6. 不引入 Neo4j。
7. 不开发题目生成 Agent。
8. 不开发知识去重 Agent。
9. 不开发知识关系 Agent。
10. 第一阶段只验证 KnowledgeExtractAgent。

---

# 77. 开发完成后必须实际测试

执行：

```bash
pytest
```

确保原有后端测试不被破坏。

然后运行：

```bash
uvicorn app.main:app --reload
```

打开：

```text
/docs
```

找到：

```text
POST /api/v1/agent/knowledge-extract/test
```

上传测试文档。

---

# 78. 必须保留原有功能

开发 Agent 后：

```text
/admin 登录
Knowledge
Question
Knowledge Relation
Import Task
Dashboard
```

全部必须继续正常。

至少重新运行：

```text
原有 pytest
```

不能因为加入 Agent 把原项目搞坏。

---

# 79. 最终交付报告

完成后输出：

## 1. Agent 架构

说明：

```text
DocumentParser
TextChunker
KnowledgeExtractAgent
Validator
LangGraph
```

之间的关系。

## 2. 新增文件

列出实际文件。

## 3. 新增依赖

列出：

```text
requirements.txt
```

新增的内容。

## 4. 新增 API

说明：

```text
POST /api/v1/agent/knowledge-extract/test
```

请求和 Response。

## 5. Agent Prompt

给出当前 Prompt 版本。

## 6. 测试结果

说明：

```text
pytest
Agent测试
Parser测试
Chunker测试
```

哪些真实通过。

## 7. 人工测试方法

说明如何准备一个测试文件并运行。

## 8. 已知问题

例如：

```text
扫描 PDF 暂不支持 OCR
表格复杂内容暂不支持
...
```

必须诚实说明。

---

# 80. 最重要的验收目标

不要把“Agent 成功调用 LLM”作为完成标准。

真正的完成标准是：

> **给它一份真实的 Android / Java 面试资料，它能够稳定地把文档内容转换成粒度合理、可追溯、结构化的知识点候选，并且不会污染正式数据库。**

只有达到这个标准：

```text
KnowledgeExtractAgent
```

才允许进入下一阶段。

---

# 81. 开始执行

现在请：

1. 阅读当前 backend 项目。
2. 阅读现有后端设计文档和数据库设计。
3. 不破坏现有 V1.0 功能。
4. 创建 KnowledgeExtractAgent。
5. 创建 DocumentParser。
6. 创建 TextChunker。
7. 使用 LangGraph 组织 Workflow。
8. 使用 Pydantic 做结构化输出。
9. 增加测试 API。
10. 增加自动化测试。
11. 实际运行测试。
12. 实际运行一个测试文档。
13. 检查输出质量。
14. 修复发现的问题。

**当前阶段不要将 Agent 接入正式 ImportTask，也不要向正式 knowledge 表写数据。**

完成后给出完整交付报告。