"""试卷题目快照模型（practice_paper_item）。

每道入卷题目一行，保存完整且独立的题目内容快照
（题干/选项/标准答案/解析/知识点/题型/难度/分值）。
快照生成后不可变：不提供修改快照内容的业务接口，
判分和回顾一律读取快照，不实时读取 question 表。
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PracticePaperItem(Base, TimestampMixin):
    """试卷题目快照。"""

    __tablename__ = "practice_paper_item"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="试卷题目 ID",
    )
    paper_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("practice_paper.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属试卷快照 ID",
    )
    source_question_id: Mapped[Optional[int]] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question.id", ondelete="RESTRICT"),
        nullable=True,
        default=None,
        comment="来源原题 ID（仅追溯与统计用）",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="题目在试卷中的固定顺序，从 1 开始",
    )
    question_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="题型快照（SINGLE_CHOICE/MULTIPLE_CHOICE/TRUE_FALSE/SHORT_ANSWER）",
    )
    difficulty: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
        comment="难度快照（项目真实 Schema：1=简单 2=中等 3=困难）",
    )
    score: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("5"),
        comment="本题分值快照",
    )
    source_status_at_snapshot: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="published",
        comment="生成快照时源题目状态（正常为 published）",
    )
    source_content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        default=None,
        comment="源题目当时的内容指纹",
    )
    knowledge_snapshot: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="当时关联知识点快照 [{knowledge_id, name, ...}]",
    )
    question_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=False,
        comment="完整题目快照 JSON（题干/选项/标准答案/解析等）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    __table_args__ = (
        UniqueConstraint("paper_id", "sort_order", name="uq_ppi_paper_sort"),
        Index("idx_ppi_paper_sort", "paper_id", "sort_order"),
        Index("idx_ppi_source_question", "source_question_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return f"<PracticePaperItem(id={self.id}, paper_id={self.paper_id}, sort={self.sort_order})>"
