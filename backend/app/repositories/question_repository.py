"""Question repository."""

from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.question import Question
from app.models.question_knowledge import QuestionKnowledge
from app.models.question_option import QuestionOption


class QuestionRepository:
    """Repository for question database operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, question_id: int) -> Optional[Question]:
        """Get question by ID with options and knowledge."""
        return (
            self.db.query(Question)
            .options(
                joinedload(Question.options),
                joinedload(Question.knowledge_associations),
            )
            .filter(Question.id == question_id)
            .first()
        )

    def get_by_id_simple(self, question_id: int) -> Optional[Question]:
        """Get question by ID without relations."""
        return (
            self.db.query(Question)
            .filter(Question.id == question_id)
            .first()
        )

    def get_list(
        self,
        page: int = 1,
        page_size: int = 20,
        question_type: Optional[str] = None,
        difficulty: Optional[int] = None,
        status: Optional[str] = None,
        knowledge_id: Optional[int] = None,
        question_bank_id: Optional[int] = None,
        source_type: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[List[Question], int]:
        """Get question list with filters and pagination."""
        query = self.db.query(Question)

        if question_type:
            query = query.filter(Question.question_type == question_type)
        if difficulty is not None:
            query = query.filter(Question.difficulty == difficulty)
        if status:
            query = query.filter(Question.status == status)
        if question_bank_id is not None:
            query = query.filter(Question.question_bank_id == question_bank_id)
        if source_type:
            query = query.filter(Question.source_type == source_type)
        if keyword:
            query = query.filter(Question.content.contains(keyword))
        if knowledge_id:
            query = query.join(QuestionKnowledge).filter(
                QuestionKnowledge.knowledge_id == knowledge_id
            )

        total = query.distinct().count()
        items = (
            query.order_by(Question.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def create(self, **kwargs) -> Question:
        """Create a new question."""
        question = Question(**kwargs)
        self.db.add(question)
        self.db.flush()
        return question

    def update(self, question: Question, **kwargs) -> Question:
        """Update an existing question."""
        for key, value in kwargs.items():
            if value is not None and hasattr(question, key):
                setattr(question, key, value)
        self.db.flush()
        return question

    def disable(self, question: Question) -> Question:
        """Disable a question (soft delete)."""
        question.status = "disabled"
        self.db.flush()
        return question

    def count(
        self,
        status: Optional[str] = None,
        question_type: Optional[str] = None,
    ) -> int:
        """Count questions."""
        query = self.db.query(func.count(Question.id))
        if status:
            query = query.filter(Question.status == status)
        if question_type:
            query = query.filter(Question.question_type == question_type)
        return query.scalar() or 0

    def count_by_type(self) -> dict:
        """Count questions grouped by type."""
        results = (
            self.db.query(
                Question.question_type,
                func.count(Question.id),
            )
            .group_by(Question.question_type)
            .all()
        )
        return {r[0]: r[1] for r in results}

    # Option operations
    def get_options(self, question_id: int) -> List[QuestionOption]:
        """Get all options for a question."""
        return (
            self.db.query(QuestionOption)
            .filter(QuestionOption.question_id == question_id)
            .order_by(QuestionOption.sort_order)
            .all()
        )

    def create_option(self, **kwargs) -> QuestionOption:
        """Create a question option."""
        option = QuestionOption(**kwargs)
        self.db.add(option)
        self.db.flush()
        return option

    def delete_options(self, question_id: int) -> None:
        """Delete all options for a question."""
        self.db.query(QuestionOption).filter(
            QuestionOption.question_id == question_id
        ).delete()
        self.db.flush()

    # Question-Knowledge operations
    def get_knowledge_ids(self, question_id: int) -> List[int]:
        """Get knowledge IDs associated with a question."""
        results = (
            self.db.query(QuestionKnowledge.knowledge_id)
            .filter(QuestionKnowledge.question_id == question_id)
            .all()
        )
        return [r[0] for r in results]

    def create_question_knowledge(
        self, question_id: int, knowledge_id: int
    ) -> QuestionKnowledge:
        """Create a question-knowledge association."""
        qk = QuestionKnowledge(
            question_id=question_id,
            knowledge_id=knowledge_id,
        )
        self.db.add(qk)
        self.db.flush()
        return qk

    def delete_question_knowledge(self, question_id: int) -> None:
        """Delete all question-knowledge associations for a question."""
        self.db.query(QuestionKnowledge).filter(
            QuestionKnowledge.question_id == question_id
        ).delete()
        self.db.flush()

    def check_question_knowledge_exists(
        self, question_id: int, knowledge_id: int
    ) -> bool:
        """Check if a question-knowledge association exists."""
        return (
            self.db.query(QuestionKnowledge)
            .filter(
                QuestionKnowledge.question_id == question_id,
                QuestionKnowledge.knowledge_id == knowledge_id,
            )
            .first()
            is not None
        )
