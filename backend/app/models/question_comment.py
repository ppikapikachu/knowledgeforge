"""题目评论模型。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class QuestionComment(Base, TimestampMixin):
    """题目评论。"""

    __tablename__ = "question_comment"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="评论 ID",
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
        comment="历史兼容用户 ID（旧记录为 admin_user，不改写不迁移）",
    )
    app_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=True,
        default=None,
        comment="正式普通用户 ID（新接口必填；历史记录为 NULL）",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="评论纯文本内容",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="visible",
        comment="状态: visible/hidden/deleted",
    )
    moderated_by: Mapped[Optional[int]] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        nullable=True,
        comment="管理员操作者 ID",
    )
    moderation_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="处理原因",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        comment="软删除时间",
    )

    __table_args__ = (
        Index("idx_qc_question", "question_id", "status", "created_at"),
        Index("idx_qc_user", "user_id", "created_at"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )
