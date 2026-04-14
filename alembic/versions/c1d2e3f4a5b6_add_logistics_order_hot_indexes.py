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


revision = "c1d2e3f4a5b6"
down_revision = "perf_indexes_ph11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_logistics_orders_status",
        "logistics_orders",
        ["status"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_logistics_orders_priority",
        "logistics_orders",
        ["priority"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_logistics_orders_order_date",
        "logistics_orders",
        ["order_date"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_logistics_orders_assigned_driver_id",
        "logistics_orders",
        ["assigned_driver_id"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_logistics_orders_assigned_driver_id", table_name="logistics_orders")
    op.drop_index("ix_logistics_orders_order_date", table_name="logistics_orders")
    op.drop_index("ix_logistics_orders_priority", table_name="logistics_orders")
    op.drop_index("ix_logistics_orders_status", table_name="logistics_orders")
