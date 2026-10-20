"""题库-知识库多对多关联表。"""

from sqlalchemy import BigInteger, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class QuestionBankKnowledgeBase(Base, TimestampMixin):
    """题库-知识库关联表。一个题库可关联多个知识库，一个知识库可供多个题库使用。"""

    __tablename__ = "question_bank_knowledge_base"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    question_bank_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question_bank.id", ondelete="RESTRICT"),
        nullable=False,
        comment="题库 ID",
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("knowledge_base.id", ondelete="RESTRICT"),
        nullable=False,
        comment="知识库 ID",
    )

    __table_args__ = (
        UniqueConstraint("question_bank_id", "knowledge_base_id", name="uq_qb_kb"),
        Index("idx_qbkb_question_bank", "question_bank_id"),
        Index("idx_qbkb_knowledge_base", "knowledge_base_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )
