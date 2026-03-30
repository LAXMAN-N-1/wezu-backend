"""Add dealer auth fields

Revision ID: ba316815d31e
Revises: merge_e28d_f6f6
Create Date: 2026-03-24 20:07:49.710428

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba316815d31e'
down_revision: Union[str, None] = 'merge_e28d_f6f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('users', sa.Column('created_by_dealer_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('created_by_user_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('invite_token', sa.String(), nullable=True))
    op.add_column('users', sa.Column('invite_token_expires', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('invite_sent_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('department', sa.String(), nullable=True))
    op.add_column('users', sa.Column('notes_internal', sa.String(), nullable=True))
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True))

    # Add constraints and indexes
    # We must explicitly name the foreign key constraint to cleanly drop it later
    op.create_foreign_key(
        'fk_users_created_by_dealer_id_dealer_profiles',
        'users', 'dealer_profiles',
        ['created_by_dealer_id'], ['id']
    )
    op.create_index(op.f('ix_users_created_by_dealer_id'), 'users', ['created_by_dealer_id'], unique=False)
    op.create_index(op.f('ix_users_invite_token'), 'users', ['invite_token'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_invite_token'), table_name='users')
    op.drop_index(op.f('ix_users_created_by_dealer_id'), table_name='users')
    op.drop_constraint('fk_users_created_by_dealer_id_dealer_profiles', 'users', type_='foreignkey')
    
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
    op.drop_column('users', 'notes_internal')
    op.drop_column('users', 'department')
    op.drop_column('users', 'invite_sent_at')
    op.drop_column('users', 'invite_token_expires')
    op.drop_column('users', 'invite_token')
    op.drop_column('users', 'created_by_user_id')
    op.drop_column('users', 'created_by_dealer_id')
