# 题库基础能力与 QuestionDecisionAgent 交付报告

## 一、修改文件清单

### 新增文件

| 文件 | 功能 |
|------|------|
| `app/models/question_bank.py` | QuestionBank ORM 模型 |
| `app/schemas/question_bank.py` | 题库 Schema |
| `app/repositories/question_bank_repository.py` | 题库数据访问层 |
| `app/api/v1/question_bank.py` | 题库 CRUD API |
| `app/api/v1/question_plan.py` | 出题计划 API |
| `agent/question_decision/__init__.py` | Agent 模块 |
| `agent/question_decision/schemas.py` | 出题计划 Schema |
| `agent/question_decision/prompts.py` | Prompt 定义 |
| `agent/question_decision/agent.py` | QuestionDecisionAgent 核心逻辑 |
| `migrations/versions/c3d4e5f6a7b8_add_question_bank.py` | 数据库迁移 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `app/models/__init__.py` | 注册 QuestionBank |
| `app/models/question.py` | 新增 `question_bank_id` 外键 |
| `app/schemas/question.py` | Create/Update/Response 增加 `question_bank_id` |
| `app/api/v1/question.py` | 创建题目支持 `question_bank_id`，列表支持筛选 |
| `app/services/question_service.py` | `create_question` 支持 `question_bank_id` |
| `app/repositories/question_repository.py` | 列表支持 `question_bank_id` 过滤 |
| `app/api/router.py` | 注册题库和出题计划路由 |
| `tests/conftest.py` | 测试数据库创建初始题库数据 |

## 二、数据库迁移

- **Revision**: `c3d4e5f6a7b8`
- **新表**: `question_bank`（code 唯一，status 启用/停用）
- **新字段**: `question.question_bank_id`（外键，NOT NULL）
- **存量回填**: 全部回填到"未分类题库"
- **内置题库**: 8 个（java_basic/java_collection/java_concurrency/jvm/android_native/database_basic/distributed_system/uncategorized）
- **幂等**: INSERT IGNORE，重复执行不产生重复记录

## 三、API

### 题库管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/question-banks` | 题库列表（含题目数量） |
| GET | `/api/v1/question-banks/{id}` | 题库详情 |
| POST | `/api/v1/question-banks` | 创建题库 |
| PUT | `/api/v1/question-banks/{id}` | 更新题库 |

### 题目 API 扩展

- `POST /api/v1/questions` 支持 `question_bank_id`（不传默认未分类）
- `GET /api/v1/questions?question_bank_id=1` 按题库筛选

### 出题计划

```
POST /api/v1/question-plans/decision
```

请求示例：
```json
{
    "question_bank_ids": [1, 4],
    "total_question_count": 20,
    "question_types": ["SINGLE_CHOICE", "SHORT_ANSWER"],
    "difficulty_distribution": {"easy": 40, "medium": 40, "hard": 20}
}
```

## 四、QuestionDecisionAgent

- **职责**：把用户练题要求转化为出题计划，不生成题目内容
- **候选检索**：按题库关键词匹配知识点
- **计划分配**：按候选数量比例分配题量
- **校验**：题库存在/启用、题量汇总、知识点有效性
- **不写数据库**：只返回计划

## 五、测试结果

```
103 passed, 0 failed
```

## 六、已知限制

1. 候选知识点检索使用关键词匹配（MVP），后续可接入向量检索
2. 计划分配使用确定性逻辑，未调用 LLM（后续可接入）
3. 题库与知识点无显式关联表，通过关键词匹配
