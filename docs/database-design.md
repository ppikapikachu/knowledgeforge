# AI 面试题库系统
## MySQL 数据库详细设计 V1.0

> 本文用于指导 AI Coding Agent 完成数据库、SQLAlchemy Model、Alembic Migration、Repository 的开发。
>
> 数据库设计目标：
>
> 1. 满足 V1.0 管理后台业务。
> 2. 保证题目、知识点等核心数据结构稳定。
> 3. 为后续 LangChain、LangGraph、向量检索、AI 题目生成预留扩展能力。
> 4. 避免 V1.0 引入不必要的数据库复杂度。

---

# 1. 数据库基础规范

## 1.1 数据库

```text
MySQL 8.x
```

数据库：

```text
interview_agent
```

---

## 1.2 字符集

统一：

```sql
utf8mb4
```

推荐：

```text
utf8mb4_0900_ai_ci
```

如果部署环境不支持，则使用兼容的 `utf8mb4` 排序规则。

---

## 1.3 主键

所有业务表：

```text
BIGINT UNSIGNED
```

建议主键：

```text
id BIGINT UNSIGNED AUTO_INCREMENT
```

V1.0 不需要 UUID 作为数据库主键。

但是文件名、任务外部标识等场景可以使用 UUID。

---

# 2. 通用字段规范

业务表原则上包含：

```text
created_at
updated_at
```

时间类型：

```text
DATETIME(3)
```

保存毫秒。

统一使用：

```text
UTC
```

展示时由前端根据用户时区转换。

注意：

> 不要一部分表保存本地时间、一部分表保存 UTC。

整个系统必须统一。

---

# 3. 表清单

V1.0 建议建立：

```text
1. admin_user
2. knowledge
3. knowledge_relation
4. question
5. question_option
6. question_knowledge
7. knowledge_import_task
```

表关系：

```text
                    admin_user
                        │
                        │ created_by
                        ▼
                knowledge_import_task
                        │
                        │
                        ▼
                    knowledge
                   /         \
                  /           \
                 ▼             ▼
  knowledge_relation      question_knowledge
        │                       │
        ▼                       ▼
   knowledge                question
                               │
                               ▼
                         question_option
```

---

# 4. admin_user 管理员表

表名：

```text
admin_user
```

用途：

保存管理后台管理员账号。

---

## 4.1 字段设计

| 字段 | 类型 | NULL | 默认值 | 说明 |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NO | AUTO_INCREMENT | 主键 |
| username | VARCHAR(50) | NO | - | 登录账号 |
| password_hash | VARCHAR(255) | NO | - | 密码哈希 |
| nickname | VARCHAR(50) | NO | - | 显示昵称 |
| avatar | VARCHAR(500) | YES | NULL | 头像 |
| status | TINYINT | NO | 1 | 账号状态 |
| last_login_at | DATETIME(3) | YES | NULL | 最后登录时间 |
| created_at | DATETIME(3) | NO | CURRENT_TIMESTAMP(3) | 创建时间 |
| updated_at | DATETIME(3) | NO | CURRENT_TIMESTAMP(3) | 更新时间 |

---

## 4.2 status

```text
1 = 正常
0 = 禁用
```

---

## 4.3 索引

```text
UNIQUE(username)
INDEX(status)
```

---

## 4.4 注意事项

### 注意 1：绝对不能保存明文密码

必须保存：

```text
password_hash
```

后端使用安全密码哈希算法。

---

### 注意 2：不要叫 password

数据库字段直接使用：

```text
password
```

容易造成误解。

使用：

```text
password_hash
```

---

# 5. knowledge 知识点表

表名：

```text
knowledge
```

这是整个系统最核心的数据表之一。

---

## 5.1 字段设计

| 字段 | 类型 | NULL | 默认值 | 说明 |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NO | AUTO_INCREMENT | 主键 |
| name | VARCHAR(200) | NO | - | 知识点名称 |
| summary | VARCHAR(1000) | YES | NULL | 简要说明 |
| content | LONGTEXT | YES | NULL | 完整知识内容 |
| difficulty | TINYINT | NO | 1 | 难度 |
| status | TINYINT | NO | 1 | 状态 |
| source_type | VARCHAR(30) | NO | MANUAL | 来源 |
| source_document | VARCHAR(500) | YES | NULL | 来源文档 |
| keywords | JSON | YES | NULL | 关键词 |
| created_at | DATETIME(3) | NO | CURRENT_TIMESTAMP(3) | 创建时间 |
| updated_at | DATETIME(3) | NO | CURRENT_TIMESTAMP(3) | 更新时间 |

---

# 6. knowledge.name 设计

例如：

```text
Java线程池
```

不要要求：

```text
name UNIQUE
```

原因：

AI 后期可能出现：

```text
Java线程池
Java 线程池
Java线程池机制
```

仅靠数据库唯一约束无法判断语义重复。

这个问题后面应该由：

```text
Embedding
+
Similarity
+
LLM
```

处理。

因此：

```text
name
```

只建立普通索引。

---

# 7. knowledge.content

使用：

```text
LONGTEXT
```

不要使用：

```text
VARCHAR(5000)
```

因为知识内容以后可能来自：

```text
PDF
DOCX
Markdown
网页
AI生成
```

长度无法提前固定。

---

# 8. knowledge.keywords

V1.0 使用：

```text
JSON
```

例如：

```json
[
  "线程池",
  "ThreadPoolExecutor",
  "核心线程数",
  "最大线程数"
]
```

这样开发简单。

暂时不要单独建立：

```text
knowledge_keyword
```

因为 V1.0 没有复杂的关键词检索需求。

---

# 9. knowledge.source_type

定义：

```text
MANUAL
IMPORT
AI
```

含义：

```text
MANUAL = 管理员手工创建
IMPORT = 文档导入
AI     = AI生成
```

后续可以继续扩展。

---

# 10. knowledge.status

```text
1 = 正常
0 = 禁用
```

不建议 V1.0 直接物理删除知识点。

---

# 11. knowledge 索引

建议：

```text
INDEX idx_knowledge_name(name)
INDEX idx_knowledge_difficulty(difficulty)
INDEX idx_knowledge_status(status)
INDEX idx_knowledge_source_type(source_type)
INDEX idx_knowledge_created_at(created_at)
```

不要给所有字段无脑建立索引。

---

# 12. knowledge_relation 知识关系表

表名：

```text
knowledge_relation
```

用于构建知识图谱的基础关系。

---

## 12.1 字段

| 字段 | 类型 | NULL | 默认值 | 说明 |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NO | AUTO_INCREMENT | 主键 |
| source_knowledge_id | BIGINT UNSIGNED | NO | - | 起点知识点 |
| target_knowledge_id | BIGINT UNSIGNED | NO | - | 终点知识点 |
| relation_type | VARCHAR(30) | NO | - | 关系类型 |
| created_at | DATETIME(3) | NO | CURRENT_TIMESTAMP(3) | 创建时间 |

---

# 13. relation_type

V1.0：

```text
prerequisite
related
extension
contrast
```

含义：

### prerequisite

前置知识。

```text
Java 多线程
      ↓
Java 线程池
```

### related

相关知识。

### extension

扩展知识。

### contrast

对比知识。

---

# 14. 知识关系唯一约束

必须：

```text
UNIQUE(
    source_knowledge_id,
    target_knowledge_id,
    relation_type
)
```

防止：

```text
Java → JVM → related
```

被重复插入。

---

# 15. 禁止自关联

必须禁止：

```text
source_knowledge_id == target_knowledge_id
```

例如：

```text
Java线程池 → Java线程池
```

不能存在。

这个规则：

```text
数据库层无法简单通过普通 UNIQUE 完成
```

因此必须在 Service 层校验。

---

# 16. 外键策略

V1.0 建议：

```text
使用外键
```

例如：

```text
knowledge_relation.source_knowledge_id
    → knowledge.id
```

删除策略：

```text
RESTRICT
```

不要使用：

```text
ON DELETE CASCADE
```

原因：

如果一个知识点被很多关系引用，不希望一个误删操作级联删除大量历史数据。

同时知识点本身采用禁用状态。

---

# 17. question 题目表

表名：

```text
question
```

核心字段：

| 字段 | 类型 | NULL | 默认值 | 说明 |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NO | AUTO_INCREMENT | 主键 |
| question_type | VARCHAR(30) | NO | - | 题型 |
| content | LONGTEXT | NO | - | 题目内容 |
| answer | LONGTEXT | NO | - | 标准答案 |
| analysis | LONGTEXT | YES | NULL | 题目解析 |
| difficulty | TINYINT | NO | 1 | 难度 |
| status | VARCHAR(30) | NO | DRAFT | 状态 |
| source_type | VARCHAR(30) | NO | MANUAL | 来源 |
| quality_score | DECIMAL(5,2) | YES | NULL | 质量评分 |
| used_count | INT UNSIGNED | NO | 0 | 被使用次数 |
| correct_count | INT UNSIGNED | NO | 0 | 正确次数 |
| created_at | DATETIME(3) | NO | CURRENT_TIMESTAMP(3) | 创建时间 |
| updated_at | DATETIME(3) | NO | CURRENT_TIMESTAMP(3) | 更新时间 |

---

# 18. question_type

V1.0：

```text
SINGLE_CHOICE
MULTIPLE_CHOICE
TRUE_FALSE
SHORT_ANSWER
```

后续可以增加：

```text
FILL_BLANK
CODING
SCENARIO
```

---

# 19. question.status

```text
DRAFT
PUBLISHED
DISABLED
```

含义：

### DRAFT

草稿，不应该进入正式练习。

### PUBLISHED

可以被用户练习。

### DISABLED

停用。

---

# 20. question.source_type

```text
MANUAL
IMPORT
AI
```

与 knowledge 保持一致。

---

# 21. question.quality_score

范围：

```text
0 ~ 100
```

例如：

```text
95
82
67
```

V1.0 可以手工维护。

后续 AI 评价时，可以由：

```text
QuestionEvaluateAgent
```

生成。

---

# 22. 为什么现在就加入 quality_score

虽然 V1.0 还没有 Agent，但这个字段非常有价值。

后期题目池选择：

```text
质量高
+
难度合适
+
用户没有近期做过
```

可以优先选择。

因此建议现在就建立。

---

# 23. 为什么现在就加入 used_count

以后题目选择不能简单：

```text
ORDER BY RAND()
```

否则题目数量大时性能差，而且很难控制题目暴露次数。

未来可以：

```text
quality_score
+
used_count
+
last_used_at
+
correct_rate
```

综合排序。

因此 V1.0 保留：

```text
used_count
```

是有意义的。

---

# 24. question_option 选项表

表名：

```text
question_option
```

字段：

| 字段 | 类型 | NULL | 默认值 | 说明 |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NO | AUTO_INCREMENT | 主键 |
| question_id | BIGINT UNSIGNED | NO | - | 所属题目 |
| option_key | VARCHAR(10) | NO | - | A/B/C/D |
| option_content | TEXT | NO | - | 选项内容 |
| is_correct | TINYINT | NO | 0 | 是否正确 |
| sort_order | INT | NO | 0 | 排序 |
| created_at | DATETIME(3) | NO | CURRENT_TIMESTAMP(3) | 创建时间 |
| updated_at | DATETIME(3) | NO | CURRENT_TIMESTAMP(3) | 更新时间 |

---

# 25. 注意：is_correct 必须放在 option

例如：

```text
A Java        true
B Kotlin      false
C Python      false
D Go          false
```

不要只依赖：

```text
question.answer = "A"
```

原因：

多选题可能：

```text
A,C
```

将正确性放到选项表更适合：

```text
SINGLE_CHOICE
MULTIPLE_CHOICE
```

统一处理。

---

# 26. question_option 唯一约束

```text
UNIQUE(
    question_id,
    option_key
)
```

防止：

```text
A
A
```

重复。

---

# 27. question_knowledge 题目知识点关联表

表名：

```text
question_knowledge
```

字段：

| 字段 | 类型 | NULL | 默认值 | 说明 |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NO | AUTO_INCREMENT | 主键 |
| question_id | BIGINT UNSIGNED | NO | - | 题目 |
| knowledge_id | BIGINT UNSIGNED | NO | - | 知识点 |
| created_at | DATETIME(3) | NO | CURRENT_TIMESTAMP(3) | 创建时间 |

---

# 28. question_knowledge 唯一约束

必须：

```text
UNIQUE(
    question_id,
    knowledge_id
)
```

一个题目不能重复绑定同一个知识点。

---

# 29. knowledge 与 question 的关系

关系：

```text
knowledge 1 ---- N question
```

但是实现上：

```text
question N ---- N knowledge
```

因此必须使用：

```text
question_knowledge
```

中间表。

---

# 30. knowledge_import_task 导入任务表

这是为后续 Agent Workflow 专门保留的核心任务表。

表名：

```text
knowledge_import_task
```

字段：

| 字段 | 类型 | NULL | 默认值 | 说明 |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NO | AUTO_INCREMENT | 主键 |
| file_name | VARCHAR(255) | NO | - | 原始文件名 |
| file_path | VARCHAR(500) | NO | - | 实际保存路径 |
| file_size | BIGINT UNSIGNED | NO | 0 | 文件大小 |
| file_type | VARCHAR(30) | NO | - | 文件类型 |
| status | VARCHAR(30) | NO | PENDING | 任务状态 |
| progress | TINYINT UNSIGNED | NO | 0 | 进度 |
| current_step | VARCHAR(100) | YES | NULL | 当前阶段 |
| error_message | TEXT | YES | NULL | 错误信息 |
| created_by | BIGINT UNSIGNED | NO | - | 创建管理员 |
| started_at | DATETIME(3) | YES | NULL | 开始时间 |
| finished_at | DATETIME(3) | YES | NULL | 完成时间 |
| created_at | DATETIME(3) | NO | CURRENT_TIMESTAMP(3) | 创建时间 |
| updated_at | DATETIME(3) | NO | CURRENT_TIMESTAMP(3) | 更新时间 |

---

# 31. import_task.status

V1.0：

```text
PENDING
RUNNING
SUCCESS
PARTIAL_SUCCESS
FAILED
CANCELLED
```

---

# 32. import_task.current_step

示例：

```text
UPLOADING
PARSING
EXTRACTING_KNOWLEDGE
DEDUPLICATING
MERGING_KNOWLEDGE
BUILDING_RELATIONS
GENERATING_QUESTIONS
EVALUATING_QUESTIONS
SAVING
FINISHED
```

V1.0 先使用少量状态即可。

后期 Agent 加入后再扩展。

---

# 33. import_task.progress

统一：

```text
0 ~ 100
```

注意：

不要让前端自己计算。

进度属于后端任务状态。

---

# 34. import_task.created_by

外键：

```text
created_by
    → admin_user.id
```

删除管理员时：

```text
RESTRICT
```

不要级联删除历史导入任务。

---

# 35. 导入任务文件设计

V1.0 文件：

```text
uploads/
```

例如：

```text
uploads/
2026/
09/
08/
a6a87b4f-xxxx.pdf
```

数据库：

```text
file_name = "Android面试题.pdf"

file_path =
"uploads/2026/09/08/a6a87b4f-xxxx.pdf"
```

---

# 36. 文件路径不要使用用户原始文件名

例如用户上传：

```text
../../test.pdf
```

不能直接保存。

后端必须：

```text
清洗文件名
+
生成随机服务器文件名
```

---

# 37. 外键总体设计

推荐：

```text id="e5z8p5"
knowledge_relation.source_knowledge_id
    → knowledge.id

knowledge_relation.target_knowledge_id
    → knowledge.id

question_option.question_id
    → question.id

question_knowledge.question_id
    → question.id

question_knowledge.knowledge_id
    → knowledge.id

knowledge_import_task.created_by
    → admin_user.id
```

策略：

```text
ON DELETE RESTRICT
```

---

# 38. 为什么不建议全部 CASCADE

例如：

```text
DELETE knowledge
```

如果设置：

```text
ON DELETE CASCADE
```

可能造成：

```text
知识点删除
 ↓
知识关系删除
 ↓
题目关联删除
```

甚至未来：

```text
知识点删除
 ↓
AI生成记录
 ↓
用户练习记录
```

被连锁影响。

这对面试题系统非常危险。

---

# 39. 软删除策略

V1.0 对：

```text
knowledge
question
```

采用状态控制。

例如：

```text
knowledge.status = 0
```

或者：

```text
question.status = DISABLED
```

而不是直接物理删除。

---

# 40. 是否所有表都需要 deleted_at

V1.0：

**不建议所有表都增加 deleted_at。**

否则查询逻辑会变复杂。

目前：

```text
knowledge.status
question.status
```

已经够用。

---

# 41. 不建议 V1.0 使用 EAV 结构

不要设计：

```text
question_attribute
key
value
```

这种万能字段表。

题目结构目前非常明确。

直接使用：

```text
question
question_option
```

更加清晰。

---

# 42. 不建议把所有扩展信息塞 JSON

例如不要：

```text
question.metadata JSON
```

然后把：

```text
difficulty
quality
source
type
```

全部塞里面。

真正参与查询、排序、过滤的数据应该使用独立字段。

JSON 只适合：

```text
keywords
```

这种不稳定、非核心结构。

---

# 43. 第一版不加入 embedding 字段

暂时不要给 knowledge 增加：

```text
embedding
```

原因：

Embedding 通常不适合直接存普通 MySQL。

后面加入：

```text
Vector DB
```

再设计。

---

# 44. 第一版不加入 Agent 字段

暂时不要把：

```text
agent_result
agent_state
agent_trace
```

直接塞入业务表。

后续建立独立的：

```text
agent_run
agent_message
agent_tool_call
```

等 Agent 真正开发时再设计。

---

# 45. 第一版不建立 question_generation_task

虽然以后一定会需要：

```text
question_generation_task
```

但 V1.0 暂时不建立。

原因：

当前没有真正的 AI 生成流程。

等实现：

```text
QuestionDecisionAgent
QuestionGenerateAgent
QuestionEvaluateAgent
```

的时候再增加。

---

# 46. 第一版不建立 practice_record

用户 Flutter 客户端暂时没有开发。

因此：

```text
practice_record
```

暂缓。

---

# 47. 第一版不建立 user 表

当前只有：

```text
admin_user
```

普通用户：

```text
user
```

等 Flutter 用户端开发时再增加。

---

# 48. 未来可能增加的表

后续：

```text
user

practice_record

wrong_question

question_generation_task

question_evaluation

agent_run

agent_tool_call

knowledge_embedding

question_embedding
```

不要 V1.0 提前创建。

---

# 49. 题目正确率

V1.0 目前：

```text
used_count
correct_count
```

保留。

未来用户练习时：

```text
correct_rate =
correct_count / used_count
```

但是注意：

不能简单让：

```text
used_count
```

长期作为用户维度统计。

未来用户练习必须设计：

```text
practice_record
```

以记录每个用户的行为。

---

# 50. 未来题目池

最终 AI 选题时需要：

```text
knowledge
+
question
+
question_knowledge
+
user practice history
```

例如：

```text
Java线程池
   ↓
找到所有题目
   ↓
过滤 DISABLED
   ↓
过滤不适合难度
   ↓
排除最近使用
   ↓
计算优先级
   ↓
选择题目
```

因此当前数据模型需要保持干净。

---

# 51. 索引设计总表

## admin_user

```text
UNIQUE(username)
INDEX(status)
```

## knowledge

```text
INDEX(name)
INDEX(difficulty)
INDEX(status)
INDEX(source_type)
INDEX(created_at)
```

## knowledge_relation

```text
INDEX(source_knowledge_id)
INDEX(target_knowledge_id)

UNIQUE(
    source_knowledge_id,
    target_knowledge_id,
    relation_type
)
```

## question

```text
INDEX(question_type)
INDEX(difficulty)
INDEX(status)
INDEX(source_type)
INDEX(created_at)
```

## question_option

```text
INDEX(question_id)

UNIQUE(
    question_id,
    option_key
)
```

## question_knowledge

```text
INDEX(question_id)
INDEX(knowledge_id)

UNIQUE(
    question_id,
    knowledge_id
)
```

## knowledge_import_task

```text
INDEX(status)
INDEX(created_by)
INDEX(created_at)
```

---

# 52. 不要无脑建立索引

原则：

> 经常用于 WHERE、JOIN、ORDER BY 的字段才考虑索引。

例如：

```text
content
analysis
summary
```

暂时不建立普通索引。

因为：

```text
LONGTEXT
```

并不适合这样简单建立全文业务索引。

后续真正需要全文检索，再单独设计。

---

# 53. SQLAlchemy Model 规范

所有 Model：

```python
class Knowledge(Base):
    __tablename__ = "knowledge"
```

使用：

```text
SQLAlchemy 2.x
Mapped
mapped_column
relationship
```

建议不要继续使用旧式：

```text
Column(...)
```

作为新项目主要写法。

---

# 54. ORM Relationship

可以定义：

```text
Question
    ↔ QuestionOption

Question
    ↔ QuestionKnowledge

Knowledge
    ↔ KnowledgeRelation
```

但是不要为了方便查询，把所有 Relationship 都配置成极其复杂的级联。

尤其不要默认：

```text
cascade="all, delete-orphan"
```

到处使用。

数据库本身已经采用 RESTRICT 策略，ORM 层也应该谨慎。

---

# 55. Repository 的查询规范

Repository 负责：

```text
find_by_id
find_list
count
create
update
disable
```

例如：

```text
KnowledgeRepository
QuestionRepository
ImportTaskRepository
```

不要在 Repository 里写：

```text
AI判断
业务规则
题目推荐
知识合并
```

---

# 56. Service 的事务边界

例如创建题目：

```text
BEGIN
 ↓
insert question
 ↓
insert options
 ↓
insert question_knowledge
 ↓
COMMIT
```

任何步骤失败：

```text
ROLLBACK
```

不能留下半成品数据。

---

# 57. 删除题目

V1.0 推荐：

```text
DELETE /questions/{id}
```

接口可以叫 delete。

但 Service 可以实现：

```text
status = DISABLED
```

而不是实际：

```sql
DELETE FROM question
```

这样 API 对前端更简单。

---

# 58. 更新题目

如果修改：

```text
题目内容
选项
答案
知识点
```

属于多表事务。

流程：

```text
BEGIN

更新 question

删除旧 options
插入新 options

删除旧 question_knowledge
插入新 question_knowledge

COMMIT
```

---

# 59. 多选题答案设计

数据库层：

```text
question.answer
```

保留。

但真正的正确答案以：

```text
question_option.is_correct
```

为准。

例如：

```text
A true
B false
C true
D false
```

最终正确答案：

```text
A,C
```

`answer` 可以用于：

```text
简短答案展示
AI 导出
文本题答案
```

但不要让两个字段产生冲突。

Service 在保存时必须保证二者逻辑一致。

---

# 60. 判断题

判断题：

```text
question_option
```

不需要数据。

例如：

```text
question.answer = "TRUE"
```

或者：

```text
FALSE
```

后端 Schema 必须根据题型验证。

---

# 61. 简答题

不需要 option。

使用：

```text
question.answer
question.analysis
```

保存标准答案与解析。

---

# 62. 题目 Schema 校验规则

后端创建题目时：

### SINGLE_CHOICE

```text
option >= 2
correct option == 1
```

### MULTIPLE_CHOICE

```text
option >= 2
correct option >= 1
```

### TRUE_FALSE

```text
option == 0
answer 必须是 TRUE/FALSE
```

### SHORT_ANSWER

```text
option == 0
answer 非空
```

这属于：

```text
Service / Schema
```

不属于数据库。

---

# 63. 数据库事务注意事项

不要在 Repository 中：

```text
每调用一次就 commit
```

例如：

```text
question_repository.create()
    commit()

option_repository.create()
    commit()
```

这样会导致：

```text
question 成功
option 失败
```

Service 应统一控制事务。

---

# 64. Alembic Migration

第一次：

```text
001_create_admin_user
002_create_knowledge
003_create_knowledge_relation
004_create_question
005_create_question_option
006_create_question_knowledge
007_create_knowledge_import_task
```

也可以将所有初始表放到一个 migration：

```text
001_initial_schema
```

对于 V1.0 更推荐：

```text
001_initial_schema
```

后续每次结构变化独立 migration。

---

# 65. 初始化管理员

不要直接把管理员密码写进：

```text
SQL migration
```

建议提供：

```text
scripts/create_admin.py
```

执行：

```bash
python scripts/create_admin.py
```

然后交互式创建管理员。

或者开发环境使用初始化脚本。

生产环境禁止使用固定默认密码。

---

# 66. MySQL 建表顺序

必须按照外键依赖顺序：

```text
1 admin_user
2 knowledge
3 question
4 knowledge_relation
5 question_option
6 question_knowledge
7 knowledge_import_task
```

---

# 67. 数据库命名规范

统一：

```text
snake_case
```

例如：

```text
question_type
source_type
created_at
updated_at
knowledge_id
```

不要：

```text
questionType
knowledgeId
```

---

# 68. 枚举值存储规范

V1.0 不建议使用 MySQL：

```text
ENUM
```

例如不要：

```sql
question_type ENUM(...)
```

建议：

```text
VARCHAR(30)
```

由：

```text
Python Enum
```

控制。

例如：

```python
class QuestionType(str, Enum):
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    SHORT_ANSWER = "SHORT_ANSWER"
```

这样以后新增题型不需要频繁修改 MySQL ENUM。

---

# 69. 状态字段同样使用 Python Enum

例如：

```python
class QuestionStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    DISABLED = "DISABLED"
```

数据库保存字符串。

---

# 70. 注意 MySQL 与 Python Enum 的一致性

不要让：

```text
Python:
SINGLE

Database:
single_choice
```

这种值混乱。

项目中统一大写字符串：

```text
SINGLE_CHOICE
MULTIPLE_CHOICE
TRUE_FALSE
SHORT_ANSWER
```

---

# 71. V1.0 最终 ER 关系

逻辑关系：

```text
                         ┌──────────────┐
                         │  admin_user  │
                         └──────┬───────┘
                                │
                                │ 1:N
                                ▼
                    ┌──────────────────────┐
                    │ knowledge_import_task│
                    └──────────────────────┘


┌─────────────────┐
│    knowledge    │
└───────┬─────────┘
        │
        │ self relation
        ▼
┌────────────────────────┐
│ knowledge_relation     │
└────────────────────────┘


┌─────────────────┐
│    knowledge    │
└────────┬────────┘
         │
         │ N:M
         ▼
┌────────────────────────┐
│  question_knowledge   │
└──────────┬─────────────┘
           │
           ▼
     ┌────────────┐
     │  question  │
     └─────┬──────┘
           │
           │ 1:N
           ▼
     ┌────────────────┐
     │ question_option│
     └────────────────┘
```

---

# 72. 当前数据库不要加入的内容

V1.0 明确不加入：

```text
user
practice_record
wrong_question

embedding
vector_document

agent_run
agent_tool_call

question_generation_task
question_evaluation

redis相关数据
celery相关数据

neo4j
```

---

# 73. 后续扩展方向

## V1.1：AI 知识提取

增加：

```text
agent_run
```

---

## V1.2：Embedding

增加：

```text
knowledge_embedding
```

或者直接采用 Vector DB。

---

## V1.3：AI 题目生成

增加：

```text
question_generation_task
```

---

## V1.4：AI 题目评价

增加：

```text
question_evaluation
```

---

## V1.5：Flutter 用户端

增加：

```text
user
practice_record
wrong_question
```

---

# 74. 给 AI Coding Agent 的硬性要求

AI 在实现数据库时：

1. 必须使用 SQLAlchemy 2.x。
2. 必须使用 Alembic。
3. 所有表使用 BIGINT UNSIGNED 主键。
4. 所有时间字段统一 DATETIME(3)。
5. 字符串统一 snake_case。
6. 不允许明文保存密码。
7. 不允许在业务代码中硬编码数据库密码。
8. 不允许使用 `Base.metadata.create_all()` 代替正式 migration。
9. 多表操作必须由 Service 控制事务。
10. Repository 不负责业务逻辑。
11. 不允许随意增加 Redis、Celery、Vector DB 等依赖。
12. 不允许为了未来需求提前创建大量空表。
13. 外键删除策略默认使用 RESTRICT。
14. 核心业务数据优先使用状态禁用，而不是物理删除。
15. 所有题型、状态、来源类型优先由 Python Enum 管理。
16. 所有创建/修改请求必须通过 Pydantic Schema 校验。
17. 必须建立必要的 UNIQUE 和 INDEX。
18. 必须防止知识点自关联。
19. 必须防止题目选项重复。
20. 必须防止题目与知识点重复关联。

---

# 75. 最终数据库 V1.0

最终只需要：

```text
admin_user
knowledge
knowledge_relation
question
question_option
question_knowledge
knowledge_import_task
```

这 7 张表。

整体保持：

```text
简单
规范
可维护
可扩展
```

后续再逐步引入：

```text
Agent
↓
Embedding
↓
Vector DB
↓
异步任务
↓
Redis
↓
用户系统
↓
Flutter
```

不要在 V1.0 为未来不存在的需求制造复杂性。