# AI 出题链路故障修复与题目状态统一 报告

## 一、根本原因

### 问题1：`'knowledge_base_id' is an invalid keyword argument for Question`

**位置**: `app/services/background_runner.py:72`

**原因**: 创建 `Question` 对象时传入了 `knowledge_base_id=1`，但 `Question` 模型没有此字段。`knowledge_base_id` 是 `Knowledge` 模型的字段，不是 `Question` 的字段。Question 与 Knowledge 之间通过 `question_knowledge` 关联表建立关系，而非直接字段。

**修复**: 移除 `knowledge_base_id=1` 参数。

### 问题2：题目状态大小写不一致

**位置**: 4 个文件使用 `DRAFT/PUBLISHED/DISABLED`（大写），与其他文件的 `pending_review/published/disabled`（小写）不一致。

**修复**: 统一为小写格式。

## 二、修改文件

| 文件 | 修改内容 |
|------|----------|
| `app/services/background_runner.py` | 移除 `knowledge_base_id=1` 参数 |
| `app/schemas/question.py` | 状态枚举值改为小写 |
| `app/repositories/question_repository.py` | `"DISABLED"` → `"disabled"` |
| `app/services/question_service.py` | `"DRAFT"` → `"pending_review"` |
| `tests/test_question.py` | 断言 `"DISABLED"` → `"disabled"` |

## 三、数据库变更

无。仅代码修改。

## 四、题目状态统一

统一为小写：`pending_review` / `published` / `rejected` / `disabled`

| 之前 | 之后 |
|------|------|
| `DRAFT` | `pending_review` |
| `PUBLISHED` | `published` |
| `DISABLED` | `disabled` |
| `rejected` | `rejected`（不变） |

## 五、修复前后

| | 修复前 | 修复后 |
|---|---|---|
| 创建生成任务 | 任务创建成功但后台执行失败 | 后台执行成功，题目正确保存 |
| 题目状态 | 大小写混用 | 统一小写 |
| Question 创建 | `knowledge_base_id` 参数错误 | 移除错误参数 |

## 六、测试结果

```
103 passed, 0 failed
```

## 七、仍存在的问题

1. AI 解析生成未实现
2. 向量语义去重未接入
3. 任务进程重启恢复未实现
