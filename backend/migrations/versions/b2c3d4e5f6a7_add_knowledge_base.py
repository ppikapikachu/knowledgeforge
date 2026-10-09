"""新增 knowledge_base 表和 knowledge/import_task 的归属字段

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-09 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 创建 knowledge_base 表
    op.create_table(
        'knowledge_base',
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
        sa.UniqueConstraint('code', name='uq_kb_code'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
    )
    op.create_index('idx_kb_status', 'knowledge_base', ['status'], unique=False)

    # 2. 插入初始知识库数据（幂等：INSERT IGNORE）
    connection = op.get_bind()
    connection.execute(sa.text("""
        INSERT IGNORE INTO knowledge_base (code, name, description, status)
        VALUES
            ('android', 'Android', 'Android 开发相关知识', 1),
            ('java', 'Java', 'Java 语言和生态相关知识', 1),
            ('distributed_systems', '分布式系统', '分布式架构和中间件相关知识', 1),
            ('c_language', 'C 语言', 'C 语言编程相关知识', 1),
            ('uncategorized', '未分类', '尚未归类的知识点', 1)
    """))

    # 3. 获取 uncategorized 的 ID
    result = connection.execute(sa.text(
        "SELECT id FROM knowledge_base WHERE code = 'uncategorized'"
    ))
    uncategorized_id = result.scalar()

    # 4. knowledge 表增加 knowledge_base_id（先加可空字段）
    op.add_column(
        'knowledge',
        sa.Column('knowledge_base_id', sa.BigInteger().with_variant(sa.BigInteger(), 'mysql'),
                  nullable=True, comment='所属知识库 ID'),
    )

    # 5. 回填旧知识到未分类
    connection.execute(sa.text(
        f"UPDATE knowledge SET knowledge_base_id = {uncategorized_id} WHERE knowledge_base_id IS NULL"
    ))

    # 6. 设置为非空 + 外键
    op.alter_column(
        'knowledge', 'knowledge_base_id',
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.create_foreign_key(
        'fk_knowledge_kb', 'knowledge', 'knowledge_base',
        ['knowledge_base_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_index('idx_knowledge_kb_id', 'knowledge', ['knowledge_base_id'], unique=False)

    # 7. knowledge_import_task 表增加 knowledge_base_id
    op.add_column(
        'knowledge_import_task',
        sa.Column('knowledge_base_id', sa.BigInteger().with_variant(sa.BigInteger(), 'mysql'),
                  nullable=True, comment='目标知识库 ID'),
    )
    connection.execute(sa.text(
        f"UPDATE knowledge_import_task SET knowledge_base_id = {uncategorized_id} WHERE knowledge_base_id IS NULL"
    ))
    op.alter_column(
        'knowledge_import_task', 'knowledge_base_id',
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.create_foreign_key(
        'fk_import_task_kb', 'knowledge_import_task', 'knowledge_base',
        ['knowledge_base_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_index('idx_import_task_kb_id', 'knowledge_import_task', ['knowledge_base_id'], unique=False)


def downgrade() -> None:
    op.drop_constraint('fk_import_task_kb', 'knowledge_import_task', type_='foreignkey')
    op.drop_index('idx_import_task_kb_id', table_name='knowledge_import_task')
    op.drop_column('knowledge_import_task', 'knowledge_base_id')

    op.drop_constraint('fk_knowledge_kb', 'knowledge', type_='foreignkey')
    op.drop_index('idx_knowledge_kb_id', table_name='knowledge')
    op.drop_column('knowledge', 'knowledge_base_id')

    op.drop_index('idx_kb_status', table_name='knowledge_base')
    op.drop_table('knowledge_base')
