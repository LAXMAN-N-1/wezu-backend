"""add_triggers

Revision ID: e4b784d7c20f
Revises: e0fff5b87f4e
Create Date: 2025-12-22 14:44:54.614994

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4b784d7c20f'
down_revision: Union[str, None] = 'e0fff5b87f4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    -- check_wallet_balance function
    CREATE OR REPLACE FUNCTION check_wallet_balance() RETURNS TRIGGER AS $$
    BEGIN
        IF NEW.amount < 0 THEN
            IF (SELECT balance FROM wallet WHERE id = NEW.wallet_id) < ABS(NEW.amount) THEN
                RAISE EXCEPTION 'Insufficient funds';
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    
    -- Trigger definition
    CREATE TRIGGER check_wallet_balance_trigger
    BEFORE INSERT ON transaction
    FOR EACH ROW
    EXECUTE FUNCTION check_wallet_balance();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS check_wallet_balance_trigger ON transaction;")
    op.execute("DROP FUNCTION IF EXISTS check_wallet_balance();")
