"""批量回填已有知识点的 Embedding 到 Vector DB。

使用方法：
    cd backend
    python scripts/sync_knowledge_embeddings.py

支持重复执行，重复执行不会产生重复向量（使用 upsert）。
"""

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.embedding_sync_service import EmbeddingSyncService


def main():
    """执行批量 Embedding 同步。"""
    print("=" * 50)
    print("  Knowledge Embedding 同步工具")
    print("=" * 50)

    db = SessionLocal()
    try:
        service = EmbeddingSyncService(db)
        result = service.batch_sync_all()

        print(f"\n知识点总数: {result['total']}")
        print(f"需要同步: {result['to_sync']}")
        print(f"成功: {result['success']}")
        print(f"失败: {result['failed']}")
        print(f"耗时: {result['duration']}s")

        if result["failed_ids"]:
            print(f"\n失败的知识点 ID:")
            for kid in result["failed_ids"]:
                print(f"  knowledge_id={kid}")

        if result["failed"] == 0:
            print("\n全部同步成功!")
        else:
            print(f"\n部分失败，请重新运行脚本重试。")

    finally:
        db.close()


if __name__ == "__main__":
    main()
