"""Question option model."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.question import Question


class QuestionOption(Base, TimestampMixin):
    """Question option model for multiple choice questions."""

    __tablename__ = "question_option"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question.id", ondelete="RESTRICT"),
        nullable=False,
        comment="所属题目ID",
    )
    option_key: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="选项标识: A/B/C/D",
    )
    option_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="选项内容",
    )
    is_correct: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="是否正确: 1=正确, 0=错误",
    )
    sort_order: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="排序",
    )

    # Relationships
    question: Mapped["Question"] = relationship(
        "Question",
        back_populates="options",
        lazy="select",
    )

    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "option_key",
            name="uq_question_option_key",
        ),
        Index("idx_qo_question_id", "question_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return (
            f"<QuestionOption(id={self.id}, "
            f"question_id={self.question_id}, "
            f"key={self.option_key})>"
        )
