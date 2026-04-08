"""Add latency-focused indexes for admin health and analytics APIs.

Targets slow endpoints seen in production logs:
- /api/v1/admin/health/batteries
- /api/v1/admin/analytics/*
- /api/v1/auth/admin/login (indirectly via user growth/user timeline scans)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-08 14:25:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def _safe_create_index(index_name: str, table: str, columns: list[str]) -> None:
    """Create index if missing without aborting the transaction."""
    bind = op.get_bind()
    try:
        with bind.begin_nested():
            op.create_index(index_name, table, columns)
    except Exception:
        # Index/table already exists or unsupported in current env.
        pass


def upgrade() -> None:
    # Rentals: heavy time-range filters and station+period aggregations.
    _safe_create_index("ix_rentals_start_time", "rentals", ["start_time"])
    _safe_create_index("ix_rentals_start_station_start_time", "rentals", ["start_station_id", "start_time"])
    _safe_create_index("ix_rentals_status_start_time", "rentals", ["status", "start_time"])

    # Users: growth/trend endpoints aggregate over created_at periods.
    _safe_create_index("ix_users_created_at", "users", ["created_at"])

    # Batteries: health list sorts/filters by health percentage.
    _safe_create_index("ix_batteries_health_percentage", "batteries", ["health_percentage"])

    # Maintenance snapshots: latest completed maintenance by battery.
    _safe_create_index(
        "ix_battery_maintenance_battery_status_completed",
        "battery_maintenance_schedules",
        ["battery_id", "status", "completed_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    for index_name in [
        "ix_battery_maintenance_battery_status_completed",
        "ix_batteries_health_percentage",
        "ix_users_created_at",
        "ix_rentals_status_start_time",
        "ix_rentals_start_station_start_time",
        "ix_rentals_start_time",
    ]:
        try:
            with bind.begin_nested():
                op.drop_index(index_name)
        except Exception:
            pass
