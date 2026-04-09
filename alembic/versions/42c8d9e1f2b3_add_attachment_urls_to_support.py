"""Add attachment_urls to support tickets and messages

Revision ID: 42c8d9e1f2b3
Revises: cfd123456789
Create Date: 2026-04-06 14:02:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '42c8d9e1f2b3'
down_revision: Union[str, None] = 'cfd123456789'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add attachment_urls to support_tickets
    op.add_column(
        'support_tickets',
        sa.Column('attachment_urls', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        schema='core'
    )
    # Add attachment_urls to ticket_messages
    op.add_column(
        'ticket_messages',
        sa.Column('attachment_urls', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        schema='core'
    )

def downgrade() -> None:
    op.drop_column('ticket_messages', 'attachment_urls', schema='core')
    op.drop_column('support_tickets', 'attachment_urls', schema='core')
