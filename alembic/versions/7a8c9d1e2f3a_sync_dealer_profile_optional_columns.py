"""sync_dealer_profile_optional_columns

Revision ID: 7a8c9d1e2f3a
Revises: eb06e42014cb
Create Date: 2026-04-01 12:35:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7a8c9d1e2f3a"
down_revision: Union[str, None] = "eb06e42014cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DEALER_PROFILE_COLUMNS = [
    ("year_established", sa.Column("year_established", sa.String(), nullable=True)),
    ("website_url", sa.Column("website_url", sa.String(), nullable=True)),
    ("business_description", sa.Column("business_description", sa.String(), nullable=True)),
    ("alternate_phone", sa.Column("alternate_phone", sa.String(), nullable=True)),
    ("whatsapp_number", sa.Column("whatsapp_number", sa.String(), nullable=True)),
    ("support_email", sa.Column("support_email", sa.String(), nullable=True)),
    ("support_phone", sa.Column("support_phone", sa.String(), nullable=True)),
    (
        "global_station_defaults",
        sa.Column(
            "global_station_defaults",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
    ),
    (
        "global_inventory_rules",
        sa.Column(
            "global_inventory_rules",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
    ),
    (
        "holiday_calendar",
        sa.Column(
            "holiday_calendar",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("dealer_profiles"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("dealer_profiles")}

    for column_name, column in _DEALER_PROFILE_COLUMNS:
        if column_name not in existing_columns:
            op.add_column("dealer_profiles", column)


def downgrade() -> None:
    # No-op downgrade for compatibility migration.
    # Dropping columns here can remove production data.
    pass
