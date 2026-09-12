"""Import task repository."""

from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.import_task import KnowledgeImportTask


class ImportTaskRepository:
    """Repository for import task database operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, task_id: int) -> Optional[KnowledgeImportTask]:
        """Get import task by ID."""
        return (
            self.db.query(KnowledgeImportTask)
            .filter(KnowledgeImportTask.id == task_id)
            .first()
        )

    def get_list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[KnowledgeImportTask], int]:
        """Get import task list with filters and pagination."""
        query = self.db.query(KnowledgeImportTask)

        if status:
            query = query.filter(KnowledgeImportTask.status == status)

        total = query.count()
        items = (
            query.order_by(KnowledgeImportTask.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def create(self, **kwargs) -> KnowledgeImportTask:
        """Create a new import task."""
        task = KnowledgeImportTask(**kwargs)
        self.db.add(task)
        self.db.flush()
        return task

    def update(self, task: KnowledgeImportTask, **kwargs) -> KnowledgeImportTask:
        """Update an import task."""
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        self.db.flush()
        return task

    def count(self, status: Optional[str] = None) -> int:
        """Count import tasks."""
        query = self.db.query(func.count(KnowledgeImportTask.id))
        if status:
            query = query.filter(KnowledgeImportTask.status == status)
        return query.scalar() or 0
