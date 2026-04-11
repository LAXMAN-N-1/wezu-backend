"""add missing battery fields manual

Revision ID: 11cdc2dd0954
Revises: 44f2d5399b8d
Create Date: 2026-03-12 16:03:56.346659

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '11cdc2dd0954'
down_revision: Union[str, None] = '44f2d5399b8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('batteries', sa.Column('last_maintenance_cycles', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('batteries', sa.Column('state_of_health', sa.Float(), nullable=False, server_default='100.0'))
    op.add_column('batteries', sa.Column('temperature_history', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('batteries', sa.Column('charge_cycles', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('batteries', sa.Column('location_id', sa.Integer(), nullable=True))

def downgrade() -> None:
    op.drop_column('batteries', 'location_id')
    op.drop_column('batteries', 'charge_cycles')
    op.drop_column('batteries', 'temperature_history')
    op.drop_column('batteries', 'state_of_health')
    op.drop_column('batteries', 'last_maintenance_cycles')
