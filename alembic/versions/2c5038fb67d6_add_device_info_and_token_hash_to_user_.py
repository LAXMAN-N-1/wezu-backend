"""add device info and token hash to user session

Revision ID: 2c5038fb67d6
Revises: a1b2c3d4e5f6
Create Date: 2026-02-18 12:02:26.819954

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c5038fb67d6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create user_sessions table if not exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token_id VARCHAR NOT NULL,
            refresh_token_hash VARCHAR,
            device_id VARCHAR,
            device_name VARCHAR,
            ip_address VARCHAR,
            user_agent VARCHAR,
            location VARCHAR,
            device_type VARCHAR DEFAULT 'unknown' NOT NULL,
            os_version VARCHAR,
            app_version VARCHAR,
            is_active BOOLEAN DEFAULT 'true' NOT NULL,
            is_revoked BOOLEAN DEFAULT 'false' NOT NULL,
            revoked_at TIMESTAMP WITHOUT TIME ZONE,
            last_active_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            issued_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            expires_at TIMESTAMP WITHOUT TIME ZONE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
        );
    """)

    # 2. Create indexes if they don't exist
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions (user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_sessions_token_id ON user_sessions (token_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_sessions_device_id ON user_sessions (device_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_sessions_refresh_token_hash ON user_sessions (refresh_token_hash);")

def downgrade() -> None:
    op.drop_table('user_sessions')

