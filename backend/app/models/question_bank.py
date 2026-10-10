"""题库（Question Bank）模型。

题库用于组织用户练习时可选择的题目范围，分类可以比知识库更细。
例如：Java 基础、Java 并发编程、JVM、原生 Android 等。

与 knowledge_base 的区别：
    - knowledge_base = 知识的来源/粗粒度领域
    - question_bank = 练题时用户选择的题目范围
    - 两者不要求一一对应
"""

from typing import Optional

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class QuestionBank(Base, TimestampMixin):
    """题库模型。"""

    __tablename__ = "question_bank"

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
        comment="稳定唯一标识，如 java_basic、jvm",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="显示名称，如 Java 基础",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="内容范围说明：覆盖什么、不覆盖什么",
    )
    status: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        comment="状态: 1=启用, 0=停用。停用后不能作为新建题目或决策目标",
    )

    __table_args__ = (
        Index("idx_qb_status", "status"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return f"<QuestionBank(id={self.id}, code={self.code}, name={self.name})>"
