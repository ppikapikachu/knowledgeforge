"""docs/14 §9 自动化测试：普通用户体系 / 组卷快照 / 练习会话 / 判分幂等 / 统计。

    9.1 认证测试        TestUserAuth
    9.2 迁移/历史兼容   TestMigrationCompat
    9.3 组卷与快照       TestAssemble
    9.4 会话续做         TestSession
    9.5 判分与幂等       TestGradingIdempotent
    9.6 统计口径         TestStatistics
"""

from datetime import datetime, timedelta

import pytest

from app.models.knowledge import Knowledge
from app.models.question import Question
from app.models.question_answer_record import QuestionAnswerRecord
from app.models.question_knowledge import QuestionKnowledge
from app.models.question_option import QuestionOption

API = "/api/v1"

# 组卷契约（docs/14 补充 §6.1）：question_bank_id 必填且题库必须开放练习；
# 测试统一使用 uncategorized 题库，autouse 夹具负责开放并记录其 ID。
CTX = {"bank_id": None}


@pytest.fixture(autouse=True)
def _open_practice_bank(db):
    """把 uncategorized 题库设为开放练习并记录 ID，供 assemble 请求使用。"""
    from app.models.question_bank import QuestionBank
    bank = db.query(QuestionBank).filter(QuestionBank.code == "uncategorized").first()
    if not bank.is_available_for_practice:
        bank.is_available_for_practice = True
        db.commit()
    CTX["bank_id"] = bank.id
    yield


# ==================== 公共 helper ====================

def register_user(client, account="alice", password="pass1234", nickname="Alice"):
    resp = client.post(f"{API}/users/register", json={
        "account": account, "password": password, "nickname": nickname,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    return body["data"]


def auth_header(token_data):
    return {"Authorization": f"Bearer {token_data['access_token']}"}


def ensure_knowledge(db, kid):
    exists = db.query(Knowledge).filter(Knowledge.id == kid).first()
    if exists:
        return
    from app.models.knowledge_base import KnowledgeBase
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.code == "uncategorized").first()
    db.add(Knowledge(
        id=kid, knowledge_base_id=kb.id, name=f"知识点{kid}",
        difficulty=1, status=1, source_type="MANUAL", content=f"知识点{kid}内容",
    ))
    db.flush()


def make_question(
    db, content="题干内容", q_type="SINGLE_CHOICE", difficulty=1,
    bank_id=None, answer="A", status="published",
    options=(("A", "选项一", 1), ("B", "选项二", 0)),
    knowledge_ids=(1,),
):
    from app.models.question_bank import QuestionBank
    if bank_id is None:
        # clean_tables 每次重插题库行但不重置自增 ID，不能假设 id=1
        bank = db.query(QuestionBank).filter(QuestionBank.code == "uncategorized").first()
        bank_id = bank.id
    q = Question(
        question_type=q_type, content=content, answer=answer,
        analysis="解析", explanation="解析说明", difficulty=difficulty, status=status,
        question_bank_id=bank_id, source_type="MANUAL",
    )
    db.add(q)
    db.flush()
    for idx, (key, opt_content, ok) in enumerate(options, start=1):
        db.add(QuestionOption(
            question_id=q.id, option_key=key, option_content=opt_content,
            is_correct=ok, sort_order=idx,
        ))
    for kid in knowledge_ids:
        ensure_knowledge(db, kid)
        db.add(QuestionKnowledge(question_id=q.id, knowledge_id=kid))
    db.commit()
    return q


@pytest.fixture
def seed_questions(db):
    """7 道题：3 单选(1/2/3) + 2 多选(2/3) + 1 判断(1) + 1 简答(2)。"""
    qs = []
    qs.append(make_question(db, content="单选题 甲", difficulty=1))
    qs.append(make_question(db, content="单选题 乙", difficulty=2))
    qs.append(make_question(db, content="单选题 丙", difficulty=3))
    qs.append(make_question(db, content="多选题 甲", q_type="MULTIPLE_CHOICE",
                            difficulty=2, answer="AB",
                            options=(("A", "选项一", 1), ("B", "选项二", 1), ("C", "选项三", 0))))
    qs.append(make_question(db, content="多选题 乙", q_type="MULTIPLE_CHOICE",
                            difficulty=3, answer="AB",
                            options=(("A", "选项一", 1), ("B", "选项二", 1), ("C", "选项三", 0))))
    qs.append(make_question(db, content="判断题 甲", q_type="TRUE_FALSE",
                            difficulty=1, answer="TRUE", options=()))
    qs.append(make_question(db, content="简答题 甲", q_type="SHORT_ANSWER",
                            difficulty=2, answer="参考答案文本", options=()))
    return qs


@pytest.fixture
def user_token(client):
    return register_user(client)


@pytest.fixture
def user_headers(user_token):
    return auth_header(user_token)


@pytest.fixture
def paper_session(client, user_headers, seed_questions):
    """组卷并取得初始会话（单选2 + 多选1 + 判断1）。"""
    resp = client.post(f"{API}/practice/papers/assemble", headers=user_headers, json={
        "title": "测试卷 A",
        "question_bank_id": CTX["bank_id"], "question_type_counts": {
            "SINGLE_CHOICE": 2, "MULTIPLE_CHOICE": 1, "TRUE_FALSE": 1,
        },
        "difficulty_distribution": {"easy": 1, "normal": 2, "hard": 1},
        "total_count": 4,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    return data["paper"], data["session"]


# ==================== 9.1 认证测试 ====================

class TestUserAuth:
    def test_register_returns_token_pair(self, client):
        data = register_user(client, account="bob01")
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "Bearer"
        assert data["user"]["account"] == "bob01"

    def test_register_duplicate_account_conflict(self, client):
        register_user(user_token := None or client, account="bob01") if False else register_user(client, account="bob01")
        resp = client.post(f"{API}/users/register", json={
            "account": "BOB01", "password": "pass1234",
        })
        body = resp.json()
        assert body["code"] == 40901  # 规范化后同名

    def test_login_wrong_password_unified_message(self, client):
        register_user(client, account="bob01")
        resp = client.post(f"{API}/users/login", json={
            "account": "bob01", "password": "wrongpass",
        })
        body = resp.json()
        assert body["code"] == 40101
        assert body["message"] == "账号或密码错误"

    def test_login_nonexistent_account_same_message(self, client):
        resp = client.post(f"{API}/users/login", json={
            "account": "ghost01", "password": "whatever1",
        })
        body = resp.json()
        assert body["code"] == 40101
        assert body["message"] == "账号或密码错误"

    def test_refresh_rotation_old_token_rejected(self, client, user_token):
        old_refresh = user_token["refresh_token"]
        resp = client.post(f"{API}/users/refresh", json={"refresh_token": old_refresh})
        assert resp.json()["code"] == 0
        new_refresh = resp.json()["data"]["refresh_token"]
        assert new_refresh != old_refresh

        # 旧 refresh 重放必须失败
        replay = client.post(f"{API}/users/refresh", json={"refresh_token": old_refresh})
        assert replay.json()["code"] == 40101

    def test_logout_revokes_session(self, client, user_token):
        refresh = user_token["refresh_token"]
        resp = client.post(
            f"{API}/users/logout", headers=auth_header(user_token),
            json={"refresh_token": refresh},
        )
        assert resp.json()["code"] == 0
        after = client.post(f"{API}/users/refresh", json={"refresh_token": refresh})
        assert after.json()["code"] == 40101

    def test_update_profile(self, client, user_headers):
        resp = client.patch(f"{API}/users/me", headers=user_headers,
                            json={"nickname": "新昵称"})
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["nickname"] == "新昵称"

    def test_me_requires_token(self, client):
        resp = client.get(f"{API}/users/me")
        assert resp.status_code in (401, 403)


# ==================== 9.2 迁移 / 历史兼容 ====================

class TestMigrationCompat:
    def test_legacy_answer_row_kept_and_excluded_from_new_stats(self, db, client, seed_questions):
        """旧行（app_user_id 为空、user_id 为历史管理员列）保留且不纳入新统计口径。"""
        legacy = QuestionAnswerRecord(
            question_id=seed_questions[0].id,
            user_id=999,
            app_user_id=None,
            user_answer="A",
            is_correct=1,
            grading_status="graded",
            created_at=datetime.utcnow(),
        )
        db.add(legacy)
        db.commit()

        row = db.query(QuestionAnswerRecord).filter(
            QuestionAnswerRecord.user_id == 999
        ).first()
        assert row is not None
        assert row.app_user_id is None

        # 新口径：统计忽略 app_user_id 为空的历史行
        from app.services.statistics_service import StatisticsService
        stats = StatisticsService(db).question_statistics(seed_questions[0].id)
        assert stats["graded_submission_count"] == 0
        assert stats["unique_user_count"] == 0

    def test_new_columns_nullable(self, db, seed_questions):
        """app_user_id / practice_* 列可空，迁移后旧写法可用。"""
        row = QuestionAnswerRecord(
            question_id=seed_questions[1].id,
            user_id=998,
            user_answer="B",
            is_correct=0,
            grading_status="graded",
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        assert row.id > 0
        assert row.practice_session_id is None


# ==================== 9.3 组卷与快照 ====================

class TestAssemble:
    def test_assemble_happy_path(self, client, user_headers, paper_session):
        paper, session = paper_session
        assert paper["status"] == "ready"
        assert paper["question_count"] == 4
        assert session["status"] == "in_progress"
        assert session["total_count"] == 4

    def test_snapshot_immutable(self, db, client, user_headers, paper_session):
        """源题修改后，快照内容不受影响（不实时读 question 表）。"""
        paper, session = paper_session
        q = db.query(Question).filter(Question.content == "单选题 甲").first()
        q.content = "源题被改写"
        db.commit()

        detail = client.get(
            f"{API}/practice/sessions/{session['session_id']}", headers=user_headers
        ).json()["data"]
        contents = [i["content"] for i in detail["items"]]
        assert "单选题 甲" in contents
        assert "源题被改写" not in contents

    def test_total_count_mismatch_rejected(self, client, user_headers):
        resp = client.post(f"{API}/practice/papers/assemble", headers=user_headers, json={
            "title": "坏卷",
            "question_bank_id": CTX["bank_id"], "question_type_counts": {"SINGLE_CHOICE": 2},
            "difficulty_distribution": {"easy": 1},
            "total_count": 3,
        })
        assert resp.json()["code"] == 40001

    def test_insufficient_stock_reports_counts(self, client, user_headers):
        resp = client.post(f"{API}/practice/papers/assemble", headers=user_headers, json={
            "title": "超量卷",
            "question_bank_id": CTX["bank_id"], "question_type_counts": {"SINGLE_CHOICE": 30},
            "difficulty_distribution": {"easy": 30},
            "total_count": 30,
        })
        body = resp.json()
        assert body["code"] == 40001
        assert body["data"]["requested_count"] == 30
        assert body["data"]["missing_count"] > 0

    def test_allow_partial_builds_with_available(self, client, user_headers):
        resp = client.post(f"{API}/practice/papers/assemble", headers=user_headers, json={
            "title": "部分卷",
            "question_bank_id": CTX["bank_id"], "question_type_counts": {"SINGLE_CHOICE": 30},
            "difficulty_distribution": {"easy": 30},
            "total_count": 30,
            "allow_partial": True,
        })
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["paper"]["question_count"] <= 30

    def test_idempotency_key_returns_same_paper(self, client, user_headers, seed_questions):
        payload = {
            "title": "幂等卷",
            "question_bank_id": CTX["bank_id"], "question_type_counts": {"SINGLE_CHOICE": 1},
            "difficulty_distribution": {"easy": 1},
            "total_count": 1,
        }
        headers = dict(user_headers)
        headers["Idempotency-Key"] = "idem-key-0001"
        r1 = client.post(f"{API}/practice/papers/assemble", headers=headers, json=payload)
        r2 = client.post(f"{API}/practice/papers/assemble", headers=headers, json=payload)
        d1, d2 = r1.json()["data"], r2.json()["data"]
        assert d1["paper"]["paper_id"] == d2["paper"]["paper_id"]
        assert d2["idempotent"] is True

    def test_snapshot_projection_hides_answers(self, client, user_headers, paper_session):
        paper, _ = paper_session
        detail = client.get(
            f"{API}/practice/papers/{paper['paper_id']}", headers=user_headers
        ).json()["data"]
        for item in detail["items"]:
            assert "correct_answer" not in item
            assert "explanation" not in item
            for opt in item["options"]:
                assert "is_correct" not in opt

    def test_unpublished_excluded(self, db, client, user_headers):
        make_question(db, content="未发布题", status="pending_review")
        resp = client.post(f"{API}/practice/papers/assemble", headers=user_headers, json={
            "title": "只组已发布",
            "question_bank_id": CTX["bank_id"], "question_type_counts": {"SINGLE_CHOICE": 2},
            "difficulty_distribution": {"easy": 2},
            "total_count": 2,
            "allow_partial": True,
        })
        paper = resp.json()["data"]["paper"]
        detail = client.get(
            f"{API}/practice/papers/{paper['paper_id']}", headers=user_headers
        ).json()["data"]
        assert all(i["content"] != "未发布题" for i in detail["items"])


# ==================== 9.4 会话续做 ====================

class TestSession:
    def test_draft_creates_no_answer_record(self, db, client, user_headers, paper_session):
        paper, session = paper_session
        items = client.get(
            f"{API}/practice/sessions/{session['session_id']}", headers=user_headers
        ).json()["data"]["items"]
        # 组卷会打乱顺序，固定挑单选题（草稿答案值类型须与题型匹配）
        item_id = next(i for i in items if i["question_type"] == "SINGLE_CHOICE")["paper_item_id"]

        resp = client.put(
            f"{API}/practice/sessions/{session['session_id']}/items/{item_id}/draft",
            headers=user_headers, json={"answer": ["A"]},
        )
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["status"] == "draft_saved"
        assert db.query(QuestionAnswerRecord).count() == 0

    def test_mark_toggle(self, client, user_headers, paper_session):
        paper, session = paper_session
        items = client.get(
            f"{API}/practice/sessions/{session['session_id']}", headers=user_headers
        ).json()["data"]["items"]
        item_id = items[0]["paper_item_id"]
        resp = client.patch(
            f"{API}/practice/sessions/{session['session_id']}/items/{item_id}/mark",
            headers=user_headers, json={"is_marked": True},
        )
        assert resp.json()["data"]["is_marked"] is True

    def test_progress_update_and_validation(self, client, user_headers, paper_session):
        paper, session = paper_session
        sid = session["session_id"]
        ok = client.patch(f"{API}/practice/sessions/{sid}/progress",
                          headers=user_headers, json={"current_item_order": 3})
        assert ok.json()["code"] == 0
        bad = client.patch(f"{API}/practice/sessions/{sid}/progress",
                           headers=user_headers, json={"current_item_order": 99})
        assert bad.json()["code"] == 40001

    def test_complete_keeps_unanswered(self, client, user_headers, paper_session):
        paper, session = paper_session
        sid = session["session_id"]
        resp = client.post(f"{API}/practice/sessions/{sid}/complete", headers=user_headers)
        data = resp.json()["data"]
        assert data["status"] == "completed"
        assert data["answered_count"] == 0
        assert data["total_count"] == 4  # 未答保留，不伪造

        # 幂等：重复完成
        again = client.post(f"{API}/practice/sessions/{sid}/complete", headers=user_headers)
        assert again.json()["data"]["status"] == "completed"

        # 已完成不可再提交
        items = client.get(
            f"{API}/practice/sessions/{sid}", headers=user_headers
        ).json()["data"]["items"]
        submit = client.post(
            f"{API}/practice/sessions/{sid}/items/{items[0]['paper_item_id']}/submit",
            headers=user_headers,
            json={"answer": ["A"], "idempotency_key": "k" * 8},
        )
        assert submit.json()["code"] == 40001

    def test_abandon_blocks_resume(self, client, user_headers, paper_session):
        paper, session = paper_session
        sid = session["session_id"]
        client.post(f"{API}/practice/sessions/{sid}/abandon", headers=user_headers)
        resp = client.post(f"{API}/practice/sessions/{sid}/resume", headers=user_headers)
        assert resp.json()["code"] == 40001

    def test_repractice_creates_new_session_same_paper(self, client, user_headers, paper_session):
        paper, session = paper_session
        resp = client.post(
            f"{API}/practice/papers/{paper['paper_id']}/sessions", headers=user_headers
        )
        new_session = resp.json()["data"]
        assert new_session["session_id"] != session["session_id"]
        assert new_session["paper_id"] == paper["paper_id"]

    def test_owner_isolation(self, client, user_headers, paper_session):
        paper, session = paper_session
        other = register_user(client, account="mallory")
        resp = client.get(
            f"{API}/practice/sessions/{session['session_id']}",
            headers=auth_header(other),
        )
        assert resp.json()["code"] == 40401


# ==================== 9.5 判分与幂等 ====================

class TestGradingIdempotent:
    def _first_item(self, client, user_headers, session):
        return client.get(
            f"{API}/practice/sessions/{session['session_id']}", headers=user_headers
        ).json()["data"]["items"][0]

    def _first_single_item(self, client, user_headers, session):
        """固定挑单选题（组卷打乱顺序；种子单选正确答案都是 A）。"""
        items = client.get(
            f"{API}/practice/sessions/{session['session_id']}", headers=user_headers
        ).json()["data"]["items"]
        return next(i for i in items if i["question_type"] == "SINGLE_CHOICE")

    def test_single_choice_correct(self, client, user_headers, paper_session):
        paper, session = paper_session
        items = client.get(
            f"{API}/practice/sessions/{session['session_id']}", headers=user_headers
        ).json()["data"]["items"]
        # 组卷会打乱顺序，固定挑单选题（种子数据单选正确答案都是 A）
        item = next(i for i in items if i["question_type"] == "SINGLE_CHOICE")
        resp = client.post(
            f"{API}/practice/sessions/{session['session_id']}/items/{item['paper_item_id']}/submit",
            headers=user_headers,
            json={"answer": ["A"], "idempotency_key": "key-000001", "time_spent_ms": 1234},
        )
        data = resp.json()["data"]
        assert data["is_correct"] is True
        assert data["grading_status"] == "graded"
        assert data["correct_answer"]  # 提交后返回正确答案
        assert data["explanation"]
        assert data["session_progress"]["answered_count"] == 1

    def test_multiple_choice_requires_exact_set(self, db, client, user_headers):
        q = make_question(
            db, content="多选精确匹配题", q_type="MULTIPLE_CHOICE", difficulty=2,
            answer="AB", options=(("A", "一", 1), ("B", "二", 1), ("C", "三", 0)),
        )
        resp = client.post(f"{API}/practice/papers/assemble", headers=user_headers, json={
            "title": "多选卷", "question_bank_id": CTX["bank_id"], "question_type_counts": {"MULTIPLE_CHOICE": 1},
            "difficulty_distribution": {"normal": 1}, "total_count": 1,
        })
        session = resp.json()["data"]["session"]
        sid = session["session_id"]
        item_id = client.get(
            f"{API}/practice/sessions/{sid}", headers=user_headers
        ).json()["data"]["items"][0]["paper_item_id"]

        # 漏选 → 错
        r1 = client.post(
            f"{API}/practice/sessions/{sid}/items/{item_id}/submit",
            headers=user_headers, json={"answer": ["A"], "idempotency_key": "mc-00001"},
        )
        assert r1.json()["data"]["is_correct"] is False
        # 全对 → 对
        r2 = client.post(
            f"{API}/practice/sessions/{sid}/items/{item_id}/submit",
            headers=user_headers, json={"answer": ["A", "B"], "idempotency_key": "mc-00002"},
        )
        assert r2.json()["data"]["is_correct"] is True

    def test_true_false_normalized(self, db, client, user_headers):
        make_question(db, content="判断归一", q_type="TRUE_FALSE", difficulty=1,
                      answer="TRUE", options=())
        resp = client.post(f"{API}/practice/papers/assemble", headers=user_headers, json={
            "title": "判断卷", "question_bank_id": CTX["bank_id"], "question_type_counts": {"TRUE_FALSE": 1},
            "difficulty_distribution": {"easy": 1}, "total_count": 1,
        })
        sid = resp.json()["data"]["session"]["session_id"]
        item_id = client.get(
            f"{API}/practice/sessions/{sid}", headers=user_headers
        ).json()["data"]["items"][0]["paper_item_id"]
        r = client.post(
            f"{API}/practice/sessions/{sid}/items/{item_id}/submit",
            headers=user_headers, json={"answer": ["true"], "idempotency_key": "tf-00001"},
        )
        assert r.json()["data"]["is_correct"] is True

    def test_short_answer_ungraded(self, db, client, user_headers):
        make_question(db, content="简答判分", q_type="SHORT_ANSWER", difficulty=2,
                      answer="参考答案", options=())
        resp = client.post(f"{API}/practice/papers/assemble", headers=user_headers, json={
            "title": "简答卷", "question_bank_id": CTX["bank_id"], "question_type_counts": {"SHORT_ANSWER": 1},
            "difficulty_distribution": {"normal": 1}, "total_count": 1,
        })
        sid = resp.json()["data"]["session"]["session_id"]
        item_id = client.get(
            f"{API}/practice/sessions/{sid}", headers=user_headers
        ).json()["data"]["items"][0]["paper_item_id"]
        r = client.post(
            f"{API}/practice/sessions/{sid}/items/{item_id}/submit",
            headers=user_headers, json={"answer": ["我的作答"], "idempotency_key": "sa-00001"},
        )
        data = r.json()["data"]
        assert data["grading_status"] == "ungraded"
        assert data["is_correct"] is None

    def test_idempotent_same_key_same_payload(self, client, user_headers, paper_session):
        paper, session = paper_session
        sid = session["session_id"]
        item = self._first_single_item(client, user_headers, session)
        payload = {"answer": ["A"], "idempotency_key": "idem-same-1"}
        r1 = client.post(
            f"{API}/practice/sessions/{sid}/items/{item['paper_item_id']}/submit",
            headers=user_headers, json=payload,
        ).json()["data"]
        r2 = client.post(
            f"{API}/practice/sessions/{sid}/items/{item['paper_item_id']}/submit",
            headers=user_headers, json=payload,
        ).json()["data"]
        assert r2["idempotent"] is True
        assert r1["answer_record_id"] == r2["answer_record_id"]
        # 不重复入账
        assert client.get(
            f"{API}/practice/sessions/{sid}/answers", headers=user_headers
        ).json()["data"]["answers"][0]["id"] == r1["answer_record_id"]

    def test_same_key_different_payload_conflict(self, client, user_headers, paper_session):
        paper, session = paper_session
        sid = session["session_id"]
        item = self._first_single_item(client, user_headers, session)
        client.post(
            f"{API}/practice/sessions/{sid}/items/{item['paper_item_id']}/submit",
            headers=user_headers, json={"answer": ["A"], "idempotency_key": "idem-conf-1"},
        )
        resp = client.post(
            f"{API}/practice/sessions/{sid}/items/{item['paper_item_id']}/submit",
            headers=user_headers, json={"answer": ["B"], "idempotency_key": "idem-conf-1"},
        )
        assert resp.json()["code"] == 40001

    def test_new_key_new_attempt_appended(self, db, client, user_headers, paper_session):
        paper, session = paper_session
        sid = session["session_id"]
        item = self._first_single_item(client, user_headers, session)
        for i in range(2):
            client.post(
                f"{API}/practice/sessions/{sid}/items/{item['paper_item_id']}/submit",
                headers=user_headers, json={"answer": ["A"], "idempotency_key": f"new-key-{i}"},
            )
        records = db.query(QuestionAnswerRecord).filter(
            QuestionAnswerRecord.practice_session_id == sid
        ).all()
        assert len(records) == 2

    def test_submit_rejects_forged_fields(self, client, user_headers, paper_session):
        paper, session = paper_session
        sid = session["session_id"]
        item = self._first_item(client, user_headers, session)
        resp = client.post(
            f"{API}/practice/sessions/{sid}/items/{item['paper_item_id']}/submit",
            headers=user_headers,
            json={
                "answer": ["A"], "idempotency_key": "forge-0001",
                "is_correct": True, "score": 100, "app_user_id": 999,
            },
        )
        data = resp.json()
        assert resp.status_code in (400, 422), data  # §9.2 严格模式：多余字段一律拒绝
        assert data.get("code", 0) != 0


# ==================== 9.6 统计口径 ====================

class TestStatistics:
    def _seed_fixed_sample(self, db, client, user_headers):
        """固定样本：U1 第一次错第二次对；U2 一次对。graded 3 条 2 对。"""
        q = make_question(db, content="统计样本题", difficulty=2)
        u1 = register_user(client, account="statuser1")
        u2 = register_user(client, account="statuser2")
        h1, h2 = auth_header(u1), auth_header(u2)

        base = datetime.utcnow()
        for i, (headers, answer, correct) in enumerate([
            (h1, "B", 0), (h1, "A", 1), (h2, "A", 1),
        ]):
            db.add(QuestionAnswerRecord(
                question_id=q.id,
                user_id=1, app_user_id=(u1 if i < 2 else u2)["user"]["id"],
                user_answer=answer, is_correct=correct,
                grading_status="graded",
                created_at=base + timedelta(seconds=i),
            ))
        db.commit()
        return q, u1, u2

    def test_question_statistics_fixed_sample(self, db, client, user_headers):
        q, _, _ = self._seed_fixed_sample(db, client, user_headers)
        from app.services.statistics_service import StatisticsService
        stats = StatisticsService(db).question_statistics(q.id)
        assert stats["graded_submission_count"] == 3
        assert stats["correct_submission_count"] == 2
        assert abs(stats["accuracy"] - 2 / 3) < 0.001
        # 首次作答：U1 首次错、U2 首次对 → 1/2
        assert abs(stats["first_attempt_accuracy"] - 0.5) < 0.001
        assert stats["unique_user_count"] == 2

    def test_user_statistics(self, db, client, user_headers):
        _, u1, _ = self._seed_fixed_sample(db, client, user_headers)
        from app.services.statistics_service import StatisticsService
        stats = StatisticsService(db).user_statistics(u1["user"]["id"])
        summary = stats["answer_summary"]
        assert summary["graded_submission_count"] == 2
        assert summary["correct_submission_count"] == 1
        assert abs(summary["accuracy"] - 0.5) < 0.001
        assert abs(summary["first_attempt_accuracy"] - 0.0) < 0.001  # 首次答错

    def test_insufficient_samples_flag(self, db, client, user_headers):
        q, _, _ = self._seed_fixed_sample(db, client, user_headers)
        from app.services.statistics_service import StatisticsService
        stats = StatisticsService(db).question_statistics(q.id)
        assert stats["display_status"] == "insufficient_samples"  # 3 < 20
        assert stats["sample_threshold"] == 20

    def test_my_statistics_endpoint(self, client, user_headers):
        resp = client.get(f"{API}/users/me/statistics", headers=user_headers)
        data = resp.json()["data"]
        assert "answer_summary" in data
        assert "practice_summary" in data

    def test_question_statistics_endpoint_dual_auth(self, db, client, user_headers, auth_headers, seed_questions):
        q = seed_questions[0]
        r_user = client.get(f"{API}/questions/{q.id}/statistics", headers=user_headers)
        assert r_user.json()["code"] == 0
        r_admin = client.get(f"{API}/questions/{q.id}/statistics", headers=auth_headers)
        assert r_admin.json()["code"] == 0
        data = r_admin.json()["data"]
        assert set(data.keys()) >= {
            "accuracy", "first_attempt_accuracy", "unique_user_count", "display_status",
        }

    def test_legacy_statistics_endpoint_shape(self, db, client, auth_headers, seed_questions):
        q = seed_questions[0]
        resp = client.get(f"{API}/answers/statistics/{q.id}", headers=auth_headers)
        data = resp.json()["data"]
        assert set(data.keys()) >= {
            "graded_attempt_count", "correct_attempt_count", "attempt_accuracy",
            "first_attempt_user_count", "first_attempt_correct_count",
            "first_attempt_accuracy", "unique_user_count", "is_sample_sufficient",
        }

    def test_answer_history_pagination(self, client, user_headers, paper_session):
        resp = client.get(f"{API}/answers/history", headers=user_headers)
        body = resp.json()
        assert body["code"] == 0
        assert "items" in body["data"]
        assert "total" in body["data"]
