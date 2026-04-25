"""change run_id to integer and sequential

Revision ID: 8128ac321536
Revises: eb1c5ca2d775
Create Date: 2026-04-21 12:24:00.308080

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8128ac321536'
down_revision: Union[str, None] = 'eb1c5ca2d775'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Truncate table to avoid casting errors from string 'run_...' to integer
    op.execute("TRUNCATE TABLE test_reports CASCADE")
    
    # 2. Change column type
    op.alter_column('test_reports', 'run_id',
               existing_type=sa.String(length=100),
               type_=sa.Integer(),
               postgresql_using='run_id::integer',
               existing_nullable=True)


def downgrade() -> None:
    op.alter_column('test_reports', 'run_id',
               existing_type=sa.Integer(),
               type_=sa.String(length=100),
               existing_nullable=True)
