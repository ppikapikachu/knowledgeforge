"""question 多层去重：指纹版本/去重唯一键、任务去重统计、审计表

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-20

说明（执行文档 §11）：
- question 新增 hash_version / dedup_key。dedup_key 仅对阻断状态
  (pending_review/published) 题目取 content_hash，其余状态为 NULL；
  MySQL 唯一索引允许多个 NULL，因此 rejected/disabled 不会阻塞新题入库。
- 回填 dedup_key 时如遇历史指纹冲突（同一指纹多行），保留 id 最小的一行，
  其余置 NULL，并保留全部历史数据（不删除任何业务行）。
- 历史行 content_hash 为旧版（content-only 16位）指纹，hash_version='0'；
  需运行 scripts/rehash_questions.py 重算 v1 指纹后精确去重层才覆盖历史题。
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. question 指纹版本 + 去重唯一键
    op.add_column("question", sa.Column("hash_version", sa.String(8), nullable=True, server_default="0"))
    op.add_column("question", sa.Column("dedup_key", sa.String(64), nullable=True))

    conn = op.get_bind()
    # 回填：阻断状态题目的 dedup_key = content_hash
    conn.execute(sa.text(
        "UPDATE question SET dedup_key = content_hash "
        "WHERE content_hash IS NOT NULL AND status IN ('pending_review', 'published')"
    ))
    # 冲突安全：同一 dedup_key 保留 id 最小行，其余置 NULL（不删除数据）
    conn.execute(sa.text(
        "UPDATE question q JOIN ("
        "  SELECT dedup_key, MIN(id) AS keep_id FROM question "
        "  WHERE dedup_key IS NOT NULL GROUP BY dedup_key HAVING COUNT(*) > 1"
        ") d ON q.dedup_key = d.dedup_key AND q.id <> d.keep_id "
        "SET q.dedup_key = NULL"
    ))

    op.create_index("uq_question_dedup_key", "question", ["dedup_key"], unique=True)
    op.create_index("idx_question_content_hash", "question", ["content_hash"], unique=False)

    # 2. 任务去重统计字段
    for col, comment in (
        ("generated_count", "实际生成的候选题目数量"),
        ("exact_duplicate_count", "精确重复跳过数量"),
        ("semantic_duplicate_count", "算法/语义重复跳过数量"),
        ("uncertain_count", "去重不确定、保留并标记人工复核数量"),
        ("unfulfilled_count", "重试用尽后仍未补足数量"),
    ):
        op.add_column("question_generation_task", sa.Column(col, sa.Integer, nullable=False, server_default="0"))

    # 3. 去重判定审计表
    op.create_table(
        "question_dedup_record",
        sa.Column("id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"),
                  sa.ForeignKey("question_generation_task.id", ondelete="SET NULL"), nullable=True),
        sa.Column("new_content_hash", sa.String(64), nullable=False),
        sa.Column("new_hash_version", sa.String(8), nullable=False, server_default="1"),
        sa.Column("new_content_snapshot", sa.Text, nullable=False),
        sa.Column("new_question_type", sa.String(30), nullable=False),
        sa.Column("new_question_bank_id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), nullable=True),
        sa.Column("new_knowledge_ids", JSON, nullable=True),
        sa.Column("matched_question_id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), nullable=True),
        sa.Column("matched_question_bank_id", sa.BigInteger().with_variant(sa.BigInteger, "mysql"), nullable=True),
        sa.Column("matched_knowledge_ids", JSON, nullable=True),
        sa.Column("matched_source", sa.String(10), nullable=True),
        sa.Column("scope_mode", sa.String(20), nullable=True),
        sa.Column("keyword_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("algorithm_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("llm_called", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("llm_decision", sa.String(20), nullable=True),
        sa.Column("llm_reason", sa.Text, nullable=True),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("decision_method", sa.String(30), nullable=False),
        sa.Column("needs_manual_review", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("embedding_model", sa.String(255), nullable=True),
        sa.Column("embedding_version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(3), nullable=False),
        sa.Column("updated_at", sa.DateTime(3), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("idx_qdr_task_id", "question_dedup_record", ["task_id"])
    op.create_index("idx_qdr_new_hash", "question_dedup_record", ["new_content_hash"])
    op.create_index("idx_qdr_matched_question", "question_dedup_record", ["matched_question_id"])


def downgrade() -> None:
    # 业务数据不删除：仅回滚本次新增的列/索引/审计表
    op.drop_index("idx_qdr_matched_question", table_name="question_dedup_record")
    op.drop_index("idx_qdr_new_hash", table_name="question_dedup_record")
    op.drop_index("idx_qdr_task_id", table_name="question_dedup_record")
    op.drop_table("question_dedup_record")

    for col in ("unfulfilled_count", "uncertain_count", "semantic_duplicate_count",
                "exact_duplicate_count", "generated_count"):
        op.drop_column("question_generation_task", col)

    op.drop_index("idx_question_content_hash", table_name="question")
    op.drop_index("uq_question_dedup_key", table_name="question")
    op.drop_column("question", "dedup_key")
    op.drop_column("question", "hash_version")
