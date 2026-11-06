"""知识库 API 路由。"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.common import ApiResponse, ApiErrorResponse, PaginatedData
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListItem,
    KnowledgeBaseResponse,
    KnowledgeBaseStatusUpdate,
    KnowledgeBaseUpdate,
)
from app.utils.response import paginated_response

router = APIRouter(prefix="/knowledge-bases", tags=["知识库管理"])


# 错误响应文档（统一响应信封 {code, message, data}；业务异常经全局异常处理以 HTTP 400 + 业务码 返回）
ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验 / 40401 不存在（知识库不存在）/ "
        "40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）",
    },
    403: {
        "model": ApiErrorResponse,
        "description": "未提供或非法 Authorization 请求头（HTTP 403）",
    },
    422: {
        "model": ApiErrorResponse,
        "description": "请求参数格式校验失败（HTTP 422，code 42201）",
    },
    500: {
        "model": ApiErrorResponse,
        "description": "系统内部错误（HTTP 500，code 50000），data 恒为 null",
    },
}


@router.get(
    "",
    response_model=ApiResponse[PaginatedData[KnowledgeBaseListItem]],
    responses=ERROR_RESPONSES,
    summary="获取知识库列表",
    description=(
        "用途：分页获取知识库列表，附带每个知识库的知识点数量。\n"
        "调用时机：管理后台知识库管理页加载、筛选状态或翻页时调用。\n"
        "返回 data 结构（分页信封）：\n"
        "  items: 知识库数组，元素字段：\n"
        "  id: 知识库ID\n"
        "  code: 稳定编码（创建后不可修改，如 android、java）\n"
        "  name: 展示名称\n"
        "  description: 简介\n"
        "  status: 状态（1=正常，0=停用）\n"
        "  knowledge_count: 该知识库下的知识点数量\n"
        "  created_at: 创建时间\n"
        "  updated_at: 更新时间\n"
        "  total: 满足条件的总条数\n"
        "  page: 当前页码\n"
        "  page_size: 每页数量\n"
        "权限：需要管理员登录（Authorization: Bearer 管理员 access token）。\n"
        "幂等性：只读查询，天然幂等；不写数据库。"
    ),
)
def get_knowledge_base_list(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始递增，默认第 1 页，取值小于 1 时按参数校验错误返回"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数，默认 20，取值范围 1~100，超出范围按参数校验错误返回"),
    status: Optional[int] = Query(default=None, ge=0, le=1, description="状态筛选：1=正常，0=停用，不传则返回全部状态的记录"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取知识库列表。"""
    repo = KnowledgeBaseRepository(db)
    items, total = repo.get_list(page=page, page_size=page_size, status=status)

    kb_ids = [kb.id for kb in items]
    counts = repo.get_knowledge_counts(kb_ids)

    item_data = []
    for kb in items:
        data = KnowledgeBaseResponse.model_validate(kb).model_dump(mode="json")
        data["knowledge_count"] = counts.get(kb.id, 0)
        item_data.append(data)

    return paginated_response(items=item_data, total=total, page=page, page_size=page_size)


@router.get(
    "/{kb_id}",
    response_model=ApiResponse[KnowledgeBaseResponse],
    summary="获取知识库详情",
    description=(
        "用途：按 ID 获取单个知识库的详细信息。\n"
        "调用时机：管理后台知识库详情页打开、编辑前回显数据时调用。\n"
        "请求体：无。\n"
        "返回 data 结构：\n"
        "  id: 知识库ID\n"
        "  code: 稳定编码（创建后不可修改）\n"
        "  name: 展示名称\n"
        "  description: 简介\n"
        "  status: 状态（1=正常，0=停用）\n"
        "  knowledge_count: 该知识库下的知识点数量\n"
        "  created_at: 创建时间\n"
        "  updated_at: 更新时间\n"
        "权限：需要管理员登录。\n"
        "幂等性：只读查询，天然幂等；不写数据库。\n"
        "错误：知识库不存在返回业务错误 40401。"
    ),
)
def get_knowledge_base(
    kb_id: int = Path(..., description="知识库ID，必须为已存在的知识库主键，不存在时返回业务错误 40401"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """获取知识库详情。"""
    repo = KnowledgeBaseRepository(db)
    kb = repo.get_by_id(kb_id)
    if not kb:
        raise ResourceNotFoundException("知识库", kb_id)

    data = KnowledgeBaseResponse.model_validate(kb).model_dump(mode="json")
    data["knowledge_count"] = repo.get_knowledge_count(kb_id)
    return ApiResponse(data=data)


@router.post(
    "",
    response_model=ApiResponse[KnowledgeBaseResponse],
    summary="创建知识库",
    description=(
        "用途：创建一个新的知识库，code 创建后不可修改。\n"
        "调用时机：管理后台知识库列表点击“新建”提交表单时调用。\n"
        "请求体（KnowledgeBaseCreate）：\n"
        "  code: 稳定编码，必填，全局唯一，如 android、java\n"
        "  name: 展示名称，必填\n"
        "  description: 简介，可空\n"
        "返回 data 结构：\n"
        "  id: 新知识库ID\n"
        "  code: 稳定编码\n"
        "  name: 展示名称\n"
        "  description: 简介\n"
        "  status: 状态（新建时为 1=正常）\n"
        "  knowledge_count: 知识点数量（新建时为 0）\n"
        "  created_at: 创建时间\n"
        "  updated_at: 更新时间\n"
        "权限：需要管理员登录。\n"
        "幂等性：非幂等，重复调用会创建多条记录；写数据库。\n"
        "错误：code 已存在时返回业务错误 40001。"
    ),
)
def create_knowledge_base(
    request: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """创建知识库。code 创建后不可修改。"""
    repo = KnowledgeBaseRepository(db)

    # 检查 code 唯一
    if repo.get_by_code(request.code):
        raise ValidationException(f"编码 '{request.code}' 已存在")

    kb = repo.create(**request.model_dump())
    db.commit()
    db.refresh(kb)

    data = KnowledgeBaseResponse.model_validate(kb).model_dump(mode="json")
    data["knowledge_count"] = 0
    return ApiResponse(data=data)


@router.put(
    "/{kb_id}",
    response_model=ApiResponse[KnowledgeBaseResponse],
    summary="更新知识库",
    description=(
        "用途：修改知识库的展示名称与简介；code 为稳定标识，创建后不可修改。\n"
        "调用时机：管理后台知识库列表点击“编辑”提交表单时调用。\n"
        "请求体（KnowledgeBaseUpdate）：\n"
        "  name: 展示名称，必填\n"
        "  description: 简介，可空\n"
        "返回 data 结构：\n"
        "  id: 知识库ID\n"
        "  code: 稳定编码（本次不会被修改）\n"
        "  name: 更新后的展示名称\n"
        "  description: 更新后的简介\n"
        "  status: 状态（1=正常，0=停用，本次不改变）\n"
        "  knowledge_count: 该知识库下的知识点数量\n"
        "  created_at: 创建时间\n"
        "  updated_at: 更新时间\n"
        "权限：需要管理员登录。\n"
        "幂等性：同一请求体重复提交结果一致（幂等）；写数据库。\n"
        "错误：知识库不存在返回业务错误 40401。"
    ),
)
def update_knowledge_base(
    kb_id: int = Path(..., description="知识库ID，必须为已存在的知识库主键，不存在时返回业务错误 40401"),
    request: KnowledgeBaseUpdate = Body(..., description="知识库更新字段（name/description 等，仅传入的字段被更新）"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """更新知识库。"""
    repo = KnowledgeBaseRepository(db)
    kb = repo.get_by_id(kb_id)
    if not kb:
        raise ResourceNotFoundException("知识库", kb_id)

    kb = repo.update(kb, **request.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(kb)

    data = KnowledgeBaseResponse.model_validate(kb).model_dump(mode="json")
    data["knowledge_count"] = repo.get_knowledge_count(kb_id)
    return ApiResponse(data=data)


@router.patch(
    "/{kb_id}/status",
    response_model=ApiResponse[KnowledgeBaseResponse],
    summary="停用/启用知识库",
    description=(
        "用途：启用或停用知识库。停用后不能作为新导入目标，但旧知识仍可查看。\n"
        "调用时机：管理后台知识库列表的状态开关切换时调用。\n"
        "请求体（KnowledgeBaseStatusUpdate）：\n"
        "  status: 目标状态，1=正常（启用），0=停用\n"
        "返回 data 结构：\n"
        "  id: 知识库ID\n"
        "  code: 稳定编码\n"
        "  name: 展示名称\n"
        "  description: 简介\n"
        "  status: 更新后的状态（1=正常，0=停用）\n"
        "  knowledge_count: 该知识库下的知识点数量\n"
        "  created_at: 创建时间\n"
        "  updated_at: 更新时间\n"
        "权限：需要管理员登录。\n"
        "幂等性：重复设置为同一状态结果一致（幂等）；写数据库。\n"
        "错误：知识库不存在返回业务错误 40401；status 不是 0/1 时返回业务错误 40001。"
    ),
)
def update_knowledge_base_status(
    kb_id: int = Path(..., description="知识库ID，必须为已存在的知识库主键，不存在时返回业务错误 40401"),
    request: KnowledgeBaseStatusUpdate = Body(..., description="状态设置：status 取 active|disabled 之一"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """停用/启用知识库。"""
    repo = KnowledgeBaseRepository(db)
    kb = repo.get_by_id(kb_id)
    if not kb:
        raise ResourceNotFoundException("知识库", kb_id)

    kb = repo.update(kb, status=request.status)
    db.commit()
    db.refresh(kb)

    data = KnowledgeBaseResponse.model_validate(kb).model_dump(mode="json")
    data["knowledge_count"] = repo.get_knowledge_count(kb_id)
    return ApiResponse(data=data)
