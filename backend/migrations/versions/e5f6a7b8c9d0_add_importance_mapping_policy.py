"""add knowledge importance, question_bank_knowledge_base, policy, task allocation fields

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. knowledge importance fields
    op.add_column("knowledge", sa.Column("importance_level", sa.String(20), nullable=False, server_default="normal"))
    op.add_column("knowledge", sa.Column("importance_source", sa.String(20), nullable=False, server_default="default"))

    # 2. question_bank_knowledge_base M2M
    op.create_table(
        "question_bank_knowledge_base",
        sa.Column("id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), primary_key=True, autoincrement=True),
        sa.Column("question_bank_id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), sa.ForeignKey("question_bank.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("knowledge_base_id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), sa.ForeignKey("knowledge_base.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(3), nullable=False),
        sa.Column("updated_at", sa.DateTime(3), nullable=False),
        sa.UniqueConstraint("question_bank_id", "knowledge_base_id", name="uq_qb_kb"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("idx_qbkb_question_bank", "question_bank_knowledge_base", ["question_bank_id"])
    op.create_index("idx_qbkb_knowledge_base", "question_bank_knowledge_base", ["knowledge_base_id"])

    # 3. question_generation_policy
    op.create_table(
        "question_generation_policy",
        sa.Column("id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), primary_key=True, autoincrement=True),
        sa.Column("question_bank_id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), nullable=True),
        sa.Column("stock_weight", sa.Integer, nullable=False, server_default="50"),
        sa.Column("usage_weight", sa.Integer, nullable=False, server_default="30"),
        sa.Column("importance_weight", sa.Integer, nullable=False, server_default="20"),
        sa.Column("target_stock", sa.Integer, nullable=False, server_default="20"),
        sa.Column("usage_window_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column("recent_answers_per_question_target", sa.Integer, nullable=False, server_default="3"),
        sa.Column("usage_extra_ratio", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("max_per_knowledge_per_task", sa.Integer, nullable=False, server_default="10"),
        sa.Column("min_demand_score", sa.Float, nullable=False, server_default="0.15"),
        sa.Column("is_enabled", sa.Integer, nullable=False, server_default="1"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(3), nullable=False),
        sa.Column("updated_at", sa.DateTime(3), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("idx_qgp_question_bank", "question_generation_policy", ["question_bank_id"])

    # 4. task allocation fields
    op.add_column("question_generation_task", sa.Column("allocation_mode", sa.String(20), nullable=False, server_default="manual"))
    op.add_column("question_generation_task", sa.Column("allocation_plan", JSON, nullable=True))
    op.add_column("question_generation_task", sa.Column("policy_snapshot", JSON, nullable=True))
    op.add_column("question_generation_task", sa.Column("requested_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("question_generation_task", sa.Column("allocated_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("question_generation_task", sa.Column("unallocated_count", sa.Integer, nullable=False, server_default="0"))

    # 5. seed default global policy
    op.execute("""
        INSERT IGNORE INTO question_generation_policy
        (question_bank_id, stock_weight, usage_weight, importance_weight, target_stock,
         usage_window_days, recent_answers_per_question_target, usage_extra_ratio,
         max_per_knowledge_per_task, min_demand_score, is_enabled, version, created_at, updated_at)
        VALUES (NULL, 50, 30, 20, 20, 30, 3, 0.5, 10, 0.15, 1, 1, NOW(3), NOW(3))
    """)


def downgrade() -> None:
    op.drop_column("question_generation_task", "unallocated_count")
    op.drop_column("question_generation_task", "allocated_count")
    op.drop_column("question_generation_task", "requested_count")
    op.drop_column("question_generation_task", "policy_snapshot")
    op.drop_column("question_generation_task", "allocation_plan")
    op.drop_column("question_generation_task", "allocation_mode")
    op.drop_table("question_generation_policy")
    op.drop_table("question_bank_knowledge_base")
    op.drop_column("knowledge", "importance_source")
    op.drop_column("knowledge", "importance_level")
