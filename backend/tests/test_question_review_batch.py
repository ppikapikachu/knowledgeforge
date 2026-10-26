"""手动批量 AI 审核测试（补充开发文档 §11）。

覆盖：
- §11.1 API：预检不建任务、批次创建计数、重复提交冲突、列表/详情、
  鉴权、单批上限、总开关、空 eligible、简答/非 pending 跳过；
- §11.2 服务：逐项执行/决策流转/幂等/认领释放/跳过不伪造记录/单题失败不拖垮；
- §11.3 一致性：批次统计=BatchItem 重算、item 与 record 一致、
  question 状态与 decision 一致、同题同轮唯一约束、并发认领、重启恢复、
  records 过滤、预检与创建一致。

全部使用 StubReviewAgent（不调真实 LLM）；真实模型冒烟在
tests/test_question_review_batch_smoke.py 与 scripts/ 手工验收。
"""

import os
import sys
from typing import List

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))

from agent.common.config import agent_settings  # noqa: E402
from agent.question_review.schemas import (  # noqa: E402
    EvidenceItem,
    QuestionReviewOutput,
    ReviewChecks,
)
from app.models.question import Question  # noqa: E402
from app.models.question_review_batch import (  # noqa: E402
    QuestionReviewBatch,
    QuestionReviewBatchItem,
)
from app.models.question_review_record import QuestionReviewRecord  # noqa: E402
from app.services.question_review_batch_service import (  # noqa: E402
    CLAIM_KEY_ACTIVE,
    QuestionReviewBatchService,
)

from test_question_review import (  # noqa: E402
    StubReviewAgent,
    approve_output,
    make_question,
    manual_output,
    reject_output,
)

API = "/api/v1/question-reviews"


# ---------------------------------------------------------------- helpers

def make_batch_service(db, outputs=None, raise_error=False):
    stub = StubReviewAgent(outputs=outputs, raise_error=raise_error)
    svc = QuestionReviewBatchService(db, review_agent=stub)
    return svc, stub


def record_count(db) -> int:
    return db.query(QuestionReviewRecord).count()


def patch_enabled(monkeypatch, value: bool = True):
    monkeypatch.setattr(agent_settings, "QUESTION_AI_REVIEW_ENABLED", value)


def kill_background(monkeypatch, calls: List[int]):
    """拦截后台线程启动（API 测试不真跑 LLM）。"""
    import app.services.background_runner as br

    def fake_run(batch_id):
        calls.append(batch_id)

    monkeypatch.setattr(br, "run_review_batch_in_background", fake_run)


# ---------------------------------------------------------------- §11.2 服务

class TestBatchService:
    def test_preview_marks_ineligible_reasons(self, db):
        q_ok = make_question(db, content="可审核题目一")
        q_short = make_question(db, content="简答题内容", question_type="SHORT_ANSWER", answer="长答案")
        q_done = make_question(db, content="已发布题目", status="published")
        svc, stub = make_batch_service(db)

        result = svc.preview([q_ok.id, q_short.id, q_done.id, 99999999])

        assert result["requested"] == 4
        assert result["eligible"] == 1
        assert result["eligible_question_ids"] == [q_ok.id]
        by_id = {i["question_id"]: i for i in result["items"]}
        assert by_id[q_short.id]["reason_code"] == "unsupported_question_type"
        assert by_id[q_done.id]["reason_code"] == "question_not_pending"
        assert by_id[99999999]["reason_code"] == "question_not_found"
        assert stub.calls == []  # 预检零 LLM
        assert record_count(db) == 0  # 预检零持久化
        assert db.query(QuestionReviewBatch).count() == 0

    def test_create_revalidates_and_counts(self, db, admin_user):
        q1 = make_question(db, content="题目内容甲")
        q2 = make_question(db, content="简答题内容", question_type="SHORT_ANSWER", answer="长答案")
        svc, _ = make_batch_service(db)

        result = svc.create_batch([q1.id, q2.id], created_by=admin_user.id)

        assert result["requested"] == 2
        assert result["accepted"] == 1
        assert result["skipped"] == 1
        items = db.query(QuestionReviewBatchItem).filter_by(batch_id=result["batch_id"]).all()
        assert len(items) == 2
        skipped = [i for i in items if i.status == "skipped"]
        assert skipped[0].skip_reason == "unsupported_question_type"
        assert skipped[0].review_record_id is None  # 跳过不伪造决策记录

    def test_create_after_status_change_skips(self, db, admin_user):
        """预检通过后题目被人工发布 → 创建时重建校验应跳过（不信预检/前端）。"""
        q = make_question(db, content="题目内容甲")
        svc, _ = make_batch_service(db)
        assert svc.preview([q.id])["eligible"] == 1

        q.status = "published"
        db.commit()
        result = svc.create_batch([q.id], created_by=admin_user.id)

        assert result["accepted"] == 0
        assert result["error"] == "no_eligible_questions"

    def test_no_eligible_creates_no_batch(self, db, admin_user):
        q = make_question(db, content="简答题内容", question_type="SHORT_ANSWER", answer="长答案")
        svc, _ = make_batch_service(db)
        result = svc.create_batch([q.id], created_by=admin_user.id)

        assert result["error"] == "no_eligible_questions"
        assert db.query(QuestionReviewBatch).count() == 0
        assert db.query(QuestionReviewBatchItem).count() == 0

    def test_duplicate_submission_no_second_active_item(self, db, admin_user):
        q = make_question(db, content="题目内容甲")
        svc, _ = make_batch_service(db)

        r1 = svc.create_batch([q.id], created_by=admin_user.id)
        r2 = svc.create_batch([q.id], created_by=admin_user.id)

        assert r1["accepted"] == 1
        assert r2["accepted"] == 0
        items = db.query(QuestionReviewBatchItem).filter_by(question_id=q.id).all()
        active = [i for i in items if i.claim_key == CLAIM_KEY_ACTIVE]
        assert len(active) == 1  # DB 唯一约束：同题仅一个活动认领

    def test_execute_completes_and_flows_decision(self, db, admin_user):
        q_ok = make_question(db, content="题目内容甲")
        q_rej = make_question(db, content="题目内容乙")
        q_man = make_question(db, content="题目内容丙")
        svc, stub = make_batch_service(
            db, outputs=[approve_output(), reject_output(), manual_output()]
        )
        result = svc.create_batch([q_ok.id, q_rej.id, q_man.id], created_by=admin_user.id)

        out = svc.execute(result["batch_id"])

        assert out["status"] == "completed"
        stats = out["stats"]
        assert stats["processed"] == 3
        assert stats["auto_approved"] == 1
        assert stats["auto_rejected"] == 1
        assert stats["manual_review"] == 1
        assert stats["failed"] == 0
        assert stats["pending"] == 0
        db.expire_all()
        assert db.query(Question).get(q_ok.id).status == "published"
        assert db.query(Question).get(q_rej.id).status == "rejected"
        assert db.query(Question).get(q_man.id).status == "pending_review"
        assert len(stub.calls) == 3

    def test_execute_is_idempotent(self, db, admin_user):
        q = make_question(db, content="题目内容甲")
        svc, stub = make_batch_service(db, outputs=[approve_output()])
        result = svc.create_batch([q.id], created_by=admin_user.id)

        svc.execute(result["batch_id"])
        out2 = svc.execute(result["batch_id"])  # 终态批次直接返回

        assert out2["status"] == "completed"
        assert len(stub.calls) == 1  # 不重复调 LLM
        assert record_count(db) == 1  # 不重复产生记录

    def test_claim_released_after_terminal(self, db, admin_user):
        q = make_question(db, content="题目内容甲")
        svc, _ = make_batch_service(db, outputs=[manual_output()])  # manual 保持 pending
        r1 = svc.create_batch([q.id], created_by=admin_user.id)
        svc.execute(r1["batch_id"])

        r2 = svc.create_batch([q.id], created_by=admin_user.id)

        assert r2["accepted"] == 1  # 认领已释放，可再次审核（新 review_round）
        assert record_count(db) == 1
        svc.execute(r2["batch_id"])
        assert record_count(db) == 2
        rounds = [r.review_round for r in db.query(QuestionReviewRecord).all()]
        assert sorted(rounds) == [1, 2]

    def test_skipped_item_writes_no_record(self, db, admin_user):
        q_short = make_question(db, content="简答题内容", question_type="SHORT_ANSWER", answer="长答案")
        q_ok = make_question(db, content="题目内容甲")
        svc, stub = make_batch_service(db, outputs=[manual_output()])
        result = svc.create_batch([q_short.id, q_ok.id], created_by=admin_user.id)

        out = svc.execute(result["batch_id"])

        assert out["status"] == "completed"
        assert out["stats"]["skipped"] == 1
        assert record_count(db) == 1  # 只有真实审核的题产生记录
        short_item = db.query(QuestionReviewBatchItem).filter_by(
            batch_id=result["batch_id"], question_id=q_short.id).one()
        assert short_item.review_record_id is None  # 跳过不伪造决策记录
        assert len(stub.calls) == 1

    def test_one_failure_does_not_cascade(self, db, admin_user):
        q1 = make_question(db, content="题目内容甲")
        q2 = make_question(db, content="题目内容乙")
        svc, stub = make_batch_service(
            db, outputs=[approve_output(), QuestionReviewOutput(
                decision="manual_review", risk_level="unknown", checks=ReviewChecks(),
                issue_types=[], reason="x", evidence=[])]
        )
        result = svc.create_batch([q1.id, q2.id], created_by=admin_user.id)
        # 让第 1 个 item 执行抛异常
        orig = svc._execute_item
        state = {"n": 0}

        def flaky(item):
            state["n"] += 1
            if state["n"] == 1:
                raise RuntimeError("boom")
            return orig(item)

        svc._execute_item = flaky
        out = svc.execute(result["batch_id"])

        assert out["status"] == "partial"
        items = db.query(QuestionReviewBatchItem).filter_by(batch_id=result["batch_id"]).all()
        by_q = {i.question_id: i for i in items}
        assert by_q[q1.id].status == "failed"
        assert by_q[q1.id].error_code == "execution_failed"
        assert by_q[q2.id].status == "completed"

    def test_recompute_stats_idempotent(self, db, admin_user):
        q1 = make_question(db, content="题目内容甲")
        q2 = make_question(db, content="简答题内容", question_type="SHORT_ANSWER", answer="长答案")
        svc, _ = make_batch_service(db, outputs=[approve_output()])
        result = svc.create_batch([q1.id, q2.id], created_by=admin_user.id)
        svc.execute(result["batch_id"])

        batch = db.query(QuestionReviewBatch).get(result["batch_id"])
        first = (batch.processed_count, batch.skipped_count, batch.auto_approved_count)
        svc._recompute_stats(batch)
        db.commit()
        db.refresh(batch)
        second = (batch.processed_count, batch.skipped_count, batch.auto_approved_count)
        assert first == second


# ---------------------------------------------------------------- §11.3 一致性

class TestConsistency:
    def test_stats_derived_from_items(self, db, admin_user):
        q1 = make_question(db, content="题目内容甲")
        q2 = make_question(db, content="题目内容乙")
        q3 = make_question(db, content="简答题内容", question_type="SHORT_ANSWER", answer="长答案")
        svc, _ = make_batch_service(db, outputs=[approve_output(), manual_output()])
        result = svc.create_batch([q1.id, q2.id, q3.id], created_by=admin_user.id)
        out = svc.execute(result["batch_id"])
        stats = out["stats"]

        assert stats["total"] == 3
        assert stats["accepted"] == 2
        assert stats["skipped"] == 1
        assert stats["total"] == stats["accepted"] + stats["skipped"]
        assert stats["accepted"] == stats["processed"] + stats["failed"] + stats["pending"]

    def test_item_matches_record_and_question(self, db, admin_user):
        q = make_question(db, content="题目内容甲")
        svc, _ = make_batch_service(db, outputs=[reject_output()])
        result = svc.create_batch([q.id], created_by=admin_user.id)
        svc.execute(result["batch_id"])

        item = db.query(QuestionReviewBatchItem).filter_by(batch_id=result["batch_id"]).one()
        record = db.query(QuestionReviewRecord).get(item.review_record_id)
        assert record.decision == "auto_reject"
        assert record.trigger_source == "manual_batch"
        assert record.batch_id == result["batch_id"]
        assert record.generation_task_id is None  # 不伪造出题任务
        assert db.query(Question).get(q.id).status == "rejected"

    def test_round_unique_constraint(self, db, admin_user):
        from sqlalchemy.exc import IntegrityError
        q = make_question(db, content="题目内容甲")
        svc, _ = make_batch_service(db, outputs=[approve_output()])
        result = svc.create_batch([q.id], created_by=admin_user.id)
        svc.execute(result["batch_id"])
        rec = db.query(QuestionReviewRecord).one()

        dup = QuestionReviewRecord(
            question_id=rec.question_id, review_round=rec.review_round,
            trigger_source="manual_batch", execution_status="success",
            decision="manual_review", reason="dup", model_name="stub",
            prompt_version="review-v1",
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_concurrent_batches_one_active_claim(self, db, admin_user):
        """两个批次认领同题：第二个批次该题只能 skipped（DB 约束，非进程锁）。"""
        q = make_question(db, content="题目内容甲")
        q2 = make_question(db, content="题目内容乙")
        svc1, _ = make_batch_service(db, outputs=[manual_output(), manual_output()])
        svc2, _ = make_batch_service(db, outputs=[manual_output(), manual_output()])
        r1 = svc1.create_batch([q.id], created_by=admin_user.id)
        r2 = svc2.create_batch([q.id, q2.id], created_by=admin_user.id)
        assert r1["accepted"] == 1 and r2["accepted"] == 1

        item2 = db.query(QuestionReviewBatchItem).filter_by(
            batch_id=r2["batch_id"], question_id=q.id).one()
        assert item2.status == "skipped"
        assert item2.skip_reason == "concurrent_review_in_progress"
        active = db.query(QuestionReviewBatchItem).filter_by(
            question_id=q.id, claim_key=CLAIM_KEY_ACTIVE).all()
        assert len(active) == 1  # 同题仅一个活动认领（r1 的 queued item）

        # 全部重复提交（accepted=0）→ 设计决策①：不建批次，返回业务错误
        r3 = svc2.create_batch([q.id], created_by=admin_user.id)
        assert r3["error"] == "no_eligible_questions"
        assert db.query(QuestionReviewBatch).count() == 2

    def test_recover_incomplete_batches_releases_claims(self, db, admin_user):
        q = make_question(db, content="题目内容甲")
        svc, _ = make_batch_service(db, outputs=[approve_output()])
        result = svc.create_batch([q.id], created_by=admin_user.id)
        # 模拟服务崩溃：item 停在 queued 且占用认领
        recovery = QuestionReviewBatchService(db).recover_incomplete_batches()

        assert recovery["recovered_batches"] == 1
        assert recovery["recovered_items"] == 1
        item = db.query(QuestionReviewBatchItem).filter_by(batch_id=result["batch_id"]).one()
        assert item.status == "failed"
        assert item.error_code == "interrupted_by_restart"
        assert item.claim_key is None  # 认领释放，可重新发起
        batch = db.query(QuestionReviewBatch).get(result["batch_id"])
        assert batch.status in ("failed", "partial")
        assert record_count(db) == 0  # 中断不伪造决策

    def test_preview_matches_create(self, db, admin_user):
        q_ok = make_question(db, content="题目内容甲")
        q_short = make_question(db, content="简答题内容", question_type="SHORT_ANSWER", answer="长答案")
        svc, _ = make_batch_service(db)
        prev = svc.preview([q_ok.id, q_short.id])
        created = svc.create_batch([q_ok.id, q_short.id], created_by=admin_user.id)

        assert prev["eligible"] == created["accepted"]
        assert prev["ineligible"] == created["skipped"]


# ---------------------------------------------------------------- §11.1 API

class TestBatchApi:
    def test_preview_no_task_no_llm(self, client, auth_headers, db, monkeypatch):
        patch_enabled(monkeypatch)
        q = make_question(db, content="题目内容甲")
        spawned: List[int] = []
        kill_background(monkeypatch, spawned)

        resp = client.post(f"{API}/batches/preview",
                           json={"question_ids": [q.id]}, headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["eligible"] == 1
        assert db.query(QuestionReviewBatch).count() == 0
        assert spawned == []

    def test_create_counts_and_returns_batch(self, client, auth_headers, db, admin_user, monkeypatch):
        patch_enabled(monkeypatch)
        q1 = make_question(db, content="题目内容甲")
        q2 = make_question(db, content="简答题内容", question_type="SHORT_ANSWER", answer="长答案")
        spawned: List[int] = []
        kill_background(monkeypatch, spawned)

        resp = client.post(f"{API}/batches",
                           json={"question_ids": [q1.id, q2.id]}, headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["requested"] == 2
        assert data["accepted"] == 1
        assert data["skipped"] == 1
        assert spawned == [data["batch_id"]]  # 已启动后台执行

    def test_duplicate_question_skipped_with_reason(self, client, auth_headers, db, admin_user, monkeypatch):
        patch_enabled(monkeypatch)
        q = make_question(db, content="题目内容甲")
        q2 = make_question(db, content="题目内容乙")
        spawned: List[int] = []
        kill_background(monkeypatch, spawned)
        client.post(f"{API}/batches", json={"question_ids": [q.id]}, headers=auth_headers)

        # 部分重复：q 已被活动批次认领 → skipped；q2 正常接纳
        resp = client.post(f"{API}/batches", json={"question_ids": [q.id, q2.id]},
                           headers=auth_headers)

        data = resp.json()["data"]
        assert data["accepted"] == 1
        assert data["skipped"] == 1
        item = db.query(QuestionReviewBatchItem).filter_by(
            batch_id=data["batch_id"], question_id=q.id).one()
        assert item.status == "skipped"
        assert item.skip_reason == "concurrent_review_in_progress"

    def test_empty_eligible_returns_business_error(self, client, auth_headers, db, monkeypatch):
        patch_enabled(monkeypatch)
        q = make_question(db, content="简答题内容", question_type="SHORT_ANSWER", answer="长答案")
        spawned: List[int] = []
        kill_background(monkeypatch, spawned)

        resp = client.post(f"{API}/batches", json={"question_ids": [q.id]}, headers=auth_headers)

        body = resp.json()
        assert body["code"] == 40001
        assert db.query(QuestionReviewBatch).count() == 0

    def test_batch_list_and_detail(self, client, auth_headers, db, admin_user, monkeypatch):
        patch_enabled(monkeypatch)
        q = make_question(db, content="题目内容甲")
        svc, _ = make_batch_service(db, outputs=[reject_output()])
        result = svc.create_batch([q.id], created_by=admin_user.id)
        svc.execute(result["batch_id"])

        list_resp = client.get(f"{API}/batches", headers=auth_headers)
        assert list_resp.status_code == 200
        payload = list_resp.json()["data"]
        assert payload["total"] == 1
        assert payload["items"][0]["id"] == result["batch_id"]

        filter_resp = client.get(f"{API}/batches?status=completed", headers=auth_headers)
        assert filter_resp.json()["data"]["total"] == 1
        assert client.get(f"{API}/batches?status=running",
                          headers=auth_headers).json()["data"]["total"] == 0

        detail_resp = client.get(f"{API}/batches/{result['batch_id']}", headers=auth_headers)
        detail = detail_resp.json()["data"]
        assert detail["processed_count"] == 1
        item = detail["items"][0]
        assert item["question_id"] == q.id
        assert item["status"] == "completed"
        assert item["review_decision"] == "auto_reject"
        assert item["review_record_id"] is not None
        assert detail["progress"]["processed"] == 1

    def test_batch_detail_not_found(self, client, auth_headers, db):
        resp = client.get(f"{API}/batches/99999999", headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json()["code"] == 40401

    def test_requires_auth(self, client, db):
        assert client.post(f"{API}/batches/preview",
                           json={"question_ids": [1]}).status_code == 401
        assert client.post(f"{API}/batches",
                           json={"question_ids": [1]}).status_code == 401
        assert client.get(f"{API}/batches").status_code == 401

    def test_size_limit_config_and_hard(self, client, auth_headers, db, monkeypatch):
        patch_enabled(monkeypatch)
        monkeypatch.setattr(agent_settings, "QUESTION_AI_REVIEW_BATCH_MAX_ITEMS", 5)
        spawned: List[int] = []
        kill_background(monkeypatch, spawned)

        resp = client.post(f"{API}/batches",
                           json={"question_ids": list(range(1, 7))}, headers=auth_headers)
        assert resp.json()["code"] == 40001  # 超过配置上限 5

        # 硬上限 200（schema 层 422）
        resp2 = client.post(f"{API}/batches",
                            json={"question_ids": list(range(1, 202))}, headers=auth_headers)
        assert resp2.status_code == 422

    def test_global_switch_disabled_rejected(self, client, auth_headers, db, monkeypatch):
        patch_enabled(monkeypatch, False)
        q = make_question(db, content="题目内容甲")

        prev = client.post(f"{API}/batches/preview",
                           json={"question_ids": [q.id]}, headers=auth_headers)
        create = client.post(f"{API}/batches",
                             json={"question_ids": [q.id]}, headers=auth_headers)

        assert prev.json()["code"] == 40001
        assert create.json()["code"] == 40001
        assert "QUESTION_AI_REVIEW_ENABLED" in create.json()["message"]
        assert db.query(QuestionReviewBatch).count() == 0

    def test_records_filter_by_batch_and_trigger(self, client, auth_headers, db, admin_user, monkeypatch):
        patch_enabled(monkeypatch)
        q1 = make_question(db, content="题目内容甲")
        q2 = make_question(db, content="题目内容乙")
        svc, _ = make_batch_service(db, outputs=[approve_output(), manual_output()])
        result = svc.create_batch([q1.id, q2.id], created_by=admin_user.id)
        svc.execute(result["batch_id"])

        by_batch = client.get(
            f"{API}/records?batch_id={result['batch_id']}", headers=auth_headers
        ).json()["data"]
        assert by_batch["total"] == 2

        by_trigger = client.get(
            f"{API}/records?trigger_source=manual_batch", headers=auth_headers
        ).json()["data"]
        assert by_trigger["total"] == 2

        by_both = client.get(
            f"{API}/records?batch_id={result['batch_id']}&trigger_source=generation_task",
            headers=auth_headers,
        ).json()["data"]
        assert by_both["total"] == 0  # AND 语义

        assert all(i["batch_id"] == result["batch_id"] for i in by_batch["items"])
        assert all(i["trigger_source"] == "manual_batch" for i in by_batch["items"])

    def test_skipped_item_detail_has_reason_text(self, client, auth_headers, db, admin_user, monkeypatch):
        patch_enabled(monkeypatch)
        q_short = make_question(db, content="简答题内容", question_type="SHORT_ANSWER", answer="长答案")
        q_ok = make_question(db, content="题目内容甲")
        svc, _ = make_batch_service(db, outputs=[manual_output()])
        result = svc.create_batch([q_short.id, q_ok.id], created_by=admin_user.id)
        svc.execute(result["batch_id"])

        detail = client.get(f"{API}/batches/{result['batch_id']}",
                            headers=auth_headers).json()["data"]
        by_q = {i["question_id"]: i for i in detail["items"]}
        short_item = by_q[q_short.id]
        assert short_item["status"] == "skipped"
        assert short_item["skip_reason"] == "unsupported_question_type"
        assert short_item["skip_reason_text"]
        assert short_item["review_decision"] is None  # 跳过不伪造决策
