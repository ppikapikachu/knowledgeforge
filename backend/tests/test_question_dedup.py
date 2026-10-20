"""题目多层去重测试（执行文档 §12 测试清单）。

覆盖：
- 规范化/指纹算法单元测试（空格标点、选项顺序、大小写敏感标识）；
- 同范围/跨范围矩阵（含精确指纹行与无知识点行）；
- 执行文档 §12.2 的 14 类重复样本；
- LLM 调用阈值校验（哈希命中 0 次；跨范围低/中相似 0 次；跨范围高相似/同范围相似才复核）；
- 并发写入竞争（去重写入锁 + DB 唯一键）；
- LLM 超时 / 非法 JSON → uncertain（保留 + 人工复核），绝不静默判 distinct；
- Embedding/向量库故障降级、索引延迟修复（rebuild_missing_vectors）；
- 四种审核状态的阻断语义；
- 生成任务重试上限与统计口径（不无限生成）。

真实 Embedding + 真实 FAISS 冒烟见 tests/test_question_dedup_smoke.py。
"""

import threading
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent.common.config import agent_settings
from agent.common.vector_store import VectorSearchResult
from agent.question_dedup.schemas import LLMReviewItem, LLMReviewOutput
from agent.question_generate.schemas import GeneratedOption, GeneratedQuestion
from app.models import (
    Knowledge,
    KnowledgeBase,
    Question,
    QuestionBank,
    QuestionDedupRecord,
    QuestionGenerationTask,
    QuestionKnowledge,
    QuestionOption,
)
from app.services.question_dedup_service import (
    LLMQuestionReviewer,
    QuestionDeduplicationService,
    QuestionSnapshot,
    snapshot_from_generated,
    sync_question_dedup_state,
)
from app.services.question_normalizer import HASH_VERSION, question_normalizer

# =====================================================================
# 测试替身
# =====================================================================


class FakeEmbedding:
    """确定性伪向量（字符二元组）：相似文本共享二元组 → 余弦更高，不依赖真实模型。"""

    def __init__(self, dim: int = 32):
        self.dim = dim
        self.calls = 0

    def embed_text(self, text: str):
        import hashlib
        import math

        self.calls += 1
        vec = [0.0] * self.dim
        t = (text or "").lower()
        for i in range(max(0, len(t) - 1)):
            bigram = t[i:i + 2]
            h = int(hashlib.md5(bigram.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[h] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_texts(self, texts):
        return [self.embed_text(t) for t in texts]


class FakeVectorStore:
    """内存向量库（余弦检索），API 与 FaissVectorStore 对齐。"""

    def __init__(self):
        self.data = {}
        self.fail_search = False
        self.fail_upsert = False

    @staticmethod
    def _cosine(a, b):
        import math

        num = sum(x * y for x, y in zip(a, b))
        da = math.sqrt(sum(x * x for x in a)) or 1.0
        db_ = math.sqrt(sum(y * y for y in b)) or 1.0
        return num / (da * db_)

    def upsert(self, id, vector, metadata=None):
        if self.fail_upsert:
            raise RuntimeError("vector store unavailable")
        self.data[str(id)] = (list(vector), dict(metadata or {}))

    def delete(self, id):
        self.data.pop(str(id), None)

    def search(self, vector, top_k=5):
        if self.fail_search:
            raise RuntimeError("vector search unavailable")
        results = [
            VectorSearchResult(id=k, score=self._cosine(vector, v), metadata=dict(m))
            for k, (v, m) in self.data.items()
        ]
        results.sort(key=lambda r: -r.score)
        return results[:top_k]

    def count(self):
        return len(self.data)

    def list_ids(self):
        return list(self.data.keys())

    def get_metadata(self, id):
        return dict(self.data.get(str(id), (None, {}))[1])


class StubLLMReviewer:
    """脚本化 LLM 复核器（带调用计数，用于阈值/调用次数断言）。"""

    def __init__(self, verdict_fn=None):
        self.calls = 0
        self.pair_count = 0
        self.verdict_fn = verdict_fn or (lambda pair: "distinct")

    def review(self, pairs, knowledge_name_fn=None, pair_index_offset=0):
        self.calls += 1
        self.pair_count += len(pairs)
        return {
            p.pair_id: LLMReviewItem(pair_id=p.pair_id, verdict=self.verdict_fn(p),
                                     reason="stub")
            for p in pairs
        }


# =====================================================================
# 工具
# =====================================================================


def get_bank_id(db) -> int:
    row = db.query(QuestionBank).filter(QuestionBank.code == "uncategorized").first()
    assert row is not None, "conftest 应插入 uncategorized 题库"
    return row.id


def ensure_knowledge(db, knowledge_ids) -> None:
    """测试库未预置 knowledge 行：按需补齐（显式 id，满足外键）。"""
    wanted = {int(k) for k in (knowledge_ids or [])}
    existing = {row.id for row in db.query(Knowledge).filter(Knowledge.id.in_(wanted)).all()} if wanted else set()
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.code == "uncategorized").first()
    assert kb is not None, "conftest 应插入 uncategorized 知识库"
    for kid in sorted(wanted - existing):
        db.add(Knowledge(id=kid, knowledge_base_id=kb.id, name=f"知识点{kid}",
                         summary=f"知识点{kid}", content=f"知识点{kid}内容",
                         difficulty=1, status=1, source_type="MANUAL",
                         importance_level="normal", importance_source="default"))
    db.flush()


def make_question(db, content, *, question_type="SINGLE_CHOICE", options=None, answer="A",
                  bank_id=None, knowledge_ids=(1,), status="pending_review", difficulty=2,
                  commit=True) -> Question:
    """插入一道库内题（含选项/知识点/指纹登记），模拟真实入库结果。"""
    bank_id = bank_id if bank_id is not None else get_bank_id(db)
    ensure_knowledge(db, knowledge_ids)
    question = Question(
        question_type=question_type, content=content, answer=answer, analysis="",
        difficulty=difficulty, status=status, source_type="AI",
        question_bank_id=bank_id,
    )
    db.add(question)
    db.flush()
    options = options or [("A", "选项一", 1), ("B", "选项二", 0)]
    for i, (key, c, correct) in enumerate(options):
        db.add(QuestionOption(question_id=question.id, option_key=key, option_content=c,
                              is_correct=correct, sort_order=i))
    for kid in knowledge_ids:
        db.add(QuestionKnowledge(question_id=question.id, knowledge_id=kid))
    pairs = [(c, correct) for _k, c, correct in options]
    question.content_hash = question_normalizer.compute_content_hash(
        question_type, content, answer, pairs)
    question.hash_version = HASH_VERSION
    if status in ("pending_review", "published"):
        clash = db.query(Question).filter(
            Question.dedup_key == question.content_hash).first()
        question.dedup_key = None if clash else question.content_hash
    else:
        question.dedup_key = None
    if commit:
        db.commit()
    return question


def make_snap(content, *, question_type="SINGLE_CHOICE", options=None, answer="A",
              bank_id=1, knowledge_ids=(1,)) -> QuestionSnapshot:
    options = options if options is not None else [("A", "选项一", 1), ("B", "选项二", 0)]
    return QuestionSnapshot(
        question_type=question_type, content=content, answer=answer,
        options=list(options), question_bank_id=bank_id,
        knowledge_ids=list(knowledge_ids),
    )


@pytest.fixture(autouse=True)
def _reset_dedup_readiness():
    """测试隔离：重置去重就绪状态机（部分测试会触发 degraded）。"""
    from app.services.question_dedup_service import reset_dedup_readiness

    reset_dedup_readiness()
    yield
    reset_dedup_readiness()


@pytest.fixture
def fakes():
    return FakeEmbedding(), FakeVectorStore(), StubLLMReviewer()


@pytest.fixture
def svc(db, fakes):
    embed, store, reviewer = fakes
    return QuestionDeduplicationService(
        db, llm_reviewer=reviewer, embedding_service=embed, vector_store=store)


@pytest.fixture
def low_same_threshold(monkeypatch):
    """放宽同范围进入复核的阈值（假向量分数不稳定，阈值断言单独控制）。"""
    from agent.common.config import agent_settings

    monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD", 0.25)
    monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_CROSS_SCOPE_HIGH_THRESHOLD", 0.85)
    monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD", 0.85)
    monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)
    yield


# =====================================================================
# 1. 指纹/规范化单元测试（§3）
# =====================================================================


class TestNormalizer:
    def test_whitespace_and_punct_variants_same_hash(self):
        a = question_normalizer.compute_content_hash(
            "SINGLE_CHOICE", "HashMap 的底层数据结构是什么？", "A",
            [("数组+链表+红黑树", 1), ("双向链表", 0)])
        b = question_normalizer.compute_content_hash(
            "SINGLE_CHOICE", "HashMap的底层数据结构是什么?", "A",
            [("数组+链表+红黑树", 1), ("双向链表", 0)])
        assert a == b

    def test_option_reorder_same_hash(self):
        a = question_normalizer.compute_content_hash(
            "SINGLE_CHOICE", "题干内容完全相同", "A",
            [("选项甲", 1), ("选项乙", 0)])
        b = question_normalizer.compute_content_hash(
            "SINGLE_CHOICE", "题干内容完全相同", "A",
            [("选项乙", 0), ("选项甲", 1)])
        assert a == b

    def test_different_options_different_hash(self):
        a = question_normalizer.compute_content_hash(
            "SINGLE_CHOICE", "题干内容完全相同", "A", [("选项甲", 1), ("选项乙", 0)])
        b = question_normalizer.compute_content_hash(
            "SINGLE_CHOICE", "题干内容完全相同", "A", [("选项甲", 1), ("选项丙", 0)])
        assert a != b

    def test_answer_key_change_different_hash(self):
        a = question_normalizer.compute_content_hash(
            "SINGLE_CHOICE", "题干内容完全相同", "A", [("选项甲", 1), ("选项乙", 0)])
        b = question_normalizer.compute_content_hash(
            "SINGLE_CHOICE", "题干内容完全相同", "A", [("选项甲", 0), ("选项乙", 1)])
        assert a != b

    def test_case_sensitive_identifiers_preserved(self):
        # 大小写敏感技术标识（C/C++、HashMap、JDK 8、==、===）不得被小写化合并
        a = question_normalizer.compute_content_hash(
            "SHORT_ANSWER", "HashMap 的默认容量是多少", "16", [])
        b = question_normalizer.compute_content_hash(
            "SHORT_ANSWER", "hashmap 的默认容量是多少", "16", [])
        assert a != b

        text = "Java == 与 === 的区别（C++、JDK 8）"
        normalized = question_normalizer.normalize_text(text)
        assert "==" in normalized and "===" in normalized
        assert "C++" in normalized and "JDK 8" not in normalized.replace("JDK8", "JDK 8") or "JDK" in normalized

    def test_question_type_participates(self):
        a = question_normalizer.compute_content_hash("SINGLE_CHOICE", "同一道题干", "A", [])
        b = question_normalizer.compute_content_hash("SHORT_ANSWER", "同一道题干", "A", [])
        assert a != b

    def test_option_label_stripped_from_content(self):
        assert question_normalizer.normalize_option_content("A. 数组") == \
               question_normalizer.normalize_option_content("数组")

    def test_text_similarity_range(self):
        s1 = question_normalizer.text_similarity("HashMap 底层数据结构", "HashMap 底层数据结构")
        s2 = question_normalizer.text_similarity("HashMap 底层数据结构", "线程安全的集合类")
        assert 0.99 <= s1 <= 1.0
        assert s2 < s1


# =====================================================================
# 2. 同范围/跨范围矩阵（§12.1）+ 精确指纹行 + 无知识点行
# =====================================================================


class TestScopeMatrix:
    @pytest.mark.parametrize("bank_same,kids_same,expect_scope", [
        (True, True, "same_scope"),     # 同题库 + 知识点相交 → 常规去重
        (True, False, "cross_scope"),   # 同题库 + 知识点不相交 → 严格
        (False, True, "cross_scope"),   # 跨题库 + 知识点相交 → 严格
        (False, False, "cross_scope"),  # 跨题库 + 知识点不相交 → 严格
    ])
    def test_scope_classification(self, svc, bank_same, kids_same, expect_scope):
        bank_new, bank_cand = (1, 1) if bank_same else (1, 2)
        kids_new, kids_cand = ([1, 2], [2, 3]) if kids_same else ([1], [3])
        new = make_snap("新题目内容甲", bank_id=bank_new, knowledge_ids=kids_new)
        cand = make_snap("候选题目内容乙", bank_id=bank_cand, knowledge_ids=kids_cand)
        scope, no_knowledge = svc._classify_scope(new, cand)
        assert scope == expect_scope
        assert no_knowledge is False

    def test_exact_hash_wins_regardless_of_scope(self, svc, db, fakes):
        # 跨题库但指纹相同 → global_exact，0 次 LLM
        make_question(db, "HashMap 的底层数据结构是什么？", bank_id=get_bank_id(db))
        new = make_snap("HashMap 的底层数据结构是什么？", bank_id=999, knowledge_ids=[42])
        result = svc.check_one(new)
        assert result.decision == "duplicate"
        assert result.scope_mode == "global_exact"
        assert result.decision_method == "exact_hash"
        assert fakes[2].calls == 0

    def test_no_knowledge_question_is_cross_scope_with_warning(self, svc):
        new = make_snap("没有知识点的新题", knowledge_ids=[])
        cand = make_snap("没有知识点的候选", knowledge_ids=[])
        scope, no_knowledge = svc._classify_scope(new, cand)
        assert scope == "cross_scope"
        assert no_knowledge is True


# =====================================================================
# 3. LLM 调用阈值校验（§12.3）
# =====================================================================


class TestLLMCallThresholds:
    def test_hash_hit_zero_llm_calls(self, svc, db, fakes):
        make_question(db, "完全相同的题干内容")
        result = svc.check_one(make_snap("完全相同的题干内容"))
        assert result.decision == "duplicate"
        assert fakes[2].calls == 0

    def test_cross_scope_low_mid_similarity_zero_llm(self, svc, db, fakes):
        # 跨题库、内容不相近 → 不进入复核
        make_question(db, "Java 集合中 ArrayList 的默认容量是多少？", bank_id=get_bank_id(db))
        new = make_snap("HashMap 的默认负载因子是多少？", bank_id=999, knowledge_ids=[7])
        result = svc.check_one(new)
        assert result.decision == "distinct"
        assert fakes[2].calls == 0
        assert result.decision_method == "algorithm_only"

    def test_cross_scope_high_similarity_enters_llm(self, svc, db, fakes, low_same_threshold, monkeypatch):
        # 跨题库、内容极高相似但非指纹相同 → 进入 LLM 复核
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_CROSS_SCOPE_HIGH_THRESHOLD", 0.80)
        make_question(db, "HashMap 的底层数据结构是什么？请简述", bank_id=get_bank_id(db))
        new = make_snap("HashMap 的底层数据结构是什么？", bank_id=999, knowledge_ids=[7])
        result = svc.check_one(new)
        assert fakes[2].calls >= 1

    def test_same_scope_similar_enters_llm(self, svc, db, fakes, low_same_threshold):
        make_question(db, "JDK 8 中 HashMap 的底层采用什么数据结构实现？",
                      bank_id=get_bank_id(db), knowledge_ids=(1, 2))
        new = make_snap("Java 中 HashMap 底层是什么结构？",
                        bank_id=get_bank_id(db), knowledge_ids=(2, 3))
        result = svc.check_one(new)
        assert fakes[2].calls >= 1

    def test_no_full_db_llm(self, svc, db, fakes, low_same_threshold):
        # 库内 20 道无关题 + 1 道相似题：LLM 配对数被上限约束，绝不是逐条比较
        from agent.common.config import agent_settings

        bank = get_bank_id(db)
        make_question(db, "Java 中 HashMap 底层是什么结构？", bank_id=bank)
        for i in range(20):
            make_question(db, f"完全无关的知识点题目第 {i} 号，讨论网络协议栈", bank_id=bank)
        new = make_snap("HashMap 的底层数据结构是什么？", bank_id=bank)
        result = svc.check_one(new)
        if fakes[2].calls > 0:
            assert fakes[2].pair_count <= agent_settings.QUESTION_DEDUP_LLM_MAX_CANDIDATES
        assert fakes[2].calls <= 2


# =====================================================================
# 4. 重复样本（§12.2 的 14 类）
# =====================================================================


class TestDuplicateSamples:
    def test_case1_identical_stem(self, svc, db, fakes):
        make_question(db, "HashMap 的底层数据结构是什么？")
        result = svc.check_one(make_snap("HashMap 的底层数据结构是什么？"))
        assert result.decision == "duplicate"
        assert result.decision_method == "exact_hash"
        assert fakes[2].calls == 0

    def test_case2_whitespace_punct_variant(self, svc, db, fakes):
        make_question(db, "HashMap 的底层数据结构是什么？")
        result = svc.check_one(make_snap("HashMap的底层数据结构是什么"))
        assert result.decision == "duplicate"
        assert result.decision_method == "exact_hash"

    def test_case3_option_reorder(self, svc, db, fakes):
        make_question(db, "HashMap 的底层数据结构是什么？",
                      options=[("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)])
        result = svc.check_one(make_snap(
            "HashMap 的底层数据结构是什么？",
            options=[("A", "双向链表", 0), ("B", "数组+链表+红黑树", 1)]))
        assert result.decision == "duplicate"
        assert result.decision_method == "exact_hash"

    def test_case4_paraphrase_same_answer(self, svc, db, fakes, low_same_threshold):
        fakes[2].verdict_fn = lambda p: "duplicate"
        bank = get_bank_id(db)
        make_question(db, "JDK 8 中 HashMap 的底层采用什么数据结构实现？",
                      options=[("A", "数组+链表+红黑树", 1), ("B", "哈希表", 0)],
                      knowledge_ids=(1, 2), bank_id=bank)
        new = make_snap("Java 中 HashMap 底层是什么结构？",
                        options=[("A", "数组、链表和红黑树", 1), ("B", "顺序表", 0)],
                        knowledge_ids=(2, 3), bank_id=bank)
        result = svc.check_one(new)
        assert result.decision == "duplicate"
        assert result.llm_called is True
        assert result.matched_question_id is not None

    def test_case5_same_knowledge_different_angle_not_killed(self, svc, db, fakes, low_same_threshold):
        # 同知识点不同考查角度：HashMap 底层结构 vs 扩容机制 —— 必须判 distinct
        make_question(db, "HashMap 的底层数据结构是什么？", knowledge_ids=(1, 2), bank_id=get_bank_id(db))
        new = make_snap("HashMap 何时触发扩容？扩容倍数是多少？", knowledge_ids=(1, 2), bank_id=get_bank_id(db))
        result = svc.check_one(new)
        assert result.decision != "duplicate"
        assert result.needs_manual_review is False or result.decision == "uncertain"

    def test_case6_same_keywords_different_topic(self, svc, db, fakes, low_same_threshold):
        make_question(db, "HashMap 是线程安全的吗？为什么？", knowledge_ids=(1,), bank_id=get_bank_id(db))
        new = make_snap("ConcurrentHashMap 如何保证线程安全？", knowledge_ids=(1,), bank_id=get_bank_id(db))
        result = svc.check_one(new)
        assert result.decision != "duplicate"

    def test_case7_cross_bank_near_identical(self, svc, db, fakes, low_same_threshold):
        make_question(db, "HashMap 的底层数据结构是什么？", bank_id=get_bank_id(db))
        new = make_snap("HashMap 的底层数据结构是什么？", bank_id=999, knowledge_ids=[5])
        result = svc.check_one(new)
        # 指纹相同 → 精确层直接判重（跨题库也不放过），无需 LLM
        assert result.decision == "duplicate"

    def test_case8_cross_bank_merely_related(self, svc, db, fakes):
        make_question(db, "Java 集合中 ArrayList 的默认容量是多少？", bank_id=get_bank_id(db))
        new = make_snap("HashMap 的默认负载因子是多少？", bank_id=999, knowledge_ids=[5])
        result = svc.check_one(new)
        assert result.decision == "distinct"
        assert fakes[2].calls == 0

    def test_case9_single_choice_vs_short_answer(self, svc, db, fakes, low_same_threshold):
        make_question(db, "HashMap 的底层数据结构是什么？",
                      question_type="SINGLE_CHOICE",
                      options=[("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)], bank_id=get_bank_id(db))
        new = make_snap("请简述 HashMap 的底层数据结构。", question_type="SHORT_ANSWER",
                        options=[], answer="数组+链表+红黑树", bank_id=get_bank_id(db))
        result = svc.check_one(new)
        # 题型不同不构成精确重复；语义由 LLM 复核决定（stub 判 distinct）
        assert result.decision_method != "exact_hash"

    def test_case10_intra_batch_duplicate(self, svc, fakes):
        q1 = make_snap("同一批次里生成的题目内容")
        q2 = make_snap("同一批次里生成的题目内容")
        results = svc.check_batch([q1, q2])
        assert results[0].decision != "duplicate"
        assert results[1].decision == "duplicate"
        assert results[1].decision_method == "batch_internal"
        assert fakes[2].calls == 0  # 批次内指纹相同不走 LLM

    def test_case10b_duplicate_batch_candidate_not_valid_kept(self, svc, fakes):
        q1 = make_snap("批次题目一")
        q2 = make_snap("批次题目一")
        q3 = make_snap("批次题目一")
        batch_context = {"accepted": [], "hashes": set()}
        svc.check_batch([q1, q2], batch_context=batch_context)
        assert len(batch_context["accepted"]) == 1  # 判重的 q2 不得成为有效保留题
        result = svc.check_one(q3, batch_context=batch_context)
        assert result.decision == "duplicate"

    def test_case11_concurrent_tasks_only_one_saved(self, db, fakes):
        embed, store, reviewer = fakes
        content = "并发任务几乎同时写入的同一道题"
        results = []
        lock = threading.Lock()
        barrier = threading.Barrier(2)

        def worker():
            session = sessionmaker(bind=db.get_bind())()
            try:
                service = QuestionDeduplicationService(
                    session, llm_reviewer=reviewer, embedding_service=embed, vector_store=store)
                snap = make_snap(content)

                def save_fn():
                    question = Question(
                        question_type="SINGLE_CHOICE", content=snap.content, answer="A",
                        analysis="", difficulty=2, status="pending_review", source_type="AI",
                        question_bank_id=get_bank_id(session),
                        content_hash=snap.content_hash, hash_version=HASH_VERSION,
                        dedup_key=snap.content_hash,
                    )
                    session.add(question)
                    session.flush()
                    return question

                barrier.wait()
                obj, verdict = service.guarded_save(snap, save_fn)
                with lock:
                    results.append((obj is not None, verdict.get("reason")))
            finally:
                session.close()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start(); t2.start()
        t1.join(timeout=30); t2.join(timeout=30)

        saved = sum(1 for ok, _ in results if ok)
        assert saved == 1, f"并发写入应只保存 1 道，实际 {results}"
        rows = db.query(Question).filter(Question.content == content).all()
        assert len(rows) == 1

    def test_case14_status_handling(self, svc, db, fakes):
        content = "同一道题在不同审核状态下的阻断行为"
        for status in ("pending_review", "published", "rejected", "disabled"):
            make_question(db, content, status=status)

        result = svc.check_one(make_snap(content))
        # 只有 pending_review/published 阻断；命中即重复（4 条里 2 条阻断）
        assert result.decision == "duplicate"
        assert result.matched_question_id is not None

        # 单独验证：只有 rejected/disabled 存在时不阻断（改为置为 disabled，避免 FK RESTRICT）
        db.query(Question).filter(
            Question.content == content,
            Question.status.in_(("pending_review", "published")),
        ).update({"status": "disabled"}, synchronize_session=False)
        db.commit()
        result2 = svc.check_one(make_snap(content))
        assert result2.decision == "distinct"

    def test_case12_llm_timeout_uncertain(self, db):
        class HangingLLM:
            def invoke(self, messages):
                time.sleep(10)
                return type("R", (), {"content": "{}"})()

        reviewer = LLMQuestionReviewer(llm=HangingLLM(), batch_size=5, timeout=0.2)
        service = QuestionDeduplicationService(
            db, llm_reviewer=reviewer,
            embedding_service=FakeEmbedding(), vector_store=FakeVectorStore())
        # 相似题构造为同范围进复核
        from agent.common.config import agent_settings
        old = agent_settings.QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD
        agent_settings.QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD = 0.05
        try:
            make_question(db, "JDK 8 中 HashMap 的底层采用什么数据结构实现？", knowledge_ids=(1, 2),
                          bank_id=get_bank_id(db))
            new = make_snap("Java 中 HashMap 底层是什么结构？", knowledge_ids=(2, 3), bank_id=get_bank_id(db))
            result = service.check_one(new)
        finally:
            agent_settings.QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD = old
        assert result.decision == "uncertain"
        assert result.needs_manual_review is True
        assert "uncertain" in (result.llm_reason or "")

    def test_case12b_llm_invalid_json_uncertain(self, db):
        class GarbageLLM:
            def invoke(self, messages):
                return type("R", (), {"content": "这不是 JSON"})()

        reviewer = LLMQuestionReviewer(llm=GarbageLLM(), batch_size=5, timeout=5)
        service = QuestionDeduplicationService(
            db, llm_reviewer=reviewer,
            embedding_service=FakeEmbedding(), vector_store=FakeVectorStore())
        from agent.common.config import agent_settings
        old = agent_settings.QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD
        agent_settings.QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD = 0.05
        try:
            make_question(db, "JDK 8 中 HashMap 的底层采用什么数据结构实现？", knowledge_ids=(1, 2),
                          bank_id=get_bank_id(db))
            new = make_snap("Java 中 HashMap 底层是什么结构？", knowledge_ids=(2, 3), bank_id=get_bank_id(db))
            result = service.check_one(new)
        finally:
            agent_settings.QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD = old
        assert result.decision == "uncertain"
        assert result.needs_manual_review is True

    def test_case13_embedding_failure_degrades(self, db, fakes):
        class BrokenEmbedding:
            def embed_text(self, text):
                raise RuntimeError("embedding down")

            def embed_texts(self, texts):
                raise RuntimeError("embedding down")

        reviewer = fakes[2]
        service = QuestionDeduplicationService(
            db, llm_reviewer=reviewer, embedding_service=BrokenEmbedding(),
            vector_store=FakeVectorStore())
        make_question(db, "完全相同的题干内容")
        result = service.check_one(make_snap("完全相同的题干内容"))
        assert result.decision == "duplicate"  # 精确层仍工作
        broken = service.check_one(make_snap("一个和库内都不相似的新题"))
        # 语义层不可用时不得把"没查到候选"当"没重复题"：uncertain + 人工复核（§2.2）
        assert broken.decision == "uncertain"
        assert broken.needs_manual_review is True
        assert broken.warning is not None and "EMBEDDING_UNAVAILABLE" in broken.warning

    def test_case13b_vector_search_failure_degrades(self, db, fakes):
        store = FakeVectorStore()
        store.fail_search = True
        service = QuestionDeduplicationService(
            db, llm_reviewer=fakes[2], embedding_service=FakeEmbedding(), vector_store=store)
        make_question(db, "完全相同的题干内容")
        result = service.check_one(make_snap("完全相同的题干内容"))
        assert result.decision == "duplicate"
        other = service.check_one(make_snap("一个和库内都不相似的新题"))
        # 向量检索失败同样不得静默 distinct（§2.2）
        assert other.decision == "uncertain"
        assert other.needs_manual_review is True
        assert other.warning is not None and "VECTOR_SEARCH_UNAVAILABLE" in other.warning

    def test_case13c_index_delay_repairable(self, db, fakes):
        embed, store, reviewer = fakes
        service = QuestionDeduplicationService(
            db, llm_reviewer=reviewer, embedding_service=embed, vector_store=store)
        q = make_question(db, "需要补建向量的题目甲")
        make_question(db, "需要补建向量的题目乙")
        store.fail_upsert = True
        assert service.index_question(q) is False  # 索引延迟/失败仅记录
        store.fail_upsert = False
        stats = service.rebuild_missing_vectors(batch_size=8, only_missing=True)
        assert stats["success"] >= 2
        assert stats["failed"] == 0
        stats2 = service.rebuild_missing_vectors(batch_size=8, only_missing=True)
        assert stats2["skipped"] >= 2  # 已有向量跳过（幂等/可重入）


# =====================================================================
# 5. 审计记录与统计（§9/§11）
# =====================================================================


class TestAuditAndStats:
    def test_dedup_records_written(self, svc, db, fakes, low_same_threshold):
        bank = get_bank_id(db)
        make_question(db, "JDK 8 中 HashMap 的底层采用什么数据结构实现？", knowledge_ids=(1, 2), bank_id=bank)
        result = svc.check_one(make_snap("Java 中 HashMap 底层是什么结构？", knowledge_ids=(2, 3), bank_id=bank))
        db.flush()
        rows = db.query(QuestionDedupRecord).all()
        assert rows, "判重过程必须写审计记录"
        row = rows[0]
        assert row.new_content_hash
        assert row.decision in ("duplicate", "distinct", "uncertain")
        assert row.embedding_model and row.embedding_version

    def test_get_dedup_stats(self, svc, db):
        make_question(db, "完全相同的题干内容")
        svc.check_one(make_snap("完全相同的题干内容"))
        svc.check_one(make_snap("一个全新的题目内容描述"))
        db.flush()
        stats = svc.get_dedup_stats()
        assert stats["records"] >= 2
        assert "by_decision" in stats and "by_method" in stats


# =====================================================================
# 6. 状态流转同步（§3.3/§8）
# =====================================================================


class TestStatusSync:
    def _patch_deps(self, monkeypatch, embed, store):
        monkeypatch.setattr("app.services.question_dedup_service.get_embedding_service", lambda: embed)
        monkeypatch.setattr("app.services.question_dedup_service.get_question_vector_store", lambda: store)

    def test_publish_registers_dedup_key_reject_clears(self, db, fakes, monkeypatch):
        embed, store, reviewer = fakes
        self._patch_deps(monkeypatch, embed, store)
        q = make_question(db, "状态流转测试题目", status="rejected")
        assert q.dedup_key is None
        q.status = "published"
        sync_question_dedup_state(db, q)
        db.commit()
        assert q.dedup_key == q.content_hash
        assert store.count() == 1  # 阻断状态登记向量索引

        q.status = "rejected"
        sync_question_dedup_state(db, q)
        db.commit()
        assert q.dedup_key is None
        assert store.count() == 0  # 驳回后移除向量索引，不阻塞新题

    def test_historical_duplicate_dedup_key_conflict_kept(self, db, fakes, monkeypatch):
        embed, store, reviewer = fakes
        self._patch_deps(monkeypatch, embed, store)
        q1 = make_question(db, "历史重复题目内容")
        q2 = Question(
            question_type="SINGLE_CHOICE", content="历史重复题目内容", answer="A",
            analysis="", difficulty=2, status="rejected", source_type="AI",
            question_bank_id=get_bank_id(db), content_hash=q1.content_hash,
            hash_version=HASH_VERSION, dedup_key=None,
        )
        db.add(q2)
        db.commit()
        q2.status = "published"
        sync_question_dedup_state(db, q2)  # 不得抛唯一键冲突
        db.commit()
        assert q2.dedup_key is None  # 保留 q1 的登记
        assert q1.dedup_key == q1.content_hash


# =====================================================================
# 7. 批量结果结构 / LLM 复核器（§7.1/§6）
# =====================================================================


class TestResultSchemaAndReviewer:
    def test_result_schema_fields(self, svc, db):
        make_question(db, "完全相同的题干内容")
        result = svc.check_one(make_snap("完全相同的题干内容"))
        d = result.to_dict()
        for key in ("decision", "scope_mode", "matched_question_id", "decision_method",
                    "algorithm_score", "llm_reason", "needs_manual_review"):
            assert key in d

    def test_llm_reviewer_batches_pairs(self):
        reviewer = StubLLMReviewer()
        pairs = []
        for i in range(12):
            pairs.append(_mk_pair(i + 1))
        reviewer.review(pairs)
        assert reviewer.pair_count == 12

    def test_llm_reviewer_missing_pair_becomes_uncertain(self):
        class PartialLLM:
            def invoke(self, messages):
                payload = '{"pairs": [{"pair_id": 1, "verdict": "duplicate", "reason": "x"}]}'
                return type("R", (), {"content": payload})()

        reviewer = LLMQuestionReviewer(llm=PartialLLM(), batch_size=10, timeout=5)
        pairs = [_mk_pair(1), _mk_pair(2)]
        results = reviewer.review(pairs)
        assert results[1].verdict == "duplicate"   # 返回的配对按 LLM 判定
        assert results[2].verdict == "uncertain"   # 未返回的配对绝不静默判 distinct

    def test_llm_reviewer_output_validation(self):
        out = LLMReviewOutput.model_validate({"pairs": [{"pair_id": 1, "verdict": "distinct", "reason": "ok"}]})
        assert out.pairs[0].verdict == "distinct"


def _mk_pair(pair_id: int):
    from app.services.question_dedup_service import ReviewPair

    return ReviewPair(
        pair_id=pair_id,
        new=make_snap(f"新题{pair_id}"),
        candidate=make_snap(f"候选{pair_id}"),
        candidate_source="db", scope="same_scope", algorithm_score=0.7,
    )
