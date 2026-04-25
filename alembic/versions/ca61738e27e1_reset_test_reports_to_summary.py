"""reset_test_reports_to_summary

Revision ID: ca61738e27e1
Revises: 82a8e8d0b7b1
Create Date: 2026-04-21 12:59:35.491196

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca61738e27e1'
down_revision: Union[str, None] = '82a8e8d0b7b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing table (which might have granular fields)
    op.drop_table('test_reports')
    
    # Create the table according to the TestReport model
    op.create_table(
        'test_reports',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=False, server_default='dev'),
        sa.Column('module_name', sa.String(255), nullable=False),
        sa.Column('total_tests', sa.Integer(), nullable=False),
        sa.Column('passed', sa.Integer(), nullable=False),
        sa.Column('failed', sa.Integer(), nullable=False),
        sa.Column('skipped', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failures', sa.JSON(), nullable=True),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('execution_time', sa.String(100), nullable=False),
        sa.Column('environment', sa.String(50), nullable=False, server_default='local'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_test_reports_run_id', 'test_reports', ['run_id'])


def downgrade() -> None:
    op.drop_index('ix_test_reports_run_id', table_name='test_reports')
    op.drop_table('test_reports')
    # Note: downgrade won't restore the granular schema easily, but that's fine here.
