"""move back to int and add cameras

Revision ID: bbcd48f1ed4a
Revises: 576cdee84c79
Create Date: 2026-04-16 18:29:49.935921

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bbcd48f1ed4a'
down_revision: Union[str, None] = '576cdee84c79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Drop ALL dependent Foreign Keys first
    foreign_keys_to_drop = [
        ('rentals', 'rentals_battery_id_fkey'),
        ('station_slots', 'station_slots_battery_id_fkey'),
        ('battery_transfers', 'battery_transfers_battery_id_fkey'),
        ('telemetry_logs', 'telemetry_logs_battery_id_fkey'),
        ('reviews', 'reviews_battery_id_fkey'),
        ('swap_sessions', 'swap_sessions_old_battery_id_fkey'),
        ('swap_sessions', 'swap_sessions_new_battery_id_fkey'),
        ('rental_events', 'rental_events_battery_id_fkey'),
        ('gps_tracking_log', 'gps_tracking_log_battery_id_fkey'),
        ('inventory_audit_logs', 'inventory_audit_logs_battery_id_fkey'),
        ('iot_devices', 'iot_devices_battery_id_fkey'),
        ('battery_lifecycle_events', 'battery_lifecycle_events_battery_id_fkey'),
        ('battery_audit_logs', 'battery_audit_logs_battery_id_fkey'),
        ('battery_health_history', 'battery_health_history_battery_id_fkey'),
        ('battery_health_alerts', 'battery_health_alerts_battery_id_fkey'),
        ('battery_health_snapshots', 'battery_health_snapshots_battery_id_fkey'),
        ('battery_maintenance_schedules', 'battery_maintenance_schedules_battery_id_fkey'),
        ('batteryhealthlog', 'batteryhealthlog_battery_id_fkey'),
        ('charging_queue', 'charging_queue_battery_id_fkey'),
        ('purchases', 'purchases_battery_id_fkey'),
        ('telemetry', 'telemetry_battery_id_fkey'),
    ]
    
    for table, fk in foreign_keys_to_drop:
        op.execute(f"ALTER TABLE IF EXISTS {table} DROP CONSTRAINT IF EXISTS {fk}")

    # 2. Add station_cameras table
    op.create_table('station_cameras',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('rtsp_url', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 3. Handle Batteries table and Type Conversion
    op.add_column('batteries', sa.Column('spec_id', sa.Integer(), nullable=True))
    op.add_column('batteries', sa.Column('purchase_cost', sa.Float(), nullable=False, server_default='0.0'))
    
    # DROP PK from batteries to change type
    op.execute("ALTER TABLE batteries DROP CONSTRAINT IF EXISTS batteries_pkey")
    
    op.alter_column('batteries', 'id',
               existing_type=sa.UUID(),
               type_=sa.Integer(),
               existing_nullable=False,
               autoincrement=True,
               postgresql_using='id::text::integer')
               
    # RECREATE PK
    op.execute("ALTER TABLE batteries ADD PRIMARY KEY (id)")

    # Handle ENUMs with default value issues
    # Drop defaults first
    op.execute("ALTER TABLE batteries ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE batteries ALTER COLUMN health_status DROP DEFAULT")
    op.execute("ALTER TABLE batteries ALTER COLUMN location_type DROP DEFAULT")

    op.alter_column('batteries', 'status',
               existing_type=sa.VARCHAR(),
               type_=sa.Enum('AVAILABLE', 'RENTED', 'MAINTENANCE', 'CHARGING', 'RETIRED', name='batterystatus'),
               existing_nullable=False,
               postgresql_using="UPPER(status)::batterystatus")
               
    op.alter_column('batteries', 'health_status',
               existing_type=sa.VARCHAR(),
               type_=sa.Enum('GOOD', 'FAIR', 'POOR', 'CRITICAL', 'EXCELLENT', 'DAMAGED', name='batteryhealth'),
               existing_nullable=False,
               postgresql_using="UPPER(health_status)::batteryhealth")
               
    op.alter_column('batteries', 'notes', existing_type=sa.TEXT(), type_=sa.String(), existing_nullable=True)
    
    op.alter_column('batteries', 'location_type',
               existing_type=sa.VARCHAR(),
               type_=sa.Enum('STATION', 'WAREHOUSE', 'SERVICE_CENTER', 'RECYCLING', name='locationtype'),
               existing_nullable=False,
               postgresql_using="UPPER(location_type)::locationtype")

    # Restore defaults
    op.execute("ALTER TABLE batteries ALTER COLUMN status SET DEFAULT 'AVAILABLE'")
    op.execute("ALTER TABLE batteries ALTER COLUMN health_status SET DEFAULT 'GOOD'")
    op.execute("ALTER TABLE batteries ALTER COLUMN location_type SET DEFAULT 'WAREHOUSE'")
               
    op.create_index(op.f('ix_batteries_current_user_id'), 'batteries', ['current_user_id'], unique=False)
    op.create_index(op.f('ix_batteries_iot_device_id'), 'batteries', ['iot_device_id'], unique=False)
    op.create_index(op.f('ix_batteries_qr_code_data'), 'batteries', ['qr_code_data'], unique=True)
    op.create_index(op.f('ix_batteries_station_id'), 'batteries', ['station_id'], unique=False)
    op.create_index(op.f('ix_batteries_status'), 'batteries', ['status'], unique=False)
    op.create_foreign_key(None, 'batteries', 'battery_catalog', ['spec_id'], ['id'])

    # 4. Alter ALL dependent columns in other tables
    op.alter_column('battery_audit_logs', 'battery_id', existing_type=sa.UUID(), type_=sa.Integer(), existing_nullable=False, postgresql_using='battery_id::text::integer')
    op.alter_column('battery_health_history', 'battery_id', existing_type=sa.UUID(), type_=sa.Integer(), existing_nullable=False, postgresql_using='battery_id::text::integer')
    op.alter_column('battery_lifecycle_events', 'battery_id', existing_type=sa.UUID(), type_=sa.Integer(), existing_nullable=False, postgresql_using='battery_id::text::integer')
    op.alter_column('battery_transfers', 'battery_id', existing_type=sa.UUID(), type_=sa.Integer(), nullable=False, postgresql_using='battery_id::text::integer')
    op.alter_column('gps_tracking_log', 'battery_id', existing_type=sa.UUID(), type_=sa.Integer(), nullable=False, postgresql_using='battery_id::text::integer')
    op.alter_column('iot_devices', 'battery_id', existing_type=sa.UUID(), type_=sa.Integer(), existing_nullable=True, postgresql_using='battery_id::text::integer')
    op.alter_column('rental_events', 'battery_id', existing_type=sa.UUID(), type_=sa.Integer(), existing_nullable=True, postgresql_using='battery_id::text::integer')
    op.alter_column('rentals', 'battery_id', existing_type=sa.UUID(), type_=sa.Integer(), nullable=False, postgresql_using='battery_id::text::integer')
    op.alter_column('reviews', 'battery_id', existing_type=sa.UUID(), type_=sa.Integer(), existing_nullable=True, postgresql_using='battery_id::text::integer')
    op.alter_column('station_slots', 'battery_id', existing_type=sa.UUID(), type_=sa.Integer(), existing_nullable=True, postgresql_using='battery_id::text::integer')
    op.alter_column('swap_sessions', 'old_battery_id', existing_type=sa.UUID(), type_=sa.Integer(), existing_nullable=True, postgresql_using='old_battery_id::text::integer')
    op.alter_column('swap_sessions', 'new_battery_id', existing_type=sa.UUID(), type_=sa.Integer(), existing_nullable=True, postgresql_using='new_battery_id::text::integer')

    # 5. Recreate Indexes and Foreign Keys
    op.create_index(op.f('ix_battery_audit_logs_battery_id'), 'battery_audit_logs', ['battery_id'], unique=False)
    op.create_index(op.f('ix_battery_health_history_battery_id'), 'battery_health_history', ['battery_id'], unique=False)
    op.create_index(op.f('ix_battery_lifecycle_events_event_type'), 'battery_lifecycle_events', ['event_type'], unique=False)
    
    op.create_foreign_key('battery_health_alerts_battery_id_fkey', 'battery_health_alerts', 'batteries', ['battery_id'], ['id'])
    op.create_foreign_key('battery_health_snapshots_battery_id_fkey', 'battery_health_snapshots', 'batteries', ['battery_id'], ['id'])
    # Using existing names
    op.create_foreign_key('battery_lifecycle_events_battery_id_fkey', 'battery_lifecycle_events', 'batteries', ['battery_id'], ['id'])
    op.create_foreign_key('battery_audit_logs_battery_id_fkey', 'battery_audit_logs', 'batteries', ['battery_id'], ['id'])
    op.create_foreign_key('battery_health_history_battery_id_fkey', 'battery_health_history', 'batteries', ['battery_id'], ['id'])
    op.create_foreign_key('battery_maintenance_schedules_battery_id_fkey', 'battery_maintenance_schedules', 'batteries', ['battery_id'], ['id'])
    op.create_foreign_key('battery_transfers_battery_id_fkey', 'battery_transfers', 'batteries', ['battery_id'], ['id'])
    op.create_foreign_key('gps_tracking_log_battery_id_fkey', 'gps_tracking_log', 'batteries', ['battery_id'], ['id'])
    op.create_foreign_key('iot_devices_battery_id_fkey', 'iot_devices', 'batteries', ['battery_id'], ['id'])
    op.create_foreign_key('purchases_battery_id_fkey', 'purchases', 'batteries', ['battery_id'], ['id'])
    op.create_foreign_key('rentals_battery_id_fkey', 'rentals', 'batteries', ['battery_id'], ['id'])
    op.create_foreign_key('reviews_battery_id_fkey', 'reviews', 'batteries', ['battery_id'], ['id'])
    # Fallback to None if unsure of name
    op.create_foreign_key('station_slots_battery_id_fkey', 'station_slots', 'batteries', ['battery_id'], ['id'])
    op.create_foreign_key('swap_sessions_old_battery_id_fkey', 'swap_sessions', 'batteries', ['old_battery_id'], ['id'])
    op.create_foreign_key('swap_sessions_new_battery_id_fkey', 'swap_sessions', 'batteries', ['new_battery_id'], ['id'])
    op.create_foreign_key('telemetry_battery_id_fkey', 'telemetry', 'batteries', ['battery_id'], ['id'])

    # 6. Audit logs fields
    op.add_column('audit_logs', sa.Column('trace_id', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('session_id', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('action_id', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('role_prefix', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('level', sa.String(), nullable=False, server_default='INFO'))
    op.add_column('audit_logs', sa.Column('module', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('status', sa.String(), nullable=False, server_default='success'))
    op.add_column('audit_logs', sa.Column('request_method', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('endpoint', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('response_time_ms', sa.Float(), nullable=True))
    op.add_column('audit_logs', sa.Column('stack_trace', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('is_suspicious', sa.Boolean(), nullable=False, server_default='false'))
    
    op.alter_column('audit_logs', 'resource_type', existing_type=sa.VARCHAR(), nullable=True)
    op.alter_column('audit_logs', 'timestamp', existing_type=postgresql.TIMESTAMP(), type_=sa.DateTime(timezone=True), nullable=True)
    
    op.create_index(op.f('ix_audit_logs_action_id'), 'audit_logs', ['action_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_is_suspicious'), 'audit_logs', ['is_suspicious'], unique=False)
    op.create_index(op.f('ix_audit_logs_module'), 'audit_logs', ['module'], unique=False)
    op.create_index(op.f('ix_audit_logs_session_id'), 'audit_logs', ['session_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_status'), 'audit_logs', ['status'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)
    op.create_index('ix_audit_logs_timestamp_desc', 'audit_logs', ['timestamp'], unique=False, postgresql_using='btree', postgresql_ops={'timestamp': 'DESC'})
    op.create_index(op.f('ix_audit_logs_trace_id'), 'audit_logs', ['trace_id'], unique=False)

    # 7. Final drift items
    op.create_index(op.f('ix_stations_rating'), 'stations', ['rating'], unique=False)
    op.alter_column('test_reports', 'created_at', existing_type=postgresql.TIMESTAMP(timezone=True), type_=sa.DateTime(), existing_nullable=True)
    op.drop_index('ix_test_reports_id', table_name='test_reports')
    
    for col in ['two_factor_secret', 'email_verification_sent_at', 'last_login_at', 'email_verification_token', 'backup_codes', 'is_email_verified']:
        op.drop_column('users', col)

def downgrade() -> None:
    op.drop_table('station_cameras')
    pass
