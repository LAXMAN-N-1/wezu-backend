"""add_trigram_indexes

Revision ID: a196ed66a6c5
Revises: c3d4e5f6a7b8
Create Date: 2026-04-08 17:34:15.542700

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a196ed66a6c5'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pg_trgm extension to allow fast ILIKE and text similarity searches
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    
    # 2. Create GIN trigram indexes for primary search columns
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_full_name_trgm ON users USING gin (full_name gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email_trgm ON users USING gin (email gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_phone_trgm ON users USING gin (phone_number gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_stations_name_trgm ON stations USING gin (name gin_trgm_ops)")


def downgrade() -> None:
    # Drop trigram indexes
    op.execute("DROP INDEX IF EXISTS ix_stations_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_users_phone_trgm")
    op.execute("DROP INDEX IF EXISTS ix_users_email_trgm")
    op.execute("DROP INDEX IF EXISTS ix_users_full_name_trgm")
