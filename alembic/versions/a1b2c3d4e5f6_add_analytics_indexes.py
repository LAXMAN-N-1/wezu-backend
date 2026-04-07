"""Add analytics-specific indexes for dashboard query performance.

These indexes cover the hottest columns in the admin analytics service:
- transactions.rental_id      (JOIN in every revenue-by-station query)
- transactions.created_at     (time-range filters in all analytics queries)
- transactions (status, created_at) composite (revenue aggregations)
- station_slots.station_id    (top-stations slot status aggregation)
- support_tickets.status      (open-ticket count in platform overview)
- battery_health_snapshots (battery_id, recorded_at) composite (health trends)

Revision ID: a1b2c3d4e5f6
Revises: ef440e24c619
Create Date: 2025-01-02 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "ef440e24c619"
branch_labels = None
depends_on = None


def _safe_create_index(index_name: str, table: str, columns: list[str], **kw):
    """Create an index only if it doesn't already exist.

    Uses a SAVEPOINT so that a failure (e.g. index/table already exists)
    doesn't abort the outer PostgreSQL transaction.
    """
    bind = op.get_bind()
    try:
        with bind.begin_nested():  # SAVEPOINT
            op.create_index(index_name, table, columns, **kw)
    except Exception:
        pass  # index or table doesn't exist — skip silently


def upgrade() -> None:
    # Transaction table — every analytics revenue query JOINs on rental_id
    # and filters on status + created_at
    _safe_create_index("ix_transactions_rental_id", "transactions", ["rental_id"])
    _safe_create_index("ix_transactions_created_at", "transactions", ["created_at"])
    _safe_create_index(
        "ix_transactions_status_created_at",
        "transactions",
        ["status", "created_at"],
    )

    # Station slots — top-stations GROUP BY station_id
    _safe_create_index("ix_station_slots_station_id", "station_slots", ["station_id"])

    # Support tickets — open-ticket count in platform overview
    _safe_create_index("ix_support_tickets_status", "support_tickets", ["status"])

    # Battery health snapshots — trends + distribution queries
    _safe_create_index(
        "ix_battery_health_snapshots_battery_recorded",
        "battery_health_snapshots",
        ["battery_id", "recorded_at"],
    )

    # KYC records — conversion funnel counts verified KYC
    _safe_create_index("ix_kyc_records_status", "kyc_records", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    for idx in [
        "ix_kyc_records_status",
        "ix_battery_health_snapshots_battery_recorded",
        "ix_support_tickets_status",
        "ix_station_slots_station_id",
        "ix_transactions_status_created_at",
        "ix_transactions_created_at",
        "ix_transactions_rental_id",
    ]:
        try:
            with bind.begin_nested():
                op.drop_index(idx)
        except Exception:
            pass
