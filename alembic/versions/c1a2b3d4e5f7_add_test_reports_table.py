"""add test_reports table

Revision ID: c1a2b3d4e5f7
Revises: merge_e28d_f6f6
Create Date: 2026-03-31 21:39:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c1a2b3d4e5f7'
down_revision: Union[str, None] = 'ba316815d31e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'test_reports',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('created_by', sa.String(255), nullable=False, server_default='dev'),
        sa.Column('module_name', sa.String(255), nullable=False),
        sa.Column('total_tests', sa.Integer(), nullable=False),
        sa.Column('passed', sa.Integer(), nullable=False),
        sa.Column('failed', sa.Integer(), nullable=False),
        sa.Column('failures', sa.JSON(), nullable=True),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('execution_time', sa.String(50), nullable=False),
        sa.Column('environment', sa.String(50), nullable=False, server_default='local'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
    )
    op.create_index('ix_test_reports_id', 'test_reports', ['id'])


def downgrade() -> None:
    op.drop_index('ix_test_reports_id', table_name='test_reports')
    op.drop_table('test_reports')
