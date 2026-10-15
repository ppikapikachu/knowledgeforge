"""用户答题记录模型。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class QuestionAnswerRecord(Base, TimestampMixin):
    """用户答题记录。"""

    __tablename__ = "question_answer_record"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="主键 ID",
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question.id", ondelete="RESTRICT"),
        nullable=False,
        comment="题目 ID",
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        nullable=False,
        comment="用户 ID（当前使用 admin_user）",
    )
    user_answer: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="用户提交的答案",
    )
    is_correct: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        default=None,
        comment="是否正确: 1=对, 0=错, NULL=未判分",
    )
    grading_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="ungraded",
        comment="判分状态: graded/ungraded/pending_review",
    )
    time_spent_ms: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="答题耗时(毫秒)",
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="幂等键（防重复提交）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=False,
        comment="提交时间",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", "idempotency_key", name="uq_answer_idempotent"),
        Index("idx_qar_question", "question_id", "created_at"),
        Index("idx_qar_user_question", "user_id", "question_id", "created_at"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )
