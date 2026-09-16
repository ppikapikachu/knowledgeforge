

请先读取项目中的：

```text
docs/backend-design.md
docs/database-design.md
docs/knowledge-extract-agent-design.md
```

当前任务只实现：

# KnowledgeExtractAgent V1.0

不要开发其他 Agent。

---

## 一、当前项目状态

当前后端 V1.0 已经完成并且基础功能可以正常运行。

已有：

* FastAPI
* MySQL
* SQLAlchemy
* Alembic
* JWT
* 管理员认证
* Knowledge CRUD
* Knowledge Relation
* Question CRUD
* Import Task
* Dashboard
* pytest

不要破坏现有功能。

---

# 二、本次任务目标

实现第一个 AI Agent：

```text
KnowledgeExtractAgent
```

它的唯一核心职责：

> 从已经解析出来的文本内容中，识别并提取“可独立学习、可独立出题”的知识点。

第一阶段必须：

```text
文件
↓
DocumentParser
↓
StructuredDocument
↓
TextChunker
↓
DocumentChunk
↓
KnowledgeExtractAgent
↓
KnowledgeCandidate
↓
Validator
↓
JSON结果
```

---

# 三、必须遵守的边界

当前阶段：

不实现：

```text
KnowledgeDeduplicateAgent
KnowledgeRelationAgent
QuestionDecisionAgent
QuestionGenerateAgent
QuestionEvaluateAgent
Embedding
Vector DB
Redis
Celery
RabbitMQ
Neo4j
```

并且：

**KnowledgeExtractAgent 当前不能自动写入正式 knowledge 表。**

不能出现：

```text
文件
↓
Agent
↓
knowledge 表
```

必须：

```text
文件
↓
Agent
↓
结构化测试结果
```

---

# 四、文件解析

实现：

```text
DocumentParser
```

支持：

```text
PDF
DOCX
TXT
MD
```

注意：

DocumentParser 不是 LLM Agent。

它是普通 Service / Tool。

它只负责：

```text
文件 → 结构化文本
```

不要让 LLM 参与文件基础解析。

扫描型 PDF 当前可以明确返回“不支持 OCR”，不要为了完成任务临时增加 OCR。

---

# 五、文本分块

实现：

```text
TextChunker
```

要求：

优先按照：

```text
标题
章节
段落
```

进行语义分块。

只有超过 chunk_size 后才进一步切分。

chunk_size、overlap 必须配置化。

不要写死在业务代码中。

---

# 六、KnowledgeExtractAgent

使用：

```text
LangChain
LangGraph
Pydantic
```

创建独立 Agent Workflow。

第一阶段 LangGraph：

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

保持简单，不要为了使用 LangGraph 而增加复杂节点。

---

# 七、模型输出

使用 Pydantic 结构化输出。

知识点：

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

difficulty：

```text
1 = 简单
2 = 中等
3 = 困难
```

keywords：

```text
3~8 个
```

不允许：

```text
difficulty = 0/4/5
```

---

# 八、Knowledge 的粒度

这是本 Agent 最重要的 Prompt 约束。

一个知识点必须：

```text
能够独立学习
能够独立理解
能够独立出题
```

不能太粗：

```text
Android
Java
数据库
```

也不能无意义地过细：

```text
onCreate
```

除非输入文本明确是在讨论 onCreate 本身。

例如输入：

```text
Activity具有完整生命周期，包括onCreate、
onStart、onResume、onPause、onStop、onDestroy。
```

合理输出可以是：

```text
Activity生命周期
```

必要时才进一步提取：

```text
Activity生命周期回调
```

---

# 九、防止幻觉

System Prompt 必须明确：

```text
只能根据输入文本提取知识点。

不得使用输入文本之外的知识补充内容。

输入不足时不要自行推测。

如果当前 Chunk 不包含可学习知识点，可以返回空数组。
```

---

# 十、允许零知识点

例如：

```text
目录
版权声明
页眉
页脚
参考资料
```

允许：

```json
{
  "knowledge_points": []
}
```

禁止为了满足数量要求而强行生成知识点。

---

# 十一、知识点来源追踪

每个 KnowledgeCandidate 必须保存：

```text
source_chunk_id
source_title
source_page_start
source_page_end
```

这样以后能够：

```text
知识点
↓
来源 Chunk
↓
原始文件
```

---

# 十二、LLM 配置

不要在代码中硬编码：

```text
API Key
Model
Base URL
```

全部从环境变量读取。

建立统一：

```text
agent/common/llm.py
```

通过：

```python
get_llm()
```

返回 ChatModel。

后续切换模型时，不应该修改 KnowledgeExtractAgent 核心代码。

---

# 十三、错误与 Retry

LLM 返回非法结构时：

```text
最多重试 2 次
```

如果仍然失败：

```text
记录 error
```

不要无限重试。

单个 Chunk 失败不能导致整个文件任务全部失败。

例如：

```text
Chunk 1 ✅
Chunk 2 ✅
Chunk 3 ❌
Chunk 4 ✅
Chunk 5 ✅
```

最终允许：

```text
partial success
```

并记录失败 Chunk。

---

# 十四、Token 和执行日志

尽可能记录：

```text
run_id
chunk_id
model
start_time
duration
input_tokens
output_tokens
error
```

如果当前模型 SDK 能获取 Token Usage，就记录。

如果获取不到，不要伪造。

---

# 十五、测试 API

新增开发测试接口：

```text
POST /api/v1/agent/knowledge-extract/test
```

这个接口：

```text
管理员权限
上传测试文件
执行 KnowledgeExtractAgent
返回结构化结果
```

非常重要：

**不能向正式 knowledge 表写数据。**

---

# 十六、返回示例

希望类似：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "run_id": "xxx",
    "file_name": "android-interview.pdf",
    "chunk_count": 10,
    "knowledge_count": 26,
    "knowledge_points": [],
    "errors": []
  }
}
```

具体字段可以根据实现调整，但必须结构化、稳定。

---

# 十七、自动化测试

必须增加：

```text
Parser Test
Chunker Test
Schema Test
Agent Test
API Test
```

重点：

不要断言 LLM 每次返回完全一样的知识点。

而是验证：

```text
JSON结构正确
字段完整
difficulty 合法
keywords 合法
source 正确
Agent 没有异常
```

---

# 十八、原项目回归测试

必须运行：

```bash
python -m pytest tests/ -v
```

确保新增 Agent 没有破坏原有业务。

---

# 十九、手工测试

准备一个：

```text
20KB~50KB
```

左右的 Android / Java 面试资料。

通过：

```text
POST /api/v1/agent/knowledge-extract/test
```

测试。

重点观察：

1. 是否漏掉明显知识点
2. 是否生成垃圾知识点
3. 粒度是否合理
4. 是否出现幻觉
5. summary 是否准确
6. content 是否忠于原文
7. difficulty 是否基本合理
8. 来源位置是否正确

---

# 二十、第一阶段不要接 ImportTask

这一点非常重要。

当前：

```text
POST /api/v1/import-tasks
```

保持原来的行为。

不要把 Agent 自动接进去。

当前只允许：

```text
测试 API
↓
KnowledgeExtractAgent
↓
返回结果
```

等人工验证 Agent 质量之后，再进行第二阶段：

```text
ImportTask
↓
DocumentParser
↓
TextChunker
↓
KnowledgeExtractAgent
↓
KnowledgeService
↓
MySQL
```

---

# 二十一、不要开发前端 Agent 页面

当前不要修改：

```text
admin-web/
```

Agent 第一阶段只通过：

```text
Swagger
curl
Postman
```

验证即可。

这样前端和后端保持独立。

---

# 二十二、最终验收标准

必须满足：

```text
[ ] PDF 可以解析
[ ] DOCX 可以解析
[ ] TXT 可以解析
[ ] MD 可以解析
[ ] 文本能够合理分块
[ ] LangGraph Workflow 能运行
[ ] LLM 能正常调用
[ ] Pydantic 结构化输出正常
[ ] 非法输出能够 Retry
[ ] 单 Chunk 失败不影响其他 Chunk
[ ] 来源信息能够保留
[ ] 不写入正式 knowledge 表
[ ] 测试 API 可以调用
[ ] Agent 自动化测试通过
[ ] 原有 pytest 通过
[ ] /docs 可以正常使用
```

---

# 二十三、不要伪造测试结果

必须实际运行：

```bash
python -m pytest tests/ -v
```

以及实际调用：

```text
POST /api/v1/agent/knowledge-extract/test
```

实际无法验证的内容必须标记：

```text
未验证
```

不能声称“测试通过”。

---

# 二十四、最终报告

完成以后报告：

```text
1. 新增文件

2. 新增依赖

3. Agent Workflow

4. DocumentParser

5. TextChunker

6. Prompt

7. 新增 API

8. 自动化测试结果

9. 实际 Agent 测试结果

10. Token / 执行情况

11. 已知问题

12. 当前不能做的事情

13. 后续建议
```

最后特别说明：

```text
当前 KnowledgeExtractAgent 尚未接入正式 ImportTask。
```

---

# 二十五、开始执行

现在请：

1. 阅读相关设计文档。
2. 检查现有 backend 结构。
3. 创建独立 KnowledgeExtractAgent。
4. 创建 DocumentParser。
5. 创建 TextChunker。
6. 创建 LangGraph Workflow。
7. 创建测试 API。
8. 创建测试。
9. 实际运行测试。
10. 实际运行测试文档。
11. 修复问题。
12. 输出最终报告。

不要只输出代码示例。

**直接在当前 backend 项目中实施。**
