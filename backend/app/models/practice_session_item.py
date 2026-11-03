"""练习会话题目状态模型（practice_session_item）。

为每个 session 对应的每个 paper item 创建一行，
保存本次会话的独立进度（草稿/标记/最近提交指针）。
保存草稿不创建 question_answer_record，也不进入正确率统计。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PracticeSessionItem(Base):
    """会话题目状态。"""

    __tablename__ = "practice_session_item"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="会话题目状态 ID",
    )
    session_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("practice_session.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属练习会话 ID",
    )
    paper_item_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("practice_paper_item.id", ondelete="RESTRICT"),
        nullable=False,
        comment="对应快照题目 ID",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unanswered",
        comment="作答状态: unanswered/draft_saved/answered",
    )
    draft_answer: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="最近保存但尚未正式提交的草稿答案",
    )
    is_marked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否标记待回看（独立于作答状态）",
    )
    latest_answer_record_id: Mapped[Optional[int]] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question_answer_record.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        comment="最近一次正式提交记录 ID",
    )
    latest_is_correct: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        default=None,
        comment="最近一次客观判分结果（NULL=未判分/未提交）",
    )
    latest_grading_status: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        default=None,
        comment="最近一次判分状态",
    )
    first_submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        default=None,
        comment="首次正式提交时间（不被后续提交覆盖）",
    )
    last_submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        default=None,
        comment="最近正式提交时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="最近修改时间",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    __table_args__ = (
        UniqueConstraint("session_id", "paper_item_id", name="uq_psi_session_item"),
        Index("idx_psi_session_status", "session_id", "status"),
        Index("idx_psi_session_marked", "session_id", "is_marked"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return f"<PracticeSessionItem(id={self.id}, session_id={self.session_id}, status={self.status})>"
