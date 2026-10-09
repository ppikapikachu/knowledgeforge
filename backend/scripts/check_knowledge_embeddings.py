"""检查 MySQL 与 Vector DB 的 Embedding 一致性。

使用方法：
    cd backend
    python scripts/check_knowledge_embeddings.py

输出 MySQL 正常知识数、向量库已索引数、缺失/多余数量。
"""

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.embedding_sync_service import EmbeddingSyncService


def main():
    """执行一致性检查。"""
    print("=" * 50)
    print("  Knowledge Embedding 一致性检查")
    print("=" * 50)

    db = SessionLocal()
    try:
        service = EmbeddingSyncService(db)
        result = service.check_consistency()

        print(f"\nMySQL 正常知识数: {result['mysql_normal']}")
        print(f"向量库已索引数: {result['vector_indexed']}")
        print(f"缺失 embedding: {len(result['missing'])}")
        print(f"多余向量: {len(result['extra'])}")

        if result.get("note"):
            print(f"\n注意: {result['note']}")

        if result["missing"]:
            print(f"\n缺失的知识点 ID:")
            for kid in result["missing"]:
                print(f"  knowledge_id={kid}")

        if result["extra"]:
            print(f"\n多余的向量 ID:")
            for vid in result["extra"]:
                print(f"  vector_id={vid}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
