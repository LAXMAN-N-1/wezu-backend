"""add station_id and related_to_id to support_tickets

Revision ID: b2c3d4e5f6g7
Revises: f1e2d3c4b5a6
Create Date: 2026-04-07 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'f1e2d3c4b5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Rename assigned_to to assigned_to_id
    op.alter_column('support_tickets', 'assigned_to', new_column_name='assigned_to_id', schema='core')
    
    # Add station_id and related_to_id
    op.add_column('support_tickets', sa.Column('station_id', sa.Integer(), nullable=True), schema='core')
    op.add_column('support_tickets', sa.Column('related_to_id', sa.Integer(), nullable=True), schema='core')
    
    # Foreign Keys
    op.create_foreign_key(
        'support_tickets_station_id_fkey',
        'support_tickets', 'stations',
        ['station_id'], ['id'],
        source_schema='core', referent_schema='stations'
    )
    op.create_foreign_key(
        'support_tickets_related_to_id_fkey',
        'support_tickets', 'support_tickets',
        ['related_to_id'], ['id'],
        source_schema='core', referent_schema='core'
    )

def downgrade() -> None:
    op.drop_constraint('support_tickets_related_to_id_fkey', 'support_tickets', schema='core')
    op.drop_constraint('support_tickets_station_id_fkey', 'support_tickets', schema='core')
    op.drop_column('support_tickets', 'related_to_id', schema='core')
    op.drop_column('support_tickets', 'station_id', schema='core')
