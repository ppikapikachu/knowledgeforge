"""add manual AI review batch tables and record batch_id

Revision ID: i9a0b1c2d3e4
Revises: h8a9b0c1d2e3
Create Date: 2026-10-26

批量 AI 审核（补充开发文档 §5/§10）：
- question_review_batch / question_review_batch_item 批次与逐题持久化；
- question_review_record.batch_id 关联手动批量批次（历史记录为 NULL，兼容默认值）；
- 活动认领唯一约束 uq_qrbi_question_claim(question_id, claim_key)：同一题目
  同时仅一条 claim_key='active' 的审核项（MySQL 允许多 NULL，终态置 NULL 不受限）。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "i9a0b1c2d3e4"
down_revision = "h8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_review_batch",
        sa.Column("id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), autoincrement=True, nullable=False, comment="批次 ID"),
        sa.Column("created_by", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), nullable=False, comment="发起管理员 ID（取自认证上下文）"),
        sa.Column("status", sa.String(20), nullable=False, comment="批次状态: queued/running/completed/partial/failed/cancelled"),
        sa.Column("total_count", sa.Integer(), nullable=False, comment="提交（去重后）题目数"),
        sa.Column("accepted_count", sa.Integer(), nullable=False, comment="被批次接纳（排队）题目数"),
        sa.Column("processed_count", sa.Integer(), nullable=False, comment="已得到审核决策数"),
        sa.Column("auto_approved_count", sa.Integer(), nullable=False, comment="自动通过并发布数"),
        sa.Column("auto_rejected_count", sa.Integer(), nullable=False, comment="自动驳回数"),
        sa.Column("manual_review_count", sa.Integer(), nullable=False, comment="转人工审核数"),
        sa.Column("failed_count", sa.Integer(), nullable=False, comment="执行失败数"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, comment="资格/去重/状态变化跳过数"),
        sa.Column("pending_count", sa.Integer(), nullable=False, comment="尚未处理数"),
        sa.Column("started_at", sa.DateTime().with_variant(sa.DateTime, "mysql"), nullable=True, comment="开始时间"),
        sa.Column("finished_at", sa.DateTime().with_variant(sa.DateTime, "mysql"), nullable=True, comment="完成时间"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="批次级错误摘要"),
        sa.Column("created_at", sa.DateTime().with_variant(sa.DateTime, "mysql"), nullable=False),
        sa.Column("updated_at", sa.DateTime().with_variant(sa.DateTime, "mysql"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["admin_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("idx_qrb_status", "question_review_batch", ["status"])
    op.create_index("idx_qrb_created_by", "question_review_batch", ["created_by"])
    op.create_index("idx_qrb_created_at", "question_review_batch", ["created_at"])

    op.create_table(
        "question_review_batch_item",
        sa.Column("id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), autoincrement=True, nullable=False, comment="批次项 ID"),
        sa.Column("batch_id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), nullable=False, comment="所属批次 ID"),
        sa.Column("question_id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), nullable=False, comment="题目 ID"),
        sa.Column("status", sa.String(20), nullable=False, comment="处理状态: queued/running/completed/failed/skipped"),
        sa.Column("claim_key", sa.String(32), nullable=True, comment="活动认领键：排队/执行期间为 active，终态后 NULL"),
        sa.Column("skip_reason", sa.String(50), nullable=True, comment="跳过原因"),
        sa.Column("review_record_id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), nullable=True, comment="对应 question_review_record.id"),
        sa.Column("error_code", sa.String(50), nullable=True, comment="单题错误码"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="单题失败原因"),
        sa.Column("started_at", sa.DateTime().with_variant(sa.DateTime, "mysql"), nullable=True, comment="开始时间"),
        sa.Column("finished_at", sa.DateTime().with_variant(sa.DateTime, "mysql"), nullable=True, comment="完成时间"),
        sa.Column("created_at", sa.DateTime().with_variant(sa.DateTime, "mysql"), nullable=False),
        sa.Column("updated_at", sa.DateTime().with_variant(sa.DateTime, "mysql"), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["question_review_batch.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["review_record_id"], ["question_review_record.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "question_id", name="uq_qrbi_batch_question"),
        sa.UniqueConstraint("question_id", "claim_key", name="uq_qrbi_question_claim"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("idx_qrbi_batch_id", "question_review_batch_item", ["batch_id"])
    op.create_index("idx_qrbi_question_id", "question_review_batch_item", ["question_id"])

    # 审核记录关联手动批量批次（历史记录 NULL，兼容默认值，不覆盖已有证据）
    op.add_column(
        "question_review_record",
        sa.Column(
            "batch_id",
            sa.BigInteger().with_variant(sa.BigInteger, "mysql"),
            nullable=True,
            comment="手动批量审核批次 ID（生成任务自动审核为空）",
        ),
    )
    op.create_foreign_key(
        "fk_qrr_batch",
        "question_review_record",
        "question_review_batch",
        ["batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_qrr_batch_id", "question_review_record", ["batch_id"])
    op.create_index("idx_qrr_trigger_source", "question_review_record", ["trigger_source"])


def downgrade() -> None:
    # MySQL 约束：必须先删外键，再删其支撑索引（1553: needed in a foreign key constraint）
    op.drop_constraint("fk_qrr_batch", "question_review_record", type_="foreignkey")
    op.drop_index("idx_qrr_trigger_source", table_name="question_review_record")
    op.drop_index("idx_qrr_batch_id", table_name="question_review_record")
    op.drop_column("question_review_record", "batch_id")

    op.drop_index("idx_qrbi_question_id", table_name="question_review_batch_item")
    op.drop_index("idx_qrbi_batch_id", table_name="question_review_batch_item")
    op.drop_table("question_review_batch_item")

    # drop_table 连带删除表内索引（MySQL 不允许单独删除 FK 支撑索引 idx_qrb_created_by）
    op.drop_table("question_review_batch")
