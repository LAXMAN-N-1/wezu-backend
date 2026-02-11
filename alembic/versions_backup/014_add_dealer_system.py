"""add_dealer_system

Revision ID: c6f7d0a14722
Revises: 5654ad288c62
Create Date: 2025-12-22 14:57:26.171347

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c6f7d0a14722'
down_revision: Union[str, None] = '5654ad288c62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DealerProfile
    op.create_table('dealerprofile',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('business_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('gst_number', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('pan_number', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('contact_person', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('contact_email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('contact_phone', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('address_line1', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('city', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('state', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('pincode', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    # DealerApplication
    op.create_table('dealerapplication',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dealer_id', sa.Integer(), nullable=False),
        sa.Column('current_stage', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=False),
        sa.Column('status_history', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dealer_id'], ['dealerprofile.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dealer_id')
    )

    # FieldVisit
    op.create_table('fieldvisit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('officer_id', sa.Integer(), nullable=False),
        sa.Column('scheduled_date', sa.DateTime(), nullable=False),
        sa.Column('completed_date', sa.DateTime(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('report_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('images', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['dealerapplication.id'], ),
        sa.ForeignKeyConstraint(['officer_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Update Station
    op.add_column('station', sa.Column('dealer_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'station', 'dealerprofile', ['dealer_id'], ['id'])

    # Update Commission (fix fk)
    # Assuming dealer_id column exists (from previous steps if not we add it)
    # But wait, M9 added Commission table with dealer_id as Int (no FK). 
    # So we just add FK constraint now.
    op.create_foreign_key(None, 'commission', 'dealerprofile', ['dealer_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'commission', type_='foreignkey')
    op.drop_constraint(None, 'station', type_='foreignkey')
    op.drop_column('station', 'dealer_id')
    op.drop_table('fieldvisit')
    op.drop_table('dealerapplication')
    op.drop_table('dealerprofile')
