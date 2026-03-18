"""add campaigns tables

Revision ID: a1b2c3d4e5f6
Revises: 7e13b0f4d899
Create Date: 2026-03-15 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '7e13b0f4d899'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- campaigns ---
    op.create_table(
        'campaigns',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('target_criteria', sa.JSON(), nullable=True),
        sa.Column('message_title', sa.String(length=60), nullable=False),
        sa.Column('message_body', sa.String(length=200), nullable=False),
        sa.Column('promo_code_id', sa.Integer(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('frequency_cap', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('sent_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('opened_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('converted_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['promo_code_id'], ['promo_codes.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['core.users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='core'
    )
    op.create_index(op.f('ix_core_campaigns_id'), 'campaigns', ['id'], schema='core')
    op.create_index(op.f('ix_core_campaigns_name'), 'campaigns', ['name'], schema='core')
    op.create_index(op.f('ix_core_campaigns_type'), 'campaigns', ['type'], schema='core')
    op.create_index(op.f('ix_core_campaigns_status'), 'campaigns', ['status'], schema='core')

    # --- campaign_targets ---
    op.create_table(
        'campaign_targets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('campaign_id', sa.Uuid(), nullable=False),
        sa.Column('rule_type', sa.String(), nullable=False),
        sa.Column('rule_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['campaign_id'], ['core.campaigns.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='core'
    )
    op.create_index(op.f('ix_core_campaign_targets_id'), 'campaign_targets', ['id'], schema='core')
    op.create_index(op.f('ix_core_campaign_targets_campaign_id'), 'campaign_targets', ['campaign_id'], schema='core')

    # --- campaign_sends ---
    op.create_table(
        'campaign_sends',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('campaign_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('opened_at', sa.DateTime(), nullable=True),
        sa.Column('converted_at', sa.DateTime(), nullable=True),
        sa.Column('notification_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['core.campaigns.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['core.users.id'], ),
        sa.ForeignKeyConstraint(['notification_id'], ['core.notifications.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='core'
    )
    op.create_index(op.f('ix_core_campaign_sends_id'), 'campaign_sends', ['id'], schema='core')
    op.create_index(op.f('ix_core_campaign_sends_campaign_id'), 'campaign_sends', ['campaign_id'], schema='core')
    op.create_index(op.f('ix_core_campaign_sends_user_id'), 'campaign_sends', ['user_id'], schema='core')


def downgrade() -> None:
    op.drop_table('campaign_sends', schema='core')
    op.drop_table('campaign_targets', schema='core')
    op.drop_table('campaigns', schema='core')
