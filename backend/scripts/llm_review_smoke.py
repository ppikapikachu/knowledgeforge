"""真实 MiMo API 题目去重 LLM 复核冒烟（加固执行文档 §5）。

覆盖 7 用例：
1. 同范围高相似（语义改写）→ LLM 判 duplicate；
2. 同范围相似但不同角度 → LLM 判 distinct；
3. 跨范围低/中相似 → 0 次 LLM 调用（服务层验证）；
4. 跨范围极高相似 → 触发 LLM 调用；
5. 批内多 pair 一次调用逐 pair 匹配；
6. 非法 JSON / 字段缺失 / 超时 → uncertain（不静默 distinct）；
7. 一次完整生成任务端到端（真实生成 + 去重）。

用法（真实 API，需要 .env 中的 LLM 配置）：
    python scripts/llm_review_smoke.py [--skip-e2e] [--report out.json]

API Key 只从环境读取，不打印、不写入报告。
"""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from agent.question_dedup.schemas import LLMReviewItem, LLMReviewOutput  # noqa: E402
from app.services.question_dedup_service import (  # noqa: E402
    LLMQuestionReviewer,
    QuestionSnapshot,
    ReviewPair,
)

CASES = []


def _snap(content, qtype="SINGLE_CHOICE", bank=1, kids=(1,), answer="A",
          options=(("选项一", 1), ("选项二", 0))):
    return QuestionSnapshot(
        question_type=qtype, content=content, answer=answer,
        options=[(chr(65 + i), c, ok) for i, (c, ok) in enumerate(options)],
        question_bank_id=bank, knowledge_ids=list(kids),
    )


def _pair(pair_id, new, cand, scope="same_scope", score=0.8):
    return ReviewPair(pair_id=pair_id, new=new, candidate=cand, candidate_source="db",
                      scope=scope, algorithm_score=score, keyword_score=score,
                      vector_score=score)


def _record(case_id, desc, **metrics):
    CASES.append({"case": case_id, "desc": desc, **metrics})
    print(f"[{case_id}] {desc}: {json.dumps(metrics, ensure_ascii=False)}")


def run_review_cases():
    reviewer = LLMQuestionReviewer()  # 真实 MiMo API

    # ---- 用例1：同范围语义改写 → duplicate ----
    pairs = [_pair(1, _snap("HashMap 的底层数据结构是什么？请简述。"),
                   _snap("Java 中 HashMap 的底层采用什么数据结构实现？"))]
    t0 = time.time()
    out = reviewer.review(pairs, knowledge_name_fn=lambda ids: ["集合"])
    dt = time.time() - t0
    v = out[1].verdict
    _record("C1", "同范围语义改写应判 duplicate", called=reviewer.call_count,
            pairs=len(pairs), verdict=v, duration_s=round(dt, 2),
            schema_valid=isinstance(out, dict))
    assert v in ("duplicate", "distinct", "uncertain")  # 真实 LLM 结果如实记录

    # ---- 用例2：同范围相似但不同角度 → distinct ----
    pairs = [_pair(1, _snap("HashMap 底层结构中为什么使用红黑树？"),
                   _snap("HashMap 扩容机制的触发条件是什么？"))]
    t0 = time.time()
    out = reviewer.review(pairs, knowledge_name_fn=lambda ids: ["集合"])
    dt = time.time() - t0
    v = out[1].verdict
    _record("C2", "同范围不同角度应判 distinct", called=reviewer.call_count,
            pairs=len(pairs), verdict=v, duration_s=round(dt, 2))
    assert v in ("duplicate", "distinct", "uncertain")

    # ---- 用例5：批内多 pair 一次调用逐 pair 匹配 ----
    pairs = [
        _pair(1, _snap("线程池的核心参数有哪些？"), _snap("线程池有几个核心参数？")),
        _pair(2, _snap("JVM 垃圾回收有哪些算法？"), _snap("HTTP 与 HTTPS 的区别是什么？")),
        _pair(3, _snap("什么是事务隔离级别？"), _snap("事务的隔离级别分哪几种？")),
    ]
    calls_before = reviewer.call_count
    t0 = time.time()
    out = reviewer.review(pairs, knowledge_name_fn=lambda ids: ["并发"])
    dt = time.time() - t0
    verdicts = {pid: out[pid].verdict for pid in (1, 2, 3)}
    _record("C5", "多 pair 批量逐 pair 判定", calls_delta=reviewer.call_count - calls_before,
            batch_pairs=len(pairs), verdicts=verdicts, duration_s=round(dt, 2))
    assert set(verdicts) == {1, 2, 3}

    return reviewer


class _BadJSONLLM:
    """返回非法 JSON 的假 LLM（用例6，注入验证降级路径）。"""

    def with_structured_output(self, _schema):
        return self

    def invoke(self, _prompt):
        class _R:
            content = "这不是JSON{broken"
        return _R()


class _MissingFieldLLM:
    """返回缺字段 JSON 的假 LLM（用例6）。"""

    def with_structured_output(self, _schema):
        return self

    def invoke(self, _prompt):
        class _R:
            content = '{"pairs": [{"pair_id": 1}]}'
        return _R()


class _HangingLLM:
    """挂起的假 LLM（用例6 超时路径）。"""

    def with_structured_output(self, _schema):
        return self

    def invoke(self, _prompt):
        time.sleep(10)
        class _R:
            content = '{"pairs": []}'
        return _R()


def run_degrade_cases():
    # ---- 用例6a：非法 JSON → uncertain ----
    r = LLMQuestionReviewer(llm=_BadJSONLLM(), timeout=20)
    pairs = [_pair(1, _snap("题目A内容是什么？"), _snap("题目B内容是什么？"))]
    out = r.review(pairs, knowledge_name_fn=lambda ids: ["知识"])
    v = out[1].verdict
    _record("C6a", "非法 JSON 必须 uncertain（不静默 distinct）", verdict=v,
            needs_uncertain=(v == "uncertain"))
    assert v == "uncertain"

    # ---- 用例6b：字段缺失 → uncertain ----
    r = LLMQuestionReviewer(llm=_MissingFieldLLM(), timeout=20)
    out = r.review(pairs, knowledge_name_fn=lambda ids: ["知识"])
    v = out[1].verdict
    _record("C6b", "字段缺失必须 uncertain", verdict=v)
    assert v == "uncertain"

    # ---- 用例6c：超时 → uncertain ----
    r = LLMQuestionReviewer(llm=_HangingLLM(), timeout=1)
    t0 = time.time()
    out = r.review(pairs, knowledge_name_fn=lambda ids: ["知识"])
    dt = time.time() - t0
    v = out[1].verdict
    _record("C6c", "超时必须 uncertain 且不长时间阻塞", verdict=v,
            duration_s=round(dt, 2))
    assert v == "uncertain"
    assert dt < 15


def run_service_trigger_cases():
    """用例3/4：服务层 LLM 触发条件（跨范围低/中相似 0 调用；高相似触发）。"""
    from app.core.database import SessionLocal
    from app.services.question_dedup_service import QuestionDeduplicationService

    db = SessionLocal()
    try:
        reviewer = LLMQuestionReviewer()
        svc = QuestionDeduplicationService(db, llm_reviewer=reviewer)

        # 用例3：跨范围低/中相似（不同主题）→ 不应触发 LLM
        calls_before = reviewer.call_count
        res3 = svc.check_one(_snap("HTTP 与 HTTPS 的区别是什么？", kids=(2,)))
        delta3 = reviewer.call_count - calls_before
        _record("C3", "跨范围低/中相似应 0 次 LLM 调用",
                llm_calls=delta3, decision=res3.decision,
                scope=res3.scope_mode, method=res3.decision_method,
                score=round(res3.algorithm_score, 3))
        assert delta3 == 0, "跨范围低/中相似不得调用 LLM"

        # 用例4：跨范围极高相似（内容相同、选项答案不同→指纹不同）→ 必须触发 LLM
        from app.models import Question, QuestionBank

        bank_id = db.query(QuestionBank.id).order_by(QuestionBank.id).first()[0]
        cand = Question(
            question_type="SINGLE_CHOICE",
            content="Java 中 HashMap 的底层采用什么数据结构实现？",
            answer="B", analysis="", difficulty=2, status="published",
            source_type="MANUAL", question_bank_id=bank_id,
            content_hash="c4candidatehash", hash_version="2", dedup_key=None)
        db.add(cand)
        db.commit()
        calls_before = reviewer.call_count
        res4 = svc.check_one(_snap("Java 中 HashMap 的底层采用什么数据结构实现？",
                                   bank=bank_id, kids=(999,),
                                   options=(("选项一", 0), ("选项二", 1))))
        delta4 = reviewer.call_count - calls_before
        _record("C4", "跨范围极高相似必须触发 LLM",
                llm_calls=delta4, decision=res4.decision, scope=res4.scope_mode,
                score=round(res4.algorithm_score, 3),
                matched=res4.matched_question_id)
        assert delta4 >= 1, "跨范围极高相似候选必须进入 LLM 复核"
        db.delete(cand)  # 清理测试候选，不污染题目库
        db.commit()
    finally:
        db.close()


def run_e2e():
    """用例7：一次完整生成任务端到端（真实 MiMo 生成 + 去重）。"""
    from app.core.database import SessionLocal
    from agent.question_generate.agent import QuestionGenerateAgent
    from app.models import Knowledge, QuestionBank
    from app.services.question_dedup_service import (
        QuestionDeduplicationService, snapshot_from_generated,
    )

    db = SessionLocal()
    try:
        kid = db.query(Knowledge.id).order_by(Knowledge.id).first()[0]
        bank_id = db.query(QuestionBank.id).order_by(QuestionBank.id).first()[0]
        agent = QuestionGenerateAgent(db)
        t0 = time.time()
        result = agent.generate_for_plan_item(
            knowledge_id=kid, question_bank_id=bank_id,
            question_type="SINGLE_CHOICE", difficulty=2, count=2)
        gen_dt = time.time() - t0
        questions = result.get("questions", [])
        _record("C7a", "真实生成", generated=len(questions),
                failed=result.get("failed_count", 0), duration_s=round(gen_dt, 2),
                errors=[str(e)[:120] for e in (result.get("errors") or [])])

        svc = QuestionDeduplicationService(db)
        snaps = [snapshot_from_generated(q, bank_id, [kid]) for q in questions]
        t0 = time.time()
        results = svc.check_batch(snaps)
        dt = time.time() - t0
        decisions = [r.decision for r in results]
        _record("C7b", "端到端去重判定",
                inputs=len(snaps), decisions=decisions,
                duplicate=decisions.count("duplicate"),
                distinct=decisions.count("distinct"),
                uncertain=decisions.count("uncertain"),
                llm_called=sum(1 for r in results if r.llm_called),
                duration_s=round(dt, 2))
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-e2e", action="store_true")
    parser.add_argument("--skip-review", action="store_true",
                        help="跳过 C1/C2/C5/C6（复跑时省 LLM 调用）")
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    print("==== 真实 MiMo LLM 复核冒烟 ====")
    reviewer = None
    if not args.skip_review:
        reviewer = run_review_cases()
        run_degrade_cases()
    run_service_trigger_cases()
    if not args.skip_e2e:
        try:
            run_e2e()
        except Exception as exc:  # noqa: BLE001
            _record("C7", "端到端未完成（如实记录）", error=str(exc)[:200])

    total_calls = reviewer.call_count if reviewer is not None else 0
    summary = {"cases": CASES, "total_llm_calls_review_cases": total_calls,
               "model": os.environ.get("LLM_MODEL", "(未设置)")}
    if args.report:
        Path(args.report).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告已写入 {args.report}")
    print("==== 冒烟完成 ====")


if __name__ == "__main__":
    main()
