"""题目 AI 质量审核记录模型（追加式审计，不覆盖历史，执行文档 §6）。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class QuestionReviewRecord(Base, TimestampMixin):
    """题目 AI 质量审核记录。

    所有自动决策必须能追溯到具体审核记录；
    自动通过/驳回不允许在无审核记录的情况下发生。
    """

    __tablename__ = "question_review_record"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="审核记录 ID",
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question.id", ondelete="RESTRICT"),
        nullable=False,
        comment="题目 ID",
    )
    generation_task_id: Mapped[Optional[int]] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question_generation_task.id", ondelete="SET NULL"),
        nullable=True,
        comment="生成任务 ID（手动批量审核为空，不伪造出题任务 ID）",
    )
    batch_id: Mapped[Optional[int]] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("question_review_batch.id", ondelete="SET NULL"),
        nullable=True,
        comment="手动批量审核批次 ID（生成任务自动审核为空）",
    )
    review_round: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="审核轮次",
    )
    trigger_source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="generation_task",
        comment="触发来源: generation_task/ manual_batch",
    )
    execution_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="success",
        comment="执行状态: success/failed/skipped",
    )
    decision: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        default=None,
        comment="AI 决策: auto_approve/auto_reject/manual_review；failed/skipped 为空",
    )
    risk_level: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        default=None,
        comment="风险等级: low/medium/high/unknown",
    )
    issue_types: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="问题类型 JSON 数组",
    )
    checks: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="8 项检查结果 JSON 对象",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="审核结论理由",
    )
    evidence: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="证据 JSON（知识点原文摘录）",
    )
    model_name: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="审核模型标识",
    )
    prompt_version: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        comment="审核 Prompt 版本",
    )
    reviewed_content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="审核时题目内容快照指纹（题干/选项/答案/解析/知识点关联）",
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=None,
        comment="审核耗时（毫秒）",
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default=None,
        comment="失败/跳过原因代码",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="失败/跳过信息",
    )
    # 人工纠正（§7.5 AI 自动驳回题目重新开放）：只追加记录，不删除 AI 审核证据
    reopened_by: Mapped[Optional[int]] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        ForeignKey("admin_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="重新开放的管理员 ID",
    )
    reopened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime().with_variant(DateTime, "mysql"),
        nullable=True,
        comment="重新开放时间",
    )
    reopen_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="重新开放理由",
    )

    __table_args__ = (
        UniqueConstraint("question_id", "review_round", name="uq_qrr_question_round"),
        Index("idx_qrr_task_id", "generation_task_id"),
        Index("idx_qrr_question_id", "question_id"),
        Index("idx_qrr_batch_id", "batch_id"),
        Index("idx_qrr_trigger_source", "trigger_source"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )
