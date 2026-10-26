"""QuestionReviewAgent 与任务级 AI 自动审核测试（执行文档 §8）。

覆盖：
- 单元：决策映射（服务端复核）、unsupported 跳过、fail-safe（异常不自动判定）、幂等；
- 集成：enable_ai_review 开关、去重优先过滤、approve/reject/manual 状态流转、
  人工修改不被旧审核覆盖、人工裁定不被迟到审核覆盖、任务统计一致、reopen。
"""

import os
import sys
import time

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))

from agent.question_review.schemas import (  # noqa: E402
    EvidenceItem,
    QuestionReviewOutput,
    ReviewChecks,
)
from agent.question_review.agent import QuestionReviewAgentError  # noqa: E402
from app.models.knowledge import Knowledge  # noqa: E402
from app.models.question import Question  # noqa: E402
from app.models.question_knowledge import QuestionKnowledge  # noqa: E402
from app.models.question_option import QuestionOption  # noqa: E402
from app.models.question_generation_task import QuestionGenerationTask  # noqa: E402
from app.models.question_review_record import QuestionReviewRecord  # noqa: E402
from app.services.question_review_service import QuestionReviewService  # noqa: E402


# ---------------------------------------------------------------- helpers

def ensure_knowledge(db, ids=(1, 2)):
    """插入测试知识点（FK question_knowledge.knowledge_id 依赖）。"""
    from app.models.knowledge_base import KnowledgeBase
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.code == "uncategorized").first()
    for kid in ids:
        if not db.query(Knowledge).filter(Knowledge.id == kid).first():
            db.add(Knowledge(
                id=kid,
                knowledge_base_id=kb.id,
                name=f"知识点{kid}",
                summary="测试",
                content=f"知识点{kid} 的正文内容",
                difficulty=1,
                status=1,
                source_type="MANUAL",
                importance_level="normal",
                importance_source="default",
            ))
    db.commit()


def make_question(db, *, content="题目内容示例", status="pending_review",
                  question_type="SINGLE_CHOICE", generation_task_id=None,
                  analysis="解析内容", knowledge_ids=(1,)):
    ensure_knowledge(db, knowledge_ids)
    from app.services.question_normalizer import question_normalizer
    q = Question(
        question_type=question_type,
        content=content,
        answer="A",
        analysis=analysis,
        difficulty=2,
        status=status,
        source_type="AI",
        question_bank_id=_bank_id(db),
        generation_task_id=generation_task_id,
        content_hash=question_normalizer.compute_content_hash(
            question_type, content, "A", [("选项一", 1), ("选项二", 0)]),
        hash_version="2",
    )
    db.add(q)
    db.flush()
    if question_type in ("SINGLE_CHOICE", "MULTIPLE_CHOICE"):
        db.add(QuestionOption(
            question_id=q.id, option_key="A", option_content="选项一",
            is_correct=True, sort_order=0))
        db.add(QuestionOption(
            question_id=q.id, option_key="B", option_content="选项二",
            is_correct=False, sort_order=1))
    for kid in knowledge_ids:
        db.add(QuestionKnowledge(question_id=q.id, knowledge_id=kid))
    db.commit()
    db.refresh(q)
    return q


def _bank_id(db):
    from app.models.question_bank import QuestionBank
    return db.query(QuestionBank.id).filter(
        QuestionBank.code == "uncategorized").scalar()


def make_task(db, admin_user, **overrides):
    from datetime import datetime
    task = QuestionGenerationTask(
        created_by=admin_user.id,
        request_config={"count": 1},
        status="success",
        total_count=1,
        success_count=1,
        allocation_mode="manual",
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    for k, v in overrides.items():
        setattr(task, k, v)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def approve_output(**kw):
    return QuestionReviewOutput(
        decision="auto_approve",
        risk_level="low",
        checks=ReviewChecks(),
        issue_types=[],
        reason=kw.get("reason", "内容与参考答案、知识点一致"),
        evidence=[],
    )


def reject_output():
    return QuestionReviewOutput(
        decision="auto_reject",
        risk_level="high",
        checks=ReviewChecks(answer_accuracy="fail", option_quality="fail"),
        issue_types=["incorrect_answer"],
        reason="参考答案与题目不符",
        evidence=[EvidenceItem(
            knowledge_id=1, source_excerpt="知识点正文摘录",
            explanation="知识点指出正确答案与题目标注不一致",
        )],
    )


def manual_output():
    return QuestionReviewOutput(
        decision="manual_review",
        risk_level="unknown",
        checks=ReviewChecks(),
        issue_types=[],
        reason="证据不足，需人工确认",
        evidence=[],
    )


class StubReviewAgent:
    """脚本化审核 Agent（记录调用次数与上下文）。"""

    def __init__(self, outputs=None, raise_error=False, delay=0.0):
        self.outputs = list(outputs or [])
        self.raise_error = raise_error
        self.delay = delay
        self.calls = []

    def review(self, context):
        self.calls.append(context)
        if self.delay:
            time.sleep(self.delay)
        if self.raise_error:
            raise QuestionReviewAgentError("质量审核执行失败（安全降级，不作自动判定）")
        if not self.outputs:
            return approve_output()
        return self.outputs.pop(0)


# ---------------------------------------------------------------- 单元：服务逻辑

class TestDecisionNormalization:
    def test_auto_approve_all_pass_goes_through(self, db):
        svc = QuestionReviewService(db)
        out = approve_output()
        assert svc._normalize_decision(out) == "auto_approve"

    def test_auto_approve_with_issue_downgraded(self, db):
        """有 issue_types 的 auto_approve 不可信 → manual_review（不自动发布）。"""
        svc = QuestionReviewService(db)
        out = QuestionReviewOutput(
            decision="auto_approve", risk_level="low",
            checks=ReviewChecks(), issue_types=["factual_error"],
            reason="小问题", evidence=[],
        )
        assert svc._normalize_decision(out) == "manual_review"

    def test_auto_reject_without_evidence_downgraded(self, db):
        """无证据的 auto_reject 不可信 → manual_review（不自动驳回）。"""
        svc = QuestionReviewService(db)
        out = QuestionReviewOutput(
            decision="auto_reject", risk_level="high",
            checks=ReviewChecks(), issue_types=["other"],
            reason="看起来不对", evidence=[],
        )
        assert svc._normalize_decision(out) == "manual_review"

    def test_auto_reject_with_full_evidence_kept(self, db):
        svc = QuestionReviewService(db)
        assert svc._normalize_decision(reject_output()) == "auto_reject"

    def test_no_parse_never_auto_reject(self, db):
        """模型不可用（异常）→ fail-safe，绝非 approve/reject。"""
        q = make_question(db)
        svc = QuestionReviewService(db, agent=StubReviewAgent(raise_error=True))
        result = svc.review_one(q.id, task_id=None)
        assert result["execution_status"] == "failed"
        assert result["decision"] != "auto_reject"
        assert result["decision"] != "auto_approve"


class TestEligibility:
    def test_unsupported_question_type_skipped(self, db):
        ensure_knowledge(db)
        q = make_question(db, question_type="SHORT_ANSWER")
        agent = StubReviewAgent()
        svc = QuestionReviewService(db, agent=agent)
        result = svc.review_one(q.id, task_id=None)
        assert result["execution_status"] == "skipped"
        assert result["error_code"] == "unsupported_question_type"
        assert agent.calls == []

    def test_dedup_unresolved_skipped(self, db):
        """去重 needs_manual_review 未处理 → 不进审核、不得自动发布。"""
        from app.models.question_dedup_record import QuestionDedupRecord
        ensure_knowledge(db)
        q = make_question(db)
        db.add(QuestionDedupRecord(
            new_content_hash=q.content_hash or "x",
            new_hash_version="2",
            new_content_snapshot=q.content,
            new_question_type=q.question_type,
            decision="uncertain",
            decision_method="vector_and_llm",
            needs_manual_review=True,
        ))
        db.commit()
        agent = StubReviewAgent()
        svc = QuestionReviewService(db, agent=agent)
        result = svc.review_one(q.id, task_id=None)
        assert result["execution_status"] == "skipped"
        assert result["error_code"] == "dedup_unresolved"
        assert agent.calls == []

    def test_dedup_duplicate_skipped(self, db):
        from app.models.question_dedup_record import QuestionDedupRecord
        ensure_knowledge(db)
        q = make_question(db)
        db.add(QuestionDedupRecord(
            new_content_hash=q.content_hash or "x",
            new_hash_version="2",
            new_content_snapshot=q.content,
            new_question_type=q.question_type,
            decision="duplicate",
            decision_method="exact_hash",
            needs_manual_review=False,
        ))
        db.commit()
        agent = StubReviewAgent()
        svc = QuestionReviewService(db, agent=agent)
        result = svc.review_one(q.id, task_id=None)
        assert result["execution_status"] == "skipped"
        assert result["error_code"] == "dedup_duplicate"
        assert agent.calls == []

    def test_idempotent_same_round(self, db):
        ensure_knowledge(db)
        q = make_question(db)
        svc = QuestionReviewService(db, agent=StubReviewAgent([approve_output()]))
        first = svc.review_one(q.id, task_id=None)
        second = svc.review_one(q.id, task_id=None)
        assert first["record_id"] == second["record_id"]
        rows = db.query(QuestionReviewRecord).filter(
            QuestionReviewRecord.question_id == q.id).count()
        assert rows == 1


# ---------------------------------------------------------------- 集成：状态流转

class TestStateTransition:
    def test_auto_approve_publishes_atomically(self, db):
        ensure_knowledge(db)
        q = make_question(db, status="pending_review")
        svc = QuestionReviewService(db, agent=StubReviewAgent([approve_output()]))
        result = svc.review_one(q.id, task_id=None)
        assert result["decision"] == "auto_approve"
        db.refresh(q)
        assert q.status == "published"

    def test_auto_reject_soft_rejects_keeps_data(self, db):
        ensure_knowledge(db)
        q = make_question(db, status="pending_review")
        svc = QuestionReviewService(db, agent=StubReviewAgent([reject_output()]))
        result = svc.review_one(q.id, task_id=None)
        assert result["decision"] == "auto_reject"
        db.refresh(q)
        assert q.status == "rejected"  # 软驳回：记录保留，不删数据

    def test_manual_review_keeps_pending(self, db):
        ensure_knowledge(db)
        q = make_question(db)
        svc = QuestionReviewService(db, agent=StubReviewAgent([manual_output()]))
        result = svc.review_one(q.id, task_id=None)
        assert result["decision"] == "manual_review"
        db.refresh(q)
        assert q.status == "pending_review"

    def test_late_review_does_not_override_human(self, db):
        """人工已处理（published）→ 迟到审核不得覆盖。"""
        ensure_knowledge(db)
        q = make_question(db)
        q.status = "published"
        db.commit()
        svc = QuestionReviewService(db, agent=StubReviewAgent([reject_output()]))
        result = svc.review_one(q.id, task_id=None)
        db.refresh(q)
        assert q.status == "published"
        assert result["transition"]["reason"] == "question_status_changed_by_human"

    def test_content_changed_during_review_not_flowed(self, db):
        """审核期间内容被修改（指纹变化）→ 不流转。"""
        ensure_knowledge(db)
        q = make_question(db)

        class ChangingAgent(StubReviewAgent):
            def review(self, context):
                result = super().review(context)
                q.content = q.content + "（人工修改后的新内容）"
                db.commit()
                return result

        svc = QuestionReviewService(db, agent=ChangingAgent([approve_output()]))
        result = svc.review_one(q.id, task_id=None)
        db.refresh(q)
        assert q.status == "pending_review"
        assert result["transition"]["reason"] == "content_changed_during_review"


# ---------------------------------------------------------------- 集成：任务级

class TestRunTaskReview:
    def _prepare_task_with_questions(self, db, admin_user, n=2, status="pending_review"):
        ensure_knowledge(db)
        task = make_task(db, admin_user, enable_ai_review=True, ai_review_status="queued")
        qs = [
            make_question(db, content=f"任务题目 {i} 的内容", status=status,
                          generation_task_id=task.id)
            for i in range(n)
        ]
        return task, qs

    def test_task_statistics_consistent(self, db, admin_user):
        task, qs = self._prepare_task_with_questions(db, admin_user, n=3)
        agent = StubReviewAgent([approve_output(), reject_output(), manual_output()])
        svc = QuestionReviewService(db, agent=agent)
        stats = svc.run_task_review(task.id)["stats"]
        assert stats["total"] == 3
        assert stats["auto_approved"] == 1
        assert stats["auto_rejected"] == 1
        assert stats["manual_review"] == 1
        db.refresh(task)
        assert task.ai_review_total_count == 3
        assert task.ai_auto_approved_count == 1
        assert task.ai_auto_rejected_count == 1
        assert task.ai_manual_review_count == 1
        assert task.ai_review_status == "completed"

    def test_enable_false_not_requested(self, db, admin_user):
        ensure_knowledge(db)
        task = make_task(db, admin_user, enable_ai_review=False)
        make_question(db, generation_task_id=task.id)
        agent = StubReviewAgent()
        svc = QuestionReviewService(db, agent=agent)
        stats = svc.run_task_review(task.id)["stats"]
        assert task.ai_review_status == "not_requested"
        assert agent.calls == []

    def test_unsupported_and_duplicate_counted_skipped(self, db, admin_user):
        from app.models.question_dedup_record import QuestionDedupRecord
        task, _ = self._prepare_task_with_questions(db, admin_user, n=0)
        ensure_knowledge(db)
        q_short = make_question(db, content="简答题内容", question_type="SHORT_ANSWER",
                                generation_task_id=task.id)
        q_dup = make_question(db, content="重复题内容", generation_task_id=task.id)
        db.add(QuestionDedupRecord(
            new_content_hash=q_dup.content_hash or "x",
            new_hash_version="2",
            new_content_snapshot=q_dup.content,
            new_question_type=q_dup.question_type,
            decision="duplicate",
            decision_method="exact_hash",
            needs_manual_review=False,
        ))
        db.commit()
        agent = StubReviewAgent()
        svc = QuestionReviewService(db, agent=agent)
        stats = svc.run_task_review(task.id)["stats"]
        assert stats["skipped"] == 2
        assert stats["processed"] == 0
        assert agent.calls == []
        db.refresh(task)
        assert task.ai_review_skipped_count == 2

    def test_failed_record_written_not_cascade(self, db, admin_user):
        task, qs = self._prepare_task_with_questions(db, admin_user, n=2)
        agent = StubReviewAgent([approve_output()])  # 第二题 outputs 空→approve 默认
        # 第一题失败、第二题成功：单题失败不拖垮任务
        class FailFirstAgent(StubReviewAgent):
            def __init__(self):
                super().__init__()
                self.n = 0

            def review(self, context):
                self.n += 1
                if self.n == 1:
                    raise QuestionReviewAgentError("boom")
                return approve_output()

        svc = QuestionReviewService(db, agent=FailFirstAgent())
        stats = svc.run_task_review(task.id)["stats"]
        assert stats["failed"] == 1
        assert stats["auto_approved"] == 1
        db.refresh(task)
        assert task.ai_review_failed_count == 1
        assert task.ai_review_status == "partial"
        failed_rows = db.query(QuestionReviewRecord).filter(
            QuestionReviewRecord.execution_status == "failed").all()
        assert len(failed_rows) == 1
        assert failed_rows[0].error_code == "execution_failed"


# ---------------------------------------------------------------- API

class TestReviewApi:
    def test_records_pagination_and_filter(self, client, auth_headers, db, admin_user):
        ensure_knowledge(db)
        task = make_task(db, admin_user, enable_ai_review=True)
        q = make_question(db, generation_task_id=task.id)
        svc = QuestionReviewService(db, agent=StubReviewAgent([approve_output()]))
        svc.review_one(q.id, task_id=task.id)

        resp = client.get("/api/v1/question-reviews/records",
                          headers=auth_headers, params={"page": 1, "page_size": 10})
        body = resp.json()
        assert resp.status_code == 200
        assert body["code"] == 0
        assert body["data"]["total"] == 1
        item = body["data"]["items"][0]
        assert item["question_id"] == q.id
        assert item["decision"] == "auto_approve"
        assert item["question_status"] == "published"
        assert "question_type" in item and "question_bank_name" in item

        resp2 = client.get("/api/v1/question-reviews/records", headers=auth_headers,
                           params={"decision": "auto_reject"})
        assert resp2.json()["data"]["total"] == 0

    def test_stats_endpoint(self, client, auth_headers, db, admin_user):
        task = make_task(db, admin_user, enable_ai_review=True,
                         ai_review_status="completed", ai_review_total_count=2)
        resp = client.get(f"/api/v1/question-reviews/stats/{task.id}", headers=auth_headers)
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["ai_review_total_count"] == 2
        assert body["data"]["ai_review_status"] == "completed"

        resp_missing = client.get("/api/v1/question-reviews/stats/99999999",
                                  headers=auth_headers)
        assert resp_missing.json()["code"] != 0

    def test_reopen_flow(self, client, auth_headers, db, admin_user):
        ensure_knowledge(db)
        q = make_question(db)
        svc = QuestionReviewService(db, agent=StubReviewAgent([reject_output()]))
        result = svc.review_one(q.id, task_id=None)
        db.refresh(q)
        assert q.status == "rejected"

        resp = client.post(f"/api/v1/question-reviews/questions/{q.id}/reopen",
                           headers=auth_headers, json={"reason": "误驳回，重新人工复核"})
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["status"] == "pending_review"
        db.refresh(q)
        assert q.status == "pending_review"

        # 重复调用 → 冲突业务码
        resp2 = client.post(f"/api/v1/question-reviews/questions/{q.id}/reopen",
                            headers=auth_headers, json={"reason": "再次开启"})
        assert resp2.json()["code"] != 0

    def test_question_detail_ai_fields(self, client, auth_headers, db):
        ensure_knowledge(db)
        q = make_question(db)
        svc = QuestionReviewService(db, agent=StubReviewAgent([reject_output()]))
        svc.review_one(q.id, task_id=None)
        resp = client.get(f"/api/v1/questions/{q.id}", headers=auth_headers)
        data = resp.json()["data"]
        assert data["ai_review_decision"] == "auto_reject"
        assert data["ai_review_risk_level"] == "high"
        assert data["ai_review_issue_types"] == ["incorrect_answer"]
        assert data["ai_review_record_id"] is not None

    def test_create_task_enable_flag_validation(self, client, auth_headers, db,
                                                monkeypatch):
        """总开关关 + 请求 enable_ai_review=true → 明确业务错误（不静默降级）。"""
        from agent.common.config import agent_settings
        monkeypatch.setattr(agent_settings, "QUESTION_AI_REVIEW_ENABLED", False)
        resp = client.post("/api/v1/question-generation/tasks", headers=auth_headers,
                           json={"question_bank_id": _bank_id(db), "knowledge_id": 1,
                                 "count": 1, "enable_ai_review": True})
        body = resp.json()
        assert body["code"] != 0
        assert "AI 质量审核" in body["message"]

    def test_create_task_enable_true_spawns_with_flag(self, client, auth_headers, db,
                                                      monkeypatch):
        ensure_knowledge(db)
        from agent.common.config import agent_settings
        from app.services import background_runner as br_mod
        monkeypatch.setattr(agent_settings, "QUESTION_AI_REVIEW_ENABLED", True)
        called = {}

        def fake_run(task_id, request_config):
            called["task_id"] = task_id

        monkeypatch.setattr(br_mod, "run_generation_in_background", fake_run)
        resp = client.post("/api/v1/question-generation/tasks", headers=auth_headers,
                           json={"question_bank_id": _bank_id(db), "knowledge_id": 1,
                                 "count": 1, "enable_ai_review": True})
        body = resp.json()
        assert body["code"] == 0
        assert called.get("task_id") is not None
        task = db.query(QuestionGenerationTask).get(called["task_id"])
        assert bool(task.enable_ai_review)
        assert task.ai_review_status == "queued"
