"""Base model and common mixins."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.dialects.mysql import DATETIME as MySQL_DATETIME
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(MySQL_DATETIME(fsp=3), "mysql"),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(MySQL_DATETIME(fsp=3), "mysql"),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )
