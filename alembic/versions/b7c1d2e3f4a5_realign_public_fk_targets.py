"""Realign public foreign keys away from core schema

Revision ID: b7c1d2e3f4a5
Revises: a9f4c3d2b1e0
Create Date: 2026-04-02 08:05:00
"""

from __future__ import annotations

from collections.abc import Iterable

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7c1d2e3f4a5"
down_revision = "a9f4c3d2b1e0"
branch_labels = None
depends_on = None


TARGET_REMAP = {
    ("core", "users"): ("public", "users"),
    ("core", "roles"): ("public", "roles"),
    ("core", "addresses"): ("public", "addresses"),
}


def _constraint_rows(conn: sa.engine.Connection) -> Iterable[dict[str, object]]:
    query = sa.text(
        """
        SELECT
            child_ns.nspname AS child_schema,
            child.relname AS child_table,
            con.conname AS constraint_name,
            parent_ns.nspname AS parent_schema,
            parent.relname AS parent_table,
            ARRAY_AGG(child_att.attname ORDER BY keys.ord) AS child_columns,
            ARRAY_AGG(parent_att.attname ORDER BY keys.ord) AS parent_columns,
            con.confupdtype AS update_type,
            con.confdeltype AS delete_type,
            con.condeferrable AS is_deferrable,
            con.condeferred AS is_deferred
        FROM pg_constraint con
        JOIN pg_class child ON child.oid = con.conrelid
        JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
        JOIN pg_class parent ON parent.oid = con.confrelid
        JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
        JOIN LATERAL UNNEST(con.conkey) WITH ORDINALITY AS keys(attnum, ord) ON TRUE
        JOIN pg_attribute child_att
            ON child_att.attrelid = child.oid
           AND child_att.attnum = keys.attnum
        JOIN pg_attribute parent_att
            ON parent_att.attrelid = parent.oid
           AND parent_att.attnum = con.confkey[keys.ord]
        WHERE con.contype = 'f'
          AND child_ns.nspname = 'public'
          AND (
                (parent_ns.nspname = 'core' AND parent.relname = 'users')
             OR (parent_ns.nspname = 'core' AND parent.relname = 'roles')
             OR (parent_ns.nspname = 'core' AND parent.relname = 'addresses')
          )
        GROUP BY
            child_ns.nspname,
            child.relname,
            con.conname,
            parent_ns.nspname,
            parent.relname,
            con.confupdtype,
            con.confdeltype,
            con.condeferrable,
            con.condeferred
        ORDER BY child_ns.nspname, child.relname, con.conname
        """
    )
    return conn.execute(query).mappings().all()


def _quote_ident(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _format_columns(columns: Iterable[str]) -> str:
    return ", ".join(_quote_ident(column) for column in columns)


def _fk_action(code: str) -> str:
    return {
        "a": "NO ACTION",
        "r": "RESTRICT",
        "c": "CASCADE",
        "n": "SET NULL",
        "d": "SET DEFAULT",
    }[code]


def _table_exists(conn: sa.engine.Connection, schema: str, table: str) -> bool:
    return bool(
        conn.execute(
            sa.text("SELECT to_regclass(:qualified_name) IS NOT NULL"),
            {"qualified_name": f"{schema}.{table}"},
        ).scalar_one()
    )


def _table_has_rows(conn: sa.engine.Connection, schema: str, table: str) -> bool:
    qualified_table = f"{schema}.{_quote_ident(table)}"
    return bool(conn.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {qualified_table})")).scalar_one())


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for row in _constraint_rows(bind):
        old_parent = (row["parent_schema"], row["parent_table"])
        new_parent_schema, new_parent_table = TARGET_REMAP[old_parent]
        if not _table_exists(bind, new_parent_schema, new_parent_table):
            continue

        child_table = row["child_table"]
        child_columns = _format_columns(row["child_columns"])
        parent_columns = _format_columns(row["parent_columns"])
        constraint_name = row["constraint_name"]

        op.drop_constraint(constraint_name, child_table, schema="public", type_="foreignkey")

        fk_sql = (
            f"ALTER TABLE public.{_quote_ident(child_table)} "
            f"ADD CONSTRAINT {_quote_ident(constraint_name)} "
            f"FOREIGN KEY ({child_columns}) "
            f"REFERENCES {new_parent_schema}.{_quote_ident(new_parent_table)} ({parent_columns}) "
            f"ON UPDATE {_fk_action(row['update_type'])} "
            f"ON DELETE {_fk_action(row['delete_type'])}"
        )
        if row["is_deferrable"]:
            fk_sql += " DEFERRABLE"
        if row["is_deferred"]:
            fk_sql += " INITIALLY DEFERRED"
        if _table_has_rows(bind, "public", child_table):
            fk_sql += " NOT VALID"

        op.execute(sa.text(fk_sql))


def downgrade() -> None:
    # Irreversible repair migration. Downgrading would reintroduce broken
    # cross-schema foreign keys into databases that use the public schema.
    return
