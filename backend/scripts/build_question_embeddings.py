"""历史题目向量索引构建/检查/修复脚本（执行文档 §10）。

特性：
    - 可重复运行、支持断点续跑（按 id 升序分批读取）；
    - --only-missing 只补缺失向量（默认），已存在且版本一致的跳过；
    - --all 强制重建全部（含版本不一致）；
    - --check 只做一致性检查（MySQL 阻断状态题目 vs 向量库），不写向量；
    - 失败记录并可重跑补齐；输出统计 total/success/failed/skipped。

用法：
    python scripts/build_question_embeddings.py                  # 只补缺失
    python scripts/build_question_embeddings.py --all            # 强制全量重建
    python scripts/build_question_embeddings.py --check          # 一致性检查
    python scripts/build_question_embeddings.py --batch-size 64
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.models.question import Question  # noqa: E402
from app.services.question_dedup_service import (  # noqa: E402
    BLOCKING_STATUSES,
    QuestionDeduplicationService,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_question_embeddings")


def check_consistency(db, service) -> int:
    """一致性检查：MySQL 阻断状态题目 vs 向量库。返回不一致条数。"""
    store = service._get_vector_store()
    indexed = set(store.list_ids())
    mysql_ids = {
        qid for (qid,) in db.query(Question.id).filter(Question.status.in_(BLOCKING_STATUSES))
    }
    indexed_qids = set()
    orphan = []
    for key in indexed:
        if not str(key).startswith("question_"):
            continue
        try:
            qid = int(str(key).split("_", 1)[1])
        except ValueError:
            continue
        indexed_qids.add(qid)
        if qid not in mysql_ids:
            orphan.append(key)

    missing = sorted(mysql_ids - indexed_qids)
    logger.info("一致性检查: MySQL 阻断状态题目=%s 向量条目=%s 缺失=%s 孤儿=%s",
                len(mysql_ids), len(indexed), len(missing), len(orphan))
    if missing:
        logger.warning("缺失向量的题目(前 50): %s", missing[:50])
    if orphan:
        logger.warning("向量库孤儿条目(前 50): %s", orphan[:50])
    if not missing and not orphan:
        logger.info("索引与 MySQL 一致 ✓")
    return len(missing) + len(orphan)


def main() -> int:
    parser = argparse.ArgumentParser(description="构建/检查/修复历史题目向量索引")
    parser.add_argument("--all", action="store_true", help="强制重建全部向量")
    parser.add_argument("--check", action="store_true", help="只做一致性检查")
    parser.add_argument("--batch-size", type=int, default=32, help="分批读取大小（默认 32）")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        service = QuestionDeduplicationService(db)
        if args.check:
            bad = check_consistency(db, service)
            return 0 if bad == 0 else 2

        stats = service.rebuild_missing_vectors(
            batch_size=args.batch_size,
            only_missing=not args.all,
            statuses=BLOCKING_STATUSES,
        )
        logger.info("向量构建完成: %s", stats)
        check_consistency(db, service)
        return 0 if stats.get("failed", 0) == 0 else 3
    except Exception as exc:  # noqa: BLE001
        logger.error("向量构建失败: %s", exc, exc_info=True)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
