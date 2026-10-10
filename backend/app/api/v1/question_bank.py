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
    QuestionBankCreate,
    QuestionBankResponse,
    QuestionBankUpdate,
)
from app.utils.response import paginated_response

router = APIRouter(prefix="/question-banks", tags=["题库管理"])


@router.get("", summary="获取题库列表")
def get_question_bank_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: Optional[str] = Query(default=None, description="名称搜索"),
    status: Optional[int] = Query(default=None, ge=0, le=1, description="状态筛选"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取题库列表，附带题目数量。"""
    repo = QuestionBankRepository(db)
    items, total = repo.get_list(page=page, page_size=page_size, keyword=keyword, status=status)

    qb_ids = [qb.id for qb in items]
    counts = repo.get_question_counts(qb_ids)

    item_data = []
    for qb in items:
        data = QuestionBankResponse.model_validate(qb).model_dump(mode="json")
        data["question_count"] = counts.get(qb.id, 0)
        item_data.append(data)

    return paginated_response(items=item_data, total=total, page=page, page_size=page_size)


@router.get("/{qb_id}", response_model=ApiResponse[QuestionBankResponse], summary="获取题库详情")
def get_question_bank(
    qb_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """获取题库详情。"""
    repo = QuestionBankRepository(db)
    qb = repo.get_by_id(qb_id)
    if not qb:
        raise ResourceNotFoundException("题库", qb_id)

    data = QuestionBankResponse.model_validate(qb).model_dump(mode="json")
    data["question_count"] = repo.get_question_count(qb_id)
    return ApiResponse(data=data)


@router.post("", response_model=ApiResponse[QuestionBankResponse], summary="创建题库")
def create_question_bank(
    request: QuestionBankCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """创建题库。code 创建后不可修改。"""
    repo = QuestionBankRepository(db)
    if repo.get_by_code(request.code):
        raise ValidationException(f"编码 '{request.code}' 已存在")

    qb = repo.create(**request.model_dump())
    db.commit()
    db.refresh(qb)

    data = QuestionBankResponse.model_validate(qb).model_dump(mode="json")
    data["question_count"] = 0
    return ApiResponse(data=data)


@router.put("/{qb_id}", response_model=ApiResponse[QuestionBankResponse], summary="更新题库")
def update_question_bank(
    qb_id: int,
    request: QuestionBankUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """更新题库名称、描述、状态。"""
    repo = QuestionBankRepository(db)
    qb = repo.get_by_id(qb_id)
    if not qb:
        raise ResourceNotFoundException("题库", qb_id)

    qb = repo.update(qb, **request.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(qb)

    data = QuestionBankResponse.model_validate(qb).model_dump(mode="json")
    data["question_count"] = repo.get_question_count(qb_id)
    return ApiResponse(data=data)
