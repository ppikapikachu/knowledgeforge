"""docs/14 补充《DSH补充_普通用户练习后端接口核查与补齐执行文档》§16 补充测试。

覆盖旧测试未覆盖的增量项：
    16.2 题库开放（用户端三接口 + 管理开关 + 归属校验）
    16.3 组卷幂等强化（同 key 同参/异参冲突/跨用户/键格式/参数校验）
    16.4 快照答案安全（result/detail 按会话状态投影，未提交不泄露）
    16.8 评论身份迁移（普通用户身份、历史匿名显示、本人删除、管理员审核）
    13   管理端普通用户管理（列表/详情/禁用撤销会话）

注：16.1/16.5/16.6/16.7 的主体用例已由 tests/test_practice.py 覆盖
（认证/会话/判分幂等/统计固定样本），本文件只补增量。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime

import pytest
from fastapi.testclient import TestClient  # noqa: F401

from app.models.question_answer_record import QuestionAnswerRecord  # noqa: F401
from app.models.question_comment import QuestionComment
from app.models.app_user import AppUser
from test_practice import (  # noqa: F401
    API,
    CTX,
    auth_header,
    make_question,
    paper_session,
    register_user,
    seed_questions,
    user_token,
)

pytestmark = pytest.mark.skipif(
    False, reason=""
)


@pytest.fixture(autouse=True)
def _open_practice_bank(db):
    """同 test_practice：开放 uncategorized 题库并记录 ID（本模块 autouse 复制一份）。"""
    from app.models.question_bank import QuestionBank
    bank = db.query(QuestionBank).filter(QuestionBank.code == "uncategorized").first()
    if not bank.is_available_for_practice:
        bank.is_available_for_practice = True
        db.commit()
    CTX["bank_id"] = bank.id
    yield


@pytest.fixture
def user_headers(client, user_token):
    return auth_header(user_token)


def _first_item(client, headers, sid):
    items = client.get(f"{API}/practice/sessions/{sid}", headers=headers).json()["data"]["items"]
    return next(i for i in items if i["question_type"] == "SINGLE_CHOICE")


def _assemble(client, headers, **over):
    body = {
        "title": "补充测试卷",
        "question_bank_id": CTX["bank_id"],
        "question_type_counts": {"SINGLE_CHOICE": 1},
        "difficulty_distribution": {"easy": 1},
        "total_count": 1,
    }
    body.update(over)
    return client.post(f"{API}/practice/papers/assemble", headers=headers, json=body)


class TestQuestionBankOpen:
    """§16.2 开放题库。"""

    def test_user_list_only_open_banks(self, db, client, user_headers):
        from app.models.question_bank import QuestionBank
        closed = QuestionBank(name="未开放题库", code="closed_bank_t", is_available_for_practice=False, status=1)
        db.add(closed)
        db.commit()
        resp = client.get(f"{API}/practice/question-banks", headers=user_headers)
        data = resp.json()["data"]
        ids = [b["id"] for b in data["items"]]
        assert CTX["bank_id"] in ids
        assert closed.id not in ids  # 未开放不出现在用户列表

    def test_user_list_item_fields(self, client, user_headers, seed_questions):
        data = client.get(f"{API}/practice/question-banks", headers=user_headers).json()["data"]
        item = next(b for b in data["items"] if b["id"] == CTX["bank_id"])
        for key in ("available_question_count", "question_type_counts",
                    "difficulty_counts", "can_assemble", "unavailable_reason"):
            assert key in item
        assert item["can_assemble"] is True

    def test_closed_bank_detail_same_as_missing(self, db, client, user_headers):
        from app.models.question_bank import QuestionBank
        closed = QuestionBank(name="未开放题库2", code="closed_bank_u", is_available_for_practice=False, status=1)
        db.add(closed)
        db.commit()
        r1 = client.get(f"{API}/practice/question-banks/{closed.id}", headers=user_headers)
        r2 = client.get(f"{API}/practice/question-banks/999999", headers=user_headers)
        assert r1.json()["code"] == r2.json()["code"] == 40401  # 不泄露存在性

    def test_knowledge_points_only_published(self, db, client, user_headers, seed_questions):
        # 造一条未发布题的知识点关联，不得出现在清单
        qs = make_question(db, content="未发布关联题", q_type="SINGLE_CHOICE", difficulty=1,
                           answer="A", options=(("A", "一", 1), ("B", "二", 0)), status="pending_review")
        resp = client.get(f"{API}/practice/question-banks/{CTX['bank_id']}/knowledge-points",
                          headers=user_headers)
        data = resp.json()["data"]["knowledge_points"]
        assert isinstance(data, list) and len(data) >= 1
        for kp in data:
            assert kp["knowledge_id"]
            assert kp["name"]
            assert kp["available_question_count"] >= 1

    def test_admin_switch_blocks_assemble_but_keeps_history(self, db, client, user_headers, auth_headers, seed_questions):
        r = _assemble(client, user_headers)
        assert r.json()["code"] == 0
        paper_id = r.json()["data"]["paper"]["paper_id"]
        # 管理端关闭
        off = client.patch(f"{API}/question-banks/{CTX['bank_id']}/practice-availability",
                           headers=auth_headers, json={"is_available_for_practice": False})
        assert off.json()["code"] == 0
        # 未来组卷被挡
        blocked = _assemble(client, user_headers)
        assert blocked.json()["code"] != 0
        # 历史试卷仍在
        detail = client.get(f"{API}/practice/papers/{paper_id}", headers=user_headers)
        assert detail.json()["code"] == 0
        # 恢复
        on = client.patch(f"{API}/question-banks/{CTX['bank_id']}/practice-availability",
                          headers=auth_headers, json={"is_available_for_practice": True})
        assert on.json()["code"] == 0

    def test_admin_list_has_practice_fields(self, client, auth_headers):
        data = client.get(f"{API}/question-banks", headers=auth_headers).json()["data"]
        item = next(b for b in data["items"] if b["id"] == CTX["bank_id"])
        for key in ("is_available_for_practice", "published_question_count",
                    "pending_review_count", "can_assemble"):
            assert key in item


class TestAssembleIdempotency:
    """§16.3 组卷幂等强化。"""

    def test_same_key_same_params_returns_original(self, client, user_headers, seed_questions):
        r1 = client.post(f"{API}/practice/papers/assemble", headers={**user_headers, "Idempotency-Key": "asm-key-1"},
                         json={"title": "幂等卷", "question_bank_id": CTX["bank_id"],
                               "question_type_counts": {"SINGLE_CHOICE": 1},
                               "difficulty_distribution": {"easy": 1}, "total_count": 1})
        r2 = client.post(f"{API}/practice/papers/assemble", headers={**user_headers, "Idempotency-Key": "asm-key-1"},
                         json={"title": "幂等卷", "question_bank_id": CTX["bank_id"],
                               "question_type_counts": {"SINGLE_CHOICE": 1},
                               "difficulty_distribution": {"easy": 1}, "total_count": 1})
        assert r1.json()["code"] == 0 and r2.json()["code"] == 0
        assert r2.json()["data"]["idempotent"] is True
        assert r1.json()["data"]["paper"]["paper_id"] == r2.json()["data"]["paper"]["paper_id"]

    def test_same_key_different_params_conflict(self, client, user_headers):
        client.post(f"{API}/practice/papers/assemble", headers={**user_headers, "Idempotency-Key": "asm-2"},
                    json={"title": "幂等卷A", "question_bank_id": CTX["bank_id"],
                          "question_type_counts": {"SINGLE_CHOICE": 1},
                          "difficulty_distribution": {"easy": 1}, "total_count": 1})
        conflict = client.post(f"{API}/practice/papers/assemble", headers={**user_headers, "Idempotency-Key": "asm-2"},
                               json={"title": "幂等卷B", "question_bank_id": CTX["bank_id"],
                                     "question_type_counts": {"SINGLE_CHOICE": 1},
                                     "difficulty_distribution": {"easy": 1}, "total_count": 1})
        assert conflict.json()["code"] == 40001

    def test_different_users_same_key_independent(self, client, user_headers, seed_questions):
        other = auth_header(register_user(client, account="idemuser2"))
        r1 = client.post(f"{API}/practice/papers/assemble", headers={**user_headers, "Idempotency-Key": "asm-3"},
                         json={"title": "卷", "question_bank_id": CTX["bank_id"],
                               "question_type_counts": {"SINGLE_CHOICE": 1},
                               "difficulty_distribution": {"easy": 1}, "total_count": 1})
        r2 = client.post(f"{API}/practice/papers/assemble", headers={**other, "Idempotency-Key": "asm-3"},
                         json={"title": "卷", "question_bank_id": CTX["bank_id"],
                               "question_type_counts": {"SINGLE_CHOICE": 1},
                               "difficulty_distribution": {"easy": 1}, "total_count": 1})
        assert r1.json()["code"] == 0 and r2.json()["code"] == 0
        assert r1.json()["data"]["paper"]["paper_id"] != r2.json()["data"]["paper"]["paper_id"]

    def test_invalid_idempotency_key_rejected(self, client, user_headers):
        bad = client.post(f"{API}/practice/papers/assemble",
                          headers={**user_headers, "Idempotency-Key": "bad key with spaces!"},
                          json={"title": "卷", "question_bank_id": CTX["bank_id"],
                                "question_type_counts": {"SINGLE_CHOICE": 1},
                                "difficulty_distribution": {"easy": 1}, "total_count": 1})
        assert bad.json()["code"] != 0
        long_key = client.post(f"{API}/practice/papers/assemble",
                               headers={**user_headers, "Idempotency-Key": "x" * 200},
                               json={"title": "卷", "question_bank_id": CTX["bank_id"],
                                     "question_type_counts": {"SINGLE_CHOICE": 1},
                                     "difficulty_distribution": {"easy": 1}, "total_count": 1})
        assert long_key.json()["code"] != 0

    def test_knowledge_ids_must_belong_to_bank(self, client, user_headers):
        resp = _assemble(client, user_headers, knowledge_ids=[999999])
        assert resp.json()["code"] == 40001

    def test_question_bank_id_required(self, client, user_headers):
        resp = client.post(f"{API}/practice/papers/assemble", headers=user_headers, json={
            "title": "缺题库", "question_type_counts": {"SINGLE_CHOICE": 1},
            "difficulty_distribution": {"easy": 1}, "total_count": 1,
        })
        assert resp.json()["code"] != 0


class TestResultAnswerSafety:
    """§16.4 快照答案安全（结果投影按会话状态）。"""

    def test_in_progress_result_hides_unanswered(self, client, user_headers, paper_session):
        _paper, session = paper_session
        sid = session["session_id"]
        result = client.get(f"{API}/practice/sessions/{sid}/result", headers=user_headers)
        assert result.json()["code"] == 0
        for it in result.json()["data"]["items"]:
            assert "correct_answer" not in it
            assert "explanation" not in it
            assert "is_correct" not in it

    def test_answered_item_shows_own_result_only(self, client, user_headers, paper_session):
        _paper, session = paper_session
        sid = session["session_id"]
        item = _first_item(client, user_headers, sid)
        client.post(f"{API}/practice/sessions/{sid}/items/{item['paper_item_id']}/submit",
                    headers=user_headers, json={"answer": ["A"], "idempotency_key": "safe-key-01"})
        result = client.get(f"{API}/practice/sessions/{sid}/result", headers=user_headers)
        for it in result.json()["data"]["items"]:
            if it["paper_item_id"] == item["paper_item_id"]:
                assert it["correct_answer"]  # 已提交可见
            else:
                assert "correct_answer" not in it  # 未提交不可见

    def test_abandoned_result_hides_unanswered(self, client, user_headers, paper_session):
        _paper, session = paper_session
        sid = session["session_id"]
        client.post(f"{API}/practice/sessions/{sid}/abandon", headers=user_headers)
        result = client.get(f"{API}/practice/sessions/{sid}/result", headers=user_headers)
        for it in result.json()["data"]["items"]:
            assert "correct_answer" not in it

    def test_completed_result_full_review(self, client, user_headers, paper_session):
        _paper, session = paper_session
        sid = session["session_id"]
        item = _first_item(client, user_headers, sid)
        client.post(f"{API}/practice/sessions/{sid}/items/{item['paper_item_id']}/submit",
                    headers=user_headers, json={"answer": ["A"], "idempotency_key": "safe-key-02"})
        client.post(f"{API}/practice/sessions/{sid}/complete", headers=user_headers)
        result = client.get(f"{API}/practice/sessions/{sid}/result", headers=user_headers)
        for it in result.json()["data"]["items"]:
            assert it["correct_answer"]  # 完成后全量回顾
            assert "explanation" in it

    def test_session_detail_projection_state_aware(self, client, user_headers, paper_session):
        _paper, session = paper_session
        sid = session["session_id"]
        item = _first_item(client, user_headers, sid)
        client.post(f"{API}/practice/sessions/{sid}/items/{item['paper_item_id']}/submit",
                    headers=user_headers, json={"answer": ["A"], "idempotency_key": "safe-key-03"})
        detail = client.get(f"{API}/practice/sessions/{sid}", headers=user_headers)
        for it in detail.json()["data"]["items"]:
            if it["paper_item_id"] == item["paper_item_id"]:
                assert it["correct_answer"]
            else:
                assert "correct_answer" not in it


class TestCommentsIdentity:
    """§16.8 评论身份迁移。"""

    def test_user_creates_comment_with_app_identity(self, db, client, user_headers, seed_questions):
        qid = seed_questions[0].id
        resp = client.post(f"{API}/comments/question/{qid}", headers=user_headers,
                           json={"content": "这是一条普通用户评论"})
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["id"]
        row = db.query(QuestionComment).order_by(QuestionComment.id.desc()).first()
        assert row.app_user_id is not None
        assert row.user_id == 0  # 历史列不承载身份

    def test_legacy_comment_shows_anonymous(self, db, client, user_headers, seed_questions):
        qid = seed_questions[0].id
        db.add(QuestionComment(question_id=qid, user_id=0, app_user_id=None,
                               content="历史评论", status="visible"))
        db.commit()
        resp = client.get(f"{API}/comments/question/{qid}", headers=user_headers)
        items = resp.json()["data"]["items"]
        legacy = next(c for c in items if c["content"] == "历史评论")
        assert legacy["nickname"] == "匿名用户"  # 历史 NULL 评论不冒充具体用户

    def test_delete_own_only(self, client, user_headers, seed_questions):
        qid = seed_questions[0].id
        cid = client.post(f"{API}/comments/question/{qid}", headers=user_headers,
                          json={"content": "我的评论"}).json()["data"]["id"]
        other = auth_header(register_user(client, account="intruder2"))
        denied = client.delete(f"{API}/comments/{cid}", headers=other)
        assert denied.json()["code"] == 40301
        ok = client.delete(f"{API}/comments/{cid}", headers=user_headers)
        assert ok.json()["code"] == 0

    def test_moderate_requires_admin(self, client, user_headers, seed_questions):
        qid = seed_questions[0].id
        cid = client.post(f"{API}/comments/question/{qid}", headers=user_headers,
                          json={"content": "待审核评论"}).json()["data"]["id"]
        denied = client.post(f"{API}/comments/{cid}/moderate", headers=user_headers,
                             json={"action": "hide"})
        assert denied.json()["code"] != 0

    def test_content_rules(self, client, user_headers, seed_questions):
        qid = seed_questions[0].id
        blank = client.post(f"{API}/comments/question/{qid}", headers=user_headers, json={"content": "  "})
        assert blank.json()["code"] != 0
        long = client.post(f"{API}/comments/question/{qid}", headers=user_headers, json={"content": "x" * 2001})
        assert long.json()["code"] != 0


class TestAdminAppUsers:
    """§13 普通用户管理。"""

    def test_list_and_detail_exclude_secrets(self, db, client, auth_headers):
        u = register_user(client, account="mgmtuser1")
        data = client.get(f"{API}/admin/app-users", headers=auth_headers).json()["data"]
        row = next(x for x in data["items"] if x["account"] == "mgmtuser1")
        for key in ("password_hash", "refresh_token_hash"):
            assert key not in row
        detail = client.get(f"{API}/admin/app-users/{row['id']}", headers=auth_headers).json()["data"]
        assert detail["account"] == "mgmtuser1"

    def test_keyword_and_status_filter(self, client, auth_headers):
        register_user(client, account="filteruser1")
        data = client.get(f"{API}/admin/app-users?keyword=filteruser&status=active",
                          headers=auth_headers).json()["data"]
        assert all("filteruser" in x["account"] for x in data["items"])
        bad = client.get(f"{API}/admin/app-users?status=whatever", headers=auth_headers)
        assert bad.json()["code"] != 0

    def test_disable_revokes_sessions_and_blocks_login(self, client, auth_headers):
        token = register_user(client, account="disableuser1")
        uid = token["user"]["id"]
        resp = client.patch(f"{API}/admin/app-users/{uid}/status", headers=auth_headers,
                            json={"status": "disabled", "reason": "违规"})
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["revoked_sessions"] >= 1
        # 旧 refresh 失效
        replay = client.post(f"{API}/users/refresh", json={"refresh_token": token["refresh_token"]})
        assert replay.json()["code"] != 0
        # 登录被拒（统一失败消息不暴露禁用状态）
        login = client.post(f"{API}/users/login", json={"account": "disableuser1", "password": "pass1234"})
        assert login.json()["code"] != 0
        # 不删历史：用户仍可被查
        detail = client.get(f"{API}/admin/app-users/{uid}", headers=auth_headers)
        assert detail.json()["data"]["status"] == "disabled"

    def test_status_validation(self, client, auth_headers):
        token = register_user(client, account="statususer1")
        uid = token["user"]["id"]
        same = client.patch(f"{API}/admin/app-users/{uid}/status", headers=auth_headers,
                            json={"status": "active"})
        assert same.json()["code"] == 40001  # 状态未变化
        bad = client.patch(f"{API}/admin/app-users/{uid}/status", headers=auth_headers,
                           json={"status": "deleted"})
        assert bad.json()["code"] != 0  # 禁止直接置 deleted
        enable = client.patch(f"{API}/admin/app-users/{uid}/status", headers=auth_headers,
                              json={"status": "disabled"})
        assert enable.json()["code"] == 0
