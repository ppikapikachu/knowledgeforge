"""Knowledge relation model."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.mysql import DATETIME as MySQL_DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgeRelation(Base):
    """Knowledge relation model for building knowledge graph."""

    __tablename__ = "knowledge_relation"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    source_knowledge_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("knowledge.id", ondelete="RESTRICT"),
        nullable=False,
        comment="起点知识点ID",
    )
    target_knowledge_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("knowledge.id", ondelete="RESTRICT"),
        nullable=False,
        comment="终点知识点ID",
    )
    relation_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="关系类型: prerequisite/related/extension/contrast",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(MySQL_DATETIME(fsp=3), "mysql"),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    __table_args__ = (
        UniqueConstraint(
            "source_knowledge_id",
            "target_knowledge_id",
            "relation_type",
            name="uq_knowledge_relation",
        ),
        Index("idx_kr_source", "source_knowledge_id"),
        Index("idx_kr_target", "target_knowledge_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeRelation(id={self.id}, "
            f"source={self.source_knowledge_id}, "
            f"target={self.target_knowledge_id}, "
            f"type={self.relation_type})>"
        )
