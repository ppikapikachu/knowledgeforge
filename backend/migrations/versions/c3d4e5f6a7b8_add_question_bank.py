"""新增 question_bank 表和 question 的题库归属

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-10 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 创建 question_bank 表
    op.create_table(
        'question_bank',
        sa.Column('id', sa.BigInteger().with_variant(sa.BigInteger(), 'mysql'),
                  autoincrement=True, nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_qb_code'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
    )
    op.create_index('idx_qb_status', 'question_bank', ['status'], unique=False)

    # 2. 插入内置题库（幂等）
    connection = op.get_bind()
    connection.execute(sa.text("""
        INSERT IGNORE INTO question_bank (code, name, description, status)
        VALUES
            ('java_basic', 'Java 基础', '语法、面向对象、常用基础 API、异常处理等', 1),
            ('java_collection', 'Java 集合框架', 'List、Set、Map、集合实现与使用场景等', 1),
            ('java_concurrency', 'Java 并发编程', '线程、锁、并发工具、线程池、JMM 等', 1),
            ('jvm', 'JVM', '运行时数据区、类加载、垃圾回收、字节码等', 1),
            ('android_native', '原生 Android', '四大组件、生命周期、Handler/Looper 等', 1),
            ('database_basic', '数据库基础', 'SQL、索引、事务、数据库原理等', 1),
            ('distributed_system', '分布式系统', '分布式一致性、服务治理、缓存与消息等', 1),
            ('uncategorized', '未分类题库', '无法可靠分类的存量题目兜底', 1)
    """))

    # 3. 获取未分类题库 ID
    result = connection.execute(sa.text(
        "SELECT id FROM question_bank WHERE code = 'uncategorized'"
    ))
    uncategorized_id = result.scalar()

    # 4. question 表增加 question_bank_id
    op.add_column(
        'question',
        sa.Column('question_bank_id', sa.BigInteger().with_variant(sa.BigInteger(), 'mysql'),
                  nullable=True, comment='所属题库 ID'),
    )

    # 5. 回填存量题目到未分类
    connection.execute(sa.text(
        f"UPDATE question SET question_bank_id = {uncategorized_id} WHERE question_bank_id IS NULL"
    ))

    # 6. 设置非空 + 外键
    op.alter_column(
        'question', 'question_bank_id',
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.create_foreign_key(
        'fk_question_bank', 'question', 'question_bank',
        ['question_bank_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_index('idx_question_bank_id', 'question', ['question_bank_id'], unique=False)


def downgrade() -> None:
    op.drop_constraint('fk_question_bank', 'question', type_='foreignkey')
    op.drop_index('idx_question_bank_id', table_name='question')
    op.drop_column('question', 'question_bank_id')

    op.drop_index('idx_qb_status', table_name='question_bank')
    op.drop_table('question_bank')
