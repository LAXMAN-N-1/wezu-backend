"""add missing rbac role columns for multi-role rollout

Revision ID: 8d7c6b5a4f3e
Revises: d1e2f3a4b5c6
Create Date: 2026-04-15 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "8d7c6b5a4f3e"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("roles"):
        return

    cols = {col["name"] for col in inspector.get_columns("roles")}

    if "is_custom_role" not in cols:
        op.add_column(
            "roles",
            sa.Column("is_custom_role", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if "scope_owner" not in cols:
        op.add_column(
            "roles",
            sa.Column("scope_owner", sa.String(), nullable=False, server_default="global"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("roles"):
        return

    cols = {col["name"] for col in inspector.get_columns("roles")}

    if "scope_owner" in cols:
        op.drop_column("roles", "scope_owner")

    if "is_custom_role" in cols:
        op.drop_column("roles", "is_custom_role")
