"""导入任务 API 路由模块。

提供文件上传创建导入任务、查询任务列表/详情、正式执行任务等接口。
耗时的导入执行在后台线程中运行，不阻塞 API 响应。
"""

import logging
import os

from fastapi import APIRouter, Depends, File, Form, Path, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiErrorResponse, ApiResponse, PaginatedData
from app.schemas.import_task import ImportTaskActionResponse, ImportTaskCreateResponse, ImportTaskResponse
from app.services.background_runner import (
    run_import_in_background,
    run_relations_retry_in_background,
)
from app.services.import_task_service import ImportTaskService
from app.utils.file import get_file_type, get_upload_path, is_allowed_file
from app.utils.response import paginated_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/import-tasks", tags=["导入任务"])

# 错误响应文档（OpenAPI responses；仅文档用途，不改变运行时 HTTP 状态码）。
# 运行时业务异常（40000/40001/40101/40301/40401/40901 等）统一经全局异常处理器以
# HTTP 400 信封返回；请求体校验失败为 HTTP 422（业务码 42201）；系统内部错误为
# HTTP 500（业务码 50000）。
ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（文件名/文件类型/文件大小/知识库校验失败）/ 40401 不存在（导入任务不存在）/ 40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）",
    },
    403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
    422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
    500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
}


@router.post(
    "",
    response_model=ApiResponse[ImportTaskCreateResponse],
    responses=ERROR_RESPONSES,
    summary="上传文件创建导入任务",
    description=(
        "用途：上传文档文件并创建一条导入任务（状态 PENDING，需再调用“正式执行导入任务”才会真正解析入库）。\n"
        "调用时机：管理后台知识导入页选择文件并提交时调用。\n"
        "请求体（multipart/form-data）：\n"
        "  file: 上传文件，仅支持 pdf、docx、txt、md 四种扩展名，大小上限 10MB（MAX_UPLOAD_SIZE），超出或类型不符返回业务错误 40001\n"
        "  knowledge_base_id: 目标知识库ID，可空；不传时归入“未分类”知识库；不存在或已停用的库返回业务错误 40001\n"
        "落盘规则：服务端生成按日期目录保存，相对路径记为 uploads/YYYY/MM/DD/<文件名>（根目录由 UPLOAD_DIR 配置），数据库仅保存相对路径，不存文件内容。\n"
        "返回 data 结构：\n"
        "  task_id: 新建的导入任务ID（后续用它调用执行/详情接口）\n"
        "权限：需要管理员登录。\n"
        "幂等性：非幂等，重复上传会创建多条任务记录；写数据库（新增任务记录）+写磁盘（保存上传文件）。"
    ),
)
async def create_import_task(
    file: UploadFile = File(..., description="上传文件：仅 pdf/docx/txt/md 四种类型，文件名不能为空，大小不超过 10MB"),
    knowledge_base_id: int = Form(default=None, description="目标知识库ID，可空；不传时归入未分类知识库；不存在或已停用时返回业务错误 40001"),
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
    response_model=ApiResponse[PaginatedData[ImportTaskResponse]],
    responses=ERROR_RESPONSES,
    summary="获取导入任务列表",
    description=(
        "用途：分页获取导入任务列表，可按任务状态筛选。\n"
        "调用时机：管理后台知识导入页加载、筛选状态或翻页时调用。\n"
        "返回 data 结构（分页信封）：\n"
        "  items: 任务数组，元素字段（ImportTaskResponse）：\n"
        "  id: 任务ID\n"
        "  file_name: 上传的原始文件名\n"
        "  file_path: 服务端相对存储路径（uploads/YYYY/MM/DD/文件名）\n"
        "  file_size: 文件大小（字节）\n"
        "  file_type: 文件类型（pdf/docx/txt/md）\n"
        "  status: 任务状态（PENDING=待执行，RUNNING=执行中，SUCCESS=成功，PARTIAL_SUCCESS=部分成功，FAILED=失败，CANCELLED=已取消（预留枚举，当前代码不会产生该状态））\n"
        "  progress: 进度百分比 0~100\n"
        "  current_step: 当前执行阶段描述\n"
        "  error_message: 失败原因（无错误时为 null）\n"
        "  created_by: 创建人（管理员ID）\n"
        "  knowledge_base_id: 目标知识库ID\n"
        "  started_at: 开始执行时间\n"
        "  finished_at: 结束时间\n"
        "  created_at: 创建时间\n"
        "  updated_at: 更新时间\n"
        "  total: 满足条件的总条数\n"
        "  page: 当前页码\n"
        "  page_size: 每页数量\n"
        "权限：需要管理员登录。\n"
        "幂等性：只读查询，天然幂等；不写数据库。"
    ),
)
def get_import_task_list(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始递增，默认第 1 页，取值小于 1 时按参数校验错误返回"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数，默认 20，取值范围 1~100，超出范围按参数校验错误返回"),
    status: str = Query(default=None, description="任务状态筛选：PENDING/RUNNING/SUCCESS/PARTIAL_SUCCESS/FAILED/CANCELLED 之一（CANCELLED 为预留枚举，当前数据中不会出现），不传则返回全部状态"),
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
    responses=ERROR_RESPONSES,
    summary="获取导入任务详情",
    description=(
        "用途：按 ID 获取单条导入任务的详细信息（含进度与错误原因）。\n"
        "调用时机：管理后台导入任务详情页打开、执行中轮询进度时调用。\n"
        "请求体：无。\n"
        "返回 data 结构（ImportTaskResponse）：\n"
        "  id: 任务ID\n"
        "  file_name: 上传的原始文件名\n"
        "  file_path: 服务端相对存储路径（uploads/YYYY/MM/DD/文件名）\n"
        "  file_size: 文件大小（字节）\n"
        "  file_type: 文件类型（pdf/docx/txt/md）\n"
        "  status: 任务状态（PENDING/RUNNING/SUCCESS/PARTIAL_SUCCESS/FAILED/CANCELLED，其中 CANCELLED 为预留枚举，当前代码不会产生该状态）\n"
        "  progress: 进度百分比 0~100\n"
        "  current_step: 当前执行阶段描述\n"
        "  error_message: 失败原因（无错误时为 null）\n"
        "  created_by: 创建人（管理员ID）\n"
        "  knowledge_base_id: 目标知识库ID\n"
        "  started_at: 开始执行时间\n"
        "  finished_at: 结束时间\n"
        "  created_at: 创建时间\n"
        "  updated_at: 更新时间\n"
        "权限：需要管理员登录。\n"
        "幂等性：只读查询，天然幂等；不写数据库。\n"
        "错误：任务不存在返回业务错误 40401。"
    ),
)
def get_import_task(
    task_id: int = Path(..., description="导入任务ID，必须为已存在的任务主键，不存在时返回业务错误 40401"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """获取导入任务详情。"""
    service = ImportTaskService(db)
    task = service.get_task(task_id)
    return ApiResponse(data=ImportTaskResponse.model_validate(task))


@router.post(
    "/{task_id}/run",
    response_model=ApiResponse[ImportTaskActionResponse],
    responses={**ERROR_RESPONSES, 200: {"description": "成功（code=0）。业务错误时 HTTP 仍为 200，用 envelope code（如 40401 任务不存在/40001 状态不允许执行）标识，前端须检查 code。"}},
    summary="正式执行导入任务",
    description=(
        "用途：提交后台异步执行完整的知识导入流程（解析文档→抽取知识点→去重入库→知识关联）。立即返回，不阻塞请求。\n"
        "调用时机：管理后台导入任务列表点击“执行”时调用；也用于失败/部分成功任务的重新执行。\n"
        "请求体：无。\n"
        "返回 data 结构：\n"
        "  task_id: 任务ID\n"
        "  status: 固定 ACCEPTED（已受理）\n"
        "  message: 提示信息，提示通过 GET /api/v1/import-tasks/{id} 轮询进度\n"
        "权限：需要管理员登录。\n"
        "幂等性：非幂等；仅任务状态为 PENDING/FAILED/PARTIAL_SUCCESS 时可执行（重复提交执行中任务返回业务错误 40001）；写数据库（任务状态与进度）。\n"
        "错误：任务不存在返回业务错误 40401。执行过程可重复调用本接口重新触发（FAILED/PARTIAL_SUCCESS 状态下），"
        "任务详情的 progress/current_step 反映实时进度。"
    ),
)
async def run_import_task(
    task_id: int = Path(..., description="导入任务ID，必须为已存在的任务主键，不存在时返回业务错误 40401"),
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
    response_model=ApiResponse[ImportTaskActionResponse],
    responses={**ERROR_RESPONSES, 200: {"description": "成功（code=0）。业务错误时 HTTP 仍为 200，用 envelope code（如 40401 任务不存在）标识，前端须检查 code。"}},
    summary="重试关系生成阶段",
    description=(
        "用途：后台重跑知识关联（关系生成）阶段，不重复导入知识，仅补建/重建知识点关系。\n"
        "调用时机：导入任务关系生成阶段失败或关系不完整时，管理后台点击“重试关系”调用。\n"
        "请求体：无。\n"
        "返回 data 结构：\n"
        "  task_id: 任务ID\n"
        "  status: 固定 ACCEPTED（已受理）\n"
        "  message: 提示信息“关系重试已提交后台执行”\n"
        "权限：需要管理员登录。\n"
        "幂等性：非幂等，可多次触发重试（每次都是新的后台执行）；写数据库（知识关系表）。\n"
        "错误：任务不存在返回业务错误 40401。"
    ),
)
async def retry_import_relations(
    task_id: int = Path(..., description="导入任务ID，必须为已存在的任务主键，不存在时返回业务错误 40401"),
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
    response_model=ApiResponse[ImportTaskResponse],
    responses=ERROR_RESPONSES,
    summary="模拟任务进度（测试用）",
    description=(
        "用途：模拟推进导入任务的进度与状态，仅用于前端 UI 测试，不执行真实导入。\n"
        "调用时机：前端联调时模拟 PENDING→RUNNING→SUCCESS 的状态流转；生产环境不应调用。\n"
        "请求体：无。\n"
        "返回 data 结构（ImportTaskResponse）：\n"
        "  id: 任务ID\n"
        "  status: 模拟推进后的任务状态\n"
        "  progress: 模拟推进后的进度百分比\n"
        "  其余字段同任务详情（file_name/file_path/file_size/file_type/current_step/error_message/created_by/knowledge_base_id/started_at/finished_at/created_at/updated_at）\n"
        "权限：需要管理员登录。\n"
        "幂等性：非幂等，每次调用推进一步模拟进度；写数据库（仅任务表模拟字段）。\n"
        "错误：任务不存在返回业务错误 40401。"
    ),
)
def simulate_task_progress(
    task_id: int = Path(..., description="导入任务ID，必须为已存在的任务主键，不存在时返回业务错误 40401"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """模拟任务进度（保留用于前端测试）。"""
    service = ImportTaskService(db)
    task = service.simulate_task_progress(task_id)
    return ApiResponse(data=ImportTaskResponse.model_validate(task))
