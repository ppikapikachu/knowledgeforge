"""试卷快照头模型（practice_paper）。

一条记录代表一次真实组卷的结果（不可变的试卷快照实例），
不是可变的试卷模板。快照内容生成后不因源题更新/下架而变化。
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PracticePaper(Base, TimestampMixin):
    """试卷快照头。"""

    __tablename__ = "practice_paper"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="试卷快照 ID",
    )
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
        comment="所属普通用户 ID",
    )
    source_question_bank_id: Mapped[Optional[int]] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question_bank.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        comment="来源题库 ID（可空）",
    )
    title: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="试卷标题",
    )
    snapshot_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="快照结构版本（首期为 1）",
    )
    snapshot_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="按确定性序列化对题目快照+组卷配置生成的 SHA-256",
    )
    assembly_config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="用户本次组卷条件的不可变快照",
    )
    question_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="实际入卷题目数",
    )
    total_score: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        comment="本卷总分",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ready",
        comment="状态: ready=可用, archived=已归档",
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        default=None,
        comment="组卷幂等键（防超时重试重复组卷）",
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        default=None,
        comment="归档时间",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        default=None,
        comment="软删除时间（不物理删除快照）",
    )

    __table_args__ = (
        UniqueConstraint("owner_user_id", "idempotency_key", name="uq_paper_owner_idem"),
        Index("idx_pp_owner_created", "owner_user_id", "created_at"),
        Index("idx_pp_owner_status_created", "owner_user_id", "status", "created_at"),
        Index("idx_pp_bank", "source_question_bank_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return f"<PracticePaper(id={self.id}, title={self.title})>"
