"""Add ui_preferences and dashboard_layout to user

Revision ID: 71d9b9290c4f
Revises: 73010826b682
Create Date: 2026-03-31 09:45:19.555293

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71d9b9290c4f'
down_revision: Union[str, None] = '73010826b682'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('ui_preferences', sa.String(), nullable=True))
    op.add_column('users', sa.Column('dashboard_layout', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'dashboard_layout')
    op.drop_column('users', 'ui_preferences')
