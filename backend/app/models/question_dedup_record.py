"""question_dedup_record：题目去重判定审计表（执行文档 §9）。

仅保存"进入最终判定的候选"与汇总：每个新题每轮判定落一行（决定性候选），
LLM 复核过的配对也各落一行；不保存全库候选。
"""

from typing import Optional

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class QuestionDedupRecord(Base, TimestampMixin):
    __tablename__ = "question_dedup_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 任务（人工/接口调用可为空）
    task_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("question_generation_task.id", ondelete="SET NULL"),
        nullable=True, comment="关联生成任务 ID"
    )

    # 新题信息（快照，MySQL 为唯一事实源，这里留审计快照）
    new_content_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="新题指纹")
    new_hash_version: Mapped[str] = mapped_column(String(8), nullable=False, default="2", comment="指纹版本")
    new_content_snapshot: Mapped[str] = mapped_column(Text, nullable=False, comment="新题题干快照(截断)")
    new_question_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="题型")
    new_question_bank_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="新题所属题库 ID"
    )
    new_knowledge_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, comment="新题知识点 ID 列表")

    # 匹配候选信息（批次内候选 matched_question_id 为空）
    matched_question_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="命中的历史题 ID"
    )
    matched_question_bank_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="命中历史题的题库 ID"
    )
    matched_knowledge_ids: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="命中历史题的知识点 ID 列表"
    )
    matched_source: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, comment="候选来源: db=库内题, batch=批次内新题"
    )

    # 判定过程
    scope_mode: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="same_scope / cross_scope / global_exact / batch_internal"
    )
    keyword_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="关键词通道分数")
    algorithm_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="融合算法分数")

    llm_called: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否调用 LLM")
    llm_decision: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="LLM 结论: duplicate/distinct/uncertain"
    )
    llm_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="LLM 理由")

    decision: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="最终结论: duplicate/distinct/uncertain"
    )
    decision_method: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="判定方式: exact_hash/algorithm_only/vector_and_llm/batch_internal"
    )
    needs_manual_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否需要人工复核"
    )

    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="向量检索使用的 Embedding 模型"
    )
    embedding_version: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Embedding 版本"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QuestionDedupRecord id={self.id} task={self.task_id} decision={self.decision}>"
