"""Add RFIDMapping table

Revision ID: cfd123456789
Revises: 53bfe56946c5
Create Date: 2026-03-31 17:30:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'cfd123456789'
down_revision: Union[str, None] = '53bfe56946c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'rfid_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rfid_tag', sa.String(), nullable=False),
        sa.Column('battery_serial', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['battery_serial'], ['inventory.batteries.serial_number']),
        sa.ForeignKeyConstraint(['created_by'], ['core.users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rfid_tag'),
        schema='inventory'
    )
    op.create_index(
        'ix_inventory_rfid_mappings_rfid_tag',
        'rfid_mappings',
        ['rfid_tag'],
        schema='inventory'
    )
    op.create_index(
        'ix_inventory_rfid_mappings_battery_serial',
        'rfid_mappings',
        ['battery_serial'],
        schema='inventory'
    )

def downgrade() -> None:
    op.drop_table('rfid_mappings', schema='inventory')
