"""统计服务：个人统计 / 题目统计（口径 A-F）。

口径（docs/14 §6）：
    A 全部提交正确率 = 有效 graded 提交中正确的 / 全部 graded 提交（同题多次计多次）
    B 首次作答正确率 = 每用户每题首次 graded 提交的正确率
    C 提交次数 = graded 提交总数
    D 独立用户数 = 不同 app_user_id 数
    样本不足（graded 提交数 < QUESTION_STATISTICS_MIN_SAMPLES）时
    accuracy 返回 None 且 display_status="insufficient_samples"

统计只做聚合查询，不建缓存表，不暴露任何用户信息。
仅统计 app_user_id 非空的记录（真实普通用户行为）；
历史 user_id（管理员）兼容行不纳入新口径。
"""

from typing import Any, Dict, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.app_user import AppUser
from app.models.practice_session import PracticeSession
from app.models.question import Question
from app.models.question_answer_record import QuestionAnswerRecord


def _display_status(graded_count: int) -> str:
    return (
        "insufficient_samples"
        if graded_count < settings.QUESTION_STATISTICS_MIN_SAMPLES
        else "available"
    )


class StatisticsService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== 题目统计（口径 A-D） ====================

    def question_statistics(self, question_id: int) -> dict:
        question = self.db.query(Question).get(question_id)
        if question is None:
            return {
                "question_id": question_id,
                "accuracy": None,
                "first_attempt_accuracy": None,
                "unique_user_count": 0,
                "graded_submission_count": 0,
                "display_status": "insufficient_samples",
                "sample_threshold": settings.QUESTION_STATISTICS_MIN_SAMPLES,
            }

        base = self.db.query(QuestionAnswerRecord).filter(
            QuestionAnswerRecord.question_id == question_id,
            QuestionAnswerRecord.app_user_id.isnot(None),
        )
        graded = base.filter(QuestionAnswerRecord.grading_status == "graded")

        graded_count = graded.count()
        correct_count = graded.filter(
            QuestionAnswerRecord.is_correct == 1
        ).count()
        unique_users = (
            self.db.query(func.count(func.distinct(QuestionAnswerRecord.app_user_id)))
            .filter(
                QuestionAnswerRecord.question_id == question_id,
                QuestionAnswerRecord.app_user_id.isnot(None),
                QuestionAnswerRecord.grading_status == "graded",
            )
            .scalar()
            or 0
        )

        # 口径 B：首次作答（每用户每题第一条 graded 记录，按 created_at,id 排序）
        first_attempt_total, first_attempt_correct = self._first_attempt_stats(question_id)

        accuracy = (correct_count / graded_count) if graded_count else None
        first_accuracy = (
            (first_attempt_correct / first_attempt_total) if first_attempt_total else None
        )

        return {
            "question_id": question_id,
            "accuracy": round(accuracy, 4) if accuracy is not None else None,
            "first_attempt_accuracy": (
                round(first_accuracy, 4) if first_accuracy is not None else None
            ),
            "first_attempt_total": first_attempt_total,
            "first_attempt_correct": first_attempt_correct,
            "unique_user_count": int(unique_users),
            "graded_submission_count": graded_count,
            "total_submission_count": base.count(),
            "correct_submission_count": correct_count,
            "display_status": _display_status(graded_count),
            "sample_threshold": settings.QUESTION_STATISTICS_MIN_SAMPLES,
        }

    def _first_attempt_stats(self, question_id: int) -> Tuple[int, int]:
        """MySQL 8 窗口函数取每用户第一条 graded 记录，统计总量与正确量。"""
        sub = (
            self.db.query(
                QuestionAnswerRecord.app_user_id.label("uid"),
                QuestionAnswerRecord.is_correct.label("is_correct"),
                func.row_number().over(
                    partition_by=QuestionAnswerRecord.app_user_id,
                    order_by=(
                        QuestionAnswerRecord.created_at.asc(),
                        QuestionAnswerRecord.id.asc(),
                    ),
                ).label("rn"),
            )
            .filter(
                QuestionAnswerRecord.question_id == question_id,
                QuestionAnswerRecord.app_user_id.isnot(None),
                QuestionAnswerRecord.grading_status == "graded",
            )
            .subquery()
        )
        rows = (
            self.db.query(sub.c.is_correct)
            .filter(sub.c.rn == 1)
            .all()
        )
        total = len(rows)
        correct = sum(1 for (is_correct,) in rows if is_correct == 1)
        return total, correct

    # ==================== 个人统计（口径 E） ====================

    def user_statistics(self, user_id: int) -> dict:
        base = self.db.query(QuestionAnswerRecord).filter(
            QuestionAnswerRecord.app_user_id == user_id
        )
        graded = base.filter(QuestionAnswerRecord.grading_status == "graded")

        graded_count = graded.count()
        correct_count = graded.filter(QuestionAnswerRecord.is_correct == 1).count()
        graded_questions = (
            self.db.query(func.count(func.distinct(QuestionAnswerRecord.question_id)))
            .filter(
                QuestionAnswerRecord.app_user_id == user_id,
                QuestionAnswerRecord.grading_status == "graded",
            )
            .scalar()
            or 0
        )

        # 首次作答正确率（按题目分组取首条）
        first_total, first_correct = self._user_first_attempt_stats(user_id)

        sessions = self.db.query(PracticeSession).filter(
            PracticeSession.app_user_id == user_id
        )
        session_total = sessions.count()
        session_completed = sessions.filter(PracticeSession.status == "completed").count()
        session_in_progress = sessions.filter(
            PracticeSession.status == "in_progress"
        ).count()
        session_abandoned = sessions.filter(PracticeSession.status == "abandoned").count()
        duration_sum = (
            self.db.query(func.coalesce(func.sum(PracticeSession.duration_ms), 0))
            .filter(
                PracticeSession.app_user_id == user_id,
                PracticeSession.status == "completed",
            )
            .scalar()
            or 0
        )

        accuracy = (correct_count / graded_count) if graded_count else None
        first_accuracy = (first_correct / first_total) if first_total else None

        return {
            "answer_summary": {
                "graded_submission_count": graded_count,
                "correct_submission_count": correct_count,
                "accuracy": round(accuracy, 4) if accuracy is not None else None,
                "first_attempt_accuracy": (
                    round(first_accuracy, 4) if first_accuracy is not None else None
                ),
                "answered_question_count": int(graded_questions),
                "display_status": _display_status(graded_count),
                "sample_threshold": settings.QUESTION_STATISTICS_MIN_SAMPLES,
            },
            "practice_summary": {
                "session_total": session_total,
                "session_completed": session_completed,
                "session_in_progress": session_in_progress,
                "session_abandoned": session_abandoned,
                "total_duration_ms": int(duration_sum),
            },
        }

    def _user_first_attempt_stats(self, user_id: int) -> Tuple[int, int]:
        sub = (
            self.db.query(
                QuestionAnswerRecord.question_id.label("qid"),
                QuestionAnswerRecord.is_correct.label("is_correct"),
                func.row_number().over(
                    partition_by=QuestionAnswerRecord.question_id,
                    order_by=(
                        QuestionAnswerRecord.created_at.asc(),
                        QuestionAnswerRecord.id.asc(),
                    ),
                ).label("rn"),
            )
            .filter(
                QuestionAnswerRecord.app_user_id == user_id,
                QuestionAnswerRecord.grading_status == "graded",
            )
            .subquery()
        )
        rows = self.db.query(sub.c.is_correct).filter(sub.c.rn == 1).all()
        total = len(rows)
        correct = sum(1 for (is_correct,) in rows if is_correct == 1)
        return total, correct
