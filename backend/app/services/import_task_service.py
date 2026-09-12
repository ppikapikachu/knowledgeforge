"""Import task service."""

import os
from typing import List, Optional, Tuple

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.models.import_task import KnowledgeImportTask
from app.repositories.import_task_repository import ImportTaskRepository
from app.utils.file import (
    get_file_type,
    get_upload_path,
    is_allowed_file,
)


class ImportTaskService:
    """Service for import task business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.task_repo = ImportTaskRepository(db)

    async def create_import_task(
        self,
        file: UploadFile,
        created_by: int,
    ) -> KnowledgeImportTask:
        """Create an import task by uploading a file."""
        # Validate file
        if not file.filename:
            raise ValidationException("文件名不能为空")

        if not is_allowed_file(file.filename):
            raise ValidationException(
                "不支持的文件类型，允许: pdf, docx, txt, md"
            )

        # Read file content to check size
        content = await file.read()
        file_size = len(content)

        if file_size > settings.MAX_UPLOAD_SIZE:
            max_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
            raise ValidationException(
                f"文件大小超过限制，最大允许: {max_mb:.0f}MB"
            )

        # Generate server-side filename and path
        relative_path, full_path = get_upload_path(
            settings.UPLOAD_DIR, file.filename
        )

        # Ensure upload directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Save file
        with open(full_path, "wb") as f:
            f.write(content)

        # Create task record
        task = self.task_repo.create(
            file_name=file.filename,
            file_path=relative_path,
            file_size=file_size,
            file_type=get_file_type(file.filename),
            status="PENDING",
            progress=0,
            created_by=created_by,
        )
        self.db.commit()
        return task

    def get_task(self, task_id: int) -> KnowledgeImportTask:
        """Get import task by ID."""
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise ResourceNotFoundException("导入任务", task_id)
        return task

    def get_task_list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[KnowledgeImportTask], int]:
        """Get import task list."""
        return self.task_repo.get_list(
            page=page,
            page_size=page_size,
            status=status,
        )

    def simulate_task_progress(self, task_id: int) -> KnowledgeImportTask:
        """Simulate task progress for testing.
        
        This is a V1.0 placeholder for future Agent integration.
        """
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise ResourceNotFoundException("导入任务", task_id)

        if task.status == "PENDING":
            self.task_repo.update(
                task,
                status="RUNNING",
                current_step="PARSING",
                progress=10,
            )
        elif task.status == "RUNNING":
            if task.progress < 100:
                new_progress = min(task.progress + 30, 100)
                step = "EXTRACTING_KNOWLEDGE"
                if new_progress >= 70:
                    step = "SAVING"
                if new_progress >= 100:
                    self.task_repo.update(
                        task,
                        status="SUCCESS",
                        current_step="FINISHED",
                        progress=100,
                    )
                else:
                    self.task_repo.update(
                        task,
                        progress=new_progress,
                        current_step=step,
                    )

        self.db.commit()
        return self.task_repo.get_by_id(task_id)
