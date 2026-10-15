"""题目生成/答题/评论相关表和字段

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-10 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    # 1. question 表增加新字段
    op.add_column('question', sa.Column('explanation', sa.Text(), nullable=True))
    op.add_column('question', sa.Column('explanation_status', sa.String(30), nullable=False, server_default='not_requested'))
    op.add_column('question', sa.Column('explanation_source', sa.String(30), nullable=True))
    op.add_column('question', sa.Column('content_hash', sa.String(64), nullable=True))
    op.add_column('question', sa.Column('generation_task_id', sa.BigInteger(), nullable=True))

    # 更新 status 默认值
    op.alter_column('question', 'status', server_default='pending_review')

    # 2. question_generation_task 表
    op.create_table(
        'question_generation_task',
        sa.Column('id', sa.BigInteger().with_variant(sa.BigInteger(), 'mysql'), autoincrement=True, nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('request_config', mysql.JSON(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('total_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duplicate_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('explanation_requested', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'), nullable=True),
        sa.Column('completed_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'), nullable=True),
        sa.Column('created_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4', mysql_collate='utf8mb4_0900_ai_ci',
    )
    op.create_index('idx_qgt_status', 'question_generation_task', ['status'])
    op.create_index('idx_qgt_created_by', 'question_generation_task', ['created_by'])

    # 3. question_answer_record 表
    op.create_table(
        'question_answer_record',
        sa.Column('id', sa.BigInteger().with_variant(sa.BigInteger(), 'mysql'), autoincrement=True, nullable=False),
        sa.Column('question_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('user_answer', sa.String(500), nullable=True),
        sa.Column('is_correct', sa.Integer(), nullable=True),
        sa.Column('grading_status', sa.String(30), nullable=False, server_default='ungraded'),
        sa.Column('time_spent_ms', sa.Integer(), nullable=True),
        sa.Column('idempotency_key', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'), nullable=False),
        sa.Column('updated_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['question_id'], ['question.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('user_id', 'question_id', 'idempotency_key', name='uq_answer_idempotent'),
        mysql_charset='utf8mb4', mysql_collate='utf8mb4_0900_ai_ci',
    )
    op.create_index('idx_qar_question', 'question_answer_record', ['question_id', 'created_at'])
    op.create_index('idx_qar_user_question', 'question_answer_record', ['user_id', 'question_id', 'created_at'])

    # 4. question_comment 表
    op.create_table(
        'question_comment',
        sa.Column('id', sa.BigInteger().with_variant(sa.BigInteger(), 'mysql'), autoincrement=True, nullable=False),
        sa.Column('question_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='visible'),
        sa.Column('moderated_by', sa.BigInteger(), nullable=True),
        sa.Column('moderation_reason', sa.String(500), nullable=True),
        sa.Column('deleted_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'), nullable=True),
        sa.Column('created_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['question_id'], ['question.id'], ondelete='RESTRICT'),
        mysql_charset='utf8mb4', mysql_collate='utf8mb4_0900_ai_ci',
    )
    op.create_index('idx_qc_question', 'question_comment', ['question_id', 'status', 'created_at'])
    op.create_index('idx_qc_user', 'question_comment', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('question_comment')
    op.drop_table('question_answer_record')
    op.drop_table('question_generation_task')
    op.drop_column('question', 'generation_task_id')
    op.drop_column('question', 'content_hash')
    op.drop_column('question', 'explanation_source')
    op.drop_column('question', 'explanation_status')
    op.drop_column('question', 'explanation')
    op.alter_column('question', 'status', server_default='DRAFT')
