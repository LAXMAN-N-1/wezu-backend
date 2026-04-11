"""Manual add user fields

Revision ID: d6b338f82335
Revises: ab35322d41e6
Create Date: 2026-02-27 16:30:48.250625

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6b338f82335'
down_revision: Union[str, None] = 'ab35322d41e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS backup_codes JSON;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_email_verified BOOLEAN DEFAULT FALSE NOT NULL;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_sent_at TIMESTAMP WITHOUT TIME ZONE;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITHOUT TIME ZONE;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE NOT NULL;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS deletion_reason VARCHAR;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITHOUT TIME ZONE;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS two_factor_enabled BOOLEAN DEFAULT FALSE NOT NULL;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS two_factor_secret VARCHAR;")


def downgrade() -> None:
    pass

