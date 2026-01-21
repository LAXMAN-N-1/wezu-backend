"""add_ops_features

Revision ID: 41ba6ceabd2a
Revises: cf80f79c918b
Create Date: 2025-12-22 15:21:58.589564

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '41ba6ceabd2a'
down_revision: Union[str, None] = 'cf80f79c918b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # MaintenanceSchedule
    op.create_table('maintenanceschedule',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('model_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('interval_days', sa.Integer(), nullable=True),
        sa.Column('interval_cycles', sa.Integer(), nullable=True),
        sa.Column('checklist', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # MaintenanceRecord
    op.create_table('maintenancerecord',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('technician_id', sa.Integer(), nullable=False),
        sa.Column('maintenance_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('cost', sa.Float(), nullable=False),
        sa.Column('parts_replaced', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('performed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['technician_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # StationDowntime
    op.create_table('stationdowntime',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(['station_id'], ['station.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Translation
    op.create_table('translation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('language_code', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('value', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('context', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_translation_key'), 'translation', ['key'], unique=False)
    op.create_index(op.f('ix_translation_language_code'), 'translation', ['language_code'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_translation_language_code'), table_name='translation')
    op.drop_index(op.f('ix_translation_key'), table_name='translation')
    op.drop_table('translation')
    op.drop_table('stationdowntime')
    op.drop_table('maintenancerecord')
    op.drop_table('maintenanceschedule')
