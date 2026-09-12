"""Knowledge service."""

from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import (
    DuplicateException,
    ResourceNotFoundException,
    ValidationException,
)
from app.models.knowledge import Knowledge
from app.repositories.knowledge_relation_repository import KnowledgeRelationRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.question_repository import QuestionRepository


class KnowledgeService:
    """Service for knowledge business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.knowledge_repo = KnowledgeRepository(db)
        self.relation_repo = KnowledgeRelationRepository(db)
        self.question_repo = QuestionRepository(db)

    def get_knowledge(self, knowledge_id: int) -> Knowledge:
        """Get knowledge by ID."""
        knowledge = self.knowledge_repo.get_by_id(knowledge_id)
        if not knowledge:
            raise ResourceNotFoundException("知识点", knowledge_id)
        return knowledge

    def get_knowledge_list(
        self,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        difficulty: Optional[int] = None,
        status: Optional[int] = None,
    ) -> Tuple[List[Knowledge], int]:
        """Get knowledge list with filters."""
        return self.knowledge_repo.get_list(
            page=page,
            page_size=page_size,
            keyword=keyword,
            difficulty=difficulty,
            status=status,
        )

    def create_knowledge(self, **kwargs) -> Knowledge:
        """Create a new knowledge point."""
        knowledge = self.knowledge_repo.create(**kwargs)
        self.db.commit()
        return knowledge

    def update_knowledge(self, knowledge_id: int, **kwargs) -> Knowledge:
        """Update an existing knowledge point."""
        knowledge = self.knowledge_repo.get_by_id(knowledge_id)
        if not knowledge:
            raise ResourceNotFoundException("知识点", knowledge_id)

        updated = self.knowledge_repo.update(knowledge, **kwargs)
        self.db.commit()
        return updated

    def delete_knowledge(self, knowledge_id: int) -> Knowledge:
        """Disable a knowledge point (soft delete)."""
        knowledge = self.knowledge_repo.get_by_id(knowledge_id)
        if not knowledge:
            raise ResourceNotFoundException("知识点", knowledge_id)

        disabled = self.knowledge_repo.disable(knowledge)
        self.db.commit()
        return disabled

    def get_knowledge_relations(self, knowledge_id: int) -> List:
        """Get all relations for a knowledge point."""
        # Verify knowledge exists
        knowledge = self.knowledge_repo.get_by_id(knowledge_id)
        if not knowledge:
            raise ResourceNotFoundException("知识点", knowledge_id)

        relations = self.relation_repo.get_by_source(knowledge_id)
        # Enrich with target knowledge names
        for rel in relations:
            target = self.knowledge_repo.get_by_id(rel.target_knowledge_id)
            rel.target_knowledge_name = target.name if target else None
        return relations

    def create_knowledge_relation(
        self,
        source_id: int,
        target_id: int,
        relation_type: str,
    ):
        """Create a knowledge relation with validation."""
        # Validate source exists
        source = self.knowledge_repo.get_by_id(source_id)
        if not source:
            raise ResourceNotFoundException("源知识点", source_id)

        # Validate target exists
        target = self.knowledge_repo.get_by_id(target_id)
        if not target:
            raise ResourceNotFoundException("目标知识点", target_id)

        # Prevent self-relation
        if source_id == target_id:
            raise ValidationException("知识点不能关联自己")

        # Validate relation type
        valid_types = {"prerequisite", "related", "extension", "contrast"}
        if relation_type not in valid_types:
            raise ValidationException(
                f"无效的关系类型，有效值: {', '.join(valid_types)}"
            )

        # Check for duplicate
        if self.relation_repo.check_exists(source_id, target_id, relation_type):
            raise DuplicateException("该知识关系已存在")

        relation = self.relation_repo.create(
            source_knowledge_id=source_id,
            target_knowledge_id=target_id,
            relation_type=relation_type,
        )
        self.db.commit()
        return relation

    def delete_knowledge_relation(
        self, knowledge_id: int, relation_id: int
    ) -> None:
        """Delete a knowledge relation."""
        relation = self.relation_repo.get_by_id(relation_id)
        if not relation:
            raise ResourceNotFoundException("知识关系", relation_id)

        # Verify the relation belongs to the given knowledge
        if relation.source_knowledge_id != knowledge_id:
            raise ValidationException("该关系不属于此知识点")

        self.relation_repo.delete(relation)
        self.db.commit()
