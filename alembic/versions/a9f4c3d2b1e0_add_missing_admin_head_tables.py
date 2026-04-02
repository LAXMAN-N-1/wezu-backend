"""Add missing admin head tables

Revision ID: a9f4c3d2b1e0
Revises: ed574375ad16
Create Date: 2026-04-02 15:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
from sqlmodel import SQLModel

import app.models.all  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "a9f4c3d2b1e0"
down_revision: Union[str, None] = "ed574375ad16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MISSING_HEAD_TABLES = (
    "battery_reservations",
    "biometric_credentials",
    "cart_items",
    "churn_predictions",
    "demand_forecasts",
    "inventory_audit_logs",
    "pricing_recommendations",
    "security_questions",
    "user_security_questions",
    "user_status_logs",
)


def _tables_to_create():
    wanted = set(MISSING_HEAD_TABLES)
    return [table for table in SQLModel.metadata.sorted_tables if table.name in wanted]


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind, tables=_tables_to_create(), checkfirst=True)


def downgrade() -> None:
    # This migration repairs head-schema drift for already-upgraded environments.
    # Dropping these tables would be destructive for seeded or production data.
    pass
