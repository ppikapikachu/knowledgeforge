"""Question model."""

from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, Index, String
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
        default="DRAFT",
        comment="状态: DRAFT/PUBLISHED/DISABLED",
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
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return f"<Question(id={self.id}, type={self.question_type})>"
