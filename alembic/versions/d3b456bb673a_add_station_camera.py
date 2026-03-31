"""add_station_camera

Revision ID: d3b456bb673a
Revises: a1b2c3d4e5f6
Create Date: 2026-03-21 17:26:20.372198
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'd3b456bb673a'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'station_cameras',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('rtsp_url', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['station_id'], ['stations.stations.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='stations'
    )

    op.create_index(
        'ix_stations_station_cameras_station_id',
        'station_cameras',
        ['station_id'],
        schema='stations'
    )


def downgrade() -> None:
    op.drop_table('station_cameras', schema='stations')

