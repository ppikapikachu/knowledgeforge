# AI 面试题库系统：KnowledgeBase V1.0 后端开发指导文档（DSH）

> 执行工具：DeepSeek Harness（DSH）  
> 本阶段代码范围：仅 `backend/`  
> 阶段目标：为知识点建立明确的领域归属，让导入、去重、向量检索和后续出题可以按知识库精确过滤。  
> 本阶段不执行：`KnowledgeRelationAgent` 正式导入集成；不得修改 `admin-web/`。

## 0. 给 DSH 的执行指令

请先阅读本文，再检查当前仓库中真实的 ORM、Repository、Service、Router、ImportTask、KnowledgeDeduplicatePipeline、Embedding/Vector DB 代码。根据实际命名进行最小变更，不要假设本文中的示例字段与项目代码完全相同。

硬性要求：

1. 只修改 `backend/`，不修改 `admin-web/`、Flutter 客户端或其他目录。
2. 先检查当前代码和数据库状态，再制定迁移计划；不要直接覆盖数据库或重置现有数据。
3. 复用现有 FastAPI、SQLAlchemy 2.x、Alembic、Pydantic、KnowledgeService、Embedding/Vector DB 与导入流程。
4. 不引入 Redis、Celery、RabbitMQ，不更换向量数据库，不重写现有 Agent。
5. 本阶段不把 `KnowledgeRelationAgent` 接进 ImportTask；只为后续集成提供可靠的 `knowledge_base_id` 上下文。
6. 迁移必须保留现有知识、关系、题目、管理员和导入任务数据。
7. 必须真实执行测试，不得把未运行的测试写成通过。

## 1. 业务目标

目前所有 Knowledge 混在同一个范围内，系统缺少一个领域维度。本阶段引入“知识库/领域”实体，例如 Android、Java、分布式系统、C 语言。它们不是普通知识点，也不是 `knowledge_relation` 中的虚拟节点。

完成后：

- 每条正式 Knowledge 都有一个主归属知识库。
- 管理员上传文档时，ImportTask 保存本次目标知识库。
- 同一次导入的数据库去重默认仅比较目标知识库内的 Knowledge。
- Vector DB 中的知识向量有 `knowledge_base_id` 元数据或可等效过滤字段。
- 现有 Knowledge 列表 API 支持按知识库筛选。
- 题库后续可通过 `question_knowledge` 关联找到题目所属知识库；本阶段不改出题逻辑。
- 原有 API 与数据在迁移后仍能正常工作。

## 2. V1.0 范围与不做的事

### 必须实现

- 新增 `knowledge_base` 表、模型、Repository/Service、Schema 和管理 API。
- 增加安全的 Alembic 迁移和旧数据回填。
- 为 `knowledge` 增加 `knowledge_base_id` 归属；为导入任务增加 `knowledge_base_id`。
- 在 Knowledge CRUD/列表与 ImportTask 创建/详情中保存并展示对应的 ID/名称。
- 在去重数据库检索中把目标知识库作为必需的过滤条件。
- 把 `knowledge_base_id` 写入新增/更新 Knowledge 的向量元数据；更新已有向量同步逻辑，并提供必要的检查或回填脚本。
- 增加测试和 API 验证。

### 本阶段禁止扩张

- 不执行 RelationAgent 正式集成。
- 不新增第二套 Vector DB 或第二套去重 Pipeline。
- 不把 Android/Java 等知识库名插入 `knowledge` 表充当知识点。
- 不实现任意深度的主题树。V1.0 为平级领域集合。
- 不做自动批量 LLM 分类旧知识；旧数据统一进入“未分类”，由管理员人工归类。
- 不修改 `admin-web/`。
- 不提前实现用户端练习界面或出题策略。

## 3. 数据模型建议

请以现有模型命名规范为准。建议 `knowledge_base` 至少包含：

| 字段 | 类型建议 | 含义 |
|---|---|---|
| `id` | 当前项目统一主键类型 | 知识库 ID |
| `code` | varchar，非空，唯一 | 稳定编码，如 `android`、`java`、`distributed_systems`、`c_language`、`uncategorized` |
| `name` | varchar，非空 | 展示名，如 Android、Java、分布式系统、C 语言、未分类 |
| `description` | nullable text/varchar | 简介 |
| `status` | 复用项目状态习惯 | 正常/停用 |
| `created_at` / `updated_at` | 复用项目时间字段规范 | 创建及更新时间 |

不为了未来假设过度设计表结构。V1.0 暂时不需要 `parent_id`，因为当前需求是平级的顶层领域分类，而不是任意层级分类树。

在 `knowledge` 表增加 `knowledge_base_id` 外键；迁移顺序要确保旧记录有合法归属后，再按实际情况设为非空。推荐先创建默认/未分类知识库，再回填旧知识，然后设置约束。

在 `knowledge_import_task` 表增加 `knowledge_base_id`。所有历史任务回填到“未分类”，不能丢失任务记录。

`question` 表 V1.0 不需要冗余添加 `knowledge_base_id`：将来从 `question_knowledge` 关联 `knowledge` 后即可过滤。若检查发现当前模型允许完全没有任何 Knowledge 关联的题目，应在报告中说明此类题目不属于任何指定领域筛选的默认结果。

## 4. 初始知识库数据与迁移

初始数据建议：

- `android` / Android
- `java` / Java
- `distributed_systems` / 分布式系统
- `c_language` / C 语言
- `uncategorized` / 未分类

初始化脚本或迁移必须幂等：重复执行不会产生相同 code 的重复记录。具体方式遵守项目 Alembic 习惯。

旧 Knowledge 与 ImportTask：

1. 创建知识库记录。
2. 为旧 Knowledge 回填 `uncategorized` ID。
3. 为旧 ImportTask 回填 `uncategorized` ID。
4. 验证不存在空/无效外键。
5. 再设置必要约束。

禁止在迁移期间调用 LLM 自动猜测每条旧 Knowledge 属于哪个领域。现有数据的正式事实不可通过推测批量改变。

如果项目测试数据库与开发数据库迁移流程不同，分别执行迁移和测试，报告测试环境实际数据状态。不能重建用户开发数据库来换取迁移成功。

## 5. 建议 API 契约

先确认当前 API 前缀、分页格式、统一响应格式和鉴权依赖，再按项目惯例实现。接口路径建议如下；如果已有同义 API，复用现有实现，不要再造重复接口。

### 5.1 知识库管理

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/v1/knowledge-bases` | 获取知识库列表，可附带每库知识点数量 |
| GET | `/api/v1/knowledge-bases/{id}` | 获取知识库详情 |
| POST | `/api/v1/knowledge-bases` | 创建知识库 |
| PUT/PATCH | `/api/v1/knowledge-bases/{id}` | 修改名称、描述等 |
| PATCH | `/api/v1/knowledge-bases/{id}/status` | 停用/启用知识库，若项目习惯不同可适配 |

字段：`id`、`code`、`name`、`description`、`status`、`knowledge_count`（如果可低成本统计）、时间字段。

规则：

- `code` 创建后建议不可随意修改，避免向量 metadata 和外部引用不一致。
- 不允许删除仍有知识点或任务引用的知识库；优先停用，或要求先迁移内容。
- 停用的知识库不能作为新导入目标，但旧知识仍可查看和查询。
- 新建、修改、停用接口使用现有管理员鉴权。

### 5.2 Knowledge API

现有 `GET /api/v1/knowledge` 增加 `knowledge_base_id` 可选过滤参数，同时保留现有分页、关键词、状态等功能。

知识点创建/更新可接收 `knowledge_base_id`。新记录应验证目标知识库存在且处于可用状态；修改已有知识点归属时，必须同步更新向量 metadata，并明确已有关系是否跨库。V1.0 默认关系候选和导入新生成关系仅限同库；手动挪动知识点归属时不要静默删除其已有关系，应在交付报告中说明处理原则。

### 5.3 ImportTask API

现有创建导入任务 API 接收 `knowledge_base_id`，任务详情返回知识库 ID 和名称，任务列表可按 `knowledge_base_id` 过滤（如果现有列表接口易于扩展）。

新管理后台会要求用户显式选择知识库。为了兼容历史脚本/旧客户端，后端在参数缺失时可暂时使用 `uncategorized` 作为兼容兜底，并记录该行为；不得把这种兼容策略做成前端默认值，让新用户无感地把所有数据导入未分类。

创建任务时校验知识库存在且可用，任务从开始到结束都保留同一个目标知识库，不能仅由当前前端选择状态临时决定。

## 6. 导入和去重如何使用知识库范围

目标流程：

```text
ImportTask(knowledge_base_id = K)
    ↓
解析 / 分块 / KnowledgeExtractAgent
    ↓
本批 Candidate 内部去重（批内规则不变）
    ↓
只在 Knowledge Base K 中查找已有 Knowledge
    ↓
KnowledgeDeduplicatePipeline
    ↓
KnowledgeService create/update（保存 knowledge_base_id = K）
    ↓
同步 embedding 与 Vector metadata
```

必须实现的原则：

- 批次内部候选去重继续复用现有实现。
- 比较数据库中已有 Knowledge 时，候选必须限定为同一个目标 `knowledge_base_id`，以及现有正常/启用状态要求。
- 不允许在 `knowledge_base_id = Android` 的任务里把 Java 库中的相似结果直接作为合并对象。
- 新增知识归属为任务的知识库。
- `MERGE` 目标只能是同一知识库下的知识点；跨库不能自动合并。
- Vector DB 查询失败、Embedding 不可用或索引过滤不可靠时，按现有错误策略失败或标记部分失败；绝不能将检索异常当成没有匹配结果后继续批量创建 `NEW`。

## 7. Vector DB / Embedding 调整

先检查当前向量记录 ID、payload/metadata、过滤 API 与同步脚本。

目标 metadata 至少包含：

```json
{
  "knowledge_id": 123,
  "knowledge_base_id": 2,
  "status": "NORMAL"
}
```

以上字段名是建议，实际应适配当前 Vector DB schema，但必须能从候选向量定位 Knowledge 及其知识库。

要求：

1. 新建 Knowledge 的 vector upsert 带上知识库归属。
2. 更新 Knowledge 或调整归属后，重新同步向量 metadata；若文本变更需要重新 embedding，沿用当前逻辑。
3. 检索服务尽可能在 Vector DB 查询端直接用 `knowledge_base_id` 做过滤。
4. 若当前 Vector DB/Repository 不支持 metadata filter，先检查是否能通过已有 Repository 做有限的 over-fetch + MySQL 二次校验；必须明确这个方案的召回/性能限制。不要直接把未过滤的结果提供给 Agent。
5. 检查并更新现有 `scripts/sync_knowledge_embeddings.py`、`scripts/check_knowledge_embeddings.py`（或仓库中的真实同等脚本），使历史向量补上知识库 metadata。
6. 回填脚本必须可重复运行，不产生重复有效向量；提供 dry-run 或清晰的预览/日志机制（如果现有脚本模式支持）。
7. 检查向量元数据过滤结果与 MySQL 数据是否一致。

## 8. 删除、停用与变更规则

- Knowledge Base 被停用后，不可被新 ImportTask 选择，也不应作为正常检索候选；其原有 Knowledge 不需要因此删除。
- 不允许硬删除非空 Knowledge Base。
- Knowledge 换库是显式业务操作，至少要更新 MySQL 归属和 Vector metadata。不要依赖旧向量的 metadata 自动变化。
- V1.0 不做跨库自动去重，也不自动移动已有 Knowledge。
- 暂不在本阶段自动重建所有知识关系；关系正式集成在下一阶段处理。

## 9. 测试要求

### 9.1 数据库与迁移

- 从当前旧 schema 升级 migration 成功。
- 旧 Knowledge 全部归属 `未分类`，数据条数不变。
- 旧 ImportTask 全部归属 `未分类`，历史任务仍可查看。
- 初始化知识库数据重复执行不产生重复 code。
- 非空知识库无法被删除；停用逻辑正常。

### 9.2 API

- 列出知识库、创建、修改、停用，鉴权和参数错误符合统一响应格式。
- `GET /api/v1/knowledge?knowledge_base_id=...` 只返回对应知识库。
- 创建或更新 Knowledge 能保留归属。
- 创建 ImportTask 能传入目标知识库；缺省参数兼容路径按设计回到未分类。
- 停用/不存在的知识库不能被新导入任务使用。

### 9.3 隔离性

用两个知识库构造名称或内容高度相似的 Knowledge：

- 向 Android 库导入时，去重搜索不返回 Java 库的知识。
- 在 Android 库导入时，MERGE 不能更新 Java 库 Knowledge。
- Vector DB 查询在有过滤能力时确实按库过滤；没有过滤能力时必须验证二次校验逻辑。
- 一个库的向量同步失败不得导致另一个库的向量被错误修改。

### 9.4 回归

至少执行项目现有：

```bash
python -m pytest tests/ -v
```

如当前仓库使用其他命令或测试目录，以真实项目配置为准。

执行/验证现有 Knowledge CRUD、Relation CRUD、Question CRUD、ImportTask、Dashboard、Auth。不得因新增字段使旧接口或测试数据初始化全部失效。

### 9.5 向量回填

- 对旧 Knowledge 执行一次同步/回填。
- 再重复执行一次，确认幂等。
- 执行检查脚本，确认知识库 metadata 完整。
- 报告实际更新向量数、失败数；若无法访问 Vector DB，明确标记未验证。

## 10. 完成标准

```text
[ ] 新增 knowledge_base 模型与迁移
[ ] 初始知识库数据幂等
[ ] 旧 Knowledge 和旧 ImportTask 安全回填为未分类
[ ] Knowledge 有明确 knowledge_base_id
[ ] ImportTask 记录目标知识库
[ ] Knowledge 列表能按知识库过滤
[ ] 导入去重限定在目标知识库
[ ] Vector metadata 包含知识库 ID
[ ] 旧 Vector 索引可回填、可检查且可重复运行
[ ] 停用库不能被新任务选中
[ ] 原 CRUD 与导入功能回归通过
[ ] 没有修改 admin-web/
[ ] 本阶段没有把 RelationAgent 接入正式导入流程
[ ] 输出真实测试报告、修改文件清单和迁移注意事项
```

## 11. 交付报告模板

请最终回答：

1. 改动了哪些文件，分别做什么。
2. 新表和字段实际名称、Alembic revision ID。
3. 旧数据迁移和默认知识库回填的实际结果。
4. Vector DB 过滤如何实现；哪些过滤发生在向量端，哪些发生在 MySQL 二次校验。
5. 实际执行的测试命令及通过/失败数量。
6. 真实 API 验证步骤与结果。
7. 未执行的测试和原因。
8. 是否存在需要下一阶段关系集成处理的已知问题。
