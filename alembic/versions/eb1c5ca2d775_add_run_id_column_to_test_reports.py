"""add run_id column to test_reports

Revision ID: eb1c5ca2d775
Revises: 6ab5602832e3
Create Date: 2026-04-21 12:11:47.024226

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb1c5ca2d775'
down_revision: Union[str, None] = '6ab5602832e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add run_id to test_reports
    op.add_column('test_reports', sa.Column('run_id', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_test_reports_run_id'), 'test_reports', ['run_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_test_reports_run_id'), table_name='test_reports')
    op.drop_column('test_reports', 'run_id')
