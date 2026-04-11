"""Add battery management tables and fields manual

Revision ID: 41b7931630bd
Revises: d6b338f82335
Create Date: 2026-03-08 16:08:05.541972

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '41b7931630bd'
down_revision: Union[str, None] = 'd6b338f82335'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create LocationType Enum in inventory schema
    location_type = sa.Enum('station', 'warehouse', 'service_center', 'recycling', name='locationtype')
    location_type.create(op.get_bind(), checkfirst=True)

    # 2. Add POOR to BatteryHealth Enum (Public schema or wherever it exists)
    # We should probably check where batteryhealth type is. Assuming public.
    op.execute("ALTER TYPE batteryhealth ADD VALUE IF NOT EXISTS 'POOR'")

    # 3. Add columns to batteries table
    op.add_column('batteries', sa.Column('manufacturer', sa.String(), nullable=True))
    op.add_column('batteries', sa.Column('notes', sa.String(), nullable=True))
    
    # We use a raw string for the enum back-reference in the Column
    location_type_enum = postgresql.ENUM('station', 'warehouse', 'service_center', 'recycling', name='locationtype')
    op.add_column('batteries', sa.Column('location_type', location_type_enum, nullable=False, server_default='warehouse'))
    
    op.add_column('batteries', sa.Column('manufacture_date', sa.DateTime(), nullable=True))
    op.add_column('batteries', sa.Column('last_charged_at', sa.DateTime(), nullable=True))


    # 4. Create BatteryAuditLog table
    op.create_table('battery_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('battery_id', sa.Integer(), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=True),
        sa.Column('field_changed', sa.String(), nullable=False),
        sa.Column('old_value', sa.String(), nullable=True),
        sa.Column('new_value', sa.String(), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['battery_id'], ['batteries.id'], ),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_battery_audit_logs_battery_id'), 'battery_audit_logs', ['battery_id'], unique=False)

    # 5. Create BatteryHealthHistory table
    op.create_table('battery_health_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('battery_id', sa.Integer(), nullable=False),
        sa.Column('health_percentage', sa.Float(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['battery_id'], ['batteries.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_battery_health_history_battery_id'), 'battery_health_history', ['battery_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_inventory_battery_health_history_battery_id'), table_name='battery_health_history')
    op.drop_table('battery_health_history')
    op.drop_index(op.f('ix_inventory_battery_audit_logs_battery_id'), table_name='battery_audit_logs')
    op.drop_table('battery_audit_logs')
    
    op.drop_column('batteries', 'last_charged_at')
    op.drop_column('batteries', 'manufacture_date')
    op.drop_column('batteries', 'location_type')
    op.drop_column('batteries', 'notes')
    op.drop_column('batteries', 'manufacturer')
    
    # Note: Removing a value from a PG Enum is hard, usually we leave it.
    # op.execute("DROP TYPE locationtype") # Only if you want to fully revert type creation

