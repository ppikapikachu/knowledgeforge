"""Knowledge relation repository."""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.knowledge_relation import KnowledgeRelation


class KnowledgeRelationRepository:
    """Repository for knowledge relation database operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, relation_id: int) -> Optional[KnowledgeRelation]:
        """Get relation by ID."""
        return (
            self.db.query(KnowledgeRelation)
            .filter(KnowledgeRelation.id == relation_id)
            .first()
        )

    def get_by_source(self, knowledge_id: int) -> List[KnowledgeRelation]:
        """Get all relations where given knowledge is source."""
        return (
            self.db.query(KnowledgeRelation)
            .filter(KnowledgeRelation.source_knowledge_id == knowledge_id)
            .all()
        )

    def get_by_target(self, knowledge_id: int) -> List[KnowledgeRelation]:
        """Get all relations where given knowledge is target."""
        return (
            self.db.query(KnowledgeRelation)
            .filter(KnowledgeRelation.target_knowledge_id == knowledge_id)
            .all()
        )

    def check_exists(
        self,
        source_id: int,
        target_id: int,
        relation_type: str,
    ) -> bool:
        """Check if a relation already exists."""
        return (
            self.db.query(KnowledgeRelation)
            .filter(
                KnowledgeRelation.source_knowledge_id == source_id,
                KnowledgeRelation.target_knowledge_id == target_id,
                KnowledgeRelation.relation_type == relation_type,
            )
            .first()
            is not None
        )

    def create(
        self,
        source_knowledge_id: int,
        target_knowledge_id: int,
        relation_type: str,
    ) -> KnowledgeRelation:
        """Create a new knowledge relation."""
        relation = KnowledgeRelation(
            source_knowledge_id=source_knowledge_id,
            target_knowledge_id=target_knowledge_id,
            relation_type=relation_type,
        )
        self.db.add(relation)
        self.db.flush()
        return relation

    def delete(self, relation: KnowledgeRelation) -> None:
        """Delete a knowledge relation."""
        self.db.delete(relation)
        self.db.flush()
