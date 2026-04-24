"""schema_consolidation

Revision ID: eb06e42014cb
Revises: 7ca261ec12f5
Create Date: 2026-03-30 11:57:35.595756

All DDL uses IF EXISTS / IF NOT EXISTS so this migration is fully idempotent
and safe to run against an existing database that may or may not have the
legacy tables/columns it cleans up.
"""
from typing import Union, Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'eb06e42014cb'
down_revision: Union[str, None] = '7ca261ec12f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Drop legacy tables (IF EXISTS — safe on any DB) ---
    for tbl in [
        'biometric_tokens', 'maintenanceschedule', 'blogs',
        'demandforecast', 'inventory_audit_logs', 'pricingrecommendation',
        'stationdowntime', 'churnprediction', 'favorite',
        'telemetics_data', 'notificationpreference', 'maintenancerecord',
    ]:
        op.execute(sa.text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))

    # --- Drop legacy indexes (IF EXISTS) ---
    for idx in [
        'ix_biometric_tokens_device_id', 'ix_biometric_tokens_user_id',
        'ix_demandforecast_forecast_date', 'ix_churnprediction_user_id',
        'ix_telemetics_data_battery_id',
    ]:
        op.execute(sa.text(f"DROP INDEX IF EXISTS {idx}"))

    # --- Banners: add new columns (IF NOT EXISTS) ---
    for col_sql in [
        "ALTER TABLE banners ADD COLUMN IF NOT EXISTS deep_link VARCHAR",
        "ALTER TABLE banners ADD COLUMN IF NOT EXISTS external_url VARCHAR",
        "ALTER TABLE banners ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE banners ADD COLUMN IF NOT EXISTS start_date TIMESTAMP",
        "ALTER TABLE banners ADD COLUMN IF NOT EXISTS end_date TIMESTAMP",
        "ALTER TABLE banners ADD COLUMN IF NOT EXISTS click_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE banners ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
    ]:
        op.execute(sa.text(col_sql))
    op.execute(sa.text("ALTER TABLE banners DROP COLUMN IF EXISTS target_url"))

    # --- Legal documents: add columns (IF NOT EXISTS) ---
    for col_sql in [
        "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS slug VARCHAR",
        "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS force_update BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS published_at TIMESTAMP",
        "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
    ]:
        op.execute(sa.text(col_sql))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_legal_documents_slug "
        "ON legal_documents (slug) WHERE slug IS NOT NULL"
    ))
    op.execute(sa.text("ALTER TABLE legal_documents DROP COLUMN IF EXISTS type"))

    # --- Users: drop stale columns (IF EXISTS) ---
    for col in [
        'sessions', 'email_verification_sent_at', 'is_email_verified',
        'two_factor_auth', 'tenant_id', 'email_verification_token',
    ]:
        op.execute(sa.text(f"ALTER TABLE users DROP COLUMN IF EXISTS {col}"))

    # --- Foreign keys: create only if missing ---
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_type='FOREIGN KEY'
                  AND table_name='chargebacks'
                  AND constraint_name LIKE '%settlement%'
            ) THEN
                ALTER TABLE chargebacks ADD CONSTRAINT fk_chargebacks_settlement
                    FOREIGN KEY (settlement_id) REFERENCES settlements(id);
            END IF;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_type='FOREIGN KEY'
                  AND table_name='late_fees'
                  AND constraint_name LIKE '%invoice%'
            ) THEN
                ALTER TABLE late_fees ADD CONSTRAINT fk_late_fees_invoice
                    FOREIGN KEY (invoice_id) REFERENCES invoices(id);
            END IF;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_type='FOREIGN KEY'
                  AND table_name='refunds'
                  AND constraint_name LIKE '%transaction%'
            ) THEN
                ALTER TABLE refunds ADD CONSTRAINT fk_refunds_transaction
                    FOREIGN KEY (transaction_id) REFERENCES transactions(id);
            END IF;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_type='FOREIGN KEY'
                  AND table_name='wallet_withdrawal_requests'
                  AND constraint_name LIKE '%wallet%'
            ) THEN
                ALTER TABLE wallet_withdrawal_requests ADD CONSTRAINT fk_withdrawal_wallet
                    FOREIGN KEY (wallet_id) REFERENCES wallets(id);
            END IF;
        END $$
    """))


def downgrade() -> None:
    pass
