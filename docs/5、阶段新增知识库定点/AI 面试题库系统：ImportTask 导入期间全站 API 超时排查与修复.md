# AI 面试题库系统：ImportTask 导入期间全站 API 超时排查与修复

## 一、问题现象

知识库分类、管理员前端改造、KnowledgeRelationAgent 正式集成均已完成。

测试时，上传文档后调用文档处理接口，系统开始依次执行文档解析、知识提取、去重、知识保存、Embedding/Vector DB 同步、知识关系识别等阶段。处理期间，其他 API 几乎全部无法响应，包括管理员登录接口，最终客户端超时。

## 二、本次目标

先定位根因，再实施最小范围修复。

只允许修改 `backend/`，不得修改 `admin-web/`、Flutter 客户端或其他前端。

不要假设一定是数据库锁表，也不要直接通过增大连接池、增加 Uvicorn Worker 或修改超时时间来掩盖问题。

## 三、第一阶段：检查实际代码调用链

先检查并列出以下代码的真实路径和职责：

1. 文档处理 API Router。
2. ImportTaskService、KnowledgeImportService。
3. DocumentParser、TextChunker。
4. KnowledgeExtractAgent。
5. KnowledgeDeduplicatePipeline。
6. KnowledgeService、EmbeddingService、Vector DB Repository。
7. KnowledgeRelationAgent 及其关系持久化调用。
8. SQLAlchemy Engine、SessionLocal、数据库 Session 依赖和事务边界。
9. 当前 Uvicorn 启动命令及 Worker 配置。
10. 当前是否使用 BackgroundTasks、线程池或其他后台执行方式。

特别检查：

- 是否存在 `async def` 路由直接调用耗时同步函数。
- 是否在事件循环中执行同步 HTTP 请求、同步 LLM 调用、同步向量检索、同步文件处理或 `time.sleep()`。
- 是否将整个导入流程放在一个长事务中。
- 是否在调用 LLM、Embedding、Vector DB 期间仍然持有数据库连接。
- Session 是否在异常分支未关闭或未回滚。
- 是否存在多个任务共享同一 SQLAlchemy Session。
- 是否有并发导入导致连接池、线程池或模型服务资源耗尽。

## 四、第二阶段：复现并收集证据

在测试环境运行一份实际文档导入，同时并发请求：

- 无数据库依赖的 `/health/live`。
- 管理员登录接口。
- 一个普通知识点查询接口。

为各接口记录请求开始时间、结束时间、状态码和耗时。

为导入阶段记录独立的开始、结束、耗时和异常信息，至少覆盖：

- parse_document
- chunk_document
- extract_knowledge
- deduplicate_knowledge
- save_knowledge
- sync_embeddings
- retrieve_relation_candidates
- generate_relations
- save_relations

在导入期间检查 MySQL `SHOW FULL PROCESSLIST`、`information_schema.innodb_trx`，并在适用时查看 `performance_schema.data_lock_waits`。

检查 SQLAlchemy 连接池配置及相关日志；如能实现，应记录连接 checkout/checkin 情况，以识别连接未归还或连接池耗尽。

## 五、第三阶段：根据证据修复

### 方案 A：事件循环被阻塞

将阻塞操作移出事件循环。不能仅把路由从 `async def` 改成 `def` 后就认定问题解决；必须进一步验证长任务不会导致其他接口失去响应。

### 方案 B：数据库连接池耗尽或长事务

缩短事务范围。仅在必要的数据读取和写入阶段持有 Session/事务；调用 LLM、Embedding、向量检索和进行文档解析时，不得继续持有不必要的数据库事务或连接。

确保每个线程或后台任务使用独立、正确管理生命周期的 Session，异常时正确 rollback/close。

### 方案 C：Worker 或线程池饱和

将耗时较长的 ImportTask 执行过程从 API 请求执行路径中分离。

在不引入 Redis、Celery、RabbitMQ 的前提下，优先评估使用现有 MySQL 导入任务表作为任务队列，并新增一个独立运行的 Worker 进程。

建议目标流程：

1. API 验证任务并保存 PENDING 状态。
2. API 提交事务后立即返回任务 ID，适合时使用 HTTP 202。
3. Worker 领取待处理任务，并通过原子操作或可靠的任务领取机制避免多个 Worker 重复执行同一任务。
4. Worker 更新 PROCESSING、步骤和进度，执行已有处理链。
5. 成功或失败后保存真实任务结果及可诊断的错误信息。
6. API 的任务查询接口继续负责查询状态与结果，不能等待整个导入任务完成。

初期限制并发处理数为 1。不为本次修复引入不必要的新基础设施，也不要重新实现已有 Agent。

如当前架构存在更简单且可靠的修复方案，先说明证据和取舍，再实施。对执行耗时较长的完整 AI 导入任务，不能只依赖增加 HTTP 超时时间解决问题。

### 事务与数据正确性要求

- 不允许用一个跨越整个导入任务的数据库事务包住所有步骤。
- MySQL 中已成功提交的知识点不能因为后续关系 Agent 失败而丢失。
- 保留已有知识去重和关系幂等逻辑。
- 防止多个 Worker 同时领取同一任务，重复创建知识点或关系。
- 任务中断后不能直接无条件重复执行全部步骤，必须符合现有状态和幂等设计。
- 数据库、向量同步、关系生成失败必须分别记录，不得把未完成的任务错误标记为 SUCCESS。

## 六、必须执行的回归测试

1. 不运行导入时，健康检查、登录、知识点查询正常。
2. 运行导入时，上述 API 仍能在合理时间内响应。
3. 导入流程所有步骤能够正常结束，并记录各步骤耗时。
4. 同一任务不会被多个 Worker 重复处理。
5. 连接池和数据库事务在成功、异常分支都能正确释放。
6. 关系生成失败不会破坏已保存的知识点。
7. 重复导入不会产生大量重复知识点或关系。
8. 原有 Auth、Knowledge、Question、ImportTask、Dashboard 和关系 CRUD 回归测试全部通过。

## 七、交付报告

完成后必须反馈：

1. 实际根因及对应的代码证据、日志或诊断结果。
2. 修改文件及每项修改的目的。
3. 修复前后的并发测试结果。
4. 各导入阶段耗时。
5. SQLAlchemy 连接池、事务管理的检查结果。
6. 自动化测试的真实执行结果。
7. 未执行或因环境限制失败的测试，不得声称通过。

本任务先解决全站 API 在导入期间失去响应的问题，再讨论性能优化。禁止凭猜测直接大范围重构。