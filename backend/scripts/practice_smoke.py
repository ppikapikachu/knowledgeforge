"""docs/14 真实 API 冒烟：普通用户体系 / 组卷快照 / 练习会话 / 判分幂等 / 统计。

    用法：python scripts/practice_smoke.py [--base http://127.0.0.1:18080]

    前置：后端服务已启动（单 worker）；MySQL 可用。
    种子：直接写库造 5 道 published 题目（uuid 标记），结束后按依赖顺序清理。
    流程：注册→登录→me→refresh 轮换→组卷→试卷列表/详情（不含答案泄露）→
          草稿/标记/进度→提交判分（对/错/漏选/简答）→幂等重放→答题记录→
          会话结果→完成（幂等）→完成后拒提交→再练→个人统计→题目统计→清理。
"""

import argparse
import sys
import uuid
from datetime import datetime

import httpx

TAG = f"smoke-practice-{uuid.uuid4().hex[:8]}"
RESULTS = []


def step(no, name, fn):
    try:
        detail = fn()
        RESULTS.append({"no": no, "name": name, "ok": True, "detail": detail})
        print(f"[PASS] {no} {name} — {detail}")
        return True
    except Exception as exc:  # noqa: BLE001
        RESULTS.append({"no": no, "name": name, "ok": False, "detail": str(exc)})
        print(f"[FAIL] {no} {name} — {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:18080")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    # ---- DB 种子 ----
    sys.path.insert(0, ".")
    from app.core.database import SessionLocal
    from app.models.knowledge import Knowledge
    from app.models.knowledge_base import KnowledgeBase
    from app.models.question import Question
    from app.models.question_knowledge import QuestionKnowledge
    from app.models.question_option import QuestionOption

    db = SessionLocal()
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.code == "uncategorized").first()
    knowledge = Knowledge(
        knowledge_base_id=kb.id, name=f"{TAG}-知识点",
        difficulty=1, status=1, source_type="MANUAL", content=f"{TAG} 知识内容",
    )
    db.add(knowledge)
    db.flush()
    seeded = []
    plan = [
        ("SINGLE_CHOICE", 1, "A", [("A", "甲", 1), ("B", "乙", 0)]),
        ("SINGLE_CHOICE", 2, "A", [("A", "甲", 1), ("B", "乙", 0)]),
        ("MULTIPLE_CHOICE", 3, "AB", [("A", "甲", 1), ("B", "乙", 1), ("C", "丙", 0)]),
        ("TRUE_FALSE", 1, "TRUE", []),
        ("SHORT_ANSWER", 2, "参考答案", []),
    ]
    for q_type, diff, answer, options in plan:
        q = Question(
            question_type=q_type, content=f"{TAG} 题目 {q_type}-{diff}",
            answer=answer, analysis="解析", explanation=f"{TAG} 解析",
            difficulty=diff, status="published", question_bank_id=kb.id,
            source_type="MANUAL",
        )
        db.add(q)
        db.flush()
        for idx, (key, content, ok) in enumerate(options, start=1):
            db.add(QuestionOption(
                question_id=q.id, option_key=key, option_content=content,
                is_correct=ok, sort_order=idx,
            ))
        db.add(QuestionKnowledge(question_id=q.id, knowledge_id=knowledge.id))
        seeded.append(q)
    db.commit()
    q_ids = [q.id for q in seeded]

    client = httpx.Client(base_url=base, timeout=60)
    state = {}

    def _check(resp, expect_code=0):
        body = resp.json()
        if body.get("code") != expect_code:
            raise AssertionError(f"code={body.get('code')} message={body.get('message')} (期望 {expect_code})")
        return body

    def s1_register():
        account = f"sp{TAG.split('-')[-1]}"  # 含 uuid 段，避免跨次运行账号冲突
        body = _check(client.post("/api/v1/users/register", json={
            "account": account, "password": "pass1234", "nickname": "冒烟用户",
        }))
        state["account"] = account
        state["tokens"] = body["data"]
        state["user_id"] = body["data"]["user"]["id"]
        return f"account={account} uid={state['user_id']}"

    def s2_login():
        body = _check(client.post("/api/v1/users/login", json={
            "account": state["account"], "password": "pass1234",
        }))
        state["tokens"] = body["data"]
        return "令牌对已获取"

    def s3_me():
        body = _check(client.get("/api/v1/users/me", headers=state["auth"]))
        assert body["data"]["account"] == state["account"]
        return "身份校验通过"

    def s4_refresh():
        old = state["tokens"]["refresh_token"]
        body = _check(client.post("/api/v1/users/refresh", json={"refresh_token": old}))
        new = body["data"]["refresh_token"]
        assert new != old
        replay = client.post("/api/v1/users/refresh", json={"refresh_token": old}).json()
        assert replay["code"] == 40101, f"旧票重放应 40101，实际 {replay['code']}"
        state["tokens"] = body["data"]
        state["auth"] = {"Authorization": f"Bearer {body['data']['access_token']}"}
        return "轮换成功且旧票已失效"

    def s5_assemble():
        body = _check(client.post("/api/v1/practice/papers/assemble", json={
            "title": f"{TAG} 试卷",
            "knowledge_ids": [knowledge.id],  # 只用种子题目，隔离开发库其他 published 题
            "question_type_counts": {"SINGLE_CHOICE": 2, "MULTIPLE_CHOICE": 1, "TRUE_FALSE": 1, "SHORT_ANSWER": 1},
            "difficulty_distribution": {"easy": 2, "normal": 2, "hard": 1},
            "total_count": 5,
        }, headers={**state["auth"], "Idempotency-Key": f"{TAG}-idem"}))
        data = body["data"]
        state["paper"] = data["paper"]
        state["session"] = data["session"]
        assert data["paper"]["question_count"] == 5
        assert data["session"]["status"] == "in_progress"
        return f"paper={data['paper']['paper_id']} session={data['session']['session_id']}"

    def s6_papers_no_answer_leak():
        body = _check(client.get(f"/api/v1/practice/papers/{state['paper']['paper_id']}", headers=state["auth"]))
        for item in body["data"]["items"]:
            assert "correct_answer" not in item and "explanation" not in item
            for opt in item["options"]:
                assert "is_correct" not in opt
        lst = _check(client.get("/api/v1/practice/papers", headers=state["auth"]))
        assert lst["data"]["total"] >= 1
        return "5 题投影无答案泄露"

    def s7_draft_mark_progress():
        sid = state["session"]["session_id"]
        items = _check(client.get(f"/api/v1/practice/sessions/{sid}", headers=state["auth"]))["data"]["items"]
        state["items"] = items
        it = items[0]
        _check(client.put(f"/api/v1/practice/sessions/{sid}/items/{it['paper_item_id']}/draft",
                          headers=state["auth"], json={"answer": ["A"]}))
        _check(client.patch(f"/api/v1/practice/sessions/{sid}/items/{it['paper_item_id']}/mark",
                            headers=state["auth"], json={"is_marked": True}))
        _check(client.patch(f"/api/v1/practice/sessions/{sid}/progress",
                            headers=state["auth"], json={"current_item_order": 2}))
        return "草稿/标记/进度均成功"

    def s8_submit_grading():
        sid = state["session"]["session_id"]
        by_type = {}
        for it in state["items"]:
            by_type.setdefault(it["question_type"], it)
        out = []
        r = _check(client.post(f"/api/v1/practice/sessions/{sid}/items/{by_type['SINGLE_CHOICE']['paper_item_id']}/submit",
                               headers=state["auth"],
                               json={"answer": ["A"], "idempotency_key": f"{TAG}-k1", "time_spent_ms": 1000}))
        state["k1_item"] = by_type["SINGLE_CHOICE"]["paper_item_id"]
        assert r["data"]["is_correct"] is True and r["data"]["correct_answer"]
        out.append("单选对")
        r = _check(client.post(f"/api/v1/practice/sessions/{sid}/items/{by_type['MULTIPLE_CHOICE']['paper_item_id']}/submit",
                               headers=state["auth"], json={"answer": ["A"], "idempotency_key": f"{TAG}-k2"}))
        assert r["data"]["is_correct"] is False  # 漏选
        out.append("多选漏选=错")
        r = _check(client.post(f"/api/v1/practice/sessions/{sid}/items/{by_type['TRUE_FALSE']['paper_item_id']}/submit",
                               headers=state["auth"], json={"answer": ["true"], "idempotency_key": f"{TAG}-k3"}))
        assert r["data"]["is_correct"] is True
        out.append("判断归一对")
        r = _check(client.post(f"/api/v1/practice/sessions/{sid}/items/{by_type['SHORT_ANSWER']['paper_item_id']}/submit",
                               headers=state["auth"], json={"answer": ["我的作答"], "idempotency_key": f"{TAG}-k4"}))
        assert r["data"]["grading_status"] == "ungraded" and r["data"]["is_correct"] is None
        out.append("简答 ungraded")
        return "；".join(out)

    def s9_idempotent_replay():
        sid = state["session"]["session_id"]
        it = state["k1_item"]  # 必须与 step8 k1 相同题目
        payload = {"answer": ["A"], "idempotency_key": f"{TAG}-k1"}
        body = _check(client.post(f"/api/v1/practice/sessions/{sid}/items/{it}/submit",
                                  headers=state["auth"], json=payload))
        assert body["data"]["idempotent"] is True
        conflict = client.post(f"/api/v1/practice/sessions/{sid}/items/{it}/submit",
                               headers=state["auth"],
                               json={"answer": ["B"], "idempotency_key": f"{TAG}-k1"}).json()
        assert conflict["code"] == 40001, f"同 key 异 payload 应冲突，实际 {conflict['code']}"
        return "重放返回原记录且异 payload 冲突"

    def s10_answers_and_result():
        sid = state["session"]["session_id"]
        ans = _check(client.get(f"/api/v1/practice/sessions/{sid}/answers", headers=state["auth"]))
        assert len(ans["data"]["answers"]) == 4
        res = _check(client.get(f"/api/v1/practice/sessions/{sid}/result", headers=state["auth"]))
        summary = res["data"]["summary"]
        assert summary["answered_count"] == 4 and summary["correct_count"] == 2
        return f"答题 4 条，正确 {summary['correct_count']}，未答保留 {summary['total_count'] - summary['answered_count']}"

    def s11_complete_and_repractice():
        sid = state["session"]["session_id"]
        done = _check(client.post(f"/api/v1/practice/sessions/{sid}/complete", headers=state["auth"]))
        assert done["data"]["status"] == "completed"
        again = _check(client.post(f"/api/v1/practice/sessions/{sid}/complete", headers=state["auth"]))
        assert again["data"]["status"] == "completed"  # 幂等
        rejected = client.post(f"/api/v1/practice/sessions/{sid}/items/{state['items'][0]['paper_item_id']}/submit",
                               headers=state["auth"],
                               json={"answer": ["A"], "idempotency_key": f"{TAG}-k9"}).json()
        assert rejected["code"] == 40001
        new = _check(client.post(f"/api/v1/practice/papers/{state['paper']['paper_id']}/sessions",
                                 headers=state["auth"]))
        assert new["data"]["session_id"] != sid
        return f"完成幂等；完成后拒提交；再练新会话 {new['data']['session_id']}"

    def s12_statistics():
        me = _check(client.get("/api/v1/users/me/statistics", headers=state["auth"]))
        summary = me["data"]["answer_summary"]
        assert summary["graded_submission_count"] == 3  # 单选+多选+判断
        qid = state["items"][0]["paper_item_id"]
        sid = state["session"]["session_id"]
        ans = _check(client.get(f"/api/v1/practice/sessions/{sid}/answers", headers=state["auth"]))["data"]["answers"]
        real_qid = ans[0]["question_id"]
        qs = _check(client.get(f"/api/v1/questions/{real_qid}/statistics", headers=state["auth"]))
        assert set(qs["data"].keys()) >= {"accuracy", "first_attempt_accuracy", "unique_user_count", "display_status"}
        return f"个人 graded={summary['graded_submission_count']}；题目统计字段齐全"

    steps = [
        ("1", "注册普通用户", s1_register),
        ("2", "登录", s2_login),
        ("3", "me 身份校验", s3_me),
        ("4", "refresh 轮换+旧票失效", s4_refresh),
        ("5", "组卷快照 5 题", s5_assemble),
        ("6", "试卷详情无答案泄露", s6_papers_no_answer_leak),
        ("7", "草稿/标记/进度", s7_draft_mark_progress),
        ("8", "提交判分四题型", s8_submit_grading),
        ("9", "幂等重放与冲突", s9_idempotent_replay),
        ("10", "答题记录与会话结果", s10_answers_and_result),
        ("11", "完成幂等+拒提交+再练", s11_complete_and_repractice),
        ("12", "个人与题目统计", s12_statistics),
    ]

    passed = failed = 0
    for no, name, fn in steps:
        ok = step(no, name, fn)
        if "access_token" in state.get("tokens", {}):
            state["auth"] = {"Authorization": f"Bearer {state['tokens']['access_token']}"}
        passed += ok
        failed += (not ok)

    # ---- 清理（按 FK 依赖顺序）----
    try:
        from app.models.practice_paper import PracticePaper
        from app.models.practice_paper_item import PracticePaperItem
        from app.models.practice_session import PracticeSession
        from app.models.practice_session_item import PracticeSessionItem
        from app.models.question_answer_record import QuestionAnswerRecord

        paper_id = state.get("paper", {}).get("paper_id")
        if paper_id:
            session_ids = [s.id for s in db.query(PracticeSession).filter(PracticeSession.paper_id == paper_id).all()]
            db.query(PracticeSessionItem).filter(PracticeSessionItem.session_id.in_(session_ids)).delete(synchronize_session=False)
            db.query(QuestionAnswerRecord).filter(QuestionAnswerRecord.practice_paper_id == paper_id).delete(synchronize_session=False)
            db.query(PracticeSession).filter(PracticeSession.paper_id == paper_id).delete(synchronize_session=False)
            db.query(PracticePaperItem).filter(PracticePaperItem.paper_id == paper_id).delete(synchronize_session=False)
            db.query(PracticePaper).filter(PracticePaper.id == paper_id).delete(synchronize_session=False)
        db.query(QuestionAnswerRecord).filter(QuestionAnswerRecord.question_id.in_(q_ids)).delete(synchronize_session=False)
        db.query(QuestionKnowledge).filter(QuestionKnowledge.question_id.in_(q_ids)).delete(synchronize_session=False)
        db.query(QuestionOption).filter(QuestionOption.question_id.in_(q_ids)).delete(synchronize_session=False)
        db.query(Question).filter(Question.id.in_(q_ids)).delete(synchronize_session=False)
        db.query(Knowledge).filter(Knowledge.id == knowledge.id).delete(synchronize_session=False)
        db.commit()
        print("[PASS] 清理完成")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[WARN] 清理失败（可手工删除 TAG={TAG} 数据）: {exc}")
    finally:
        db.close()

    print(f"\n结果：{passed} 通过 / {failed} 失败")
    import json
    import os
    out_path = os.path.join(os.environ.get("TEMP", "."), "practice_smoke_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"tag": TAG, "passed": passed, "failed": failed, "steps": RESULTS}, f, ensure_ascii=False, indent=2)
    print(f"报告：{out_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
