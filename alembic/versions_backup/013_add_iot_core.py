"""add_iot_core

Revision ID: 5654ad288c62
Revises: 4997d7b90c03
Create Date: 2025-12-22 14:53:56.611553

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5654ad288c62'
down_revision: Union[str, None] = '4997d7b90c03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FirmwareUpdate
    op.create_table('firmwareupdate',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('file_url', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('checksum', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('device_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('is_critical', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # IoTDevice
    op.create_table('iotdevice',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('device_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('firmware_version', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('communication_protocol', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('battery_id', sa.Integer(), nullable=True),
        sa.Column('auth_token', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
        sa.Column('last_ip_address', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['battery_id'], ['battery.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_iotdevice_device_id'), 'iotdevice', ['device_id'], unique=True)

    # DeviceCommand
    op.create_table('devicecommand',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('command_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('payload', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('response_data', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['iotdevice.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('devicecommand')
    op.drop_index(op.f('ix_iotdevice_device_id'), table_name='iotdevice')
    op.drop_table('iotdevice')
    op.drop_table('firmwareupdate')
