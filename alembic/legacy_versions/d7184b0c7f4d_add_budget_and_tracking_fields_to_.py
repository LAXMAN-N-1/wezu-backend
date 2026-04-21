"""Add budget and tracking fields to dealer promotion

Revision ID: d7184b0c7f4d
Revises: 2c5038fb67d6
Create Date: 2026-03-04 00:43:16.267149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7184b0c7f4d'
down_revision: Union[str, None] = '2c5038fb67d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create new tables (safe)
    op.create_table('password_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('hashed_password', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_history_user_id'), 'password_history', ['user_id'], unique=False)
    op.create_table('revenue_reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('report_type', sa.String(), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('total_revenue', sa.Float(), nullable=False),
    sa.Column('total_transactions', sa.Integer(), nullable=False),
    sa.Column('avg_transaction_value', sa.Float(), nullable=False),
    sa.Column('total_refunds', sa.Float(), nullable=False),
    sa.Column('net_revenue', sa.Float(), nullable=False),
    sa.Column('growth_percentage', sa.Float(), nullable=True),
    sa.Column('breakdown_by_dealer', sa.JSON(), nullable=True),
    sa.Column('breakdown_by_station', sa.JSON(), nullable=True),
    sa.Column('breakdown_by_category', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_revenue_reports_period_start'), 'revenue_reports', ['period_start'], unique=False)
    op.create_index(op.f('ix_revenue_reports_report_type'), 'revenue_reports', ['report_type'], unique=False)

    # Safely add columns using IF NOT EXISTS (no-ops if already present)
    conn.execute(sa.text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS target_id INTEGER"))
    conn.execute(sa.text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS old_value JSON"))
    conn.execute(sa.text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS new_value JSON"))

    # Create index only if it doesn't exist
    result = conn.execute(sa.text("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_audit_logs_target_id'"))
    if not result.scalar():
        op.create_index(op.f('ix_audit_logs_target_id'), 'audit_logs', ['target_id'], unique=False)

    # commission_configs - only alter if table exists
    result = conn.execute(sa.text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='commission_configs')"))
    if result.scalar():
        conn.execute(sa.text("ALTER TABLE commission_configs ADD COLUMN IF NOT EXISTS effective_from TIMESTAMP WITHOUT TIME ZONE"))
        conn.execute(sa.text("ALTER TABLE commission_configs ADD COLUMN IF NOT EXISTS effective_until TIMESTAMP WITHOUT TIME ZONE"))

    # dealer_promotions - only alter if table exists
    result = conn.execute(sa.text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='dealer_promotions')"))
    if result.scalar():
        conn.execute(sa.text("ALTER TABLE dealer_promotions ADD COLUMN IF NOT EXISTS budget_limit FLOAT"))
        conn.execute(sa.text("ALTER TABLE dealer_promotions ADD COLUMN IF NOT EXISTS daily_cap INTEGER"))
        conn.execute(sa.text("ALTER TABLE dealer_promotions ADD COLUMN IF NOT EXISTS total_discount_given FLOAT NOT NULL DEFAULT 0"))
        conn.execute(sa.text("ALTER TABLE dealer_promotions ADD COLUMN IF NOT EXISTS impressions INTEGER NOT NULL DEFAULT 0"))
        conn.execute(sa.text("ALTER TABLE dealer_promotions ADD COLUMN IF NOT EXISTS applicable_station_ids VARCHAR"))

    # settlements - only alter if table exists
    result = conn.execute(sa.text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='settlements')"))
    if result.scalar():
        conn.execute(sa.text("ALTER TABLE settlements ADD COLUMN IF NOT EXISTS settlement_month VARCHAR NOT NULL DEFAULT ''"))
        conn.execute(sa.text("ALTER TABLE settlements ADD COLUMN IF NOT EXISTS total_commission FLOAT NOT NULL DEFAULT 0"))
        conn.execute(sa.text("ALTER TABLE settlements ADD COLUMN IF NOT EXISTS chargeback_amount FLOAT NOT NULL DEFAULT 0"))
        conn.execute(sa.text("ALTER TABLE settlements ADD COLUMN IF NOT EXISTS net_payable FLOAT NOT NULL DEFAULT 0"))
        conn.execute(sa.text("ALTER TABLE settlements ADD COLUMN IF NOT EXISTS payment_proof_url VARCHAR"))
        result2 = conn.execute(sa.text("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_settlements_settlement_month'"))
        if not result2.scalar():
            op.create_index(op.f('ix_settlements_settlement_month'), 'settlements', ['settlement_month'], unique=False)

    # users - always exists
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP WITHOUT TIME ZONE"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS force_password_change BOOLEAN NOT NULL DEFAULT FALSE"))



def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'force_password_change')
    op.drop_column('users', 'password_changed_at')
    op.add_column('settlements', sa.Column('payable_amount', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False))
    op.drop_index(op.f('ix_settlements_settlement_month'), table_name='settlements')
    op.drop_column('settlements', 'payment_proof_url')
    op.drop_column('settlements', 'net_payable')
    op.drop_column('settlements', 'chargeback_amount')
    op.drop_column('settlements', 'total_commission')
    op.drop_column('settlements', 'settlement_month')
    op.drop_column('dealer_promotions', 'applicable_station_ids')
    op.drop_column('dealer_promotions', 'impressions')
    op.drop_column('dealer_promotions', 'total_discount_given')
    op.drop_column('dealer_promotions', 'daily_cap')
    op.drop_column('dealer_promotions', 'budget_limit')
    op.drop_column('commission_configs', 'effective_until')
    op.drop_column('commission_configs', 'effective_from')
    op.drop_index(op.f('ix_audit_logs_target_id'), table_name='audit_logs')
    op.drop_column('audit_logs', 'new_value')
    op.drop_column('audit_logs', 'old_value')
    op.drop_column('audit_logs', 'target_id')
    op.drop_index(op.f('ix_revenue_reports_report_type'), table_name='revenue_reports')
    op.drop_index(op.f('ix_revenue_reports_period_start'), table_name='revenue_reports')
    op.drop_table('revenue_reports')
    op.drop_index(op.f('ix_password_history_user_id'), table_name='password_history')
    op.drop_table('password_history')
    # ### end Alembic commands ###
