"""Admin user model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.dialects.mysql import DATETIME as MySQL_DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AdminUser(Base, TimestampMixin):
    """Administrator user model."""

    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="登录账号",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="密码哈希",
    )
    nickname: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="管理员",
        comment="显示昵称",
    )
    avatar: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        default=None,
        comment="头像URL",
    )
    status: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        comment="状态: 1=正常, 0=禁用",
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(MySQL_DATETIME(fsp=3), "mysql"),
        nullable=True,
        default=None,
        comment="最后登录时间",
    )

    __table_args__ = (
        Index("idx_admin_user_status", "status"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return f"<AdminUser(id={self.id}, username={self.username})>"
