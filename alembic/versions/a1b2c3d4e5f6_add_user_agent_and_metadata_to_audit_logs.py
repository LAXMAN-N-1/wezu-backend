"""add_user_agent_and_metadata_to_audit_logs

Revision ID: a1b2c3d4e5f6
Revises: dcde4d26bcfb
Create Date: 2026-02-16 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'dcde4d26bcfb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_agent column to audit_logs
    op.add_column('audit_logs', sa.Column('user_agent', sa.String(), nullable=True))
    # Add metadata column (JSON) to audit_logs
    op.add_column('audit_logs', sa.Column('metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('audit_logs', 'metadata')
    op.drop_column('audit_logs', 'user_agent')
