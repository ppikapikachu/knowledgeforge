# 题目去重服务专项加固与真实环境验收报告

> 依据：`docs/12、题目生成去重/DSH_题目去重服务专项加固与真实环境验收执行文档.md`（§1–§14）
> 范围：仅 `backend/`（app/agent/scripts/tests/migrations/docs 与 `.env.example`）；未改 `frontend/`、Flutter 及无关模块。
> 日期：2026-10-20（Asia/Shanghai）。阈值未改动：同范围 0.65 / 跨范围 0.75 / 最终阻断 0.85，融合 0.6×向量 + 0.4×关键词。

---

## A. 发现的问题、根因和修改

| # | 问题 | 是否真实 | 根因 | 修改文件 | 修复方式 | 迁移 | 阈值/规则变更 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0-1 | 向量索引不随服务启动初始化，无法证明服务进程内索引完整 | 真实（实读 `app/main.py` 无 startup/lifespan，`initialize_question_index` 无调用方） | 向量索引为进程内存态单例，只有独立脚本/出题时惰性写入；脚本进程索引与服务进程不共享 | `app/main.py`（lifespan + `_detect_worker_count`）、`app/services/question_dedup_service.py`（`initialize_question_index`、`DedupReadiness`）、`app/services/background_runner.py`、`app/api/v1/question_generation.py`、新 `app/api/v1/question_dedup.py`、`app/api/router.py` | 启动 lifespan 同步幂等构建（状态机 initializing→ready/degraded）；多 worker 配置启动即 `RuntimeError` 阻止；创建任务时非 ready 拒绝（明确错误）；执行中转 degraded 安全中止；索引写失败记 `question_id`+错误并降级，绝不静默跳过语义层 | 无表结构迁移（索引可重建） | 否 |
| P0-2 | 语义改写题并发可双双入库（最终门槛 0.85 漏掉 0.65~0.84 区间，且初次检索早于对方落库） | 真实（§3.1 竞争窗口实证：两任务初次 check_batch 互不可见） | 最终校验只按 0.85 单阈值拦截、无 LLM 复核、不复检"复核后才出现"的候选；REPEATABLE READ 快照甚至看不到并发线程已提交的行 | `app/services/question_dedup_service.py`（`verify_before_save` 重写、`guarded_save` 重写）、`app/services/background_runner.py` | 锁内流程改为 `commit 旧事务 → 最终校验 → 中段候选（范围阈值 ≤ fused < 0.85）LLM 复核（dup→拦 / uncertain→不入库转有限补生成 / distinct→放行）→ 入库 → 锁内写向量索引 → commit`；不复用过期结果（rivals 重新核验）；LLM 不占行锁（调用发生在无长事务状态）；跨进程精确指纹仍由 `dedup_key` 唯一索引兜底 | 无 | 否（阈值只做分段路由，未下调） |
| P0-3 | 标准化删**全部**空白会把 `System.out.println("a b")` 与 `("ab")` 错误并成同指纹 | 真实（v1 `_WS_RE.sub("", t)`） | v1 指纹对全文无差别去空白，破坏代码/字符串语义 | `app/services/question_normalizer.py`（HASH_VERSION="2" 全量重构）、`app/services/question_dedup_service.py`（`_find_exact_hash` 加 `hash_version` 过滤）、`app/models/question_dedup_record.py`、`scripts/rehash_questions.py` | v2：字符串/行内代码字面量**原样保留**（含空格）；中文段折叠空白+删除紧邻 CJK 的空格，英文词边界保留（`JDK 8`≠`JDK8`）；代码块围栏剥除但内容同规则归一；技术标识大小写、`==`/`===`、`C`/`C++` 参与指纹；选项标签剥离、顺序无关签名保留（答案映射随行） | 是：指纹 v1→v2 重算（`scripts/rehash_questions.py`，先 dry-run 后实跑；26/26 更新，历史重复 1 组仅报告不删除；旧新指纹不混比（查询按 `hash_version` 过滤）） | 否（签名算法升级为 v2，属 §4 允许范围；阈值与融合权重不变） |
| P1 | 真实 MiMo LLM 复核链路未验收 | 真实（此前只有 Mock/桩） | 无 API 冒烟工具 | 新 `scripts/llm_review_smoke.py`、`app/services/question_dedup_service.py`（`LLMQuestionReviewer.call_count`） | 7 用例真实 API 冒烟（见 E） | 无 | 否 |
| P1 | uncertain（不确定）结果不可追踪、语义层故障可能被静默判 distinct | 真实 | v1 中 LLM 失败→uncertain 有记录，但 API/DTO 不暴露；embedding/向量故障走"退化"路径可能落成 distinct | `app/api/v1/question_dedup.py`、`app/api/v1/question_generation.py`、`app/schemas/question.py`、`app/api/v1/question.py`、`app/services/question_dedup_service.py` | 语义层不可用→`uncertain`+`needs_manual_review`（不入库伪装 duplicate、不静默 distinct）；`GET /question-dedup/records`（task_id/question_id/decision/needs_manual_review 过滤）；任务详情 `dedup_review_status`+`dedup_manual_review_count`；题目详情 `dedup_review_status` | 无 | 否 |
| 附 | `guarded_save` 把 FK 违规静默计为重复 | 真实（1452 误分类） | IntegrityError 未区分类别 | `app/services/question_dedup_service.py:796-808` | 仅 MySQL 1062（唯一键冲突）按重复处理，其余完整性错误回滚后上抛 | 无 | 否 |
| 附 | 历史数据 `hash_version` 默认值 "1" 与现版本不符 | 真实 | v2 升级后默认值未同步 | `app/models/question_dedup_record.py` | 默认值改 "2" | 无（列已有，值修正随 rehash） | 否 |
| 附 | LLM 复核（10~20s）期间持有 MySQL 查询事务，与测试 teardown 的 DDL 元数据锁互锁（`DROP TABLE` `Waiting for table metadata lock` 实证） | 真实（§3.3.7 违反） | `check_one`/`guarded_save` 的查询事务在 LLM 调用结束前未提交；后台 daemon 线程长事务与 `drop_all` 排他元数据锁互相等待 | `app/services/question_dedup_service.py`（两处 LLM 调用前 `db.rollback()` 释放事务；`guarded_save` 复核后增加精确指纹终验）、`app/services/background_runner.py`（`_spawn` 线程注册 + `join_background_tasks`）、`tests/conftest.py`（收尾先等后台线程再 drop） | LLM 调用只持进程级写锁、不持任何 MySQL 事务/元数据锁；复核窗口内新出现的精确重复由锁内终验兜住 | 无 | 否 |

**是否修改阈值或去重规则**：均未修改。同范围 0.65 / 跨范围 0.75 / 最终阻断 0.85、融合 0.6/0.4、Top-K 15、LLM 上限 5 pair/题保持 §7 校准值；新增的仅是"最终校验的中段区间不再绕过复核"（§3.3 强制要求，属于补齐规则而非收紧阈值）。

---

## B. 向量索引生命周期

- **初始化**：FastAPI `lifespan`（`app/main.py`）对外服务前 `initialize_question_index(db)`：仅索引 `pending_review`/`published` 题（排除 rejected/disabled），使用当前 Embedding 模型与 `EMBEDDING_VERSION`，幂等（`only_missing=True`，版本匹配跳过），记录 `total/success/failed/duration_seconds/embedding_model/embedding_version`。真实数据实测：24 题全量构建 2.8s（success 24/failed 0）。
- **状态机**：`disabled`（`QUESTION_DEDUP_ENABLED=false`）/ `initializing` / `ready` / `degraded`。`degraded` **不等于**空索引可用；非 ready 时创建生成任务被拒绝并返回明确错误，执行中转 degraded 则安全中止剩余生成——"没查到候选"永远不会被当成"没有重复"。
- **失败与一致性**：向量写失败→日志+题目 ID+`recent_failures`+`degraded`（入库不失败但任务受控）；MySQL 是唯一事实源，索引为可重建副本；重建与实时写入由进程级写入锁串行化，互不覆盖；恢复必须在**服务进程内** `POST /api/v1/question-dedup/index/rebuild`（脚本构建的是脚本进程索引）。
- **部署约束**：强制单 Uvicorn worker/单进程（多 worker 启动即拒绝）；不支持多进程语义一致性（见 G）。
- **状态查询**：`GET /api/v1/question-dedup/status`（管理员）。

## C. 并发语义去重

保护模型：召回可并行；最终入库在进程级短时锁内 `commit → 最终校验 → 中段 rivals LLM 复核 → 入库 → 索引写入`；刚保存已阻断的新题会被后续最终校验看到（校验前先 `commit` 结束 REPEATABLE READ 旧快照）；初次不存在的候选进入 rivals 复核，复核 uncertain 则**不入库**并转有限补生成；跨进程精确指纹由 MySQL `dedup_key` 唯一索引兜底。

并发专项（`tests/test_question_dedup_hardening.py`，14/14 通过）实测记录：

| 场景 | 输入与题目关系 | 实际融合分 | 保存结果 |
| --- | --- | --- | --- |
| 10 线程同题 | 同内容、指纹相同 | 1.00（精确层） | 只存 1，其余 `unique_constraint`/精确拦截 |
| 2 线程同知识点语义改写（**指纹不同**） | "HashMap 的底层数据结构是什么？请简述。" vs "Java 中 HashMap 的底层采用什么数据结构实现？" | 文本 0.593→融合 0.593（同范围，阈值 0.25 下进 rivals） | 只存 1（先到者保存，后到者 `semantic_concurrent_duplicate` 拦截，LLM 复核 duplicate） |
| 跨知识点高相似（>0.75） | 同题干不同知识点 | ≥0.75 | 进跨范围 LLM 复核（calls≥1），按结论保存 |
| 跨题库 | 精确指纹相同 | 1.00 | 全局拦截 `global_exact`（LLM 0 调用）；低/中相似跨库 0 调用、不误杀 |
| 并发不同题 | 互不相似 | 低 | 都保留（不误杀） |
| LLM 判 distinct 后竞争 | 双方初次复核都判 distinct，落库有先后 | 中段区间 | 后到方对新增候选**重新核验**（rivals LLM 调用），distinct 则都保存——证明不沿用过期结果 |

真实 Embedding 竞争（`TestRealEmbeddingSemanticRace`，真实 FlagModel + FAISS 语义改写对）：并发只存 1。

## D. 标准化/指纹（HASH_VERSION = 2）

v2 归一规则（`app/services/question_normalizer.py`）：

| 输入差异 | 结果 | 说明 |
| --- | --- | --- |
| 代码块围栏内缩进/换行不同 | 同指纹 | 围栏剥除 + 段内空白折叠（plain 段规则统一） |
| `println("a b")` vs `println("ab")` | **不同指纹** | 字符串/行内代码字面量原样保留（含空格） |
| `HashMap` vs `hashmap` | 不同指纹 | 大小写参与 |
| `==` vs `===`、`C` vs `C++`、`JDK 8` vs `JDK 18` | 不同指纹 | 运算符/技术标识参与 |
| `JDK 8` vs `JDK8` | 不同指纹 | 英文词边界保留（宁可进向量层复核，不为 hash 命中率破坏语义，§4.2） |
| 选项标签 `A.`/`A、` 变化 | 同指纹 | 标签剥离、正文参与 |
| 选项顺序变、答案映射不变 | 同指纹 | 排序 (内容, is_correct) 签名 |
| 选项顺序变、答案映射变 | 不同指纹 | 正确性关系随行 |
| 单选 vs 简答（同文字） | 不同指纹 | 题型参与 |
| 中文全半角标点 | 同指纹 | NFKC + 标点映射（仅确认等价） |

**版本迁移（v1→v2）**：`scripts/rehash_questions.py --dry-run` 先输出冲突清单（不删历史）→ 实跑：`{'total': 26, 'updated': 26, 'skipped': 0, 'dedup_key_registered': 23, 'dedup_key_null_for_duplicate': 0}`；q14/15/22 指纹变化（英文词空格/字符串差异），其余为版本号更新；历史重复 1 组（指纹 f7cf66b8ca8a3e99f4f08668aef3119f，question_id=[1, 2]）**保留待人工裁决，不删除不合并**；重算幂等；`_find_exact_hash` 按 `hash_version` 过滤，旧新指纹不同规则比较。

## E. 真实 LLM 验收（MiMo `mimo-v2.6-pro`，真实 API 调用）

`scripts/llm_review_smoke.py` 7 用例全部通过（API Key 未出现在任何日志/报告/代码）：

| 用例 | 判定 | LLM 调用 | 耗时 | 说明 |
| --- | --- | --- | --- | --- |
| C1 同范围语义改写 | duplicate | 1 | 17.8s | 高相似进复核 |
| C2 同范围相似、不同角度 | distinct | 1 | 3.1s | 不误杀（同主题≠重复） |
| C3 跨范围低/中相似 | distinct/algorithm_only | **0** | — | 触发条件达标 |
| C4 跨范围极高相似（同内容、答案不同、指纹不同、知识点不交集） | duplicate | 1 | — | cross_scope, matched=29 |
| C5 批内 3 pair 批量 | dup/distinct/dup | **1**（单次调用 3 pair） | 9.92s | 逐 pair 对应，无错位 |
| C6a 非法 JSON / C6b 字段缺失 / C6c 超时(1s) | 全部 uncertain | 各 1 | 3.04s（超时用例，不阻塞） | 不静默 distinct；schema 校验拒绝无效输出 |
| C7 端到端：真实生成 2 题 → check_batch | [duplicate, distinct] | 1 | 生成 10.36s / 复核 18.8s | 生成 0 失败 |

指标口径：每用例记录 called/calls_delta/batch pair 数/verdict/耗时/schema 校验结果；单题平均 LLM 调用 ≈ 0.5（仅高相似进入复核）；整任务耗时见 F 性能表。

## F. 测试结果

- 去重专项 4 文件：**82 passed / 34.12s**（`test_question_dedup.py` 45、`test_question_dedup_runner.py` 5、`test_question_normalizer_v2.py` 18（§4.5 12 项 + 补充）、`test_question_dedup_hardening.py` 16（§3.4 六场景 + 最终门槛中段/范围阈值一致性 + 向量生命周期 + 真实 Embedding 竞争 2 组））。
- 阈值验证用例按 §12.3 用调用计数断言：hash 命中 0 次、跨范围低/中 0 次、跨范围高相似 ≥1 次、同范围相似 ≥1 次、无全库 LLM（候选截断 LLM_MAX_CANDIDATES=5）。
- 真实 Embedding/FAISS：`test_question_dedup_smoke.py`（服务内语义召回）与 `TestRealEmbeddingSemanticRace` 真实通过（模型路径存在，非 Mock）。

### F-补：全量回归与真实进程内验证（最终数字，以此为准）

**1. 全量回归：`175 passed` / 183.89s**（`python -m pytest tests/`，2026-10-20，.venv Python 3.14.5）：

| 测试文件 | 数量 | 说明 |
| --- | --- | --- |
| 既有回归（auth/dashboard/import_task/knowledge/knowledge_base_mapping/question/question_demand 等） | 87 | 全过，无回归 |
| tests/test_question_dedup.py | 45 | 四层去重、范围矩阵、LLM 调用次数、审计 |
| tests/test_question_dedup_runner.py | 5 | 生成任务集成、补生成上限、统计口径 |
| tests/test_question_normalizer_v2.py | 18 | §4.5 标准化 12 项 + 补充 |
| tests/test_question_dedup_hardening.py | 16 | §3.4 并发 6 场景、门槛一致性、生命周期、真实 Embedding 竞争 |
| tests/test_question_dedup_smoke.py | 4 | 真实 FlagModel+FAISS（未 Mock） |
| **合计** | **175** | 4 项 skipped 为 0（真实模型可用，未 skip） |

已知耗时点（非故障）：`test_update_question` 78s = 真实 FlagModel 首次加载（单例一次性）；session teardown 62s = `join_background_tasks(30s)` 等后台生成线程 + `drop_all`（事务边界修复后不再互锁死等，修复前表现为 dots 打完后无限等待 `DROP TABLE ... Waiting for table metadata lock`）。

**2. 真实 FastAPI 进程内验证**（`scripts/_lifecycle_probe.py`，TestClient 触发真实 lifespan；真实 dev 库 + 真实 bge-small-zh-v1.5 + FAISS）：

| 验收点 | 结果 |
| --- | --- |
| 启动自动初始化索引（lifespan，不依赖手动脚本） | ready，total 24 / success 24 / failed 0 / skipped 0，耗时 57.53s（含模型加载 36.9s；纯构建 2.8s） |
| 服务进程内查索引数量/状态 | `GET /question-dedup/status` 逻辑同源：index_count=24，readiness ready |
| 重启再验（幂等） | boot2：skipped 24 / 0.01~0.02s，ready，`/health` healthy |
| 新题入库立即可召回 | 新题（id=31/32）`index_ok=true`、`recall_new_question=true` |
| 驳回/下架不再阻断 | 驳回后 `dedup_key=NULL`、同指纹新题 `verify_before_save blocked=false`、索引条目移除（count 回 24） |
| 索引损坏/失败任务明确错误不静默 | 单测覆盖（`test_index_write_failure_marks_degraded`、`test_degraded_rejects_new_generation_tasks`、`test_semantic_unavailable_blocks_save_safely`）+ 探针 ready 路径 |

**3. 性能记录**（§10，真实环境）：历史题总数 24（blocking）；启动索引 2.8s（模型已载）/57.5s（含首次模型加载）；单题 `check_one` 含真实 LLM 复核平均 6.6s（10 次采样 4.2~16.4s）；批量 20 题 98.2s（20 次 LLM 调用，全部判重命中）；Top-K=15；FAISS 内存 24×512×4B≈48KB（向量本体）。

**4. 收口期修复（详见 A 表附 3）**：LLM 复核期间释放 MySQL 事务（§3.3.7）、`guarded_save` 复核后精确指纹终验、后台线程注册与 `join_background_tasks`、conftest 收尾等待——修复后全量 175 passed 稳定复现。

## G. 已知限制

1. **多进程不支持**：向量索引为进程内存态、写入锁为进程级；多 worker 启动被阻止。跨进程仅精确指纹（`dedup_key` 唯一索引）可靠。多进程部署需先引入共享向量存储/持久化索引（未实施，避免过度设计）。
2. **向量索引不持久化**：重启后由 lifespan 重建（幂等、实测 24 题 2.8s）；期间创建任务被拒绝（有界、明确错误）。
3. **历史重复人工裁决**：question_id=[1, 2]（指纹 f7cf66b8ca8a3e99f4f08668aef3119f）保留不删；`dedup_key` 仅登记其一（MIN(id)），重复清理/合并留待人工。
4. **LLM 复核依赖外部 MiMo API**：超时/限流/非法输出→uncertain 保留（不阻塞任务、不误判 duplicate）；网络不可用时语义复核降级为不确定标记，不会静默放行跨范围高相似。
5. **性能口径**：check_one 含真实 LLM 复核平均 6.6s；批量 20 题（20 次 LLM）98.2s——LLM 是主要耗时，已按 pair 批量（batch_size=5）压缩调用次数。
6. **拒绝/下架题的历史指纹记录**：`question_dedup_record` 保留审计（含 rejected 时期的判定），状态变化只影响后续参与资格，不回溯删除审计。

---

## H. 验收对照（文档 §14 十三项）

| # | 验收项 | 结果 | 证据 |
| --- | --- | --- | --- |
| 1 | 服务启动自动初始化向量索引 | ✅ | lifespan 实跑：24 题 ready（F-补 表 2） |
| 2 | 索引未就绪/失败不静默跳过语义去重 | ✅ | degraded 拒任务、执行中安全中止、语义不可用→uncertain（A 表 P0-1/P1） |
| 3 | 部署约束明确（单 worker/单进程） | ✅ | 多 worker 启动即 RuntimeError；`QUESTION_DEDUP_DEPLOYMENT.md` |
| 4 | 同范围 hash 不同的语义重复并发不双存 | ✅ | `test_2_threads_semantic_rewrite_only_one_saved` + 真实 Embedding 版（saved==1） |
| 5 | 跨范围高相似并发安全 | ✅ | `test_cross_knowledge_high_similarity_enters_llm_review` 等 §3.4 场景 |
| 6 | 语义不同不误杀 | ✅ | `test_mid_band_distinct_not_killed`、`test_concurrent_distinct_questions_all_kept`、真实 distinct 竞争双存 |
| 7 | 最终校验不用 0.85 绕过 0.65/0.75 | ✅ | `test_rivals_use_scope_threshold_not_final_gate` + `test_mid_band_candidates_go_to_review_not_bypassed` |
| 8 | 代码/字符串空白不被抹除 | ✅ | v2 12 项标准化测试（"a b"≠"ab" 等） |
| 9 | 历史题未删 | ✅ | 迁移/重算只报告不删除；[1,2] 保留 |
| 10 | 原有测试 + 新增测试全过（准确数字） | ✅ | **175 passed / 183.89s**（原 141 + 新增 34；F-补 表 1） |
| 11 | 真实 Embedding 在 API 服务进程内验证 | ✅ | `_lifecycle_probe.py`（真实 lifespan 内召回/幂等/驳回） |
| 12 | 真实 MiMo API LLM 验收 | ✅ | C1-C7 全部真实调用通过（E）；API Key 未写入任何文件 |
| 13 | 交付报告 | ✅ | 本文件 + `QUESTION_DEDUP_DEPLOYMENT.md` |
