"""add maintenance checklist tables

Revision ID: 3f9b2a1c4d5e
Revises: ed574375ad16
Create Date: 2026-04-02 16:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = "3f9b2a1c4d5e"
down_revision: Union[str, None] = "ed574375ad16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_type() -> sa.types.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)

    if not inspector.has_table("maintenance_checklist_templates"):
        op.create_table(
            "maintenance_checklist_templates",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("station_type", sa.String(), nullable=False, server_default="standard"),
            sa.Column("maintenance_type", sa.String(), nullable=False, server_default="routine"),
            sa.Column("tasks", _json_type(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index(
            "ix_maintenance_checklist_templates_name",
            "maintenance_checklist_templates",
            ["name"],
            unique=False,
        )
        op.create_index(
            "ix_maintenance_checklist_templates_station_type",
            "maintenance_checklist_templates",
            ["station_type"],
            unique=False,
        )
        op.create_index(
            "ix_maintenance_checklist_templates_maintenance_type",
            "maintenance_checklist_templates",
            ["maintenance_type"],
            unique=False,
        )

    if not inspector.has_table("maintenance_checklist_submissions"):
        # Build column list; only add FK to maintenance_records if that table exists
        has_mr = inspector.has_table("maintenance_records")
        mr_col = (
            sa.Column(
                "maintenance_record_id",
                sa.Integer(),
                sa.ForeignKey("maintenance_records.id"),
                nullable=True,
            )
            if has_mr
            else sa.Column("maintenance_record_id", sa.Integer(), nullable=True)
        )

        op.create_table(
            "maintenance_checklist_submissions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            mr_col,
            sa.Column(
                "template_id",
                sa.Integer(),
                sa.ForeignKey("maintenance_checklist_templates.id"),
                nullable=False,
            ),
            sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("completed_tasks", _json_type(), nullable=False),
            sa.Column("submitted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("submitted_by_name", sa.String(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index(
            "ix_maintenance_checklist_submissions_maintenance_record_id",
            "maintenance_checklist_submissions",
            ["maintenance_record_id"],
            unique=False,
        )
        op.create_index(
            "ix_maintenance_checklist_submissions_template_id",
            "maintenance_checklist_submissions",
            ["template_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)

    if inspector.has_table("maintenance_checklist_submissions"):
        op.drop_index(
            "ix_maintenance_checklist_submissions_template_id",
            table_name="maintenance_checklist_submissions",
        )
        op.drop_index(
            "ix_maintenance_checklist_submissions_maintenance_record_id",
            table_name="maintenance_checklist_submissions",
        )
        op.drop_table("maintenance_checklist_submissions")

    if inspector.has_table("maintenance_checklist_templates"):
        op.drop_index(
            "ix_maintenance_checklist_templates_maintenance_type",
            table_name="maintenance_checklist_templates",
        )
        op.drop_index(
            "ix_maintenance_checklist_templates_station_type",
            table_name="maintenance_checklist_templates",
        )
        op.drop_index(
            "ix_maintenance_checklist_templates_name",
            table_name="maintenance_checklist_templates",
        )
        op.drop_table("maintenance_checklist_templates")
