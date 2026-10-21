"""question_dedup_record 增加向量通道分数与人工复核结论字段

背景（题目去重 API 修复与人工复核接口开发执行文档）：
1. vector_score：向量通道分数在判定时已计算但未落库，导致
   GET /question-dedup/records 返回字段缺失（AttributeError → HTTP 500）；
   补列并由 _build_record 回填，历史行默认 0.0。
2. 人工复核结论独立保存（manual_resolution/resolution_reason/resolved_by/resolved_at），
   不覆盖自动判定证据（decision/llm_decision/算法分数）；
   effective_decision = manual_resolution or decision 为派生值，不落库。

修订历史：
- f6a7b8c9d0e1: 去重 v1（hash_version/dedup_key/审计表）

Revision ID: g7a8b9c0d1e2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "g7a8b9c0d1e2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) 向量通道分数补列（历史行 0.0，保持既有算法分数不动）
    op.add_column(
        "question_dedup_record",
        sa.Column("vector_score", sa.Float(), nullable=False,
                  server_default="0", comment="向量通道分数"),
    )

    # 2) 人工复核结论（与自动判定证据分离，可追溯）
    op.add_column(
        "question_dedup_record",
        sa.Column("manual_resolution", sa.String(20), nullable=True,
                  comment="人工最终结论: duplicate/distinct（人工必须二选一）"),
    )
    op.add_column(
        "question_dedup_record",
        sa.Column("resolution_reason", sa.Text(), nullable=True,
                  comment="人工判断依据"),
    )
    op.add_column(
        "question_dedup_record",
        sa.Column("resolved_by", sa.BigInteger(), nullable=True,
                  comment="处理人（管理员 ID，取自认证上下文）"),
    )
    op.add_column(
        "question_dedup_record",
        sa.Column("resolved_at", mysql.DATETIME(fsp=3), nullable=True,
                  comment="人工处理时间"),
    )
    op.create_foreign_key(
        "fk_qdr_resolved_by_admin",
        "question_dedup_record", "admin_user",
        ["resolved_by"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_qdr_manual_resolution", "question_dedup_record",
        ["manual_resolution"], unique=False,
    )


def downgrade() -> None:
    # 业务数据不删除；仅回退本次新增的结构（人工结论字段随列移除）
    op.drop_index("idx_qdr_manual_resolution", table_name="question_dedup_record")
    op.drop_constraint("fk_qdr_resolved_by_admin", "question_dedup_record", type_="foreignkey")
    op.drop_column("question_dedup_record", "resolved_at")
    op.drop_column("question_dedup_record", "resolved_by")
    op.drop_column("question_dedup_record", "resolution_reason")
    op.drop_column("question_dedup_record", "manual_resolution")
    op.drop_column("question_dedup_record", "vector_score")
