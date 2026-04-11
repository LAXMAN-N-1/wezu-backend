"""add_payout_settings

Revision ID: a1b2c3d4e5f6
Revises: 7272fc017d9d
Create Date: 2026-04-01 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '7a8c9d1e2f3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('dealer_profiles', sa.Column('payout_interval', sa.String(), server_default='Weekly', nullable=True))
    op.add_column('dealer_profiles', sa.Column('min_payout_amount', sa.Float(), server_default='0.0', nullable=True))

def downgrade() -> None:
    op.drop_column('dealer_profiles', 'min_payout_amount')
    op.drop_column('dealer_profiles', 'payout_interval')
