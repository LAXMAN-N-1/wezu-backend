"""unified_new_tables

Creates all new tables introduced by the unified backend that do not exist
in the previous local backend schema:
  - logistics_orders + logistics_order_batteries
  - order_realtime_outbox
  - inventory_transfers + inventory_transfer_items + stock_discrepancies
  - manifests + manifest_items
  - idempotency_keys
  - notification_outbox
  - passkey_credentials + passkey_challenges
  - payment_methods
  - station_daily_metrics
  - telemetics_data (unified telematics model)
  - dealer_stock_requests
  - analytics_activity_events + analytics_report_jobs
  - maintenance_checklists + maintenance_checklist_items
  - kyc_verifications

Revision ID: f1e2d3c4b5a6
Revises: c1d2e3f4a5b6
Create Date: 2026-04-14
"""
from typing import Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    def table_exists(name: str) -> bool:
        return conn.dialect.has_table(conn, name)

    def col_exists(table: str, col: str) -> bool:
        result = conn.execute(sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name=:t AND column_name=:c"
        ), {"t": table, "c": col})
        return result.fetchone() is not None

    # ── logistics_orders ──────────────────────────────────────────────────
    if not table_exists("logistics_orders"):
        op.create_table(
            "logistics_orders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("order_number", sa.String(), nullable=False, unique=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("priority", sa.String(), nullable=False, server_default="normal"),
            sa.Column("source_warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=True),
            sa.Column("destination_warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=True),
            sa.Column("destination_station_id", sa.Integer(), sa.ForeignKey("stations.id"), nullable=True),
            sa.Column("assigned_driver_id", sa.Integer(), sa.ForeignKey("driver_profiles.id"), nullable=True),
            sa.Column("idempotency_key", sa.String(), nullable=True, unique=True),
            sa.Column("proof_of_delivery_url", sa.String(), nullable=True),
            sa.Column("failure_reason", sa.String(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("estimated_delivery", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("order_date", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        )
        op.create_index("ix_logistics_orders_status", "logistics_orders", ["status"])
        op.create_index("ix_logistics_orders_assigned_driver_id", "logistics_orders", ["assigned_driver_id"])

    # ── logistics_order_batteries ─────────────────────────────────────────
    if not table_exists("logistics_order_batteries"):
        op.create_table(
            "logistics_order_batteries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("logistics_orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("battery_id", sa.Integer(), sa.ForeignKey("batteries.id"), nullable=False),
            sa.Column("serial_number", sa.String(), nullable=True),
            sa.Column("pre_transfer_status", sa.String(), nullable=True),
            sa.Column("post_transfer_status", sa.String(), nullable=True),
        )
        op.create_index("ix_order_batteries_order_id", "logistics_order_batteries", ["order_id"])

    # ── order_realtime_outbox ─────────────────────────────────────────────
    if not table_exists("order_realtime_outbox"):
        op.create_table(
            "order_realtime_outbox",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("order_id", sa.Integer(), nullable=False, index=True),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column("published", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ── inventory_transfers ───────────────────────────────────────────────
    if not table_exists("inventory_transfers"):
        op.create_table(
            "inventory_transfers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("transfer_number", sa.String(), nullable=False, unique=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("from_warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=True),
            sa.Column("to_warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=True),
            sa.Column("from_station_id", sa.Integer(), sa.ForeignKey("stations.id"), nullable=True),
            sa.Column("to_station_id", sa.Integer(), sa.ForeignKey("stations.id"), nullable=True),
            sa.Column("initiated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
        )

    if not table_exists("inventory_transfer_items"):
        op.create_table(
            "inventory_transfer_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("transfer_id", sa.Integer(), sa.ForeignKey("inventory_transfers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("battery_id", sa.Integer(), sa.ForeignKey("batteries.id"), nullable=False),
            sa.Column("serial_number", sa.String(), nullable=True),
        )

    if not table_exists("stock_discrepancies"):
        op.create_table(
            "stock_discrepancies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=True),
            sa.Column("battery_id", sa.Integer(), sa.ForeignKey("batteries.id"), nullable=True),
            sa.Column("expected_location", sa.String(), nullable=True),
            sa.Column("actual_location", sa.String(), nullable=True),
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ── manifests ─────────────────────────────────────────────────────────
    if not table_exists("manifests"):
        op.create_table(
            "manifests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("manifest_number", sa.String(), nullable=False, unique=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("logistics_orders.id"), nullable=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=True),
            sa.Column("driver_id", sa.Integer(), sa.ForeignKey("driver_profiles.id"), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not table_exists("manifest_items"):
        op.create_table(
            "manifest_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("manifest_id", sa.Integer(), sa.ForeignKey("manifests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("battery_id", sa.Integer(), sa.ForeignKey("batteries.id"), nullable=True),
            sa.Column("serial_number", sa.String(), nullable=True),
            sa.Column("condition", sa.String(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
        )

    # ── idempotency_keys ──────────────────────────────────────────────────
    if not table_exists("idempotency_keys"):
        op.create_table(
            "idempotency_keys",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("key", sa.String(128), nullable=False, unique=True, index=True),
            sa.Column("request_fingerprint", sa.String(), nullable=True),
            sa.Column("response_status", sa.Integer(), nullable=True),
            sa.Column("response_body", postgresql.JSONB(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ── notification_outbox ───────────────────────────────────────────────
    if not table_exists("notification_outbox"):
        op.create_table(
            "notification_outbox",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("body", sa.String(), nullable=False),
            sa.Column("data", postgresql.JSONB(), nullable=True),
            sa.Column("channel", sa.String(), nullable=False, server_default="fcm"),
            sa.Column("sent", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("failed", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ── passkey_credentials + passkey_challenges ──────────────────────────
    if not table_exists("passkey_credentials"):
        op.create_table(
            "passkey_credentials",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("credential_id", sa.String(), nullable=False, unique=True),
            sa.Column("public_key", sa.Text(), nullable=False),
            sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("device_type", sa.String(), nullable=True),
            sa.Column("aaguid", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not table_exists("passkey_challenges"):
        op.create_table(
            "passkey_challenges",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("challenge", sa.String(), nullable=False, unique=True),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
        )

    # ── payment_methods ───────────────────────────────────────────────────
    if not table_exists("payment_methods"):
        op.create_table(
            "payment_methods",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("provider", sa.String(), nullable=True),
            sa.Column("last4", sa.String(4), nullable=True),
            sa.Column("display_name", sa.String(), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("metadata", postgresql.JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ── station_daily_metrics ─────────────────────────────────────────────
    if not table_exists("station_daily_metrics"):
        op.create_table(
            "station_daily_metrics",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id"), nullable=False, index=True),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("swaps_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rentals_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("revenue", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("avg_battery_health", sa.Float(), nullable=True),
            sa.Column("uptime_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
        )
        op.create_index("ix_station_daily_metrics_station_date",
                        "station_daily_metrics", ["station_id", "date"], unique=True)

    # ── telemetics_data (unified telematics model) ────────────────────────
    if not table_exists("telemetics_data"):
        op.create_table(
            "telemetics_data",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("battery_id", sa.Integer(), sa.ForeignKey("batteries.id"), nullable=False, index=True),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("voltage", sa.Float(), nullable=True),
            sa.Column("current", sa.Float(), nullable=True),
            sa.Column("temperature", sa.Float(), nullable=True),
            sa.Column("soc", sa.Float(), nullable=True),
            sa.Column("latitude", sa.Float(), nullable=True),
            sa.Column("longitude", sa.Float(), nullable=True),
            sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        )

    # ── dealer_stock_requests ─────────────────────────────────────────────
    if not table_exists("dealer_stock_requests"):
        op.create_table(
            "dealer_stock_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("dealer_id", sa.Integer(), sa.ForeignKey("dealer_profiles.id"), nullable=False, index=True),
            sa.Column("model_id", sa.Integer(), sa.ForeignKey("battery_catalog.id"), nullable=True),
            sa.Column("model_name", sa.String(), nullable=True),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("delivery_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("priority", sa.String(), nullable=False, server_default="normal"),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending", index=True),
            sa.Column("admin_notes", sa.Text(), nullable=True),
            sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejected_reason", sa.Text(), nullable=True),
            sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("fulfilled_quantity", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
        )

    # ── analytics_activity_events + analytics_report_jobs ────────────────
    if not table_exists("analytics_activity_events"):
        op.create_table(
            "analytics_activity_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
            sa.Column("event_type", sa.String(), nullable=False, index=True),
            sa.Column("entity_type", sa.String(), nullable=True),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
        )

    if not table_exists("analytics_report_jobs"):
        op.create_table(
            "analytics_report_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("report_type", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("parameters", postgresql.JSONB(), nullable=True),
            sa.Column("result_url", sa.String(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ── maintenance_checklists ────────────────────────────────────────────
    if not table_exists("maintenance_checklists"):
        op.create_table(
            "maintenance_checklists",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id"), nullable=True),
            sa.Column("battery_id", sa.Integer(), sa.ForeignKey("batteries.id"), nullable=True),
            sa.Column("assigned_to", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
        )

    if not table_exists("maintenance_checklist_items"):
        op.create_table(
            "maintenance_checklist_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("checklist_id", sa.Integer(), sa.ForeignKey("maintenance_checklists.id", ondelete="CASCADE"), nullable=False),
            sa.Column("description", sa.String(), nullable=False),
            sa.Column("is_completed", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
        )

    # ── kyc_verifications ─────────────────────────────────────────────────
    if not table_exists("kyc_verifications"):
        op.create_table(
            "kyc_verifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("document_type", sa.String(), nullable=False),
            sa.Column("document_number", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ── dealer_profiles additive columns ──────────────────────────────────
    if not col_exists("dealer_profiles", "global_rental_settings"):
        op.add_column(
            "dealer_profiles",
            sa.Column("global_rental_settings", postgresql.JSONB(), nullable=True),
        )


def downgrade() -> None:
    # Drop in reverse dependency order
    for tbl in [
        "kyc_verifications", "maintenance_checklist_items", "maintenance_checklists",
        "analytics_report_jobs", "analytics_activity_events", "dealer_stock_requests",
        "telemetics_data", "station_daily_metrics", "payment_methods",
        "passkey_challenges", "passkey_credentials", "notification_outbox",
        "idempotency_keys", "manifest_items", "manifests",
        "stock_discrepancies", "inventory_transfer_items", "inventory_transfers",
        "order_realtime_outbox", "logistics_order_batteries", "logistics_orders",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
    op.execute("ALTER TABLE dealer_profiles DROP COLUMN IF EXISTS global_rental_settings")
