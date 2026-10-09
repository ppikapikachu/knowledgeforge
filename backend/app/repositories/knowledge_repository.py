"""Knowledge repository."""

from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.knowledge import Knowledge
from app.models.question_knowledge import QuestionKnowledge


class KnowledgeRepository:
    """Repository for knowledge database operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, knowledge_id: int) -> Optional[Knowledge]:
        """Get knowledge by ID."""
        return (
            self.db.query(Knowledge)
            .filter(Knowledge.id == knowledge_id)
            .first()
        )

    def get_list(
        self,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        difficulty: Optional[int] = None,
        status: Optional[int] = None,
        knowledge_base_id: Optional[int] = None,
    ) -> Tuple[List[Knowledge], int]:
        """Get knowledge list with filters and pagination."""
        query = self.db.query(Knowledge)

        if keyword:
            query = query.filter(Knowledge.name.contains(keyword))
        if difficulty is not None:
            query = query.filter(Knowledge.difficulty == difficulty)
        if status is not None:
            query = query.filter(Knowledge.status == status)
        if knowledge_base_id is not None:
            query = query.filter(Knowledge.knowledge_base_id == knowledge_base_id)

        total = query.count()
        items = (
            query.order_by(Knowledge.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def create(self, **kwargs) -> Knowledge:
        """Create a new knowledge point."""
        knowledge = Knowledge(**kwargs)
        self.db.add(knowledge)
        self.db.flush()
        return knowledge

    def update(self, knowledge: Knowledge, **kwargs) -> Knowledge:
        """Update an existing knowledge point."""
        for key, value in kwargs.items():
            if value is not None and hasattr(knowledge, key):
                setattr(knowledge, key, value)
        self.db.flush()
        return knowledge

    def disable(self, knowledge: Knowledge) -> Knowledge:
        """Disable a knowledge point (soft delete)."""
        knowledge.status = 0
        self.db.flush()
        return knowledge

    def count(self, status: Optional[int] = None) -> int:
        """Count knowledge points."""
        query = self.db.query(func.count(Knowledge.id))
        if status is not None:
            query = query.filter(Knowledge.status == status)
        return query.scalar() or 0

    def get_question_counts(self, knowledge_ids: List[int]) -> dict:
        """Get the number of questions associated with each knowledge point.
        
        Returns:
            dict: {knowledge_id: question_count}
        """
        if not knowledge_ids:
            return {}
        rows = (
            self.db.query(
                QuestionKnowledge.knowledge_id,
                func.count(QuestionKnowledge.id),
            )
            .filter(QuestionKnowledge.knowledge_id.in_(knowledge_ids))
            .group_by(QuestionKnowledge.knowledge_id)
            .all()
        )
        return {row[0]: row[1] for row in rows}
