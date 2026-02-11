"""add_swap_fraud

Revision ID: 1c520ea20f5a
Revises: 23e2accc5ba3
Create Date: 2025-12-22 15:10:31.597226

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1c520ea20f5a'
down_revision: Union[str, None] = '23e2accc5ba3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SwapRequest
    op.create_table('swaprequest',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rental_id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('reserved_battery_id', sa.Integer(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('expiry_time', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['rental_id'], ['rental.id'], ),
        sa.ForeignKeyConstraint(['reserved_battery_id'], ['battery.id'], ),
        sa.ForeignKeyConstraint(['station_id'], ['station.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # SwapHistory
    op.create_table('swaphistory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rental_id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('old_battery_id', sa.Integer(), nullable=False),
        sa.Column('new_battery_id', sa.Integer(), nullable=False),
        sa.Column('soc_in', sa.Float(), nullable=False),
        sa.Column('soc_out', sa.Float(), nullable=False),
        sa.Column('swap_fee', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['new_battery_id'], ['battery.id'], ),
        sa.ForeignKeyConstraint(['old_battery_id'], ['battery.id'], ),
        sa.ForeignKeyConstraint(['rental_id'], ['rental.id'], ),
        sa.ForeignKeyConstraint(['station_id'], ['station.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # RiskScore
    op.create_table('riskscore',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('total_score', sa.Float(), nullable=False),
        sa.Column('breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    # FraudCheckLog
    op.create_table('fraudchecklog',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('check_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('details', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Blacklist
    op.create_table('blacklist',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('value', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_blacklist_value'), 'blacklist', ['value'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_blacklist_value'), table_name='blacklist')
    op.drop_table('blacklist')
    op.drop_table('fraudchecklog')
    op.drop_table('riskscore')
    op.drop_table('swaphistory')
    op.drop_table('swaprequest')
