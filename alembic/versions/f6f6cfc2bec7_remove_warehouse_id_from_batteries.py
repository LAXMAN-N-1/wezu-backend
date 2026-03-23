"""remove warehouse_id from batteries

Revision ID: f6f6cfc2bec7
Revises: 11cdc2dd0954
Create Date: 2026-03-12 16:22:26.869632

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6f6cfc2bec7'
down_revision: Union[str, None] = '11cdc2dd0954'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('batteries', 'warehouse_id', schema='inventory')


def downgrade() -> None:
    op.add_column('batteries', sa.Column('warehouse_id', sa.Integer(), nullable=True), schema='inventory')
