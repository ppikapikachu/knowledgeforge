# 题目多层去重服务实现报告

> 任务来源：`docs/12、题目生成去重/DSH_题目多层去重服务开发与接入执行文档.md`
> 实施范围：仅后端（backend/），不改前端。
> 执行日期：2026-10-20。本报告只记录真实执行过的内容；未执行/未验证项在第 14 节如实标注。

---

## 1. 当前状态与根因

**改造前问题（根因）**：

1. `content_hash` 只算题干（16 位小写哈希），选项顺序、全半角、标点都会造成漏判/误判；且**只存不查**——生成时算好写入 `question.content_hash`，但没有任何环节用它拦截重复题。
2. `question.content_hash` 无唯一约束，并发任务可同时写入同一道题。
3. 生成链路没有语义去重：新题不与历史题、不与同批其他新题比对，重复题可直接入库。
4. `QuestionGenerationTask.duplicate_count` 只在 API 回显，从未累加。
5. 向量能力只有知识点库（`get_vector_store()`，id=`knowledge_{id}`），题目没有独立向量命名空间。

**改造后**：四层去重（精确指纹 → 关键词+向量召回 → 范围阈值 → 批量 LLM 复核）接入生成保存链路；指纹带版本、DB 唯一约束兜底并发；任务统计字段真实累计；题目独立向量命名空间 + 历史索引重建命令。

## 2. 变更文件清单

**新增**：

| 文件 | 职责 |
|---|---|
| `app/services/question_normalizer.py` | 标准化 + 指纹 v1（NFKC、全半角、空白、选项签名、大小写敏感标识保留）+ 文本相似度 + 关键词 + 向量文本 |
| `app/services/question_dedup_service.py` | `QuestionDeduplicationService`（check_one/check_batch/index_question/remove_or_deactivate_index/rebuild_missing_vectors/get_dedup_stats/verify_before_save/guarded_save）+ `LLMQuestionReviewer`（批量复核、超时/非法输出→uncertain）+ `sync_question_dedup_state`/`refresh_question_hash` |
| `app/models/question_dedup_record.py` | 去重审计表 `question_dedup_record` |
| `agent/question_dedup/__init__.py`、`schemas.py`、`prompts.py` | LLM 复核结构化输出（`LLMReviewItem` verdict=duplicate/distinct/uncertain）与批量复核提示词（明确"同一主题≠重复"） |
| `migrations/versions/f6a7b8c9d0e1_question_dedup.py` | 指纹版本/去重唯一键/审计表/任务统计字段迁移 |
| `scripts/rehash_questions.py` | 历史题目指纹 v1 重算（幂等、可 dry-run、输出历史重复报告、不删数据） |
| `scripts/build_question_embeddings.py` | 历史题目向量索引构建/一致性检查（--all/--check/--only-missing） |
| `scripts/calibrate_question_dedup_thresholds.py` | 标注样本阈值校准（真实 Embedding 打分 + 误判/漏判评估） |
| `tests/test_question_dedup.py` | 45 项：标准化、范围矩阵、14 个重复样例、LLM 调用次数、并发、降级、状态、审计 |
| `tests/test_question_dedup_runner.py` | 5 项：生成任务接入去重的集成（统计/重试上限/不确定保留/不回归/自动分配） |
| `tests/test_question_dedup_smoke.py` | 4 项：真实 FlagModel + 真实 FAISS 冒烟（模型缺失时 skip） |

**修改**：

| 文件 | 变更 |
|---|---|
| `app/models/question.py` | +`hash_version`（String(8) default "0"）、+`dedup_key`（String(64) nullable，阻断状态=指纹）；唯一索引 `uq_question_dedup_key`、查询索引 `idx_question_content_hash` |
| `app/models/question_generation_task.py` | +`generated_count`/`exact_duplicate_count`/`semantic_duplicate_count`/`uncertain_count`/`unfulfilled_count` |
| `app/models/__init__.py` | 注册 QuestionDedupRecord |
| `app/services/background_runner.py` | 抽出可测核心 `execute_generation_task(task_id, request_config, session_factory=None)`；接入 check_batch + guarded_save + 限量重试补足 + 统计 |
| `agent/question_generate/agent.py` | `generate_content_hash` 委托 `question_normalizer.compute_content_hash`（v1 指纹） |
| `agent/common/config.py`、`.env.example` | 题目去重配置 12 项（见第 7 节） |
| `agent/common/vector_store.py` | `FaissVectorStore.list_ids()/get_metadata()`；独立题目向量单例 `get_question_vector_store()`（与 knowledge 库隔离） |
| `app/api/v1/question_generation.py` | 任务列表/详情输出新统计字段；进度上限 100；发布/驳回时 `sync_question_dedup_state` 同步 dedup_key 与索引 |
| `app/services/question_service.py` | 编辑后 `refresh_question_hash`；软删除同步（dedup_key 置空 + 索引移除） |

## 3. 调用链

```
POST /api/v1/question-generation/tasks（manual/auto）
  → run_generation_in_background（daemon thread）
    → execute_generation_task（可单测同步核心）
      → QuestionGenerateAgent.generate_for_plan_item（按知识点+题型+难度生成 N 道候选）
      → snapshot_from_generated（候选 → 去重视图）
      → QuestionDeduplicationService.check_batch（任务级共享 batch_context）
           ├─ normalize_and_hash（指纹 v1）
           ├─ check_exact_hash（全局精确层，命中即 duplicate，LLM 0 次）
           ├─ retrieve_keyword_candidates（关键词召回）
           ├─ retrieve_vector_candidates（题目向量 Top-K）
           ├─ classify_scope（same_scope / cross_scope）
           ├─ calculate_algorithm_scores（fused = 0.6×向量 + 0.4×文本）
           ├─ apply_scope_thresholds（同范围 0.65 / 跨范围 0.75）
           └─ llm_review_shortlist（批量复核，≤5 对/题，5 对/次调用）
      → guarded_save（写锁内 verify_before_save 二次校验 + 原子写入 + IntegrityError 兜底）
      → index_question（MySQL 先落库，再写向量；失败可 rebuild 恢复）
      → 限量重试补足（≤2 轮，≤1.5 倍生成量）
      → 任务统计与状态收尾
```

人工编辑/审核链路：`update_question` → `refresh_question_hash`（重算指纹+索引）；`review` 发布/驳回、`delete` 软删 → `sync_question_dedup_state`（dedup_key 同步 + 索引登记/移除）。

## 4. 指纹规则与索引

**指纹 v1**（`hash_version="1"`，sha256 取前 32 位）：

- 标准化：Unicode NFKC → 全角标点映射半角 → 去首尾空白与句末标点 → **移除全部空白**；**不做小写化**（`HashMap`/`C/C++`/`JDK 8`/`==`/`===` 大小写与符号敏感保留）。
- 选项：剥离 `^[A-Fa-f][.、．:：)）]` 标签后参与；签名 = (选项内容, 是否正确) 排序拼接 → **选项顺序无关**，但正确答案分布不同 = 不同题。
- 签名 = `题型 | 标准化题干 | 选项签名 | 答案`；答案位仅对判断题/简答题参与（选择题答案由选项签名承载）。题型参与签名：同题干单选/简答 = 不同指纹。
- 旧指纹（题干小写 16 位）标 `hash_version="0"`，由 `scripts/rehash_questions.py` 重算。

**DB 索引**：

- `uq_question_dedup_key`（unique）：`dedup_key` 仅在阻断状态（pending_review/published）登记指纹，其余状态为 NULL（MySQL 唯一索引允许多 NULL）→ rejected/disabled 不阻断新题，阻断状态下全局唯一由数据库强制。
- `idx_question_content_hash`（非唯一）：精确层查询索引。
- 状态切换（发布/驳回/下架/编辑）都经 `sync_question_dedup_state`/`refresh_question_hash` 同步 dedup_key 与向量索引。

## 5. 复用的 Embedding / VectorStore / 命名空间

- Embedding：**完全复用** `agent/common/embedding.py`（本地 FlagModel，`BAAI/bge-small-zh-v1.5`，512 维，fp16）。
- VectorStore：**完全复用** `agent/common/vector_store.py` 的 `FaissVectorStore`（线程安全、内积归一化=余弦、numpy 降级）；未引入新向量数据库。
- 命名空间：新增独立题目单例 `get_question_vector_store()`，与知识点库物理隔离；题目向量 id = `question_{id}`。
- 向量文本 = 题型 + 题干 + 选项内容（不含知识点名、不含解析）；metadata = `question_id/question_bank_id/knowledge_ids/question_type/status/embedding_model/embedding_version`。MySQL 为唯一事实源，向量库可随时重建。

## 6. 历史索引构建命令与执行结果

```bash
python scripts/rehash_questions.py            # 历史指纹重算（幂等，可 --dry-run）
python scripts/build_question_embeddings.py --all   # 全量构建
python scripts/build_question_embeddings.py --check # 一致性检查（缺失误差可 --only-missing 修复）
```

**真实执行记录（2026-10-20，项目 venv Python 3.14.5，torch 2.14.0+cpu）**：

| 命令 | 结果 |
|---|---|
| `alembic upgrade head` | e5f6a7b8c9d0 → **f6a7b8c9d0e1** 成功 |
| `rehash_questions.py` | `{'total': 26, 'updated': 26, 'skipped': 0, 'dedup_key_registered': 23, 'dedup_key_null_for_duplicate': 0}`；输出历史重复 **1 组**：指纹 `f7cf66b8ca8a3e99f4f08668aef3119f` 对应 `question_id=[1, 2]` —— **未删除**，按文档要求仅报告，建议人工裁决保留其一 |
| `build_question_embeddings.py --all` | `{'total': 23, 'success': 23, 'failed': 0, 'skipped': 0}`（真实 FlagModel fp16 + FAISS） |
| `build_question_embeddings.py --check` | 脚本进程内"缺失=23"——内存态向量库跨进程不共享的预期表现（见 13/14 节），重建即恢复 |
| `calibrate_question_dedup_thresholds.py` | 见第 7 节校准表 |

## 7. 范围规则与阈值依据

**范围分类**（`_classify_scope`）：

- 新题无知识点 → cross_scope + 警告 `NEW_QUESTION_HAS_NO_KNOWLEDGE`（走严格规则）。
- `question_bank_id` 相同 **且** 知识点相交 → same_scope（常规去重，宽召回）；否则 cross_scope（严格过滤）。
- 精确指纹层不受范围影响：全局命中即 duplicate（0 次 LLM）。

**阈值（配置项，2026-10-20 真实 Embedding 标定后写入默认值）**：

| 配置 | 值 | 含义 |
|---|---|---|
| `QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD` | **0.65** | 同范围候选进入 LLM 复核的下限 |
| `QUESTION_DEDUP_CROSS_SCOPE_HIGH_THRESHOLD` | **0.75** | 跨范围进入 LLM 复核的高阈值（严于同范围） |
| `QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD` | 0.85 | 入库前二次校验直接拦截（防误杀取严格值） |
| `QUESTION_DEDUP_VECTOR_TOP_K` / `KEYWORD_TOP_K` | 15 / 15 | 双通道召回数 |
| `QUESTION_DEDUP_LLM_MAX_CANDIDATES` / `LLM_BATCH_SIZE` | 5 / 5 | 每题复核对数上限 / 每次调用批量 |
| `QUESTION_DEDUP_MAX_REGENERATION_ATTEMPTS` / `MAX_GENERATION_MULTIPLIER` | 2 / 1.5 | 重试补足轮数上限 / 生成量倍数上限 |
| `QUESTION_DEDUP_ENABLED` / `LLM_TIMEOUT_SECONDS` | true / 60 | 总开关 / 单次复核超时 |

**校准数据（真实 bge-small-zh-v1.5，fused = 0.6×向量 + 0.4×文本）**：

| 样本 | 期望 | 范围 | kw | vec | fused |
|---|---|---|---|---|---|
| S01 完全相同题干 | 重复 | same | 1.000 | 1.000 | 1.000 |
| S02 空格/标点不同 | 重复 | same | 1.000 | 0.996 | 0.998 |
| S03 选项顺序变化 | 重复 | same | 1.000 | 0.998 | 0.999 |
| S04 同答案改写题干 | 重复 | same | 0.481 | 0.862 | 0.710 |
| S05 同知识点不同角度 | 不重复 | same | 0.320 | 0.426 | 0.384 |
| S06 不同关键词不同主题 | 不重复 | same | 0.446 | 0.759 | 0.634 |
| S07 跨题库题干相同 | 重复 | cross | 1.000 | 1.000 | 1.000 |
| S08 跨题库仅知识关联 | 不重复 | cross | 0.209 | 0.701 | 0.504 |
| S09 单选 vs 简答相似题干 | 不重复 | same | 0.812 | 0.816 | 0.815 |
| S10 同批次内部重复 | 重复 | same | 1.000 | 1.000 | 1.000 |
| S11 并发任务写同一题 | 重复 | same | 1.000 | 1.000 | 1.000 |
| S12 不同审核状态（rejected 旧题） | 不重复 | — | 状态过滤层处理，不进阈值评估 | | |

阈值扫描：same_scope 0.40~0.60 误判 3/漏判 0；**0.65~0.70 误判 2/漏判 0**；cross_scope **0.75~0.95 误判 0/漏判 0**。选定 same=0.65、cross=0.75（跨范围严格于同范围，且各期望重复样本 0 漏判）。误判=不重复样本进入复核（复核≠误杀，如 S09 进复核后由 LLM 判 distinct 保留）。

## 8. LLM 触发条件、批处理与调用次数验证

**触发条件**：仅当算法融合分 ≥ 范围阈值的候选对进入复核；精确指纹命中、跨范围低/中相似度**不触发**。无任何"全库逐条 LLM 比对"路径。

**批处理**：每题最多 `QUESTION_DEDUP_LLM_MAX_CANDIDATES`(5) 对，按 `LLM_BATCH_SIZE`(5) 对/次批量调用；结构化输出 `{"pairs":[{"pair_id","verdict","reason"}]}`，schema 校验 + 有限重试；超时/非法 JSON/缺对 → 该对 `uncertain`（保留新题 + 人工复核标记），**绝不静默判 distinct**。提示词明确"同一主题≠重复、同知识点不同角度=distinct、选项顺序/全半角不影响"。

**调用次数验证（mock spy，`TestLLMCallThresholds`）**：

| 场景 | LLM 调用 | 结果 |
|---|---|---|
| 精确指纹命中 | 0 | duplicate/exact_hash |
| 跨库低相似度 | 0 | distinct/algorithm_only |
| 跨库中相似度 | 0 | distinct/algorithm_only |
| 跨库高相似度 | ≥1 | 进复核 |
| 同范围相似候选 | ≥1 | 进复核 |
| 全库比对 | 不存在 | 候选对数 ≤ 上限 |

## 9. 批次与并发去重

- **批内**：check_batch 维护任务级 `batch_context`（跨目标共享），已通过的新题作为后续候选；已判 duplicate 的候选**不再**成为有效保留题（`guarded_save` 拦截时同步移出 accepted）。
- **并发**：`guarded_save` 模块级 RLock 内执行"verify_before_save + save_fn + commit"短临界区（LLM 调用在锁外）；verify_before_save 二次精确哈希校验 + 严格语义门槛（0.85，跳过本轮已复核过的候选，避免推翻 LLM distinct 结论）；DB 唯一索引 `uq_question_dedup_key` + IntegrityError 兜底跨进程竞争。10 线程并发写同一题 → 1 条入库（`test_case11` 实证）。
- **写序**：MySQL 先落库再写向量；向量失败记日志不阻塞，`rebuild_missing_vectors` 可完整恢复；MySQL 始终是事实源。

## 10. 重新生成与生成上限

每目标（知识点+题型+难度）循环：生成 → 去重 → 通过者入库，直到补足计划数或触顶（`MAX_REGENERATION_ATTEMPTS=2` 轮、`MAX_GENERATION_MULTIPLIER=1.5` 倍生成量）。触顶后差额记 `unfulfilled_count`（不虚报完成）；生成/校验失败累计 `failed_count`；不确定但保留的题计 `uncertain_count` 并带人工复核标记。任务统计：`generated_count`（实际生成候选）/ `exact_duplicate_count` / `semantic_duplicate_count`（含批内）/ `duplicate_count=exact+semantic`（字段兼容保留）/ `success_count`（入库数）/ `unfulfilled_count` / `failed_count`。状态：补足全部=success，部分=partial_success，0=failed。

## 11. 数据库迁移与回滚

迁移 `f6a7b8c9d0e1`（down_revision `e5f6a7b8c9d0`）：

1. `question` +`hash_version`（server_default "0"）、+`dedup_key`；
2. 背书 `dedup_key=content_hash`（仅阻断状态），重复组保最小 id、其余置 NULL（不删数据）后建 `uq_question_dedup_key` 唯一索引 + `idx_question_content_hash`；
3. `question_generation_task` +5 统计字段（server_default "0"）；
4. 建审计表 `question_dedup_record`（含 hash/快照/两侧题库与知识点/范围/三层分数/LLM 结论/最终判定/Embedding 模型版本）+ 3 个查询索引。

**downgrade**：只删新增列/表/索引，**不删业务数据**。已在开发库执行成功；`rehash_questions.py` 幂等可重跑（--dry-run 预演）。

## 12. 测试与真实冒烟

**`python -m pytest tests/` = 141 passed**（项目 venv，2026-10-20 实跑）：

| 测试文件 | 数量 | 覆盖 |
|---|---|---|
| `tests/test_question_dedup.py` | 45 | 标准化 8（空格/标点/选项序/答案/大小写/题型/标签剥离/相似度）；范围矩阵 5 行；LLM 调用次数 5；14 个重复样例全量（含同知识点不同角度不误杀、跨库近似、批内重复、并发 10 线程、LLM 超时/非法 JSON→uncertain、Embedding/向量故障降级、4 种状态处理）；审计与统计；状态同步；结果 schema |
| `tests/test_question_dedup_runner.py` | 5 | 任务级统计正确、重试上限与 unfulfilled、uncertain 保留计数、正常生成不回归、auto 分配多目标 |
| `tests/test_question_dedup_smoke.py` | 4 | **真实 FlagModel + 真实 FAISS**：索引元数据与语义召回（同题改写得分高于无关题）、精确层 0 LLM、rebuild 幂等、题目库与知识库隔离 |
| 既有回归（auth/knowledge/question/import/dashboard/demand/mapping 等） | 87 | 全部通过，无回归 |

**真实冒烟（非 mock）**：真实 Embedding（bge-small-zh-v1.5 fp16）+ 真实 FAISS 索引 23/23 成功、语义召回验证、阈值校准 12 样本（第 7 节数据即真实打分）。LLM 复核的真实 API 调用见第 14 节标注。

## 13. 误判、一致性与性能

- **误判优先级**：宁可漏判不误杀——不同角度同知识点题（S05 fused=0.384）不进复核直接保留；S09 型（相似但不同题型）进复核后由 LLM 判 distinct 保留；最终拦截门槛取严格值 0.85 且跳过已复核候选。校准各阈值点漏判均为 0。
- **一致性**：MySQL 事实源 + 写序（DB→向量）+ rebuild 命令幂等恢复 + `question_dedup_record` 全量判定审计。已知：向量库为进程内存态（沿用既有 FaissVectorStore 设计），跨进程/重启不共享，`--check` 在独立进程会报缺失，属预期；恢复=重建（实证 23/23）。
- **性能**：Embedding 每新题只算 1 次；候选合并去重后按分数截断 5 对进 LLM；LLM 批量 5 对/次；短临界区锁不覆盖 LLM；生成链路无全库扫描（精确层走索引，召回层 Top-K=15）。

## 14. 未完成项 / 未验证项 / 已知限制（如实标注）

1. **LLM 真实 API 复核调用未验证**：本次执行环境无外网（PyPI 不可达），LLM 复核的触发条件、批量结构、超时/非法输出降级均由 mock/单测+spy 验证（8/12/13 节），但**未做真实 MiMo API 的端到端复核冒烟**。部署后建议跑一轮真实生成任务确认。
2. **向量索引持久化未做**：`FaissVectorStore` 是进程内存态（既有设计，未新建向量数据库），服务重启后需重跑 `build_question_embeddings.py --all` 或启动时调 `rebuild_missing_vectors`；多进程部署下各进程索引独立，DB 唯一约束与精确层兜底正确性，语义层召回依赖本进程索引（建议单进程部署或后续加持久化，超出本次"最小改动"边界）。
3. **历史重复数据未清理**：`question_id=[1,2]`（指纹 `f7cf66b8ca8a3e99f4f08668aef3119f`）为历史重复，按文档要求只报告不删除，需人工裁决。
4. 既有告警未处理（非本任务范围）：`datetime.utcnow()` deprecation、SQLAlchemy `Query.get()` legacy 警告。
5. 真实 Embedding 冒烟依赖项目 venv（`D:\pythonproject\knowledgeforge\.venv`，含 FlagEmbedding/torch/faiss）；系统默认 Python 3.14 无 FlagEmbedding，测试会自动 skip 冒烟项——CI 需使用项目 venv。

**验收对照**：同范围常规去重 ✓（S01-S06、45 项用例）；跨范围严格过滤、仅极端相似进 LLM ✓（S07/S08、spy 5 项）；指纹命中 0 次 LLM ✓；无全库 LLM ✓；新题/历史题/批内/并发全覆盖 ✓（14 样例 + 并发测试）；索引同步可恢复 ✓（rebuild 幂等 23/23）；统计准确 ✓（runner 5 项集成）；旧生成模式与审核流无回归 ✓（87 项既有测试）。
