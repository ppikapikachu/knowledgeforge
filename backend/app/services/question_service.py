"""Question service."""

from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import (
    DuplicateException,
    ResourceNotFoundException,
    ValidationException,
)
from app.models.question import Question
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.question_repository import QuestionRepository


class QuestionService:
    """Service for question business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.question_repo = QuestionRepository(db)
        self.knowledge_repo = KnowledgeRepository(db)

    def get_question(self, question_id: int) -> Question:
        """Get question by ID with options and knowledge."""
        question = self.question_repo.get_by_id(question_id)
        if not question:
            raise ResourceNotFoundException("题目", question_id)
        return question

    def get_question_list(
        self,
        page: int = 1,
        page_size: int = 20,
        question_type: Optional[str] = None,
        difficulty: Optional[int] = None,
        status: Optional[str] = None,
        knowledge_id: Optional[int] = None,
        source_type: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[List[Question], int]:
        """Get question list with filters."""
        return self.question_repo.get_list(
            page=page,
            page_size=page_size,
            question_type=question_type,
            difficulty=difficulty,
            status=status,
            knowledge_id=knowledge_id,
            source_type=source_type,
            keyword=keyword,
        )

    def create_question(
        self,
        question_type: str,
        content: str,
        answer: str,
        analysis: Optional[str] = None,
        difficulty: int = 1,
        status: str = "DRAFT",
        source_type: str = "MANUAL",
        quality_score: Optional[float] = None,
        options: Optional[List[dict]] = None,
        knowledge_ids: Optional[List[int]] = None,
    ) -> Question:
        """Create a new question with options and knowledge associations.
        
        This operation is transactional - all or nothing.
        """
        # Validate question type
        valid_types = {
            "SINGLE_CHOICE",
            "MULTIPLE_CHOICE",
            "TRUE_FALSE",
            "SHORT_ANSWER",
        }
        if question_type not in valid_types:
            raise ValidationException(
                f"无效的题型，有效值: {', '.join(valid_types)}"
            )

        # Validate options based on question type
        self._validate_options(question_type, options or [], answer)

        # Validate knowledge IDs exist
        if knowledge_ids:
            for kid in knowledge_ids:
                if not self.knowledge_repo.get_by_id(kid):
                    raise ResourceNotFoundException("知识点", kid)

        # Create question
        question = self.question_repo.create(
            question_type=question_type,
            content=content,
            answer=answer,
            analysis=analysis,
            difficulty=difficulty,
            status=status,
            source_type=source_type,
            quality_score=quality_score,
        )

        # Create options
        if options:
            for opt in options:
                self.question_repo.create_option(
                    question_id=question.id,
                    option_key=opt["option_key"],
                    option_content=opt["option_content"],
                    is_correct=opt.get("is_correct", 0),
                    sort_order=opt.get("sort_order", 0),
                )

        # Create knowledge associations
        if knowledge_ids:
            for kid in knowledge_ids:
                if self.question_repo.check_question_knowledge_exists(
                    question.id, kid
                ):
                    raise DuplicateException(
                        f"题目已关联知识点: {kid}"
                    )
                self.question_repo.create_question_knowledge(
                    question_id=question.id,
                    knowledge_id=kid,
                )

        self.db.commit()
        return self.question_repo.get_by_id(question.id)

    def update_question(
        self,
        question_id: int,
        **kwargs,
    ) -> Question:
        """Update an existing question with options and knowledge.
        
        This operation is transactional.
        """
        question = self.question_repo.get_by_id(question_id)
        if not question:
            raise ResourceNotFoundException("题目", question_id)

        # Extract options and knowledge_ids from kwargs
        options = kwargs.pop("options", None)
        knowledge_ids = kwargs.pop("knowledge_ids", None)

        # If question type is changing, validate
        new_type = kwargs.get("question_type", question.question_type)
        new_answer = kwargs.get("answer", question.answer)
        if options is not None:
            self._validate_options(new_type, options, new_answer)

        # Update question fields
        if kwargs:
            self.question_repo.update(question, **kwargs)

        # Update options if provided
        if options is not None:
            self.question_repo.delete_options(question_id)
            for opt in options:
                self.question_repo.create_option(
                    question_id=question_id,
                    option_key=opt["option_key"],
                    option_content=opt["option_content"],
                    is_correct=opt.get("is_correct", 0),
                    sort_order=opt.get("sort_order", 0),
                )

        # Update knowledge associations if provided
        if knowledge_ids is not None:
            # Validate knowledge IDs exist
            for kid in knowledge_ids:
                if not self.knowledge_repo.get_by_id(kid):
                    raise ResourceNotFoundException("知识点", kid)

            self.question_repo.delete_question_knowledge(question_id)
            for kid in knowledge_ids:
                self.question_repo.create_question_knowledge(
                    question_id=question_id,
                    knowledge_id=kid,
                )

        self.db.commit()
        return self.question_repo.get_by_id(question_id)

    def delete_question(self, question_id: int) -> Question:
        """Disable a question (soft delete)."""
        question = self.question_repo.get_by_id_simple(question_id)
        if not question:
            raise ResourceNotFoundException("题目", question_id)

        disabled = self.question_repo.disable(question)
        self.db.commit()
        return disabled

    def _validate_options(
        self,
        question_type: str,
        options: List[dict],
        answer: str,
    ) -> None:
        """Validate options based on question type."""
        if question_type == "SINGLE_CHOICE":
            if len(options) < 2:
                raise ValidationException("单选题至少需要2个选项")
            correct_count = sum(1 for o in options if o.get("is_correct") == 1)
            if correct_count != 1:
                raise ValidationException("单选题必须有且仅有1个正确答案")

        elif question_type == "MULTIPLE_CHOICE":
            if len(options) < 2:
                raise ValidationException("多选题至少需要2个选项")
            correct_count = sum(1 for o in options if o.get("is_correct") == 1)
            if correct_count < 1:
                raise ValidationException("多选题至少需要1个正确答案")

        elif question_type == "TRUE_FALSE":
            if options:
                raise ValidationException("判断题不应有选项")
            if answer not in ("TRUE", "FALSE"):
                raise ValidationException('判断题答案必须是 "TRUE" 或 "FALSE"')

        elif question_type == "SHORT_ANSWER":
            if options:
                raise ValidationException("简答题不应有选项")

    def count_by_type(self) -> Dict[str, int]:
        """Count questions by type."""
        return self.question_repo.count_by_type()
