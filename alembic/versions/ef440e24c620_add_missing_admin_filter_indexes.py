"""Add missing admin filter indexes.

Revision ID: ef440e24c620
Revises: a196ed66a6c5
Create Date: 2026-04-09 14:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "ef440e24c620"
down_revision = "a196ed66a6c5"
branch_labels = None
depends_on = None

def _safe_create_index(index_name: str, table: str, columns: list[str], **kw):
    """Create an index only if it doesn't already exist."""
    bind = op.get_bind()
    try:
        with bind.begin_nested():
            op.create_index(index_name, table, columns, **kw)
    except Exception:
        pass  # index or table doesn't exist — skip silently

def upgrade() -> None:
    # User missing indexes
    _safe_create_index("ix_users_is_deleted", "users", ["is_deleted"])
    
    # Station missing indexes
    _safe_create_index("ix_stations_status", "stations", ["status"])
    _safe_create_index("ix_stations_station_type", "stations", ["station_type"])
    
    # Battery missing indexes
    _safe_create_index("ix_batteries_location_type", "batteries", ["location_type"])
    _safe_create_index("ix_batteries_battery_type", "batteries", ["battery_type"])
    _safe_create_index("ix_batteries_manufacturer", "batteries", ["manufacturer"])

def downgrade() -> None:
    bind = op.get_bind()
    for idx in [
        "ix_batteries_manufacturer",
        "ix_batteries_battery_type",
        "ix_batteries_location_type",
        "ix_stations_station_type",
        "ix_stations_status",
        "ix_users_is_deleted",
    ]:
        try:
            with bind.begin_nested():
                op.drop_index(idx)
        except Exception:
            pass
