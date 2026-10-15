"""答题记录 API 路由。"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.admin import AdminUser
from app.models.question import Question
from app.models.question_answer_record import QuestionAnswerRecord
from app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/answers", tags=["答题记录"])


@router.post(
    "/submit",
    summary="提交答题",
    description="用户提交答题，自动判分。支持幂等（相同 idempotency_key 不重复入账）。",
)
async def submit_answer(
    request: dict,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """提交答题并判分。"""
    question_id = request.get("question_id")
    user_answer = request.get("user_answer", "")
    idempotency_key = request.get("idempotency_key")
    time_spent_ms = request.get("time_spent_ms")

    if not question_id:
        return ApiResponse(code=40001, message="question_id 必填", data=None)

    # 检查幂等
    if idempotency_key:
        existing = db.query(QuestionAnswerRecord).filter(
            QuestionAnswerRecord.user_id == current_admin.id,
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
        return ApiResponse(code=40401, message="题目不存在", data=None)
    if question.status != "published":
        return ApiResponse(code=40001, message="题目未发布，不能作答", data=None)

    # 判分
    is_correct = None
    grading_status = "ungraded"

    if question.question_type in ("SINGLE_CHOICE", "MULTIPLE_CHOICE"):
        # 客观题判分
        from app.models.question_option import QuestionOption
        correct_options = db.query(QuestionOption).filter(
            QuestionOption.question_id == question_id,
            QuestionOption.is_correct == 1,
        ).all()
        correct_keys = {o.option_key for o in correct_options}

        user_keys = set(user_answer.split(",")) if user_answer else set()
        user_keys = {k.strip().upper() for k in user_keys if k.strip()}

        is_correct = 1 if user_keys == correct_keys else 0
        grading_status = "graded"

    elif question.question_type == "TRUE_FALSE":
        correct_answer = question.answer.strip().upper()
        is_correct = 1 if user_answer.strip().upper() == correct_answer else 0
        grading_status = "graded"

    elif question.question_type == "SHORT_ANSWER":
        # 简答题不自动判分
        is_correct = None
        grading_status = "ungraded"

    # 保存答题记录
    record = QuestionAnswerRecord(
        question_id=question_id,
        user_id=current_admin.id,
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
    "/statistics/{question_id}",
    summary="获取题目答题统计",
    description="获取题目的正确率、首次作答正确率等统计数据。",
)
def get_answer_statistics(
    question_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
) -> ApiResponse:
    """获取题目答题统计。"""
    from sqlalchemy import func

    # 全部已判分记录
    graded_query = db.query(QuestionAnswerRecord).filter(
        QuestionAnswerRecord.question_id == question_id,
        QuestionAnswerRecord.grading_status == "graded",
    )

    graded_count = graded_query.count()
    correct_count = graded_query.filter(
        QuestionAnswerRecord.is_correct == 1
    ).count()

    # 首次作答正确率
    from sqlalchemy import text as sa_text
    first_attempts = db.execute(sa_text("""
        SELECT is_correct, COUNT(*) as cnt FROM (
            SELECT is_correct, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at ASC) as rn
            FROM question_answer_record
            WHERE question_id = :qid AND grading_status = 'graded'
        ) t WHERE rn = 1
        GROUP BY is_correct
    """), {"qid": question_id}).fetchall()

    first_total = sum(row[1] for row in first_attempts)
    first_correct = sum(row[1] for row in first_attempts if row[0] == 1)

    # 独立用户数
    unique_users = db.query(func.count(func.distinct(
        QuestionAnswerRecord.user_id
    ))).filter(
        QuestionAnswerRecord.question_id == question_id,
        QuestionAnswerRecord.grading_status == "graded",
    ).scalar() or 0

    return ApiResponse(data={
        "graded_attempt_count": graded_count,
        "correct_attempt_count": correct_count,
        "attempt_accuracy": round(correct_count / graded_count, 4) if graded_count > 0 else None,
        "first_attempt_user_count": first_total,
        "first_attempt_correct_count": first_correct,
        "first_attempt_accuracy": round(first_correct / first_total, 4) if first_total > 0 else None,
        "unique_user_count": unique_users,
        "is_sample_sufficient": graded_count >= 20,
    })
