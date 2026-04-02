"""bootstrap_public_schema

Revision ID: eb06e42014cb
Revises:
Create Date: 2026-03-30 11:57:35.595756

This repository's historical schema was largely created via SQLModel metadata
bootstrap rather than a trustworthy Alembic lineage. For new environments we
need `alembic upgrade head` to create a usable schema instead of replaying a
destructive diff against tables that do not exist.

This baseline migration intentionally bootstraps the current public-schema
metadata in an idempotent way. Later revisions in this chain are additive
compatibility migrations and are written to no-op when the target columns
already exist.
"""

from typing import Sequence, Union

from alembic import op
from sqlmodel import SQLModel

import app.models.all  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "eb06e42014cb"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _public_tables():
    return [
        table
        for table in SQLModel.metadata.sorted_tables
        if table.schema in (None, "public")
    ]


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind, tables=_public_tables(), checkfirst=True)


def downgrade() -> None:
    # This baseline represents the canonical bootstrap schema for new
    # environments. A destructive downgrade would be unsafe for production data.
    pass
