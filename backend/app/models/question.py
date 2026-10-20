"""Question model."""

from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.question_knowledge import QuestionKnowledge
    from app.models.question_option import QuestionOption


class Question(Base, TimestampMixin):
    """Question/interview question model."""

    __tablename__ = "question"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    question_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="题型: SINGLE_CHOICE/MULTIPLE_CHOICE/TRUE_FALSE/SHORT_ANSWER",
    )
    question_bank_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question_bank.id", ondelete="RESTRICT"),
        nullable=False,
        default=0,
        comment="所属题库 ID",
    )
    content: Mapped[str] = mapped_column(
        LONGTEXT,
        nullable=False,
        comment="题目内容",
    )
    answer: Mapped[str] = mapped_column(
        LONGTEXT,
        nullable=False,
        comment="标准答案",
    )
    analysis: Mapped[Optional[str]] = mapped_column(
        LONGTEXT,
        nullable=True,
        default=None,
        comment="题目解析",
    )
    difficulty: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        comment="难度: 1=简单, 2=中等, 3=困难",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending_review",
        comment="状态: pending_review/published/disabled/rejected",
    )
    explanation: Mapped[Optional[str]] = mapped_column(
        LONGTEXT,
        nullable=True,
        default=None,
        comment="解析文本",
    )
    explanation_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="not_requested",
        comment="解析状态: not_requested/pending/processing/success/failed",
    )
    explanation_source: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        default=None,
        comment="解析来源: ai/manual",
    )
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        default=None,
        comment="内容指纹（用于去重）",
    )
    hash_version: Mapped[Optional[str]] = mapped_column(
        String(8),
        nullable=True,
        default="0",
        comment="指纹算法版本: 0=历史content-only指纹, 1=v1结构化指纹",
    )
    dedup_key: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        default=None,
        comment="去重唯一键: 仅阻断状态(pending_review/published)题目=content_hash，其余为 NULL",
    )
    generation_task_id: Mapped[Optional[int]] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        nullable=True,
        default=None,
        comment="来源生成任务 ID",
    )
    source_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="MANUAL",
        comment="来源: MANUAL/IMPORT/AI",
    )
    quality_score: Mapped[Optional[Decimal]] = mapped_column(
        nullable=True,
        default=None,
        comment="质量评分: 0~100",
    )
    used_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="被使用次数",
    )
    correct_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="正确次数",
    )

    # Relationships
    options: Mapped[List["QuestionOption"]] = relationship(
        "QuestionOption",
        back_populates="question",
        lazy="select",
        cascade="save-update, merge",
    )
    knowledge_associations: Mapped[List["QuestionKnowledge"]] = relationship(
        "QuestionKnowledge",
        back_populates="question",
        lazy="select",
        cascade="save-update, merge",
    )

    __table_args__ = (
        Index("idx_question_type", "question_type"),
        Index("idx_question_difficulty", "difficulty"),
        Index("idx_question_status", "status"),
        Index("idx_question_source_type", "source_type"),
        Index("idx_question_created_at", "created_at"),
        # 去重精确层：全局唯一键（同指纹只允许一个阻断状态题目）
        Index("uq_question_dedup_key", "dedup_key", unique=True),
        # 去重精确层查询加速（非唯一：历史行/非阻断行可共享指纹）
        Index("idx_question_content_hash", "content_hash"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return f"<Question(id={self.id}, type={self.question_type})>"
