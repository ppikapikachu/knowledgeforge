"""QuestionDeduplicationService：题目多层去重服务（执行文档《DSH_题目多层去重服务开发与接入执行文档》）。

四层防线：
1. 精确层：normalize_and_hash + check_exact_hash（全局、状态过滤 + DB 唯一键兜底）；
2. 召回层：关键词通道 + 向量通道（独立题目向量库，Top-K 可配）；
3. 范围阈值层：classify_scope + calculate_algorithm_scores + apply_scope_thresholds
   （同范围宽召回 / 跨范围高阈值）；
4. LLM 复核层：llm_review_shortlist（批量复核 shortlist，不做全库逐条比较）。

范围规则（§2）：
- same_scope（同题库 且 知识点相交）：常规去重，中高相似进入 LLM 复核；
- cross_scope（跨题库 或 知识点不相交）：严格过滤，仅极高相似进入 LLM；
- 精确指纹命中：无论范围一律判重，0 次 LLM 调用；
- 无知识点新题：按 cross_scope 处理并记录告警。

结论三态（§6）：duplicate / distinct / uncertain；LLM 超时或非法输出 → uncertain
（保留新题 + 标记人工复核），绝不静默判 distinct。
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agent.common.config import agent_settings
from agent.common.embedding import get_embedding_service
from agent.common.vector_store import get_question_vector_store
from agent.question_dedup.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, build_pair_block
from agent.question_dedup.schemas import LLMReviewItem, LLMReviewOutput
from app.models.question import Question
from app.models.question_dedup_record import QuestionDedupRecord
from app.models.question_knowledge import QuestionKnowledge
from app.models.question_option import QuestionOption
from app.services.question_normalizer import HASH_VERSION, question_normalizer

logger = logging.getLogger(__name__)

# 阻断新题的状态（§4.3）：待审 + 已发布；rejected/disabled 默认不阻断
BLOCKING_STATUSES = ("pending_review", "published")

# 短时串行化写入锁（§8）：仅覆盖"入库前二次校验 + 落库"窗口。
# 临界区可包含"针对新竞争候选的有限 LLM 复核"（批量 ≤ LLM_MAX_CANDIDATES、
# 总超时 LLM_TIMEOUT_SECONDS）——不持有 MySQL 行锁/长事务，事务只在 save_fn
# 内短暂开启。
_write_lock = threading.RLock()


# =====================================================================
# §2.3 就绪状态机（题目向量索引生命周期，进程级单例）
# =====================================================================

class DedupReadiness:
    """题目去重（向量索引）就绪状态机。

    - initializing：启动/重建进行中，语义去重尚不可用；
    - ready：索引构建成功，语义去重完整可用；
    - degraded：索引构建/写入失败或不完整。不得当作空索引，也不得
      静默只跑指纹/关键词就继续批量出题（§2.3/§2.4）；
    - disabled：QUESTION_DEDUP_ENABLED=false，显式关闭语义去重。
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # 初值 ready：生产服务进程由 FastAPI lifespan 同步执行启动初始化
        # （initializing → ready/degraded）；测试/脚本等未走启动钩子的进程
        # 视为空索引但可用（空索引 ≠ 不可用，没有题即没有重复候选）。
        self.status: str = "ready"
        self.reason: Optional[str] = "进程内尚未执行启动初始化（测试/脚本场景）"
        self.stats: Dict[str, Any] = {}
        self.failures: List[Dict[str, Any]] = []

    def reset(self, status: str = "ready", reason: Optional[str] = None) -> None:
        """重置状态（测试隔离/手动恢复用）。"""
        with self._lock:
            self.status = status
            self.reason = reason
            self.stats = {}
            self.failures = []

    def set_status(self, status: str, reason: Optional[str] = None) -> None:
        with self._lock:
            self.status = status
            self.reason = reason

    def set_stats(self, stats: Dict[str, Any]) -> None:
        with self._lock:
            self.stats = dict(stats)

    def mark_index_failure(self, question_id: Optional[int], error: str) -> None:
        """向量索引写入失败（§2.5）：记录题目 ID + 原因并置 degraded。"""
        with self._lock:
            self.failures.append({"question_id": question_id, "error": str(error)[:500]})
            if self.status != "disabled":
                self.status = "degraded"
                self.reason = f"向量索引写入失败 question_id={question_id}"

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "reason": self.reason,
                "stats": dict(self.stats),
                "failure_count": len(self.failures),
                "recent_failures": list(self.failures[-5:]),
            }


_readiness = DedupReadiness()


def get_dedup_readiness() -> Dict[str, Any]:
    """就绪状态查询（只读，供 API/任务启动前检查）。"""
    return _readiness.snapshot()


def get_dedup_readiness_status() -> str:
    return _readiness.status


def reset_dedup_readiness(status: str = "ready", reason: Optional[str] = None) -> None:
    """重置就绪状态（测试隔离用）。"""
    _readiness.reset(status, reason)


# =====================================================================
# 数据结构
# =====================================================================

@dataclass
class QuestionSnapshot:
    """一道题的去重视图（新题与库内候选共用）。"""

    question_type: str
    content: str
    answer: str = ""
    options: List[Tuple[str, str, int]] = field(default_factory=list)  # (option_key, option_content, is_correct)
    question_bank_id: Optional[int] = None
    knowledge_ids: List[int] = field(default_factory=list)
    question_id: Optional[int] = None
    status: Optional[str] = None
    content_hash: Optional[str] = None
    vector: Optional[List[float]] = None

    def option_pairs(self) -> List[Tuple[str, int]]:
        return [(content, is_correct) for _key, content, is_correct in self.options]

    def ensure_hash(self, normalizer=question_normalizer) -> str:
        if not self.content_hash:
            self.content_hash = normalizer.compute_content_hash(
                self.question_type, self.content, self.answer, self.option_pairs()
            )
        return self.content_hash

    def vector_text(self, normalizer=question_normalizer) -> str:
        opts = [(key, content) for key, content, _c in self.options]
        return normalizer.build_vector_text(self.question_type, self.content, opts)


def snapshot_from_generated(q, question_bank_id: Optional[int],
                            knowledge_ids: Optional[List[int]] = None) -> QuestionSnapshot:
    """从 QuestionGenerateAgent 的 GeneratedQuestion 构建快照。"""
    options = [(opt.option_key, opt.option_content, 1 if opt.is_correct else 0) for opt in q.options]
    kids = list(knowledge_ids or [])
    if getattr(q, "knowledge_id", None) and q.knowledge_id not in kids:
        kids.append(q.knowledge_id)
    return QuestionSnapshot(
        question_type=q.question_type,
        content=q.content,
        answer=q.answer or "",
        options=options,
        question_bank_id=question_bank_id,
        knowledge_ids=kids,
    )


@dataclass
class DedupCheckResult:
    """单题去重判定结果（§7.1 结果结构 + 运行期补充字段）。"""

    decision: str                      # duplicate / distinct / uncertain
    scope_mode: Optional[str] = None   # same_scope / cross_scope / global_exact / batch_internal
    matched_question_id: Optional[int] = None
    matched_source: Optional[str] = None   # db / batch
    decision_method: str = "algorithm_only"  # exact_hash / algorithm_only / vector_and_llm / batch_internal
    algorithm_score: float = 0.0
    llm_reason: Optional[str] = None
    needs_manual_review: bool = False

    # 补充审计字段
    content_hash: str = ""
    hash_version: str = HASH_VERSION
    keyword_score: float = 0.0
    vector_score: float = 0.0
    candidate_count: int = 0
    llm_called: bool = False
    warning: Optional[str] = None
    matched_question_bank_id: Optional[int] = None
    matched_knowledge_ids: Optional[List[int]] = None
    reviewed_question_ids: List[int] = field(default_factory=list)
    reviewed_content_hashes: List[str] = field(default_factory=list)
    review_pairs: List["ReviewPair"] = field(default_factory=list)
    pair_verdicts: Dict[int, str] = field(default_factory=dict)
    pair_reasons: Dict[int, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "scope_mode": self.scope_mode,
            "matched_question_id": self.matched_question_id,
            "decision_method": self.decision_method,
            "algorithm_score": round(float(self.algorithm_score), 4),
            "llm_reason": self.llm_reason,
            "needs_manual_review": self.needs_manual_review,
        }


@dataclass
class ReviewPair:
    """进入 LLM 复核 shortlist 的一组配对。"""

    pair_id: int
    new: QuestionSnapshot
    candidate: QuestionSnapshot
    candidate_source: str              # db / batch
    scope: str                         # same_scope / cross_scope
    algorithm_score: float
    keyword_score: float = 0.0
    vector_score: float = 0.0


@dataclass
class TaskContext:
    """任务上下文（审计用）。"""

    task_id: Optional[int] = None
    question_bank_id: Optional[int] = None
    question_type: Optional[str] = None
    difficulty: Optional[int] = None


# =====================================================================
# LLM 复核（§6）：批量、结构化、失败→uncertain
# =====================================================================

class LLMQuestionReviewer:
    """LLM 批量复核器：多组配对一次调用；超时/非法输出/异常一律回 uncertain。"""

    def __init__(self, llm: Any = None, batch_size: Optional[int] = None,
                 timeout: Optional[int] = None):
        self._llm = llm
        self.batch_size = batch_size or agent_settings.QUESTION_DEDUP_LLM_BATCH_SIZE
        self.timeout = timeout or agent_settings.QUESTION_DEDUP_LLM_TIMEOUT_SECONDS
        self.call_count = 0  # LLM 请求次数（触发条件验证用，§12.3）

    def _get_llm(self):
        if self._llm is None:
            from agent.common.llm import get_llm
            self._llm = get_llm(thinking="enabled")
        return self._llm

    def review(self, pairs: Sequence[ReviewPair],
               knowledge_name_fn: Optional[Callable[[List[int]], str]] = None,
               pair_index_offset: int = 0) -> Dict[int, LLMReviewItem]:
        """批量复核，返回 {pair_id: LLMReviewItem}；未返回/异常的 pair 一律 uncertain。"""
        results: Dict[int, LLMReviewItem] = {}
        for start in range(0, len(pairs), self.batch_size):
            chunk = list(pairs[start:start + self.batch_size])
            results.update(self._review_chunk(chunk, knowledge_name_fn))
        return results

    def _review_chunk(self, chunk: List[ReviewPair],
                      knowledge_name_fn: Optional[Callable[[List[int]], str]]) -> Dict[int, LLMReviewItem]:
        name_fn = knowledge_name_fn or (lambda ids: "、".join(str(i) for i in ids) or "（无）")
        pairs_block = []
        for p in chunk:
            pairs_block.append(build_pair_block(
                pair_id=p.pair_id,
                new_type=p.new.question_type,
                new_content=p.new.content,
                new_options=p.new.options,
                new_answer=p.new.answer,
                new_knowledge=name_fn(p.new.knowledge_ids),
                cand_type=p.candidate.question_type,
                cand_content=p.candidate.content,
                cand_options=p.candidate.options,
                cand_answer=p.candidate.answer,
                cand_knowledge=name_fn(p.candidate.knowledge_ids),
                algorithm_score=p.algorithm_score,
                scope=p.scope,
            ))
        user_prompt = USER_PROMPT_TEMPLATE.format(
            pair_count=len(chunk), pairs_block="\n".join(pairs_block)
        )

        out: Optional[LLMReviewOutput] = None
        last_error: Optional[Exception] = None
        retries = max(0, int(agent_settings.AGENT_MAX_RETRIES))
        for attempt in range(retries + 1):
            try:
                self.call_count += 1
                raw = self._invoke_with_timeout(
                    lambda: self._get_llm().invoke(
                        [("system", SYSTEM_PROMPT), ("user", user_prompt)]
                    ),
                    self.timeout,
                )
                content = getattr(raw, "content", raw)
                out = self._parse_output(content, chunk)
                break
            except Exception as exc:  # noqa: BLE001 —— 任何失败都不能冒充 distinct
                last_error = exc
                logger.warning("题目去重 LLM 复核失败(第 %s 次): %s", attempt + 1, exc)

        results: Dict[int, LLMReviewItem] = {}
        for p in chunk:
            if out is not None:
                item = next((i for i in out.pairs if i.pair_id == p.pair_id), None)
                if item is not None:
                    results[p.pair_id] = item
                    continue
            # 缺失/失败 → uncertain（保留新题并标记人工复核）
            reason = f"LLM 复核失败/超时/非法输出，按 uncertain 处理: {last_error}" if last_error \
                else "LLM 未返回该配对结论，按 uncertain 处理"
            results[p.pair_id] = LLMReviewItem(pair_id=p.pair_id, verdict="uncertain", reason=reason)
        return results

    def _parse_output(self, content: Any, chunk: List[ReviewPair]) -> LLMReviewOutput:
        """解析并校验 LLM 输出；不合法抛 ValueError（走 uncertain 通道）。"""
        import json
        import re

        if isinstance(content, LLMReviewOutput):
            parsed = content
        else:
            text = content if isinstance(content, str) else str(content)
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                raise ValueError(f"LLM 输出不含 JSON: {text[:200]}")
            data = json.loads(m.group(0))
            parsed = LLMReviewOutput.model_validate(data)
        valid_ids = {p.pair_id for p in chunk}
        cleaned = [i for i in parsed.pairs if i.pair_id in valid_ids and i.verdict in ("duplicate", "distinct", "uncertain")]
        if not cleaned:
            raise ValueError("LLM 输出无有效配对结论")
        parsed.pairs = cleaned
        return parsed

    @staticmethod
    def _invoke_with_timeout(fn: Callable[[], Any], timeout: float) -> Any:
        box: Dict[str, Any] = {}

        def _run():
            try:
                box["result"] = fn()
            except Exception as exc:  # noqa: BLE001
                box["error"] = exc

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            raise TimeoutError(f"LLM 复核调用超时(>{timeout}s)")
        if "error" in box:
            raise box["error"]
        return box.get("result")


# =====================================================================
# 主服务
# =====================================================================

class QuestionDeduplicationService:
    """题目多层去重服务（内部服务，不直接暴露 HTTP API，§11）。"""

    def __init__(self, db: Session, *, llm_reviewer: Any = None,
                 embedding_service: Any = None, vector_store: Any = None):
        self.db = db
        self.normalizer = question_normalizer
        self._llm_reviewer = llm_reviewer
        self._embedding = embedding_service
        self._vector_store = vector_store
        self._knowledge_name_cache: Dict[int, str] = {}

    # ---------- 依赖获取（模块级引用便于测试注入） ----------

    def _get_embedding(self):
        if self._embedding is None:
            self._embedding = get_embedding_service()
        return self._embedding

    def _get_vector_store(self):
        if self._vector_store is None:
            self._vector_store = get_question_vector_store()
        return self._vector_store

    def _get_llm_reviewer(self) -> LLMQuestionReviewer:
        if self._llm_reviewer is None:
            self._llm_reviewer = LLMQuestionReviewer()
        return self._llm_reviewer

    # =================================================================
    # §5-§7 主流程
    # =================================================================

    def check_batch(self, questions: Sequence[QuestionSnapshot],
                    task_context: Optional[TaskContext] = None,
                    batch_context: Optional[Dict[str, Any]] = None) -> List[DedupCheckResult]:
        """批量判定。只有未判重的新题才进入 batch_context 成为后续批次候选（§5.5）。"""
        if batch_context is None:
            batch_context = {"accepted": [], "hashes": set()}
        if not agent_settings.QUESTION_DEDUP_ENABLED:
            # 去重总开关关闭：指纹照算（DB 层仍登记），不进入召回/阈值/LLM
            return [
                DedupCheckResult(
                    decision="distinct",
                    decision_method="algorithm_only",
                    content_hash=q.ensure_hash(self.normalizer),
                    warning="QUESTION_DEDUP_ENABLED=false（去重关闭）",
                )
                for q in questions
            ]
        results: List[DedupCheckResult] = []
        for q in questions:
            result = self.check_one(q, task_context, batch_context)
            results.append(result)
            if result.decision != "duplicate":
                batch_context["accepted"].append(q)
                batch_context["hashes"].add(q.content_hash)
        return results

    def check_one(self, question: QuestionSnapshot,
                  task_context: Optional[TaskContext] = None,
                  batch_context: Optional[Dict[str, Any]] = None) -> DedupCheckResult:
        """单题判定：精确层 → 召回层 → 范围阈值层 → LLM 复核层。"""
        t0 = time.time()
        s = agent_settings
        warnings: List[str] = []
        q_hash = question.ensure_hash(self.normalizer)

        # ---- 1. 精确指纹（全局，状态过滤；命中即判重，0 次 LLM，§2.2） ----
        exact = self._find_exact_hash(q_hash, exclude_id=question.question_id)
        if exact is not None:
            result = DedupCheckResult(
                decision="duplicate", scope_mode="global_exact",
                matched_question_id=exact.id, matched_source="db",
                decision_method="exact_hash", algorithm_score=1.0,
                content_hash=q_hash,
                candidate_count=1,
                matched_question_bank_id=exact.question_bank_id,
                matched_knowledge_ids=self._knowledge_ids_of([exact.id]).get(exact.id, []),
            )
            self._write_records(question, result, task_context)
            return result

        # ---- 2. 批次内候选（§5.5） ----
        candidates: Dict[Tuple[str, Any], Dict[str, Any]] = {}
        if batch_context:
            for prev in batch_context.get("accepted", []):
                prev_hash = prev.ensure_hash(self.normalizer)
                if prev_hash == q_hash:
                    # 批次内指纹相同：直接判重（记录指向胜出候选，
                    # 使胜出题不被此记录误标为 duplicate）
                    result = DedupCheckResult(
                        decision="duplicate", scope_mode="batch_internal",
                        matched_question_id=prev.question_id, matched_source="batch",
                        decision_method="batch_internal", algorithm_score=1.0,
                        content_hash=q_hash, candidate_count=1,
                    )
                    self._write_records(question, result, task_context)
                    return result
                candidates[("batch", id(prev))] = {
                    "snapshot": prev, "source": "batch", "vector_score": 0.0,
                }

        # ---- 3. 关键词通道召回（§5.2/§5.3） ----
        kw_rows = self._retrieve_keyword_candidates(question, top_k=s.QUESTION_DEDUP_KEYWORD_TOP_K)
        for row in kw_rows:
            candidates[("db", row.id)] = {
                "row": row, "source": "db", "vector_score": 0.0,
            }

        # ---- 4. 向量通道召回（Embedding 只计算一次；失败降级不阻塞，§5.1） ----
        vector: Optional[List[float]] = None
        try:
            vector = self._embed(question)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"EMBEDDING_UNAVAILABLE: {exc}")
            logger.warning("题目 Embedding 失败，降级为关键词/指纹去重: %s", exc)
        question.vector = vector
        if vector is not None:
            try:
                for row, vscore in self._retrieve_vector_candidates(question, vector, top_k=s.QUESTION_DEDUP_VECTOR_TOP_K):
                    entry = candidates.get(("db", row.id))
                    if entry is None:
                        candidates[("db", row.id)] = {"row": row, "source": "db", "vector_score": vscore}
                    else:
                        entry["vector_score"] = max(entry["vector_score"], vscore)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"VECTOR_SEARCH_UNAVAILABLE: {exc}")
                logger.warning("题目向量检索失败，降级为关键词/指纹去重: %s", exc)

        # ---- 5. 算法打分 + 范围分类 + 阈值（§2.3/§2.4） ----
        shortlist: List[ReviewPair] = []
        reviewed_ids: List[int] = []
        for entry in candidates.values():
            cand = self._entry_snapshot(entry)
            scope, no_knowledge = self._classify_scope(question, cand)
            if no_knowledge:
                warnings.append("NEW_QUESTION_HAS_NO_KNOWLEDGE: 按 cross_scope 严格规则处理")
            kw_score = self.normalizer.text_similarity(question.content, cand.content)
            vec_score = self._pair_vector_score(question, cand, entry.get("vector_score", 0.0))
            fused = self._fuse(kw_score, vec_score)
            threshold = (s.QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD if scope == "same_scope"
                         else s.QUESTION_DEDUP_CROSS_SCOPE_HIGH_THRESHOLD)
            if fused < threshold:
                continue
            pair = ReviewPair(
                pair_id=len(shortlist) + 1,
                new=question, candidate=cand, candidate_source=entry["source"],
                scope=scope, algorithm_score=fused,
                keyword_score=kw_score, vector_score=vec_score,
            )
            shortlist.append(pair)
            if cand.question_id is not None:
                reviewed_ids.append(cand.question_id)

        shortlist.sort(key=lambda p: -p.algorithm_score)
        shortlist = shortlist[:max(1, int(s.QUESTION_DEDUP_LLM_MAX_CANDIDATES))]
        # 重新编号并只保留实际进入复核的 id
        for i, p in enumerate(shortlist, start=1):
            p.pair_id = i
        reviewed_ids = [p.candidate.question_id for p in shortlist if p.candidate.question_id is not None]
        # 已复核候选指纹（含批次内候选）：入库兜底门槛不得重复拦截 LLM 已判 distinct 的配对
        reviewed_hashes = [
            p.candidate.ensure_hash(self.normalizer) for p in shortlist
            if p.candidate.ensure_hash(self.normalizer)
        ]

        # ---- 6. LLM 复核（仅 shortlist，绝不全库比较，§6） ----
        # §2.2 语义层不可用（Embedding/向量检索失败）时，不得把"没查到候选"
        # 当成"没有重复题"静默放行：精确层结论仍有效，其余一律 uncertain + 人工复核。
        semantic_unavailable = any(
            w.startswith(("EMBEDDING_UNAVAILABLE", "VECTOR_SEARCH_UNAVAILABLE")) for w in warnings)

        if not shortlist:
            result = DedupCheckResult(
                decision=("uncertain" if semantic_unavailable else "distinct"),
                scope_mode=None,
                decision_method="algorithm_only",
                needs_manual_review=semantic_unavailable,
                content_hash=q_hash, candidate_count=len(candidates),
                reviewed_question_ids=reviewed_ids,
                reviewed_content_hashes=reviewed_hashes,
                warning="; ".join(warnings) or None,
            )
            self._write_records(question, result, task_context)
            return result

        # §3.3.7：LLM 调用可能长达十几秒，调用前结束查询事务，
        # 绝不长时间占用 MySQL 事务/元数据锁
        try:
            self.db.rollback()
        except Exception:  # noqa: BLE001
            pass
        try:
            verdicts = self._get_llm_reviewer().review(
                shortlist, knowledge_name_fn=self._knowledge_names_of)
            llm_called = True
        except Exception as exc:  # noqa: BLE001 —— reviewer 内部已兜底，这里再保险
            logger.warning("LLM 复核器异常，全部按 uncertain 处理: %s", exc)
            verdicts = {p.pair_id: LLMReviewItem(pair_id=p.pair_id, verdict="uncertain",
                                                 reason=f"LLM 复核异常: {exc}") for p in shortlist}
            llm_called = True

        duplicates = [p for p in shortlist if verdicts[p.pair_id].verdict == "duplicate"]
        uncertains = [p for p in shortlist if verdicts[p.pair_id].verdict == "uncertain"]
        pair_verdicts = {p.pair_id: verdicts[p.pair_id].verdict for p in shortlist}
        pair_reasons = {p.pair_id: verdicts[p.pair_id].reason for p in shortlist}

        def _mk(decision: str, pair: Optional[ReviewPair], method: str,
                manual: bool = False) -> DedupCheckResult:
            best = pair or max(shortlist, key=lambda p: p.algorithm_score)
            return DedupCheckResult(
                decision=decision,
                scope_mode=("batch_internal" if best.candidate_source == "batch" and method == "batch_internal"
                            else best.scope),
                matched_question_id=best.candidate.question_id,
                matched_source=best.candidate_source,
                decision_method=method,
                algorithm_score=best.algorithm_score,
                llm_reason=verdicts[best.pair_id].reason,
                needs_manual_review=manual,
                content_hash=q_hash,
                keyword_score=best.keyword_score,
                vector_score=best.vector_score,
                candidate_count=len(candidates),
                llm_called=llm_called,
                warning="; ".join(warnings) or None,
                matched_question_bank_id=best.candidate.question_bank_id,
                matched_knowledge_ids=list(best.candidate.knowledge_ids),
                reviewed_question_ids=reviewed_ids,
                reviewed_content_hashes=reviewed_hashes,
                review_pairs=shortlist,
                pair_verdicts=pair_verdicts,
                pair_reasons=pair_reasons,
            )

        if duplicates:
            best = max(duplicates, key=lambda p: p.algorithm_score)
            result = _mk("duplicate", best, "vector_and_llm")
        elif uncertains or semantic_unavailable:
            best = (max(uncertains, key=lambda p: p.algorithm_score) if uncertains else None)
            result = _mk("uncertain", best, "vector_and_llm", manual=True)
        else:
            result = _mk("distinct", None, "vector_and_llm")

        self._write_records(question, result, task_context)
        logger.info(
            "题目去重判定: decision=%s method=%s score=%.3f scope=%s matched=%s llm=%s (%.2fs)",
            result.decision, result.decision_method, result.algorithm_score,
            result.scope_mode, result.matched_question_id, llm_called, time.time() - t0,
        )
        return result

    # =================================================================
    # §8 并发安全写入
    # =================================================================

    def verify_before_save(self, question: QuestionSnapshot,
                           reviewed_question_ids: Optional[Sequence[int]] = None,
                           reviewed_content_hashes: Optional[Sequence[str]] = None) -> Dict[str, Any]:
        """入库前二次校验（并发竞争兜底，§3.3）。在写入锁内、新事务快照下调用。

        - 全局精确指纹命中 → 拦（reason="exact_hash"）；
        - 语义层不可用（Embedding/向量检索失败）→ 安全失败拦
          （reason="semantic_unavailable"），不得静默跳过语义层（§2.4）；
        - 未复核候选融合分 ≥ FINAL_BLOCK(0.85) → 拦（reason="semantic_final_gate"）；
        - 未复核候选融合分落在范围阈值（same 0.65 / cross 0.75）~ 0.85 之间 →
          作为"新竞争候选"放入返回值 rivals，由 guarded_save 在锁内做有限 LLM
          复核——不能只按 0.85 单阈值放过 0.65~0.84 区间（§3.3.4）。
        已进入过 LLM 复核的候选（question_id 或 content_hash 命中）不重复拦截：
        兜底只负责"复核之后才出现"的竞争候选，不推翻 LLM 的 distinct 结论。
        """
        s = agent_settings
        if not s.QUESTION_DEDUP_ENABLED:
            return {"blocked": False, "reason": None, "matched_question_id": None,
                    "algorithm_score": 0.0, "rivals": []}
        q_hash = question.ensure_hash(self.normalizer)
        exact = self._find_exact_hash(q_hash, exclude_id=question.question_id)
        if exact is not None:
            return {"blocked": True, "reason": "exact_hash", "matched_question_id": exact.id,
                    "algorithm_score": 1.0, "rivals": []}

        reviewed = set(reviewed_question_ids or [])
        reviewed_hashes = set(reviewed_content_hashes or [])
        best: Optional[Tuple[float, Any]] = None
        rivals: List[ReviewPair] = []
        semantic_broken = False

        def _consider(row: Question, cand: QuestionSnapshot, kw: float, vec: float) -> float:
            nonlocal best
            fused = self._fuse(kw, vec)
            if best is None or fused > best[0]:
                best = (fused, row)
            scope, _nk = self._classify_scope(question, cand)
            threshold = (s.QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD if scope == "same_scope"
                         else s.QUESTION_DEDUP_CROSS_SCOPE_HIGH_THRESHOLD)
            if threshold <= fused < s.QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD:
                rivals.append(ReviewPair(
                    pair_id=0, new=question, candidate=cand, candidate_source="db",
                    scope=scope, algorithm_score=fused, keyword_score=kw, vector_score=vec,
                ))
            return fused

        for row in self._retrieve_keyword_candidates(question, top_k=s.QUESTION_DEDUP_KEYWORD_TOP_K):
            if row.id in reviewed or (row.content_hash and row.content_hash in reviewed_hashes):
                continue
            cand = self._snapshot_from_row(row)
            kw = self.normalizer.text_similarity(question.content, cand.content)
            fused = _consider(row, cand, kw, 0.0)
            if fused >= s.QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD:
                return {"blocked": True, "reason": "semantic_final_gate",
                        "matched_question_id": row.id, "algorithm_score": fused, "rivals": []}

        vector = question.vector
        if vector is None:
            try:
                vector = self._embed(question)
                question.vector = vector
            except Exception as exc:  # noqa: BLE001
                semantic_broken = True
                logger.warning("入库前 Embedding 失败（语义层不可用，安全失败）: %s", exc)
        if vector is not None:
            try:
                for row, vscore in self._retrieve_vector_candidates(question, vector,
                                                                    top_k=s.QUESTION_DEDUP_VECTOR_TOP_K):
                    if row.id in reviewed or (row.content_hash and row.content_hash in reviewed_hashes):
                        continue
                    cand = self._snapshot_from_row(row)
                    kw = self.normalizer.text_similarity(question.content, cand.content)
                    fused = _consider(row, cand, kw, vscore)
                    if fused >= s.QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD:
                        return {"blocked": True, "reason": "semantic_final_gate",
                                "matched_question_id": row.id, "algorithm_score": fused, "rivals": []}
            except Exception as exc:  # noqa: BLE001
                semantic_broken = True
                logger.warning("入库前向量检索失败（语义层不可用，安全失败）: %s", exc)

        if semantic_broken:
            # §2.4：语义去重不可用时不得把"没查到候选"当"没重复题"
            return {"blocked": True, "reason": "semantic_unavailable",
                    "matched_question_id": None, "algorithm_score": 0.0, "rivals": []}

        rivals.sort(key=lambda p: -p.algorithm_score)
        for i, p in enumerate(rivals, start=1):
            p.pair_id = i
        return {"blocked": False, "reason": None, "matched_question_id": None,
                "algorithm_score": 0.0, "rivals": rivals[:max(1, int(s.QUESTION_DEDUP_LLM_MAX_CANDIDATES))]}

    def guarded_save(self, question: QuestionSnapshot, save_fn: Callable[[], Any],
                     reviewed_question_ids: Optional[Sequence[int]] = None,
                     task_context: Optional[TaskContext] = None,
                     reviewed_content_hashes: Optional[Sequence[str]] = None) -> Tuple[Any, Dict[str, Any]]:
        """短时串行化"最终校验 + 入库 + 向量写入"（§3.3/§8.4）。

        进程级 _write_lock 临界区（单进程部署前提，§3.5）：
        1. commit 提交调用方审计记录并开启新事务快照——能看到其他任务刚提交的题；
        2. verify_before_save：精确指纹 + 语义门槛 + 新竞争候选收集；
        3. 对新竞争候选做有限批量 LLM 复核（≤ LLM_MAX_CANDIDATES、超时保护）——
           不持 MySQL 行锁，事务只在 save_fn 内短暂开启；
        4. save_fn 落库 + commit；唯一键冲突回滚按重复计数；
        5. 锁内写向量索引，保证其他任务的下一次最终校验能看到新题（§3.3.8）；
           索引写失败记日志 + 置 degraded（MySQL 是事实源，不回滚）。
        """
        s = agent_settings
        with _write_lock:
            # 结束旧事务（旧快照），让本次校验看到并发任务已提交的行
            try:
                self.db.commit()
            except Exception:  # noqa: BLE001
                self.db.rollback()
            verdict = self.verify_before_save(question, reviewed_question_ids,
                                              reviewed_content_hashes)
            if verdict.get("blocked"):
                reason = verdict["reason"]
                self._write_records(question, DedupCheckResult(
                    decision=("uncertain" if reason == "semantic_unavailable" else "duplicate"),
                    scope_mode="global_exact" if reason == "exact_hash" else None,
                    matched_question_id=verdict.get("matched_question_id"),
                    matched_source="db",
                    decision_method=("exact_hash" if reason == "exact_hash"
                                     else "algorithm_only" if reason == "semantic_final_gate"
                                     else "semantic_unavailable"),
                    algorithm_score=float(verdict.get("algorithm_score") or 0.0),
                    needs_manual_review=(reason == "semantic_unavailable"),
                    content_hash=question.content_hash or "",
                ), task_context)
                return None, verdict

            # ---- 新竞争候选（初次检查时不存在的）有限 LLM 复核（§3.3.5） ----
            rivals: List[ReviewPair] = list(verdict.get("rivals") or [])
            if rivals:
                # §3.3.7：LLM 调用前结束查询事务，不持 MySQL 事务/元数据锁；
                # 进程级 _write_lock 继续保证同进程互斥
                try:
                    self.db.rollback()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    rverdicts = self._get_llm_reviewer().review(
                        rivals, knowledge_name_fn=self._knowledge_names_of)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("并发竞争候选复核异常，按 uncertain 处理: %s", exc)
                    rverdicts = {p.pair_id: LLMReviewItem(pair_id=p.pair_id, verdict="uncertain",
                                                          reason=f"并发复核异常: {exc}") for p in rivals}
                dup = [p for p in rivals if rverdicts[p.pair_id].verdict == "duplicate"]
                unc = [p for p in rivals if rverdicts[p.pair_id].verdict == "uncertain"]
                if dup or unc:
                    worst = max((dup or unc), key=lambda p: p.algorithm_score)
                    is_dup = bool(dup)
                    self._write_records(question, DedupCheckResult(
                        decision="duplicate" if is_dup else "uncertain",
                        scope_mode=worst.scope,
                        matched_question_id=worst.candidate.question_id,
                        matched_source=worst.candidate_source,
                        decision_method="vector_and_llm",
                        algorithm_score=worst.algorithm_score,
                        keyword_score=worst.keyword_score,
                        vector_score=worst.vector_score,
                        llm_reason=rverdicts[worst.pair_id].reason,
                        needs_manual_review=not is_dup,
                        content_hash=question.content_hash or "",
                        llm_called=True, candidate_count=len(rivals),
                    ), task_context)
                    return None, {
                        "blocked": True,
                        "reason": ("semantic_concurrent_duplicate" if is_dup
                                   else "semantic_concurrent_uncertain"),
                        "matched_question_id": worst.candidate.question_id,
                        "algorithm_score": worst.algorithm_score,
                    }

            # §3.3.5：LLM 复核期间事务已释放——入库前再做一次精确指纹终验
            #（新事务短查询，兜住复核窗口内新出现的精确重复）
            q_hash = question.ensure_hash(self.normalizer)
            late_exact = self._find_exact_hash(q_hash)
            if late_exact is not None:
                self._write_records(question, DedupCheckResult(
                    decision="duplicate", scope_mode="global_exact",
                    matched_question_id=late_exact.id, matched_source="db",
                    decision_method="exact_hash", algorithm_score=1.0,
                    content_hash=q_hash,
                ), task_context)
                return None, {"blocked": True, "reason": "exact_hash",
                              "matched_question_id": late_exact.id, "algorithm_score": 1.0}

            try:
                obj = save_fn()
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                code = getattr(getattr(exc, "orig", None), "args", [None])[0]
                if code == 1062:
                    # DB 唯一键兜底（跨进程竞争）：回滚后按重复计数
                    logger.info("入库唯一键冲突（并发重复题），按重复处理: %s", exc)
                    return None, {"blocked": True, "reason": "unique_constraint",
                                  "matched_question_id": None, "algorithm_score": 1.0}
                # 其他完整性错误（如外键）不是重复信号，不得静默吞掉
                logger.error("入库完整性错误（非唯一键冲突，向上抛出）: %s", exc)
                raise
            except Exception:
                self.db.rollback()
                raise

            # §3.3.8：保存后立即写向量索引（仍在锁内），其他任务的最终校验即可见
            indexed = self.index_question(obj)
            return obj, {"blocked": False, "reason": None,
                         "indexed": indexed, "rivals_reviewed": len(rivals)}

    # =================================================================
    # §10/§11 索引维护
    # =================================================================

    def index_question(self, question: Question) -> bool:
        """MySQL 先落库、向量后写入（§8.5）；失败仅记录，可由 rebuild_missing_vectors 修复。"""
        try:
            opts = sorted(
                [(o.option_key, o.option_content) for o in (question.options or [])],
                key=lambda kv: kv[0],
            )
            text = self.normalizer.build_vector_text(question.question_type, question.content, opts)
            vector = self._get_embedding().embed_text(text)
            metadata = {
                "question_id": question.id,
                "question_bank_id": question.question_bank_id,
                "knowledge_ids": [ka.knowledge_id for ka in (question.knowledge_associations or [])],
                "question_type": question.question_type,
                "status": question.status,
                "embedding_model": agent_settings.EMBEDDING_MODEL,
                "embedding_version": agent_settings.EMBEDDING_VERSION,
            }
            self._get_vector_store().upsert(f"question_{question.id}", vector, metadata=metadata)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("题目向量索引写入失败 question_id=%s: %s", getattr(question, "id", None), exc)
            # §2.5：写失败必须记日志 + 题目 ID + degraded，不得假装入库与索引都成功
            _readiness.mark_index_failure(getattr(question, "id", None), str(exc))
            return False

    def remove_or_deactivate_index(self, question_id: int) -> bool:
        """下架/删除/驳回时移除向量索引（返回是否成功，§11）。"""
        try:
            self._get_vector_store().delete(f"question_{question_id}")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("题目向量索引移除失败 question_id=%s: %s", question_id, exc)
            _readiness.mark_index_failure(question_id, str(exc))
            return False

    def rebuild_missing_vectors(self, batch_size: int = 32, only_missing: bool = True,
                                statuses: Optional[Sequence[str]] = None) -> Dict[str, int]:
        """历史题目向量补建（§10）：批量读取、支持断点续跑、可只补缺失、按版本跳过。"""
        statuses = tuple(statuses or BLOCKING_STATUSES)
        stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
        store = self._get_vector_store()
        existing = set(store.list_ids())
        last_id = 0
        while True:
            rows = (
                self.db.query(Question)
                .filter(Question.id > last_id, Question.status.in_(statuses))
                .order_by(Question.id.asc())
                .limit(batch_size)
                .all()
            )
            if not rows:
                break
            for row in rows:
                last_id = max(last_id, row.id)
                stats["total"] += 1
                key = f"question_{row.id}"
                if only_missing and key in existing:
                    meta = store.get_metadata(key)
                    if meta.get("embedding_version") == agent_settings.EMBEDDING_VERSION:
                        stats["skipped"] += 1
                        continue
                if self.index_question(row):
                    stats["success"] += 1
                    existing.add(key)
                else:
                    stats["failed"] += 1
        return stats

    def get_dedup_stats(self, task_id: Optional[int] = None) -> Dict[str, Any]:
        """去重统计（§11）：审计记录汇总 + 任务批次统计。"""
        q = (
            self.db.query(
                QuestionDedupRecord.decision,
                QuestionDedupRecord.decision_method,
                func.count(QuestionDedupRecord.id),
            )
            .group_by(QuestionDedupRecord.decision, QuestionDedupRecord.decision_method)
        )
        if task_id is not None:
            q = q.filter(QuestionDedupRecord.task_id == task_id)
        by_method: Dict[str, int] = {}
        by_decision: Dict[str, int] = {}
        for decision, method, cnt in q.all():
            by_decision[decision] = by_decision.get(decision, 0) + int(cnt)
            key = f"{decision}:{method}"
            by_method[key] = by_method.get(key, 0) + int(cnt)
        llm_called = 0
        q2 = self.db.query(func.count(QuestionDedupRecord.id)).filter(QuestionDedupRecord.llm_called.is_(True))
        if task_id is not None:
            q2 = q2.filter(QuestionDedupRecord.task_id == task_id)
        llm_called = int(q2.scalar() or 0)
        return {
            "task_id": task_id,
            "records": sum(by_decision.values()),
            "by_decision": by_decision,
            "by_method": by_method,
            "llm_called": llm_called,
        }

    # =================================================================
    # 内部：检索 / 打分 / 范围
    # =================================================================

    def _find_exact_hash(self, content_hash: str, exclude_id: Optional[int] = None) -> Optional[Question]:
        """全局精确指纹匹配。

        只比较当前 HASH_VERSION 的指纹：旧版本指纹与新版本不得同规则比较
        （§4.4），历史行经 scripts/rehash_questions.py 重算后才参与精确层。
        """
        q = (
            self.db.query(Question)
            .filter(Question.content_hash == content_hash,
                    Question.hash_version == HASH_VERSION,
                    Question.status.in_(BLOCKING_STATUSES))
        )
        if exclude_id is not None:
            q = q.filter(Question.id != exclude_id)
        return q.order_by(Question.id.asc()).first()

    def _retrieve_keyword_candidates(self, question: QuestionSnapshot,
                                     top_k: int) -> List[Question]:
        keywords = self.normalizer.extract_keywords(question.content, limit=5)
        if not keywords:
            return []
        conds = [Question.content.like(f"%{kw}%") for kw in keywords]
        q = (
            self.db.query(Question)
            .filter(Question.status.in_(BLOCKING_STATUSES), or_(*conds))
        )
        if question.question_id is not None:
            q = q.filter(Question.id != question.question_id)
        return q.order_by(Question.id.desc()).limit(max(1, top_k)).all()

    def _retrieve_vector_candidates(self, question: QuestionSnapshot,
                                    vector: List[float], top_k: int) -> List[Tuple[Question, float]]:
        store = self._get_vector_store()
        hits = store.search(vector, top_k=max(1, top_k))
        ids: List[int] = []
        scores: Dict[int, float] = {}
        for hit in hits:
            qid = (hit.metadata or {}).get("question_id")
            if qid is None and str(hit.id).startswith("question_"):
                try:
                    qid = int(str(hit.id).split("_", 1)[1])
                except ValueError:
                    continue
            if qid is None:
                continue
            qid = int(qid)
            if qid == question.question_id:
                continue
            ids.append(qid)
            scores[qid] = max(scores.get(qid, 0.0), float(hit.score))
        if not ids:
            return []
        rows = (
            self.db.query(Question)
            .filter(Question.id.in_(ids), Question.status.in_(BLOCKING_STATUSES))
            .all()
        )
        return [(row, scores.get(row.id, 0.0)) for row in rows]

    def _embed(self, question: QuestionSnapshot) -> List[float]:
        return self._get_embedding().embed_text(question.vector_text(self.normalizer))

    @staticmethod
    def _fuse(keyword_score: float, vector_score: float) -> float:
        """融合算法分数：双通道 0.6*向量 + 0.4*文本，缺失通道退化为单通道。"""
        kw = max(0.0, float(keyword_score or 0.0))
        vec = max(0.0, float(vector_score or 0.0))
        if vec > 0 and kw > 0:
            return 0.6 * vec + 0.4 * kw
        return vec if vec > 0 else kw

    @staticmethod
    def _pair_vector_score(question: QuestionSnapshot, cand: QuestionSnapshot,
                           recalled_score: float) -> float:
        if question.vector is not None and cand.vector is not None:
            import math
            va, vb = question.vector, cand.vector
            num = sum(a * b for a, b in zip(va, vb))
            da = math.sqrt(sum(a * a for a in va)) or 1.0
            db_ = math.sqrt(sum(b * b for b in vb)) or 1.0
            return max(0.0, num / (da * db_))
        return max(0.0, float(recalled_score or 0.0))

    def _classify_scope(self, new: QuestionSnapshot,
                        cand: QuestionSnapshot) -> Tuple[str, bool]:
        """范围分类（§2）。返回 (scope, no_knowledge_warning)。"""
        if not new.knowledge_ids:
            return "cross_scope", True
        if new.question_bank_id is None or cand.question_bank_id is None:
            return "cross_scope", False
        if new.question_bank_id != cand.question_bank_id:
            return "cross_scope", False
        if set(new.knowledge_ids) & set(cand.knowledge_ids):
            return "same_scope", False
        return "cross_scope", False

    def _entry_snapshot(self, entry: Dict[str, Any]) -> QuestionSnapshot:
        if entry["source"] == "batch":
            return entry["snapshot"]
        return self._snapshot_from_row(entry["row"])

    def _snapshot_from_row(self, row: Question) -> QuestionSnapshot:
        kids = self._knowledge_ids_of([row.id]).get(row.id, [])
        opts = [(o.option_key, o.option_content, 1 if o.is_correct else 0)
                for o in (row.options or [])]
        return QuestionSnapshot(
            question_type=row.question_type,
            content=row.content,
            answer=row.answer or "",
            options=opts,
            question_bank_id=row.question_bank_id,
            knowledge_ids=kids,
            question_id=row.id,
            status=row.status,
            content_hash=row.content_hash,
        )

    def _knowledge_ids_of(self, question_ids: Sequence[int]) -> Dict[int, List[int]]:
        if not question_ids:
            return {}
        rows = (
            self.db.query(QuestionKnowledge.question_id, QuestionKnowledge.knowledge_id)
            .filter(QuestionKnowledge.question_id.in_(list(question_ids)))
            .all()
        )
        out: Dict[int, List[int]] = {}
        for qid, kid in rows:
            out.setdefault(qid, []).append(kid)
        return out

    def _knowledge_names_of(self, knowledge_ids: Sequence[int]) -> str:
        from app.models.knowledge import Knowledge
        ids = [i for i in (knowledge_ids or []) if i not in self._knowledge_name_cache]
        if ids:
            rows = self.db.query(Knowledge.id, Knowledge.name).filter(Knowledge.id.in_(ids)).all()
            for kid, name in rows:
                self._knowledge_name_cache[kid] = name
        names = [self._knowledge_name_cache.get(i, f"知识点{i}") for i in (knowledge_ids or [])]
        return "、".join(names) if names else "（无）"

    # ---------- 审计记录（§9） ----------

    def _write_records(self, question: QuestionSnapshot, result: DedupCheckResult,
                       task_context: Optional[TaskContext]) -> None:
        try:
            rows: List[QuestionDedupRecord] = []
            pairs = result.review_pairs or []
            if pairs:
                for p in pairs:
                    rows.append(self._build_record(question, result, task_context, p))
            else:
                rows.append(self._build_record(question, result, task_context, None))
            for rec in rows:
                self.db.add(rec)
        except Exception as exc:  # noqa: BLE001 —— 审计失败不阻断主流程
            logger.error("写入去重审计记录失败: %s", exc)

    def _build_record(self, question: QuestionSnapshot, result: DedupCheckResult,
                      task_context: Optional[TaskContext],
                      pair: Optional[ReviewPair]) -> QuestionDedupRecord:
        cand = pair.candidate if pair else None
        pair_id = pair.pair_id if pair else None
        return QuestionDedupRecord(
            task_id=getattr(task_context, "task_id", None),
            new_content_hash=result.content_hash or question.content_hash or "",
            new_hash_version=result.hash_version,
            new_content_snapshot=(question.content or "")[:1000],
            new_question_type=question.question_type,
            new_question_bank_id=question.question_bank_id,
            new_knowledge_ids=list(question.knowledge_ids or []),
            matched_question_id=(cand.question_id if cand else result.matched_question_id),
            matched_question_bank_id=(cand.question_bank_id if cand else result.matched_question_bank_id),
            matched_knowledge_ids=(list(cand.knowledge_ids or []) if cand
                                   else (result.matched_knowledge_ids or [])),
            matched_source=(pair.candidate_source if pair else result.matched_source),
            scope_mode=(pair.scope if pair else result.scope_mode),
            keyword_score=float(pair.keyword_score if pair else result.keyword_score),
            vector_score=float(pair.vector_score if pair else result.vector_score),
            algorithm_score=float(pair.algorithm_score if pair else result.algorithm_score),
            llm_called=bool(result.llm_called),
            llm_decision=(result.pair_verdicts.get(pair_id) if pair_id else None),
            llm_reason=(result.pair_reasons.get(pair_id) if pair_id else result.llm_reason),
            decision=result.decision,
            decision_method=result.decision_method,
            needs_manual_review=result.needs_manual_review,
            embedding_model=agent_settings.EMBEDDING_MODEL,
            embedding_version=agent_settings.EMBEDDING_VERSION,
        )


# =====================================================================
# 状态流转同步（审核通过/驳回/下架时维护 dedup_key 与向量索引，§3.3/§8）
# =====================================================================

def refresh_question_hash(db: Session, question: Question) -> None:
    """编辑题目后重算 v1 指纹并同步去重状态（内容/选项/类型变化时必须调用）。"""
    from app.models.question_option import QuestionOption as QO
    rows = db.query(QO).filter(QO.question_id == question.id).all()
    options = [(o.option_content, 1 if o.is_correct else 0) for o in rows]
    question.content_hash = question_normalizer.compute_content_hash(
        question.question_type, question.content, question.answer or "", options
    )
    question.hash_version = HASH_VERSION
    sync_question_dedup_state(db, question)


def sync_question_dedup_state(db: Session, question: Question) -> None:
    """根据 question.status 同步 dedup_key 与向量索引。

    - 阻断状态(pending_review/published)：dedup_key = content_hash，登记向量索引；
    - 非阻断状态(rejected/disabled)：dedup_key = NULL（不阻塞新题），移除向量索引。
    历史重复数据导致 dedup_key 冲突时保留既有登记（不抛异常）。
    """
    if question.status in BLOCKING_STATUSES and question.content_hash:
        clash = (
            db.query(Question.id)
            .filter(Question.dedup_key == question.content_hash, Question.id != question.id)
            .first()
        )
        if clash:
            logger.warning(
                "dedup_key 冲突（历史重复题），保留既有登记 question_id=%s keep_id=%s",
                question.id, clash.id,
            )
            question.dedup_key = None
        else:
            question.dedup_key = question.content_hash
    else:
        question.dedup_key = None

    service = QuestionDeduplicationService(db)
    if question.status in BLOCKING_STATUSES:
        service.index_question(question)
    else:
        service.remove_or_deactivate_index(question.id)


def initialize_question_index(db: Session, *, only_missing: bool = True) -> Dict[str, Any]:
    """API 服务启动期题目向量索引初始化（§2.2，由 FastAPI lifespan 调用）。

    - 独立 question 向量库（与 knowledge 库隔离），只建阻断状态题目
      （排除 rejected/disabled），用当前 Embedding 模型版本；
    - 幂等：only_missing=True 时跳过已存在且版本一致的向量；
    - 记录 total/success/failed/耗时/模型/版本，写入就绪状态机：
      成功 → ready；失败 > 0 或异常 → degraded（不得当作空索引）；
    - 必须在 API 服务进程内执行：FAISS 为进程内存态，外部脚本无法为
      本进程修复索引。
    """
    s = agent_settings
    if not s.QUESTION_DEDUP_ENABLED:
        _readiness.set_status("disabled", "QUESTION_DEDUP_ENABLED=false（显式关闭语义去重）")
        _readiness.set_stats({})
        return _readiness.snapshot()
    _readiness.set_status("initializing", "启动初始化中（构建题目向量索引）")
    t0 = time.time()
    try:
        service = QuestionDeduplicationService(db)
        stats = service.rebuild_missing_vectors(only_missing=only_missing)
        stats.update({
            "duration_seconds": round(time.time() - t0, 2),
            "embedding_model": s.EMBEDDING_MODEL,
            "embedding_version": s.EMBEDDING_VERSION,
        })
        _readiness.set_stats(stats)
        if stats.get("failed"):
            _readiness.set_status(
                "degraded", f"题目向量索引构建失败 {stats['failed']} 条，语义去重不完整")
        else:
            _readiness.set_status("ready", None)
    except Exception as exc:  # noqa: BLE001
        logger.error("题目向量索引启动初始化失败: %s", exc, exc_info=True)
        _readiness.set_stats({"error": str(exc)[:500],
                              "duration_seconds": round(time.time() - t0, 2)})
        _readiness.set_status("degraded", f"题目向量索引初始化异常: {exc}")
    return _readiness.snapshot()
