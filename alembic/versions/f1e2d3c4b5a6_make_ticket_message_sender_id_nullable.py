"""make ticket_message sender_id nullable

Revision ID: f1e2d3c4b5a6
Revises: 42c8d9e1f2b3
Create Date: 2026-04-07 12:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'f1e2d3c4b5a6'
down_revision: Union[str, None] = '42c8d9e1f2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Make core.ticket_messages.sender_id nullable
    op.alter_column(
        'ticket_messages', 
        'sender_id',
        existing_type=sa.INTEGER(),
        nullable=True,
        schema='core'
    )

def downgrade() -> None:
    # Revert core.ticket_messages.sender_id to non-nullable
    op.alter_column(
        'ticket_messages',
        'sender_id',
        existing_type=sa.INTEGER(),
        nullable=False,
        schema='core'
    )
