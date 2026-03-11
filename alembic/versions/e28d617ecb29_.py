"""empty message

Revision ID: e28d617ecb29
Revises: d7184b0c7f4d
Create Date: 2026-03-04 00:47:28.964984

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e28d617ecb29'
down_revision: Union[str, None] = 'd7184b0c7f4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
