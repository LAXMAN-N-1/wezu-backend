"""add_views

Revision ID: 4997d7b90c03
Revises: e4b784d7c20f
Create Date: 2025-12-22 14:45:24.795712

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4997d7b90c03'
down_revision: Union[str, None] = 'e4b784d7c20f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE VIEW analytics_summary AS
    SELECT 
        date_trunc('day', created_at) as date,
        count(id) as total_users
    FROM "user"
    GROUP BY 1;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS analytics_summary;")
