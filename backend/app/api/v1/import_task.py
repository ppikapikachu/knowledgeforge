"""导入任务 API 路由模块。

提供文件上传创建导入任务、查询任务列表/详情、正式执行任务等接口。
"""

import logging
import os

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiResponse
from app.schemas.import_task import ImportTaskResponse
from app.services.import_task_service import ImportTaskService
from app.core.exceptions import ValidationException
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
        # 兜底：使用未分类
        uncategorized = kb_repo.get_by_code("uncategorized")
        knowledge_base_id = uncategorized.id if uncategorized else 1

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
        raise ValidationException(f"文件大小超过限制，最大允许: {max_mb:.0f}MB")

    # 保存文件到 uploads/YYYY/MM/DD/
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
        "执行完整的知识导入流程：解析文档 → LLM 提取 → 去重 → 落库 → Embedding 同步。"
        "任务完成后返回导入统计结果。"
    ),
)
async def run_import_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """正式执行导入任务（完整 AI 导入流程）。"""
    from app.services.knowledge_import_service import KnowledgeImportService

    service = KnowledgeImportService(db)
    result = service.execute_import(task_id)

    return ApiResponse(data=result)


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
