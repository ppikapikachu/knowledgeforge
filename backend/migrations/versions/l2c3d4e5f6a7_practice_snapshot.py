"""练习快照与会话体系

新增 practice_paper / practice_paper_item / practice_session / practice_session_item 表；
question_answer_record 增加试卷/快照题目/练习会话关联列
（历史记录保持 NULL，不伪造归属）。

Revision ID: l2c3d4e5f6a7
Revises: k1b2c3d4e5f6
Create Date: 2026-11-02
"""

from alembic import op
import sqlalchemy as sa

revision = "l2c3d4e5f6a7"
down_revision = "k1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 试卷快照头
    op.create_table(
        "practice_paper",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("source_question_bank_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("assembly_config", sa.JSON(), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_score", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="ready"),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["app_user.id"],
                                name="fk_pp_owner", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_question_bank_id"], ["question_bank.id"],
                                name="fk_pp_bank", ondelete="SET NULL"),
        sa.UniqueConstraint("owner_user_id", "idempotency_key", name="uq_paper_owner_idem"),
        sa.Index("idx_pp_owner_created", "owner_user_id", "created_at"),
        sa.Index("idx_pp_owner_status_created", "owner_user_id", "status", "created_at"),
        sa.Index("idx_pp_bank", "source_question_bank_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )

    # 2. 试卷题目快照（不可变）
    op.create_table(
        "practice_paper_item",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("paper_id", sa.BigInteger(), nullable=False),
        sa.Column("source_question_id", sa.BigInteger(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("question_type", sa.String(30), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("score", sa.Numeric(10, 2), nullable=False, server_default="5"),
        sa.Column("source_status_at_snapshot", sa.String(30), nullable=False,
                  server_default="published"),
        sa.Column("source_content_hash", sa.String(64), nullable=True),
        sa.Column("knowledge_snapshot", sa.JSON(), nullable=True),
        sa.Column("question_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["practice_paper.id"],
                                name="fk_ppi_paper", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_question_id"], ["question.id"],
                                name="fk_ppi_question", ondelete="RESTRICT"),
        sa.UniqueConstraint("paper_id", "sort_order", name="uq_ppi_paper_sort"),
        sa.Index("idx_ppi_paper_sort", "paper_id", "sort_order"),
        sa.Index("idx_ppi_source_question", "source_question_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )

    # 3. 练习会话
    op.create_table(
        "practice_session",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("app_user_id", sa.BigInteger(), nullable=False),
        sa.Column("paper_id", sa.BigInteger(), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False, server_default="practice"),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("current_item_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("answered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("incorrect_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ungraded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("last_active_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("abandoned_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["app_user_id"], ["app_user.id"],
                                name="fk_ps_user", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["paper_id"], ["practice_paper.id"],
                                name="fk_ps_paper", ondelete="RESTRICT"),
        sa.Index("idx_ps_user_status_active", "app_user_id", "status", "last_active_at"),
        sa.Index("idx_ps_user_created", "app_user_id", "created_at"),
        sa.Index("idx_ps_paper", "paper_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )

    # 4. 会话题目状态
    op.create_table(
        "practice_session_item",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("paper_item_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="unanswered"),
        sa.Column("draft_answer", sa.JSON(), nullable=True),
        sa.Column("is_marked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("latest_answer_record_id", sa.BigInteger(), nullable=True),
        sa.Column("latest_is_correct", sa.Boolean(), nullable=True),
        sa.Column("latest_grading_status", sa.String(30), nullable=True),
        sa.Column("first_submitted_at", sa.DateTime(), nullable=True),
        sa.Column("last_submitted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["practice_session.id"],
                                name="fk_psi_session", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paper_item_id"], ["practice_paper_item.id"],
                                name="fk_psi_paper_item", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["latest_answer_record_id"], ["question_answer_record.id"],
                                name="fk_psi_answer", ondelete="SET NULL"),
        sa.UniqueConstraint("session_id", "paper_item_id", name="uq_psi_session_item"),
        sa.Index("idx_psi_session_status", "session_id", "status"),
        sa.Index("idx_psi_session_marked", "session_id", "is_marked"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )

    # 5. question_answer_record：试卷/快照题目/会话关联 + 会话统计索引
    op.add_column("question_answer_record",
                  sa.Column("practice_paper_id", sa.BigInteger(), nullable=True,
                            comment="试卷快照 ID（旧的非试卷答题为 NULL）"))
    op.add_column("question_answer_record",
                  sa.Column("practice_paper_item_id", sa.BigInteger(), nullable=True,
                            comment="试卷题目快照 ID"))
    op.add_column("question_answer_record",
                  sa.Column("practice_session_id", sa.BigInteger(), nullable=True,
                            comment="练习会话 ID（单题练习为 NULL）"))
    op.create_foreign_key("fk_qar_paper", "question_answer_record", "practice_paper",
                          ["practice_paper_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_qar_paper_item", "question_answer_record", "practice_paper_item",
                          ["practice_paper_item_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_qar_session", "question_answer_record", "practice_session",
                          ["practice_session_id"], ["id"], ondelete="RESTRICT")
    op.create_index("idx_qar_session_question", "question_answer_record",
                    ["practice_session_id", "question_id", "created_at"])


def downgrade() -> None:
    # 注意顺序（MySQL 1553）：先删外键，再删其支撑索引，最后删列
    op.drop_constraint("fk_qar_session", "question_answer_record", type_="foreignkey")
    op.drop_constraint("fk_qar_paper_item", "question_answer_record", type_="foreignkey")
    op.drop_constraint("fk_qar_paper", "question_answer_record", type_="foreignkey")
    op.drop_index("idx_qar_session_question", table_name="question_answer_record")
    op.drop_column("question_answer_record", "practice_session_id")
    op.drop_column("question_answer_record", "practice_paper_item_id")
    op.drop_column("question_answer_record", "practice_paper_id")

    op.drop_table("practice_session_item")
    op.drop_table("practice_session")
    op.drop_table("practice_paper_item")
    op.drop_table("practice_paper")
