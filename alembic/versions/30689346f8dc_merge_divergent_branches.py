"""merge_divergent_branches

Revision ID: 30689346f8dc
Revises: db63948b0a3c, ef3c2dc85e46
Create Date: 2026-02-11 17:04:05.837106

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30689346f8dc'
down_revision: Union[str, None] = ('db63948b0a3c', 'ef3c2dc85e46')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
