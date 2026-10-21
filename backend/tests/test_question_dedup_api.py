"""题目去重 API 修复与人工复核接口测试（API 执行文档 §5）。

覆盖：
- §5.1 响应 envelope：5 个接口业务成功时 code == 0（解析 JSON 断言，不只看 HTTP 200）；
- §5.2 分页矩阵：元数据/空结果/越界/非法参数/组合筛选；
- §5.3 人工复核 resolve：13 项（结论/审计保留/校验/404/权限/冲突/并发/事务/审计人防伪造）；
- §5.4 状态与索引：initializing/ready/degraded 真实 reason、重建并发保护。
"""

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.models.admin import AdminUser
from app.models.question_dedup_record import QuestionDedupRecord
from app.models.question_generation_task import QuestionGenerationTask
from app.services.question_dedup_service import (
    get_dedup_readiness,
    reset_dedup_readiness,
)

# 项目统一错误协议：BusinessException → HTTP 400 + 业务 code
#（40401 不存在 / 40901 冲突），HTTP 状态码不随业务语义变化（全局 exception_handler）。
NOT_FOUND = (400, 40401)
CONFLICT = (400, 40901)


def assert_error(payload, status_code, biz_code):
    assert payload["code"] == biz_code, f"业务 code 应为 {biz_code}: {payload}"
    return status_code


# =====================================================================
# helpers
# =====================================================================

RECORD_ITEM_KEYS = {
    "id", "task_id", "new_content_hash", "new_hash_version", "new_question_type",
    "new_question_bank_id", "new_knowledge_ids", "new_content_snapshot",
    "matched_question_id", "matched_question_bank_id", "matched_knowledge_ids",
    "matched_source", "scope_mode", "keyword_score", "vector_score",
    "algorithm_score", "llm_called", "llm_decision", "llm_reason",
    "decision", "decision_method", "needs_manual_review", "created_at",
}


def make_record(db, **overrides):
    """插入一条去重判定记录（默认 uncertain 待人工复核）。"""
    fields = dict(
        new_content_hash="test-hash-0001",
        new_hash_version="2",
        new_content_snapshot="题干快照内容",
        new_question_type="SINGLE_CHOICE",
        decision="uncertain",
        decision_method="vector_and_llm",
        needs_manual_review=True,
        llm_called=True,
        llm_decision="uncertain",
        llm_reason="信息不足，无法稳定判断",
        keyword_score=0.61,
        vector_score=0.72,
        algorithm_score=0.67,
        scope_mode="same_scope",
    )
    fields.update(overrides)
    row = QuestionDedupRecord(**fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def make_task(db, admin_user, **overrides):
    fields = dict(
        allocation_mode="manual",
        status="success",
        total_count=2,
        success_count=2,
        created_by=admin_user.id,
    )
    fields.update(overrides)
    task = QuestionGenerationTask(**fields)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def assert_code(payload, expect=0):
    assert payload["code"] == expect, f"业务 code 应为 {expect}，实际 {payload['code']}: {payload}"


@pytest.fixture(autouse=True)
def _reset_readiness():
    reset_dedup_readiness()
    yield
    reset_dedup_readiness()


# =====================================================================
# §5.1 响应 envelope
# =====================================================================

class TestEnvelope:
    def test_status_code_zero(self, client, auth_headers):
        resp = client.get("/api/v1/question-dedup/status", headers=auth_headers)
        assert resp.status_code == 200
        assert_code(resp.json())

    def test_records_code_zero(self, client, auth_headers, db):
        make_record(db)
        resp = client.get("/api/v1/question-dedup/records", headers=auth_headers)
        assert resp.status_code == 200
        payload = resp.json()
        assert_code(payload)

    def test_stats_code_zero(self, client, auth_headers, db, admin_user):
        task = make_task(db, admin_user)
        resp = client.get(f"/api/v1/question-dedup/stats/{task.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert_code(resp.json())

    def test_rebuild_code_zero(self, client, auth_headers, monkeypatch):
        import app.services.question_dedup_service as svc

        monkeypatch.setattr(
            svc, "initialize_question_index",
            lambda db, only_missing=True: {
                "status": "ready", "reason": None,
                "stats": {"total": 0, "success": 0, "failed": 0, "skipped": 0},
                "failures": [],
            },
        )
        resp = client.post("/api/v1/question-dedup/index/rebuild", headers=auth_headers)
        assert resp.status_code == 200
        assert_code(resp.json())

    def test_resolve_code_zero(self, client, auth_headers, db):
        row = make_record(db)
        resp = client.post(
            f"/api/v1/question-dedup/records/{row.id}/resolve",
            headers=auth_headers,
            json={"conclusion": "duplicate", "reason": "实际考查点一致"},
        )
        assert resp.status_code == 200
        assert_code(resp.json())


# =====================================================================
# §5.2 分页接口
# =====================================================================

class TestPagination:
    def test_first_page_metadata(self, client, auth_headers, db):
        for i in range(5):
            make_record(db, new_content_hash=f"hash-p-{i}")
        resp = client.get("/api/v1/question-dedup/records?page=1&page_size=2", headers=auth_headers)
        payload = resp.json()
        assert_code(payload)
        data = payload["data"]
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] == 5
        assert len(data["items"]) == 2

    def test_second_page_no_overlap_no_gap(self, client, auth_headers, db):
        for i in range(5):
            make_record(db, new_content_hash=f"hash-q-{i}")
        page1 = client.get("/api/v1/question-dedup/records?page=1&page_size=2", headers=auth_headers).json()["data"]
        page2 = client.get("/api/v1/question-dedup/records?page=2&page_size=2", headers=auth_headers).json()["data"]
        ids1 = [it["id"] for it in page1["items"]]
        ids2 = [it["id"] for it in page2["items"]]
        assert not set(ids1) & set(ids2)
        assert page2["total"] == 5

    def test_empty_result_is_code_zero(self, client, auth_headers, db):
        resp = client.get("/api/v1/question-dedup/records", headers=auth_headers)
        payload = resp.json()
        assert_code(payload)
        assert payload["data"]["items"] == []
        assert payload["data"]["total"] == 0

    def test_page_out_of_range_returns_empty(self, client, auth_headers, db):
        make_record(db, new_content_hash="hash-oor")
        resp = client.get("/api/v1/question-dedup/records?page=999&page_size=20", headers=auth_headers)
        payload = resp.json()
        assert_code(payload)
        assert payload["data"]["items"] == []
        assert payload["data"]["total"] == 1

    @pytest.mark.parametrize("param", ["page=0", "page=-1"])
    def test_invalid_page_rejected(self, client, auth_headers, param):
        resp = client.get(f"/api/v1/question-dedup/records?{param}", headers=auth_headers)
        assert resp.status_code == 422
        assert resp.json()["code"] != 0

    @pytest.mark.parametrize("param", ["page_size=0", "page_size=101"])
    def test_invalid_page_size_rejected(self, client, auth_headers, param):
        resp = client.get(f"/api/v1/question-dedup/records?{param}", headers=auth_headers)
        assert resp.status_code == 422

    def test_filter_combination_is_and(self, client, auth_headers, db, admin_user):
        task_a = make_task(db, admin_user)
        task_b = make_task(db, admin_user)
        make_record(db, new_content_hash="h-a-u", task_id=task_a.id, decision="uncertain")
        make_record(db, new_content_hash="h-a-d", task_id=task_a.id, decision="duplicate", needs_manual_review=False)
        make_record(db, new_content_hash="h-b-u", task_id=task_b.id, decision="uncertain")
        resp = client.get(
            f"/api/v1/question-dedup/records?task_id={task_a.id}&decision=uncertain&needs_manual_review=true",
            headers=auth_headers,
        )
        payload = resp.json()
        assert_code(payload)
        assert payload["data"]["total"] == 1
        assert payload["data"]["items"][0]["new_content_hash"] == "h-a-u"

    def test_invalid_decision_rejected(self, client, auth_headers):
        resp = client.get("/api/v1/question-dedup/records?decision=maybe", headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json()["code"] == 40001

    def test_item_fields_contract(self, client, auth_headers, db):
        make_record(db, new_content_hash="h-contract")
        item = client.get("/api/v1/question-dedup/records", headers=auth_headers).json()["data"]["items"][0]
        assert RECORD_ITEM_KEYS <= set(item.keys()), f"缺字段: {RECORD_ITEM_KEYS - set(item.keys())}"
        # 人工结论派生字段（新增，向后兼容）
        assert item["manual_resolution"] is None
        assert item["effective_decision"] == item["decision"]


# =====================================================================
# §5.3 人工复核 resolve
# =====================================================================

class TestResolve:
    def test_uncertain_resolved_as_duplicate(self, client, auth_headers, db):
        row = make_record(db, new_content_hash="h-r1")
        resp = client.post(
            f"/api/v1/question-dedup/records/{row.id}/resolve",
            headers=auth_headers,
            json={"conclusion": "duplicate", "reason": "题干措辞不同，考查点与答案一致"},
        )
        payload = resp.json()
        assert_code(payload)
        data = payload["data"]
        assert data["manual_resolution"] == "duplicate"
        assert data["effective_decision"] == "duplicate"
        assert data["needs_manual_review"] is False

    def test_uncertain_resolved_as_distinct(self, client, auth_headers, db):
        row = make_record(db, new_content_hash="h-r2")
        resp = client.post(
            f"/api/v1/question-dedup/records/{row.id}/resolve",
            headers=auth_headers,
            json={"conclusion": "distinct", "reason": "同一知识点不同考查角度"},
        )
        data = resp.json()["data"]
        assert data["manual_resolution"] == "distinct"
        assert data["effective_decision"] == "distinct"
        assert data["needs_manual_review"] is False

    def test_auto_evidence_preserved(self, client, auth_headers, db):
        row = make_record(db, new_content_hash="h-r3", llm_decision="uncertain",
                          algorithm_score=0.67, matched_question_id=None)
        client.post(
            f"/api/v1/question-dedup/records/{row.id}/resolve",
            headers=auth_headers,
            json={"conclusion": "duplicate", "reason": "确认重复"},
        )
        db.rollback()
        fresh = db.query(QuestionDedupRecord).filter(QuestionDedupRecord.id == row.id).first()
        assert fresh.decision == "uncertain"          # 原始自动判定不被覆盖
        assert fresh.llm_decision == "uncertain"
        assert float(fresh.algorithm_score) == pytest.approx(0.67)
        assert float(fresh.vector_score) == pytest.approx(0.72)

    def test_response_fields(self, client, auth_headers, db, admin_user):
        row = make_record(db, new_content_hash="h-r4")
        data = client.post(
            f"/api/v1/question-dedup/records/{row.id}/resolve",
            headers=auth_headers,
            json={"conclusion": "duplicate", "reason": "考查点一致"},
        ).json()["data"]
        assert data["id"] == row.id
        assert data["decision"] == "uncertain"
        assert data["resolution_reason"] == "考查点一致"
        assert data["resolved_by"] == admin_user.id
        assert data["resolved_at"]

    @pytest.mark.parametrize("body", [
        {},
        {"conclusion": "duplicate"},
        {"conclusion": "uncertain", "reason": "x"},       # 人工不允许 uncertain
        {"conclusion": "DUPLICATE", "reason": "x"},       # 大小写敏感
        {"reason": "x"},
    ])
    def test_invalid_conclusion_rejected(self, client, auth_headers, db, body):
        row = make_record(db, new_content_hash=f"h-r5-{hash(str(body))}")
        resp = client.post(
            f"/api/v1/question-dedup/records/{row.id}/resolve",
            headers=auth_headers,
            json=body,
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize("reason", ["", "   ", None])
    def test_blank_reason_rejected(self, client, auth_headers, db, reason):
        row = make_record(db, new_content_hash=f"h-r6-{hash(str(reason))}")
        resp = client.post(
            f"/api/v1/question-dedup/records/{row.id}/resolve",
            headers=auth_headers,
            json={"conclusion": "duplicate", "reason": reason},
        )
        # 空串/None 由 Pydantic 422 拦；纯空白由服务端 40001 拦——都不允许 500/成功
        assert resp.status_code in (400, 422)
        assert resp.json()["code"] != 0

    def test_too_long_reason_rejected(self, client, auth_headers, db):
        row = make_record(db, new_content_hash="h-r7")
        resp = client.post(
            f"/api/v1/question-dedup/records/{row.id}/resolve",
            headers=auth_headers,
            json={"conclusion": "duplicate", "reason": "长" * 1001},
        )
        assert resp.status_code == 422

    def test_not_found_404(self, client, auth_headers):
        resp = client.post(
            "/api/v1/question-dedup/records/99999999/resolve",
            headers=auth_headers,
            json={"conclusion": "duplicate", "reason": "x"},
        )
        assert resp.status_code == NOT_FOUND[0]
        assert_error(resp.json(), *NOT_FOUND)

    def test_non_admin_rejected(self, client, db):
        resp = client.post(
            "/api/v1/question-dedup/records/1/resolve",
            json={"conclusion": "duplicate", "reason": "x"},
        )
        assert resp.status_code == 401

    def test_non_uncertain_record_conflict(self, client, auth_headers, db):
        row = make_record(db, new_content_hash="h-r8", decision="distinct",
                          needs_manual_review=False)
        resp = client.post(
            f"/api/v1/question-dedup/records/{row.id}/resolve",
            headers=auth_headers,
            json={"conclusion": "duplicate", "reason": "x"},
        )
        assert resp.status_code == CONFLICT[0]
        assert_error(resp.json(), *CONFLICT)

    def test_second_resolve_does_not_overwrite(self, client, auth_headers, db):
        row = make_record(db, new_content_hash="h-r9")
        first = client.post(
            f"/api/v1/question-dedup/records/{row.id}/resolve",
            headers=auth_headers,
            json={"conclusion": "duplicate", "reason": "第一次结论"},
        )
        assert_code(first.json())
        second = client.post(
            f"/api/v1/question-dedup/records/{row.id}/resolve",
            headers=auth_headers,
            json={"conclusion": "distinct", "reason": "第二次结论"},
        )
        assert second.status_code == CONFLICT[0]
        assert_error(second.json(), *CONFLICT)
        db.rollback()
        fresh = db.query(QuestionDedupRecord).filter(QuestionDedupRecord.id == row.id).first()
        assert fresh.manual_resolution == "duplicate"          # 不被覆盖
        assert fresh.resolution_reason == "第一次结论"

    def test_concurrent_resolve_only_one_wins(self, client, auth_headers, db):
        from app.core.database import get_db
        from app.main import app as fastapi_app
        from tests.conftest import TestingSessionLocal

        # 并发请求需要各自独立的 DB Session（共享 Session 不是线程安全的）
        def _fresh_db():
            session = TestingSessionLocal()
            try:
                yield session
            finally:
                session.close()

        row = make_record(db, new_content_hash="h-r10")
        url = f"/api/v1/question-dedup/records/{row.id}/resolve"
        fastapi_app.dependency_overrides[get_db] = _fresh_db

        def _call(conclusion):
            return client.post(
                url, headers=auth_headers,
                json={"conclusion": conclusion, "reason": f"并发结论 {conclusion}"},
            )

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(_call, ["duplicate", "distinct"]))
        finally:
            fastapi_app.dependency_overrides[get_db] = lambda: (yield db)
        codes = sorted(r.status_code for r in results)
        biz_codes = sorted(r.json()["code"] for r in results)
        # 条件更新（UPDATE ... WHERE manual_resolution IS NULL）保证只有一方首次处理成功
        assert codes == [200, CONFLICT[0]], f"并发应恰好一个成功一个冲突: {codes}"
        assert biz_codes == [0, CONFLICT[1]]

    def test_transaction_rollback_on_db_error(self, client, auth_headers, db, monkeypatch):
        import app.api.v1.question_dedup as api_mod

        row = make_record(db, new_content_hash="h-r11")

        def _boom(*args, **kwargs):
            raise RuntimeError("模拟数据库写入失败")

        monkeypatch.setattr(api_mod.func, "now", _boom)
        try:
            resp = client.post(
                f"/api/v1/question-dedup/records/{row.id}/resolve",
                headers=auth_headers,
                json={"conclusion": "duplicate", "reason": "不应写入"},
            )
            assert resp.status_code >= 500
        except RuntimeError:
            # TestClient 默认 raise_server_exceptions=True 会把服务端异常直接抛出，
            # 等价于"该请求失败"，事务回滚断言不受影响。
            pass
        db.rollback()
        fresh = db.query(QuestionDedupRecord).filter(QuestionDedupRecord.id == row.id).first()
        # 不得出现"人工结论已写入但 needs_manual_review 仍 true"的半完成状态
        assert fresh.manual_resolution is None
        assert bool(fresh.needs_manual_review) is True

    def test_resolved_by_ignores_body_spoof(self, client, auth_headers, db, admin_user):
        row = make_record(db, new_content_hash="h-r12")
        data = client.post(
            f"/api/v1/question-dedup/records/{row.id}/resolve",
            headers=auth_headers,
            json={"conclusion": "duplicate", "reason": "x", "resolved_by": 99999},
        ).json()["data"]
        assert data["resolved_by"] == admin_user.id      # 伪造的请求体字段被忽略


# =====================================================================
# §5.4 状态与索引
# =====================================================================

class TestStatusAndIndex:
    def test_status_reports_real_readiness(self, client, auth_headers):
        data = client.get("/api/v1/question-dedup/status", headers=auth_headers).json()["data"]
        assert data["status"] in ("initializing", "ready", "degraded", "disabled")
        assert "reason" in data and "failures" in data
        assert data["hash_version"] == "2"

    def test_initializing_not_reported_ready(self, client, auth_headers):
        reset_dedup_readiness("initializing", "启动索引构建中")
        data = client.get("/api/v1/question-dedup/status", headers=auth_headers).json()["data"]
        assert data["status"] == "initializing"
        assert data["reason"] == "启动索引构建中"

    def test_degraded_keeps_reason_and_failures(self, client, auth_headers):
        reset_dedup_readiness("degraded", "向量写入失败")
        data = client.get("/api/v1/question-dedup/status", headers=auth_headers).json()["data"]
        assert data["status"] == "degraded"
        assert data["reason"] == "向量写入失败"

    def test_rebuild_concurrent_conflict(self, client, auth_headers, monkeypatch):
        import app.services.question_dedup_service as svc
        from app.core.database import get_db
        from app.main import app as fastapi_app
        from tests.conftest import TestingSessionLocal

        def _fresh_db():
            session = TestingSessionLocal()
            try:
                yield session
            finally:
                session.close()

        started = []

        def _slow_rebuild(db, only_missing=True):
            started.append(1)
            time.sleep(1.0)
            return {"status": "ready", "reason": None, "stats": {}, "failures": []}

        monkeypatch.setattr(svc, "initialize_question_index", _slow_rebuild)
        fastapi_app.dependency_overrides[get_db] = _fresh_db
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(client.post, "/api/v1/question-dedup/index/rebuild", headers=auth_headers)
                    for _ in range(2)
                ]
                responses = [f.result() for f in futures]
        finally:
            fastapi_app.dependency_overrides[get_db] = lambda: (yield db)
        statuses = sorted(r.status_code for r in responses)
        # 只允许一个进入重建，另一个明确冲突（不并发重建）
        assert statuses == [200, CONFLICT[0]], statuses

    def test_stats_unknown_task_404(self, client, auth_headers):
        resp = client.get("/api/v1/question-dedup/stats/99999999", headers=auth_headers)
        assert resp.status_code == NOT_FOUND[0]
        assert_error(resp.json(), *NOT_FOUND)

    def test_stats_task_without_records_is_zero(self, client, auth_headers, db, admin_user):
        task = make_task(db, admin_user)
        data = client.get(f"/api/v1/question-dedup/stats/{task.id}", headers=auth_headers).json()["data"]
        assert data["records"] == 0
        assert data["by_decision"] == {}
        assert data["by_method"] == {}
        assert data["llm_called"] == 0

    def test_stats_matches_records(self, client, auth_headers, db, admin_user):
        task = make_task(db, admin_user)
        make_record(db, new_content_hash="h-s1", task_id=task.id, decision="uncertain")
        make_record(db, new_content_hash="h-s2", task_id=task.id, decision="uncertain")
        make_record(db, new_content_hash="h-s3", task_id=task.id, decision="duplicate",
                    needs_manual_review=False, decision_method="exact_hash")
        data = client.get(f"/api/v1/question-dedup/stats/{task.id}", headers=auth_headers).json()["data"]
        assert data["records"] == 3
        assert data["by_decision"] == {"uncertain": 2, "duplicate": 1}
