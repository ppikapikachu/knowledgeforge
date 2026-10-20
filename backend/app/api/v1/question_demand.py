"""知识点需求评估、出题策略、智能分配 API。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiResponse
from app.schemas.question_demand import (
    AllocationPreviewRequest,
    AllocationPreviewResponse,
    EffectivePolicyResponse,
    ImportanceLevelInfo,
    PolicyRequest,
    PolicyResponse,
)
from app.services.knowledge_demand_service import IMPORTANCE_LEVELS, KnowledgePointDemandService
from app.services.policy_service import PolicyService

router = APIRouter(prefix="/question-generation", tags=["出题策略与智能分配"])


@router.get(
    "/policies/effective",
    response_model=ApiResponse[EffectivePolicyResponse],
    summary="查询生效策略",
    description="返回题库生效的出题策略。题库无覆盖时返回全局策略。",
)
def get_effective_policy(
    question_bank_id: Optional[int] = Query(default=None, description="题库 ID"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    service = PolicyService(db)
    result = service.get_effective_policy(question_bank_id)
    result["importance_levels"] = [ImportanceLevelInfo(**item) for item in IMPORTANCE_LEVELS]
    return ApiResponse(data=EffectivePolicyResponse(**result))


@router.put(
    "/policies/global",
    response_model=ApiResponse[PolicyResponse],
    summary="保存全局策略",
)
def save_global_policy(
    request: PolicyRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    service = PolicyService(db)
    result = service.save_global_policy(request.model_dump())
    return ApiResponse(data=PolicyResponse(**result))


@router.put(
    "/policies/question-banks/{question_bank_id}",
    response_model=ApiResponse[PolicyResponse],
    summary="保存题库级策略",
)
def save_question_bank_policy(
    question_bank_id: int,
    request: PolicyRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    service = PolicyService(db)
    result = service.save_question_bank_policy(question_bank_id, request.model_dump())
    return ApiResponse(data=PolicyResponse(**result))


@router.delete(
    "/policies/question-banks/{question_bank_id}",
    summary="删除题库级策略覆盖",
)
def delete_question_bank_policy(
    question_bank_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    service = PolicyService(db)
    service.delete_question_bank_policy(question_bank_id)
    return ApiResponse(message="已删除题库级策略，恢复继承全局策略")


@router.post(
    "/allocations/preview",
    response_model=ApiResponse[AllocationPreviewResponse],
    summary="智能分配预览",
    description="只计算、不创建任务、不调用模型、不占用库存。",
)
def preview_allocation(
    request: AllocationPreviewRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    policy_svc = PolicyService(db)
    effective = policy_svc.get_effective_policy(request.question_bank_id)
    policy = effective["policy"]

    if not policy.get("is_enabled", True):
        raise ValidationException("QUESTION_DEMAND_POLICY_DISABLED: 出题策略未启用")

    demand_svc = KnowledgePointDemandService(db)
    result = demand_svc.preview(
        question_bank_id=request.question_bank_id,
        question_type=request.question_type,
        difficulty=request.difficulty,
        count=request.count,
        policy=policy,
    )
    return ApiResponse(data=AllocationPreviewResponse(**result))
