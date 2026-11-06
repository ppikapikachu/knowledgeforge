"""知识点需求评估、出题策略、智能分配 API。"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ValidationException
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.schemas.common import ApiErrorResponse, ApiResponse, DataNull
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

# 错误响应文档（OpenAPI responses；仅文档用途，不改变运行时 HTTP 状态码）。
# 运行时业务异常（40000/40001/40101/40301/40401/40901 等）统一经全局异常处理器以
# HTTP 400 信封返回；请求体校验失败为 HTTP 422（业务码 42201）；系统内部错误为
# HTTP 500（业务码 50000）。
ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（权重和≠100 INVALID_POLICY_WEIGHTS/策略未启用 QUESTION_DEMAND_POLICY_DISABLED）/ 40401 不存在（题库不存在）/ 40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）",
    },
    403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
    422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
    500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
}


@router.get(
    "/policies/effective",
    response_model=ApiResponse[EffectivePolicyResponse],
    responses=ERROR_RESPONSES,
    summary="查询生效策略",
    description=(
        "用途：查询出题策略（知识点需求评估权重、目标库存、用量窗口等）的生效值。\n"
        "调用时机：出题策略配置页打开时、或智能分配前核对策略时调用。\n"
        "参数：question_bank_id 题库ID（可选）——传入则返回该题库级覆盖策略，题库无覆盖时回退全局策略。\n"
        "返回 data 结构：question_bank_id 题库ID（未指定时为 null）/"
        "source 策略来源(global_default 全局默认|question_bank_override 题库覆盖)/"
        "policy 生效策略对象（stock_weight 库存权重/usage_weight 用量权重/importance_weight 重要度权重，"
        "三者和=100；target_stock 目标库存题数；usage_window_days 用量统计窗口天数；recent_answers_per_question_target 每题近期答题目标次数；"
        "usage_extra_ratio 用量加成比例；max_per_knowledge_per_task 单任务单知识点上限；min_demand_score 最低需求分；"
        "is_enabled 是否启用；version 版本号（嵌套在 policy 内，每次保存递增）；updated_at 更新时间）/"
        "importance_levels 可选重要度等级字典（core 重要/important 次要/normal 一般/supplementary 补充）。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：只读查询，可安全重复调用。\n"
        "写库：否。"
    ),
)
def get_effective_policy(
    question_bank_id: Optional[int] = Query(default=None, description="题库 ID（可选）：传入返回题库级覆盖策略，不传或无覆盖时返回全局策略"),
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
    responses=ERROR_RESPONSES,
    summary="保存全局策略",
    description=(
        "用途：保存/更新全局出题策略（智能出题分配规则）。\n"
        "调用时机：出题策略配置页点击保存时调用。\n"
        "请求体（PolicyRequest）：stock_weight/usage_weight/importance_weight 三个权重，和必须=100；"
        "target_stock 目标库存题数；usage_window_days 用量统计窗口天数；recent_answers_per_question_target 每题近期答题目标次数；"
        "usage_extra_ratio 用量加成比例；max_per_knowledge_per_task 单任务单知识点生成上限；min_demand_score 最低需求分；is_enabled 是否启用。\n"
        "业务行为：权重和≠100 返回 40001（INVALID_POLICY_WEIGHTS）；每次保存 version+1。\n"
        "返回 data 结构（PolicyResponse 平铺）：stock_weight/usage_weight/importance_weight 三权重 / target_stock 目标库存题数 / "
        "usage_window_days 用量窗口天数 / recent_answers_per_question_target 每题近期答题目标次数 / usage_extra_ratio 用量加成比例 / "
        "max_per_knowledge_per_task 单任务单知识点上限 / min_demand_score 最低需求分 / is_enabled 是否启用 / "
        "version 递增后的版本号 / updated_at 更新时间。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：非幂等——重复调用会重复递增 version（PUT 为覆盖式保存）。\n"
        "写库：是（question_generation_policy 全局行 upsert）。"
    ),
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
    responses=ERROR_RESPONSES,
    summary="保存题库级策略",
    description=(
        "用途：为单个题库保存策略覆盖（仅覆盖该题库的智能出题分配规则，其余题库仍用全局策略）。\n"
        "调用时机：题库级出题策略配置页保存时调用。\n"
        "路径参数：question_bank_id 题库ID。\n"
        "请求体（PolicyRequest）：同全局策略（三项权重和=100，同校验 INVALID_POLICY_WEIGHTS）。\n"
        "返回 data 结构（PolicyResponse 平铺）：stock_weight/usage_weight/importance_weight 三权重 / target_stock / "
        "usage_window_days / recent_answers_per_question_target / usage_extra_ratio / max_per_knowledge_per_task / "
        "min_demand_score / is_enabled / version 保存递增后的版本号 / updated_at 更新时间。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：非幂等——重复调用递增 version。\n"
        "写库：是（question_generation_policy 题库行 upsert）。"
    ),
)
def save_question_bank_policy(
    question_bank_id: int = Path(..., description="题库 ID，必须为已存在的题库主键，不存在时按参数/资源错误返回"),
    request: PolicyRequest = Body(..., description="题库级策略参数（三项权重和须=100，字段同全局策略）"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    service = PolicyService(db)
    result = service.save_question_bank_policy(question_bank_id, request.model_dump())
    return ApiResponse(data=PolicyResponse(**result))


@router.delete(
    "/policies/question-banks/{question_bank_id}",
    response_model=ApiResponse[DataNull],
    responses=ERROR_RESPONSES,
    summary="删除题库级策略覆盖",
    description=(
        "用途：删除题库级策略覆盖，该题库恢复继承全局策略。\n"
        "调用时机：题库策略页点击\"恢复默认（跟随全局）\"时调用。\n"
        "路径参数：question_bank_id 题库ID。\n"
        "返回 data 结构：无（data=null，message 提示已恢复继承全局策略）。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：幂等——重复删除结果一致。\n"
        "写库：是（物理删除该题库的策略覆盖行；不删除全局策略）。"
    ),
)
def delete_question_bank_policy(
    question_bank_id: int = Path(..., description="题库 ID，必须为已存在的题库主键，不存在时按参数/资源错误返回"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    service = PolicyService(db)
    service.delete_question_bank_policy(question_bank_id)
    return ApiResponse(message="已删除题库级策略，恢复继承全局策略")


@router.post(
    "/allocations/preview",
    response_model=ApiResponse[AllocationPreviewResponse],
    responses=ERROR_RESPONSES,
    summary="智能分配预览",
    description=(
        "用途：按生效策略计算知识点出题数量分配预览（真实执行前的试算）。\n"
        "调用时机：出题配置页点击\"预览分配\"时调用。\n"
        "请求体（AllocationPreviewRequest）：question_bank_id 题库ID / question_type 题型 / difficulty 难度 / count 计划生成总数。\n"
        "业务行为：只计算不创建任务、不调用 LLM、不占用库存；策略未启用返回 40001（QUESTION_DEMAND_POLICY_DISABLED）；"
        "demand_score = stock_score*库存权重/100 + usage_score*用量权重/100 + importance_score*重要度权重/100；分配用最大余数法。\n"
        "返回 data 结构：question_bank_id 题库ID / allocation_mode 分配模式 / requested_count 请求总题数 / "
        "allocatable_count 可分配总题数 / unallocated_count 未能分配的题数（库存不足）/ is_fully_allocatable 是否全部可分配 / "
        "policy_version 策略版本 / summary 汇总信息 / allocations 分配项数组（knowledge_id 知识点ID/knowledge_name 知识点名/"
        "knowledge_base_id/knowledge_base_name/importance_level 重要度/importance_label/published_count/pending_review_count/"
        "reserved_count/recent_used_question_count/recent_answer_count/stock_score/usage_score/importance_score/"
        "demand_score 需求分 0-1/demand_count/allocated_count 分配题数/reason_codes/reason_summary）/ "
        "warnings 预警文案列表（如 NO_KNOWLEDGE_IN_SCOPE）。\n"
        "权限：仅管理员（JWT）。\n"
        "幂等性：只读计算，可安全重复调用。\n"
        "写库：否。"
    ),
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
