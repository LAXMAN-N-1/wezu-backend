"""Fix reorder request id default

Revision ID: d1e2f3a4b5c6
Revises: c9d8e7f6a5b4
Create Date: 2026-04-02 08:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "c9d8e7f6a5b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    column_default = bind.execute(
        sa.text(
            """
            SELECT column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'reorder_requests'
              AND column_name = 'id'
            """
        )
    ).scalar_one_or_none()
    if column_default:
        return

    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS public.reorder_requests_id_seq"))
    op.execute(sa.text("ALTER SEQUENCE public.reorder_requests_id_seq OWNED BY public.reorder_requests.id"))

    max_id = bind.execute(sa.text("SELECT COALESCE(MAX(id), 0) FROM public.reorder_requests")).scalar_one()
    if max_id > 0:
        bind.execute(
            sa.text("SELECT setval('public.reorder_requests_id_seq', :value, true)"),
            {"value": max_id},
        )
    else:
        bind.execute(sa.text("SELECT setval('public.reorder_requests_id_seq', 1, false)"))

    op.execute(
        sa.text(
            """
            ALTER TABLE public.reorder_requests
            ALTER COLUMN id SET DEFAULT nextval('public.reorder_requests_id_seq')
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text("ALTER TABLE public.reorder_requests ALTER COLUMN id DROP DEFAULT"))
