# MiMo-Pro 思考模式缓存与并发隔离优化 交付报告

## 一、修改文件

| 文件 | 修改内容 |
|------|----------|
| `agent/common/llm.py` | **重写** 按 thinking 模式缓存 ChatOpenAI 实例（线程安全双重检查锁） |
| `agent/knowledge_extract/nodes.py` | 调用改为 `get_llm(thinking="disabled")` |
| `agent/knowledge_deduplicate/nodes.py` | 调用改为 `get_llm(thinking="enabled")` |
| `agent/knowledge_relation/nodes.py` | 调用改为 `get_llm(thinking="disabled")` |
| `agent_tests/test_llm_cache.py` | **新增** 8 个缓存/隔离测试 |

## 二、模式映射

| 调用位置 | thinking 模式 | 原因 |
|----------|--------------|------|
| KnowledgeExtractAgent | `disabled` | 原文提取，不需要深度推理 |
| KnowledgeDeduplicateAgent | `enabled` | 语义去重/冲突判断，需要推理 |
| KnowledgeRelationAgent | `disabled` | 初期默认，通过测试评估调整 |

## 三、核心设计

```
get_llm(thinking="disabled") → 缓存实例 A（temperature=0.1）
get_llm(thinking="enabled")  → 缓存实例 B（不传 temperature）
```

- **每种模式一个缓存实例**，不为每个 Chunk 创建新实例
- **创建后不修改参数**（线程安全）
- **enabled 不传 temperature**（MiMo 思考模式不支持自定义）
- **双重检查锁**防止并发首次创建重复实例

## 四、测试结果

```
103 passed, 0 failed
  - 原有测试: 95 passed
  - LLM 缓存测试: 8 passed
```

### 缓存测试覆盖

| 测试 | 验证 |
|------|------|
| 同模式返回同一实例 | ✅ |
| 不同模式返回不同实例 | ✅ |
| 非法模式抛出 ValueError | ✅ |
| 并发同模式只创建一个实例 | ✅ |
| 并发不同模式互不干扰 | ✅ |
| extra_body 包含 thinking 配置 | ✅ |
| enabled 不传自定义 temperature | ✅ |
| disabled 使用配置的 temperature | ✅ |

## 五、已知限制

1. `extra_body` 的 HTTP 请求体验证需真实 API 调用（mock 测试仅验证实例配置）
2. MiMo `max_tokens` 与 `max_completion_tokens` 的映射取决于 langchain-openai 版本
3. 多 Worker 进程各自有独立缓存（预期行为）
