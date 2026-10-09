"""ImportTask 统计字段

Revision ID: a1b2c3d4e5f6
Revises: 4e328b1185f7
Create Date: 2026-09-17 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '4e328b1185f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 knowledge_import_task 增加统计字段。"""
    op.add_column(
        'knowledge_import_task',
        sa.Column('candidate_count', sa.Integer(), nullable=False,
                  server_default='0', comment='候选知识点总数'),
    )
    op.add_column(
        'knowledge_import_task',
        sa.Column('new_count', sa.Integer(), nullable=False,
                  server_default='0', comment='新增知识点数'),
    )
    op.add_column(
        'knowledge_import_task',
        sa.Column('duplicate_count', sa.Integer(), nullable=False,
                  server_default='0', comment='重复知识点数'),
    )
    op.add_column(
        'knowledge_import_task',
        sa.Column('merge_count', sa.Integer(), nullable=False,
                  server_default='0', comment='合并知识点数'),
    )
    op.add_column(
        'knowledge_import_task',
        sa.Column('failed_count', sa.Integer(), nullable=False,
                  server_default='0', comment='失败知识点数'),
    )


def downgrade() -> None:
    """移除统计字段。"""
    op.drop_column('knowledge_import_task', 'failed_count')
    op.drop_column('knowledge_import_task', 'merge_count')
    op.drop_column('knowledge_import_task', 'duplicate_count')
    op.drop_column('knowledge_import_task', 'new_count')
    op.drop_column('knowledge_import_task', 'candidate_count')
