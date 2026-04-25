"""merge heads

Revision ID: 30e4397d49db
Revises: a9b1c2d3e4f5, ca61738e27e1
Create Date: 2026-04-24 21:48:22.254316

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30e4397d49db'
down_revision: Union[str, None] = ('a9b1c2d3e4f5', 'ca61738e27e1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
