"""题库 API 路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.repositories.question_bank_repository import QuestionBankRepository
from app.schemas.common import ApiResponse
from app.schemas.question_bank import (
    PracticeAvailabilityRequest,
    QuestionBankCreate,
    QuestionBankResponse,
    QuestionBankUpdate,
)
from app.services.question_bank_stats import bank_question_stats
from app.utils.response import paginated_response

router = APIRouter(prefix="/question-banks", tags=["题库管理"])


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
    summary="获取题库列表",
    description="分页获取题库列表，支持按名称搜索和状态筛选。返回每个题库的题目数量。",
)
def get_question_bank_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(default=None, description="按名称搜索"),
    status: Optional[int] = Query(default=None, ge=0, le=1, description="状态: 1=启用, 0=停用"),
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
    description="根据 ID 获取题库详细信息，包含题目数量。",
)
def get_question_bank(
    qb_id: int,
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
    description="创建新题库。code 创建后不可修改。",
)
def create_question_bank(
    request: QuestionBankCreate,
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
    description="修改题库名称、描述、启用状态。code 不可修改。",
)
def update_question_bank(
    qb_id: int,
    request: QuestionBankUpdate,
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
        "管理端设置题库是否开放练习（普通用户组卷入口的唯一开关）。"
        "关闭只影响未来的组卷请求，不删除历史试卷与练习会话。"
    ),
)
def update_practice_availability(
    qb_id: int,
    request: PracticeAvailabilityRequest,
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
