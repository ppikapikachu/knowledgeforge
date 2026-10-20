# -*- coding: utf-8 -*-
"""一次性验收探针：真实 FastAPI 进程内验证题目向量索引生命周期（§10/§14）。

验证点（全部在 API 服务进程内完成，非脚本进程）：
1. 启动实际 FastAPI（TestClient 触发 lifespan）→ 索引自动初始化；
2. 服务进程内查询索引数量与就绪状态；
3. 新题入库后立即可被语义检索召回；
4. 驳回/下架后不再阻断（dedup_key 清空 + 索引移除）；
5. 重启（再次进入 lifespan）→ 初始化幂等（skipped）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402


def main() -> None:
    from agent.common.vector_store import get_question_vector_store
    from app.core.database import SessionLocal
    from app.main import app
    from app.models.question import Question
    from app.models.question_knowledge import QuestionKnowledge
    from app.models.question_option import QuestionOption
    from app.services.question_dedup_service import (
        QuestionDeduplicationService,
        get_dedup_readiness,
        sync_question_dedup_state,
    )
    from app.services.question_normalizer import HASH_VERSION, question_normalizer

    report = {}

    # ---- 第一次启动（lifespan → initialize_question_index）----
    with TestClient(app) as client:  # noqa: F841
        readiness = get_dedup_readiness()
        report["boot1_readiness"] = readiness
        report["boot1_index_count"] = get_question_vector_store().count()

        db = SessionLocal()
        try:
            service = QuestionDeduplicationService(db)
            bank_id = db.query(Question.question_bank_id).filter(
                Question.question_bank_id.isnot(None)).limit(1).scalar()
            kid = db.query(QuestionKnowledge.knowledge_id).limit(1).scalar()
            content = "生命周期探针题目：请说明 FAISS 内存索引的启动初始化流程。"
            snap_hash = question_normalizer.compute_content_hash(
                "SHORT_ANSWER", content, "启动时全量构建幂等跳过", [])
            q = Question(
                question_type="SHORT_ANSWER", content=content,
                answer="启动时全量构建幂等跳过", difficulty=2,
                status="pending_review", source_type="MANUAL",
                question_bank_id=bank_id, content_hash=snap_hash,
                hash_version=HASH_VERSION,
                dedup_key=snap_hash,
            )
            db.add(q)
            db.flush()
            db.add(QuestionKnowledge(question_id=q.id, knowledge_id=kid))
            db.commit()
            report["new_question_id"] = q.id

            # 3. 新题入库立即可召回（同进程向量索引）
            indexed = service.index_question(q)
            from app.services.question_dedup_service import QuestionSnapshot
            snap = QuestionSnapshot(
                question_type="SHORT_ANSWER", content=content,
                answer="启动时全量构建幂等跳过", options=[],
                question_bank_id=bank_id, knowledge_ids=[kid],
            )
            from agent.common.embedding import get_embedding_service
            hits = get_question_vector_store().search(
                get_embedding_service().embed_text(snap.vector_text()), top_k=5)
            recalled = [h.metadata.get("question_id") for h in hits]
            report["index_ok"] = indexed
            report["recall_new_question"] = q.id in recalled

            # 4. 驳回后不再阻断：dedup_key 清空 + 索引移除
            q.status = "rejected"
            db.commit()
            sync_question_dedup_state(db, q)
            db.commit()
            db.refresh(q)
            after = get_question_vector_store().count()
            report["rejected_dedup_key_null"] = q.dedup_key is None
            snap2 = QuestionSnapshot(
                question_type="SHORT_ANSWER", content=content,
                answer="启动时全量构建幂等跳过", options=[],
                question_bank_id=bank_id, knowledge_ids=[kid],
            )
            verify2 = service.verify_before_save(snap2)
            report["rejected_not_blocking"] = verify2["blocked"] is False
            report["index_count_after_remove"] = after

            # 清理探针数据
            db.query(QuestionKnowledge).filter_by(question_id=q.id).delete()
            db.query(QuestionOption).filter_by(question_id=q.id).delete()
            db.query(Question).filter_by(id=q.id).delete()
            db.commit()
        finally:
            db.close()

    # ---- 重启（幂等）----
    with TestClient(app) as client:  # noqa: F841
        readiness2 = get_dedup_readiness()
        report["boot2_readiness"] = readiness2
        report["boot2_index_count"] = get_question_vector_store().count()
        report["http_health"] = client.get("/health").json()

    out = os.path.join(os.environ.get("TEMP", "."), "lifecycle_probe_result.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"[report] {out}")


if __name__ == "__main__":
    main()
