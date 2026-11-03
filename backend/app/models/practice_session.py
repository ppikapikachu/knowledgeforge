"""练习会话模型（practice_session）。

每次用户基于某份试卷快照（practice_paper）进行的一次练习过程。
paper_id 非空：会话必须关联试卷快照，不接受只记录题目列表。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PracticeSession(Base, TimestampMixin):
    """练习会话。"""

    __tablename__ = "practice_session"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="练习会话 ID",
    )
    app_user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
        comment="会话所属普通用户 ID",
    )
    paper_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("practice_paper.id", ondelete="RESTRICT"),
        nullable=False,
        comment="本次练习使用的试卷快照 ID（非空）",
    )
    mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="practice",
        comment="模式: practice=练习（首期唯一开放）, exam=考试（预留）",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="in_progress",
        comment="状态: in_progress/completed/abandoned",
    )
    current_item_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="当前题目序号（恢复界面位置）",
    )
    total_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="会话创建时题目总数快照",
    )
    answered_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="已提交题目数（按 item 最新提交统计）",
    )
    correct_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="当前最新答案为正确的客观题数",
    )
    incorrect_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="当前最新答案为错误的客观题数",
    )
    ungraded_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="未自动判分题数（简答等）",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        default=None,
        comment="开始时间",
    )
    last_active_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        default=None,
        comment="最近活动时间（继续练习列表排序）",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        default=None,
        comment="完成时间",
    )
    abandoned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        default=None,
        comment="放弃时间",
    )
    duration_ms: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="本次会话耗时（毫秒，可按有效活动区间累计或完成时汇总）",
    )

    __table_args__ = (
        Index("idx_ps_user_status_active", "app_user_id", "status", "last_active_at"),
        Index("idx_ps_user_created", "app_user_id", "created_at"),
        Index("idx_ps_paper", "paper_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return f"<PracticeSession(id={self.id}, paper_id={self.paper_id}, status={self.status})>"
