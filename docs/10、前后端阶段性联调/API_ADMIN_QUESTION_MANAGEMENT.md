# 管理员题库管理 API 文档

## 基础信息

- **Base URL**: `http://localhost:8000/api/v1`
- **认证**: Bearer Token（管理员登录获取）
- **响应格式**: `ApiResponse[code, message, data]`

## 状态枚举

| 枚举 | 值 | 说明 |
|------|----|------|
| QuestionStatus | `pending_review` | 待审核 |
| | `published` | 已发布（可组卷） |
| | `rejected` | 已驳回 |
| | `disabled` | 已下架 |
| TaskStatus | `pending` | 待执行 |
| | `running` | 执行中 |
| | `success` | 全部成功 |
| | `partial_success` | 部分成功 |
| | `failed` | 失败 |

---

## 一、认证

### POST /auth/login
登录获取 Token。`{"username": "admin", "password": "xxx"}`

## 二、题库管理

### GET /question-banks
题库列表（分页、名称搜索、状态筛选）。

### GET /question-banks/{id}
题库详情（含题目数量）。

## 三、知识点管理

### GET /knowledge
知识点列表（分页、关键词、难度、状态、knowledge_base_id 筛选）。

## 四、出题任务

### POST /question-generation/tasks
创建生成任务，后台执行，立即返回 task_id。

**请求**:
```json
{
    "knowledge_id": 1,
    "question_bank_id": 1,
    "question_type": "SINGLE_CHOICE",
    "difficulty": 2,
    "count": 5
}
```

**响应**:
```json
{
    "code": 0,
    "data": {
        "task_id": 1,
        "status": "pending",
        "message": "任务已创建，后台执行中"
    }
}
```

### GET /question-generation/tasks
任务列表（分页、状态筛选）。

### GET /question-generation/tasks/{id}
任务详情（参数、进度、关联题目列表、错误摘要）。

## 五、题目管理

### GET /questions
题目列表（分页、题库/知识点/题型/难度/状态/关键词筛选）。

### GET /questions/{id}
题目详情（含选项、答案、解析、知识点）。

### PUT /questions/{id}
编辑题目。**历史答题保护**: 有答题记录时不能修改题干/选项/答案。

### DELETE /questions/{id}
下架题目（软删除）。

## 六、题目审核

### POST /question-generation/questions/{id}/review
发布或驳回题目。

**请求**: `{"action": "publish", "reason": ""}` 或 `{"action": "reject", "reason": "内容不准确"}`

---

## 调用顺序示例

```
1. POST /auth/login → 获取 token
2. GET /question-banks → 选择题库
3. GET /knowledge → 选择知识点
4. POST /question-generation/tasks → 创建任务
5. GET /question-generation/tasks/{id} → 查看进度
6. GET /questions?status=pending_review → 查看待审核题
7. GET /questions/{id} → 查看题目详情
8. PUT /questions/{id} → 编辑解析
9. POST /question-generation/questions/{id}/review → 发布
10. GET /questions?status=published → 确认已发布
```
