"""merge heads e28d617ecb29 and f6f6cfc2bec7

Revision ID: merge_e28d_f6f6
Revises: e28d617ecb29, f6f6cfc2bec7
Create Date: 2026-03-17 15:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'merge_e28d_f6f6'
down_revision: Union[str, None] = ('e28d617ecb29', 'f6f6cfc2bec7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
