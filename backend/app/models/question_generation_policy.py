"""出题策略模型。"""

from typing import Optional

from sqlalchemy import BigInteger, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class QuestionGenerationPolicy(Base, TimestampMixin):
    """出题策略（全局或题库级）。"""

    __tablename__ = "question_generation_policy"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    question_bank_id: Mapped[Optional[int]] = mapped_column(
        BigInteger().with_variant(BigInteger, "mysql"),
        nullable=True,
        default=None,
        comment="题库 ID，NULL=全局策略",
    )
    stock_weight: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50, comment="库存权重(0-100)"
    )
    usage_weight: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, comment="使用权重(0-100)"
    )
    importance_weight: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20, comment="重要程度权重(0-100)"
    )
    target_stock: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20, comment="目标库存量(1-500)"
    )
    usage_window_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, comment="使用窗口天数(1-365)"
    )
    recent_answers_per_question_target: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, comment="每题目标题答题数(1-100)"
    )
    usage_extra_ratio: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5, comment="使用额外补充比例(0-2)"
    )
    max_per_knowledge_per_task: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, comment="单任务单知识点上限(1-50)"
    )
    min_demand_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.15, comment="最低需求分(0-1)"
    )
    is_enabled: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="是否启用: 1=是, 0=否"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="版本号"
    )

    __table_args__ = (
        Index("idx_qgp_question_bank", "question_bank_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )
