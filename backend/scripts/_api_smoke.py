# -*- coding: utf-8 -*-
"""§6 真实服务冒烟 12 步（一次性脚本，服务地址 http://127.0.0.1:8000）。

步骤：登录 → status → records → 组合筛选 → stats → resolve(dup) → resolve(dist)
→ records 复查 → 重复 resolve 冲突 → rebuild → status 一致 → 前端页面（手工）。
"""
import sys
import time

import requests

BASE = "http://127.0.0.1:8000/api/v1"
REPORT = []


def step(no, name, ok, detail=""):
    REPORT.append((no, name, ok, detail))
    label = f"{no:02d}" if isinstance(no, int) else str(no)
    print(f"[report] step{label} {'PASS' if ok else 'FAIL'} {name}: {detail}")


def main():
    s = requests.Session()

    # ---- 0. 准备冒烟专用管理员（dev 库，不触碰业务数据）----
    sys.path.insert(0, ".")
    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.models.admin import AdminUser

    db = SessionLocal()
    try:
        admin = db.query(AdminUser).filter(AdminUser.username == "smoke_admin").first()
        if admin is None:
            admin = AdminUser(username="smoke_admin", password_hash=hash_password("Smoke#2026"),
                              nickname="冒烟专用", status=1)
            db.add(admin)
            db.commit()
        admin_id = admin.id
    finally:
        db.close()

    # ---- 1. 登录 ----
    r = s.post(f"{BASE}/auth/login", json={"username": "smoke_admin", "password": "Smoke#2026"})
    token = r.json().get("data", {}).get("token") or r.json().get("data", {}).get("access_token")
    step(1, "登录", r.status_code == 200 and bool(token), f"code={r.json().get('code')} token={'ok' if token else 'none'}")
    h = {"Authorization": f"Bearer {token}"}

    # ---- 2. status ----
    r = s.get(f"{BASE}/question-dedup/status", headers=h)
    data = r.json().get("data", {})
    step(2, "status", r.json().get("code") == 0,
         f"status={data.get('status')} reason={data.get('reason')} blocking={data.get('blocking_question_count')} "
         f"stats_total={(data.get('stats') or {}).get('total')}")
    status2 = data

    # ---- 3. records 默认分页 ----
    r = s.get(f"{BASE}/question-dedup/records", headers=h)
    body = r.json()
    items = (body.get("data") or {}).get("items", [])
    step(3, "records 默认分页", body.get("code") == 0 and isinstance(items, list),
         f"code={body.get('code')} total={(body.get('data') or {}).get('total')} keys={len(items[0]) if items else 0}")

    # ---- 4. 组合筛选 ----
    r = s.get(f"{BASE}/question-dedup/records", headers=h,
              params={"decision": "distinct", "needs_manual_review": "false", "page": 1, "page_size": 5})
    body = r.json()
    ok = body.get("code") == 0 and all(it["decision"] == "distinct" and not it["needs_manual_review"]
                                       for it in body.get("data", {}).get("items", []))
    step(4, "组合筛选 AND", ok, f"code={body.get('code')} matched={body.get('data', {}).get('total')}")

    # ---- 5. stats（存在任务）----
    # 找一个有记录的任务或任意任务
    r = s.get(f"{BASE}/question-generation/tasks", headers=h, params={"page": 1, "page_size": 5})
    tasks = (r.json().get("data") or {}).get("items") or []
    if tasks:
        tid = tasks[0]["id"]
        r = s.get(f"{BASE}/question-dedup/stats/{tid}", headers=h)
        step(5, "stats", r.json().get("code") == 0,
             f"task={tid} stats={r.json().get('data')}")
    else:
        step(5, "stats", True, "无任务，跳过（空库场景）")

    # ---- 5b. stats 不存在任务 40401 ----
    r = s.get(f"{BASE}/question-dedup/stats/99999999", headers=h)
    step("5b", "stats 不存在任务 40401", r.json().get("code") == 40401, f"code={r.json().get('code')}")

    # ---- 6/7. resolve：造两条 uncertain 记录后处理 ----
    from app.models.question_dedup_record import QuestionDedupRecord

    db = SessionLocal()
    try:
        rows = []
        for i, concl in enumerate(("duplicate", "distinct")):
            row = QuestionDedupRecord(
                new_content_hash=f"smoke-{int(time.time())}-{i}", new_hash_version="2",
                new_content_snapshot="冒烟样本", new_question_type="SINGLE_CHOICE",
                decision="uncertain", decision_method="vector_and_llm",
                needs_manual_review=True, llm_called=True, llm_decision="uncertain",
            )
            db.add(row)
            rows.append(row)
        db.commit()
        ids = [row.id for row in rows]
    finally:
        db.close()

    r = s.post(f"{BASE}/question-dedup/records/{ids[0]}/resolve", headers=h,
               json={"conclusion": "duplicate", "reason": "冒烟：确为同一考点重复"})
    d = r.json().get("data") or {}
    step(6, "resolve duplicate", r.json().get("code") == 0 and d.get("effective_decision") == "duplicate",
         f"code={r.json().get('code')} effective={d.get('effective_decision')} by={d.get('resolved_by')}")

    r = s.post(f"{BASE}/question-dedup/records/{ids[1]}/resolve", headers=h,
               json={"conclusion": "distinct", "reason": "冒烟：不同角度非重复"})
    d = r.json().get("data") or {}
    step(7, "resolve distinct", r.json().get("code") == 0 and d.get("effective_decision") == "distinct",
         f"code={r.json().get('code')} effective={d.get('effective_decision')}")

    # ---- 8. records 复查（人工结论与证据）----
    r = s.get(f"{BASE}/question-dedup/records", headers=h, params={"page_size": 100})
    items = r.json().get("data", {}).get("items") or []
    found = {it["id"]: it for it in items if it["id"] in ids}
    ok = (found.get(ids[0], {}).get("manual_resolution") == "duplicate"
          and found.get(ids[1], {}).get("manual_resolution") == "distinct"
          and found.get(ids[0], {}).get("decision") == "uncertain")  # 原始自动判定不被覆盖
    step(8, "records 复查", ok, f"r0={found.get(ids[0], {}).get('manual_resolution')}/{found.get(ids[0], {}).get('decision')} "
                               f"r1={found.get(ids[1], {}).get('manual_resolution')}")

    # ---- 9. 重复 resolve 冲突 40901 ----
    r = s.post(f"{BASE}/question-dedup/records/{ids[0]}/resolve", headers=h,
               json={"conclusion": "distinct", "reason": "重复提交"})
    step(9, "重复 resolve 冲突", r.json().get("code") == 40901, f"code={r.json().get('code')} msg={r.json().get('message')}")

    # ---- 10. rebuild ----
    r = s.post(f"{BASE}/question-dedup/index/rebuild", headers=h)
    body = r.json()
    step(10, "rebuild", body.get("code") == 0, f"code={body.get('code')} data={body.get('data')}")

    # ---- 11. status 一致 ----
    r = s.get(f"{BASE}/question-dedup/status", headers=h)
    data = r.json().get("data", {})
    ok = data.get("status") == "ready" and (data.get("stats") or {}).get("failed", 0) == 0
    step(11, "status 一致", ok, f"status={data.get('status')} stats={data.get('stats')}")

    # ---- 12. 前端页面 ----
    step(12, "前端管理页", True, "手工验证项：本脚本无法自动（无前端），报告标注人工确认")

    print("\n[report] SUMMARY")
    fails = [x for x in REPORT if not x[2]]
    print(f"[report] total={len(REPORT)} passed={len(REPORT) - len(fails)} failed={len(fails)}")
    for f in fails:
        print(f"[report] FAIL {f}")


if __name__ == "__main__":
    main()
