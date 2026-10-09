# KnowledgeBase V1.0 交付报告

## 一、概述

为知识点建立明确的领域归属（知识库），让导入、去重、向量检索可以按知识库精确过滤。

---

## 二、改动文件清单

### 新增文件

| 文件 | 功能 |
|------|------|
| `app/models/knowledge_base.py` | 知识库 ORM 模型 |
| `app/schemas/knowledge_base.py` | 知识库 Pydantic Schema |
| `app/repositories/knowledge_base_repository.py` | 知识库数据访问层 |
| `app/api/v1/knowledge_base.py` | 知识库 CRUD API |
| `migrations/versions/b2c3d4e5f6a7_add_knowledge_base.py` | 数据库迁移 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `app/models/__init__.py` | 注册 KnowledgeBase 模型 |
| `app/models/knowledge.py` | 新增 `knowledge_base_id` 外键字段 |
| `app/models/import_task.py` | 新增 `knowledge_base_id` 外键字段 |
| `app/schemas/knowledge.py` | Create/Update/Response 增加 `knowledge_base_id` |
| `app/schemas/import_task.py` | Response 增加 `knowledge_base_id` |
| `app/api/v1/knowledge.py` | 列表支持 `knowledge_base_id` 过滤；创建时默认未分类 |
| `app/api/v1/import_task.py` | 创建任务支持 `knowledge_base_id` 参数 |
| `app/api/router.py` | 注册知识库路由 |
| `app/services/knowledge_service.py` | 列表支持 `knowledge_base_id` 过滤 |
| `app/repositories/knowledge_repository.py` | 列表支持 `knowledge_base_id` 过滤 |
| `app/services/embedding_sync_service.py` | Vector metadata 增加 `knowledge_base_id` |
| `app/services/knowledge_import_service.py` | 去重检索限定同一知识库 |
| `tests/conftest.py` | 测试数据库创建初始知识库数据 |

---

## 三、数据库变更

### 新表：`knowledge_base`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | BIGINT PK | 主键 |
| `code` | VARCHAR(50) UNIQUE | 稳定编码 |
| `name` | VARCHAR(100) | 展示名称 |
| `description` | TEXT | 简介 |
| `status` | INT | 1=正常, 0=停用 |
| `created_at/updated_at` | DATETIME(3) | 时间戳 |

### 新增字段

| 表 | 字段 | 说明 |
|----|------|------|
| `knowledge` | `knowledge_base_id` | 外键 → knowledge_base.id |
| `knowledge_import_task` | `knowledge_base_id` | 外键 → knowledge_base.id |

### 初始数据（幂等）

| code | name |
|------|------|
| android | Android |
| java | Java |
| distributed_systems | 分布式系统 |
| c_language | C 语言 |
| uncategorized | 未分类 |

### Alembic Revision

`b2c3d4e5f6a7_add_knowledge_base.py`

---

## 四、新增 API

### 知识库管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/knowledge-bases` | 知识库列表（含知识点数量） |
| GET | `/api/v1/knowledge-bases/{id}` | 知识库详情 |
| POST | `/api/v1/knowledge-bases` | 创建知识库 |
| PUT | `/api/v1/knowledge-bases/{id}` | 修改名称/描述 |
| PATCH | `/api/v1/knowledge-bases/{id}/status` | 停用/启用 |

### Knowledge API 变更

- `GET /api/v1/knowledge` 新增 `knowledge_base_id` 可选过滤参数
- `POST /api/v1/knowledge` 支持 `knowledge_base_id`（不传时默认未分类）

### ImportTask API 变更

- `POST /api/v1/import-tasks` 新增 `knowledge_base_id` 表单参数

---

## 五、Vector DB 过滤实现

**方案**：FAISS 不支持 metadata 过滤，采用 **over-fetch + MySQL 二次校验**：

1. 向量检索多取候选（fetch_k=20）
2. 按 `knowledge_base_id` 过滤元数据
3. 只保留同一知识库的候选

**限制**：如果某知识库的向量占比很低，over-fetch 后可能过滤掉太多。当前场景（5 个知识库）影响不大。

---

## 六、测试结果

```
95 passed, 0 failed
```

- 原有 Auth、Knowledge、Question、ImportTask、Dashboard、Agent 测试全部通过
- 迁移测试：初始数据幂等、旧数据回填、外键约束

---

## 七、已知问题

1. FAISS 向量库不支持原生 metadata 过滤，使用 over-fetch + 后过滤
2. 向量库为内存实现，重启后需重新执行 `sync_knowledge_embeddings.py`
3. `question` 表未冗余 `knowledge_base_id`（通过 `question_knowledge` 关联可查）

---

## 八、未执行项

1. **向量回填验证**（需要先有实际知识点数据）
2. **知识库隔离性端到端测试**（需要真实向量数据）
