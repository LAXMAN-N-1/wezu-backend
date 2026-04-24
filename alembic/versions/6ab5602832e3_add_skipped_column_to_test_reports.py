"""add skipped column to test_reports

Revision ID: 6ab5602832e3
Revises: ed574375ad16
Create Date: 2026-04-21 11:30:51.601462

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ab5602832e3'
down_revision: Union[str, None] = 'ed574375ad16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('test_reports', sa.Column('skipped', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('test_reports', 'skipped')
