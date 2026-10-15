# 管理员 Web 联调 API 就绪报告

## 一、接口盘点结果

| 能力 | 状态 | 说明 |
|------|------|------|
| 题库列表 | ✅ 已有 | `GET /question-banks` |
| 知识点列表 | ✅ 已有 | `GET /knowledge` |
| 创建生成任务 | ✅ 已有 | `POST /question-generation/tasks` |
| 生成任务列表 | ✅ 已有 | `GET /question-generation/tasks` |
| **生成任务详情** | ✅ **新增** | `GET /question-generation/tasks/{id}` |
| 题目列表 | ✅ 已有 | `GET /questions` |
| 题目详情 | ✅ 已有 | `GET /questions/{id}` |
| **题目编辑（含保护）** | ✅ **增强** | `PUT /questions/{id}` |
| 题目审核 | ✅ 已有 | `POST /question-generation/questions/{id}/review` |

## 二、修改文件

| 文件 | 修改内容 |
|------|----------|
| `app/api/v1/question_generation.py` | **重写** 任务详情 API + 后台执行 + 参数校验 |
| `app/api/v1/question.py` | **增强** 历史答题保护 + 解析来源标记 |
| `app/services/background_runner.py` | **新增** `run_generation_in_background` |

## 三、新增接口

### GET /api/v1/question-generation/tasks/{task_id}

返回任务详情：参数、进度、关联题目列表、错误摘要。

### POST /api/v1/question-generation/tasks（增强）

- 参数校验（题库/知识点存在、题型/难度/数量合法）
- 后台线程执行，立即返回 task_id
- 防止任务重复执行

## 四、题目编辑保护规则

| 场景 | 允许修改 |
|------|----------|
| 无答题记录 | 题干/选项/答案/解析/难度 |
| 有答题记录 | 仅解析/难度/元数据 |
| 修改解析 | 自动标记 `explanation_source=manual` |

## 五、任务可靠性

- 后台线程独立 Session
- 异常时标记 `failed` + 错误摘要
- 进程重启后遗留 running 任务会保持（未实现自动恢复）

## 六、测试结果

```
103 passed, 0 failed
```

## 七、curl 冒烟测试

```bash
# 1. 登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 2. 题库列表
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/question-banks

# 3. 创建生成任务
curl -X POST http://localhost:8000/api/v1/question-generation/tasks \
  -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" \
  -d '{"knowledge_id":1,"question_bank_id":1,"question_type":"SINGLE_CHOICE","difficulty":2,"count":3}'

# 4. 查看任务
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/question-generation/tasks/1

# 5. 审核发布
curl -X POST http://localhost:8000/api/v1/question-generation/questions/1/review \
  -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" \
  -d '{"action":"publish"}'
```

## 八、未实现功能

- AI 解析自动生成（`explanation_status` 已预留）
- 普通用户体系（当前使用 admin_user）
- 向量语义去重（当前使用 content_hash）
- 任务进程重启恢复

## 九、API 文档路径

`backend/docs/API_ADMIN_QUESTION_MANAGEMENT.md`
