"""convert iot_device battery_id to uuid

Revision ID: 44f2d5399b8d
Revises: d4b0fe593fe7
Create Date: 2026-03-08 17:27:35.079394

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44f2d5399b8d'
down_revision: Union[str, None] = 'd4b0fe593fe7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert battery_id from integer to uuid, setting existing to NULL since they are incompatible
    op.execute("ALTER TABLE iot_devices ALTER COLUMN battery_id TYPE uuid USING NULL;")


def downgrade() -> None:
    op.execute("ALTER TABLE iot_devices ALTER COLUMN battery_id TYPE integer USING NULL;")
