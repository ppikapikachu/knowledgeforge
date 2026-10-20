"""题目去重服务管理 API（只读为主，管理员权限）。

职责（加固文档 §2/§6/§11）：
- 查询去重服务就绪状态（initializing/ready/degraded/disabled）与索引统计；
- 查询去重判定审计记录（question_dedup_record），uncertain 可按题目/任务追踪；
- 手动触发题目向量索引重建（必须在 API 服务进程内执行，幂等）。

不暴露向量内容、提示词、API Key 等敏感信息。
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from agent.common.config import agent_settings
from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.models.question import Question
from app.models.question_dedup_record import QuestionDedupRecord
from app.schemas.common import ApiResponse
from app.services.question_normalizer import HASH_VERSION
from app.utils.response import paginated_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/question-dedup", tags=["题目去重"])


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
        code=200,
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
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return paginated_response(items, page, page_size, total)


@router.get("/stats/{task_id}", summary="任务去重统计")
def get_task_dedup_stats(
    task_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """按 decision/decision_method 聚合任务的去重判定（§7.2 对账口径）。"""
    from app.services.question_dedup_service import QuestionDeduplicationService

    service = QuestionDeduplicationService(db)
    return ApiResponse(code=200, message="success", data=service.get_dedup_stats(task_id))


@router.post("/index/rebuild", summary="手动重建题目向量索引")
def rebuild_index(
    only_missing: bool = Query(True, description="仅补齐缺失向量（幂等）"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """在 API 服务进程内重建/补齐题目向量索引（§2.5）。

    FAISS 为进程内存态：外部脚本无法为本进程修复索引，恢复必须走本接口。
    """
    from app.services.question_dedup_service import initialize_question_index

    readiness = initialize_question_index(db, only_missing=only_missing)
    return ApiResponse(code=200, message="success", data=readiness)
