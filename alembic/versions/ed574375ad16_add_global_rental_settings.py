"""Add global_rental_settings

Revision ID: ed574375ad16
Revises: eb06e42014cb
Create Date: 2026-04-01 17:20:03.796835

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ed574375ad16'
down_revision: Union[str, None] = 'eb06e42014cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    op.add_column('dealer_profiles', sa.Column('global_rental_settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('dealer_profiles', 'global_rental_settings')
