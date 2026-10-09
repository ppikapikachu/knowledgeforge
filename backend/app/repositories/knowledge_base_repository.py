"""知识库 Repository。"""

from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.knowledge import Knowledge
from app.models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository:
    """知识库数据访问层。"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, kb_id: int) -> Optional[KnowledgeBase]:
        """根据 ID 获取知识库。"""
        return self.db.query(KnowledgeBase).filter(
            KnowledgeBase.id == kb_id
        ).first()

    def get_by_code(self, code: str) -> Optional[KnowledgeBase]:
        """根据编码获取知识库。"""
        return self.db.query(KnowledgeBase).filter(
            KnowledgeBase.code == code
        ).first()

    def get_list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[int] = None,
    ) -> Tuple[List[KnowledgeBase], int]:
        """获取知识库列表。"""
        query = self.db.query(KnowledgeBase)
        if status is not None:
            query = query.filter(KnowledgeBase.status == status)

        total = query.count()
        items = (
            query.order_by(KnowledgeBase.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def create(self, **kwargs) -> KnowledgeBase:
        """创建知识库。"""
        kb = KnowledgeBase(**kwargs)
        self.db.add(kb)
        self.db.flush()
        return kb

    def update(self, kb: KnowledgeBase, **kwargs) -> KnowledgeBase:
        """更新知识库。"""
        for key, value in kwargs.items():
            if value is not None and hasattr(kb, key):
                setattr(kb, key, value)
        self.db.flush()
        return kb

    def get_knowledge_count(self, kb_id: int) -> int:
        """获取知识库下的知识点数量。"""
        return self.db.query(func.count(Knowledge.id)).filter(
            Knowledge.knowledge_base_id == kb_id
        ).scalar() or 0

    def get_knowledge_counts(self, kb_ids: List[int]) -> dict:
        """批量获取知识库下的知识点数量。"""
        if not kb_ids:
            return {}
        rows = (
            self.db.query(
                Knowledge.knowledge_base_id,
                func.count(Knowledge.id),
            )
            .filter(Knowledge.knowledge_base_id.in_(kb_ids))
            .group_by(Knowledge.knowledge_base_id)
            .all()
        )
        return {row[0]: row[1] for row in rows}
