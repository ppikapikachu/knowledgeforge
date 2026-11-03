"""普通用户登录会话（Refresh Token）模型。

只保存 Refresh Token 的 SHA-256 哈希，不保存原文。
支持多设备登录；退出登录只撤销当前会话。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserAuthSession(Base, TimestampMixin):
    """普通用户刷新 Token 会话。"""

    __tablename__ = "user_auth_session"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="会话 ID",
    )
    app_user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
        comment="所属普通用户 ID",
    )
    refresh_token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="Refresh Token 的 SHA-256 哈希（hex），不存原文",
    )
    device_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        default=None,
        comment="设备标识（可空）",
    )
    device_name: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        default=None,
        comment="设备名称（可空）",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=False,
        comment="过期时间",
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        default=None,
        comment="撤销时间（退出登录/轮换后置位）",
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        default=None,
        comment="最近使用时间",
    )

    __table_args__ = (
        Index("idx_uas_user", "app_user_id", "created_at"),
        Index("idx_uas_expires", "expires_at"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return f"<UserAuthSession(id={self.id}, app_user_id={self.app_user_id})>"
