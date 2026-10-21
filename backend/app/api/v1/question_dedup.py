"""题目去重服务管理 API（只读为主，管理员权限）。

职责（加固文档 §2/§6/§11）：
- 查询去重服务就绪状态（initializing/ready/degraded/disabled）与索引统计；
- 查询去重判定审计记录（question_dedup_record），uncertain 可按题目/任务追踪；
- 手动触发题目向量索引重建（必须在 API 服务进程内执行，幂等）。

不暴露向量内容、提示词、API Key 等敏感信息。
"""

import logging
import threading
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from agent.common.config import agent_settings
from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.models.question import Question
from app.models.question_dedup_record import QuestionDedupRecord
from app.schemas.common import ApiResponse
from app.schemas.question_dedup import QuestionDedupResolveRequest
from app.services.question_normalizer import HASH_VERSION
from app.utils.response import paginated_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/question-dedup", tags=["题目去重"])

# 进程内重建互斥：重建期间重复点击返回冲突，不并发重建
_rebuild_lock = threading.Lock()
_rebuild_in_progress = False


@router.get("/status", summary="获取去重服务状态")
def get_dedup_status(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """去重服务就绪状态 + 向量索引统计 + 当前阈值（管理端可观测，§2.3/§11）。"""
    from app.services.question_dedup_service import get_dedup_readiness

    readiness = get_dedup_readiness()
    blocking_count = (
        db.query(Question.id)
        .filter(Question.status.in_(("pending_review", "published")))
        .count()
    )
    return ApiResponse(
        code=0,
        message="success",
        data={
            "enabled": agent_settings.QUESTION_DEDUP_ENABLED,
            "status": readiness.get("status"),
            "reason": readiness.get("reason"),
            "stats": readiness.get("stats") or {},
            "failures": readiness.get("failures") or [],
            "blocking_question_count": blocking_count,
            "thresholds": {
                "same_scope_candidate_threshold": agent_settings.QUESTION_DEDUP_SAME_SCOPE_CANDIDATE_THRESHOLD,
                "cross_scope_high_threshold": agent_settings.QUESTION_DEDUP_CROSS_SCOPE_HIGH_THRESHOLD,
                "final_block_threshold": agent_settings.QUESTION_DEDUP_FINAL_BLOCK_THRESHOLD,
                "vector_top_k": agent_settings.QUESTION_DEDUP_VECTOR_TOP_K,
                "keyword_top_k": agent_settings.QUESTION_DEDUP_KEYWORD_TOP_K,
                "llm_max_candidates_per_question": agent_settings.QUESTION_DEDUP_LLM_MAX_CANDIDATES,
                "llm_batch_size": agent_settings.QUESTION_DEDUP_LLM_BATCH_SIZE,
            },
            "hash_version": HASH_VERSION,
        },
    )


@router.get("/records", summary="查询去重判定审计记录")
def list_dedup_records(
    task_id: int | None = Query(None, description="生成任务 ID"),
    question_id: int | None = Query(None, description="题目 ID（新题或匹配题）"),
    decision: str | None = Query(None, description="duplicate|distinct|uncertain"),
    needs_manual_review: bool | None = Query(None, description="仅需人工复核的记录"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """分页查询 question_dedup_record（uncertain 按题目/任务可追踪，§6）。"""
    from app.core.exceptions import ValidationException

    if decision is not None and decision not in ("duplicate", "distinct", "uncertain"):
        raise ValidationException("decision 必须是 duplicate/distinct/uncertain")

    query = db.query(QuestionDedupRecord)
    if task_id is not None:
        query = query.filter(QuestionDedupRecord.task_id == task_id)
    if question_id is not None:
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            from app.core.exceptions import ResourceNotFoundException
            raise ResourceNotFoundException(f"题目 {question_id} 不存在")
        query = query.filter(
            (QuestionDedupRecord.matched_question_id == question_id)
            | (QuestionDedupRecord.new_content_hash == (question.content_hash or ""))
        )
    if decision is not None:
        query = query.filter(QuestionDedupRecord.decision == decision)
    if needs_manual_review is not None:
        query = query.filter(QuestionDedupRecord.needs_manual_review == int(needs_manual_review))

    total = query.count()
    rows = (
        query.order_by(QuestionDedupRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": r.id,
            "task_id": r.task_id,
            "new_content_hash": r.new_content_hash,
            "new_hash_version": r.new_hash_version,
            "new_question_type": r.new_question_type,
            "new_question_bank_id": r.new_question_bank_id,
            "new_knowledge_ids": r.new_knowledge_ids,
            "new_content_snapshot": r.new_content_snapshot,
            "matched_question_id": r.matched_question_id,
            "matched_question_bank_id": r.matched_question_bank_id,
            "matched_knowledge_ids": r.matched_knowledge_ids,
            "matched_source": r.matched_source,
            "scope_mode": r.scope_mode,
            "keyword_score": r.keyword_score,
            "vector_score": r.vector_score,
            "algorithm_score": r.algorithm_score,
            "llm_called": bool(r.llm_called),
            "llm_decision": r.llm_decision,
            "llm_reason": r.llm_reason,
            "decision": r.decision,
            "decision_method": r.decision_method,
            "needs_manual_review": bool(r.needs_manual_review),
            "manual_resolution": r.manual_resolution,
            "effective_decision": r.manual_resolution or r.decision,
            "resolution_reason": r.resolution_reason,
            "resolved_by": r.resolved_by,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return paginated_response(items, total, page, page_size)


@router.post(
    "/records/{record_id}/resolve",
    summary="人工复核去重记录",
    response_model=None,
)
def resolve_dedup_record(
    record_id: int,
    payload: QuestionDedupResolveRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """记录管理员对一条去重疑点的人工结论与理由（API 执行文档 §3）。

    职责边界：只记录人工去重结论，**不自动驳回、不下架、不删除题目**；
    题目生命周期仍走原有审核流程（§3.6）。

    状态与并发（§3.5）：
    - 仅 decision=uncertain 且未处理的记录允许首次 resolve；
    - 处理后 needs_manual_review=false，但原始自动判定证据（decision/
      llm_decision/算法分数/匹配题 ID）全部保留；
    - 重复提交/并发处理通过条件更新（`UPDATE ... WHERE manual_resolution IS NULL`）
      在数据库层面保证只有一个首次处理成功，另一个得到 40901 冲突；
    - effective_decision = manual_resolution or decision（派生，不落库）。
    """
    from app.core.exceptions import (
        DuplicateException,
        ResourceNotFoundException,
        ValidationException,
    )

    reason = (payload.reason or "").strip()
    if not reason:
        raise ValidationException("reason 不能为空（去除首尾空白后必须非空）")
    if len(reason) > 1000:
        raise ValidationException("reason 最长 1000 字符")

    record = (
        db.query(QuestionDedupRecord)
        .filter(QuestionDedupRecord.id == record_id)
        .first()
    )
    if not record:
        raise ResourceNotFoundException(f"去重记录 {record_id} 不存在")

    if record.decision != "uncertain":
        raise DuplicateException(
            f"记录 {record_id} 的自动判定结论为 {record.decision}，无需人工复核"
        )
    if record.manual_resolution is not None:
        raise DuplicateException(
            f"记录 {record_id} 已由管理员 {record.resolved_by} 于 "
            f"{record.resolved_at.isoformat() if record.resolved_at else '未知时间'} "
            f"处理为 {record.manual_resolution}，不允许覆盖；如需改判请走带审计的重新打开流程"
        )

    # 条件更新实现并发安全的首次处理（事务内原子，§3.5.3/§4.5/§4.6）
    updated = (
        db.query(QuestionDedupRecord)
        .filter(
            QuestionDedupRecord.id == record_id,
            QuestionDedupRecord.manual_resolution.is_(None),
        )
        .update(
            {
                "manual_resolution": payload.conclusion,
                "resolution_reason": reason,
                "resolved_by": current_admin.id,
                "resolved_at": func.now(),
                "needs_manual_review": False,
            },
            synchronize_session=False,
        )
    )
    if updated == 0:
        db.rollback()
        raise DuplicateException("该记录已被其他管理员处理，不允许覆盖")

    db.commit()
    db.refresh(record)
    return ApiResponse(
        code=0,
        message="success",
        data={
            "id": record.id,
            "decision": record.decision,
            "manual_resolution": record.manual_resolution,
            "effective_decision": record.manual_resolution or record.decision,
            "needs_manual_review": bool(record.needs_manual_review),
            "resolution_reason": record.resolution_reason,
            "resolved_by": record.resolved_by,
            "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
        },
    )


@router.get("/stats/{task_id}", summary="任务去重统计")
def get_task_dedup_stats(
    task_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """按 decision/decision_method 聚合任务的去重判定（§7.2 对账口径）。"""
    from app.core.exceptions import ResourceNotFoundException
    from app.models.question_generation_task import QuestionGenerationTask
    from app.services.question_dedup_service import QuestionDeduplicationService

    task = db.query(QuestionGenerationTask).filter(QuestionGenerationTask.id == task_id).first()
    if not task:
        raise ResourceNotFoundException(f"任务 {task_id} 不存在")

    service = QuestionDeduplicationService(db)
    return ApiResponse(code=0, message="success", data=service.get_dedup_stats(task_id))


@router.post("/index/rebuild", summary="手动重建题目向量索引")
def rebuild_index(
    only_missing: bool = Query(True, description="仅补齐缺失向量（幂等）"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """在 API 服务进程内重建/补齐题目向量索引（§2.5）。

    FAISS 为进程内存态：外部脚本无法为本进程修复索引，恢复必须走本接口。
    重建期间的重复调用返回 40901 冲突（并发保护，§2.4）。
    """
    global _rebuild_in_progress
    from app.core.exceptions import DuplicateException
    from app.services.question_dedup_service import initialize_question_index

    if not _rebuild_lock.acquire(blocking=False):
        raise DuplicateException("题目向量索引正在重建中，请稍后重试")
    _rebuild_in_progress = True
    try:
        readiness = initialize_question_index(db, only_missing=only_missing)
    finally:
        _rebuild_in_progress = False
        _rebuild_lock.release()
    return ApiResponse(code=0, message="success", data=readiness)
