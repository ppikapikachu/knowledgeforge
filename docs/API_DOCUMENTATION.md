# KnowledgeForge API 接口文档

## 1. 概览

### 基础信息

| 项目 | 说明 |
|------|------|
| **基础 URL** | `http://localhost:8000/api/v1` |
| **协议** | HTTP/HTTPS |
| **数据格式** | JSON |
| **认证方式** | JWT Bearer Token（通过 `Authorization` 请求头传递） |

### 认证方式

除登录接口外，所有接口均需要在请求头中携带 JWT 令牌：

```
Authorization: Bearer <access_token>
```

令牌通过调用 `POST /api/v1/auth/login` 接口获取，有效期由服务端配置决定。

---

## 2. 统一响应格式

所有接口均返回统一的 JSON 响应结构：

### 通用响应体 `ApiResponse`

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `int` | 状态码。`0` 表示成功，非 `0` 表示错误 |
| `message` | `string` | 响应消息。成功时为 `"success"`，失败时为错误描述 |
| `data` | `object / array / null` | 响应数据。具体内容取决于接口 |

**示例 — 成功响应：**

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

**示例 — 错误响应：**

```json
{
  "code": 400,
  "message": "参数错误",
  "data": null
}
```

### 分页响应体 `PaginatedData`

分页接口的 `data` 字段遵循以下结构：

| 字段 | 类型 | 说明 |
|------|------|------|
| `items` | `array` | 当前页数据列表 |
| `page` | `int` | 当前页码 |
| `page_size` | `int` | 每页数量 |
| `total` | `int` | 总记录数 |

**示例：**

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

---

## 3. 枚举定义

### 3.1 知识点难度 `KnowledgeDifficulty`

| 值 | 名称 | 说明 |
|----|------|------|
| `1` | EASY | 简单 |
| `2` | MEDIUM | 中等 |
| `3` | HARD | 困难 |

### 3.2 知识点状态 `KnowledgeStatus`

| 值 | 名称 | 说明 |
|----|------|------|
| `1` | ACTIVE | 正常 |
| `0` | DISABLED | 禁用 |

### 3.3 知识点来源类型 `KnowledgeSourceType`

| 值 | 名称 | 说明 |
|----|------|------|
| `"MANUAL"` | MANUAL | 手动创建 |
| `"IMPORT"` | IMPORT | 导入创建 |
| `"AI"` | AI | AI 生成 |

### 3.4 知识点关系类型 `RelationType`

| 值 | 名称 | 说明 |
|----|------|------|
| `"prerequisite"` | PREREQUISITE | 前置依赖关系 |
| `"related"` | RELATED | 相关关系 |
| `"extension"` | EXTENSION | 扩展延伸关系 |
| `"contrast"` | CONTRAST | 对比关系 |

### 3.5 题目类型 `QuestionType`

| 值 | 名称 | 说明 |
|----|------|------|
| `"SINGLE_CHOICE"` | SINGLE_CHOICE | 单选题 |
| `"MULTIPLE_CHOICE"` | MULTIPLE_CHOICE | 多选题 |
| `"TRUE_FALSE"` | TRUE_FALSE | 判断题 |
| `"SHORT_ANSWER"` | SHORT_ANSWER | 简答题 |

### 3.6 题目状态 `QuestionStatus`

| 值 | 名称 | 说明 |
|----|------|------|
| `"DRAFT"` | DRAFT | 草稿 |
| `"PUBLISHED"` | PUBLISHED | 已发布 |
| `"DISABLED"` | DISABLED | 已禁用 |

### 3.7 题目来源类型 `QuestionSourceType`

| 值 | 名称 | 说明 |
|----|------|------|
| `"MANUAL"` | MANUAL | 手动创建 |
| `"IMPORT"` | IMPORT | 导入创建 |
| `"AI"` | AI | AI 生成 |

### 3.8 导入任务状态 `ImportTaskStatus`

| 值 | 名称 | 说明 |
|----|------|------|
| `"PENDING"` | PENDING | 等待中 |
| `"RUNNING"` | RUNNING | 运行中 |
| `"SUCCESS"` | SUCCESS | 完成 |
| `"PARTIAL_SUCCESS"` | PARTIAL_SUCCESS | 部分成功 |
| `"FAILED"` | FAILED | 失败 |
| `"CANCELLED"` | CANCELLED | 已取消 |

---

## 4. 认证管理 `/auth`

### 4.1 管理员登录

- **接口：** `POST /api/v1/auth/login`
- **描述：** 使用用户名和密码登录，返回 JWT 访问令牌。
- **认证：** 不需要

#### 请求参数（Body - JSON）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | `string` | ✅ | 登录账号，长度 1~50 |
| `password` | `string` | ✅ | 密码，长度 1~128 |

#### 响应字段 `data` — `TokenResponse`

| 字段 | 类型 | 说明 |
|------|------|------|
| `access_token` | `string` | JWT 访问令牌 |
| `token_type` | `string` | 令牌类型，默认 `"bearer"` |

#### 请求示例

```json
{
  "username": "admin",
  "password": "123456"
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
}
```

---

### 4.2 获取当前管理员信息

- **接口：** `GET /api/v1/auth/me`
- **描述：** 获取当前已登录管理员的详细信息。
- **认证：** 需要 Bearer Token

#### 请求参数

无。

#### 响应字段 `data` — `AdminInfo`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 管理员 ID |
| `username` | `string` | 登录账号 |
| `nickname` | `string` | 显示昵称 |
| `avatar` | `string / null` | 头像 URL |
| `status` | `int` | 管理员状态 |
| `last_login_at` | `datetime / null` | 最后登录时间 |
| `created_at` | `datetime` | 创建时间 |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "username": "admin",
    "nickname": "超级管理员",
    "avatar": null,
    "status": 1,
    "last_login_at": "2025-01-15T10:30:00",
    "created_at": "2024-12-01T08:00:00"
  }
}
```

---

## 5. 知识点管理 `/knowledge`

### 5.1 获取知识点列表

- **接口：** `GET /api/v1/knowledge`
- **描述：** 分页获取知识点列表，支持按关键词、难度、状态筛选。
- **认证：** 需要 Bearer Token

#### 请求参数（Query）

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `page` | `int` | 否 | `1` | 页码，≥ 1 |
| `page_size` | `int` | 否 | `20` | 每页数量，范围 1~100 |
| `keyword` | `string` | 否 | `null` | 关键词搜索 |
| `difficulty` | `int` | 否 | `null` | 难度筛选，范围 1~3（见枚举 3.1） |
| `status` | `int` | 否 | `null` | 状态筛选，0 或 1（见枚举 3.2） |

#### 响应字段 `data` — `PaginatedData<KnowledgeResponse>`

分页结构中的 `items` 每项字段如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 知识点 ID |
| `name` | `string` | 知识点名称 |
| `summary` | `string / null` | 简要说明 |
| `content` | `string / null` | 完整知识内容 |
| `difficulty` | `int` | 难度（1=简单, 2=中等, 3=困难） |
| `status` | `int` | 状态（1=正常, 0=禁用） |
| `source_type` | `string` | 来源（MANUAL/IMPORT/AI） |
| `source_document` | `string / null` | 来源文档 |
| `keywords` | `array / null` | 关键词列表 |
| `created_at` | `datetime` | 创建时间 |
| `updated_at` | `datetime` | 更新时间 |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "name": "Python 变量与数据类型",
        "summary": "介绍 Python 中的基本变量类型",
        "content": "Python 是一种动态类型语言...",
        "difficulty": 1,
        "status": 1,
        "source_type": "MANUAL",
        "source_document": null,
        "keywords": ["python", "变量", "数据类型"],
        "created_at": "2025-01-10T08:00:00",
        "updated_at": "2025-01-10T08:00:00"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 50
  }
}
```

---

### 5.2 获取知识点详情

- **接口：** `GET /api/v1/knowledge/{knowledge_id}`
- **描述：** 根据 ID 获取知识点详细信息。
- **认证：** 需要 Bearer Token

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `knowledge_id` | `int` | ✅ | 知识点 ID |

#### 响应字段 `data` — `KnowledgeResponse`

同 5.1 中的 `KnowledgeResponse` 字段定义。

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "name": "Python 变量与数据类型",
    "summary": "介绍 Python 中的基本变量类型",
    "content": "Python 是一种动态类型语言...",
    "difficulty": 1,
    "status": 1,
    "source_type": "MANUAL",
    "source_document": null,
    "keywords": ["python", "变量", "数据类型"],
    "created_at": "2025-01-10T08:00:00",
    "updated_at": "2025-01-10T08:00:00"
  }
}
```

---

### 5.3 创建知识点

- **接口：** `POST /api/v1/knowledge`
- **描述：** 创建一个新的知识点。
- **认证：** 需要 Bearer Token

#### 请求参数（Body - JSON）— `KnowledgeCreate`

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | `string` | ✅ | — | 知识点名称，长度 1~200 |
| `summary` | `string` | 否 | `null` | 简要说明，最大 1000 字符 |
| `content` | `string` | 否 | `null` | 完整知识内容 |
| `difficulty` | `int` | 否 | `1` | 难度，范围 1~3（见枚举 3.1） |
| `status` | `int` | 否 | `1` | 状态，0 或 1（见枚举 3.2） |
| `source_type` | `string` | 否 | `"MANUAL"` | 来源（见枚举 3.3） |
| `source_document` | `string` | 否 | `null` | 来源文档，最大 500 字符 |
| `keywords` | `array` | 否 | `null` | 关键词列表 |

#### 响应字段 `data` — `KnowledgeResponse`

同 5.1 中的 `KnowledgeResponse` 字段定义。

#### 请求示例

```json
{
  "name": "Python 变量与数据类型",
  "summary": "介绍 Python 中的基本变量类型",
  "content": "Python 是一种动态类型语言，变量不需要声明类型...",
  "difficulty": 1,
  "status": 1,
  "source_type": "MANUAL",
  "keywords": ["python", "变量", "数据类型"]
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "name": "Python 变量与数据类型",
    "summary": "介绍 Python 中的基本变量类型",
    "content": "Python 是一种动态类型语言，变量不需要声明类型...",
    "difficulty": 1,
    "status": 1,
    "source_type": "MANUAL",
    "source_document": null,
    "keywords": ["python", "变量", "数据类型"],
    "created_at": "2025-01-10T08:00:00",
    "updated_at": "2025-01-10T08:00:00"
  }
}
```

---

### 5.4 更新知识点

- **接口：** `PUT /api/v1/knowledge/{knowledge_id}`
- **描述：** 更新指定知识点的信息。仅传入需要更新的字段即可。
- **认证：** 需要 Bearer Token

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `knowledge_id` | `int` | ✅ | 知识点 ID |

#### 请求参数（Body - JSON）— `KnowledgeUpdate`

所有字段均为可选，仅传入需要修改的字段：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `string` | 否 | 知识点名称，长度 1~200 |
| `summary` | `string` | 否 | 简要说明，最大 1000 字符 |
| `content` | `string` | 否 | 完整知识内容 |
| `difficulty` | `int` | 否 | 难度，范围 1~3 |
| `status` | `int` | 否 | 状态，0 或 1 |
| `source_type` | `string` | 否 | 来源 |
| `source_document` | `string` | 否 | 来源文档，最大 500 字符 |
| `keywords` | `array` | 否 | 关键词列表 |

#### 响应字段 `data` — `KnowledgeResponse`

同 5.1 中的 `KnowledgeResponse` 字段定义。

#### 请求示例

```json
{
  "name": "Python 变量与数据类型（修订版）",
  "difficulty": 2
}
```

---

### 5.5 删除知识点

- **接口：** `DELETE /api/v1/knowledge/{knowledge_id}`
- **描述：** 禁用指定知识点（软删除，将状态设为禁用）。
- **认证：** 需要 Bearer Token

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `knowledge_id` | `int` | ✅ | 知识点 ID |

#### 响应字段 `data` — `KnowledgeResponse`

同 5.1 中的 `KnowledgeResponse` 字段定义（状态将变为 `0`）。

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "name": "Python 变量与数据类型",
    "status": 0,
    ...
  }
}
```

---

### 5.6 获取知识点关系列表

- **接口：** `GET /api/v1/knowledge/{knowledge_id}/relations`
- **描述：** 获取指定知识点的所有关系。
- **认证：** 需要 Bearer Token

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `knowledge_id` | `int` | ✅ | 知识点 ID |

#### 响应字段 `data` — `KnowledgeRelationResponse[]`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 关系 ID |
| `source_knowledge_id` | `int` | 源知识点 ID |
| `target_knowledge_id` | `int` | 目标知识点 ID |
| `relation_type` | `string` | 关系类型（见枚举 3.4） |
| `target_knowledge_name` | `string / null` | 目标知识点名称 |
| `created_at` | `datetime` | 创建时间 |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 1,
      "source_knowledge_id": 1,
      "target_knowledge_id": 2,
      "relation_type": "prerequisite",
      "target_knowledge_name": "Python 基础语法",
      "created_at": "2025-01-10T09:00:00"
    }
  ]
}
```

---

### 5.7 创建知识点关系

- **接口：** `POST /api/v1/knowledge/{knowledge_id}/relations`
- **描述：** 为指定知识点创建一条关系。
- **认证：** 需要 Bearer Token

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `knowledge_id` | `int` | ✅ | 源知识点 ID |

#### 请求参数（Body - JSON）— `KnowledgeRelationCreate`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `target_knowledge_id` | `int` | ✅ | 目标知识点 ID |
| `relation_type` | `string` | ✅ | 关系类型（见枚举 3.4） |

#### 响应字段 `data` — `KnowledgeRelationResponse`

同 5.6 中的字段定义。

#### 请求示例

```json
{
  "target_knowledge_id": 2,
  "relation_type": "prerequisite"
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "source_knowledge_id": 1,
    "target_knowledge_id": 2,
    "relation_type": "prerequisite",
    "target_knowledge_name": "Python 基础语法",
    "created_at": "2025-01-10T09:00:00"
  }
}
```

---

### 5.8 删除知识点关系

- **接口：** `DELETE /api/v1/knowledge/{knowledge_id}/relations/{relation_id}`
- **描述：** 删除指定知识点的指定关系。
- **认证：** 需要 Bearer Token

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `knowledge_id` | `int` | ✅ | 知识点 ID |
| `relation_id` | `int` | ✅ | 关系 ID |

#### 响应示例

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

## 6. 题目管理 `/questions`

### 6.1 获取题目列表

- **接口：** `GET /api/v1/questions`
- **描述：** 分页获取题目列表，支持多种筛选条件。
- **认证：** 需要 Bearer Token

#### 请求参数（Query）

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `page` | `int` | 否 | `1` | 页码，≥ 1 |
| `page_size` | `int` | 否 | `20` | 每页数量，范围 1~100 |
| `question_type` | `string` | 否 | `null` | 题型筛选（见枚举 3.5） |
| `difficulty` | `int` | 否 | `null` | 难度筛选，范围 1~3 |
| `status` | `string` | 否 | `null` | 状态筛选（见枚举 3.6） |
| `knowledge_id` | `int` | 否 | `null` | 按关联知识点 ID 筛选 |
| `source_type` | `string` | 否 | `null` | 来源筛选（见枚举 3.7） |
| `keyword` | `string` | 否 | `null` | 关键词搜索 |

#### 响应字段 `data` — `PaginatedData<QuestionResponse>`

分页结构中的 `items` 每项字段如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 题目 ID |
| `question_type` | `string` | 题型（见枚举 3.5） |
| `content` | `string` | 题目内容 |
| `answer` | `string` | 标准答案 |
| `analysis` | `string / null` | 题目解析 |
| `difficulty` | `int` | 难度（1=简单, 2=中等, 3=困难） |
| `status` | `string` | 状态（见枚举 3.6） |
| `source_type` | `string` | 来源（见枚举 3.7） |
| `quality_score` | `decimal / null` | 质量评分（0~100） |
| `used_count` | `int` | 使用次数 |
| `correct_count` | `int` | 正确次数 |
| `options` | `OptionResponse[]` | 选项列表（选择题/判断题时有值） |
| `knowledge_ids` | `int[]` | 关联知识点 ID 列表 |
| `created_at` | `datetime` | 创建时间 |
| `updated_at` | `datetime` | 更新时间 |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "question_type": "SINGLE_CHOICE",
        "content": "Python 中哪个关键字用于定义函数？",
        "answer": "B",
        "analysis": "def 是 Python 中定义函数的关键字",
        "difficulty": 1,
        "status": "PUBLISHED",
        "source_type": "MANUAL",
        "quality_score": 85.5,
        "used_count": 10,
        "correct_count": 8,
        "options": [
          {
            "id": 1,
            "question_id": 1,
            "option_key": "A",
            "option_content": "class",
            "is_correct": 0,
            "sort_order": 0,
            "created_at": "2025-01-10T08:00:00"
          },
          {
            "id": 2,
            "question_id": 1,
            "option_key": "B",
            "option_content": "def",
            "is_correct": 1,
            "sort_order": 1,
            "created_at": "2025-01-10T08:00:00"
          }
        ],
        "knowledge_ids": [1, 3],
        "created_at": "2025-01-10T08:00:00",
        "updated_at": "2025-01-10T08:00:00"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 100
  }
}
```

---

### 6.2 获取题目详情

- **接口：** `GET /api/v1/questions/{question_id}`
- **描述：** 根据 ID 获取题目详细信息，包含选项和关联知识点。
- **认证：** 需要 Bearer Token

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question_id` | `int` | ✅ | 题目 ID |

#### 响应字段 `data` — `QuestionResponse`

同 6.1 中的 `QuestionResponse` 字段定义。

---

### 6.3 创建题目

- **接口：** `POST /api/v1/questions`
- **描述：** 创建一道新题目，支持选项和知识点关联。操作在事务中执行。
- **认证：** 需要 Bearer Token

#### 请求参数（Body - JSON）— `QuestionCreate`

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `question_type` | `string` | ✅ | — | 题型（见枚举 3.5） |
| `content` | `string` | ✅ | — | 题目内容 |
| `answer` | `string` | ✅ | — | 标准答案 |
| `analysis` | `string` | 否 | `null` | 题目解析 |
| `difficulty` | `int` | 否 | `1` | 难度，范围 1~3 |
| `status` | `string` | 否 | `"DRAFT"` | 状态（见枚举 3.6） |
| `source_type` | `string` | 否 | `"MANUAL"` | 来源（见枚举 3.7） |
| `quality_score` | `float` | 否 | `null` | 质量评分，范围 0~100 |
| `options` | `OptionCreate[]` | 否 | `null` | 选项列表（选择题必填） |
| `knowledge_ids` | `int[]` | 否 | `null` | 关联知识点 ID 列表 |

#### 选项参数 `OptionCreate`

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `option_key` | `string` | ✅ | — | 选项标识（如 A/B/C/D），长度 1~10 |
| `option_content` | `string` | ✅ | — | 选项内容 |
| `is_correct` | `int` | 否 | `0` | 是否正确答案：`1`=正确，`0`=错误 |
| `sort_order` | `int` | 否 | `0` | 排序序号，≥ 0 |

#### 题型校验规则

| 题型 | 选项要求 | 答案要求 |
|------|----------|----------|
| `SINGLE_CHOICE` | 至少 2 个选项 | 必须有且仅有 1 个正确答案 |
| `MULTIPLE_CHOICE` | 至少 2 个选项 | 至少 1 个正确答案 |
| `TRUE_FALSE` | 不应有选项 | 答案必须为 `"TRUE"` 或 `"FALSE"` |
| `SHORT_ANSWER` | 不应有选项 | 无特殊限制 |

#### 响应字段 `data` — `QuestionResponse`

同 6.1 中的 `QuestionResponse` 字段定义。

#### 请求示例（单选题）

```json
{
  "question_type": "SINGLE_CHOICE",
  "content": "Python 中哪个关键字用于定义函数？",
  "answer": "B",
  "analysis": "def 是 Python 中定义函数的关键字",
  "difficulty": 1,
  "status": "PUBLISHED",
  "source_type": "MANUAL",
  "quality_score": 85.5,
  "options": [
    { "option_key": "A", "option_content": "class", "is_correct": 0, "sort_order": 0 },
    { "option_key": "B", "option_content": "def", "is_correct": 1, "sort_order": 1 },
    { "option_key": "C", "option_content": "function", "is_correct": 0, "sort_order": 2 },
    { "option_key": "D", "option_content": "func", "is_correct": 0, "sort_order": 3 }
  ],
  "knowledge_ids": [1, 3]
}
```

#### 请求示例（判断题）

```json
{
  "question_type": "TRUE_FALSE",
  "content": "Python 是一种编译型语言。",
  "answer": "FALSE",
  "analysis": "Python 是解释型语言",
  "difficulty": 1,
  "status": "DRAFT"
}
```

---

### 6.4 更新题目

- **接口：** `PUT /api/v1/questions/{question_id}`
- **描述：** 更新题目信息，包括选项和知识点关联。操作在事务中执行。
- **认证：** 需要 Bearer Token

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question_id` | `int` | ✅ | 题目 ID |

#### 请求参数（Body - JSON）— `QuestionUpdate`

所有字段均为可选，仅传入需要修改的字段：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question_type` | `string` | 否 | 题型（见枚举 3.5） |
| `content` | `string` | 否 | 题目内容 |
| `answer` | `string` | 否 | 标准答案 |
| `analysis` | `string` | 否 | 题目解析 |
| `difficulty` | `int` | 否 | 难度，范围 1~3 |
| `status` | `string` | 否 | 状态（见枚举 3.6） |
| `source_type` | `string` | 否 | 来源（见枚举 3.7） |
| `quality_score` | `float` | 否 | 质量评分，范围 0~100 |
| `options` | `OptionCreate[]` | 否 | 选项列表（替换全部选项） |
| `knowledge_ids` | `int[]` | 否 | 关联知识点 ID 列表（替换全部关联） |

> **注意：** 更新 `options` 和 `knowledge_ids` 时会替换原有数据。

#### 响应字段 `data` — `QuestionResponse`

同 6.1 中的 `QuestionResponse` 字段定义。

---

### 6.5 删除题目

- **接口：** `DELETE /api/v1/questions/{question_id}`
- **描述：** 禁用指定题目（软删除，将状态设为 `DISABLED`）。
- **认证：** 需要 Bearer Token

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question_id` | `int` | ✅ | 题目 ID |

#### 响应字段 `data` — `QuestionResponse`

同 6.1 中的 `QuestionResponse` 字段定义（状态将变为 `"DISABLED"`）。

---

## 7. 导入任务 `/import-tasks`

### 7.1 上传文件创建导入任务

- **接口：** `POST /api/v1/import-tasks`
- **描述：** 上传文档文件创建导入任务。支持的文件格式：`pdf`、`docx`、`txt`、`md`。
- **认证：** 需要 Bearer Token
- **Content-Type：** `multipart/form-data`

#### 请求参数（Form Data）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | `File` | ✅ | 上传的文件（支持 pdf/docx/txt/md） |

#### 响应字段 `data`

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | `int` | 新创建的任务 ID |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": 1
  }
}
```

---

### 7.2 获取导入任务列表

- **接口：** `GET /api/v1/import-tasks`
- **描述：** 分页获取导入任务列表。
- **认证：** 需要 Bearer Token

#### 请求参数（Query）

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `page` | `int` | 否 | `1` | 页码，≥ 1 |
| `page_size` | `int` | 否 | `20` | 每页数量，范围 1~100 |
| `status` | `string` | 否 | `null` | 任务状态筛选（见枚举 3.8） |

#### 响应字段 `data` — `PaginatedData<ImportTaskResponse>`

分页结构中的 `items` 每项字段如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 任务 ID |
| `file_name` | `string` | 原始文件名 |
| `file_path` | `string` | 服务器保存路径 |
| `file_size` | `int` | 文件大小（字节） |
| `file_type` | `string` | 文件类型（如 pdf、docx 等） |
| `status` | `string` | 任务状态（见枚举 3.8） |
| `progress` | `int` | 进度百分比（0~100） |
| `current_step` | `string / null` | 当前处理阶段描述 |
| `error_message` | `string / null` | 错误信息（失败时） |
| `created_by` | `int` | 创建管理员 ID |
| `started_at` | `datetime / null` | 任务开始时间 |
| `finished_at` | `datetime / null` | 任务完成时间 |
| `created_at` | `datetime` | 创建时间 |
| `updated_at` | `datetime` | 更新时间 |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "file_name": "Python基础教程.pdf",
        "file_path": "/uploads/2025/01/10/abc123.pdf",
        "file_size": 1048576,
        "file_type": "pdf",
        "status": "SUCCESS",
        "progress": 100,
        "current_step": null,
        "error_message": null,
        "created_by": 1,
        "started_at": "2025-01-10T08:00:05",
        "finished_at": "2025-01-10T08:05:30",
        "created_at": "2025-01-10T08:00:00",
        "updated_at": "2025-01-10T08:05:30"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 5
  }
}
```

---

### 7.3 获取导入任务详情

- **接口：** `GET /api/v1/import-tasks/{task_id}`
- **描述：** 根据 ID 获取导入任务详细信息。
- **认证：** 需要 Bearer Token

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | `int` | ✅ | 任务 ID |

#### 响应字段 `data` — `ImportTaskResponse`

同 7.2 中的 `ImportTaskResponse` 字段定义。

---

### 7.4 模拟任务进度（测试用）

- **接口：** `POST /api/v1/import-tasks/{task_id}/simulate`
- **描述：** 模拟推进导入任务进度，仅用于 V1.0 测试。
- **认证：** 需要 Bearer Token

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | `int` | ✅ | 任务 ID |

#### 响应字段 `data` — `ImportTaskResponse`

同 7.2 中的 `ImportTaskResponse` 字段定义。调用后任务进度会向前推进一个阶段。

---

## 8. 仪表盘 `/dashboard`

### 8.1 获取仪表盘概览

- **接口：** `GET /api/v1/dashboard/overview`
- **描述：** 获取系统统计数据，包括知识点、题目、导入任务等数量。
- **认证：** 需要 Bearer Token

#### 请求参数

无。

#### 响应字段 `data` — `DashboardOverview`

| 字段 | 类型 | 说明 |
|------|------|------|
| `knowledge_count` | `int` | 知识点总数 |
| `question_count` | `int` | 题目总数 |
| `single_choice_count` | `int` | 单选题数量 |
| `multiple_choice_count` | `int` | 多选题数量 |
| `true_false_count` | `int` | 判断题数量 |
| `short_answer_count` | `int` | 简答题数量 |
| `import_task_count` | `int` | 导入任务总数 |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "knowledge_count": 150,
    "question_count": 520,
    "single_choice_count": 200,
    "multiple_choice_count": 120,
    "true_false_count": 100,
    "short_answer_count": 100,
    "import_task_count": 15
  }
}
```

---

## 9. 接口总览

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| `POST` | `/api/v1/auth/login` | 管理员登录 | ❌ |
| `GET` | `/api/v1/auth/me` | 获取当前管理员信息 | ✅ |
| `GET` | `/api/v1/knowledge` | 获取知识点列表 | ✅ |
| `GET` | `/api/v1/knowledge/{knowledge_id}` | 获取知识点详情 | ✅ |
| `POST` | `/api/v1/knowledge` | 创建知识点 | ✅ |
| `PUT` | `/api/v1/knowledge/{knowledge_id}` | 更新知识点 | ✅ |
| `DELETE` | `/api/v1/knowledge/{knowledge_id}` | 删除知识点（软删除） | ✅ |
| `GET` | `/api/v1/knowledge/{knowledge_id}/relations` | 获取知识点关系列表 | ✅ |
| `POST` | `/api/v1/knowledge/{knowledge_id}/relations` | 创建知识点关系 | ✅ |
| `DELETE` | `/api/v1/knowledge/{knowledge_id}/relations/{relation_id}` | 删除知识点关系 | ✅ |
| `GET` | `/api/v1/questions` | 获取题目列表 | ✅ |
| `GET` | `/api/v1/questions/{question_id}` | 获取题目详情 | ✅ |
| `POST` | `/api/v1/questions` | 创建题目 | ✅ |
| `PUT` | `/api/v1/questions/{question_id}` | 更新题目 | ✅ |
| `DELETE` | `/api/v1/questions/{question_id}` | 删除题目（软删除） | ✅ |
| `POST` | `/api/v1/import-tasks` | 上传文件创建导入任务 | ✅ |
| `GET` | `/api/v1/import-tasks` | 获取导入任务列表 | ✅ |
| `GET` | `/api/v1/import-tasks/{task_id}` | 获取导入任务详情 | ✅ |
| `POST` | `/api/v1/import-tasks/{task_id}/simulate` | 模拟任务进度（测试用） | ✅ |
| `GET` | `/api/v1/dashboard/overview` | 获取仪表盘概览 | ✅ |

---

## 10. 附录：数据模型关系图

```
管理员 (AdminUser)
  │
  ├── 创建 → 知识点 (Knowledge)
  │              ├── 属性: name, summary, content, difficulty, status, source_type, keywords
  │              └── 关系 → 知识点关系 (KnowledgeRelation)
  │                           ├── 关系类型: prerequisite / related / extension / contrast
  │                           └── 连接: source_knowledge ↔ target_knowledge
  │
  ├── 创建 → 题目 (Question)
  │              ├── 属性: question_type, content, answer, analysis, difficulty, status
  │              ├── 包含 → 选项 (Option) [选择题]
  │              └── 关联 → 知识点 (多对多)
  │
  └── 创建 → 导入任务 (ImportTask)
                 ├── 上传文件: pdf / docx / txt / md
                 └── 状态流转: PENDING → RUNNING → SUCCESS / FAILED / CANCELLED
```
