"""add_advanced_features

Revision ID: cf80f79c918b
Revises: c14a61f942ca
Create Date: 2025-12-22 15:17:25.604795

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'cf80f79c918b'
down_revision: Union[str, None] = 'c14a61f942ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Geofence
    op.add_column('geofence', sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='safe_zone'))
    op.add_column('geofence', sa.Column('polygon_coords', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    
    # Notification
    op.add_column('notification', sa.Column('channel', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='push'))
    op.add_column('notification', sa.Column('payload', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('notification', sa.Column('scheduled_at', sa.DateTime(), nullable=True))
    op.add_column('notification', sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='pending'))
    
    # VideoKYCSession
    op.add_column('videokycsession', sa.Column('scheduled_at', sa.DateTime(), nullable=True))
    op.add_column('videokycsession', sa.Column('agent_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'videokycsession', 'user', ['agent_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'videokycsession', type_='foreignkey')
    op.drop_column('videokycsession', 'agent_id')
    op.drop_column('videokycsession', 'scheduled_at')
    
    op.drop_column('notification', 'status')
    op.drop_column('notification', 'scheduled_at')
    op.drop_column('notification', 'payload')
    op.drop_column('notification', 'channel')
    
    op.drop_column('geofence', 'polygon_coords')
    op.drop_column('geofence', 'type')
