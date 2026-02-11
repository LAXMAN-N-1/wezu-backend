"""merge heads

Revision ID: 977e543b1c75
Revises: 019_customer_app, 7147282b1fa1
Create Date: 2026-02-04 15:32:50.118731

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '977e543b1c75'
down_revision: Union[str, None] = ('019_customer_app', '7147282b1fa1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
