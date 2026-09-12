"""Knowledge model."""

from typing import Optional

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.dialects.mysql import JSON, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Knowledge(Base, TimestampMixin):
    """Knowledge point model."""

    __tablename__ = "knowledge"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="知识点名称",
    )
    summary: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        default=None,
        comment="简要说明",
    )
    content: Mapped[Optional[str]] = mapped_column(
        LONGTEXT,
        nullable=True,
        default=None,
        comment="完整知识内容",
    )
    difficulty: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        comment="难度: 1=简单, 2=中等, 3=困难",
    )
    status: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        comment="状态: 1=正常, 0=禁用",
    )
    source_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="MANUAL",
        comment="来源: MANUAL/IMPORT/AI",
    )
    source_document: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        default=None,
        comment="来源文档",
    )
    keywords: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="关键词JSON数组",
    )

    __table_args__ = (
        Index("idx_knowledge_name", "name"),
        Index("idx_knowledge_difficulty", "difficulty"),
        Index("idx_knowledge_status", "status"),
        Index("idx_knowledge_source_type", "source_type"),
        Index("idx_knowledge_created_at", "created_at"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return f"<Knowledge(id={self.id}, name={self.name})>"
