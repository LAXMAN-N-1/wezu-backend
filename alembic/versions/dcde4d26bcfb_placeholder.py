"""placeholder for missing migration dcde4d26bcfb

Revision ID: dcde4d26bcfb
Revises: ab35322d41e6
Create Date: 2026-02-16 12:59:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'dcde4d26bcfb'
down_revision: Union[str, None] = 'ab35322d41e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # This placeholder migration was recreated because the original file was missing.
    # It assumes all tables from ab35322d41e6 already exist.
    pass

def downgrade() -> None:
    pass
