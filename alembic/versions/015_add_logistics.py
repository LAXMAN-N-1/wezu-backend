"""add_logistics

Revision ID: 23e2accc5ba3
Revises: c6f7d0a14722
Create Date: 2025-12-22 15:06:56.697001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '23e2accc5ba3'
down_revision: Union[str, None] = 'c6f7d0a14722'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DriverProfile
    op.create_table('driverprofile',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('license_number', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('vehicle_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('vehicle_plate', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('is_online', sa.Boolean(), nullable=False),
        sa.Column('current_latitude', sa.Float(), nullable=True),
        sa.Column('current_longitude', sa.Float(), nullable=True),
        sa.Column('last_location_update', sa.DateTime(), nullable=True),
        sa.Column('rating', sa.Float(), nullable=False),
        sa.Column('total_deliveries', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    # DeliveryAssignment
    op.create_table('deliveryassignment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('return_request_id', sa.Integer(), nullable=True),
        sa.Column('driver_id', sa.Integer(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('pickup_address', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('delivery_address', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('picked_up_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('proof_of_delivery_img', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('customer_signature', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('otp_verified', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['driver_id'], ['driverprofile.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['order.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('deliveryassignment')
    op.drop_table('driverprofile')
