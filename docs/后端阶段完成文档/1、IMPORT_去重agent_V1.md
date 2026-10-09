# Knowledge Import Integration V1.0 开发文档

## 一、概述

本次开发将已验证的 KnowledgeExtractAgent、KnowledgeDeduplicatePipeline、MySQL、Vector DB 正式串联，实现完整的 AI 知识导入链路。

```
管理员上传文档
      ↓
ImportTask (PENDING)
      ↓
DocumentParser → TextChunker → KnowledgeExtractAgent
      ↓
KnowledgeCandidate[]
      ↓
Batch 内部去重
      ↓
与数据库已有 Knowledge 去重（Embedding + Vector Search + LLM）
      ↓
NEW / DUPLICATE / MERGE
      ↓
KnowledgeService → MySQL
      ↓
Embedding 同步 → Vector DB
      ↓
ImportTask SUCCESS
```

---

## 二、目录结构

```
backend/
├── app/
│   ├── services/
│   │   ├── embedding_sync_service.py    # 新增 Embedding 同步服务
│   │   └── knowledge_import_service.py  # 新增 知识导入编排服务
│   │
│   └── api/v1/
│       └── import_task.py               # 修改 新增 run 接口
│
├── agent/
│   └── knowledge_deduplicate/
│       └── batch_dedup.py               # 新增 批次内部去重
│
├── scripts/
│   ├── sync_knowledge_embeddings.py     # 新增 Embedding 回填脚本
│   └── check_knowledge_embeddings.py    # 新增 一致性检查脚本
│
└── migrations/versions/
    └── a1b2c3d4e5f6_add_import_task_stats.py  # 新增 统计字段迁移
```

---

## 三、新增文件功能

### 3.1 app/services/embedding_sync_service.py — Embedding 同步服务

| 方法 | 功能 |
|------|------|
| `sync_knowledge(knowledge_id)` | 同步单个知识点到向量库（upsert） |
| `remove_knowledge(knowledge_id)` | 从向量库移除知识点（禁用时调用） |
| `batch_sync_all(batch_size)` | 批量回填所有正常知识点的 Embedding |
| `check_consistency()` | 检查 MySQL 与向量库的一致性 |

**数据所有权原则**：MySQL = Source of Truth，Vector DB = Search Index。

### 3.2 app/services/knowledge_import_service.py — 知识导入编排服务

**核心编排层**，协调整个导入流程：

| 阶段 | 进度 | 说明 |
|------|------|------|
| PARSING | 0~10% | 解析文档 |
| EXTRACTING_KNOWLEDGE | 10~50% | LLM 提取候选知识 |
| DEDUPLICATING_KNOWLEDGE | 50~75% | 批次内部去重 + 数据库去重 |
| SAVING_KNOWLEDGE | 75~90% | NEW/MERGE 落库 |
| SYNCING_EMBEDDINGS | 90~100% | 向量同步 |

**关键设计**：
- 先提交 MySQL → 再同步 Vector DB
- 单个 Candidate 失败不影响其他 Candidate
- Vector DB 不可用时任务 FAIL，不偷偷创建大量 NEW
- 重复导入通过去重 Pipeline 保证幂等

### 3.3 agent/knowledge_deduplicate/batch_dedup.py — 批次内部去重

对本次导入产生的候选知识点先内部去重，避免同批次内产生重复。

流程：标准化 → 精确匹配去重 → 向量相似度去重 → Unique Candidates

### 3.4 scripts/sync_knowledge_embeddings.py — Embedding 回填脚本

```bash
cd backend
python scripts/sync_knowledge_embeddings.py
```

输出：知识点总数、需要同步、成功、失败、耗时、失败 ID 列表。

支持重复执行，使用 upsert 保证幂等。

### 3.5 scripts/check_knowledge_embeddings.py — 一致性检查脚本

```bash
cd backend
python scripts/check_knowledge_embeddings.py
```

输出：MySQL 正常知识数、向量库已索引数、缺失/多余数量。

---

## 四、修改文件

| 文件 | 修改内容 |
|------|----------|
| `app/api/v1/import_task.py` | 新增 `POST /{id}/run` 正式执行接口 |
| `app/models/import_task.py` | 新增 5 个统计字段 |
| `migrations/versions/a1b2c3d4e5f6_...` | 统计字段 Migration |

---

## 五、新增 API

### POST /api/v1/import-tasks/{task_id}/run

正式执行导入任务（完整 AI 流程）。

**请求**：无 Body，认证为 Bearer Token

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": 1,
    "status": "SUCCESS",
    "candidate_count": 13,
    "new_count": 10,
    "duplicate_count": 2,
    "merge_count": 1,
    "failed_count": 0,
    "duration": 85.3,
    "errors": []
  }
}
```

---

## 六、数据库 Migration

为 `knowledge_import_task` 新增 5 个统计字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `candidate_count` | INT | 候选知识点总数 |
| `new_count` | INT | 新增知识点数 |
| `duplicate_count` | INT | 重复知识点数 |
| `merge_count` | INT | 合并知识点数 |
| `failed_count` | INT | 失败知识点数 |

Migration: `a1b2c3d4e5f6_add_import_task_stats.py`

---

## 七、Embedding 同步机制

```
Knowledge 创建 → MySQL commit → Embedding → Vector DB upsert
Knowledge 更新 → MySQL commit → 重新 Embedding → Vector DB upsert
Knowledge 禁用 → MySQL commit → Vector DB delete
```

**Vector ID 规则**：`knowledge_{knowledge_id}`，保证重复同步不产生重复向量。

---

## 八、测试结果

```
77 passed, 0 failed（回归测试）
```

原有 Auth、Knowledge、Question、ImportTask、Dashboard 全部通过。

---

## 九、已知问题

1. Vector DB 为内存实现（FAISS），重启后向量丢失，需重新执行 `sync_knowledge_embeddings.py`
2. LLM 去重调用未在自动化测试中实际验证（需要 LLM API Key）
3. 重复导入的幂等性依赖去重 Pipeline，未在真实文档上完整验证

---

## 十、尚未完成

1. **真实文档导入验证**：需要 Android/Java 面试资料实际测试
2. **重复导入测试**：同一文件导入两次，验证第二次 DUPLICATE 占绝大多数
3. **性能测试**：25~100 个候选的耗时和 LLM 调用数统计
4. **Vector DB 持久化**：生产环境建议切换到持久化向量存储

---

## 十一、下一步建议

1. **KnowledgeRelationAgent** — 知识关系自动建立
2. **QuestionGenerateAgent** — AI 题目生成
3. **向量库持久化** — 避免重启丢失
4. **前端适配** — ImportTask 新增统计字段展示
