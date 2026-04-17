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

    # 2. Add POOR to BatteryHealth Enum
    op.execute("ALTER TYPE batteryhealth ADD VALUE IF NOT EXISTS 'POOR'")

    # 3. Add columns to batteries table (Idempotent)
    op.execute("ALTER TABLE batteries ADD COLUMN IF NOT EXISTS manufacturer VARCHAR;")
    op.execute("ALTER TABLE batteries ADD COLUMN IF NOT EXISTS notes VARCHAR;")
    
    # Enum column with server default
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='batteries' AND column_name='location_type') THEN
                ALTER TABLE batteries ADD COLUMN location_type locationtype NOT NULL DEFAULT 'warehouse';
            END IF;
        END
        $$;
    """)
    
    op.execute("ALTER TABLE batteries ADD COLUMN IF NOT EXISTS manufacture_date TIMESTAMP WITHOUT TIME ZONE;")
    op.execute("ALTER TABLE batteries ADD COLUMN IF NOT EXISTS last_charged_at TIMESTAMP WITHOUT TIME ZONE;")

    # 4. Create BatteryAuditLog table if not exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS battery_audit_logs (
            id SERIAL PRIMARY KEY,
            battery_id INTEGER NOT NULL REFERENCES batteries(id),
            changed_by INTEGER REFERENCES users(id),
            field_changed VARCHAR NOT NULL,
            old_value VARCHAR,
            new_value VARCHAR,
            reason VARCHAR,
            timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL
        );
    """)
    # Index creation if not exists
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_battery_audit_logs_battery_id ON battery_audit_logs (battery_id);")

    # 5. Create BatteryHealthHistory table if not exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS battery_health_history (
            id SERIAL PRIMARY KEY,
            battery_id INTEGER NOT NULL REFERENCES batteries(id),
            health_percentage FLOAT NOT NULL,
            recorded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_battery_health_history_battery_id ON battery_health_history (battery_id);")


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

