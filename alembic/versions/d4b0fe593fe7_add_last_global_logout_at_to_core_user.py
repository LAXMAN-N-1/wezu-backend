"""add last_global_logout_at to core user

Revision ID: d4b0fe593fe7
Revises: 14b548ec0175
Create Date: 2026-03-08 17:07:27.059482

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b0fe593fe7'
down_revision: Union[str, None] = '14b548ec0175'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_global_logout_at TIMESTAMP WITHOUT TIME ZONE;")


def downgrade() -> None:
    op.drop_column('users', 'last_global_logout_at')
