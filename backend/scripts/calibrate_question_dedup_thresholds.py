"""题目去重阈值标定脚本（执行文档 §4.2：用标注样本标定阈值并输出误判/漏判）。

用真实 Embedding + 文本相似度为标注样本打分，评估同范围/跨范围阈值网格，
输出每对样本的分数、误判（本应 distinct 却进入复核/判重）与漏判（本应 duplicate
却被放行）情况，并给出推荐阈值。

样本取自执行文档 §12.2 的重复样本清单（题干类 11 对；LLM 超时、向量故障、
状态处理等 3 类不涉及阈值，由 tests/test_question_dedup.py 覆盖）。

用法：
    python scripts/calibrate_question_dedup_thresholds.py
    python scripts/calibrate_question_dedup_thresholds.py --report out.json
"""

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.common.embedding import get_embedding_service  # noqa: E402
from app.services.question_normalizer import question_normalizer  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("calibrate_thresholds")

# 标注样本：(case_id, 说明, 新题, 候选题, 范围, 期望判重)
# 新题/候选题 = (question_type, content, options[(key, content, is_correct)])
SAMPLES = [
    ("S01", "完全相同题干",
     ("SINGLE_CHOICE", "HashMap 的底层数据结构是什么？", [("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)]),
     ("SINGLE_CHOICE", "HashMap 的底层数据结构是什么？", [("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)]),
     "same_scope", True),
    ("S02", "题干空格/标点不同",
     ("SINGLE_CHOICE", "HashMap 的底层数据结构是什么？", [("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)]),
     ("SINGLE_CHOICE", "HashMap的底层数据结构是什么", [("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)]),
     "same_scope", True),
    ("S03", "选项顺序变化",
     ("SINGLE_CHOICE", "HashMap 的底层数据结构是什么？", [("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)]),
     ("SINGLE_CHOICE", "HashMap 的底层数据结构是什么？", [("A", "双向链表", 0), ("B", "数组+链表+红黑树", 1)]),
     "same_scope", True),
    ("S04", "同一答案改写题干",
     ("SINGLE_CHOICE", "JDK 8 中 HashMap 的底层采用什么数据结构实现？", [("A", "数组+链表+红黑树", 1), ("B", "哈希表", 0)]),
     ("SINGLE_CHOICE", "Java 中 HashMap 底层是什么结构？", [("A", "数组、链表和红黑树", 1), ("B", "顺序表", 0)]),
     "same_scope", True),
    ("S05", "同知识点不同考查角度（不得误杀）",
     ("SINGLE_CHOICE", "HashMap 的底层数据结构是什么？", [("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)]),
     ("SINGLE_CHOICE", "HashMap 何时触发扩容？扩容倍数是多少？", [("A", "元素超过阈值时扩容一倍", 1), ("B", "每次 put 都扩容", 0)]),
     "same_scope", False),
    ("S06", "相同关键词不同主题",
     ("SINGLE_CHOICE", "HashMap 是线程安全的吗？为什么？", [("A", "不是，未同步", 1), ("B", "是", 0)]),
     ("SINGLE_CHOICE", "ConcurrentHashMap 如何保证线程安全？", [("A", "分段锁/CAS", 1), ("B", "全局锁", 0)]),
     "same_scope", False),
    ("S07", "跨题库题目近乎相同",
     ("SINGLE_CHOICE", "HashMap 的底层数据结构是什么？", [("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)]),
     ("SINGLE_CHOICE", "HashMap 的底层数据结构是什么？", [("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)]),
     "cross_scope", True),
    ("S08", "跨题库仅知识点相关",
     ("SINGLE_CHOICE", "Java 集合中 ArrayList 的默认容量是多少？", [("A", "10", 1), ("B", "16", 0)]),
     ("SINGLE_CHOICE", "HashMap 的默认负载因子是多少？", [("A", "0.75", 1), ("B", "0.5", 0)]),
     "cross_scope", False),
    ("S09", "单选题和简答题题干相似",
     ("SINGLE_CHOICE", "HashMap 的底层数据结构是什么？", [("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)]),
     ("SHORT_ANSWER", "请简述 HashMap 的底层数据结构。", []),
     "same_scope", False),
    ("S10", "同一生成任务内重复",
     ("MULTIPLE_CHOICE", "以下哪些属于 JVM 垃圾回收算法？", [("A", "标记清除", 1), ("B", "复制", 1), ("C", "归并", 1), ("D", "轮询", 0)]),
     ("MULTIPLE_CHOICE", "以下哪些属于 JVM 垃圾回收算法？", [("A", "标记清除", 1), ("B", "复制", 1), ("C", "归并", 1), ("D", "轮询", 0)]),
     "same_scope", True),
    ("S11", "并发任务几乎同时写入同一道题",
     ("TRUE_FALSE", "Java 中的 HashMap 是线程安全的。", []),
     ("TRUE_FALSE", "Java 中的 HashMap 是线程安全的。", []),
     "same_scope", True),
    ("S12", "不同审核状态（rejected 不阻断）",
     ("SINGLE_CHOICE", "HashMap 的底层数据结构是什么？", [("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)]),
     ("SINGLE_CHOICE", "HashMap 的底层数据结构是什么？", [("A", "数组+链表+红黑树", 1), ("B", "双向链表", 0)]),
     "same_scope", False),  # 状态在服务层处理；样本层面按"不阻断"标注
]

SAME_GRID = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
CROSS_GRID = [0.75, 0.80, 0.85, 0.90, 0.95]


def vec_cosine(a, b) -> float:
    import math
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a)) or 1.0
    db_ = math.sqrt(sum(y * y for y in b)) or 1.0
    return max(0.0, num / (da * db_))


def vector_text(qt, content, options) -> str:
    opts = [(k, c) for k, c, _ in options]
    return question_normalizer.build_vector_text(qt, content, opts)


def main() -> int:
    parser = argparse.ArgumentParser(description="题目去重阈值标定")
    parser.add_argument("--report", type=str, default=None, help="JSON 报告输出路径")
    args = parser.parse_args()

    try:
        emb = get_embedding_service()
    except Exception as exc:  # noqa: BLE001
        logger.error("Embedding 服务不可用（需要本地 FlagModel）: %s", exc)
        return 1

    rows = []
    logger.info("样本打分（真实 Embedding=%s）...", emb)
    for case_id, desc, new, cand, scope, expect_dup in SAMPLES:
        (nt, nc, nopt), (ct, cc, copt) = new, cand
        kw = question_normalizer.text_similarity(nc, cc)
        try:
            vn = emb.embed_text(vector_text(nt, nc, nopt))
            vc = emb.embed_text(vector_text(ct, cc, copt))
            vec = vec_cosine(vn, vc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s Embedding 失败: %s", case_id, exc)
            vec = 0.0
        fused = 0.6 * vec + 0.4 * kw if (vec > 0 and kw > 0) else (vec or kw)
        rows.append({
            "case_id": case_id, "desc": desc, "scope": scope, "expect_duplicate": expect_dup,
            "keyword_score": round(kw, 4), "vector_score": round(vec, 4), "fused": round(fused, 4),
        })
        logger.info("%s %-28s scope=%-11s expect=%-5s kw=%.3f vec=%.3f fused=%.3f",
                    case_id, desc, scope, expect_dup, kw, vec, fused)

    # 阈值网格评估：阈值决定"是否进入复核/判重流程"
    same_scores = [(r["fused"], r["expect_duplicate"]) for r in rows if r["scope"] == "same_scope"]
    cross_scores = [(r["fused"], r["expect_duplicate"]) for r in rows if r["scope"] == "cross_scope"]

    def evaluate(scores, threshold):
        fp = sum(1 for s, dup in scores if (not dup) and s >= threshold)  # 误判风险（distinct 进复核）
        fn = sum(1 for s, dup in scores if dup and s < threshold)          # 漏判（duplicate 被放行）
        return fp, fn

    evaluation = {"same_scope": [], "cross_scope": []}
    for thr in SAME_GRID:
        fp, fn = evaluate(same_scores, thr)
        evaluation["same_scope"].append({"threshold": thr, "false_positive": fp, "false_negative": fn})
        logger.info("same_scope 阈值 %.2f → 误判风险 %s 漏判 %s", thr, fp, fn)
    for thr in CROSS_GRID:
        fp, fn = evaluate(cross_scores, thr)
        evaluation["cross_scope"].append({"threshold": thr, "false_positive": fp, "false_negative": fn})
        logger.info("cross_scope 阈值 %.2f → 误判风险 %s 漏判 %s", thr, fp, fn)

    # 推荐：漏判优先为 0 的最低阈值；误判（distinct 进复核）交给 LLM 复核兜底
    def recommend(grid_eval):
        ok = [e for e in grid_eval if e["false_negative"] == 0]
        return min(ok, key=lambda e: e["false_positive"] + e["threshold"])["threshold"] if ok else None

    rec_same = recommend(evaluation["same_scope"])
    rec_cross = recommend(evaluation["cross_scope"])
    logger.info("推荐阈值: same_scope=%s cross_scope=%s（跨范围必须严于同范围）", rec_same, rec_cross)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump({
                "samples": rows,
                "evaluation": evaluation,
                "recommended": {"same_scope": rec_same, "cross_scope": rec_cross},
                "note": "误判=distinct 样本进入复核（由 LLM 复核兜底，关注误杀率）；漏判=duplicate 样本未进入复核被放行（必须为 0）",
            }, f, ensure_ascii=False, indent=2)
        logger.info("报告已写入 %s", args.report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
