"""普通用户（App User）模型。

与 admin_user 的区别：
    - admin_user = 管理端身份，负责题库/题目/审核管理
    - app_user = 用户端身份，负责练习、答题、评论
两者身份严格分离，互不冒充。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AppUser(Base, TimestampMixin):
    """普通用户账号。"""

    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="普通用户 ID",
    )
    account: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        comment="登录账号（服务端规范化：去首尾空格+小写）",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="密码哈希（bcrypt，禁止明文）",
    )
    nickname: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        default=None,
        comment="用户昵称",
    )
    avatar: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        default=None,
        comment="头像 URL",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        comment="状态: active=正常, disabled=禁用, deleted=已注销",
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        default=None,
        comment="最近登录时间",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        default=None,
        comment="软删除时间",
    )

    __table_args__ = (
        Index("idx_app_user_status", "status"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return f"<AppUser(id={self.id}, account={self.account})>"
