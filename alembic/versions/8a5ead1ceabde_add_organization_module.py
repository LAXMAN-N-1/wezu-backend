"""Add Organization module and link to Branch

Revision ID: 8a5ead1ceabde
Revises: e7d6e537e5b0
Create Date: 2026-02-09 12:58:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '8a5ead1ceabde'
down_revision: Union[str, None] = 'e7d6e537e5b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Create organizations table
    op.create_table('organizations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('code', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('website', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('logo_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('logo_width', sa.Integer(), nullable=True),
    sa.Column('logo_height', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_organizations_code'), 'organizations', ['code'], unique=True)
    op.create_index(op.f('ix_organizations_name'), 'organizations', ['name'], unique=False)

    # 2. Create organization_social_links table
    op.create_table('organization_social_links',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('platform', sa.Enum('website', 'facebook', 'instagram', 'linkedin', 'twitter', 'youtube', 'others', name='socialplatform'), nullable=False),
    sa.Column('url', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # 3. Add organization_id to branches table
    op.add_column('branches', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_branches_organization', 'branches', 'organizations', ['organization_id'], ['id'])

def downgrade() -> None:
    op.drop_constraint('fk_branches_organization', 'branches', type_='foreignkey')
    op.drop_column('branches', 'organization_id')
    op.drop_table('organization_social_links')
    op.drop_index(op.f('ix_organizations_name'), table_name='organizations')
    op.drop_index(op.f('ix_organizations_code'), table_name='organizations')
    op.drop_table('organizations')
