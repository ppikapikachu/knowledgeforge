"""答题记录 API 路由（兼容层）。

docs/14 §5.8 兼容约定：
    - 旧 POST /answers/submit 保留：身份必须是真实普通用户（AppUser），
      app_user_id 如实写入；practice_paper_id / practice_paper_item_id /
      practice_session_id 可为 NULL（该接口不参与练习会话）
    - 旧 GET /answers/statistics/{question_id} 保留，统计改由
      StatisticsService 统一口径（样本阈值配置化）
    - 新增 GET /answers/history、GET /answers/{id}（按 app_user_id 过滤）

练习会话内的提交请走 POST /practice/sessions/{sid}/items/{pid}/submit
（以快照标准答案判分）。
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.dependencies.auth import get_current_admin, get_current_principal, get_current_user
from app.models.admin import AdminUser
from app.models.app_user import AppUser
from app.models.question import Question
from app.models.question_answer_record import QuestionAnswerRecord
from app.schemas.common import ApiResponse
from app.services.statistics_service import StatisticsService
from app.utils.response import paginated_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/answers", tags=["答题记录"])


@router.post(
    "/submit",
    summary="提交答题（兼容旧接口）",
    description="普通用户提交答题，自动判分（无快照，按当前题目判分）。"
                "支持幂等（相同 idempotency_key 不重复入账）。"
                "练习会话请使用 /practice/sessions/{sid}/items/{pid}/submit。",
)
async def submit_answer(
    request: dict,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> ApiResponse:
    """提交答题并判分（兼容旧接口，身份为真实普通用户）。"""
    question_id = request.get("question_id")
    user_answer = request.get("user_answer", "")
    idempotency_key = request.get("idempotency_key")
    time_spent_ms = request.get("time_spent_ms")

    if not question_id:
        raise ValidationException("question_id 必填")

    # 检查幂等（同一用户 + 题目 + 幂等键）
    if idempotency_key:
        existing = db.query(QuestionAnswerRecord).filter(
            QuestionAnswerRecord.app_user_id == current_user.id,
            QuestionAnswerRecord.question_id == question_id,
            QuestionAnswerRecord.idempotency_key == idempotency_key,
        ).first()
        if existing:
            return ApiResponse(data={
                "record_id": existing.id,
                "is_correct": existing.is_correct,
                "grading_status": existing.grading_status,
                "idempotent": True,
            })

    # 获取题目
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise ResourceNotFoundException("题目不存在")
    if question.status != "published":
        raise ValidationException("题目未发布，不能作答")

    # 判分（兼容旧接口无快照，按当前题目判定；**统一复用 judge() 判分服务，无分叉**）
    # docs/14 §9.7：新旧接口共用同一判分 Service，避免规则漂移。
    from app.services.grading_service import judge as judge_answer

    if question.question_type in ("SINGLE_CHOICE", "MULTIPLE_CHOICE"):
        from app.models.question_option import QuestionOption
        options = db.query(QuestionOption).filter(
            QuestionOption.question_id == question_id,
        ).all()
        correct_keys = {o.option_key for o in options if o.is_correct}
        snapshot = {
            "question_type": question.question_type,
            "correct_answer": ",".join(sorted(correct_keys)),
            "options": [
                {
                    "option_key": o.option_key,
                    "option_content": o.option_content,
                    "is_correct": bool(o.is_correct),
                }
                for o in options
            ],
        }
    else:
        snapshot = {
            "question_type": question.question_type,
            "correct_answer": (question.answer or "").strip(),
            "options": [],
        }

    verdict = judge_answer(snapshot, user_answer)
    is_correct = (
        1 if verdict["is_correct"] is True
        else (0 if verdict["is_correct"] is False else None)
    )
    grading_status = verdict["grading_status"]
    user_answer = verdict["user_answer_text"] or user_answer

    # 保存答题记录（app_user_id 如实写入；不参与练习会话，paper/item/session 为空）
    record = QuestionAnswerRecord(
        question_id=question_id,
        user_id=current_user.id,
        app_user_id=current_user.id,
        user_answer=user_answer,
        is_correct=is_correct,
        grading_status=grading_status,
        time_spent_ms=time_spent_ms,
        idempotency_key=idempotency_key,
        created_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return ApiResponse(data={
        "record_id": record.id,
        "is_correct": record.is_correct,
        "grading_status": record.grading_status,
    })


@router.get(
    "/history",
    summary="我的答题历史",
    description="按当前普通用户分页查询答题记录，可按题目/练习会话过滤。",
)
def get_answer_history(
    question_id: int | None = Query(default=None),
    practice_session_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    query = db.query(QuestionAnswerRecord).filter(
        QuestionAnswerRecord.app_user_id == current_user.id
    )
    if question_id is not None:
        query = query.filter(QuestionAnswerRecord.question_id == question_id)
    if practice_session_id is not None:
        query = query.filter(
            QuestionAnswerRecord.practice_session_id == practice_session_id
        )
    query = query.order_by(QuestionAnswerRecord.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return paginated_response(
        [_answer_dict(r) for r in rows], total, page, page_size
    )


@router.get(
    "/{record_id}",
    summary="查看单条答题记录",
    description="仅可查看本人的答题记录。",
)
def get_answer_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> ApiResponse:
    record = db.query(QuestionAnswerRecord).filter(
        QuestionAnswerRecord.id == record_id,
        QuestionAnswerRecord.app_user_id == current_user.id,
    ).first()
    if record is None:
        raise ResourceNotFoundException("答题记录不存在")
    return ApiResponse(data=_answer_dict(record))


@router.get(
    "/statistics/{question_id}",
    summary="获取题目答题统计（兼容旧接口）",
    description="获取题目的正确率、首次作答正确率等统计数据（统一口径，样本阈值配置化）。",
)
def get_answer_statistics(
    question_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """获取题目答题统计（兼容旧字段名 + 统一口径新字段）。"""
    stats = StatisticsService(db).question_statistics(question_id)
    # 兼容旧响应字段名
    return ApiResponse(data={
        "graded_attempt_count": stats["graded_submission_count"],
        "correct_attempt_count": stats["correct_submission_count"],
        "attempt_accuracy": stats["accuracy"],
        "first_attempt_user_count": stats["first_attempt_total"],
        "first_attempt_correct_count": stats["first_attempt_correct"],
        "first_attempt_accuracy": stats["first_attempt_accuracy"],
        "unique_user_count": stats["unique_user_count"],
        "is_sample_sufficient": stats["display_status"] == "available",
        # 新增统一口径字段
        "accuracy": stats["accuracy"],
        "display_status": stats["display_status"],
        "sample_threshold": stats["sample_threshold"],
    })


def _answer_dict(record: QuestionAnswerRecord) -> dict:
    return {
        "id": record.id,
        "question_id": record.question_id,
        "user_answer": record.user_answer,
        "is_correct": record.is_correct,
        "grading_status": record.grading_status,
        "score": float(record.score) if record.score is not None else None,
        "time_spent_ms": record.time_spent_ms,
        "practice_paper_id": record.practice_paper_id,
        "practice_paper_item_id": record.practice_paper_item_id,
        "practice_session_id": record.practice_session_id,
        "idempotency_key": record.idempotency_key,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
