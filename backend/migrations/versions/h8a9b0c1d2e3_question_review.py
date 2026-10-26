"""add question AI review records and task review fields

Revision ID: h8a9b0c1d2e3
Revises: g7a8b9c0d1e2
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON

# revision identifiers, used by Alembic.
revision = "h8a9b0c1d2e3"
down_revision = "g7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) question_generation_task：AI 审核开关与统计字段（§6）
    op.add_column(
        "question_generation_task",
        sa.Column("enable_ai_review", sa.Integer(), nullable=False,
                  server_default="0", comment="本次任务是否启用 AI 质量审核: 1=是, 0=否"),
    )
    op.add_column(
        "question_generation_task",
        sa.Column("ai_review_status", sa.String(20), nullable=False,
                  server_default="not_requested",
                  comment="AI 审核状态: not_requested/queued/running/completed/partial/failed"),
    )
    for name, comment in (
        ("ai_review_total_count", "进入本次任务 AI 审核阶段的题目数（不含去重淘汰候选）"),
        ("ai_review_processed_count", "AI 审核已处理数（success，不含 skipped/failed）"),
        ("ai_auto_approved_count", "AI 自动通过数"),
        ("ai_auto_rejected_count", "AI 自动驳回数"),
        ("ai_manual_review_count", "AI 判定需人工审核数"),
        ("ai_review_failed_count", "AI 审核执行失败数（安全降级人工）"),
        ("ai_review_skipped_count", "AI 审核跳过数（不支持题型/去重疑点/超预算）"),
        ("ai_review_pending_count", "AI 审核待处理数（任务执行中）"),
    ):
        op.add_column(
            "question_generation_task",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0", comment=comment),
        )

    # 2) question_review_record：追加式审核审计表（§6）
    op.create_table(
        "question_review_record",
        sa.Column("id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"),
                  primary_key=True, autoincrement=True, comment="审核记录 ID"),
        sa.Column("question_id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"),
                  sa.ForeignKey("question.id", ondelete="RESTRICT"),
                  nullable=False, comment="题目 ID"),
        sa.Column("generation_task_id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"),
                  sa.ForeignKey("question_generation_task.id", ondelete="SET NULL"),
                  nullable=True, comment="生成任务 ID"),
        sa.Column("review_round", sa.Integer(), nullable=False, server_default="1",
                  comment="审核轮次"),
        sa.Column("trigger_source", sa.String(30), nullable=False,
                  server_default="generation_task", comment="触发来源"),
        sa.Column("execution_status", sa.String(20), nullable=False,
                  server_default="success", comment="执行状态: success/failed/skipped"),
        sa.Column("decision", sa.String(20), nullable=True,
                  comment="AI 决策: auto_approve/auto_reject/manual_review；failed/skipped 为空"),
        sa.Column("risk_level", sa.String(10), nullable=True,
                  comment="风险等级: low/medium/high/unknown"),
        sa.Column("issue_types", JSON, nullable=True, comment="问题类型 JSON 数组"),
        sa.Column("checks", JSON, nullable=True, comment="8 项检查结果 JSON 对象"),
        sa.Column("reason", sa.Text, nullable=True, comment="审核结论理由"),
        sa.Column("evidence", JSON, nullable=True, comment="证据 JSON（知识点原文摘录）"),
        sa.Column("model_name", sa.String(128), nullable=True, comment="审核模型标识"),
        sa.Column("prompt_version", sa.String(32), nullable=True, comment="审核 Prompt 版本"),
        sa.Column("reviewed_content_hash", sa.String(64), nullable=True,
                  comment="审核时题目内容快照指纹"),
        sa.Column("duration_ms", sa.Integer(), nullable=True, comment="审核耗时（毫秒）"),
        sa.Column("error_code", sa.String(50), nullable=True, comment="失败/跳过原因代码"),
        sa.Column("error_message", sa.Text, nullable=True, comment="失败/跳过信息"),
        sa.Column("reopened_by", sa.BigInteger().with_variant(sa.BigInteger, "mysql"),
                  sa.ForeignKey("admin_user.id", ondelete="SET NULL"),
                  nullable=True, comment="重新开放的管理员 ID"),
        sa.Column("reopened_at", sa.DateTime().with_variant(sa.DateTime, "mysql"),
                  nullable=True, comment="重新开放时间"),
        sa.Column("reopen_reason", sa.Text, nullable=True, comment="重新开放理由"),
        sa.Column("created_at", sa.DateTime(3), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(3), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("question_id", "review_round", name="uq_qrr_question_round"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("idx_qrr_task_id", "question_review_record", ["generation_task_id"])
    op.create_index("idx_qrr_question_id", "question_review_record", ["question_id"])


def downgrade() -> None:
    # 回滚只删结构，不删业务数据之外的内容；审核表本身可安全移除
    op.drop_index("idx_qrr_question_id", table_name="question_review_record")
    op.drop_index("idx_qrr_task_id", table_name="question_review_record")
    op.drop_table("question_review_record")

    for name in (
        "ai_review_pending_count",
        "ai_review_skipped_count",
        "ai_review_failed_count",
        "ai_manual_review_count",
        "ai_auto_rejected_count",
        "ai_auto_approved_count",
        "ai_review_processed_count",
        "ai_review_total_count",
        "ai_review_status",
        "enable_ai_review",
    ):
        op.drop_column("question_generation_task", name)
