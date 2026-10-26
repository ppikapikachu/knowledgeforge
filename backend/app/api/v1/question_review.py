"""AI 质量审核查询与人工重开 API（管理员权限）。

职责（执行文档 §7）：
- GET /question-reviews/records：查询 AI 审核记录（分页 + 筛选）；
- GET /question-reviews/stats/{task_id}：任务 AI 审核统计；
- POST /question-reviews/questions/{question_id}/reopen：AI 自动驳回的题目重新开启人工复核。

不在此处执行审核本身（审核由生成任务后台流程驱动）；不自动发布/删除题目。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.models.question import Question
from app.models.question_bank import QuestionBank
from app.models.question_generation_task import QuestionGenerationTask
from app.models.question_review_record import QuestionReviewRecord
from app.schemas.common import ApiResponse
from app.schemas.question_review import QuestionReviewBatchRequest, QuestionReviewReopenRequest
from app.utils.response import paginated_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/question-reviews", tags=["AI质量审核"])


@router.get("/records", summary="查询 AI 审核记录")
def list_review_records(
    task_id: Optional[int] = Query(None, description="生成任务 ID"),
    question_id: Optional[int] = Query(None, description="题目 ID"),
    decision: Optional[str] = Query(
        None, description="审核决策 auto_approve/auto_reject/manual_review"
    ),
    execution_status: Optional[str] = Query(
        None, description="执行状态 success/failed/skipped"
    ),
    batch_id: Optional[int] = Query(None, description="批量审核批次 ID（补充开发）"),
    trigger_source: Optional[str] = Query(
        None, description="触发来源 generation_task/manual_batch（补充开发）"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
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


@router.get("/stats/{task_id}", summary="获取任务 AI 审核统计")
def get_review_stats(
    task_id: int,
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


@router.post("/questions/{question_id}/reopen", summary="AI 驳回题目重新开启人工复核")
def reopen_question(
    question_id: int,
    request: QuestionReviewReopenRequest,
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


@router.post("/batches/preview", summary="批量 AI 审核预检")
def preview_review_batch(
    request: QuestionReviewBatchRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """预检：不建任务、不调 LLM、不产生持久化。创建时会重新校验（不信任预检结果）。"""
    from app.services.question_review_batch_service import QuestionReviewBatchService

    ids = list(dict.fromkeys(request.question_ids or []))
    _check_batch_enabled_and_size(ids)
    result = QuestionReviewBatchService(db).preview(ids)
    return ApiResponse(code=0, message="success", data=result)


@router.post("/batches", summary="创建批量 AI 审核任务")
def create_review_batch(
    request: QuestionReviewBatchRequest,
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


@router.get("/batches", summary="批量审核任务列表")
def list_review_batches(
    status: Optional[str] = Query(
        None, description="批次状态 queued/running/completed/partial/failed/cancelled"
    ),
    created_by: Optional[int] = Query(None, description="创建管理员 ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """批次列表（管理员可查看全部；筛选按 AND 组合）。"""
    from app.services.question_review_batch_service import QuestionReviewBatchService

    items, total = QuestionReviewBatchService(db).list_batches(
        status=status, created_by=created_by, page=page, page_size=page_size
    )
    return paginated_response(items, total, page, page_size)


@router.get("/batches/{batch_id}", summary="批量审核任务详情")
def get_review_batch(
    batch_id: int,
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
