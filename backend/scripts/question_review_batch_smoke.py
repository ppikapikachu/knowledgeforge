# -*- coding: utf-8 -*-
"""批量 AI 审核真实冒烟（§11.4，10 步，仅验收用）。

前提：
  1. 服务已启动（单 worker），且启动时环境变量 QUESTION_AI_REVIEW_ENABLED=true
     （.env 默认 false，冒烟通过进程环境变量覆盖，不修改 .env）。
  2. 真实 MiMo API Key 可用（LLM_API_KEY，本脚本不打印、不落盘）。

运行（backend 目录）：
  python scripts/question_review_batch_smoke.py [--base http://127.0.0.1:8000]

脚本自行创建一次性题目数据并在结束后清理（含审核记录/批次/题目）。
报告 JSON 写入 %TEMP%\\question_review_batch_smoke_result.json。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:8000"
RESULTS = []
CLEANUP_IDS: list[int] = []


def step(no, name, ok, detail=""):
    RESULTS.append({"step": str(no), "name": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)[:400]})
    print(f"[{no}] {'PASS' if ok else 'FAIL'} {name} :: {str(detail)[:300]}")


def api(method, path, token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE)
    args = ap.parse_args()
    BASE = args.base.rstrip("/")

    # ---- 预备：经 ORM 创建一次性题目数据（3 可审 + 1 简答 + 1 已发布）----
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.core.database import SessionLocal
    from app.models.question import Question
    from app.models.question_bank import QuestionBank
    from app.models.question_knowledge import QuestionKnowledge
    from app.models.question_review_batch import QuestionReviewBatch, QuestionReviewBatchItem
    from app.models.question_review_record import QuestionReviewRecord

    tag = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        bank_id = db.query(QuestionBank.id).filter(QuestionBank.code == "uncategorized").scalar()
        kid = db.query(QuestionKnowledge.knowledge_id).first()
        kid = kid[0] if kid else 1
        qids = []
        specs = [
            ("SINGLE_CHOICE", "pending_review", f"冒烟单选题：Java 中 HashMap 的默认初始容量是？[{tag}]"),
            ("MULTIPLE_CHOICE", "pending_review", f"冒烟多选题：以下哪些属于 Java 集合框架？[{tag}]"),
            ("TRUE_FALSE", "pending_review", f"冒烟判断题：Python 是解释型语言。[{tag}]"),
            ("SHORT_ANSWER", "pending_review", f"冒烟简答题：请简述 REST 风格约束。[{tag}]"),
            ("SINGLE_CHOICE", "published", f"冒烟已发布题：不应进入审核。[{tag}]"),
        ]
        for qt, st, content in specs:
            q = Question(
                question_type=qt, content=content, answer="A", analysis="冒烟数据",
                difficulty=2, status=st, source_type="AI", question_bank_id=bank_id,
            )
            db.add(q)
            db.flush()
            CLEANUP_IDS.append(q.id)
            qids.append(q.id)
        db.commit()
    finally:
        db.close()
    eligible = qids[:3]
    q_short, q_published = qids[3], qids[4]

    # 1. 登录
    st, body = api("POST", "/api/v1/auth/login", body={"username": "admin", "password": "admin123"})
    token = (body.get("data") or {}).get("access_token")
    step(1, "管理员登录", st == 200 and body.get("code") == 0 and token, f"http={st} code={body.get('code')}")
    if not token:
        finish()
        return

    # 2. 服务与去重索引就绪
    st, body = api("GET", "/api/v1/question-dedup/status", token=token)
    d = body.get("data") or {}
    step(2, "去重索引 status（审核依赖）", st == 200 and d.get("status") == "ready", f"http={st} status={d.get('status')}")

    # 3. 预检（不建任务）
    st, body = api("POST", "/api/v1/question-reviews/batches/preview", token=token,
                   body={"question_ids": qids})
    d = body.get("data") or {}
    ok = (st == 200 and body.get("code") == 0 and d.get("requested") == 5 and d.get("eligible") == 3
          and d.get("ineligible") == 2 and set(d.get("eligible_question_ids") or []) == set(eligible))
    reason_map = {i.get("question_id"): i.get("reason_code") for i in (d.get("items") or [])}
    ok = ok and reason_map.get(q_short) == "unsupported_question_type" and reason_map.get(q_published) == "question_not_pending"
    step(3, "preview 预检（3 可审/2 拦截，零 LLM）", ok, f"http={st} {d.get('eligible')}/{d.get('ineligible')} reasons={reason_map}")

    # 4. 创建批次（重新校验+认领）
    st, body = api("POST", "/api/v1/question-reviews/batches", token=token, body={"question_ids": qids})
    d = body.get("data") or {}
    batch_id = d.get("batch_id")
    ok = (st == 200 and body.get("code") == 0 and batch_id and d.get("requested") == 5
          and d.get("accepted") == 3 and d.get("skipped") == 2)
    step(4, "创建批次（accepted=3 skipped=2）", ok, f"http={st} batch_id={batch_id} {d}")
    if not batch_id:
        finish()
        return

    # 5. 轮询直至终态（后台线程执行真实 LLM 审核）
    deadline = time.time() + 300
    detail, terminal = {}, False
    while time.time() < deadline:
        st, body = api("GET", f"/api/v1/question-reviews/batches/{batch_id}", token=token)
        detail = body.get("data") or {}
        if detail.get("status") in ("completed", "partial", "failed"):
            terminal = True
            break
        time.sleep(3)
    step(5, "批次执行至终态（含真实 LLM）", terminal,
         f"status={detail.get('status')} progress={detail.get('progress')}")

    # 6. item 明细：可审项 completed 且有审核记录；跳过项有原因且无决策
    items = detail.get("items") or []
    done = [i for i in items if i.get("question_id") in eligible]
    skipped = [i for i in items if i.get("question_id") in (q_short, q_published)]
    ok = (all(i.get("status") == "completed" and i.get("review_record_id") for i in done)
          and all(i.get("review_decision") in ("auto_approve", "auto_reject", "manual_review") for i in done)
          and all(i.get("status") == "skipped" and i.get("skip_reason") and i.get("review_decision") is None for i in skipped))
    step(6, "item 明细契约（跳过项不伪造决策）", ok, str([(i.get("question_id"), i.get("status"), i.get("review_decision")) for i in items]))

    # 7. 审核记录按 batch_id 过滤
    st, body = api("GET", f"/api/v1/question-reviews/records?batch_id={batch_id}", token=token)
    d = body.get("data") or {}
    recs = d.get("items") or []
    ok = (st == 200 and body.get("code") == 0 and len(recs) == 3
          and all(r.get("batch_id") == batch_id and r.get("trigger_source") == "manual_batch" for r in recs))
    step(7, "records?batch_id= 过滤（trigger_source=manual_batch）", ok, f"total={d.get('total')}")

    # 8. AND 语义（batch_id + trigger_source 叠加）
    st, body = api("GET", f"/api/v1/question-reviews/records?batch_id={batch_id}&trigger_source=manual_batch", token=token)
    d2 = body.get("data") or {}
    step(8, "records 组合筛选 AND 语义", st == 200 and d2.get("total") == d.get("total"), f"total={d2.get('total')}")
    st, body = api("GET", f"/api/v1/question-reviews/records?batch_id={batch_id}&trigger_source=generation_task", token=token)
    step(8.5, "records 反向筛选为空", st == 200 and (body.get("data") or {}).get("total") == 0, f"total={(body.get('data') or {}).get('total')}")

    # 9. 重复提交同题（终态后认领释放）：再审一轮或被状态门槛拦截，不得同轮重复
    st, body = api("POST", "/api/v1/question-reviews/batches", token=token, body={"question_ids": eligible})
    d = body.get("data") or {}
    ok = st == 200 and body.get("code") == 0
    rounds = {}
    if ok:
        bid2 = d.get("batch_id")
        deadline = time.time() + 300
        while time.time() < deadline:
            st2, b2 = api("GET", f"/api/v1/question-reviews/batches/{bid2}", token=token)
            dd = b2.get("data") or {}
            if dd.get("status") in ("completed", "partial", "failed"):
                break
            time.sleep(3)
        db = SessionLocal()
        try:
            rows = db.query(QuestionReviewRecord).filter(
                QuestionReviewRecord.question_id.in_(eligible)).order_by(
                QuestionReviewRecord.question_id, QuestionReviewRecord.review_round).all()
            for r in rows:
                rounds.setdefault(r.question_id, []).append(r.review_round)
            unique = all(len(v) == len(set(v)) for v in rounds.values())
            ok = ok and unique
        finally:
            db.close()
    step(9, "重复提交同题（释放后新轮次/状态拦截，无同轮重复）", ok, f"batch2={d} rounds={rounds}")

    # 10. 统计一致性：批次计数 = item 派生（批次字段为 *_count 列名）
    st, body = api("GET", f"/api/v1/question-reviews/batches/{batch_id}", token=token)
    d = body.get("data") or {}
    items = d.get("items") or []
    n_completed = sum(1 for i in items if i.get("status") == "completed")
    n_failed = sum(1 for i in items if i.get("status") == "failed")
    n_skipped = sum(1 for i in items if i.get("status") == "skipped")
    prog = d.get("progress") or {}
    ok = (d.get("processed_count") == n_completed and d.get("failed_count") == n_failed
          and d.get("skipped_count") == n_skipped and d.get("total_count") == len(items)
          and d.get("total_count") == d.get("accepted_count") + d.get("skipped_count")
          and prog.get("processed") == n_completed)
    step(10, "批次统计与 item 派生一致", ok,
         f"total={d.get('total_count')} processed={d.get('processed_count')} failed={d.get('failed_count')} skipped={d.get('skipped_count')} progress={prog}")

    finish(db_models=(SessionLocal, Question, QuestionReviewBatch, QuestionReviewBatchItem, QuestionReviewRecord))


def finish(db_models=None):
    # 清理一次性冒烟数据（审核记录→批次→题目；均为本脚本自建，不触碰历史数据）
    if db_models:
        SessionLocal, Question, QuestionReviewBatch, QuestionReviewBatchItem, QuestionReviewRecord = db_models
        db = SessionLocal()
        try:
            db.query(QuestionReviewRecord).filter(QuestionReviewRecord.question_id.in_(CLEANUP_IDS)).delete(synchronize_session=False)
            batch_ids = [r[0] for r in db.query(QuestionReviewBatch.id).all()]
            db.query(QuestionReviewBatchItem).filter(QuestionReviewBatchItem.question_id.in_(CLEANUP_IDS)).delete(synchronize_session=False)
            db.query(QuestionReviewBatch).filter(QuestionReviewBatch.id.in_(batch_ids)).delete(synchronize_session=False)
            db.query(Question).filter(Question.id.in_(CLEANUP_IDS)).delete(synchronize_session=False)
            db.commit()
            print(f"[cleanup] 已清理冒烟题目 {CLEANUP_IDS} 与同批审核记录/批次")
        except Exception as exc:
            db.rollback()
            print(f"[cleanup] 清理失败（不影响冒烟结论）: {exc}")
        finally:
            db.close()
    passed = sum(1 for r in RESULTS if r["result"] == "PASS")
    summary = {"total": len(RESULTS), "passed": passed, "failed": len(RESULTS) - passed}
    out = os.path.join(os.environ.get("TEMP", "."), "question_review_batch_smoke_result.json")
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "results": RESULTS}, f, ensure_ascii=False, indent=2)
        print(f"报告 JSON: {out}")
    except Exception as exc:
        print(f"报告写入失败: {exc}")
    print(f"SMOKE SUMMARY: {summary}")
    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
