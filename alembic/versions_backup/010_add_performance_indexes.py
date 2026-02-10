"""add_performance_indexes

Revision ID: e0fff5b87f4e
Revises: 3aa053ae04ae
Create Date: 2025-12-22 14:43:22.450686

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0fff5b87f4e'
down_revision: Union[str, None] = '3aa053ae04ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f('ix_user_created_at'), 'user', ['created_at'], unique=False, if_not_exists=True)
    op.create_index(op.f('ix_transaction_created_at'), 'transaction', ['created_at'], unique=False, if_not_exists=True)
    op.create_index(op.f('ix_auditlog_timestamp'), 'auditlog', ['timestamp'], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_auditlog_timestamp'), table_name='auditlog')
    op.drop_index(op.f('ix_transaction_created_at'), table_name='transaction')
    op.drop_index(op.f('ix_user_created_at'), table_name='user')
