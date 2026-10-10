"""导入任务 API 路由模块。

提供文件上传创建导入任务、查询任务列表/详情、正式执行任务等接口。
耗时的导入执行在后台线程中运行，不阻塞 API 响应。
"""

import logging
import os

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiResponse
from app.schemas.import_task import ImportTaskResponse
from app.services.background_runner import (
    run_import_in_background,
    run_relations_retry_in_background,
)
from app.services.import_task_service import ImportTaskService
from app.utils.file import get_file_type, get_upload_path, is_allowed_file
from app.utils.response import paginated_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/import-tasks", tags=["导入任务"])


@router.post(
    "",
    summary="上传文件创建导入任务",
    description="上传文档文件（pdf/docx/txt/md）创建导入任务。",
)
async def create_import_task(
    file: UploadFile = File(..., description="上传文件"),
    knowledge_base_id: int = Form(default=None, description="目标知识库 ID（不传时使用未分类）"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """创建导入任务：保存文件 + 创建任务记录（状态 PENDING）。"""
    if not file.filename:
        raise ValidationException("文件名不能为空")

    if not is_allowed_file(file.filename):
        raise ValidationException("不支持的文件类型，允许: pdf, docx, txt, md")

    # 校验知识库
    from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
    kb_repo = KnowledgeBaseRepository(db)

    if knowledge_base_id is not None:
        kb = kb_repo.get_by_id(knowledge_base_id)
        if not kb:
            raise ValidationException(f"知识库 {knowledge_base_id} 不存在")
        if kb.status == 0:
            raise ValidationException(f"知识库 '{kb.name}' 已停用，不能作为导入目标")
    else:
        uncategorized = kb_repo.get_by_code("uncategorized")
        knowledge_base_id = uncategorized.id if uncategorized else 1

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
        raise ValidationException(f"文件大小超过限制，最大允许: {max_mb:.0f}MB")

    # 保存文件
    relative_path, full_path = get_upload_path(settings.UPLOAD_DIR, file.filename)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(content)

    # 创建任务记录
    from app.models.import_task import KnowledgeImportTask
    task = KnowledgeImportTask(
        file_name=file.filename,
        file_path=relative_path,
        file_size=len(content),
        file_type=get_file_type(file.filename),
        status="PENDING",
        progress=0,
        created_by=current_admin.id,
        knowledge_base_id=knowledge_base_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    logger.info(f"导入任务创建: id={task.id}, file={file.filename}")
    return ApiResponse(data={"task_id": task.id})


@router.get(
    "",
    summary="获取导入任务列表",
    description="分页获取导入任务列表。",
)
def get_import_task_list(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取导入任务列表。"""
    service = ImportTaskService(db)
    items, total = service.get_task_list(page=page, page_size=page_size, status=status)
    item_data = [ImportTaskResponse.model_validate(t).model_dump(mode="json") for t in items]
    return paginated_response(items=item_data, total=total, page=page, page_size=page_size)


@router.get(
    "/{task_id}",
    response_model=ApiResponse[ImportTaskResponse],
    summary="获取导入任务详情",
    description="根据 ID 获取导入任务详细信息。",
)
def get_import_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """获取导入任务详情。"""
    service = ImportTaskService(db)
    task = service.get_task(task_id)
    return ApiResponse(data=ImportTaskResponse.model_validate(task))


@router.post(
    "/{task_id}/run",
    summary="正式执行导入任务",
    description=(
        "后台异步执行完整的知识导入流程。立即返回任务 ID，"
        "通过 GET /{task_id} 查询进度和结果。"
    ),
)
async def run_import_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """提交导入任务到后台执行（立即返回，不阻塞）。"""
    from app.models.import_task import KnowledgeImportTask

    # 校验任务存在
    task = db.query(KnowledgeImportTask).filter(
        KnowledgeImportTask.id == task_id
    ).first()
    if not task:
        return ApiResponse(code=40401, message=f"任务 {task_id} 不存在", data=None)

    if task.status not in ("PENDING", "FAILED", "PARTIAL_SUCCESS"):
        return ApiResponse(
            code=40001,
            message=f"任务当前状态为 {task.status}，无法执行",
            data=None,
        )

    # 提交后台执行（立即返回）
    run_import_in_background(task_id)

    return ApiResponse(data={
        "task_id": task_id,
        "status": "ACCEPTED",
        "message": "任务已提交后台执行，请通过 GET /api/v1/import-tasks/{id} 查询进度",
    })


@router.post(
    "/{task_id}/relations/retry",
    summary="重试关系生成阶段",
    description="后台重跑关系生成阶段，不重复导入知识。",
)
async def retry_import_relations(
    task_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """提交关系重试到后台执行。"""
    from app.models.import_task import KnowledgeImportTask

    task = db.query(KnowledgeImportTask).filter(
        KnowledgeImportTask.id == task_id
    ).first()
    if not task:
        return ApiResponse(code=40401, message=f"任务 {task_id} 不存在", data=None)

    run_relations_retry_in_background(task_id)

    return ApiResponse(data={
        "task_id": task_id,
        "status": "ACCEPTED",
        "message": "关系重试已提交后台执行",
    })


@router.post(
    "/{task_id}/simulate",
    summary="模拟任务进度（测试用）",
    description="模拟推进导入任务进度，仅用于前端 UI 测试。",
)
def simulate_task_progress(
    task_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """模拟任务进度（保留用于前端测试）。"""
    service = ImportTaskService(db)
    task = service.simulate_task_progress(task_id)
    return ApiResponse(data=ImportTaskResponse.model_validate(task))
