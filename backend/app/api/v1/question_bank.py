"""题库 API 路由。"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.repositories.question_bank_repository import QuestionBankRepository
from app.schemas.common import ApiResponse, ApiErrorResponse, PaginatedData
from app.schemas.question_bank import (
    PracticeAvailabilityRequest,
    QuestionBankCreate,
    QuestionBankListItem,
    QuestionBankResponse,
    QuestionBankUpdate,
)
from app.services.question_bank_stats import bank_question_stats
from app.utils.response import paginated_response

router = APIRouter(prefix="/question-banks", tags=["题库管理"])


# 错误响应文档（统一响应信封 {code, message, data}；业务异常经全局异常处理以 HTTP 400 + 业务码 返回）
ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（如编码已存在）/ 40401 不存在（题库不存在）/ "
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


def _bank_payload(qb, stats_entry: Optional[dict], question_count: int) -> dict:
    """题库响应负载：基础字段 + 开放练习 + 统计（一次聚合，禁 N+1）。"""
    data = QuestionBankResponse.model_validate(qb).model_dump(mode="json")
    data["question_count"] = question_count
    stats = stats_entry or {}
    data["is_available_for_practice"] = bool(getattr(qb, "is_available_for_practice", False))
    data["published_question_count"] = stats.get("published_question_count", 0)
    data["pending_review_count"] = stats.get("pending_review_count", 0)
    data["can_assemble"] = data["published_question_count"] > 0
    return data


@router.get(
    "",
    response_model=ApiResponse[PaginatedData[QuestionBankListItem]],
    responses=ERROR_RESPONSES,
    summary="获取题库列表",
    description=(
        "用途：管理端分页获取题库列表，支持按名称搜索和状态筛选。\n"
        "调用时机：后台题库管理页；返回每个题库的题目数量与练习开放统计。\n"
        "权限：管理员 access token。\n"
        "幂等性：只读幂等。\n"
        "写库：否（仅查询）。\n"
        "返回 data：\n"
        "items[].id: 题库 ID\n"
        "items[].code: 稳定唯一标识（创建后不可修改）\n"
        "items[].name: 题库名称\n"
        "items[].description: 内容范围说明\n"
        "items[].status: 启用状态（1=启用，0=停用）\n"
        "items[].is_available_for_practice: 是否开放练习（普通用户可组卷练习）\n"
        "items[].question_count: 题库下题目总数\n"
        "items[].published_question_count: 已发布（可组卷）题目数量\n"
        "items[].pending_review_count: 待审核题目数量\n"
        "items[].can_assemble: 是否可组卷（至少 1 道已发布题）\n"
        "items[].created_at/updated_at: 创建/更新时间\n"
        "page/page_size/total: 分页信封字段"
    ),
)
def get_question_bank_list(
    page: int = Query(default=1, ge=1, description="页码（可选参数，从 1 开始计数，缺省默认第 1 页）"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数（可选参数，默认 20 条，取值范围 1~100）"),
    keyword: Optional[str] = Query(default=None, description="按题库名称模糊搜索的关键字；不传=不按名称筛选"),
    status: Optional[int] = Query(default=None, ge=0, le=1, description="启用状态筛选：1=启用，0=停用；不传=返回全部状态"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取题库列表。"""
    repo = QuestionBankRepository(db)
    items, total = repo.get_list(page=page, page_size=page_size, keyword=keyword, status=status)

    qb_ids = [qb.id for qb in items]
    counts = repo.get_question_counts(qb_ids)
    stats_map = bank_question_stats(db, qb_ids)

    item_data = []
    for qb in items:
        item_data.append(_bank_payload(qb, stats_map.get(qb.id), counts.get(qb.id, 0)))

    return paginated_response(items=item_data, total=total, page=page, page_size=page_size)


@router.get(
    "/{qb_id}",
    response_model=ApiResponse[QuestionBankResponse],
    summary="获取题库详情",
    description=(
        "用途：根据 ID 获取题库详细信息，包含题目数量与练习开放统计。\n"
        "调用时机：后台题库详情页/编辑前回显。\n"
        "权限：管理员 access token。\n"
        "幂等性：只读幂等。\n"
        "写库：否（仅查询）。\n"
        "返回 data：id 题库 ID/code 稳定唯一标识/name 题库名称/description 内容范围说明/status 启用状态（1=启用，0=停用）/"
        "is_available_for_practice 是否开放练习/question_count 题目总数/published_question_count 已发布题目数量/"
        "pending_review_count 待审核题目数量/can_assemble 是否可组卷/created_at updated_at 创建/更新时间"
    ),
)
def get_question_bank(
    qb_id: int = Path(default=..., ge=1, description="题库 ID（正整数），不存在返回 40401"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse[QuestionBankResponse]:
    """获取题库详情。"""
    repo = QuestionBankRepository(db)
    qb = repo.get_by_id(qb_id)
    if not qb:
        raise ResourceNotFoundException("题库", qb_id)

    data = _bank_payload(qb, bank_question_stats(db, [qb_id]).get(qb_id), repo.get_question_count(qb_id))
    return ApiResponse[QuestionBankResponse](data=data)


@router.post(
    "",
    response_model=ApiResponse[QuestionBankResponse],
    summary="创建题库",
    description=(
        "用途：创建新题库；code 创建后不可修改，重复 code 报 40001。\n"
        "调用时机：后台新建题库。\n"
        "权限：管理员 access token。\n"
        "幂等性：非幂等（重复调用将创建多个题库，除非 code 冲突报错）。\n"
        "写库：是（question_bank 插入一行）。\n"
        "返回 data：id 题库 ID/code 稳定唯一标识/name 题库名称/description 内容范围说明/status 启用状态/"
        "is_available_for_practice 是否开放练习/question_count 题目总数（新库为 0）/published_question_count 已发布题目数量/"
        "pending_review_count 待审核题目数量/can_assemble 是否可组卷/created_at updated_at 创建/更新时间"
    ),
)
def create_question_bank(
    request: QuestionBankCreate = Body(
        default=...,
        description="创建内容：code 稳定唯一标识（创建后不可修改）、name 显示名称、description 内容范围说明（可选）、"
        "is_available_for_practice 是否开放练习（可选，默认不开放）",
    ),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse[QuestionBankResponse]:
    """创建题库。"""
    repo = QuestionBankRepository(db)
    if repo.get_by_code(request.code):
        raise ValidationException(f"编码 '{request.code}' 已存在")

    qb = repo.create(**request.model_dump())
    db.commit()
    db.refresh(qb)

    data = _bank_payload(qb, bank_question_stats(db, [qb.id]).get(qb.id), 0)
    return ApiResponse[QuestionBankResponse](data=data)


@router.put(
    "/{qb_id}",
    response_model=ApiResponse[QuestionBankResponse],
    summary="更新题库",
    description=(
        "用途：修改题库名称、描述、启用状态与练习开放；code 不可修改。\n"
        "调用时机：后台编辑题库；只更新传入的字段（exclude_unset）。\n"
        "权限：管理员 access token。\n"
        "幂等性：幂等覆盖（重复提交相同内容无副作用）。\n"
        "写库：是（question_bank 字段更新）。\n"
        "返回 data：id 题库 ID/code 稳定唯一标识/name 题库名称/description 内容范围说明/status 启用状态/"
        "is_available_for_practice 是否开放练习/question_count 题目总数/published_question_count 已发布题目数量/"
        "pending_review_count 待审核题目数量/can_assemble 是否可组卷/created_at updated_at 创建/更新时间"
    ),
)
def update_question_bank(
    qb_id: int = Path(default=..., ge=1, description="题库 ID（正整数），不存在返回 40401"),
    request: QuestionBankUpdate = Body(
        default=...,
        description="更新内容（仅传需修改的字段）：name 显示名称、description 内容范围说明、status 启用状态（1=启用，0=停用）、"
        "is_available_for_practice 是否开放练习（关闭只挡未来组卷，不删历史试卷与会话）",
    ),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse[QuestionBankResponse]:
    """更新题库。"""
    repo = QuestionBankRepository(db)
    qb = repo.get_by_id(qb_id)
    if not qb:
        raise ResourceNotFoundException("题库", qb_id)

    qb = repo.update(qb, **request.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(qb)

    data = _bank_payload(qb, bank_question_stats(db, [qb_id]).get(qb_id), repo.get_question_count(qb_id))
    return ApiResponse[QuestionBankResponse](data=data)


@router.patch(
    "/{qb_id}/practice-availability",
    response_model=ApiResponse[QuestionBankResponse],
    summary="开关题库练习开放",
    description=(
        "用途：管理端设置题库是否开放练习（普通用户组卷入口的唯一开关）。\n"
        "调用时机：后台控制哪些题库对普通用户开放组卷；关闭只影响未来的组卷请求，不删除历史试卷与练习会话。\n"
        "权限：管理员 access token。\n"
        "幂等性：幂等（重复设置同一值无副作用）。\n"
        "写库：是（question_bank.is_available_for_practice）。\n"
        "返回 data：id 题库 ID/code 稳定唯一标识/name 题库名称/description 内容范围说明/status 启用状态/"
        "is_available_for_practice 是否开放练习（本次设置结果）/question_count 题目总数/published_question_count 已发布题目数量/"
        "pending_review_count 待审核题目数量/can_assemble 是否可组卷/created_at updated_at 创建/更新时间"
    ),
)
def update_practice_availability(
    qb_id: int = Path(default=..., ge=1, description="题库 ID（正整数），不存在返回 40401"),
    request: PracticeAvailabilityRequest = Body(
        default=...,
        description="开关设置（is_available_for_practice：true=开放练习，false=关闭；关闭只挡未来组卷，不删历史数据）",
    ),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse[QuestionBankResponse]:
    """开关题库练习开放（管理端）。"""
    repo = QuestionBankRepository(db)
    qb = repo.get_by_id(qb_id)
    if not qb:
        raise ResourceNotFoundException("题库", qb_id)

    qb.is_available_for_practice = bool(request.is_available_for_practice)
    db.commit()
    db.refresh(qb)

    data = _bank_payload(qb, bank_question_stats(db, [qb_id]).get(qb_id), repo.get_question_count(qb_id))
    return ApiResponse[QuestionBankResponse](data=data)
