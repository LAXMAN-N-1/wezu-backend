"""Add performance indexes for N+1 and slow query elimination.

Covers the most queried foreign-key columns that lack indexes:
- users.role_id          (RBAC middleware, deps, role distribution)
- stations.dealer_id     (dealer portal: dashboard, customers, transactions)
- rentals.user_id        (customer rentals, analytics)
- rentals.start_station_id (station-based rental lookups)
- rentals.status         (active rental counts, dashboard)
- batteries.location_id  (station health, inventory)
- kyc_documents.user_id  (KYC queue)
- audit_logs.user_id     (admin audit logs)
- user_roles.user_id     (RBAC bulk ops, role distribution)
- user_roles.role_id     (role distribution GROUP BY)

Revision ID: ef440e24c619
Revises: 3f9b2a1c4d5e
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "ef440e24c619"
down_revision = "3f9b2a1c4d5e"
branch_labels = None
depends_on = None


def _safe_create_index(index_name: str, table: str, columns: list[str], **kw):
    """Create an index only if it doesn't already exist.

    Uses a SAVEPOINT so that a failure (e.g. index/table already exists)
    doesn't abort the outer PostgreSQL transaction.
    """
    bind = op.get_bind()
    try:
        with bind.begin_nested():          # SAVEPOINT
            op.create_index(index_name, table, columns, **kw)
    except Exception:
        pass  # index or table doesn't exist — skip silently


def upgrade() -> None:
    _safe_create_index("ix_users_role_id", "users", ["role_id"])
    _safe_create_index("ix_stations_dealer_id", "stations", ["dealer_id"])
    _safe_create_index("ix_rentals_user_id", "rentals", ["user_id"])
    _safe_create_index("ix_rentals_start_station_id", "rentals", ["start_station_id"])
    _safe_create_index("ix_rentals_status", "rentals", ["status"])
    _safe_create_index("ix_rentals_created_at", "rentals", ["created_at"])
    _safe_create_index("ix_batteries_location_id_type", "batteries", ["location_id", "location_type"])
    _safe_create_index("ix_kyc_documents_user_id", "kyc_documents", ["user_id"])
    _safe_create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    _safe_create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    _safe_create_index("ix_user_roles_role_id", "user_roles", ["role_id"])
    _safe_create_index("ix_dealer_profiles_user_id", "dealer_profiles", ["user_id"])
    _safe_create_index("ix_commission_logs_dealer_id", "commission_logs", ["dealer_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for idx in [
        "ix_commission_logs_dealer_id",
        "ix_dealer_profiles_user_id",
        "ix_user_roles_role_id",
        "ix_user_roles_user_id",
        "ix_audit_logs_user_id",
        "ix_kyc_documents_user_id",
        "ix_batteries_location_id_type",
        "ix_rentals_created_at",
        "ix_rentals_status",
        "ix_rentals_start_station_id",
        "ix_rentals_user_id",
        "ix_stations_dealer_id",
        "ix_users_role_id",
    ]:
        try:
            with bind.begin_nested():
                op.drop_index(idx)
        except Exception:
            pass
