"""Reconcile logistics schema on drifted DBs.

Revision ID: e2f4c6a8b9d0
Revises: c1a2b3d4e5f7
Create Date: 2026-04-21 18:55:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e2f4c6a8b9d0"
down_revision: Union[str, None] = "c1a2b3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _battery_id_sql_type(bind) -> str:
    row = bind.execute(
        sa.text(
            """
            SELECT data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'batteries'
              AND column_name = 'id'
              AND table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY CASE WHEN table_schema = 'public' THEN 0 ELSE 1 END
            LIMIT 1
            """
        )
    ).fetchone()

    if not row:
        return "TEXT"

    data_type = str(row[0] or "").lower()
    udt_name = str(row[1] or "").lower()
    if data_type == "uuid" or udt_name == "uuid":
        return "UUID"
    if data_type in {"integer", "smallint", "bigint"}:
        return "INTEGER"
    return "TEXT"


def _create_tables(bind) -> None:
    battery_id_type = _battery_id_sql_type(bind)

    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS driver_profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            name VARCHAR,
            phone_number VARCHAR,
            status VARCHAR DEFAULT 'active',
            license_number VARCHAR NOT NULL,
            vehicle_type VARCHAR NOT NULL,
            vehicle_plate VARCHAR NOT NULL,
            is_online BOOLEAN NOT NULL DEFAULT FALSE,
            current_latitude DOUBLE PRECISION,
            current_longitude DOUBLE PRECISION,
            current_battery_level DOUBLE PRECISION,
            location_accuracy DOUBLE PRECISION,
            last_location_update TIMESTAMP,
            rating DOUBLE PRECISION NOT NULL DEFAULT 5.0,
            total_deliveries INTEGER NOT NULL DEFAULT 0,
            on_time_deliveries INTEGER NOT NULL DEFAULT 0,
            total_delivery_time_seconds INTEGER NOT NULL DEFAULT 0,
            satisfaction_sum DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS logistics_orders (
            id VARCHAR PRIMARY KEY,
            status VARCHAR NOT NULL DEFAULT 'pending',
            priority VARCHAR NOT NULL DEFAULT 'normal',
            units INTEGER NOT NULL DEFAULT 1,
            destination VARCHAR NOT NULL,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            notes TEXT,
            customer_name VARCHAR NOT NULL DEFAULT 'Walk-in Customer',
            customer_phone VARCHAR,
            total_value NUMERIC(12,2) NOT NULL DEFAULT 0,
            tracking_number VARCHAR,
            assigned_battery_ids TEXT,
            assigned_driver_id INTEGER,
            order_date TIMESTAMP NOT NULL DEFAULT NOW(),
            estimated_delivery TIMESTAMP,
            dispatch_date TIMESTAMP,
            delivered_at TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            proof_of_delivery_url VARCHAR,
            proof_of_delivery_notes TEXT,
            proof_of_delivery_captured_at TIMESTAMP,
            proof_of_delivery_signature_url VARCHAR,
            recipient_name VARCHAR,
            failure_reason TEXT,
            scheduled_slot_start TIMESTAMP,
            scheduled_slot_end TIMESTAMP,
            is_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
            confirmation_sent_at TIMESTAMP,
            type VARCHAR NOT NULL DEFAULT 'delivery',
            original_order_id VARCHAR,
            refund_status VARCHAR NOT NULL DEFAULT 'none'
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS logistics_order_batteries (
            id SERIAL PRIMARY KEY,
            order_id VARCHAR NOT NULL,
            battery_id VARCHAR NOT NULL,
            battery_pk {battery_id_type},
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_logistics_order_battery UNIQUE (order_id, battery_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory_transfers (
            id SERIAL PRIMARY KEY,
            from_location_type VARCHAR NOT NULL DEFAULT 'warehouse',
            from_location_id INTEGER NOT NULL,
            to_location_type VARCHAR NOT NULL DEFAULT 'station',
            to_location_id INTEGER NOT NULL,
            driver_id INTEGER,
            items TEXT NOT NULL DEFAULT '[]',
            status VARCHAR NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS inventory_transfer_items (
            id SERIAL PRIMARY KEY,
            transfer_id INTEGER NOT NULL,
            battery_id VARCHAR NOT NULL,
            battery_pk {battery_id_type},
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_inventory_transfer_item UNIQUE (transfer_id, battery_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS stock_discrepancies (
            id SERIAL PRIMARY KEY,
            location_type VARCHAR NOT NULL,
            location_id INTEGER NOT NULL,
            system_count INTEGER NOT NULL,
            physical_count INTEGER NOT NULL,
            missing_items TEXT,
            extra_items TEXT,
            notes TEXT,
            status VARCHAR NOT NULL DEFAULT 'open',
            reported_by_id INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS manifests (
            id VARCHAR PRIMARY KEY,
            source VARCHAR NOT NULL,
            date TIMESTAMP NOT NULL DEFAULT NOW(),
            status VARCHAR NOT NULL DEFAULT 'In Transit',
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS manifest_items (
            id SERIAL PRIMARY KEY,
            manifest_id VARCHAR NOT NULL,
            battery_id VARCHAR NOT NULL,
            battery_table_id {battery_id_type},
            serial_number VARCHAR,
            type VARCHAR NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'pending',
            CONSTRAINT uq_manifest_items_manifest_battery UNIQUE (manifest_id, battery_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS warehouses (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            code VARCHAR NOT NULL,
            address TEXT NOT NULL DEFAULT '',
            city VARCHAR NOT NULL DEFAULT '',
            state VARCHAR NOT NULL DEFAULT '',
            pincode VARCHAR NOT NULL DEFAULT '',
            branch_id INTEGER,
            manager_id INTEGER,
            capacity INTEGER NOT NULL DEFAULT 100,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS warehouse_racks (
            id SERIAL PRIMARY KEY,
            warehouse_id INTEGER NOT NULL,
            name VARCHAR NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS warehouse_shelves (
            id SERIAL PRIMARY KEY,
            rack_id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            capacity INTEGER NOT NULL DEFAULT 50
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS shelf_batteries (
            id SERIAL PRIMARY KEY,
            shelf_id INTEGER NOT NULL,
            battery_id VARCHAR NOT NULL UNIQUE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS idempotency_keys (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            idempotency_key VARCHAR NOT NULL,
            request_method VARCHAR NOT NULL,
            request_path VARCHAR NOT NULL,
            request_fingerprint TEXT NOT NULL,
            response_status_code INTEGER NOT NULL,
            response_payload TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMP NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS station_daily_metrics (
            id SERIAL PRIMARY KEY,
            station_id INTEGER NOT NULL,
            metric_date DATE NOT NULL,
            rentals_started INTEGER NOT NULL DEFAULT 0,
            rentals_completed INTEGER NOT NULL DEFAULT 0,
            average_duration_minutes DOUBLE PRECISION,
            refreshed_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_station_daily_metrics_station_date UNIQUE (station_id, metric_date)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS settlements (
            id SERIAL PRIMARY KEY,
            vendor_id INTEGER,
            dealer_id INTEGER,
            settlement_month VARCHAR NOT NULL DEFAULT '',
            start_date TIMESTAMP NOT NULL DEFAULT NOW(),
            end_date TIMESTAMP NOT NULL DEFAULT NOW(),
            due_date TIMESTAMP,
            total_revenue DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            total_commission DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            chargeback_amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            platform_fee DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            tax_amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            net_payable DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            currency VARCHAR NOT NULL DEFAULT 'INR',
            status VARCHAR NOT NULL DEFAULT 'pending',
            failure_reason TEXT,
            transaction_reference VARCHAR,
            payment_proof_url VARCHAR,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            paid_at TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS order_realtime_outbox (
            id SERIAL PRIMARY KEY,
            order_id VARCHAR NOT NULL,
            event_type VARCHAR NOT NULL,
            payload TEXT NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 10,
            last_error TEXT,
            idempotency_key VARCHAR,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            next_attempt_at TIMESTAMP,
            published_at TIMESTAMP
        )
        """,
    ]

    for ddl in ddl_statements:
        bind.execute(sa.text(ddl))


def _create_indexes(bind) -> None:
    index_statements = [
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_warehouses_code ON warehouses (code)",
        "CREATE INDEX IF NOT EXISTS ix_warehouses_name ON warehouses (name)",
        "CREATE INDEX IF NOT EXISTS ix_driver_profiles_user_id ON driver_profiles (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_logistics_orders_status ON logistics_orders (status)",
        "CREATE INDEX IF NOT EXISTS ix_logistics_orders_priority ON logistics_orders (priority)",
        "CREATE INDEX IF NOT EXISTS ix_logistics_orders_assigned_driver_id ON logistics_orders (assigned_driver_id)",
        "CREATE INDEX IF NOT EXISTS ix_inventory_transfers_from_location_id ON inventory_transfers (from_location_id)",
        "CREATE INDEX IF NOT EXISTS ix_inventory_transfers_to_location_id ON inventory_transfers (to_location_id)",
        "CREATE INDEX IF NOT EXISTS ix_station_daily_metrics_station_id ON station_daily_metrics (station_id)",
        "CREATE INDEX IF NOT EXISTS ix_order_realtime_outbox_status ON order_realtime_outbox (status)",
        "CREATE INDEX IF NOT EXISTS ix_order_realtime_outbox_created_at ON order_realtime_outbox (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_order_realtime_outbox_next_attempt_at ON order_realtime_outbox (next_attempt_at)",
        "CREATE INDEX IF NOT EXISTS ix_idempotency_keys_user_id ON idempotency_keys (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_idempotency_keys_idempotency_key ON idempotency_keys (idempotency_key)",
    ]
    for ddl in index_statements:
        bind.execute(sa.text(ddl))


def _ensure_station_soft_delete_columns(bind) -> None:
    inspector = sa.inspect(bind)
    if not inspector.has_table("stations"):
        return

    station_columns = {column["name"] for column in inspector.get_columns("stations")}
    if "is_deleted" not in station_columns:
        op.add_column(
            "stations",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if "deleted_at" not in station_columns:
        op.add_column("stations", sa.Column("deleted_at", sa.DateTime(), nullable=True))


def upgrade() -> None:
    bind = op.get_bind()
    _create_tables(bind)
    _create_indexes(bind)
    _ensure_station_soft_delete_columns(bind)


def downgrade() -> None:
    # No-op by design. This repair migration should never drop production data.
    pass

