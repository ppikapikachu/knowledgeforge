"""QuestionReviewAgent 真实模型验收冒烟（执行文档 §8 三级验收）。

8 类人工标注样本逐一对比期望决策与真实 MiMo 模型输出，输出对比表与
误通过/误驳回率。用法：
    python scripts/question_review_smoke.py [--report <json 路径>]

只读验收：不写业务表、不流转题目状态（服务层 skip 验证除外，使用临时记录）。
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.question_review.agent import QuestionReviewAgent, QuestionReviewAgentError  # noqa: E402
from agent.question_review.schemas import QuestionReviewOutput  # noqa: E402


def ctx(question_id, question_type, content, answer, analysis, options=None,
        knowledge_points=None, difficulty=2, dedup_status="distinct",
        dedup_unresolved=False):
    # options 允许 (key, content, is_correct) 元组写法，统一为契约 dict
    norm_options = []
    for opt in (options or []):
        if isinstance(opt, dict):
            norm_options.append(opt)
        else:
            key, content_text, is_correct = opt
            norm_options.append({
                "option_key": key,
                "option_content": content_text,
                "is_correct": is_correct,
            })
    return {
        "question_id": question_id,
        "question_type": question_type,
        "difficulty": difficulty,
        "content": content,
        "answer": answer,
        "analysis": analysis,
        "options": norm_options,
        "knowledge_points": knowledge_points or [],
        "version_environment": None,
        "dedup_status": dedup_status,
        "dedup_unresolved": dedup_unresolved,
    }


KP_HASHMAP = [{
    "knowledge_id": 1,
    "name": "HashMap 底层结构",
    "content": "HashMap 在 JDK 8 中采用数组 + 链表 + 红黑树实现；哈希冲突以链表法解决，"
               "当链表长度超过 8 且数组长度超过 64 时转为红黑树。默认负载因子 0.75。",
    "importance_level": "core",
}]

SAMPLES = [
    {
        "id": "R1 正确单选",
        "expect": "auto_approve",
        "context": ctx(
            1, "SINGLE_CHOICE",
            "Java 中 HashMap 在 JDK 8 的默认负载因子是多少？",
            "0.75",
            "HashMap 默认负载因子为 0.75，是空间与时间的折中。",
            options=[("A", "0.5", False), ("B", "0.75", True),
                     ("C", "1.0", False), ("D", "1.5", False)],
            knowledge_points=KP_HASHMAP,
        ),
    },
    {
        "id": "R2 参考答案错误",
        "expect": "auto_reject",
        "context": ctx(
            2, "SINGLE_CHOICE",
            "Java 中 HashMap 在 JDK 8 的默认负载因子是多少？",
            "1.5",
            "负载因子是 1.5。",
            options=[("A", "0.5", False), ("B", "0.75", True),
                     ("C", "1.0", False), ("D", "1.5", False)],
            knowledge_points=KP_HASHMAP,
        ),
    },
    {
        "id": "R3 选项内容重复无效",
        "expect": "auto_reject",
        "context": ctx(
            3, "SINGLE_CHOICE",
            "HashMap 采用什么结构处理哈希冲突？",
            "A",
            "链表法。",
            options=[("A", "链表法", True), ("B", "链表法", False),
                     ("C", "开放寻址法", False), ("D", "再哈希法", False)],
            knowledge_points=KP_HASHMAP,
        ),
    },
    {
        "id": "R4 与知识点不符",
        "expect": "manual_review",
        "context": ctx(
            4, "SINGLE_CHOICE",
            "以下哪个不是 Java 基本数据类型？",
            "String",
            "String 是引用类型。",
            options=[("A", "int", False), ("B", "char", False),
                     ("C", "boolean", False), ("D", "String", True)],
            knowledge_points=KP_HASHMAP,
        ),
    },
    {
        "id": "R5 题干歧义",
        "expect": "manual_review",
        "context": ctx(
            5, "SINGLE_CHOICE",
            "HashMap 的容量是多少？",
            "16",
            "默认初始容量 16。",
            options=[("A", "16", True), ("B", "32", False),
                     ("C", "64", False), ("D", "8", False)],
            knowledge_points=KP_HASHMAP,
        ),
    },
    {
        "id": "R6 答案与选项不匹配",
        "expect": "auto_reject",
        "context": ctx(
            6, "SINGLE_CHOICE",
            "HashMap 默认初始容量是多少？",
            "C",
            "初始容量为 16。",
            options=[("A", "8", False), ("B", "16", True),
                     ("C", "32", False), ("D", "64", False)],
            knowledge_points=KP_HASHMAP,
        ),
    },
    {
        "id": "R7 资料不足争议题",
        "expect": "manual_review",
        "context": ctx(
            7, "TRUE_FALSE",
            "HashMap 在所有 JDK 版本中的实现完全相同。",
            "FALSE",
            "不同版本实现有差异。",
            options=[],
            knowledge_points=KP_HASHMAP,
        ),
    },
    {
        "id": "R8 正确多选",
        "expect": "auto_approve",
        "context": ctx(
            8, "MULTIPLE_CHOICE",
            "以下关于 HashMap 的说法正确的是？",
            "AB",
            "负载因子 0.75；红黑树阈值 8。",
            options=[("A", "默认负载因子 0.75", True),
                     ("B", "链表长度超 8 可转红黑树", True),
                     ("C", "HashMap 是线程安全的", False),
                     ("D", "HashMap 允许 null 键但不允许 null 值", False)],
            knowledge_points=KP_HASHMAP,
        ),
    },
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=None, help="结果 JSON 输出路径")
    args = parser.parse_args()

    agent = QuestionReviewAgent()
    rows = []
    mismatch = 0
    false_approve = 0
    false_reject = 0
    for sample in SAMPLES:
        started = time.monotonic()
        try:
            output: QuestionReviewOutput = agent.review(sample["context"])
            decision, risk = output.decision, output.risk_level
            issues = list(output.issue_types)
            reason = (output.reason or "")[:120]
            error = None
        except QuestionReviewAgentError as exc:
            decision, risk, issues, reason = "manual_review", "unknown", [], ""
            error = str(exc)[:200]
        duration = round(time.monotonic() - started, 2)

        ok = decision == sample["expect"]
        if not ok:
            mismatch += 1
            if decision == "auto_approve" and sample["expect"] != "auto_approve":
                false_approve += 1
            if decision == "auto_reject" and sample["expect"] != "auto_reject":
                false_reject += 1

        rows.append({
            "id": sample["id"],
            "expect": sample["expect"],
            "actual": decision,
            "risk_level": risk,
            "issue_types": issues,
            "match": ok,
            "duration_s": duration,
            "reason": reason,
            "error": error,
        })
        print(f"{sample['id']}: 期望={sample['expect']} 实际={decision} "
              f"风险={risk} 问题项={issues} 匹配={ok} 耗时={duration}s")
        if reason:
            print(f"    理由: {reason}")

    n = len(rows)
    print("\n==== 汇总 ====")
    print(f"样本数: {n}  匹配: {n - mismatch}  不匹配: {mismatch}")
    print(f"误通过（应人工/驳回却 approve）: {false_approve}")
    print(f"误驳回（应通过/人工却 reject）: {false_reject}")
    print(f"匹配率: {(n - mismatch) / n:.0%}")

    if args.report:
        Path(args.report).write_text(json.dumps(
            {"samples": rows, "mismatch": mismatch,
             "false_approve": false_approve, "false_reject": false_reject},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[report] {args.report}")


if __name__ == "__main__":
    main()
