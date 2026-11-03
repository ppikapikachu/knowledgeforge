"""question_comment.user_id 历史列改为可空（评论身份迁移到 app_user_id）。

Revision ID: m3d4e5f6a7b8
Revises: l2c3d4e5f6a7
背景：comment 历史行为管理员发帖（user_id=admin_user.id，NOT NULL）。
身份迁移后新评论归属普通用户（app_user_id），user_id 不再写入。
为避免用管理员 ID 或占位值冒充作者，历史列改为可空；历史行数据不变。

注意 MySQL 1553 教训：先删外键/唯一约束，再删支撑索引，最后删列。
本迁移只改列可空性，不涉及索引删除。
"""

from alembic import op
import sqlalchemy as sa

revision = "m3d4e5f6a7b8"
down_revision = "l2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 新评论不再写 user_id（历史管理员语义列）；历史行值保留不动
    op.alter_column(
        "question_comment",
        "user_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    # 回滚：先把空值统一置 0（无管理员归属），再收紧为 NOT NULL（不删数据）
    op.execute("UPDATE question_comment SET user_id = 0 WHERE user_id IS NULL")
    op.alter_column(
        "question_comment",
        "user_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
