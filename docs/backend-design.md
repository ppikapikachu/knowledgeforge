# AI 面试题库系统
## FastAPI 后端完整设计文档 V1.0

> 本文用于指导 AI 编程助手完成后端项目的实际开发。
>
> 开发目标：先完成稳定、清晰、可维护的传统业务后端，为后续接入 LangChain、LangGraph、Embedding、Vector DB、Redis、异步任务等 AI 能力预留扩展点。
>
> **V1.0 不要求实现 Agent，但代码结构必须能够平滑接入 Agent。**

---

# 1. 项目概述

系统是一个 AI 驱动的面试题库和知识库系统。

当前阶段只开发：

```text
Vue3 管理后台
        ↓ HTTP/JSON
FastAPI 后端
        ↓
MySQL
```

后端主要负责：

1. 管理员认证
2. 知识点管理
3. 知识点关系管理
4. 面试题管理
5. 题目与知识点关联
6. 题库文档上传
7. 导入任务管理
8. Dashboard 数据统计
9. 为后续 AI Agent 提供业务接口和数据基础

---

# 2. V1.0 技术栈

## 2.1 核心框架

```text
Python
FastAPI
Pydantic
SQLAlchemy
Alembic
MySQL
JWT
```

## 2.2 管理后台

后端只需要提供 REST API：

```text
Vue3
Element Plus
Axios
```

## 2.3 暂时不引入

```text
Redis
Celery
RabbitMQ
Kafka
Milvus
Qdrant
Neo4j
MinIO
LangChain
LangGraph
```

这些技术不是不使用，而是放到后续版本。

---

# 3. 总体架构

V1.0：

```text
                    ┌──────────────────┐
                    │     Vue3 Admin   │
                    │    Element Plus  │
                    └────────┬─────────┘
                             │ HTTP
                             ▼
                    ┌──────────────────┐
                    │      FastAPI     │
                    │                  │
                    │ Router           │
                    │ Service          │
                    │ Repository       │
                    │ ORM              │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │      MySQL       │
                    └──────────────────┘
```

未来扩展：

```text
                     FastAPI
                        │
              ┌─────────┴─────────┐
              │                   │
           业务模块              Agent
                                  │
                              LangGraph
                                  │
                         ┌────────┴────────┐
                         │                 │
                       LLM           Vector DB
```

---

# 4. 核心设计原则

## 4.1 分层架构

后端严格按照：

```text
Router
   ↓
Service
   ↓
Repository
   ↓
SQLAlchemy
   ↓
MySQL
```

职责：

### Router

负责：

- 接收 HTTP 请求
- 参数校验
- 权限依赖
- 调用 Service
- 返回统一响应

Router 不负责：

- 复杂业务逻辑
- SQL
- LLM 调用

---

### Service

负责：

- 业务逻辑
- 业务规则
- 多 Repository 协作
- 事务边界
- 数据组装

---

### Repository

负责：

- 数据库查询
- 新增
- 修改
- 删除
- 分页
- 条件查询

Repository 不负责业务判断。

---

# 5. 项目目录结构

最终目录：

```text
backend/
│
├── app/
│   │
│   ├── main.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   │
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── admin.py
│   │       ├── knowledge.py
│   │       ├── knowledge_relation.py
│   │       ├── question.py
│   │       ├── question_option.py
│   │       ├── import_task.py
│   │       └── dashboard.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── admin.py
│   │   ├── knowledge.py
│   │   ├── knowledge_relation.py
│   │   ├── question.py
│   │   ├── question_option.py
│   │   ├── question_knowledge.py
│   │   └── import_task.py
│   │
│   ├── schemas/
│   │   ├── common.py
│   │   ├── auth.py
│   │   ├── admin.py
│   │   ├── knowledge.py
│   │   ├── knowledge_relation.py
│   │   ├── question.py
│   │   └── import_task.py
│   │
│   ├── repositories/
│   │   ├── admin_repository.py
│   │   ├── knowledge_repository.py
│   │   ├── knowledge_relation_repository.py
│   │   ├── question_repository.py
│   │   └── import_task_repository.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── admin_service.py
│   │   ├── knowledge_service.py
│   │   ├── knowledge_relation_service.py
│   │   ├── question_service.py
│   │   ├── import_task_service.py
│   │   └── dashboard_service.py
│   │
│   ├── dependencies/
│   │   ├── auth.py
│   │   └── database.py
│   │
│   ├── utils/
│   │   ├── pagination.py
│   │   ├── response.py
│   │   ├── file.py
│   │   └── datetime.py
│   │
│   └── middleware/
│       ├── request_id.py
│       └── exception_handler.py
│
├── migrations/
│   └── versions/
│
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_knowledge.py
│   ├── test_question.py
│   └── test_import_task.py
│
├── uploads/
│
├── .env
├── .env.example
├── alembic.ini
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

# 6. 特别注意：不要过度拆分

V1.0 使用：

```text
一个 FastAPI 项目
```

不要拆成：

```text
用户服务
题库服务
知识库服务
Agent 服务
文件服务
```

这种微服务架构。

当前项目规模没有必要。

未来真正需要的时候再拆。

---

# 7. 数据库设计

数据库：

```text
MySQL 8.x
```

字符集：

```text
utf8mb4
```

排序规则优先使用适合项目的 `utf8mb4` Unicode 排序规则。

---

# 8. 所有业务表通用字段

除特殊表外，业务表建议包含：

```text
id
created_at
updated_at
```

其中：

```text
id BIGINT
```

不要使用 INT。

原因：

后续题目、知识点、AI 生成记录增长以后，BIGINT 更稳妥。

---

# 9. admin_user 管理员表

```text
admin_user
```

字段：

```text
id
username
password_hash
nickname
avatar
status
last_login_at
created_at
updated_at
```

建议：

```text
username VARCHAR(50) UNIQUE
password_hash VARCHAR(255)
status TINYINT
```

状态：

```text
1 = 正常
0 = 禁用
```

注意：

**绝对不能保存明文密码。**

密码必须使用安全哈希算法。

---

# 10. knowledge 知识点表

```text
knowledge
```

字段：

```text
id
name
summary
content
difficulty
status
source_type
source_document
keywords
created_at
updated_at
```

说明：

### name

知识点名称。

例如：

```text
Java线程池
```

### summary

简短描述。

### content

完整知识内容。

### difficulty

例如：

```text
1 = 简单
2 = 中等
3 = 困难
```

### status

```text
1 = 正常
0 = 禁用
```

### source_type

例如：

```text
MANUAL
IMPORT
AI
```

注意：

**source_type 现在就建议保留。**

后面 AI 生成知识点时会使用。

---

# 11. knowledge_relation 知识点关系表

```text
knowledge_relation
```

字段：

```text
id
source_knowledge_id
target_knowledge_id
relation_type
created_at
```

关系：

```text
prerequisite
related
extension
contrast
```

例如：

```text
Java线程池
   │
   └── prerequisite → Java多线程
```

注意：

必须禁止：

```text
source_knowledge_id == target_knowledge_id
```

即：

```text
知识点不能指向自己
```

数据库层最好配合应用层一起防止。

---

# 12. question 题目表

```text
question
```

字段：

```text
id
question_type
content
answer
analysis
difficulty
status
source_type
quality_score
used_count
correct_count
created_at
updated_at
```

题型：

```text
SINGLE_CHOICE
MULTIPLE_CHOICE
TRUE_FALSE
SHORT_ANSWER
```

状态：

```text
DRAFT
PUBLISHED
DISABLED
```

来源：

```text
MANUAL
IMPORT
AI
```

---

# 13. question_option 选项表

```text
question_option
```

字段：

```text
id
question_id
option_key
option_content
sort_order
created_at
```

例如：

```text
A   Java
B   Kotlin
C   Python
D   Go
```

注意：

判断题和简答题不需要 option。

---

# 14. question_knowledge 题目与知识点关联表

```text
question_knowledge
```

字段：

```text
id
question_id
knowledge_id
created_at
```

题目可以关联多个知识点。

例如：

```text
题目：
“Java线程池核心参数有哪些？”

关联：

Java线程池
Java多线程
并发编程
```

必须建立唯一约束：

```text
question_id + knowledge_id
```

防止重复关联。

---

# 15. knowledge_import_task 导入任务

```text
knowledge_import_task
```

字段：

```text
id
file_name
file_path
file_size
file_type
status
progress
current_step
error_message
created_by
started_at
finished_at
created_at
updated_at
```

状态：

```text
PENDING
RUNNING
SUCCESS
PARTIAL_SUCCESS
FAILED
CANCELLED
```

进度：

```text
0 ~ 100
```

当前阶段，例如：

```text
文件上传
文件解析
知识点提取
知识点去重
题目生成
完成
```

虽然 V1.0 暂时不真正执行 Agent，但这个表必须设计好。

因为后面 Agent Workflow 会直接使用这个表。

---

# 16. 文件存储设计

V1.0：

```text
uploads/
```

保存上传文件。

例如：

```text
uploads/
├── 2026/
│   ├── 09/
│   │   ├── abc.pdf
│   │   └── xyz.docx
```

数据库只保存：

```text
file_path
file_name
file_type
file_size
```

不要把文件二进制直接存进 MySQL。

---

# 17. 文件路径注意事项

**不要直接信任客户端传来的文件名。**

例如不能直接：

```python
save_path = "uploads/" + file.filename
```

应该：

1. 清理文件名
2. 生成服务器端唯一文件名
3. 限制扩展名
4. 限制文件大小

推荐：

```text
UUID + 扩展名
```

例如：

```text
c5c1f7c5-xxxx-xxxx.pdf
```

---

# 18. API 统一前缀

所有后台接口：

```text
/api/v1
```

例如：

```text
/api/v1/auth/login
/api/v1/knowledge
/api/v1/questions
```

这样以后 V2 不会影响 V1。

---

# 19. API 统一响应格式

正常响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

列表：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 100
  }
}
```

失败：

```json
{
  "code": 40001,
  "message": "知识点不存在",
  "data": null
}
```

---

# 20. 分页规范

统一：

```text
page
page_size
```

例如：

```text
?page=1&page_size=20
```

限制：

```text
page >= 1
1 <= page_size <= 100
```

以后用户端题目流可以采用 Cursor Pagination。

但是：

**管理后台列表 V1.0 使用普通 page/page_size 即可。**

---

# 21. 管理员认证

使用：

```text
JWT Access Token
```

登录：

```text
POST /api/v1/auth/login
```

请求：

```json
{
  "username": "admin",
  "password": "******"
}
```

返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "xxx",
    "token_type": "bearer"
  }
}
```

前端后续：

```text
Authorization: Bearer xxx
```

---

# 22. JWT 注意事项

JWT 中只放：

```text
sub
```

或者：

```text
admin_id
```

不要把：

```text
用户名
权限列表
大量业务数据
```

全部塞进 JWT。

Token 应保持尽可能小。

---

# 23. 权限设计

V1.0 暂时：

```text
管理员登录
```

只做基础认证。

暂时不做复杂 RBAC。

不要第一阶段就加入：

```text
角色
权限组
菜单权限
按钮权限
数据权限
```

等后台真的有多个角色需求后再做。

但是代码应该通过依赖：

```python
get_current_admin()
```

统一获取当前管理员。

这样以后增加 RBAC 时不会修改大量业务接口。

---

# 24. Knowledge API

## 获取知识点列表

```text
GET /api/v1/knowledge
```

支持：

```text
page
page_size
keyword
difficulty
status
```

---

## 获取知识点详情

```text
GET /api/v1/knowledge/{id}
```

返回：

```text
知识点
+
关联题目数量
+
关联知识点
```

---

## 创建知识点

```text
POST /api/v1/knowledge
```

---

## 修改知识点

```text
PUT /api/v1/knowledge/{id}
```

---

## 删除知识点

```text
DELETE /api/v1/knowledge/{id}
```

V1.0 推荐采用：

```text
逻辑删除 / 状态禁用
```

而不是直接物理删除。

特别是已经被题目关联的知识点。

---

# 25. 知识关系 API

```text
GET    /api/v1/knowledge/{id}/relations
POST   /api/v1/knowledge/{id}/relations
DELETE /api/v1/knowledge/{id}/relations/{relation_id}
```

创建：

```json
{
  "target_knowledge_id": 1002,
  "relation_type": "prerequisite"
}
```

必须校验：

```text
target_knowledge_id 存在
不能自己关联自己
不能重复关联
relation_type 合法
```

---

# 26. Question API

```text
GET    /api/v1/questions
GET    /api/v1/questions/{id}
POST   /api/v1/questions
PUT    /api/v1/questions/{id}
DELETE /api/v1/questions/{id}
```

查询条件：

```text
question_type
difficulty
status
knowledge_id
source_type
keyword
```

---

# 27. 创建题目注意事项

创建题目时：

```text
Question
QuestionOption
QuestionKnowledge
```

可能需要同时保存。

所以必须由 Service 控制事务。

例如：

```text
开始事务
 ↓
创建 question
 ↓
创建 option
 ↓
创建 question_knowledge
 ↓
提交事务
```

任何一步失败：

```text
全部回滚
```

不能出现：

```text
question 保存成功
option 保存失败
```

这种脏数据。

---

# 28. 不同题型的数据规则

## 单选题

必须：

```text
至少 2 个 option
只能有一个正确答案
```

## 多选题

必须：

```text
至少 2 个 option
可以多个正确答案
```

## 判断题

不需要：

```text
question_option
```

answer：

```text
TRUE
FALSE
```

## 简答题

不需要：

```text
question_option
```

answer 保存标准答案。

---

# 29. 题目删除注意事项

已经有练习记录以后：

**不要随便物理删除题目。**

虽然 V1.0 还没有用户练习模块，但要提前考虑数据生命周期。

建议：

```text
DISABLED
```

而不是直接 DELETE。

API 可以保留 delete，但 Service 内部优先采用逻辑删除。

---

# 30. 导入任务 API

上传：

```text
POST /api/v1/import-tasks
```

使用：

```text
multipart/form-data
```

上传成功：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": 10001
  }
}
```

查询：

```text
GET /api/v1/import-tasks/{id}
```

列表：

```text
GET /api/v1/import-tasks
```

---

# 31. V1.0 导入任务的实现方式

第一版可以先：

```text
上传文件
 ↓
保存文件
 ↓
创建任务
 ↓
PENDING
```

暂时不真正运行 AI。

可以提供：

```text
模拟任务
```

例如：

```text
PENDING
 ↓
RUNNING
 ↓
文件解析
 ↓
知识点处理
 ↓
SUCCESS
```

这样 Vue 管理后台可以先把任务管理整个流程跑通。

---

# 32. Dashboard API

```text
GET /api/v1/dashboard/overview
```

返回：

```json
{
  "knowledge_count": 1000,
  "question_count": 5000,
  "single_choice_count": 2000,
  "multiple_choice_count": 1200,
  "true_false_count": 1000,
  "short_answer_count": 800,
  "import_task_count": 20
}
```

数据统计直接使用 SQL 聚合。

V1.0：

**不要为了 Dashboard 引入 Redis 缓存。**

---

# 33. 异常处理

必须实现统一异常体系。

例如：

```python
BusinessException
ResourceNotFoundException
ValidationException
AuthenticationException
PermissionException
```

HTTP 层统一转换。

例如：

```json
{
  "code": 40401,
  "message": "知识点不存在",
  "data": null
}
```

不要在每个 Router 里面：

```python
try:
    ...
except Exception:
    ...
```

大量重复处理。

---

# 34. 全局异常处理

统一捕获：

```text
BusinessException
RequestValidationError
HTTPException
Exception
```

对于未知异常：

用户：

```text
系统内部错误
```

日志：

```text
完整错误堆栈
```

不要把 Python 堆栈返回给前端。

---

# 35. 日志设计

必须有：

```text
INFO
WARNING
ERROR
```

重点记录：

```text
request_id
请求路径
请求方法
响应状态
耗时
异常
```

例如：

```text
request_id=xxx
POST /api/v1/questions
200
cost=35ms
```

---

# 36. Request ID

建议加入：

```text
RequestIdMiddleware
```

每一次 HTTP 请求分配：

```text
request_id
```

并在日志里打印。

后面 Agent 出现问题时：

```text
用户操作
 ↓
HTTP request_id
 ↓
import_task_id
 ↓
agent_run_id
```

就能追踪完整链路。

所以：

**request_id 现在就值得做。**

---

# 37. 配置管理

所有环境配置通过：

```text
.env
```

例如：

```text
APP_NAME
APP_ENV
DEBUG

MYSQL_HOST
MYSQL_PORT
MYSQL_DATABASE
MYSQL_USERNAME
MYSQL_PASSWORD

JWT_SECRET_KEY
JWT_EXPIRE_MINUTES

UPLOAD_DIR
MAX_UPLOAD_SIZE
```

代码中禁止：

```python
password = "123456"
```

禁止把：

```text
数据库密码
JWT Secret
API Key
LLM Key
```

写死在代码里。

---

# 38. .env.example

必须提供：

```text
.env.example
```

例如：

```text
APP_ENV=development

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=interview_agent
MYSQL_USERNAME=root
MYSQL_PASSWORD=

JWT_SECRET_KEY=
JWT_EXPIRE_MINUTES=120

UPLOAD_DIR=./uploads
```

`.env` 不提交 Git。

---

# 39. SQLAlchemy 设计

使用：

```text
SQLAlchemy 2.x 风格
```

模型统一继承：

```python
Base
```

尽量使用类型注解。

数据库 Session 通过 FastAPI Dependency 注入。

例如逻辑：

```text
Request
 ↓
get_db()
 ↓
Session
 ↓
Service
 ↓
Repository
```

---

# 40. Alembic

数据库结构必须由：

```text
Alembic
```

管理。

禁止开发过程中长期依赖：

```text
Base.metadata.create_all()
```

作为正式数据库迁移方式。

正确流程：

```text
修改 Model
 ↓
Alembic migration
 ↓
执行 upgrade
```

例如：

```bash
alembic revision --autogenerate -m "create knowledge table"

alembic upgrade head
```

---

# 41. Repository 设计

例如：

```text
knowledge_repository.py
```

负责：

```text
get_by_id()
list()
create()
update()
delete()
count()
exists()
```

不要在 Repository 里写：

```text
“这个知识点是否应该合并”
```

这种属于 Service / Agent 的业务逻辑。

---

# 42. Service 设计

例如：

```text
knowledge_service.py
```

负责：

```text
create_knowledge()
update_knowledge()
delete_knowledge()
get_knowledge()
list_knowledge()
```

例如：

```text
创建知识点
 ↓
检查名称
 ↓
校验数据
 ↓
Repository.create()
 ↓
返回
```

---

# 43. 不要让 Router 直接访问 Repository

禁止：

```python
@router.get(...)
def xxx(db):
    knowledge = db.query(...)
```

正确：

```text
Router
 ↓
Service
 ↓
Repository
```

这样后面 Agent 也能复用 Service。

---

# 44. Agent 扩展设计

V1.0 不实现 Agent。

但是必须预留：

```text
agent/
```

未来：

```text
agent/
├── graph/
│   ├── knowledge_graph.py
│   ├── question_graph.py
│   └── import_graph.py
│
├── agents/
│   ├── document_agent.py
│   ├── knowledge_agent.py
│   ├── dedup_agent.py
│   ├── relation_agent.py
│   ├── question_agent.py
│   └── evaluate_agent.py
│
├── tools/
│   ├── knowledge_tool.py
│   ├── question_tool.py
│   ├── vector_tool.py
│   └── document_tool.py
│
├── prompts/
│
└── state/
```

---

# 45. Agent 与业务后端的边界

这是整个项目非常重要的设计。

不要设计成：

```text
Agent
 ↓
直接 SQL
```

正确：

```text
Agent
 ↓
Tool
 ↓
Service
 ↓
Repository
 ↓
MySQL
```

也就是说 Agent 不知道：

```text
SQLAlchemy
MySQL Session
```

Agent 只知道：

```text
create_knowledge()
search_knowledge()
create_question()
get_question_pool()
```

---

# 46. 后续 Knowledge Agent

例如：

```text
KnowledgeExtractAgent
```

输入：

```text
文档文本
```

输出结构化：

```json
{
  "name": "Java线程池",
  "summary": "...",
  "difficulty": 2,
  "keywords": [
    "ThreadPoolExecutor",
    "核心线程数"
  ]
}
```

然后调用：

```text
KnowledgeTool
```

最终：

```text
KnowledgeService
```

负责保存。

---

# 47. 后续 Question Agent

最终：

```text
QuestionDecisionAgent
```

先调用：

```text
get_question_pool()
```

判断：

```text
现有题目够不够？
```

够：

```text
直接使用已有题目
```

不够：

```text
QuestionGenerateAgent
```

然后：

```text
QuestionEvaluateAgent
```

最后：

```text
QuestionService
```

保存。

---

# 48. 非常重要：不要让 LLM 决定所有事情

例如：

```text
题目数量是否不足
```

应该普通代码判断：

```python
if question_count < min_count:
    need_generate = True
```

而不是：

```text
LLM：
“我觉得题目可能不够。”
```

LLM 只用于：

```text
语义理解
语义判断
内容生成
内容评价
```

确定性逻辑使用普通代码。

---

# 49. 后续向量数据库扩展

以后知识点去重：

```text
knowledge
 ↓
embedding
 ↓
vector db
 ↓
top K
 ↓
similarity
```

然后：

```text
相似度很高
 ↓
直接判断重复

相似度很低
 ↓
直接新增

中间区域
 ↓
交给 LLM 判断
```

注意：

**不要每一个知识点都调用 LLM 判断重复。**

这样成本高，而且没有必要。

---

# 50. 数据库唯一性约束

必须增加必要的 UNIQUE。

例如：

```text
admin_user.username
```

唯一。

```text
question_knowledge(question_id, knowledge_id)
```

唯一。

```text
knowledge_relation(source_knowledge_id,
                   target_knowledge_id,
                   relation_type)
```

唯一。

同时应用层也需要检查。

---

# 51. 事务设计

以下场景必须事务：

### 创建题目

```text
Question
+
Options
+
Knowledge Relations
```

### 删除题目

```text
Question
+
Options
+
Question Knowledge
```

### 修改题目

涉及多张表时统一事务。

原则：

> 一个业务操作要么全部成功，要么全部失败。

---

# 52. 删除策略

第一版尽可能使用：

```text
status
```

进行软删除/禁用。

尤其是：

```text
knowledge
question
```

原因：

未来 AI 分析、生成记录、用户练习记录都可能引用历史数据。

真实系统一般不应该轻易物理删除。

---

# 53. 输入校验

Pydantic Schema 必须进行：

```text
长度限制
枚举限制
数字范围限制
必填检查
字符串清洗
```

例如：

```text
difficulty ∈ [1,3]
page_size ∈ [1,100]
progress ∈ [0,100]
```

不要完全依赖前端校验。

后端必须再次校验。

---

# 54. SQL 注入与数据库安全

不要拼接 SQL：

```python
sql = "SELECT * FROM question WHERE name = '" + keyword + "'"
```

必须使用：

```text
SQLAlchemy 参数绑定
```

用户输入永远视为不可信数据。

---

# 55. 文件上传安全

必须限制：

```text
文件大小
文件扩展名
Content-Type
文件名
保存路径
```

第一版建议支持：

```text
pdf
docx
txt
md
```

暂时不支持：

```text
exe
zip
rar
html
js
```

---

# 56. CORS

开发环境允许：

```text
Vue3 Dev Server
```

生产环境必须限制具体域名。

不要：

```text
allow_origins=["*"]
```

长期用于生产环境。

---

# 57. OpenAPI

FastAPI 自带：

```text
Swagger
ReDoc
```

开发过程中必须保持 API 文档完整。

每个 API：

```text
summary
description
request schema
response schema
error response
```

尽量使用明确的 Pydantic Schema。

---

# 58. 测试要求

V1.0 至少测试：

```text
管理员登录
知识点 CRUD
知识关系
题目 CRUD
题目选项
题目与知识点关联
文件上传
导入任务
```

重点测试：

```text
非法参数
不存在的数据
重复数据
无权限
事务失败
文件过大
非法文件类型
```

---

# 59. Docker

可以准备：

```text
docker-compose.yml
```

但是 V1.0 只需要：

```text
MySQL
```

不需要：

```text
Redis
RabbitMQ
Milvus
Neo4j
```

示意：

```text
FastAPI
   │
   └── MySQL
```

后续逐步增加服务。

---

# 60. README

README 必须包含：

```text
项目介绍

技术栈

环境要求

项目目录

数据库配置

启动方式

数据库迁移

API 文档

测试

Docker 启动

后续 Agent 规划
```

---

# 61. 启动流程

开发环境：

```bash
python -m venv .venv
```

安装：

```bash
pip install -r requirements.txt
```

执行迁移：

```bash
alembic upgrade head
```

启动：

```bash
uvicorn app.main:app --reload
```

Swagger：

```text
/docs
```

---

# 62. 第一阶段开发顺序

不要一次性生成整个项目。

严格按下面顺序开发：

```text
1. 初始化 FastAPI

2. 配置管理

3. MySQL + SQLAlchemy

4. Alembic

5. 基础模型

6. 管理员登录

7. JWT

8. 全局异常处理

9. 统一响应

10. 知识点 CRUD

11. 知识关系

12. 题目 CRUD

13. 题目选项

14. 题目知识点关联

15. 文件上传

16. 导入任务

17. Dashboard

18. 日志

19. 测试

20. Docker

21. README
```

---

# 63. 给 AI 编程助手的开发规则

AI 编程助手在开发本项目时必须遵守：

### 规则 1

不要随意增加依赖。

增加第三方库前先判断是否真的必要。

### 规则 2

不要在 Router 中写业务逻辑。

### 规则 3

不要让 Agent/LLM 直接操作数据库。

### 规则 4

不要把数据库连接信息、JWT Secret、API Key 写死。

### 规则 5

不要使用 `Base.metadata.create_all()` 替代 Alembic。

### 规则 6

所有数据库操作必须经过 SQLAlchemy。

### 规则 7

所有输入参数必须经过 Pydantic 校验。

### 规则 8

多表操作必须考虑事务。

### 规则 9

代码必须考虑空数据、重复数据、资源不存在等情况。

### 规则 10

不要为了“以后可能用到”提前加入 Redis、消息队列、向量数据库。

---

# 64. 明确标记：V1.0 暂时不要做

以下内容不要提前实现：

```text
[暂缓]

Redis
Celery
RabbitMQ
Kafka

Milvus
Qdrant
Neo4j

LangChain
LangGraph

Embedding

RAG

AI 自动生成题目

AI 答案评价

用户端

Flutter

RBAC

WebSocket

微服务
```

---

# 65. 明确标记：虽然暂时不用，但需要预留

这些内容暂时不实现，但代码架构需要预留：

```text
[预留]

Agent
Agent Tool
Agent Task
Vector Search
Embedding
AI Question Generation
AI Evaluation
Task Queue
Object Storage
RBAC
```

预留方法：

```text
使用清晰的 Service 层
使用独立 Repository
使用独立 Import Task
使用统一配置
使用统一异常
使用 request_id
```

而不是：

```text
现在就把所有功能写进去
```

---

# 66. 特别需要注意的架构问题

## 注意事项一：不要把 Service 写成“大杂烩”

禁止：

```text
knowledge_service.py
里面同时处理：

MySQL
文件
LLM
Embedding
HTTP
Agent
```

一个 Service 应该负责一个业务领域。

---

## 注意事项二：不要提前微服务化

当前：

```text
一个 FastAPI
```

完全足够。

---

## 注意事项三：不要把数据库设计成纯 AI 项目

虽然以后有 Agent，但：

```text
knowledge
question
admin
import_task
```

都是稳定业务数据。

数据库应该首先服务业务。

---

## 注意事项四：不要依赖前端做安全校验

所有重要规则后端必须重新检查。

---

## 注意事项五：不要为了实时状态提前上 Redis/WebSocket

V1.0：

```text
HTTP + MySQL
```

已经够用。

---

# 67. 后续 Agent 时代推荐的数据流

最终：

```text
管理员上传 PDF
        ↓
FastAPI
        ↓
创建 import_task
        ↓
Agent Workflow
        ↓
Document Parse
        ↓
Knowledge Extract
        ↓
Knowledge Dedup
        ↓
Knowledge Merge
        ↓
Knowledge Relation
        ↓
Question Coverage
        ↓
Question Generate
        ↓
Question Evaluate
        ↓
Question Save
        ↓
SUCCESS
```

其中：

```text
FastAPI
```

负责系统业务。

```text
LangGraph
```

负责 AI 工作流。

```text
Service
```

负责真正的数据业务。

```text
Repository
```

负责数据库。

---

# 68. 最终后端架构

第一阶段：

```text
                    Vue3
                      │
                      ▼
                  FastAPI
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
      Router        Service      Exception
                      │
                      ▼
                 Repository
                      │
                      ▼
                    MySQL
```

最终：

```text
                         Vue3
                           │
                           ▼
                        FastAPI
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
             业务 Service           Agent
                │                     │
                ▼                  LangGraph
            Repository                │
                │              ┌──────┴──────┐
                ▼              ▼             ▼
              MySQL           Tools          LLM
                                  │
                                  ▼
                             Service Layer
                                  │
                                  ▼
                                MySQL
```

核心原则：

> **FastAPI 是业务系统，Agent 是智能能力，而不是让整个后端变成 Agent。**

---

# 69. V1.0 验收标准

最终后端必须能够完整运行以下流程：

```text
启动项目
 ↓
管理员登录
 ↓
获取 JWT
 ↓
访问 Dashboard
 ↓
创建知识点
 ↓
修改知识点
 ↓
建立知识关系
 ↓
创建面试题
 ↓
创建题目选项
 ↓
关联知识点
 ↓
查询题目
 ↓
上传 PDF/TXT/DOCX/MD
 ↓
创建导入任务
 ↓
查询导入任务状态
```

并满足：

```text
数据库迁移正常
异常处理统一
接口文档正常
测试通过
日志正常
配置与密钥未硬编码
```

完成后才进入：

```text
LangChain
    ↓
LangGraph
    ↓
Agent Workflow
```

---

# 70. 开发结论

当前项目不要追求“一步到位”。

优先保证：

```text
稳定
清晰
可维护
可测试
可扩展
```

而不是：

```text
技术越多越高级
```

V1.0 最核心目标：

> **先建立一个规范的 FastAPI 业务后端。**

在此基础上，再逐步加入：

```text
LangChain
↓
LangGraph
↓
Embedding
↓
Vector DB
↓
Redis
↓
异步任务
```

这样每增加一种技术，都是为了解决一个真实出现的问题，而不是为了堆技术栈。