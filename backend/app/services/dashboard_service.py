"""Dashboard service."""

from typing import Dict

from sqlalchemy.orm import Session

from app.repositories.import_task_repository import ImportTaskRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.question_repository import QuestionRepository


class DashboardService:
    """Service for dashboard statistics."""

    def __init__(self, db: Session):
        self.db = db
        self.knowledge_repo = KnowledgeRepository(db)
        self.question_repo = QuestionRepository(db)
        self.import_task_repo = ImportTaskRepository(db)

    def get_overview(self) -> Dict:
        """Get dashboard overview statistics."""
        knowledge_count = self.knowledge_repo.count()
        question_count = self.question_repo.count()
        type_counts = self.question_repo.count_by_type()
        import_task_count = self.import_task_repo.count()

        return {
            "knowledge_count": knowledge_count,
            "question_count": question_count,
            "single_choice_count": type_counts.get("SINGLE_CHOICE", 0),
            "multiple_choice_count": type_counts.get("MULTIPLE_CHOICE", 0),
            "true_false_count": type_counts.get("TRUE_FALSE", 0),
            "short_answer_count": type_counts.get("SHORT_ANSWER", 0),
            "import_task_count": import_task_count,
        }
