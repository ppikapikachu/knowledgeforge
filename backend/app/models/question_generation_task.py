"""题目生成任务模型。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.mysql import JSON, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class QuestionGenerationTask(Base, TimestampMixin):
    """题目生成任务。"""

    __tablename__ = "question_generation_task"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="任务 ID",
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("admin_user.id", ondelete="RESTRICT"),
        nullable=False,
        comment="发起管理员 ID",
    )
    request_config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="请求配置快照（题库、题型、难度、题量等）",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        comment="任务状态: pending/running/partial_success/success/failed/cancelled",
    )
    total_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="计划生成数量",
    )
    success_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="成功生成并保存的题目数",
    )
    duplicate_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="去重跳过数量",
    )
    failed_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="失败数量",
    )
    explanation_requested: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="是否请求生成解析: 1=是, 0=否",
    )
    error_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="错误摘要",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        comment="开始时间",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        comment="完成时间",
    )
    allocation_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
        comment="分配模式: manual/auto",
    )
    allocation_plan: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="分配计划快照",
    )
    policy_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="策略快照（auto模式）",
    )
    requested_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="请求题量",
    )
    allocated_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="实际分配题量",
    )
    unallocated_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="未分配题量",
    )

    __table_args__ = (
        Index("idx_qgt_status", "status"),
        Index("idx_qgt_created_by", "created_by"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )
