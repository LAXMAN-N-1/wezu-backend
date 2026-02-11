"""add emergency_contact and notification_preferences to users

Revision ID: db63948b0a3c
Revises: 4cd75111728e
Create Date: 2026-02-05 14:39:44.189582

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'db63948b0a3c'
down_revision: Union[str, None] = '4cd75111728e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to users table
    op.add_column('users', sa.Column('emergency_contact', sa.String(), nullable=True))
    op.add_column('users', sa.Column('notification_preferences', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'notification_preferences')
    op.drop_column('users', 'emergency_contact')
