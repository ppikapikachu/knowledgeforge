# AI 面试题库系统 - FastAPI 后端 V1.0

AI 驱动的面试题库和知识库管理系统后端 API。

## 技术栈

- **Python** 3.11+
- **FastAPI** - Web 框架
- **SQLAlchemy 2.x** - ORM
- **Alembic** - 数据库迁移
- **Pydantic** - 数据验证
- **MySQL 8.x** - 数据库
- **JWT** - 身份认证
- **pytest** - 测试框架

## 环境要求

- Python 3.11+
- MySQL 8.0+
- pip

## 项目结构

```
backend/
├── app/
│   ├── main.py                  # 应用入口
│   ├── api/v1/                  # API 路由
│   │   ├── auth.py              # 认证 API
│   │   ├── knowledge.py         # 知识点 API
│   │   ├── question.py          # 题目 API
│   │   ├── import_task.py       # 导入任务 API
│   │   └── dashboard.py         # 仪表盘 API
│   ├── core/                    # 核心模块
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # 数据库连接
│   │   ├── security.py          # 安全工具
│   │   ├── exceptions.py        # 异常定义
│   │   └── logging.py           # 日志配置
│   ├── models/                  # SQLAlchemy 模型
│   ├── schemas/                 # Pydantic Schema
│   ├── repositories/            # 数据访问层
│   ├── services/                # 业务逻辑层
│   ├── dependencies/            # FastAPI 依赖
│   ├── middleware/               # 中间件
│   └── utils/                   # 工具函数
├── migrations/                  # Alembic 迁移
├── tests/                       # 测试文件
├── scripts/                     # 脚本工具
├── uploads/                     # 上传文件目录
├── .env.example                 # 环境变量示例
├── alembic.ini                  # Alembic 配置
├── requirements.txt             # Python 依赖
├── Dockerfile                   # Docker 配置
├── docker-compose.yml           # Docker Compose
└── README.md                    # 本文档
```

## 快速开始

### 1. 克隆项目

```bash
cd D:\pythonproject\knowledgeforge\backend
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
```

主要配置项：

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=interview_agent
MYSQL_USERNAME=root
MYSQL_PASSWORD=your_password

JWT_SECRET_KEY=your-secret-key-change-in-production
```

### 5. 创建数据库

```sql
CREATE DATABASE interview_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

### 6. 执行数据库迁移

```bash
alembic upgrade head
```

### 7. 创建管理员账号

```bash
python scripts/create_admin.py --username admin --password admin123
```

### 8. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 9. 访问 API 文档

打开浏览器访问：

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## 运行测试

### 执行全部测试

```bash
cd backend
python -m pytest tests/ -v
```

### 执行特定测试

```bash
# 认证测试
python -m pytest tests/test_auth.py -v

# 知识点测试
python -m pytest tests/test_knowledge.py -v

# 题目测试
python -m pytest tests/test_question.py -v

# 导入任务测试
python -m pytest tests/test_import_task.py -v

# 仪表盘测试
python -m pytest tests/test_dashboard.py -v
```

### 测试数据库

测试使用独立的测试数据库 `interview_agent_test`，需要提前创建：

```sql
CREATE DATABASE interview_agent_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

## API Smoke Test

### PowerShell 脚本

```powershell
cd backend
.\scripts\smoke_test.ps1
```

### Bash 脚本

```bash
cd backend
chmod +x scripts/smoke_test.sh
./scripts/smoke_test.sh
```

### 环境变量配置

脚本支持通过环境变量配置用户名和密码：

```powershell
$env:SMOKE_TEST_USERNAME = "admin"
$env:SMOKE_TEST_PASSWORD = "admin123"
```

## API 列表

### 认证管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 管理员登录 |
| GET | `/api/v1/auth/me` | 获取当前管理员信息 |

### 知识点管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/knowledge` | 获取知识点列表 |
| GET | `/api/v1/knowledge/{id}` | 获取知识点详情 |
| POST | `/api/v1/knowledge` | 创建知识点 |
| PUT | `/api/v1/knowledge/{id}` | 更新知识点 |
| DELETE | `/api/v1/knowledge/{id}` | 删除知识点（软删除） |
| GET | `/api/v1/knowledge/{id}/relations` | 获取知识点关系 |
| POST | `/api/v1/knowledge/{id}/relations` | 创建知识点关系 |
| DELETE | `/api/v1/knowledge/{id}/relations/{relation_id}` | 删除知识点关系 |

### 题目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/questions` | 获取题目列表 |
| GET | `/api/v1/questions/{id}` | 获取题目详情 |
| POST | `/api/v1/questions` | 创建题目 |
| PUT | `/api/v1/questions/{id}` | 更新题目 |
| DELETE | `/api/v1/questions/{id}` | 删除题目（软删除） |

### 导入任务

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/import-tasks` | 上传文件创建任务 |
| GET | `/api/v1/import-tasks` | 获取任务列表 |
| GET | `/api/v1/import-tasks/{id}` | 获取任务详情 |
| POST | `/api/v1/import-tasks/{id}/simulate` | 模拟任务进度 |

### 仪表盘

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/dashboard/overview` | 获取统计数据 |

## 数据库表

| 表名 | 说明 |
|------|------|
| `admin_user` | 管理员表 |
| `knowledge` | 知识点表 |
| `knowledge_relation` | 知识点关系表 |
| `question` | 题目表 |
| `question_option` | 题目选项表 |
| `question_knowledge` | 题目-知识点关联表 |
| `knowledge_import_task` | 导入任务表 |

## Docker 部署

### 使用 Docker Compose

```bash
cd backend
docker-compose up -d
```

这将启动：
- MySQL 8.0 数据库（端口 3306）
- FastAPI 应用（端口 8000）

### 单独构建 Docker 镜像

```bash
docker build -t interview-agent-api .
docker run -p 8000:8000 --env-file .env interview-agent-api
```

## 统一响应格式

### 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

### 列表响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [ ... ],
    "page": 1,
    "page_size": 20,
    "total": 100
  }
}
```

### 错误响应

```json
{
  "code": 40401,
  "message": "知识点不存在",
  "data": null
}
```

## 错误码说明

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 40001 | 数据验证失败 |
| 40101 | 认证失败 |
| 40301 | 权限不足 |
| 40401 | 资源不存在 |
| 40901 | 数据已存在 |
| 42201 | 请求参数验证失败 |
| 50000 | 系统内部错误 |

## 架构说明

```
Router (API 路由)
    ↓
Service (业务逻辑)
    ↓
Repository (数据访问)
    ↓
SQLAlchemy (ORM)
    ↓
MySQL (数据库)
```

## 未来扩展

V1.0 为以下功能预留了扩展点：

- **AI Agent** - 通过 Service 层接口
- **向量搜索** - 通过独立 Repository
- **异步任务** - 通过 Import Task 表
- **用户系统** - 通过独立 User 表

## 常见问题

### Q: 如何重置数据库？

```bash
alembic downgrade base
alembic upgrade head
python scripts/create_admin.py --username admin --password admin123
```

### Q: 如何修改管理员密码？

直接修改数据库或重新运行 create_admin 脚本。

### Q: 测试数据库在哪里配置？

测试使用环境变量 `MYSQL_DATABASE=interview_agent_test`，在 `tests/conftest.py` 中设置。

## 许可证

MIT License
