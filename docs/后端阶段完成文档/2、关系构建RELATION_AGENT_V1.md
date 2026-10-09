# KnowledgeRelationAgent V1.0 开发文档

## 一、概述

本阶段实现 KnowledgeRelationAgent，根据知识点内容判断知识点之间的关系类型（prerequisite / related / extension / contrast）。**只输出关系建议，不写入 knowledge_relation 表。**

```
锚点知识点
      ↓
候选检索（人工提供 / 向量自动检索）
      ↓
LLM 批量关系判断
      ↓
确定性校验（去重/自关联/非法类型/方向标准化）
      ↓
返回关系建议 + 置信度 + 理由
      ↓
saved: false（不写库）
```

---

## 二、目录结构

```
backend/
├── agent/
│   └── knowledge_relation/           # 新增
│       ├── __init__.py
│       ├── schemas.py                # Pydantic 模型
│       ├── prompts.py                # LLM Prompt (v1)
│       ├── validator.py              # 确定性校验器
│       ├── nodes.py                  # LangGraph 节点
│       └── graph.py                  # LangGraph 工作流
│
├── app/api/v1/
│   └── agent_relation.py            # 新增 测试 API
│
└── agent_tests/
    ├── conftest.py                   # 新增 复用测试 fixtures
    └── test_knowledge_relation.py   # 新增 18 个测试用例
```

---

## 三、文件功能

### 3.1 schemas.py — 数据模型

| 模型 | 用途 |
|------|------|
| `RelationKnowledgeInput` | 知识点输入对象（id/name/summary/content/keywords） |
| `KnowledgeRelationJudgement` | 单条判定结果（decision/relation_type/from/to/confidence/reason） |
| `RelationExtractOutput` | LLM 批量结构化输出 |
| `RelationTestRequest` | API 请求（source + candidates + top_k + min_confidence） |
| `RelationTestResponse` | API 响应（统计 + evaluations + saved=false） |

### 3.2 prompts.py — LLM Prompt

- `SYSTEM_PROMPT`：定义四种关系类型、方向规则、判断原则、防幻觉约束
- `USER_PROMPT_TEMPLATE`：锚点 + 候选列表
- `RELATION_PROMPT_VERSION = "v1"`

### 3.3 validator.py — 确定性校验

| 校验规则 | 说明 |
|----------|------|
| NO_RELATION 清空 | 清空 relation_type/from/to |
| relation_type 合法 | 必须是四种之一 |
| 候选 ID 有效 | 必须在候选集合中 |
| 自关联拒绝 | from != to |
| from/to ID 有效 | 必须是锚点或候选 |
| 去重 | 同一候选只保留一条 |
| 置信度范围 | 0~1 |

### 3.4 nodes.py — LangGraph 节点

| 节点 | 功能 |
|------|------|
| `prepare_candidates` | 准备候选（人工/ID/向量检索） |
| `llm_judge` | LLM 批量关系判断 |
| `validate_results` | 确定性校验 |
| `finalize` | 汇总结果 |

### 3.5 graph.py — 工作流

```
START → prepare_candidates → llm_judge → validate_results → finalize → END
```

---

## 四、四种关系类型与方向

| 类型 | 含义 | 方向 |
|------|------|------|
| `prerequisite` | 前置知识 | from=前置 → to=后续 |
| `extension` | 扩展知识 | from=基础 → to=扩展 |
| `related` | 相关知识 | 无方向 |
| `contrast` | 对比知识 | 无方向 |

**特殊值**：`NO_RELATION` — 无关系（必须允许返回）

---

## 五、测试 API

```
POST /api/v1/agent/knowledge-relation/test
```

### 人工候选模式（不访问 Vector DB）

```json
{
    "source_knowledge": {"id": 1, "name": "Java线程池", "summary": "..."},
    "candidates": [
        {"id": 2, "name": "Java多线程", "summary": "..."},
        {"id": 3, "name": "SQL索引", "summary": "..."}
    ],
    "top_k": 10
}
```

### 自动检索模式

```json
{
    "source_knowledge_id": 1,
    "top_k": 10
}
```

### 响应格式

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "source_knowledge_id": 1,
        "retrieval_mode": "provided_candidates",
        "candidate_count": 2,
        "relation_count": 1,
        "no_relation_count": 1,
        "llm_call_count": 1,
        "elapsed_ms": 1500,
        "saved": false,
        "evaluations": [...],
        "errors": []
    }
}
```

**`saved: false` 是硬性要求，服务端固定返回。**

---

## 六、测试结果

```
95 passed, 0 failed
```

### 测试覆盖

| 编号 | 场景 | 结果 |
|------|------|------|
| T01 | prerequisite 正向关系 | ✅ |
| T02 | extension 正向关系 | ✅ |
| T03 | related 关系 | ✅ |
| T04 | contrast 关系 | ✅ |
| T05 | NO_RELATION 清空字段 | ✅ |
| T06 | 自关联拒绝 | ✅ |
| T07 | 非法 relation_type 拒绝 | ✅ |
| T08 | 候选外 ID 拒绝 | ✅ |
| T09 | 重复候选去重 | ✅ |
| T10 | 空候选不调用 LLM | ✅ |
| T11 | from/to 无效 ID 拒绝 | ✅ |
| T12 | 置信度范围校验 | ✅ |
| T16 | 未认证拒绝 | ✅ |
| T17 | 不写 knowledge_relation | ✅ |
| T18 | 原有回归测试 | ✅ 95/95 |

---

## 七、已知限制

1. **LLM 真实判断质量未验证**（需要 LLM API Key 和 20 对人工标注样例）
2. **向量自动检索模式**依赖 FAISS 内存向量库（重启后需重新回填）
3. **批量 LLM 判断**当前一次调用处理所有候选，大候选列表可能超 Token 限制

---

## 八、尚未完成

1. 20 对人工标注样例的质量验证（需要真实 LLM）
2. 接入正式 ImportTask 流程（下一阶段）
3. 关系持久化到 knowledge_relation 表（下一阶段）

---

## 九、下一阶段边界

```
ImportTask 保存知识成功
      ↓
KnowledgeRelationAgent 输出建议
      ↓
关系去重 + 方向校验 + 幂等检查
      ↓
通过 Relation Service 写入 knowledge_relation
```
