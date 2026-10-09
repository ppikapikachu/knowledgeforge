"""Embedding 同步服务模块。

本模块负责将 MySQL 中的知识点向量同步到 Vector DB。
是 MySQL（事实来源）和 Vector DB（搜索索引）之间的桥梁。

职责：
    1. 单个知识点的 Embedding 同步（create/update/disable）
    2. 批量回填已有知识点的 Embedding
    3. 禁用知识点时从向量库删除

数据所有权原则：
    MySQL = Source of Truth（正式数据）
    Vector DB = Search Index（搜索索引）

同步策略：
    先提交 MySQL → 再同步 Vector DB
    MySQL 成功但 Vector DB 失败 → 记录错误，允许重试
"""

import logging
import time
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from agent.common.embedding import get_embedding_service
from agent.common.vector_store import get_vector_store
from agent.knowledge_deduplicate.normalizer import KnowledgeNormalizer
from app.models.knowledge import Knowledge

logger = logging.getLogger(__name__)


class EmbeddingSyncService:
    """Embedding 同步服务。

    使用方法：
        service = EmbeddingSyncService(db)
        service.sync_knowledge(1001)           # 同步单个
        result = service.batch_sync_all()       # 批量回填
    """

    def __init__(self, db: Session):
        self.db = db
        self.normalizer = KnowledgeNormalizer()

    def _build_embedding_text(self, knowledge: Knowledge) -> str:
        """构建用于 Embedding 的文本。

        使用 name + summary + keywords，不使用完整 content。
        这样更稳定、更省计算。
        """
        keywords = knowledge.keywords or []
        return self.normalizer.build_embedding_text(
            knowledge.name or "",
            knowledge.summary or "",
            keywords,
        )

    def sync_knowledge(self, knowledge_id: int) -> bool:
        """同步单个知识点的 Embedding 到 Vector DB。

        流程：
            1. 从 MySQL 读取知识点
            2. 构建 Embedding 文本
            3. 生成向量
            4. upsert 到 Vector DB

        Args:
            knowledge_id: 知识点 ID

        Returns:
            是否同步成功

        注意：
            - MySQL 必须已经提交，本函数只负责 Vector DB 同步
            - 使用 upsert 保证重复同步不会产生重复向量
        """
        knowledge = self.db.query(Knowledge).filter(
            Knowledge.id == knowledge_id
        ).first()

        if not knowledge:
            logger.warning(f"知识点 {knowledge_id} 不存在，跳过同步")
            return False

        return self._sync_knowledge_object(knowledge)

    def _sync_knowledge_object(self, knowledge: Knowledge) -> bool:
        """将知识对象同步到向量库。"""
        try:
            embedding_text = self._build_embedding_text(knowledge)
            service = get_embedding_service()
            vector = service.embed_text(embedding_text)

            store = get_vector_store()
            store.upsert(
                id=f"knowledge_{knowledge.id}",
                vector=vector,
                metadata={
                    "knowledge_id": knowledge.id,
                    "knowledge_base_id": knowledge.knowledge_base_id,
                    "name": knowledge.name,
                    "summary": knowledge.summary,
                    "content": knowledge.content,
                    "difficulty": knowledge.difficulty,
                    "keywords": knowledge.keywords,
                    "status": knowledge.status,
                },
            )
            logger.info(f"知识点 {knowledge.id} Embedding 同步成功")
            return True

        except Exception as e:
            logger.error(f"知识点 {knowledge.id} Embedding 同步失败: {e}")
            return False

    def remove_knowledge(self, knowledge_id: int) -> bool:
        """从向量库中移除知识点（禁用时调用）。

        Args:
            knowledge_id: 知识点 ID

        Returns:
            是否移除成功
        """
        try:
            store = get_vector_store()
            store.delete(f"knowledge_{knowledge_id}")
            logger.info(f"知识点 {knowledge_id} 已从向量库移除")
            return True
        except Exception as e:
            logger.error(f"知识点 {knowledge_id} 向量移除失败: {e}")
            return False

    def batch_sync_all(
        self,
        batch_size: int = 32,
    ) -> Dict:
        """批量回填所有正常知识点的 Embedding。

        只处理 status = 1（正常）的知识点。
        禁用知识点不进入检索。

        Args:
            batch_size: 批量 Embedding 大小

        Returns:
            统计信息 dict:
                - total: 知识点总数
                - to_sync: 需要同步的数量
                - success: 成功数量
                - failed: 失败数量
                - failed_ids: 失败的知识点 ID 列表
                - duration: 耗时（秒）
        """
        start_time = time.time()

        # 查询所有正常知识点
        total = self.db.query(Knowledge).filter(
            Knowledge.status == 1
        ).count()

        knowledge_list = self.db.query(Knowledge).filter(
            Knowledge.status == 1
        ).all()

        logger.info(f"开始批量 Embedding 同步: 共 {total} 个知识点")

        success = 0
        failed = 0
        failed_ids = []

        # 分批处理
        for i in range(0, len(knowledge_list), batch_size):
            batch = knowledge_list[i:i + batch_size]

            try:
                # 批量构建 Embedding 文本
                texts = [
                    self._build_embedding_text(k) for k in batch
                ]

                # 批量生成向量
                service = get_embedding_service()
                vectors = service.embed_texts(texts)

                # 批量写入向量库
                store = get_vector_store()
                for knowledge, vector in zip(batch, vectors):
                    try:
                        store.upsert(
                            id=f"knowledge_{knowledge.id}",
                            vector=vector,
                            metadata={
                                "knowledge_id": knowledge.id,
                                "knowledge_base_id": knowledge.knowledge_base_id,
                                "name": knowledge.name,
                                "summary": knowledge.summary,
                                "content": knowledge.content,
                                "difficulty": knowledge.difficulty,
                                "keywords": knowledge.keywords,
                                "status": knowledge.status,
                            },
                        )
                        success += 1
                    except Exception as e:
                        failed += 1
                        failed_ids.append(knowledge.id)
                        logger.error(
                            f"知识点 {knowledge.id} 向量写入失败: {e}"
                        )

            except Exception as e:
                # 批量 Embedding 失败，本批次全部标记失败
                failed += len(batch)
                failed_ids.extend(k.id for k in batch)
                logger.error(f"批次 {i // batch_size + 1} Embedding 失败: {e}")

        duration = time.time() - start_time

        logger.info(
            f"批量 Embedding 同步完成: "
            f"总数={total}, 成功={success}, 失败={failed}, "
            f"耗时={duration:.2f}s"
        )

        return {
            "total": total,
            "to_sync": total,
            "success": success,
            "failed": failed,
            "failed_ids": failed_ids,
            "duration": round(duration, 2),
        }

    def check_consistency(self) -> Dict:
        """检查 MySQL 与 Vector DB 的一致性。

        Returns:
            检查结果 dict:
                - mysql_normal: MySQL 正常知识数
                - vector_indexed: 向量库已索引数
                - missing: 缺失 embedding 的知识点 ID
                - extra: 多余的向量 ID
        """
        # MySQL 正常知识
        mysql_list = self.db.query(Knowledge).filter(
            Knowledge.status == 1
        ).all()
        mysql_ids = {f"knowledge_{k.id}" for k in mysql_list}

        # Vector DB 中的记录
        store = get_vector_store()
        vector_count = store.count()

        # 简单一致性检查
        # （FAISS 内存存储不支持枚举所有 ID，这里只检查数量）
        return {
            "mysql_normal": len(mysql_list),
            "vector_indexed": vector_count,
            "missing": [],  # 需要持久化存储才能精确检查
            "extra": [],
            "note": "当前使用内存向量库，重启后向量丢失，需重新回填",
        }
