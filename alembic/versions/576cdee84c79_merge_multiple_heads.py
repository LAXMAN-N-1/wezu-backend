"""merge_multiple_heads

Revision ID: 576cdee84c79
Revises: c1a2b3d4e5f7, d7184b0c7f4d, ed574375ad16, f6f6cfc2bec7
Create Date: 2026-04-14 13:57:32.200190

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '576cdee84c79'
down_revision: Union[str, None] = ('c1a2b3d4e5f7', 'd7184b0c7f4d', 'ed574375ad16', 'f6f6cfc2bec7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
