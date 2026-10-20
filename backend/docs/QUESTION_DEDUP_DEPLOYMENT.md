# 题目去重服务部署与运维说明

适用范围：`backend/`（FastAPI + MySQL + 进程内存向量索引 + 本地 Embedding + MiMo LLM）。本文回答《题目去重服务专项加固与真实环境验收执行文档》§11 的 10 个部署问题。

## 1. 向量索引是否内存态

**是。** 题目向量索引是进程内存态 FAISS（`agent/common/vector_store.py` 的 `FaissVectorStore`，独立于知识向量库的 `get_question_vector_store()` 单例），**不落盘、不持久化**。进程重启后索引为空，需要重新构建（见第 2 点）。MiMo 生成/复核结果和指纹、审计记录（`question_dedup_record`）以 MySQL 为唯一事实源，向量索引只是加速召回的可重建副本。

## 2. 服务启动时是否自动构建

**是。** `app/main.py` 的 FastAPI `lifespan` 启动钩子在对外服务前执行 `initialize_question_index(db)`：

- 状态机：`initializing` →（构建完成）`ready` /（失败）`degraded`；
- 幂等：默认 `only_missing=True`，已有且 `embedding_version` 匹配的向量跳过；
- 记录：`total/success/failed/duration_seconds/embedding_model/embedding_version`，通过 `GET /api/v1/question-dedup/status` 可查；
- 也可手动触发：`POST /api/v1/question-dedup/index/rebuild`（管理员）或 `python scripts/build_question_embeddings.py --all`（注意：脚本在脚本进程内构建，**不恢复服务进程的索引**，见第 7 点）。

## 3. 启动构建期间是否接受生成任务

**不接受。** 创建生成任务（`POST /api/v1/question-generation/tasks`）时检查就绪状态：`initializing` 或 `degraded` 直接返回明确错误（"题目去重服务未就绪（status=...），当前不允许创建生成任务"），**绝不静默跳过语义去重**。执行中的任务若发现索引转为 `degraded`，安全中止并把任务标记失败（或按重试规则处理），同样不静默降级。

## 4. 是否强制单 worker

**是。** 启动钩子检测 `--workers`/`WEB_CONCURRENCY`/`UVICORN_WORKERS`，发现多 worker 直接 `RuntimeError` 拒绝启动：

```
检测到多 worker 配置（workers=N）：题目去重向量索引为进程内存态，多进程无法保证语义去重一致性。
请以单 worker/单进程启动（uvicorn --workers 1），或引入共享向量存储后另行改造。
```

**不支持多进程部署**：跨进程精确指纹有 MySQL `dedup_key` 唯一索引兜底，但语义去重（向量召回 + LLM）只在单进程内可靠。多进程部署前必须先引入共享向量存储/持久化索引并另行改造（见报告 G 节）。

## 5. 如何查询索引状态

- `GET /api/v1/question-dedup/status`（管理员）：`status`（disabled/initializing/ready/degraded）、`reason`、构建统计、`recent_failures`（最近索引写失败，含 question_id 与错误）、阻断题目数、阈值与指纹版本；
- 健康检查 `GET /health` 为公开端点，仅返回基础存活信息，不暴露向量内容/提示词/密钥；
- 就绪语义：`degraded` **不等于**空索引可用——`degraded` 时生成任务被拒绝，避免"没查到候选"被误当"没有重复"。

## 6. 如何手动重建

- 服务进程内（推荐，恢复服务索引）：`POST /api/v1/question-dedup/index/rebuild?only_missing=true`；
- 离线/一致性检查：`python scripts/build_question_embeddings.py --all`（重建）/ `--check`（对比 MySQL 与索引差异）；
- 重算指纹（如标准化算法升级后）：`python scripts/rehash_questions.py --dry-run` 先看冲突清单，确认后去掉 `--dry-run` 实跑；脚本**不删除任何历史题目**，重复组只输出报告供人工裁决。

## 7. 新题入库/编辑/审核/驳回/下架的索引同步

| 事件 | 指纹 `dedup_key` | 向量索引 |
| --- | --- | --- |
| 新题入库（pending_review） | 登记（参与阻断） | 立即写入（guarded_save 锁内） |
| 编辑（改题干/选项/答案） | 重算 v1→当前版本指纹并同步 | 重新向量化覆盖 |
| 审核通过 published | 保持登记 | 保持（状态元数据更新） |
| 驳回 rejected / 下架 disabled | 置 NULL（不再阻断新题） | 移除/停用（不再作为候选） |

**同步失败的后果与恢复**：向量写失败不会让入库失败，但会把就绪状态降级为 `degraded` 并记录 `question_id`+错误（`recent_failures`）；此时新生成任务被安全拒绝（见第 3 点）。恢复方式：在**服务进程内**执行 `POST /api/v1/question-dedup/index/rebuild`（幂等，只补缺失），状态回到 `ready`。独立脚本构建的索引在脚本进程内存中，对服务进程无效——恢复必须走服务进程内接口。

## 8. MiMo 需要哪些环境变量

`.env`（参考 `.env.example`，**不要把密钥写进代码/日志/报告**）：

- `LLM_API_KEY`、`LLM_API_BASE`、`LLM_MODEL`（MiMo 复核与生成）；
- `EMBEDDING_MODEL`（本地 FlagModel 路径）、`EMBEDDING_USE_FP16`、`EMBEDDING_VERSION`（向量元数据版本）；
- 去重阈值（默认值即生产值，不建议改）：`QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD=0.65`、`QUESTION_DEDUP_CROSS_SCOPE_HIGH_THRESHOLD=0.75`、`QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD=0.85`；
- 其余：`QUESTION_DEDUP_ENABLED`、`QUESTION_DEDUP_VECTOR_TOP_K=15`、`QUESTION_DEDUP_LLM_MAX_CANDIDATES=5`、`QUESTION_DEDUP_LLM_BATCH_SIZE=5`、`QUESTION_DEDUP_MAX_REGENERATION_ATTEMPTS=2`、`QUESTION_DEDUP_MAX_GENERATION_MULTIPLIER=1.5`、`QUESTION_DEDUP_LLM_TIMEOUT_SECONDS=60`；
- `MYSQL_*`、`JWT_SECRET`、`UPLOAD_DIR` 等基础配置同既有部署。

日志脱敏：请求日志中间件不记录密码/JWT 密钥/数据库密码/API Key（既有约定，本次未放宽）。

## 9. 多进程支持与否

**不支持**（见第 4 点）。单进程内线程并发是受支持的：最终入库在进程级短时锁内完成"最终校验→入库→向量索引写入"，MySQL `dedup_key` 唯一索引兜底精确指纹的并发/跨进程竞争。

## 10. 管理员状态接口说明

`/api/v1/question-dedup/*` 全部要求管理员 JWT（`get_current_admin`）：

- `GET /status`：索引与阈值状态（不暴露向量内容/提示词/密钥）；
- `GET /records`：去重审计（task_id / question_id / decision / needs_manual_review 过滤，分页）；
- `GET /stats/{task_id}`：任务去重统计（duplicate/distinct/uncertain、LLM 调用数）；
- `POST /index/rebuild`：进程内重建（幂等）。

## 附：uncertain（不确定）题目的处理约定

LLM 复核超时/非法输出/语义层不可用时，判定为 `uncertain` 并**保留题目**（不伪装成 duplicate），`needs_manual_review=true` 写入审计；任务详情的 `dedup_review_status`（manual_review_required/deduplicated/clean）与 `dedup_manual_review_count` 可查。人工在审核流中裁决（现有 pending_review 流程覆盖）。
