"""Add expression index on lower(email) for case-insensitive login lookups.

Replaces 3 sequential queries (exact, case-sensitive, case-insensitive) with
a single func.lower(User.email) query that hits this index.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # Check if the index already exists before creating
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_users_email_lower'"
        )
    ).fetchone()
    if not result:
        op.execute(
            "CREATE INDEX ix_users_email_lower ON users (lower(email))"
        )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_users_email_lower")
