"""题目去重专项加固测试（加固执行文档 §2/§3/§10）。

覆盖：
- 向量索引生命周期（就绪状态机、写失败 degraded、安全失败口径）；
- 并发语义重复竞争（hash 不同的语义改写题不得双存，§3.4 六场景）；
- 最终校验不得只用 0.85 单阈值绕过 0.65/0.75 范围复核（§3.3.4）；
- 至少一组真实 Embedding 的语义改写并发样本（不得只 Mock）。
"""

import threading

import pytest
from sqlalchemy.orm import sessionmaker

from agent.common.config import agent_settings
from app.models import Question, QuestionKnowledge
from app.services.background_runner import execute_generation_task
from app.services.question_dedup_service import (
    QuestionDeduplicationService,
    get_dedup_readiness,
    reset_dedup_readiness,
)

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from test_question_dedup import (  # noqa: E402
    FakeEmbedding,
    FakeVectorStore,
    StubLLMReviewer,
    ensure_knowledge,
    get_bank_id,
    make_question,
    make_snap,
)


@pytest.fixture(autouse=True)
def _reset_readiness():
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


def _refresh(db):
    """读取并发线程的提交前必须结束旧快照事务（MySQL REPEATABLE READ）。"""
    db.rollback()
    db.expire_all()


def _run_concurrently(worker, n):
    barrier = threading.Barrier(n)
    results = []
    lock = threading.Lock()

    def _wrap(idx):
        try:
            out = worker(idx, barrier)
            with lock:
                results.append((idx, out))
        except Exception as exc:  # noqa: BLE001
            with lock:
                results.append((idx, exc))

    threads = [threading.Thread(target=_wrap, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


def _saved_service(db, reviewer=None, embed=None, store=None):
    return QuestionDeduplicationService(
        db,
        llm_reviewer=reviewer or StubLLMReviewer(),
        embedding_service=embed or FakeEmbedding(),
        vector_store=store or FakeVectorStore(),
    )


def _save_fn_for(session, snap, bank, kid=None):
    """构造落库闭包：Question + QuestionKnowledge（无知识关联会被判 cross_scope）。"""
    def save_fn():
        q = Question(
            question_type="SINGLE_CHOICE", content=snap.content, answer="A",
            analysis="", difficulty=2, status="pending_review", source_type="AI",
            question_bank_id=bank, content_hash=snap.content_hash,
            hash_version="2", dedup_key=snap.content_hash,
        )
        session.add(q)
        session.flush()
        if kid is not None:
            session.add(QuestionKnowledge(question_id=q.id, knowledge_id=kid))
        return q
    return save_fn


# =====================================================================
# 1. 并发竞争场景（§3.4）
# =====================================================================


class TestConcurrentSemanticRace:
    def test_10_threads_same_question_only_one_saved(self, db, fakes, monkeypatch):
        """场景1：10 线程写入完全相同题目 → 只保存 1 道。"""
        monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)
        embed, store, reviewer = fakes
        content = "十个线程并发写入的完全相同题目"
        bank = get_bank_id(db)

        def worker(idx, barrier):
            session = sessionmaker(bind=db.get_bind())()
            try:
                service = _saved_service(session, reviewer, embed, store)
                snap = make_snap(content, bank_id=bank)
                save_fn = _save_fn_for(session, snap, bank)

                barrier.wait()
                obj, verdict = service.guarded_save(snap, save_fn)
                return obj is not None, verdict.get("reason")
            finally:
                session.close()

        results = _run_concurrently(worker, 10)
        assert not any(isinstance(v, Exception) for _, v in results), results
        saved = sum(1 for _, (ok, _reason) in results if ok)
        assert saved == 1, f"10 线程同题应只存 1 道，实际 {results}"
        _refresh(db)
        rows = db.query(Question).filter(Question.content == content).all()
        assert len(rows) == 1

    def test_2_threads_semantic_rewrite_only_one_saved(self, db, fakes, monkeypatch):
        """场景2：同知识点语义改写（hash 不同）并发 → 不能双存。"""
        monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD", 0.25)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD", 0.85)
        embed, store, reviewer = fakes
        reviewer.verdict_fn = lambda p: "duplicate"
        bank = get_bank_id(db)
        ensure_knowledge(db, [1])
        db.commit()  # 线程 session 需要看到知识行（FK 约束）
        contents = [
            "HashMap 的底层数据结构是什么？请简述。",
            "Java 中 HashMap 的底层采用什么数据结构实现？",
        ]

        def worker(idx, barrier):
            session = sessionmaker(bind=db.get_bind())()
            try:
                service = _saved_service(session, reviewer, embed, store)
                snap = make_snap(contents[idx], bank_id=bank, knowledge_ids=(1,))
                save_fn = _save_fn_for(session, snap, bank, 1)

                barrier.wait()
                obj, verdict = service.guarded_save(snap, save_fn)
                return obj is not None, verdict.get("reason")
            finally:
                session.close()

        results = _run_concurrently(worker, 2)
        assert not any(isinstance(v, Exception) for _, v in results), results
        saved = sum(1 for _, (ok, _r) in results if ok)
        _refresh(db)
        rows = db.query(Question).filter(Question.content.in_(contents)).all()
        assert saved == 1, f"语义改写并发应只存 1 道，实际 {results}"
        assert len(rows) == 1

    def test_cross_knowledge_high_similarity_enters_llm_review(self, svc, db, fakes, monkeypatch):
        """场景3：跨知识点高相似（>0.75）按跨范围进入 LLM 复核。"""
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_CROSS_SCOPE_HIGH_THRESHOLD", 0.30)
        monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)
        bank = get_bank_id(db)
        ensure_knowledge(db, [1, 2])
        make_question(db, "HashMap 的底层数据结构是什么？请简述。",
                      bank_id=bank, knowledge_ids=(1,))
        result = svc.check_one(make_snap(
            "Java 中 HashMap 的底层采用什么数据结构实现？",
            bank_id=bank, knowledge_ids=(2,)))
        assert result.scope_mode == "cross_scope"
        assert fakes[2].calls >= 1, "跨范围高相似必须进入 LLM 复核"
        assert result.decision in ("duplicate", "distinct", "uncertain")

    def test_cross_bank_exact_hash_and_strict_threshold(self, svc, db, fakes, monkeypatch):
        """场景4：跨题库相同指纹全局拦截；跨题库仅相关（低/中相似）不触发 LLM。"""
        monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)
        bank = get_bank_id(db)
        ensure_knowledge(db, [1, 2])
        make_question(db, "完全相同题干跨题库测试", bank_id=bank, knowledge_ids=(1,))
        exact = svc.check_one(make_snap("完全相同题干跨题库测试", bank_id=99999, knowledge_ids=(2,)))
        assert exact.decision == "duplicate"
        assert exact.scope_mode == "global_exact"
        assert fakes[2].calls == 0, "精确指纹命中不得调用 LLM"

        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_CROSS_SCOPE_HIGH_THRESHOLD", 0.95)
        make_question(db, "线程池的核心参数有哪些？", bank_id=bank, knowledge_ids=(1,))
        related = svc.check_one(make_snap("集合类的遍历方式有哪些？", bank_id=99999, knowledge_ids=(2,)))
        assert related.decision == "distinct"
        assert fakes[2].calls == 0, "跨范围低/中相似不得调用 LLM"

    def test_concurrent_distinct_questions_all_kept(self, db, fakes, monkeypatch):
        """场景5：并发生成不同题 → 都保留（不误杀）。"""
        monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD", 0.25)
        embed, store, reviewer = fakes
        bank = get_bank_id(db)
        contents = ["完全不相关的题目内容A", "另一个毫无关系的题目内容B"]

        def worker(idx, barrier):
            session = sessionmaker(bind=db.get_bind())()
            try:
                service = _saved_service(session, reviewer, embed, store)
                snap = make_snap(contents[idx], bank_id=bank)
                save_fn = _save_fn_for(session, snap, bank)

                barrier.wait()
                obj, _verdict = service.guarded_save(snap, save_fn)
                return obj is not None
            finally:
                session.close()

        results = _run_concurrently(worker, 2)
        assert all(v is True for _, v in results), results
        _refresh(db)
        assert db.query(Question).filter(Question.content.in_(contents)).count() == 2

    def test_llm_distinct_competition_requires_recheck(self, db, fakes, monkeypatch):
        """场景6：LLM 判 distinct 后的竞争——后入库方必须对新增候选重新核验，
        不得沿用过期的"无重复"结论（复核计数 ≥ 2）。"""
        monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD", 0.25)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD", 0.99)
        embed, store, reviewer = fakes
        reviewer.verdict_fn = lambda p: "distinct"
        bank = get_bank_id(db)
        ensure_knowledge(db, [1])
        db.commit()  # 线程 session 需要看到知识行（FK 约束）
        contents = [
            "HashMap 的底层数据结构是什么？请简述。",
            "Java 中 HashMap 的底层采用什么数据结构实现？",
        ]

        def worker(idx, barrier):
            session = sessionmaker(bind=db.get_bind())()
            try:
                service = _saved_service(session, reviewer, embed, store)
                snap = make_snap(contents[idx], bank_id=bank, knowledge_ids=(1,))
                save_fn = _save_fn_for(session, snap, bank, 1)

                barrier.wait()
                obj, verdict = service.guarded_save(snap, save_fn)
                return obj is not None, verdict.get("rivals_reviewed")
            finally:
                session.close()

        results = _run_concurrently(worker, 2)
        assert not any(isinstance(v, Exception) for _, v in results), results
        # distinct 结论不误杀 → 两道都保留
        assert all(ok for _, (ok, _rv) in results), results
        _refresh(db)
        assert db.query(Question).filter(Question.content.in_(contents)).count() == 2
        # 后到者必须重新核验对方（不得沿用过期结果）
        assert reviewer.calls >= 2 or sum(rv for _, (_ok, rv) in results if rv) >= 1, results


# =====================================================================
# 2. 最终校验不得绕过 0.65/0.75 范围复核（§3.3.4）
# =====================================================================


class TestFinalGateMidBand:
    def test_mid_band_candidates_go_to_review_not_bypassed(self, db, fakes, monkeypatch):
        """融合分落在范围阈值~0.85 之间的竞争候选必须经 LLM 复核，
        不得只用 0.85 单阈值直接放过。"""
        monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD", 0.25)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD", 0.85)
        embed, store, reviewer = fakes
        reviewer.verdict_fn = lambda p: "duplicate"
        bank = get_bank_id(db)
        ensure_knowledge(db, [1])
        existing = make_question(db, "HashMap 的底层数据结构是什么？请简述。",
                                 bank_id=bank, knowledge_ids=(1,))
        service = _saved_service(db, reviewer, embed, store)
        snap = make_snap("Java 中 HashMap 的底层采用什么数据结构实现？",
                         bank_id=bank, knowledge_ids=(1,))

        verdict = service.verify_before_save(snap)
        assert verdict["blocked"] is False
        rivals = verdict["rivals"]
        assert rivals, "范围阈值~0.85 之间的竞争候选必须进入复核，不得直接放过"
        assert 0.25 <= rivals[0].algorithm_score < 0.85

        obj, final_verdict = service.guarded_save(
            snap, _save_fn_for(db, snap, bank, 1))
        assert obj is None, "LLM 判 duplicate 的中段候选不得被放过"
        assert final_verdict["reason"] in ("semantic_concurrent_duplicate", "semantic_final_gate")
        assert db.query(Question).filter(
            Question.content == "Java 中 HashMap 的底层采用什么数据结构实现？").count() == 0
        assert existing.id  # 原题保留

    def test_rivals_use_scope_threshold_not_final_gate(self, db, fakes, monkeypatch):
        """最终校验的 rivals 收集必须用"范围阈值"（同/跨范围各自判定），
        不能只按 0.85 单阈值放过 0.65~0.84 区间（§3.3.4/§7 一致性）。"""
        embed, store, reviewer = fakes
        reviewer.verdict_fn = lambda p: "distinct"
        bank = get_bank_id(db)
        ensure_knowledge(db, [1])
        make_question(db, "HashMap 的底层数据结构是什么？请简述。",
                      bank_id=bank, knowledge_ids=(1,))
        service = _saved_service(db, reviewer, embed, store)
        snap = make_snap("Java 中 HashMap 的底层采用什么数据结构实现？",
                         bank_id=bank, knowledge_ids=(1,))

        # 范围阈值放宽 → 中段候选必须进 rivals（即使 < 0.85）
        monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD", 0.0)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD", 0.85)
        verdict = service.verify_before_save(snap)
        assert verdict["rivals"], "范围阈值命中的候选必须进复核队列"

        # 范围阈值抬高到超过任何实际分数 → rivals 空（证明用的是范围阈值，而非固定 0.85）
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD", 0.99)
        verdict2 = service.verify_before_save(snap)
        assert verdict2["rivals"] == [], "范围阈值未命中的候选不应进复核队列"

    def test_mid_band_distinct_not_killed(self, db, fakes, monkeypatch):
        """同样区间内 LLM 判 distinct 的题必须保留（不误杀）。"""
        monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD", 0.25)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD", 0.85)
        embed, store, reviewer = fakes
        reviewer.verdict_fn = lambda p: "distinct"
        bank = get_bank_id(db)
        ensure_knowledge(db, [1])
        make_question(db, "HashMap 的底层数据结构是什么？请简述。",
                      bank_id=bank, knowledge_ids=(1,))
        service = _saved_service(db, reviewer, embed, store)
        snap = make_snap("Java 中 HashMap 的底层采用什么数据结构实现？",
                         bank_id=bank, knowledge_ids=(1,))

        obj, final_verdict = service.guarded_save(
            snap, _save_fn_for(db, snap, bank, 1))
        assert obj is not None, "LLM 判 distinct 不得误杀"
        assert final_verdict["blocked"] is False


# =====================================================================
# 3. 向量生命周期与安全失败（§2.2~§2.5）
# =====================================================================


class TestVectorLifecycle:
    def test_index_write_failure_marks_degraded(self, db, fakes):
        embed, store, reviewer = fakes
        store.fail_upsert = True
        service = _saved_service(db, reviewer, embed, store)
        q = make_question(db, "向量写入失败的题目")
        assert service.index_question(q) is False
        readiness = get_dedup_readiness()
        assert readiness["status"] == "degraded"
        assert readiness["failure_count"] >= 1
        assert readiness["recent_failures"][-1]["question_id"] == q.id

    def test_degraded_rejects_new_generation_tasks(self, db, fakes, monkeypatch):
        """执行中索引失效 → 新任务安全失败 + 明确报错（不静默跳过语义去重）。"""
        reset_dedup_readiness("degraded", "向量索引写入失败")
        monkeypatch.setattr(
            "app.services.question_dedup_service.get_embedding_service", lambda: fakes[0])
        monkeypatch.setattr(
            "app.services.question_dedup_service.get_question_vector_store", lambda: fakes[1])

        from app.models import AdminUser, QuestionGenerationTask

        admin = db.query(AdminUser).order_by(AdminUser.id).first()
        if admin is None:
            admin = AdminUser(username="testadmin", password_hash="x",
                              nickname="测试管理员", status=1)
            db.add(admin)
            db.flush()
        task = QuestionGenerationTask(
            total_count=1, success_count=0, duplicate_count=0, failed_count=0,
            status="pending", allocation_mode="manual", requested_count=1,
            created_by=admin.id,
        )
        db.add(task)
        db.flush()
        db.commit()

        execute_generation_task(task.id, {
            "question_bank_id": get_bank_id(db), "question_type": "SINGLE_CHOICE",
            "difficulty": 2, "allocation_mode": "manual", "knowledge_id": 1, "count": 1,
        }, session_factory=sessionmaker(bind=db.get_bind()))

        db.rollback()
        db.expire_all()
        task = db.get(QuestionGenerationTask, task.id)
        assert task.status == "failed"
        assert "未就绪" in (task.error_summary or "")

    def test_semantic_unavailable_blocks_save_safely(self, db, monkeypatch):
        """语义层不可用时最终入库校验安全失败，不得静默只跑指纹。"""
        monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)

        class BrokenEmbedding:
            def embed_text(self, text):
                raise RuntimeError("embedding down")

            def embed_texts(self, texts):
                raise RuntimeError("embedding down")

        service = QuestionDeduplicationService(
            db, llm_reviewer=StubLLMReviewer(), embedding_service=BrokenEmbedding(),
            vector_store=FakeVectorStore())
        bank = get_bank_id(db)
        snap = make_snap("语义层不可用时的新题", bank_id=bank)

        def save_fn():
            raise AssertionError("语义层不可用时不得入库")

        obj, verdict = service.guarded_save(snap, save_fn)
        assert obj is None
        assert verdict["reason"] == "semantic_unavailable"

    def test_initialize_question_index_success_and_idempotent(self, db, fakes, monkeypatch):
        from app.services.question_dedup_service import initialize_question_index

        monkeypatch.setattr(
            "app.services.question_dedup_service.get_embedding_service", lambda: fakes[0])
        monkeypatch.setattr(
            "app.services.question_dedup_service.get_question_vector_store", lambda: fakes[1])
        make_question(db, "启动初始化构建的题目甲", status="published")
        make_question(db, "启动初始化构建的题目乙", status="rejected")  # 排除非阻断状态

        snap = initialize_question_index(db)
        assert snap["status"] == "ready"
        assert snap["stats"]["success"] >= 1
        snap2 = initialize_question_index(db)
        assert snap2["status"] == "ready"
        assert snap2["stats"]["skipped"] >= 1  # 幂等

    def test_initialize_question_index_failure_degraded(self, db, fakes, monkeypatch):
        from app.services.question_dedup_service import initialize_question_index

        store = FakeVectorStore()
        store.fail_upsert = True
        monkeypatch.setattr(
            "app.services.question_dedup_service.get_embedding_service", lambda: fakes[0])
        monkeypatch.setattr(
            "app.services.question_dedup_service.get_question_vector_store", lambda: store)
        make_question(db, "构建失败的题目", status="published")

        snap = initialize_question_index(db)
        assert snap["status"] == "degraded"
        assert "degraded" in snap["reason"] or snap["stats"].get("failed", 0) >= 1


# =====================================================================
# 4. 真实 Embedding 语义改写并发样本（§3.4：不得只 Mock）
# =====================================================================


def _real_embedding_available() -> bool:
    try:
        from agent.common.embedding import get_embedding_service
        svc = get_embedding_service()
        svc.embed_text("模型可用性探测")
        return True
    except Exception:  # noqa: BLE001
        return False


REAL_OK = _real_embedding_available()


@pytest.mark.skipif(not REAL_OK, reason="真实 Embedding 模型（FlagEmbedding）不可用")
class TestRealEmbeddingSemanticRace:
    def test_real_embedding_rewrite_race_only_one_saved(self, db, monkeypatch):
        """真实 Embedding + 真实 FAISS：语义改写对并发 → 只存 1 道。"""
        from agent.common.vector_store import reset_question_vector_store

        reset_question_vector_store()
        monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD", 0.65)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD", 0.85)
        ensure_knowledge(db, [1])
        db.commit()  # 线程 session 需要看到知识行（FK 约束）
        bank = get_bank_id(db)
        reviewer = StubLLMReviewer()
        reviewer.verdict_fn = lambda p: "duplicate"
        contents = [
            "HashMap 的底层数据结构是什么？",
            "Java 中 HashMap 的底层采用什么数据结构实现？",
        ]
        seen_scores = []

        def worker(idx, barrier):
            session = sessionmaker(bind=db.get_bind())()
            try:
                service = QuestionDeduplicationService(
                    session, llm_reviewer=reviewer)
                snap = make_snap(contents[idx], bank_id=bank, knowledge_ids=(1,))
                save_fn = _save_fn_for(session, snap, bank, 1)

                barrier.wait()
                obj, verdict = service.guarded_save(snap, save_fn)
                seen_scores.append(verdict.get("algorithm_score"))
                return obj is not None, verdict.get("reason")
            finally:
                session.close()

        results = _run_concurrently(worker, 2)
        assert not any(isinstance(v, Exception) for _, v in results), results
        saved = sum(1 for _, (ok, _r) in results if ok)
        _refresh(db)
        rows = db.query(Question).filter(Question.content.in_(contents)).all()
        print(f"\n[真实Embedding语义改写竞争] 保存={saved} 判定分={seen_scores}")
        assert saved == 1, f"真实语义改写并发应只存 1 道，实际 {results}"
        assert len(rows) == 1

    def test_real_embedding_llm_distinct_competition_both_kept(self, db, monkeypatch):
        """真实 Embedding 语义改写对 + LLM 判 distinct 的并发竞争：
        双方都应保留（不误杀），且后到一方必须对新增候选重新核验，不得沿用过期结果（§3.3.7）。"""
        from agent.common.vector_store import reset_question_vector_store

        reset_question_vector_store()
        monkeypatch.setattr(agent_settings, "AGENT_MAX_RETRIES", 0)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD", 0.65)
        monkeypatch.setattr(agent_settings, "QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD", 0.99)  # 全靠 rivals 复核
        ensure_knowledge(db, [1])
        db.commit()
        bank = get_bank_id(db)
        reviewer = StubLLMReviewer()
        reviewer.verdict_fn = lambda p: "distinct"
        contents = [
            "HashMap 的底层数据结构是什么？",
            "Java 中 HashMap 的底层采用什么数据结构实现？",
        ]

        def worker(idx, barrier):
            session = sessionmaker(bind=db.get_bind())()
            try:
                service = QuestionDeduplicationService(
                    session, llm_reviewer=reviewer)
                snap = make_snap(contents[idx], bank_id=bank, knowledge_ids=(1,))
                save_fn = _save_fn_for(session, snap, bank, 1)

                barrier.wait()
                obj, verdict = service.guarded_save(snap, save_fn)
                return obj is not None, verdict
            finally:
                session.close()

        results = _run_concurrently(worker, 2)
        assert not any(isinstance(v, Exception) for _, v in results), results
        saved = sum(1 for _, (ok, _v) in results if ok)
        rivals_reviewed = sum(
            (v or {}).get("rivals_reviewed", 0) for _, (ok, v) in results if ok)
        _refresh(db)
        rows = db.query(Question).filter(Question.content.in_(contents)).all()
        print(f"\n[真实Embedding distinct竞争] 保存={saved} rivals复核={rivals_reviewed} "
              f"LLM调用={reviewer.calls}")
        assert saved == 2, f"LLM 判 distinct 的语义改写并发应都保留，实际 {results}"
        assert len(rows) == 2
        assert reviewer.calls >= 1 or rivals_reviewed >= 1, (
            "后到一方必须对新增候选重新核验，不得沿用过期结果")
