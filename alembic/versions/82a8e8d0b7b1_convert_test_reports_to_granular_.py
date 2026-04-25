"""convert test_reports to granular granular schema

Revision ID: 82a8e8d0b7b1
Revises: 8128ac321536
Create Date: 2026-04-21 12:40:50.448471

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82a8e8d0b7b1'
down_revision: Union[str, None] = '8128ac321536'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
