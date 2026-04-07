"""expand_battery_enums_and_fields

Expand BatteryStatus enum with service-layer statuses (deployed, reserved,
in_transit, faulty, new, ready).  Expand LocationType enum with service-layer
types (customer, transit, shelf).  Add lifecycle milestone columns to batteries.

Also fixes RentalService.return_battery referencing drop_station_id (now uses
end_station_id which already exists in the model).

Revision ID: a1b2c3d4e5f6
Revises: 3f9b2a1c4d5e
Create Date: 2026-04-07 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "3f9b2a1c4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── PostgreSQL enum expansion ───────────────────────────────────────────
# Postgres requires ALTER TYPE ... ADD VALUE for each new enum member.
# SQLite ignores enum types (they're just text columns).

NEW_BATTERY_STATUSES = ["deployed", "reserved", "in_transit", "faulty", "new", "ready"]
NEW_LOCATION_TYPES = ["customer", "transit", "shelf"]


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ── 1. Expand BatteryStatus enum ────────────────────────────────────
    if dialect == "postgresql":
        for status in NEW_BATTERY_STATUSES:
            op.execute(
                f"ALTER TYPE batterystatus ADD VALUE IF NOT EXISTS '{status}'"
            )

    # ── 2. Expand LocationType enum ─────────────────────────────────────
    if dialect == "postgresql":
        for loc_type in NEW_LOCATION_TYPES:
            op.execute(
                f"ALTER TYPE locationtype ADD VALUE IF NOT EXISTS '{loc_type}'"
            )

    # ── 3. Add lifecycle milestone columns to batteries ─────────────────
    with op.batch_alter_table("batteries", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("retirement_date", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("decommissioned_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "decommissioned_by",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("decommission_reason", sa.String(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("batteries", schema=None) as batch_op:
        batch_op.drop_column("decommission_reason")
        batch_op.drop_column("decommissioned_by")
        batch_op.drop_column("decommissioned_at")
        batch_op.drop_column("retirement_date")

    # NOTE: Postgres does not support DROP VALUE from enums.
    # To fully downgrade, you'd need to recreate the enum type.
    # This is intentionally omitted for safety.
