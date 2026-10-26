"""手动批量 AI 审核批次模型（补充开发文档 §5）。

职责：
- question_review_batch：管理员手动发起的批量 AI 审核任务（持久化，可查询进度/统计）；
- question_review_batch_item：逐题处理结果（含资格跳过/失败原因），不依赖
  question_review_record（资格校验跳过的题目不产生 Agent 审核记录）。

并发认领（§5.2）：item.claim_key 在排队/执行期间为常量 "active"，终态后置 NULL，
配合 UNIQUE(question_id, claim_key)（MySQL 允许多个 NULL）实现"同一题目同时只有一条
活动审核项"的数据库级约束——不依赖 Python 进程内锁。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# 活动认领键：排队/执行期间固定为该值，终态（completed/failed/skipped）后置 NULL
ACTIVE_CLAIM_KEY = "active"

# 批次状态（§8.1）
BATCH_QUEUED = "queued"
BATCH_RUNNING = "running"
BATCH_COMPLETED = "completed"
BATCH_PARTIAL = "partial"
BATCH_FAILED = "failed"
BATCH_CANCELLED = "cancelled"

# 批次项状态（§5.2）
ITEM_QUEUED = "queued"
ITEM_RUNNING = "running"
ITEM_COMPLETED = "completed"
ITEM_FAILED = "failed"
ITEM_SKIPPED = "skipped"


class QuestionReviewBatch(Base, TimestampMixin):
    """手动批量 AI 审核批次。"""

    __tablename__ = "question_review_batch"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="批次 ID",
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("admin_user.id", ondelete="RESTRICT"),
        nullable=False,
        comment="发起管理员 ID（取自认证上下文）",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=BATCH_QUEUED,
        comment="批次状态: queued/running/completed/partial/failed/cancelled",
    )
    total_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="提交（去重后）题目数"
    )
    accepted_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="被批次接纳（排队）题目数"
    )
    processed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="已得到审核决策数"
    )
    auto_approved_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="自动通过并发布数"
    )
    auto_rejected_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="自动驳回数"
    )
    manual_review_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="转人工审核数"
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="执行失败数"
    )
    skipped_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="资格/去重/状态变化跳过数"
    )
    pending_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="尚未处理数"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        comment="开始时间",
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        comment="完成时间",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="批次级错误摘要"
    )

    __table_args__ = (
        Index("idx_qrb_status", "status"),
        Index("idx_qrb_created_by", "created_by"),
        Index("idx_qrb_created_at", "created_at"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )


class QuestionReviewBatchItem(Base, TimestampMixin):
    """批量审核批次项（逐题持久化结果，含资格跳过/失败原因）。"""

    __tablename__ = "question_review_batch_item"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="批次项 ID",
    )
    batch_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question_review_batch.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属批次 ID",
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question.id", ondelete="RESTRICT"),
        nullable=False,
        comment="题目 ID",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ITEM_QUEUED,
        comment="处理状态: queued/running/completed/failed/skipped",
    )
    claim_key: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        default=None,
        comment="活动认领键：排队/执行期间为 active，终态后 NULL（配合唯一约束防并发认领）",
    )
    skip_reason: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="跳过原因 dedup_unresolved/dedup_duplicate/unsupported_question_type/question_not_pending/review_in_progress 等",
    )
    review_record_id: Mapped[Optional[int]] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question_review_record.id", ondelete="SET NULL"),
        nullable=True,
        comment="对应 question_review_record.id",
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="单题错误码"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="单题失败原因"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        comment="开始时间",
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        comment="完成时间",
    )

    __table_args__ = (
        UniqueConstraint("batch_id", "question_id", name="uq_qrbi_batch_question"),
        # 同一题目同时只允许一条活动（claim_key='active'）审核项；终态 NULL 不受限
        UniqueConstraint("question_id", "claim_key", name="uq_qrbi_question_claim"),
        Index("idx_qrbi_batch_id", "batch_id"),
        Index("idx_qrbi_question_id", "question_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )
