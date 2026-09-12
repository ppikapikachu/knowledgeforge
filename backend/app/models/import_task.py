"""Import task model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.mysql import DATETIME as MySQL_DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class KnowledgeImportTask(Base, TimestampMixin):
    """Knowledge import task model for file upload and processing."""

    __tablename__ = "knowledge_import_task"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="原始文件名",
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="实际保存路径",
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        nullable=False,
        default=0,
        comment="文件大小(字节)",
    )
    file_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="文件类型: pdf/docx/txt/md",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING",
        comment="任务状态: PENDING/RUNNING/SUCCESS/PARTIAL_SUCCESS/FAILED/CANCELLED",
    )
    progress: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="进度: 0~100",
    )
    current_step: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        comment="当前阶段",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="错误信息",
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("admin_user.id", ondelete="RESTRICT"),
        nullable=False,
        comment="创建管理员ID",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(MySQL_DATETIME(fsp=3), "mysql"),
        nullable=True,
        default=None,
        comment="开始时间",
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(MySQL_DATETIME(fsp=3), "mysql"),
        nullable=True,
        default=None,
        comment="完成时间",
    )

    __table_args__ = (
        Index("idx_import_task_status", "status"),
        Index("idx_import_task_created_by", "created_by"),
        Index("idx_import_task_created_at", "created_at"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeImportTask(id={self.id}, "
            f"file_name={self.file_name}, "
            f"status={self.status})>"
        )
