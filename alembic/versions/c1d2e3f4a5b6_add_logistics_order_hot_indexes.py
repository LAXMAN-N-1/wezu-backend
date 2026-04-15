"""Add logistics_orders hot-filter indexes

Adds indexes on columns that are filtered/sorted in the orders list
endpoints (app/api/v1/orders.py) but were not previously indexed:
  - logistics_orders.status
  - logistics_orders.priority
  - logistics_orders.order_date  (used for ORDER BY DESC + LIMIT)
  - logistics_orders.assigned_driver_id  (FK, per-driver queries)

Revision ID: c1d2e3f4a5b6
Revises: perf_indexes_ph11
"""
from alembic import op
from sqlalchemy import inspect


revision = "c1d2e3f4a5b6"
down_revision = "perf_indexes_ph11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("logistics_orders"):
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("logistics_orders")
    }
    candidates = [
        ("ix_logistics_orders_status", "status"),
        ("ix_logistics_orders_priority", "priority"),
        ("ix_logistics_orders_order_date", "order_date"),
        ("ix_logistics_orders_assigned_driver_id", "assigned_driver_id"),
    ]
    for index_name, column_name in candidates:
        if column_name not in existing_columns:
            continue
        op.create_index(
            index_name,
            "logistics_orders",
            [column_name],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("logistics_orders"):
        return

    existing_indexes = {
        index["name"] for index in inspector.get_indexes("logistics_orders")
    }
    for index_name in (
        "ix_logistics_orders_assigned_driver_id",
        "ix_logistics_orders_order_date",
        "ix_logistics_orders_priority",
        "ix_logistics_orders_status",
    ):
        if index_name not in existing_indexes:
            continue
        op.drop_index(index_name, table_name="logistics_orders")
