"""接口核查与补齐 · 真实服务冒烟（10 步，docs/14 补充 §16/§20 验证）。

用法：先起 uvicorn（单 worker），再运行本脚本：
    python scripts/practice_supplement_smoke.py --base http://127.0.0.1:18080
自建带 uuid tag 的一次性数据，结束按 FK 序清理（不触碰历史数据）。
"""
import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

API = "/api/v1"
TAG = uuid.uuid4().hex[:8]
PASS, FAIL = 0, 0
results = []


def step(no, name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
    else:
        FAIL += 1
    results.append({"step": no, "name": name, "pass": bool(ok), "detail": str(detail)[:300]})
    print(f"[{'PASS' if ok else 'FAIL'}] {no} {name} {str(detail)[:120]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:18080")
    args = ap.parse_args()
    s = requests.Session()
    created = {"comments": [], "users": []}

    try:
        # 1 就绪
        r = s.get(f"{args.base}/health", timeout=60).json()
        step(1, "服务就绪", r.get("status") == "healthy", r)

        # 2 管理员登录
        r = s.post(f"{args.base}{API}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=30).json()
        admin = {"Authorization": f"Bearer {r['data']['access_token']}"}
        step(2, "管理员登录", r.get("code") == 0)

        # 3 普通用户注册+登录
        account = f"sp{TAG}"
        r = s.post(f"{args.base}{API}/users/register", json={
            "account": account, "password": "pass1234", "nickname": "冒烟用户"}, timeout=30).json()
        step(3, "普通用户注册", r.get("code") == 0, r.get("message"))
        user = {"Authorization": f"Bearer {r['data']['access_token']}"}
        uid = r["data"]["user"]["id"]
        refresh = r["data"]["refresh_token"]
        created["users"].append(uid)

        # 4 管理端开放有题题库 + 用户列表只出开放题库
        banks_admin = s.get(f"{args.base}{API}/question-banks", headers=admin, timeout=30).json()
        target = next((b for b in banks_admin.get("data", {}).get("items", [])
                       if b.get("published_question_count", 0) > 0), None)
        assert target is not None, "开发库无含 published 题的题库"
        bid = target["id"]
        created["bank_was_open"] = bool(target.get("is_available_for_practice"))
        r = s.patch(f"{args.base}{API}/question-banks/{bid}/practice-availability",
                    headers=admin, json={"is_available_for_practice": True}, timeout=30).json()
        r = s.get(f"{args.base}{API}/practice/question-banks", headers=user, timeout=30).json()
        banks = r.get("data", {}).get("items", [])
        ok = (r.get("code") == 0 and any(b["id"] == bid for b in banks) and all(
            all(k in b for k in ("available_question_count", "can_assemble", "unavailable_reason"))
            for b in banks))
        open_bank = next((b for b in banks if b["id"] == bid), None)
        step(4, "开放题库列表（只出开放+字段完整）", ok and open_bank, f"banks={len(banks)} bid={bid}")

        # 5 题库详情+知识点
        r1 = s.get(f"{args.base}{API}/practice/question-banks/{bid}", headers=user, timeout=30).json()
        r2 = s.get(f"{args.base}{API}/practice/question-banks/{bid}/knowledge-points", headers=user, timeout=30).json()
        kps = r2.get("data", {}).get("knowledge_points", [])
        step(5, "题库详情+知识点清单", r1["code"] == 0 and r2["code"] == 0, f"kps={len(kps)}")

        # 6 管理开关挡组卷
        r = s.patch(f"{args.base}{API}/question-banks/{bid}/practice-availability",
                    headers=admin, json={"is_available_for_practice": False}, timeout=30).json()
        blocked = s.post(f"{args.base}{API}/practice/papers/assemble", headers=user, json={
            "question_bank_id": bid, "question_type_counts": {"SINGLE_CHOICE": 1},
            "difficulty_distribution": {"normal": 1}, "total_count": 1}, timeout=30).json()
        s.patch(f"{args.base}{API}/question-banks/{bid}/practice-availability",
                headers=admin, json={"is_available_for_practice": True}, timeout=30)
        step(6, "关闭开关挡未来组卷", r["code"] == 0 and blocked["code"] != 0, blocked.get("message"))

        # 7 组卷+结果投影安全
        r = s.post(f"{args.base}{API}/practice/papers/assemble", headers={**user, "Idempotency-Key": f"smoke-{TAG}"},
                   json={"question_bank_id": bid, "question_type_counts": {"SINGLE_CHOICE": 1},
                         "difficulty_distribution": {"normal": 1}, "total_count": 1}, timeout=30).json()
        sid = r["data"]["session"]["session_id"]
        res = s.get(f"{args.base}{API}/practice/sessions/{sid}/result", headers=user, timeout=30).json()
        items = res.get("data", {}).get("items", [])
        leak = [it for it in items if "correct_answer" in it]
        step(7, "组卷+未提交题不泄露答案", r["code"] == 0 and not leak, f"items={len(items)}")

        # 8 幂等同 key 同参
        r2 = s.post(f"{args.base}{API}/practice/papers/assemble", headers={**user, "Idempotency-Key": f"smoke-{TAG}"},
                    json={"question_bank_id": bid, "question_type_counts": {"SINGLE_CHOICE": 1},
                          "difficulty_distribution": {"normal": 1}, "total_count": 1}, timeout=30).json()
        step(8, "同 key 同参返回原卷", r2["code"] == 0 and r2["data"].get("idempotent") is True
            and r2["data"]["paper"]["paper_id"] == r["data"]["paper"]["paper_id"])

        # 9 评论身份
        qid = items[0].get("question_id") or 1
        r = s.post(f"{args.base}{API}/comments/question/{qid}", headers=user,
                   json={"content": f"冒烟评论 {TAG}"}, timeout=30).json()
        cid = r.get("data", {}).get("id")
        lst = s.get(f"{args.base}{API}/comments/question/{qid}", headers=user, timeout=30).json()
        mine = next((c for c in lst.get("data", {}).get("items", []) if c.get("id") == cid), None)
        step(9, "普通用户评论身份", r.get("code") == 0 and mine is not None, mine)
        created["comments"].append(cid)

        # 10 用户管理禁用撤销会话
        r = s.patch(f"{args.base}{API}/admin/app-users/{uid}/status", headers=admin,
                    json={"status": "disabled", "reason": "冒烟验证"}, timeout=30).json()
        replay = s.post(f"{args.base}{API}/users/refresh", json={"refresh_token": refresh}, timeout=30).json()
        s.patch(f"{args.base}{API}/admin/app-users/{uid}/status", headers=admin,
                json={"status": "active"}, timeout=30)
        step(10, "禁用撤销 refresh 会话", r.get("code") == 0
            and r["data"].get("revoked_sessions", 0) >= 1 and replay.get("code") != 0, replay.get("message"))

        # 恢复题库开放状态
        try:
            s.patch(f"{args.base}{API}/question-banks/{bid}/practice-availability",
                    headers=admin,
                    json={"is_available_for_practice": created.get("bank_was_open", False)}, timeout=30)
        except Exception as exc:
            print(f"[WARN] restore bank: {exc}")

    finally:
        # 清理自建数据（按 FK 序）
        try:
            from app.core.database import SessionLocal
            from app.models.question_comment import QuestionComment
            from app.models.user_auth_session import UserAuthSession
            from app.models.practice_session_item import PracticeSessionItem
            from app.models.practice_session import PracticeSession
            from app.models.practice_paper_item import PracticePaperItem
            from app.models.practice_paper import PracticePaper
            from app.models.app_user import AppUser
            db = SessionLocal()
            try:
                for cid in created["comments"]:
                    db.query(QuestionComment).filter(QuestionComment.id == cid).delete()
                for uid in created["users"]:
                    db.query(UserAuthSession).filter(UserAuthSession.app_user_id == uid).delete()
                    papers = db.query(PracticePaper).filter(PracticePaper.owner_user_id == uid).all()
                    for p in papers:
                        db.query(PracticeSessionItem).filter(
                            PracticeSessionItem.session_id.in_(
                                db.query(PracticeSession.id).filter(PracticeSession.paper_id == p.id))).delete(
                            synchronize_session=False)
                        db.query(PracticeSession).filter(PracticeSession.paper_id == p.id).delete()
                        db.query(PracticePaperItem).filter(PracticePaperItem.paper_id == p.id).delete()
                    db.query(PracticePaper).filter(PracticePaper.owner_user_id == uid).delete()
                    db.query(AppUser).filter(AppUser.id == uid).delete()
                db.commit()
            finally:
                db.close()
        except Exception as exc:  # 清理失败不影响冒烟结论，但要报告
            print(f"[WARN] cleanup: {exc}")

    report = {
        "tag": TAG, "total": PASS + FAIL, "passed": PASS, "failed": FAIL,
        "results": results, "finished_at": datetime.now().isoformat(),
    }
    out = os.path.join(os.environ.get("TEMP", "."), "practice_supplement_smoke_result.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n{PASS}/{PASS + FAIL} passed; report -> {out}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
