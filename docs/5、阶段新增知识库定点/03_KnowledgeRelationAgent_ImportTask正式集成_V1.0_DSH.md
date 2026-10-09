# AI 面试题库系统：KnowledgeRelationAgent 接入正式 ImportTask 指导文档 V1.0（DSH）

> 执行工具：DeepSeek Harness（DSH）  
> 代码范围：仅 `backend/`  
> 前置条件：KnowledgeBase V1.0 后端基础能力已完成；管理后台已能在创建 ImportTask 时选择知识库，并已通过基本联调。  
> 当前目标：把已独立测试通过的 `KnowledgeRelationAgent` 接入正式知识导入流程，并把有效关系写入现有 `knowledge_relation`。  
> 不修改 `admin-web/`。

## 0. 给 DSH 的执行指令

请先检查当前代码，确认以下模块的真实路径、函数签名、事务边界及测试现状：

- ImportTask Router/Service/Repository 和现有状态/进度机制。
- KnowledgeImportService（或实际负责协调导入链路的服务）。
- KnowledgeService、KnowledgeRepository。
- Embedding/Vector DB 同步与过滤实现。
- KnowledgeRelationAgent 的 graph/nodes/schemas/prompts。
- `knowledge_relation` ORM、关系 CRUD Service/Repository/API。
- `knowledge_base` ORM，以及 Knowledge 和 ImportTask 的 `knowledge_base_id`。

根据当前代码适配，不要照抄本文假设的类名或字段名。优先最小改动，复用既有 Agent、Service 和关系表，不重写已完成功能。

硬性要求：

1. 只修改 `backend/`。
2. 所有 relation candidate retrieval 必须使用当前 ImportTask 的 `knowledge_base_id` 作为范围；不能跨库取候选后不加筛选地交给 Agent。
3. 不把 Agent 直接写库；最终持久化由现有 Relation Service/Repository 完成。
4. 不增加 Redis、Celery、RabbitMQ，不新建 Vector DB。
5. 保证知识保存与关系生成可部分成功；关系失败不得丢失已经成功保存的 Knowledge。
6. 重复执行任务/重试不能生成重复关系。
7. 必须运行真实测试，明确列出未执行项。

## 1. 前置条件检查

开始编码前，先确认以下条件全部存在：

- [ ] `knowledge` 有可靠的 `knowledge_base_id`。
- [ ] `knowledge_import_task` 保存本任务选择的 `knowledge_base_id`。
- [ ] 新增/更新 Knowledge 会同步向量元数据，能按知识库检索候选。
- [ ] `KnowledgeRelationAgent` 的独立测试接口仍然可运行。
- [ ] 现有 `knowledge_relation` Service 可以创建/查询/删除关系；确认真实字段和唯一约束。
- [ ] 已知关系方向契约与独立测试文档一致。

如有任何前置条件未满足，先报告缺口，不要在本次任务中绕过知识库过滤或重造一套逻辑。

## 2. 本阶段业务流程

推荐将关系处理作为已保存知识后的独立阶段：

```text
ImportTask (包含 knowledge_base_id = K)
       ↓
DocumentParser / TextChunker
       ↓
KnowledgeExtractAgent
       ↓
Candidate 内部去重
       ↓
KnowledgeDeduplicatePipeline（仅查询 K）
       ↓
KnowledgeService 创建/更新 Knowledge
       ↓
MySQL commit
       ↓
Embedding 同步 / Vector DB upsert（metadata 含 K）
       ↓
收集本次实际新增或内容发生变化的 knowledge_id
       ↓
KnowledgeRelationAgent（候选只在 K 中检索）
       ↓
确定性校验 + 关系去重 + 方向规范化
       ↓
现有 Relation Service/Repository 写入 knowledge_relation
       ↓
ImportTask 记录各阶段结果
```

### 执行顺序重点

- 必须先获得真实的 `knowledge_id`，不能使用 ExtractAgent 的候选数组位置或知识点名称代替 ID。
- 在调用自动关系检索前，应先完成本次新增 Knowledge 的 Vector upsert，使同批新知识有机会成为彼此候选。
- 若 Vector 同步失败，不要假定关系候选为空；按现有错误处理策略记录失败/部分成功。
- 对 `DUPLICATE` 且数据库内容未变更的知识，不必重复生成关系。
- 对 `MERGE` / 更新且内容确实变化的知识，可以触发关系补充检查；不要因此自动删除所有已有关系。

## 3. 只处理本批新增或变更知识

导入服务应在知识写入阶段收集 `changed_knowledge_ids`，包括：

- 本次新建成功的 Knowledge ID。
- 本次 Merge 后字段发生实际变化的 Knowledge ID。

排除：

- 判为 `DUPLICATE` 且没有更新内容的候选。
- 写入失败或没有可靠 ID 的候选。
- 已停用/软删除且按现有规则不参加正常检索的 Knowledge。

按确定性的顺序去重并排序 ID，避免一个 ID 在同一任务中被反复处理。

不要扫描全库所有知识点两两比较。每个锚点通过现有 Vector DB / Candidate Retrieval Service 获取同库 Top-K 候选，复用独立开发时验证过的参数和过滤规则。

## 4. 知识库隔离规则

关系检索必须执行：

```text
ImportTask.knowledge_base_id = K
       ↓
锚点 Knowledge.knowledge_base_id 必须为 K
       ↓
Vector Search 按 K 过滤
       ↓
候选 Knowledge.knowledge_base_id 再经 MySQL 校验为 K
       ↓
KnowledgeRelationAgent 判断
```

必要时在调用 Agent 前从 MySQL 二次验证锚点和候选的 `knowledge_base_id`、状态及 ID。

不允许：

- Android 任务为 Java 知识写入自动关系。
- 把向量检索失败当作“没有关系”。
- 把无候选与检索异常混为一谈。
- 将知识库归属 ID 仅存于内存但没有在 ImportTask 持久化。

V1.0 关系自动生成默认限同库。跨库关系（例如 Android 与 Java 间的关系）后续作为显式需求设计，不在当前阶段放开。

## 5. 关系类型与方向

复用当前表已有的关系类型：`prerequisite`、`related`、`extension`、`contrast`。以现有模型约定为准，不擅自改枚举名。

方向语义：

- `prerequisite`：起点是先修知识，终点是依赖它的后续知识。例如 `Java 多线程 -> Java 线程池`。
- `extension`：起点是基础/通用知识，终点是它的延伸或细化内容。
- `related`：语义上通常对称。
- `contrast`：语义上通常对称。

重要：`KnowledgeRelationAgent` 返回的 `from_knowledge_id` / `to_knowledge_id`（或当前实际字段）必须映射为数据库中已约定的 source/target。不能把候选 ID 默认当起点；必须按关系的语义方向写入。

对 `related` 和 `contrast`，按现有 schema/服务层定义固定一种规范存储方式，避免 A->B 与 B->A 被重复保存。如果现有表已存储有向关系且 API 通过 source 或 target 查单侧，请补充/验证双向查询能力；不要随便插入两条互逆关系来掩盖查询不完整。

允许 `NO_RELATION`。没有足够语义关系时不写入任何记录。不能因为名字相似、同属一库或共享关键词就强行建立关系。

## 6. 写库、幂等与已有关系

所有保存都走现有关系 Service/Repository，不要让 Agent 本身直接调用 ORM session 写关系表。

写入前需要：

1. 排除自关联（from ID == to ID）。
2. 校验双方 Knowledge 都存在、可用，并同属当前知识库 K。
3. 校验 relation_type 是现有合法类型。
4. 同一任务内对关系对进行规范化和去重。
5. 查询或依靠现有唯一约束确认数据库中不存在相同关系。
6. 如果唯一约束冲突，将其作为幂等重复处理，不应让任务整体失败。
7. 只有 `decision = RELATION` 且通过规则校验的输出才可能写入。
8. 低于独立测试阶段已经确定的置信度阈值的结果跳过；阈值集中配置，不要散落硬编码。若当前项目尚未校准阈值，先沿用 Agent 独立测试所用默认值并报告。

### 不要擅自清空已有关系

更新知识点后再次运行 Agent 时，本阶段原则上只补充缺失的有效关系，不自动删除旧关系。

如果当前表无法区分人工建立关系与 Agent 生成关系，禁止因为重试或 Agent 返回空列表而删除该知识点所有旧关系。若未来确实要自动重建，需要先设计可靠的关系来源标识和审计规则，属于另一个任务。

## 7. ImportTask 状态、结果与失败恢复

复用当前 ImportTask 的状态、进度、日志和错误字段。不要假设项目一定已有 `PARTIAL_SUCCESS` 状态；先检查当前枚举/状态机。

至少要能区分这些阶段：

- 文档解析/抽取失败。
- 去重/知识保存失败。
- Embedding/Vector 同步失败。
- RelationAgent 推理失败。
- 关系写入失败。
- 全流程成功，但没有生成关系（这是合法结果）。

保存知识成功、关系失败时：

- 不回滚已经提交的 Knowledge。
- 记录 RelationAgent 阶段、错误摘要、受影响的锚点 ID、已写关系数和失败数。
- 使用现有状态体系标记部分成功或“知识导入成功、关系阶段失败/待重试”；如现有体系不能表示，优先增加最小的阶段/结果字段，而不是重构整套任务系统。
- 提供安全重试方式。优先复用现有 ImportTask retry 模式；如当前没有，可加一条仅重跑关系阶段的管理员接口/服务入口，必须只对已存在知识 ID 执行，不能重新解析并重复插入全批知识。
- 重试必须幂等，不重复创建已保存关系。

如果关系服务只部分成功，保存成功的关系可以保留，记录失败部分并允许重试。不要因为某一个候选失败就把其他有效关系全部回滚。

## 8. 性能控制

- 只处理 `changed_knowledge_ids`。
- 沿用 Agent 独立测试阶段的 Top-K 和并发设定；不要无上限循环调用 LLM。
- 同一对知识只需要一次有效判定，不应因为 A 作为锚点、B 也作为锚点而重复产生同一条对称关系。
- 在任务日志/结果中记录候选锚点数量、检索候选数、LLM 调用数、建议关系数、实际新建关系数、重复跳过数、失败数和耗时。
- 暂时不引入队列框架或 Redis。若当前任务机制为同步运行，沿用现有机制，先保证稳定与幂等。

## 9. API / 内部服务边界

不要暴露让客户端传 `persist=true` 的测试接口来承载正式写库。独立 Agent 测试 API 保持无副作用。

正式流程由 `KnowledgeImportService`（或当前等效协调服务）决定何时执行 Agent，再通过现有关系服务持久化。可以新增内部方法，例如 `build_relations_for_import(changed_knowledge_ids, knowledge_base_id, task_id)`，但应遵循项目实际目录和依赖注入方式。

若需要增加关系阶段重试 API，建议沿用管理员鉴权和统一响应结构，例如：

```text
POST /api/v1/import-tasks/{task_id}/relations/retry
```

仅在当前项目没有合适的现有重试入口且确实需要时才新增；不要复制已有接口功能。

## 10. 自动化测试

必须使用 Fake/Mock LLM 和 Fake/Mock Vector Search 覆盖稳定的单元测试，不要让基础 pytest 必须访问真实外部模型 API。

### 10.1 流程测试

- 一个 ImportTask 指定 Android，Knowledge 都写入 Android 归属。
- 关系阶段只收到本批新增/变更的真实 Knowledge ID。
- Vector 同步完成后才触发关系自动检索。
- 同库候选关系能成功写入现有关系表。
- `NO_RELATION` 不落库。
- 纯重复导入不会重复调用所有关系推理，也不会大量新增关系。

### 10.2 领域隔离

准备 Android 和 Java 两个知识库，各有相似知识：

- Android 导入任务不能为 Java Knowledge 写入关系。
- Vector 返回混杂候选时，MySQL 二次过滤会排除异库候选。
- anchor 的库与 task 库不一致时，流程拒绝或记为明确错误。
- 已停用 Knowledge 不作为正常候选。

### 10.3 幂等与关系方向

- 同一任务执行两次，同一关系不会出现重复记录。
- 重试关系阶段，不重复写已经成功的关系。
- `prerequisite` 起点/终点符合约定。
- `extension` 方向正确。
- `related`、`contrast` 不出现多余互逆重复记录。
- 自关联、无效 relation_type、已不存在的 Knowledge 都不会写入。
- 查询任意一端的知识关系时，根据当前 API 契约能正确看到相关关系。

### 10.4 失败隔离

- LLM/Agent 抛错：知识仍留在 MySQL，任务记录关系失败阶段。
- Vector 同步失败：不伪造无候选/无关系结果。
- 关系写入一条失败：其他成功关系保留并记录失败数量。
- RelationAgent 返回格式异常：Pydantic/规则校验阻止无效数据入库。
- 关系阶段重试可成功且不重复新增。

### 10.5 回归

执行项目现有测试，至少验证 Auth、Knowledge CRUD、Relation CRUD、Question CRUD、ImportTask、Dashboard。以真实测试配置和命令为准，不得只测试新模块。

## 11. 真实 API 联调建议

1. 在 Android 知识库新建一个导入任务并上传测试文档。
2. 检查任务记录中 `knowledge_base_id` 符合选择。
3. 检查新 Knowledge 的 MySQL 记录与向量 metadata 都属于 Android。
4. 检查同批有合理关系的知识点新增 `knowledge_relation` 记录。
5. 检查关系表中的 source/target 和 relation_type 语义正确。
6. 再次导入相同文档，检查 Knowledge 和关系数量不会大幅重复增加。
7. 在 Java 库构造相似知识，重复执行 Android 导入，确认关系候选没有跨库泄漏。
8. 通过可控 Mock 或测试注入制造 RelationAgent 失败，确认已保存知识保留并可单独重试关系阶段。
9. 检查管理员现有知识关系查询 API 是否能返回入边和出边（按当前 API 契约）。

不要在生产数据中制造故障。优先使用 `interview_agent_test` 或项目现有的隔离测试库。

## 12. 完成验收清单

```text
[ ] 正式 ImportTask 经过知识库选择并记录 knowledge_base_id
[ ] RelationAgent 只处理本批新增/内容变更的 Knowledge
[ ] 同库 Vector 检索和 MySQL 二次校验生效
[ ] 新 Knowledge 的 Vector 同步先于自动关系检索
[ ] 有效关系通过现有 Relation Service/Repository 持久化
[ ] 关系方向符合 prerequisite/extension 等语义
[ ] NO_RELATION 不入库
[ ] 对称关系不会重复存储
[ ] 重复运行和关系重试保持幂等
[ ] 关系失败不会回滚已保存 Knowledge
[ ] ImportTask 能显示/记录各阶段结果与错误
[ ] 现有关系 CRUD 能正确查询关系
[ ] Android 与 Java 数据不会跨库自动建立关系
[ ] 现有后端回归测试通过
[ ] 没有修改 admin-web/
[ ] 输出修改清单、迁移信息、真实测试结果与未执行项
```

## 13. 最终交付报告

请明确报告：

1. 改动文件清单及每个改动目的。
2. 正式导入中 RelationAgent 的实际调用位置。
3. changed Knowledge ID 的收集方式及其去重规则。
4. 知识库范围如何从 ImportTask 传到 Vector Search、Agent 和关系校验。
5. 关系持久化调用了哪个现有 Service/Repository；如有新迁移，给出 revision ID。
6. ImportTask 如何记录失败、部分成功和关系阶段重试。
7. 实际运行的 pytest/API 联调步骤及通过/失败项。
8. 未执行的真实 LLM 测试、Vector DB 测试及原因。
9. 是否仍有人工关系与 Agent 关系无法区分的问题。
