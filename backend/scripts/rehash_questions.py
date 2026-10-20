"""历史题目指纹重算脚本（执行文档 §3.3 指纹版本化 / §7）。

用途：
    存量题目 content_hash 为旧算法（16 位题干 hash，hash_version="0"），
    与 v1 指纹（题型+规范化题干+选项签名+答案）不兼容，精确去重层无法覆盖。
    本脚本按 v1 重算全部存量题指纹，并登记 dedup_key（仅阻断状态题目）。

规则：
    - 只更新 content_hash / hash_version / dedup_key，不删除任何业务数据；
    - 历史重复组只输出报告与清理建议，绝不自动删除；
    - dedup_key 冲突（历史重复）：id 最小者持有 dedup_key，其余置 NULL，
      与迁移脚本的去冲突规则一致；
    - 支持 --dry-run 与断点续跑（按 id 升序处理，逐题提交）。

用法：
    python scripts/rehash_questions.py                 # 只处理 hash_version != 1 的题目
    python scripts/rehash_questions.py --all           # 全量重算
    python scripts/rehash_questions.py --dry-run       # 只统计与报告，不写库
    python scripts/rehash_questions.py --report out.json  # 历史重复组写入 JSON
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.models.question import Question  # noqa: E402
from app.models.question_option import QuestionOption  # noqa: E402
from app.services.question_normalizer import HASH_VERSION, question_normalizer  # noqa: E402
from app.services.question_dedup_service import BLOCKING_STATUSES  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("rehash_questions")


def compute_v1_hash(db, question: Question) -> str:
    rows = db.query(QuestionOption).filter(
        QuestionOption.question_id == question.id
    ).order_by(QuestionOption.option_key.asc()).all()
    options = [(o.option_content, 1 if o.is_correct else 0) for o in rows]
    return question_normalizer.compute_content_hash(
        question.question_type, question.content, question.answer or "", options
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="按 v1 指纹算法重算存量题目指纹")
    parser.add_argument("--all", action="store_true", help="全量重算（默认跳过 hash_version=1）")
    parser.add_argument("--dry-run", action="store_true", help="只统计与报告，不写库")
    parser.add_argument("--batch-commit", type=int, default=50, help="每 N 题提交一次（默认 50）")
    parser.add_argument("--report", type=str, default=None, help="历史重复组 JSON 报告输出路径")
    args = parser.parse_args()

    db = SessionLocal()
    stats = {"total": 0, "updated": 0, "skipped": 0, "dedup_key_registered": 0,
             "dedup_key_null_for_duplicate": 0}
    try:
        query = db.query(Question).order_by(Question.id.asc())
        if not args.all:
            query = query.filter(
                (Question.hash_version.is_(None)) | (Question.hash_version != HASH_VERSION)
            )

        pending = 0
        for question in query.yield_per(200):
            stats["total"] += 1
            if question.content_hash and question.hash_version == HASH_VERSION and not args.all:
                stats["skipped"] += 1
                continue

            new_hash = compute_v1_hash(db, question)
            old_hash, old_version = question.content_hash, question.hash_version
            question.content_hash = new_hash
            question.hash_version = HASH_VERSION

            # dedup_key 登记：仅阻断状态；冲突（同指纹已登记）则置 NULL
            if question.status in BLOCKING_STATUSES:
                clash = db.query(Question.id).filter(
                    Question.dedup_key == new_hash, Question.id != question.id
                ).first()
                if clash:
                    question.dedup_key = None
                    stats["dedup_key_null_for_duplicate"] += 1
                    logger.warning(
                        "历史重复题：%s 与 %s 指纹相同，后者不登记 dedup_key（不删除）",
                        question.id, clash.id,
                    )
                else:
                    question.dedup_key = new_hash
                    stats["dedup_key_registered"] += 1
            else:
                question.dedup_key = None

            stats["updated"] += 1
            if stats["updated"] % 100 == 0:
                logger.info("进度: 已重算 %s 题", stats["updated"])

            if not args.dry_run:
                pending += 1
                if pending >= args.batch_commit:
                    db.commit()
                    pending = 0
            else:
                db.rollback()  # dry-run 不落库

        if not args.dry_run:
            db.commit()

        # 历史重复组报告
        groups = defaultdict(list)
        for qid, chash in db.query(Question.id, Question.content_hash).filter(
                Question.content_hash.isnot(None)):
            groups[chash].append(qid)
        dup_groups = {h: ids for h, ids in groups.items() if len(ids) > 1}
        if dup_groups:
            logger.warning("发现 %s 组历史重复题目（均未删除，请人工处理）:", len(dup_groups))
            for h, ids in sorted(dup_groups.items(), key=lambda kv: kv[1][0])[:50]:
                logger.warning("  指纹 %s → question_id=%s", h, sorted(ids))

        report = {
            "stats": stats,
            "duplicate_group_count": len(dup_groups),
            "duplicate_groups": [
                {"content_hash": h, "question_ids": sorted(ids)}
                for h, ids in sorted(dup_groups.items(), key=lambda kv: kv[1][0])
            ],
            "cleanup_hint": "历史重复组保留所有题目；建议人工核对后将多余的置 rejected/disabled",
        }
        if args.report:
            with open(args.report, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info("报告已写入 %s", args.report)

        logger.info("完成: %s", stats)
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("重算失败: %s", exc, exc_info=True)
        db.rollback()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
