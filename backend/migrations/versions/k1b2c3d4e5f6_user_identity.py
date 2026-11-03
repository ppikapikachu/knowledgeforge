"""普通用户体系与历史归属扩展

新增 app_user / user_auth_session 表；
为 question_answer_record / question_comment 增加正式普通用户外键 app_user_id
（历史记录保持 NULL，不伪造归属）；
question_answer_record 增加判分得分 score；
question_bank 增加用户端开放状态 is_available_for_practice。

Revision ID: k1b2c3d4e5f6
Revises: i9a0b1c2d3e4
Create Date: 2026-11-02
"""

from alembic import op
import sqlalchemy as sa

revision = "k1b2c3d4e5f6"
down_revision = "i9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 普通用户表
    op.create_table(
        "app_user",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account", sa.String(128), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("nickname", sa.String(64), nullable=True),
        sa.Column("avatar", sa.String(512), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account", name="uq_app_user_account"),
        sa.Index("idx_app_user_status", "status"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )

    # 2. 登录会话表（Refresh Token 哈希）
    op.create_table(
        "user_auth_session",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("app_user_id", sa.BigInteger(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("device_id", sa.String(128), nullable=True),
        sa.Column("device_name", sa.String(128), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("refresh_token_hash", name="uq_uas_token_hash"),
        sa.ForeignKeyConstraint(["app_user_id"], ["app_user.id"],
                                name="fk_uas_user", ondelete="RESTRICT"),
        sa.Index("idx_uas_user", "app_user_id", "created_at"),
        sa.Index("idx_uas_expires", "expires_at"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )

    # 3. question_answer_record：正式普通用户归属 + 得分 + 幂等/统计索引
    op.add_column("question_answer_record",
                  sa.Column("app_user_id", sa.BigInteger(), nullable=True,
                            comment="正式普通用户 ID（新接口必填；历史记录为 NULL）"))
    op.add_column("question_answer_record",
                  sa.Column("score", sa.Numeric(10, 2), nullable=True,
                            comment="本次判分得分（未判分为 NULL）"))
    op.create_foreign_key("fk_qar_app_user", "question_answer_record", "app_user",
                          ["app_user_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_answer_user_idem", "question_answer_record",
                                ["app_user_id", "idempotency_key"])
    op.create_index("idx_qar_question_graded", "question_answer_record",
                    ["question_id", "grading_status", "created_at"])
    op.create_index("idx_qar_app_user_created", "question_answer_record",
                    ["app_user_id", "created_at"])
    op.create_index("idx_qar_app_user_question", "question_answer_record",
                    ["app_user_id", "question_id", "created_at", "id"])

    # 4. question_comment：正式普通用户归属
    op.add_column("question_comment",
                  sa.Column("app_user_id", sa.BigInteger(), nullable=True,
                            comment="正式普通用户 ID（新接口必填；历史记录为 NULL）"))
    op.create_foreign_key("fk_qc_app_user", "question_comment", "app_user",
                          ["app_user_id"], ["id"], ondelete="RESTRICT")
    op.create_index("idx_qc_app_user", "question_comment", ["app_user_id", "created_at"])

    # 5. question_bank：用户端开放状态
    op.add_column("question_bank",
                  sa.Column("is_available_for_practice", sa.Boolean(), nullable=False,
                            server_default=sa.text("0"),
                            comment="是否对用户端开放练习（默认 false）"))


def downgrade() -> None:
    op.drop_column("question_bank", "is_available_for_practice")

    # 注意顺序（MySQL 1553）：先删外键/唯一约束，再删支撑索引，最后删列
    op.drop_constraint("fk_qc_app_user", "question_comment", type_="foreignkey")
    op.drop_index("idx_qc_app_user", table_name="question_comment")
    op.drop_column("question_comment", "app_user_id")

    op.drop_constraint("fk_qar_app_user", "question_answer_record", type_="foreignkey")
    op.drop_constraint("uq_answer_user_idem", "question_answer_record", type_="unique")
    op.drop_index("idx_qar_app_user_question", table_name="question_answer_record")
    op.drop_index("idx_qar_app_user_created", table_name="question_answer_record")
    op.drop_index("idx_qar_question_graded", table_name="question_answer_record")
    op.drop_column("question_answer_record", "score")
    op.drop_column("question_answer_record", "app_user_id")

    op.drop_table("user_auth_session")
    op.drop_table("app_user")
