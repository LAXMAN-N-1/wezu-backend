"""merge migration heads

Revision ID: 6755380a429d
Revises: 63e31f07d91a, eef1b0eaa6ef
Create Date: 2026-02-16 13:26:26.640937

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6755380a429d'
down_revision: Union[str, None] = ('63e31f07d91a', 'eef1b0eaa6ef')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
