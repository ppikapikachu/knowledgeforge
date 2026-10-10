# KnowledgeRelationAgent ImportTask 正式集成 V1.0 交付报告

## 一、概述

将已独立测试通过的 KnowledgeRelationAgent 接入正式知识导入流程。导入完成后，自动为本批新增/变更的知识点生成关系，并写入 `knowledge_relation` 表。

```
ImportTask (knowledge_base_id=K)
  → 解析/分块/ExtractAgent → 去重 → 落库 → Embedding 同步
  → 收集 changed_knowledge_ids
  → KnowledgeRelationAgent（同库检索候选）
  → 确定性校验 + 去重
  → RelationRepository 写入 knowledge_relation
  → ImportTask 记录结果
```

---

## 二、改动文件清单

| 文件 | 修改内容 |
|------|----------|
| `app/services/knowledge_import_service.py` | 新增关系生成阶段 `build_relations_for_import` + `retry_relations` + `changed_knowledge_ids` 收集 |
| `app/api/v1/import_task.py` | 新增 `POST /{task_id}/relations/retry` 重试接口 |

---

## 三、RelationAgent 调用位置

在 `execute_import` 的最后阶段（Embedding 同步完成后）：

```
阶段 1~6: 解析→提取→去重→落库（收集 changed_knowledge_ids）
阶段 7:   Embedding 同步
阶段 8:   build_relations_for_import(changed_ids, kb_id, task_id)  ← 这里
```

**执行顺序**：Vector upsert 先于关系检索，确保同批新知识可互相成为候选。

---

## 四、changed_knowledge_ids 收集方式

| 决策 | 是否收集 | 原因 |
|------|----------|------|
| NEW + SUCCESS | ✅ | 新知识点需要生成关系 |
| MERGE + SUCCESS | ✅ | 内容变化需要补充关系 |
| DUPLICATE | ❌ | 未变更，不必重复生成 |
| FAILED | ❌ | 无可靠 ID |

去重排序后逐个处理，每个 ID 只处理一次。

---

## 五、知识库隔离

```
ImportTask.knowledge_base_id = K
  → 锚点校验 knowledge_base_id == K
  → Vector Search over-fetch + 后过滤 == K
  → MySQL 二次校验 == K
  → Agent 判断
  → 写库前再次校验双方 == K
```

不允许 Android 任务为 Java 知识写关系。

---

## 六、关系持久化

- 调用现有 `KnowledgeRelationRepository.create()` 写入
- 幂等：写入前 `check_exists` 检查，唯一约束兜底
- `related`/`contrast` 对称关系：检查反向避免重复
- `prerequisite`/`extension`：按语义方向写入 source→target
- 置信度阈值：`RELATION_MIN_CONFIDENCE = 0.5`（集中配置）

---

## 七、关系阶段重试

```
POST /api/v1/import-tasks/{task_id}/relations/retry
```

- 仅重跑关系阶段，不重复导入知识
- 通过时间范围查找本任务创建的 Knowledge
- 幂等，不会重复创建已有关系

---

## 八、ImportTask 阶段记录

| 阶段 | 进度 | 说明 |
|------|------|------|
| PARSING | 0~10% | 文档解析 |
| EXTRACTING_KNOWLEDGE | 10~50% | LLM 提取 |
| DEDUPLICATING_KNOWLEDGE | 50~75% | 去重 |
| SAVING_KNOWLEDGE | 75~85% | 落库 |
| SYNCING_EMBEDDINGS | 85% | 向量同步 |
| BUILDING_RELATIONS | 90% | **关系生成（新增）** |
| FINISHED | 100% | 完成 |

关系失败不回滚已保存的 Knowledge，任务记录错误信息。

---

## 九、测试结果

```
95 passed, 0 failed（回归无破坏）
```

---

## 十、未执行项

| 项目 | 原因 |
|------|------|
| 真实 LLM 关系判断测试 | 需要 LLM API Key |
| 端到端导入+关系生成测试 | 需要真实文档 + LLM |
| 跨库隔离性测试 | 需要向量数据 |

---

## 十一、已知问题

1. 人工关系与 Agent 关系无法区分（`knowledge_relation` 表无来源标识字段）
2. 关系重试通过时间范围查找任务知识点，可能不精确（可改进为记录 task_id）
3. FAISS 向量库无原生 metadata 过滤，使用 over-fetch + 后过滤
