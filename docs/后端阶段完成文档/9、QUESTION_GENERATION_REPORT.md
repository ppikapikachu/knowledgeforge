# 题目生成、答题统计与评论功能 交付报告

## 一、现状核对

| 检查项 | 结果 |
|--------|------|
| Question 模型 | 有 status/explanation 等基础字段，已扩展 |
| QuestionDecisionAgent | 已有，输出计划格式复用 |
| 普通用户表 | **无**（当前使用 admin_user 兼容，已标注缺口） |
| 任务执行机制 | 使用 threading 后台任务（复用现有） |
| 统一响应/异常 | 复用现有 ApiResponse/BusinessException |

## 二、修改文件清单

### 新增文件（11 个）

| 文件 | 功能 |
|------|------|
| `app/models/question_generation_task.py` | 生成任务模型 |
| `app/models/question_answer_record.py` | 答题记录模型 |
| `app/models/question_comment.py` | 评论模型 |
| `agent/question_generate/__init__.py` | Agent 模块 |
| `agent/question_generate/schemas.py` | 生成 Schema |
| `agent/question_generate/prompts.py` | 出题 Prompt |
| `agent/question_generate/agent.py` | QuestionGenerateAgent |
| `app/api/v1/question_generation.py` | 生成任务 API |
| `app/api/v1/answer.py` | 答题记录 API |
| `app/api/v1/comment.py` | 评论 API |
| `migrations/versions/d4e5f6a7b8c9_...` | 数据库迁移 |

### 修改文件（3 个）

| 文件 | 修改内容 |
|------|----------|
| `app/models/question.py` | 增加 explanation/explanation_status/explanation_source/content_hash/generation_task_id |
| `app/models/__init__.py` | 注册新模型 |
| `app/api/router.py` | 注册新路由 |

## 三、数据库变更

| 变更 | 说明 |
|------|------|
| `question` 新增 5 字段 | explanation, explanation_status, explanation_source, content_hash, generation_task_id |
| `question.status` 默认值 | DRAFT → pending_review |
| `question_generation_task` 新表 | 生成任务跟踪 |
| `question_answer_record` 新表 | 答题记录（含幂等键） |
| `question_comment` 新表 | 题目评论 |

## 四、API 清单

| 接口 | 权限 | 说明 |
|------|------|------|
| `POST /question-generation/tasks` | 管理员 | 创建生成任务 |
| `GET /question-generation/tasks` | 管理员 | 任务列表 |
| `POST /question-generation/questions/{id}/review` | 管理员 | 发布/驳回题目 |
| `POST /answers/submit` | 用户 | 提交答题（幂等+自动判分） |
| `GET /answers/statistics/{id}` | 用户 | 答题统计 |
| `GET /comments/question/{id}` | 用户 | 获取评论 |
| `POST /comments/question/{id}` | 用户 | 发表评论 |
| `DELETE /comments/{id}` | 用户 | 删除自己评论 |
| `POST /comments/{id}/moderate` | 管理员 | 隐藏/恢复评论 |

## 五、题目生命周期

```
AI 生成 → pending_review → 管理员审核 → published → 可组卷
                     ↘ rejected（驳回）
published → disabled（下架）
```

## 六、判分规则

| 题型 | 判分方式 |
|------|----------|
| 单选 | 选项完全匹配 |
| 多选 | 完全匹配（漏选/多选均错） |
| 判断 | 布尔匹配 |
| 简答 | 不自动判分（ungraded） |

## 七、测试结果

```
103 passed, 0 failed
```

## 八、已知限制

1. **无独立普通用户表**：当前使用 admin_user 作为答题用户，正式产品需用户体系
2. **解析生成未实现**：explanation 字段已预留，Agent 待后续开发
3. **向量去重未接入**：使用 content_hash 精确去重，向量去重待接入
4. **统计阈值**：is_sample_sufficient 使用固定 20，待配置化
