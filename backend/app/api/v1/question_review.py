"""AI 质量审核查询与人工重开 API（管理员权限）。

职责（执行文档 §7）：
- GET /question-reviews/records：查询 AI 审核记录（分页 + 筛选）；
- GET /question-reviews/stats/{task_id}：任务 AI 审核统计；
- POST /question-reviews/questions/{question_id}/reopen：AI 自动驳回的题目重新开启人工复核。

不在此处执行审核本身（审核由生成任务后台流程驱动）；不自动发布/删除题目。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.models.question import Question
from app.models.question_bank import QuestionBank
from app.models.question_generation_task import QuestionGenerationTask
from app.models.question_review_record import QuestionReviewRecord
from app.schemas.common import ApiErrorResponse, ApiResponse, PaginatedData
from app.schemas.question_review import (
    QuestionReviewBatchCreateResponse,
    QuestionReviewBatchDetailResponse,
    QuestionReviewBatchListItem,
    QuestionReviewBatchPreviewResponse,
    QuestionReviewBatchRequest,
    QuestionReviewRecordItem,
    QuestionReviewReopenRequest,
    QuestionReviewReopenResponse,
    QuestionReviewStatsResponse,
)
from app.utils.response import paginated_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/question-reviews", tags=["AI质量审核"])

# 错误响应文档（OpenAPI responses；仅文档用途，不改变运行时 HTTP 状态码）。
# 运行时业务异常（40000/40001/40101/40301/40401/40901 等）统一经全局异常处理器以
# HTTP 400 信封返回；请求体校验失败为 HTTP 422（业务码 42201）；系统内部错误为
# HTTP 500（业务码 50000）。
ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "业务错误（HTTP 400，envelope code 区分）：40001 参数校验（reason 必填且长度 1~1000/最新审核记录非 auto_reject 不允许 reopen/AI 审核未启用/单批超上限/无可执行题目）/ 40401 不存在（题目/生成任务/批次不存在）/ 40901 冲突（已重开或题目已被人工处理/状态并发修改）/ 40101 未认证（管理员令牌无效/过期/管理员不存在/已禁用）",
    },
    403: {"model": ApiErrorResponse, "description": "未提供或非法 Authorization 请求头（HTTP 403）"},
    422: {"model": ApiErrorResponse, "description": "请求参数格式校验失败（HTTP 422，code 42201）"},
    500: {"model": ApiErrorResponse, "description": "系统内部错误（HTTP 500，code 50000）"},
}


@router.get(
    "/records",
    response_model=ApiResponse[PaginatedData[QuestionReviewRecordItem]],
    responses=ERROR_RESPONSES,
    summary="查询 AI 审核记录",
    description=(
        "用途：分页查询 AI 质量审核记录（question_review_record），含题目当前状态/题型/题库名。\n"
        "调用时机：管理端追溯某题审核结论、按任务/批次统计审核结果、排查 auto_reject 误判。\n"
        "权限：管理员 access token。\n"
        "幂等性：只读幂等；筛选条件按 AND 组合。\n"
        "写库：否。\n"
        "返回 data：items 记录列表（id 记录 ID/question_id 题目 ID/generation_task_id 生成任务 ID（可空）/"
        "batch_id 批量批次 ID（可空）/review_round 审核轮次/trigger_source 触发来源 generation_task|manual_batch/"
        "execution_status 执行状态 success|failed|skipped/decision 审核决策 auto_approve|auto_reject|manual_review（skipped 时为空）/"
        "risk_level 风险等级 low|medium|high|unknown/issue_types 问题类型列表/checks 八维检查结果/reason 审核理由/"
        "evidence 证据列表（知识点摘录）/model_name 使用模型/prompt_version 提示词版本/reviewed_content_hash 审核时内容指纹/"
        "duration_ms 审核耗时/error_code、error_message 失败信息/reopened_by、reopened_at、reopen_reason 人工重开信息/"
        "question_status 题目当前状态/question_type 题型/question_bank_name 题库名/created_at 记录时间）/"
        "page 当前页码/page_size 每页条数/total 总条数"
    ),
)
def list_review_records(
    task_id: Optional[int] = Query(None, description="生成任务 ID（可选，按 AI 审核发生的生成任务精确过滤）"),
    question_id: Optional[int] = Query(None, description="题目 ID（可选，按被审核题目精确过滤）"),
    decision: Optional[str] = Query(
        None, description="审核决策筛选（可选）：auto_approve=自动通过、auto_reject=自动驳回、manual_review=转人工"
    ),
    execution_status: Optional[str] = Query(
        None, description="执行状态筛选（可选）：success=审核成功、failed=执行失败、skipped=准入跳过"
    ),
    batch_id: Optional[int] = Query(None, description="批量审核批次 ID（可选，按手动批量审核批次过滤）"),
    trigger_source: Optional[str] = Query(
        None, description="触发来源筛选（可选）：generation_task=生成任务自动审核、manual_batch=人工批量审核"
    ),
    page: int = Query(1, ge=1, description="页码（可选参数，从 1 开始计数，缺省默认第 1 页）"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数（可选，默认 20，取值 1~100）"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """查询 AI 审核记录，含题目当前状态/题型/题库名。筛选条件按 AND 组合。"""
    query = db.query(QuestionReviewRecord)
    if task_id is not None:
        query = query.filter(QuestionReviewRecord.generation_task_id == task_id)
    if question_id is not None:
        query = query.filter(QuestionReviewRecord.question_id == question_id)
    if decision:
        query = query.filter(QuestionReviewRecord.decision == decision)
    if execution_status:
        query = query.filter(QuestionReviewRecord.execution_status == execution_status)
    if batch_id is not None:
        query = query.filter(QuestionReviewRecord.batch_id == batch_id)
    if trigger_source:
        query = query.filter(QuestionReviewRecord.trigger_source == trigger_source)

    total = query.count()
    rows = (
        query.order_by(QuestionReviewRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for r in rows:
        question = db.query(Question).filter(Question.id == r.question_id).first()
        bank_name = None
        if question and question.question_bank_id:
            bank = db.query(QuestionBank).filter(
                QuestionBank.id == question.question_bank_id
            ).first()
            bank_name = bank.name if bank else None
        items.append({
            "id": r.id,
            "question_id": r.question_id,
            "generation_task_id": r.generation_task_id,
            "batch_id": r.batch_id,
            "review_round": r.review_round,
            "trigger_source": r.trigger_source,
            "execution_status": r.execution_status,
            "decision": r.decision,
            "risk_level": r.risk_level,
            "issue_types": r.issue_types or [],
            "checks": r.checks or {},
            "reason": r.reason,
            "evidence": r.evidence or [],
            "model_name": r.model_name,
            "prompt_version": r.prompt_version,
            "reviewed_content_hash": r.reviewed_content_hash,
            "duration_ms": r.duration_ms,
            "error_code": r.error_code,
            "error_message": r.error_message,
            "reopened_by": r.reopened_by,
            "reopened_at": r.reopened_at.isoformat() if r.reopened_at else None,
            "reopen_reason": r.reopen_reason,
            "question_status": question.status if question else None,
            "question_type": question.question_type if question else None,
            "question_bank_name": bank_name,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return paginated_response(items, total, page, page_size)


@router.get(
    "/stats/{task_id}",
    response_model=ApiResponse[QuestionReviewStatsResponse],
    responses=ERROR_RESPONSES,
    summary="获取任务 AI 审核统计",
    description=(
        "用途：获取单个生成任务的 AI 审核统计计数。\n"
        "调用时机：任务详情页展示审核进度与结果分布。\n"
        "权限：管理员 access token。\n"
        "幂等性：只读幂等。\n"
        "写库：否。\n"
        "错误：任务不存在返回 40401。\n"
        "返回 data：task_id 任务 ID/enable_ai_review 任务是否开启 AI 审核/ai_review_status 审核状态 "
        "not_requested|queued|running|completed|partial|failed/ai_review_total_count 进入审核的题目总数/"
        "ai_review_processed_count 已处理数/ai_auto_approved_count 自动通过数/ai_auto_rejected_count 自动驳回数/"
        "ai_manual_review_count 转人工数/ai_review_failed_count 执行失败数/ai_review_skipped_count 准入跳过数（含去重疑点与不支持题型）/"
        "ai_review_pending_count 未处理数"
    ),
)
def get_review_stats(
    task_id: int = Path(..., ge=1, description="生成任务 ID（question_generation_task 主键；不存在返回 40401）"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """任务级 AI 审核统计；任务不存在返回业务错误，无审核数据返回全 0 + not_requested。"""
    from app.core.exceptions import ResourceNotFoundException

    task = db.query(QuestionGenerationTask).filter(
        QuestionGenerationTask.id == task_id
    ).first()
    if not task:
        raise ResourceNotFoundException(f"生成任务 {task_id} 不存在")

    return ApiResponse(code=0, message="success", data={
        "task_id": task_id,
        "enable_ai_review": bool(task.enable_ai_review),
        "ai_review_status": task.ai_review_status or "not_requested",
        "ai_review_total_count": task.ai_review_total_count or 0,
        "ai_review_processed_count": task.ai_review_processed_count or 0,
        "ai_auto_approved_count": task.ai_auto_approved_count or 0,
        "ai_auto_rejected_count": task.ai_auto_rejected_count or 0,
        "ai_manual_review_count": task.ai_manual_review_count or 0,
        "ai_review_failed_count": task.ai_review_failed_count or 0,
        "ai_review_skipped_count": task.ai_review_skipped_count or 0,
        "ai_review_pending_count": task.ai_review_pending_count or 0,
    })


@router.post(
    "/questions/{question_id}/reopen",
    response_model=ApiResponse[QuestionReviewReopenResponse],
    responses=ERROR_RESPONSES,
    summary="AI 驳回题目重新开启人工复核",
    description=(
        "用途：对 AI 自动驳回（auto_reject）的题目重新开启人工复核，回到待审核状态。\n"
        "调用时机：管理端复核发现 AI 误驳回，需要恢复人工审核流程时。\n"
        "权限：管理员 access token（操作人取认证上下文）。\n"
        "幂等性：不幂等可重入——仅最新记录为 auto_reject 且题目当前 rejected 的题允许 reopen；"
        "重复调用返回 40901 冲突（含已由他人 reopen、题目已被人工处理两种情形）。\n"
        "写库：是（条件更新题目 rejected→pending_review，写 reopen 操作人/时间/理由；**不直接发布/不删除题目**，保留 AI 审核证据）。\n"
        "返回 data：question_id 题目 ID/status 重新开启后的状态（pending_review）/reopened_by 操作管理员 ID/"
        "reopen_reason 操作理由/record_id 关联的审核记录 ID（= 既有最新 auto_reject 审核记录 id；"
        "重开不新建审核记录，仅在该记录上回填 reopened_by/reopened_at/reopen_reason）"
    ),
)
def reopen_question(
    question_id: int = Path(..., ge=1, description="题目 ID（question 主键；不存在返回 40401）"),
    request: QuestionReviewReopenRequest = Body(
        ...,
        description="重开请求体：reason 重新开启理由（必填，1~1000 字符，用于审计追溯）",
    ),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """仅允许对最新记录为 auto_reject 且题目当前 rejected 的题重新开启。

    - 回到 pending_review（不直接发布），保留 AI 审核证据；
    - 记录操作管理员/时间/理由；
    - 重复调用返回冲突业务码；已由人工处理（非 rejected）同样冲突。
    """
    from app.core.exceptions import (
        DuplicateException,
        ResourceNotFoundException,
        ValidationException,
    )

    reason = (request.reason or "").strip()
    if not reason or len(reason) > 1000:
        raise ValidationException("reason 必填且长度 1~1000")

    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise ResourceNotFoundException(f"题目 {question_id} 不存在")

    latest = (
        db.query(QuestionReviewRecord)
        .filter(QuestionReviewRecord.question_id == question_id)
        .order_by(QuestionReviewRecord.review_round.desc(), QuestionReviewRecord.id.desc())
        .first()
    )
    if not latest or latest.decision != "auto_reject":
        raise ValidationException(
            f"题目 {question_id} 最新 AI 审核记录不是 auto_reject，不允许 reopen"
        )
    if latest.reopened_by is not None:
        raise DuplicateException(
            f"题目 {question_id} 已由管理员 {latest.reopened_by} 于 "
            f"{latest.reopened_at.isoformat() if latest.reopened_at else '未知时间'} 重新开启，不允许重复操作"
        )
    if question.status != "rejected":
        raise DuplicateException(
            f"题目 {question_id} 当前状态为 {question.status}（已被人工处理），不允许 reopen"
        )

    # 条件更新（原子）：仅当仍为 rejected
    updated = (
        db.query(Question)
        .filter(Question.id == question_id, Question.status == "rejected")
        .update({"status": "pending_review"}, synchronize_session=False)
    )
    if not updated:
        db.rollback()
        raise DuplicateException(f"题目 {question_id} 状态已被并发修改，请刷新后查看")

    latest.reopened_by = current_admin.id
    from sqlalchemy import func
    latest.reopened_at = func.now()
    latest.reopen_reason = reason[:1000]
    db.flush()
    db.refresh(question)

    # 状态同步：回到 pending_review → 登记去重阻断键 + 向量索引
    from app.services.question_dedup_service import sync_question_dedup_state
    sync_question_dedup_state(db, question)
    db.commit()

    return ApiResponse(code=0, message="success", data={
        "question_id": question_id,
        "status": question.status,
        "reopened_by": current_admin.id,
        "reopen_reason": reason[:1000],
        "record_id": latest.id,
    })


# ----------------------------------------------------------------------
# 手动批量 AI 审核（补充开发文档 §6）
# ----------------------------------------------------------------------


def _check_batch_enabled_and_size(ids: list) -> None:
    """批量共用总开关（§4.3）与单批上限（§6.1）。"""
    from agent.common.config import agent_settings
    from app.core.exceptions import ValidationException

    if not agent_settings.QUESTION_AI_REVIEW_ENABLED:
        raise ValidationException(
            "AI 质量审核功能当前未启用（QUESTION_AI_REVIEW_ENABLED=false），"
            "不允许创建/预检批量审核任务"
        )
    max_items = min(agent_settings.QUESTION_AI_REVIEW_BATCH_MAX_ITEMS, 200)
    if len(ids) > max_items:
        raise ValidationException(f"单批题目数量超过上限 {max_items}")


@router.post(
    "/batches/preview",
    response_model=ApiResponse[QuestionReviewBatchPreviewResponse],
    responses=ERROR_RESPONSES,
    summary="批量 AI 审核预检",
    description=(
        "用途：对勾选的题目做批量 AI 审核准入预检，返回每题是否可审核与拦截原因。\n"
        "调用时机：人工审核页勾选题目后、正式创建批量审核前展示预检结果。\n"
        "权限：管理员 access token。\n"
        "幂等性：只读幂等（不建任务、不调 LLM、零持久化）；创建批次时会逐题重新校验，不信任预检结果。\n"
        "写库：否。\n"
        "前置：QUESTION_AI_REVIEW_ENABLED=false 时返回 40001 明确错误；单批上限 min(配置,200) 超限报 40001。\n"
        "返回 data：requested 请求题数/eligible 可审核数/ineligible 拦截数/eligible_question_ids 可审核题目 ID 列表/"
        "items 每题明细（question_id/eligible 是否可审/reason_code 原因码 question_not_found|question_not_pending|"
        "unsupported_question_type|dedup_unresolved|dedup_duplicate|concurrent_review_in_progress/reason 可读文案）"
    ),
)
def preview_review_batch(
    request: QuestionReviewBatchRequest = Body(
        ...,
        description="预检请求体：question_ids 题目 ID 列表（非空、去重保序，单批不超过上限）",
    ),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """预检：不建任务、不调 LLM、不产生持久化。创建时会重新校验（不信任预检结果）。"""
    from app.services.question_review_batch_service import QuestionReviewBatchService

    ids = list(dict.fromkeys(request.question_ids or []))
    _check_batch_enabled_and_size(ids)
    result = QuestionReviewBatchService(db).preview(ids)
    return ApiResponse(code=0, message="success", data=result)


@router.post(
    "/batches",
    response_model=ApiResponse[QuestionReviewBatchCreateResponse],
    responses=ERROR_RESPONSES,
    summary="创建批量 AI 审核任务",
    description=(
        "用途：创建手动批量 AI 审核批次并异步执行（后台线程逐题调 LLM 审核）。\n"
        "调用时机：人工审核页勾选多道待审题，一键批量 AI 审核。\n"
        "权限：管理员 access token（created_by 取认证上下文）。\n"
        "幂等性：同一题不建重复活动项（DB 唯一约束认领，冲突题记 skipped）；批次失败可重新发起新批次。\n"
        "写库：是（创建 question_review_batch/batch_item、审核产生 question_review_record 并按结论流转题目状态）。\n"
        "前置：QUESTION_AI_REVIEW_ENABLED=false 时 40001；无任何可执行题目（accepted=0）报 40001 不创建批次。\n"
        "返回 data：batch_id 批次 ID/status 初始状态 queued/requested 请求题数/accepted 接受执行数/"
        "skipped 创建时即跳过数（含准入不过与并发认领冲突）；执行进度与明细见 GET /batches/{batch_id}"
    ),
)
def create_review_batch(
    request: QuestionReviewBatchRequest = Body(
        ...,
        description="创建请求体：question_ids 题目 ID 列表（非空、去重保序，单批不超过上限）",
    ),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """创建并异步执行批量 AI 审核。

    - 创建时逐题重建校验 + DB 唯一约束认领（活动项冲突→该题 skipped）；
    - 无任何可执行题目（accepted=0）→ 业务错误，不创建批次；
    - 审核在后台线程执行（不阻塞 HTTP 请求，§13）。
    """
    from app.core.exceptions import ValidationException
    from app.services.background_runner import run_review_batch_in_background
    from app.services.question_review_batch_service import QuestionReviewBatchService

    ids = list(dict.fromkeys(request.question_ids or []))
    _check_batch_enabled_and_size(ids)

    service = QuestionReviewBatchService(db)
    result = service.create_batch(ids, created_by=current_admin.id)
    if result.get("error") == "no_eligible_questions" or result.get("accepted", 0) == 0:
        raise ValidationException("没有可执行 AI 审核的题目（均不满足准入条件），未创建批次")

    run_review_batch_in_background(result["batch_id"])
    return ApiResponse(code=0, message="success", data={
        "batch_id": result["batch_id"],
        "status": result["status"],
        "requested": result["requested"],
        "accepted": result["accepted"],
        "skipped": result["skipped"],
    })


@router.get(
    "/batches",
    response_model=ApiResponse[PaginatedData[QuestionReviewBatchListItem]],
    responses=ERROR_RESPONSES,
    summary="批量审核任务列表",
    description=(
        "用途：分页查询手动批量 AI 审核批次列表。\n"
        "调用时机：管理端查看批量审核执行历史与状态。\n"
        "权限：管理员 access token（可查看全部管理员创建的批次）。\n"
        "幂等性：只读幂等；筛选条件按 AND 组合。\n"
        "写库：否。\n"
        "返回 data：items 批次列表（id 批次 ID/status 状态 queued|running|completed|partial|failed（cancelled 为预留枚举，当前不产生）/"
        "total_count 请求题数/accepted_count 认领受理并进入执行的题数（非通过数，通过数见 auto_approved_count）/processed_count 已处理数/auto_approved_count 自动通过数/"
        "auto_rejected_count 自动驳回数/manual_review_count 转人工数/failed_count 执行失败数/skipped_count 跳过数/"
        "pending_count 未处理数/created_by 创建管理员 ID/started_at、finished_at 起止时间/error_message 失败信息/created_at 创建时间/updated_at 更新时间）/"
        "page 当前页码/page_size 每页条数/total 总条数"
    ),
)
def list_review_batches(
    status: Optional[str] = Query(
        None,
        description="批次状态筛选（可选）：queued=待执行、running=执行中、completed=全部完成、partial=部分完成、failed=失败、cancelled=已取消（预留枚举，当前不产生）",
    ),
    created_by: Optional[int] = Query(None, description="创建管理员 ID 筛选（可选，按批次创建人精确过滤）"),
    page: int = Query(1, ge=1, description="页码（可选参数，从 1 开始计数，缺省默认第 1 页）"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数（可选，默认 20，取值 1~100）"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """批次列表（管理员可查看全部；筛选按 AND 组合）。"""
    from app.services.question_review_batch_service import QuestionReviewBatchService

    items, total = QuestionReviewBatchService(db).list_batches(
        status=status, created_by=created_by, page=page, page_size=page_size
    )
    return paginated_response(items, total, page, page_size)


@router.get(
    "/batches/{batch_id}",
    response_model=ApiResponse[QuestionReviewBatchDetailResponse],
    responses=ERROR_RESPONSES,
    summary="批量审核任务详情",
    description=(
        "用途：查看单个批量审核批次的总体统计与逐题执行明细。\n"
        "调用时机：批次执行中/完成后查看进度、审核结论摘要、跳过原因与失败信息。\n"
        "权限：管理员 access token。\n"
        "幂等性：只读幂等。\n"
        "写库：否。\n"
        "错误：批次不存在返回 40401。\n"
        "返回 data：批次总体字段平铺在顶层（与列表项字段一致：id/created_by/status/total_count/accepted_count/processed_count/"
        "auto_approved_count/auto_rejected_count/manual_review_count/failed_count/skipped_count/pending_count/"
        "started_at/finished_at/error_message/created_at/updated_at，无嵌套 batch 对象）/"
        "progress 执行进度（processed 已处理/accepted 认领受理数/pending 未处理）/"
        "items 逐题明细（id 明细行 ID/question_id 题目 ID/question_content 题干摘要（120 字）/question_type 题型/question_status 题目当前状态/"
        "status item 状态 queued|running|completed|failed|skipped/skip_reason 跳过原因码/skip_reason_text 跳过原因文案/"
        "review_record_id 关联审核记录 ID（跳过项为空，不伪造决策记录）/review_decision 审核结论/review_risk_level 风险等级/"
        "review_reason 审核理由/review_issue_types 问题类型/review_evidence_summary 证据摘要（每条截断 120 字）/"
        "error_code、error_message 失败信息/started_at、finished_at 时间）"
    ),
)
def get_review_batch(
    batch_id: int = Path(..., ge=1, description="批量审核批次 ID（question_review_batch 主键；不存在返回 40401）"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """批次总体统计 + 每个题目的执行明细（含审核结论摘要/跳过原因/错误）。"""
    from app.core.exceptions import ResourceNotFoundException
    from app.services.question_review_batch_service import QuestionReviewBatchService

    detail = QuestionReviewBatchService(db).get_batch_detail(batch_id)
    if not detail:
        raise ResourceNotFoundException(f"批量审核任务 {batch_id} 不存在")
    return ApiResponse(code=0, message="success", data=detail)


# §6.6 cancel：本版未提供取消接口——后台执行器暂无安全取消机制（强行取消
# 会与单题审核的条件更新/认领释放逻辑竞争）；批次失败可重新发起新批次。
