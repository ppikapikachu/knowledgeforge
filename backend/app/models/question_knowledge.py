"""Question-Knowledge association model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.mysql import DATETIME as MySQL_DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.question import Question


class QuestionKnowledge(Base):
    """Association between questions and knowledge points."""

    __tablename__ = "question_knowledge"

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
        comment="题目ID",
    )
    knowledge_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("knowledge.id", ondelete="RESTRICT"),
        nullable=False,
        comment="知识点ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(MySQL_DATETIME(fsp=3), "mysql"),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    # Relationships
    question: Mapped["Question"] = relationship(
        "Question",
        back_populates="knowledge_associations",
        lazy="select",
    )

    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "knowledge_id",
            name="uq_question_knowledge",
        ),
        Index("idx_qk_question_id", "question_id"),
        Index("idx_qk_knowledge_id", "knowledge_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return (
            f"<QuestionKnowledge(id={self.id}, "
            f"question_id={self.question_id}, "
            f"knowledge_id={self.knowledge_id})>"
        )
