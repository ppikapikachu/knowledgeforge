"""知识库（领域）模型。

知识库是知识点的领域归属，如 Android、Java、分布式系统。
不是普通知识点，也不是 knowledge_relation 中的虚拟节点。
V1.0 为平级领域集合，不支持层级树。
"""

from typing import Optional

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class KnowledgeBase(Base, TimestampMixin):
    """知识库（领域）模型。"""

    __tablename__ = "knowledge_base"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="稳定编码，如 android、java、uncategorized",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="展示名称，如 Android、Java",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="简介",
    )
    status: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        comment="状态: 1=正常, 0=停用",
    )

    __table_args__ = (
        Index("idx_kb_status", "status"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBase(id={self.id}, code={self.code}, name={self.name})>"
