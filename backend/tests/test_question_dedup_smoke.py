"""真实 Embedding + 真实 FAISS 冒烟测试（执行文档 §12：不得只 Mock 向量查询后宣称语义去重完成）。

依赖本地 FlagModel（BAAI/bge-small-zh-v1.5）模型文件；模型缺失时整组跳过并在报告中标记“未验证”。
真实 LLM 不在此测试中调用（网络/密钥不可控）——LLM 触发条件由 test_question_dedup.py 的
调用计数测试覆盖。
"""

import os
import sys

import pytest

from agent.common.config import agent_settings
from agent.common.embedding import get_embedding_service, reset_embedding_service
from agent.common.vector_store import get_question_vector_store, reset_question_vector_store
from app.models import Question
from app.services.question_dedup_service import QuestionDeduplicationService

sys.path.insert(0, os.path.dirname(__file__))
from test_question_dedup import get_bank_id, make_question, make_snap  # noqa: E402

try:
    _embed_probe = get_embedding_service()
    _embed_probe.embed_text("模型可用性探测")
    REAL_EMBEDDING_OK = True
except Exception:  # noqa: BLE001
    REAL_EMBEDDING_OK = False

pytestmark = pytest.mark.skipif(
    not REAL_EMBEDDING_OK,
    reason="本地 Embedding 模型不可用（跳过真实向量冒烟，报告中标记未验证）",
)


class SilentReviewer:
    """真实冒烟不调用 LLM：若被触发则记录并回 distinct。"""

    def __init__(self):
        self.calls = 0

    def review(self, pairs, knowledge_name_fn=None, pair_index_offset=0):
        self.calls += 1
        from agent.question_dedup.schemas import LLMReviewItem

        return {p.pair_id: LLMReviewItem(pair_id=p.pair_id, verdict="distinct", reason="smoke")
                for p in pairs}


@pytest.fixture
def real_env(db):
    """真实 Embedding + 真实 FAISS 题目向量库（与 knowledge 向量库隔离）。"""
    reset_embedding_service()
    reset_question_vector_store()
    service = QuestionDeduplicationService(db, llm_reviewer=SilentReviewer())
    yield service
    reset_question_vector_store()
    reset_embedding_service()


class TestRealEmbeddingVectorSmoke:
    def test_index_and_semantic_recall(self, db, real_env):
        """索引历史题后，语义相近的新题能被真实向量通道召回（同范围）。"""
        bank_id = get_bank_id(db)
        q1 = make_question(db, "HashMap 的底层数据结构是什么？", bank_id=bank_id,
                           knowledge_ids=(1, 2))
        q2 = make_question(db, "Spring 中 Bean 的生命周期有哪些阶段？", bank_id=bank_id,
                           knowledge_ids=(3,))
        assert real_env.index_question(q1) is True
        assert real_env.index_question(q2) is True

        store = get_question_vector_store()
        assert store.count() == 2
        meta = store.get_metadata(f"question_{q1.id}")
        assert meta["question_id"] == q1.id
        assert meta["question_bank_id"] == bank_id
        assert meta["knowledge_ids"] == [1, 2]
        assert meta["embedding_model"] and meta["embedding_version"]

        # 语义相近的新题（换一种说法）应召回 q1 且分数高于 q2
        snap = make_snap("Java 里 HashMap 底层用的什么数据结构呀？",
                         bank_id=bank_id, knowledge_ids=(1,))
        hits = real_env._retrieve_vector_candidates(snap, real_env._embed(snap), top_k=5)
        ids = [h[0].id for h in hits]
        assert q1.id in ids
        score_q1 = next(s for h, s in hits if h.id == q1.id)
        score_q2 = next((s for h, s in hits if h.id == q2.id), 0.0)
        assert score_q1 > score_q2

    def test_exact_hash_zero_llm_with_real_vectors(self, db, real_env):
        """真实向量链路下，指纹命中依旧 0 次 LLM。"""
        make_question(db, "完全相同的题干内容", bank_id=get_bank_id(db))
        result = real_env.check_one(make_snap("完全相同的题干内容",
                                              bank_id=get_bank_id(db)))
        assert result.decision == "duplicate"
        assert result.decision_method == "exact_hash"
        assert real_env._llm_reviewer.calls == 0

    def test_rebuild_missing_vectors_idempotent(self, db, real_env):
        """历史向量补建可重入：全量成功后二次运行全部 skipped。"""
        make_question(db, "历史题目一：ConcurrentHashMap 原理", bank_id=get_bank_id(db))
        make_question(db, "历史题目二：JVM 垃圾回收器对比", bank_id=get_bank_id(db))
        stats1 = real_env.rebuild_missing_vectors(batch_size=4, only_missing=True)
        assert stats1["total"] >= 2 and stats1["failed"] == 0
        assert stats1["success"] >= 2
        stats2 = real_env.rebuild_missing_vectors(batch_size=4, only_missing=True)
        assert stats2["skipped"] >= 2 and stats2["success"] == 0

    def test_question_store_isolated_from_knowledge_store(self, db, real_env):
        """题目向量库与知识向量库相互隔离（独立 namespace）。"""
        make_question(db, "隔离性测试题目", bank_id=get_bank_id(db))
        real_env.rebuild_missing_vectors(batch_size=8)
        qstore = get_question_vector_store()
        from agent.common.vector_store import get_vector_store

        kstore = get_vector_store()
        q_ids = qstore.list_ids()
        assert all(str(i).startswith("question_") for i in q_ids)
        # knowledge 库里不应出现题目向量
        assert not any(str(i).startswith("question_") for i in kstore.list_ids())
