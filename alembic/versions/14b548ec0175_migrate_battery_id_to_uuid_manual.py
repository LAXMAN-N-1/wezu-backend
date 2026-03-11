"""migrate battery id to uuid manual

Revision ID: 14b548ec0175
Revises: 41b7931630bd
Create Date: 2026-03-08 16:29:33.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '14b548ec0175'
down_revision = '41b7931630bd'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Drop ALL dependent Foreign Keys
    op.execute("ALTER TABLE IF EXISTS rentals.rentals DROP CONSTRAINT IF EXISTS rentals_battery_id_fkey")
    op.execute("ALTER TABLE IF EXISTS stations.station_slots DROP CONSTRAINT IF EXISTS station_slots_battery_id_fkey")
    op.execute("ALTER TABLE IF EXISTS logistics.battery_transfers DROP CONSTRAINT IF EXISTS battery_transfers_battery_id_fkey")
    op.execute("ALTER TABLE IF EXISTS inventory.telemetry_logs DROP CONSTRAINT IF EXISTS telemetry_logs_battery_id_fkey")
    op.execute("ALTER TABLE IF EXISTS core.reviews DROP CONSTRAINT IF EXISTS reviews_battery_id_fkey")
    op.execute("ALTER TABLE IF EXISTS rentals.swap_sessions DROP CONSTRAINT IF EXISTS swap_sessions_old_battery_id_fkey")
    op.execute("ALTER TABLE IF EXISTS rentals.swap_sessions DROP CONSTRAINT IF EXISTS swap_sessions_new_battery_id_fkey")
    op.execute("ALTER TABLE IF EXISTS rentals.rental_events DROP CONSTRAINT IF EXISTS rental_events_battery_id_fkey")
    op.execute("ALTER TABLE IF EXISTS inventory.gps_tracking_log DROP CONSTRAINT IF EXISTS gps_tracking_log_battery_id_fkey")
    op.execute("ALTER TABLE IF EXISTS inventory.inventory_audit_logs DROP CONSTRAINT IF EXISTS inventory_audit_logs_battery_id_fkey")
    
    # 2. Drop the tables that need to change PK type or depend on it
    op.execute("DROP TABLE IF EXISTS inventory.battery_health_history")
    op.execute("DROP TABLE IF EXISTS inventory.battery_audit_logs")
    op.execute("DROP TABLE IF EXISTS inventory.battery_lifecycle_events")
    op.execute("DROP TABLE IF EXISTS inventory.batteries CASCADE")

    # 3. Recreate 'batteries' with UUID PK and new fields
    op.create_table('batteries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('serial_number', sa.String(), nullable=False),
        sa.Column('qr_code_data', sa.String(), nullable=True),
        sa.Column('iot_device_id', sa.String(), nullable=True),
        sa.Column('sku_id', sa.Integer(), sa.ForeignKey('inventory.battery_catalog.id'), nullable=True),
        sa.Column('station_id', sa.Integer(), sa.ForeignKey('stations.stations.id'), nullable=True),
        sa.Column('current_user_id', sa.Integer(), sa.ForeignKey('core.users.id'), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('core.users.id'), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='available'),
        sa.Column('health_status', sa.String(), nullable=False, server_default='good'),
        sa.Column('current_charge', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('health_percentage', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('cycle_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_cycles', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('temperature_c', sa.Float(), nullable=False, server_default='25.0'),
        sa.Column('manufacturer', sa.String(), nullable=True),
        sa.Column('battery_type', sa.String(), nullable=True, server_default='48V/30Ah'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('location_type', sa.String(), nullable=False, server_default='warehouse'),
        sa.Column('manufacture_date', sa.DateTime(), nullable=True),
        sa.Column('purchase_date', sa.DateTime(), nullable=True),
        sa.Column('warranty_expiry', sa.DateTime(), nullable=True),
        sa.Column('last_charged_at', sa.DateTime(), nullable=True),
        sa.Column('last_inspected_at', sa.DateTime(), nullable=True),
        sa.Column('last_maintenance_date', sa.DateTime(), nullable=True),
        sa.Column('last_telemetry_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('warehouse_id', sa.Integer(), sa.ForeignKey('logistics.warehouses.id'), nullable=True),
        schema='inventory'
    )
    op.create_index(op.f('ix_inventory_batteries_serial_number'), 'batteries', ['serial_number'], unique=True, schema='inventory')

    # 4. Recreate helper tables with UUID battery_id
    op.create_table('battery_lifecycle_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('battery_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory.batteries.id'), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        schema='inventory'
    )

    op.create_table('battery_audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('battery_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory.batteries.id'), nullable=False),
        sa.Column('changed_by', sa.Integer(), sa.ForeignKey('core.users.id'), nullable=True),
        sa.Column('field_changed', sa.String(), nullable=False),
        sa.Column('old_value', sa.String(), nullable=True),
        sa.Column('new_value', sa.String(), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        schema='inventory'
    )

    op.create_table('battery_health_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('battery_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory.batteries.id'), nullable=False),
        sa.Column('health_percentage', sa.Float(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        schema='inventory'
    )

    # 5. Fix Foreign Keys in other schemas to use UUID
    tables_to_fix = [
        ('rentals', 'rentals', 'battery_id', 'rentals_battery_id_fkey'),
        ('stations', 'station_slots', 'battery_id', 'station_slots_battery_id_fkey'),
        ('logistics', 'battery_transfers', 'battery_id', 'battery_transfers_battery_id_fkey'),
        ('inventory', 'telemetry_logs', 'battery_id', 'telemetry_logs_battery_id_fkey'),
        ('core', 'reviews', 'battery_id', 'reviews_battery_id_fkey'),
        ('rentals', 'swap_sessions', 'old_battery_id', 'swap_sessions_old_battery_id_fkey'),
        ('rentals', 'swap_sessions', 'new_battery_id', 'swap_sessions_new_battery_id_fkey'),
        ('rentals', 'rental_events', 'battery_id', 'rental_events_battery_id_fkey'),
        ('inventory', 'gps_tracking_log', 'battery_id', 'gps_tracking_log_battery_id_fkey'),
        ('inventory', 'inventory_audit_logs', 'battery_id', 'inventory_audit_logs_battery_id_fkey'),
    ]

    for schema, table, col, fk_name in tables_to_fix:
        # Cast to text then to UUID to avoid conversion errors on potential old data
        op.execute(f"ALTER TABLE {schema}.{table} ALTER COLUMN {col} TYPE UUID USING {col}::text::uuid")
        op.create_foreign_key(fk_name, table, 'batteries', [col], ['id'], source_schema=schema, referent_schema='inventory')

def downgrade() -> None:
    # Inverse operations (minimal, mostly for consistency)
    pass
