"""Import task API router."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiResponse
from app.schemas.import_task import ImportTaskResponse
from app.services.import_task_service import ImportTaskService
from app.utils.response import paginated_response

router = APIRouter(prefix="/import-tasks", tags=["导入任务"])


@router.post(
    "",
    summary="上传文件创建导入任务",
    description="上传文档文件（pdf/docx/txt/md）创建导入任务。",
)
async def create_import_task(
    file: UploadFile = File(..., description="上传文件"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Create an import task by uploading a file."""
    service = ImportTaskService(db)
    task = await service.create_import_task(
        file=file,
        created_by=current_admin.id,
    )
    return ApiResponse(data={"task_id": task.id})


@router.get(
    "",
    summary="获取导入任务列表",
    description="分页获取导入任务列表。",
)
def get_import_task_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(default=None, description="任务状态"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get import task list with pagination."""
    service = ImportTaskService(db)
    items, total = service.get_task_list(
        page=page,
        page_size=page_size,
        status=status,
    )
    item_data = [ImportTaskResponse.model_validate(t).model_dump(mode="json") for t in items]
    return paginated_response(
        items=item_data,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{task_id}",
    response_model=ApiResponse[ImportTaskResponse],
    summary="获取导入任务详情",
    description="根据ID获取导入任务详细信息。",
)
def get_import_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Get import task by ID."""
    service = ImportTaskService(db)
    task = service.get_task(task_id)
    return ApiResponse(data=ImportTaskResponse.model_validate(task))


@router.post(
    "/{task_id}/simulate",
    response_model=ApiResponse[ImportTaskResponse],
    summary="模拟任务进度（测试用）",
    description="模拟推进导入任务进度，仅用于V1.0测试。",
)
def simulate_task_progress(
    task_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """Simulate task progress for testing."""
    service = ImportTaskService(db)
    task = service.simulate_task_progress(task_id)
    return ApiResponse(data=ImportTaskResponse.model_validate(task))
