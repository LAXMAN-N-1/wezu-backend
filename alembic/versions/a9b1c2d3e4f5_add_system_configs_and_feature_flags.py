"""add_system_configs_and_feature_flags

Creates system_configs and feature_flags tables if they don't exist.
These were defined in the initial migration but may be missing from
databases that were set up before the tables were added to that file.

Revision ID: a9b1c2d3e4f5
Revises: e2f4c6a8b9d0
Create Date: 2026-04-24

"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "a9b1c2d3e4f5"
down_revision: Union[str, None] = "e2f4c6a8b9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    def table_exists(name: str) -> bool:
        return conn.dialect.has_table(conn, name)

    if not table_exists("system_configs"):
        op.create_table(
            "system_configs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("value", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_system_configs_key"), "system_configs", ["key"], unique=True)

    if not table_exists("feature_flags"):
        op.create_table(
            "feature_flags",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False),
            sa.Column("rollout_percentage", sa.Integer(), nullable=False),
            sa.Column("enabled_for_users", sa.String(), nullable=True),
            sa.Column("enabled_for_tenants", sa.String(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_feature_flags_name"), "feature_flags", ["name"], unique=True)


def downgrade() -> None:
    conn = op.get_bind()

    def table_exists(name: str) -> bool:
        return conn.dialect.has_table(conn, name)

    if table_exists("feature_flags"):
        op.drop_index(op.f("ix_feature_flags_name"), table_name="feature_flags")
        op.drop_table("feature_flags")

    if table_exists("system_configs"):
        op.drop_index(op.f("ix_system_configs_key"), table_name="system_configs")
        op.drop_table("system_configs")
