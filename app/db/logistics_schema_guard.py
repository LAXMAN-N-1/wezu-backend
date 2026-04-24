from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Sequence, Set, Tuple

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.db.session import engine as default_engine

logger = logging.getLogger(__name__)

REQUIRED_LOGISTICS_SCHEMA: Dict[str, Set[str]] = {
    "batteries": {
        "id",
        "serial_number",
        "status",
        "location_type",
        "location_id",
        "updated_at",
        "created_at",
        "current_charge",
        "health_percentage",
        "cycle_count",
        "qr_code_data",
    },
    "battery_lifecycle_events": {"id", "battery_id", "event_type", "description", "timestamp"},
    "driver_profiles": {
        "id",
        "user_id",
        "status",
        "is_online",
        "name",
        "phone_number",
        "vehicle_type",
        "vehicle_plate",
        "license_number",
        "current_latitude",
        "current_longitude",
        "current_battery_level",
        "location_accuracy",
        "last_location_update",
        "rating",
        "total_deliveries",
    },
    "logistics_orders": {
        "id",
        "status",
        "priority",
        "units",
        "destination",
        "customer_name",
        "customer_phone",
        "total_value",
        "tracking_number",
        "assigned_battery_ids",
        "assigned_driver_id",
        "order_date",
        "estimated_delivery",
        "dispatch_date",
        "delivered_at",
        "updated_at",
        "proof_of_delivery_url",
        "proof_of_delivery_notes",
        "proof_of_delivery_captured_at",
        "proof_of_delivery_signature_url",
        "recipient_name",
        "failure_reason",
        "scheduled_slot_start",
        "scheduled_slot_end",
        "is_confirmed",
        "confirmation_sent_at",
        "type",
        "original_order_id",
        "refund_status",
    },
    "logistics_order_batteries": {
        "id",
        "order_id",
        "battery_id",
        "created_at",
    },
    "inventory_transfers": {
        "id",
        "from_location_type",
        "from_location_id",
        "to_location_type",
        "to_location_id",
        "driver_id",
        "items",
        "status",
        "created_at",
        "updated_at",
        "completed_at",
    },
    "inventory_transfer_items": {
        "id",
        "transfer_id",
        "battery_id",
        "created_at",
    },
    "stock_discrepancies": {
        "id",
        "location_type",
        "location_id",
        "system_count",
        "physical_count",
        "missing_items",
        "extra_items",
        "notes",
        "status",
        "reported_by_id",
        "created_at",
    },
    "manifests": {"id", "source", "date", "status", "created_at"},
    "manifest_items": {
        "id",
        "manifest_id",
        "battery_id",
        "battery_table_id",
        "type",
        "status",
    },
    "warehouses": {"id", "name", "code", "is_active"},
    "warehouse_racks": {"id", "warehouse_id", "name"},
    "warehouse_shelves": {"id", "rack_id", "name", "capacity"},
    "shelf_batteries": {"id", "shelf_id", "battery_id"},
    "idempotency_keys": {
        "id",
        "user_id",
        "idempotency_key",
        "request_method",
        "request_path",
        "request_fingerprint",
        "response_status_code",
        "response_payload",
        "created_at",
        "expires_at",
    },
    "stations": {
        "id",
        "name",
        "status",
        "latitude",
        "longitude",
        "is_deleted",
        "deleted_at",
        "updated_at",
    },
    "station_daily_metrics": {
        "id",
        "station_id",
        "metric_date",
        "rentals_started",
        "rentals_completed",
        "average_duration_minutes",
        "refreshed_at",
    },
    "settlements": {
        "id",
        "vendor_id",
        "dealer_id",
        "status",
        "created_at",
    },
}

REQUIRED_LOGISTICS_FOREIGN_KEYS: Dict[str, Sequence[Tuple[str, str, str]]] = {
    "logistics_orders": (
        ("assigned_driver_id", "driver_profiles", "id"),
    ),
    "inventory_transfers": (
        ("driver_id", "driver_profiles", "id"),
    ),
    "station_daily_metrics": (
        ("station_id", "stations", "id"),
    ),
    "settlements": (
        ("dealer_id", "users", "id"),
    ),
}


def _collect_foreign_key_issues(inspector, *, existing_tables: Set[str]) -> List[str]:
    issues: List[str] = []

    for table_name, expected_foreign_keys in REQUIRED_LOGISTICS_FOREIGN_KEYS.items():
        if table_name not in existing_tables:
            continue
        existing_foreign_keys = inspector.get_foreign_keys(table_name, schema=None)
        for local_column, referred_table, referred_column in expected_foreign_keys:
            matching = [
                fk
                for fk in existing_foreign_keys
                if (fk.get("constrained_columns") or []) == [local_column]
            ]
            if not matching:
                issues.append(
                    f"Missing foreign key in '{table_name}': {local_column} -> {referred_table}.{referred_column}"
                )
                continue

            if not any(
                fk.get("referred_table") == referred_table
                and (fk.get("referred_columns") or []) == [referred_column]
                for fk in matching
            ):
                observed_targets = ", ".join(
                    f"{fk.get('referred_table')}.{','.join(fk.get('referred_columns') or [])}"
                    for fk in matching
                )
                issues.append(
                    f"Foreign key mismatch in '{table_name}.{local_column}': expected {referred_table}.{referred_column}, found {observed_targets}"
                )
    return issues


def _get_app_schema(connection) -> str:
    """Return the schema where app tables actually live.

    Neon (and some other hosted PGs) set current_schema() to 'public' even
    when the application tables are in a different schema (e.g. 'core').
    We detect the real schema by looking for a well-known table name.
    Falls back to 'public' if nothing is found.
    """
    result = connection.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'batteries' "
            "  AND table_schema NOT IN ('information_schema', 'pg_catalog') "
            "LIMIT 1"
        )
    )
    row = result.fetchone()
    return row[0] if row else "public"


def _table_exists_sql(connection, table_name: str, schema: str) -> bool:
    result = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :s AND table_name = :t LIMIT 1"
        ),
        {"s": schema, "t": table_name},
    )
    return result.fetchone() is not None


def _get_columns_sql(connection, table_name: str, schema: str) -> Set[str]:
    result = connection.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = :t"
        ),
        {"s": schema, "t": table_name},
    )
    return {row[0] for row in result}


def collect_logistics_schema_issues(schema_requirements: Dict[str, Set[str]], engine: Engine) -> List[str]:
    issues: List[str] = []

    with engine.connect() as connection:
        schema = _get_app_schema(connection)
        for table_name, required_columns in schema_requirements.items():
            if not _table_exists_sql(connection, table_name, schema):
                issues.append(f"Missing table: {table_name}")
                continue

            existing_columns = _get_columns_sql(connection, table_name, schema)
            missing_columns = sorted(required_columns - existing_columns)
            if missing_columns:
                issues.append(
                    f"Missing columns in '{table_name}': {', '.join(missing_columns)}"
                )

    return issues


def format_logistics_schema_issues(issues: Iterable[str]) -> str:
    formatted = ["Logistics schema validation failed:"]
    formatted.extend(f"- {issue}" for issue in issues)
    formatted.append("Run alembic migrations to align DB schema with logistics models.")
    return "\n".join(formatted)


def validate_logistics_schema(*, strict: bool = False, engine: Engine = default_engine) -> List[str]:
    issues = collect_logistics_schema_issues(REQUIRED_LOGISTICS_SCHEMA, engine)
    if not issues:
        logger.info("Logistics schema validation passed")
        return []

    message = format_logistics_schema_issues(issues)
    if strict:
        raise RuntimeError(message)

    logger.error(message)
    return issues
