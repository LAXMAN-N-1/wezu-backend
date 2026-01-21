"""add_financial_features

Revision ID: c14a61f942ca
Revises: 1c520ea20f5a
Create Date: 2025-12-22 15:14:36.180064

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c14a61f942ca'
down_revision: Union[str, None] = '1c520ea20f5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # WalletWithdrawalRequest
    op.create_table('walletwithdrawalrequest',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('wallet_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('bank_details', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['wallet_id'], ['wallet.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Settlement
    op.create_table('settlement',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dealer_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('total_commission', sa.Float(), nullable=False),
        sa.Column('total_deductions', sa.Float(), nullable=False),
        sa.Column('net_amount', sa.Float(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('pdf_statement_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(['dealer_id'], ['dealerprofile.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Update Invoice
    op.add_column('invoice', sa.Column('gstin', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('invoice', sa.Column('hsn_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('invoice', sa.Column('is_late_fee', sa.Boolean(), server_default='f', nullable=False))

    # Update Commission
    op.add_column('commission', sa.Column('settlement_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'commission', 'settlement', ['settlement_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'commission', type_='foreignkey')
    op.drop_column('commission', 'settlement_id')
    op.drop_column('invoice', 'is_late_fee')
    op.drop_column('invoice', 'hsn_code')
    op.drop_column('invoice', 'gstin')
    op.drop_table('settlement')
    op.drop_table('walletwithdrawalrequest')
