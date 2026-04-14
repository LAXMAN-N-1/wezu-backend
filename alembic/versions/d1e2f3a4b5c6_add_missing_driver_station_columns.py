"""add missing driver_profiles and stations columns

Revision ID: d1e2f3a4b5c6
Revises: f1e2d3c4b5a6
Create Date: 2026-04-14

Adds columns required by logistics schema guard:
  driver_profiles: name, phone_number, status, current_battery_level, location_accuracy
  stations: deleted_at
All uses IF NOT EXISTS so idempotent.
"""
from typing import Union, Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "f1e2d3c4b5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for col_sql in [
        "ALTER TABLE driver_profiles ADD COLUMN IF NOT EXISTS name VARCHAR",
        "ALTER TABLE driver_profiles ADD COLUMN IF NOT EXISTS phone_number VARCHAR",
        "ALTER TABLE driver_profiles ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'active'",
        "ALTER TABLE driver_profiles ADD COLUMN IF NOT EXISTS current_battery_level DOUBLE PRECISION",
        "ALTER TABLE driver_profiles ADD COLUMN IF NOT EXISTS location_accuracy DOUBLE PRECISION",
        "ALTER TABLE stations ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP",
    ]:
        op.execute(sa.text(col_sql))


def downgrade() -> None:
    for col_sql in [
        "ALTER TABLE driver_profiles DROP COLUMN IF EXISTS name",
        "ALTER TABLE driver_profiles DROP COLUMN IF EXISTS phone_number",
        "ALTER TABLE driver_profiles DROP COLUMN IF EXISTS status",
        "ALTER TABLE driver_profiles DROP COLUMN IF EXISTS current_battery_level",
        "ALTER TABLE driver_profiles DROP COLUMN IF EXISTS location_accuracy",
        "ALTER TABLE stations DROP COLUMN IF EXISTS deleted_at",
    ]:
        op.execute(sa.text(col_sql))
