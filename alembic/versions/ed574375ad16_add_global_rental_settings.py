"""Add global_rental_settings

Revision ID: ed574375ad16
Revises: eb06e42014cb
Create Date: 2026-04-01 17:20:03.796835

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'ed574375ad16'
down_revision: Union[str, None] = '7a8c9d1e2f3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("dealer_profiles"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("dealer_profiles")}
    if "global_rental_settings" not in existing_columns:
        op.add_column(
            "dealer_profiles",
            sa.Column(
                "global_rental_settings",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("dealer_profiles"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("dealer_profiles")}
    if "global_rental_settings" in existing_columns:
        op.drop_column("dealer_profiles", "global_rental_settings")
