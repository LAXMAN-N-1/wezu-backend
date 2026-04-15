"""
RBAC hard-reset cutover script.

Implements:
1) pre-cutover backups
2) role/permission hard reset
3) user_roles rebuild
4) users.role_id active-role pointer rebuild
5) session revocation
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import inspect, text
from sqlmodel import Session

from app.core.database import engine


BACKUP_SUFFIX = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


ROLE_BLUEPRINTS = [
    {"name": "super_admin", "category": "platform", "level": 100, "parent": None},
    {"name": "operations_admin", "category": "platform", "level": 90, "parent": "super_admin"},
    {"name": "security_admin", "category": "platform", "level": 85, "parent": "operations_admin"},
    {"name": "finance_admin", "category": "platform", "level": 85, "parent": "operations_admin"},
    {"name": "support_manager", "category": "support", "level": 70, "parent": "operations_admin"},
    {"name": "support_agent", "category": "support", "level": 60, "parent": "support_manager"},
    {"name": "logistics_manager", "category": "logistics", "level": 70, "parent": "operations_admin"},
    {"name": "dispatcher", "category": "logistics", "level": 60, "parent": "logistics_manager"},
    {"name": "fleet_manager", "category": "logistics", "level": 60, "parent": "logistics_manager"},
    {"name": "warehouse_manager", "category": "logistics", "level": 55, "parent": "logistics_manager"},
    {"name": "driver", "category": "logistics", "level": 40, "parent": "dispatcher"},
    {"name": "dealer_owner", "category": "dealer", "level": 60, "parent": "operations_admin"},
    {"name": "dealer_manager", "category": "dealer", "level": 55, "parent": "dealer_owner"},
    {"name": "dealer_inventory_staff", "category": "dealer", "level": 45, "parent": "dealer_manager"},
    {"name": "dealer_finance_staff", "category": "dealer", "level": 45, "parent": "dealer_manager"},
    {"name": "dealer_support_staff", "category": "dealer", "level": 45, "parent": "dealer_manager"},
    {"name": "customer", "category": "customer", "level": 10, "parent": None},
]

MODULES = [
    "users",
    "roles",
    "dealers",
    "drivers",
    "stations",
    "batteries",
    "rentals",
    "swaps",
    "orders",
    "support",
    "finance",
    "logistics",
    "analytics",
    "profile",
    "favorites",
    "dealer_portal",
    "inventory",
    "stock",
    "warehouse",
    "manifests",
    "routes",
    "sessions",
    "settings",
    "security",
    "audit",
    "notifications",
    "wallet",
    "payments",
    "transactions",
    "settlements",
    "invoices",
    "customers",
    "campaigns",
    "kyc",
]
ACTION_SET = ["view", "create", "update", "delete", "assign", "approve", "export", "override"]
SCOPE_SET = ["own", "dealer", "region", "global"]

ROLE_MODULE_SCOPE = {
    "super_admin": (set(MODULES), set(SCOPE_SET), set(ACTION_SET)),
    "operations_admin": (set(MODULES), {"region", "global"}, {"view", "create", "update", "delete", "assign", "approve", "export"}),
    "security_admin": ({"security", "audit", "sessions", "users", "roles", "settings"}, {"global"}, {"view", "create", "update", "delete", "assign", "approve", "export", "override"}),
    "finance_admin": ({"finance", "payments", "wallet", "transactions", "settlements", "invoices", "analytics"}, {"dealer", "region", "global"}, {"view", "create", "update", "delete", "assign", "approve", "export"}),
    "support_manager": ({"support", "users", "notifications", "analytics"}, {"dealer", "region", "global"}, {"view", "create", "update", "assign", "approve", "export"}),
    "support_agent": ({"support", "notifications", "customers"}, {"own", "dealer", "region"}, {"view", "create", "update"}),
    "logistics_manager": ({"logistics", "orders", "manifests", "routes", "warehouse", "inventory", "drivers", "analytics", "stock"}, {"dealer", "region", "global"}, {"view", "create", "update", "delete", "assign", "approve", "export"}),
    "dispatcher": ({"logistics", "orders", "routes", "drivers", "manifests"}, {"dealer", "region"}, {"view", "create", "update", "assign", "approve"}),
    "fleet_manager": ({"logistics", "orders", "drivers", "routes"}, {"dealer", "region"}, {"view", "create", "update", "assign"}),
    "warehouse_manager": ({"warehouse", "inventory", "stock", "logistics", "orders"}, {"dealer", "region"}, {"view", "create", "update", "assign", "approve"}),
    "driver": ({"orders", "logistics", "manifests", "routes"}, {"own", "dealer"}, {"view", "update"}),
    "dealer_owner": ({"dealer_portal", "stations", "inventory", "customers", "campaigns", "analytics", "support", "finance"}, {"own", "dealer"}, {"view", "create", "update", "delete", "assign", "approve", "export"}),
    "dealer_manager": ({"dealer_portal", "stations", "inventory", "customers", "campaigns", "analytics", "support"}, {"own", "dealer"}, {"view", "create", "update", "assign", "approve"}),
    "dealer_inventory_staff": ({"inventory", "stations", "stock", "dealer_portal"}, {"own", "dealer"}, {"view", "create", "update"}),
    "dealer_finance_staff": ({"finance", "payments", "wallet", "dealer_portal"}, {"own", "dealer"}, {"view", "create", "update", "approve", "export"}),
    "dealer_support_staff": ({"support", "customers", "dealer_portal", "notifications"}, {"own", "dealer"}, {"view", "create", "update"}),
    "customer": ({"profile", "stations", "rentals", "wallet", "payments", "notifications", "support", "favorites"}, {"own"}, {"view", "create", "update"}),
}


def _table_exists(session: Session, table_name: str) -> bool:
    return inspect(session.connection()).has_table(table_name)


def _add_roles_columns_if_missing(session: Session) -> None:
    cols = {col["name"] for col in inspect(session.connection()).get_columns("roles")}
    if "is_custom_role" not in cols:
        session.exec(text("ALTER TABLE roles ADD COLUMN is_custom_role BOOLEAN DEFAULT FALSE"))
    if "scope_owner" not in cols:
        session.exec(text("ALTER TABLE roles ADD COLUMN scope_owner VARCHAR DEFAULT 'global'"))
    session.commit()


def _backup_tables(session: Session) -> None:
    for table_name in ("roles", "permissions", "role_permissions", "user_roles", "admin_user_roles"):
        if not _table_exists(session, table_name):
            continue
        backup_name = f"{table_name}_backup_{BACKUP_SUFFIX}"
        session.exec(text(f"CREATE TABLE IF NOT EXISTS {backup_name} AS SELECT * FROM {table_name}"))
    session.commit()


def _truncate_rbac(session: Session) -> None:
    session.exec(text("UPDATE users SET role_id = NULL"))
    if _table_exists(session, "admin_user_roles"):
        session.exec(text("DELETE FROM admin_user_roles"))
    if _table_exists(session, "user_roles"):
        session.exec(text("DELETE FROM user_roles"))
    if _table_exists(session, "role_permissions"):
        session.exec(text("DELETE FROM role_permissions"))
    if _table_exists(session, "permissions"):
        session.exec(text("DELETE FROM permissions"))
    if _table_exists(session, "roles"):
        session.exec(text("DELETE FROM roles"))
    session.commit()


def _seed_roles(session: Session) -> dict[str, int]:
    role_ids: dict[str, int] = {}
    for role in ROLE_BLUEPRINTS:
        session.exec(
            text(
                """
                INSERT INTO roles (name, description, category, level, parent_id, is_system_role, is_custom_role, is_active, scope_owner, dealer_id, icon, color, created_at, updated_at)
                VALUES (:name, :description, :category, :level, NULL, TRUE, FALSE, TRUE, 'global', NULL, 'shield', '#4CAF50', :now, :now)
                """
            ),
            {
                "name": role["name"],
                "description": f"{role['name'].replace('_', ' ').title()} preset role",
                "category": role["category"],
                "level": role["level"],
                "now": datetime.now(UTC),
            },
        )
    session.commit()

    rows = session.exec(text("SELECT id, name FROM roles")).all()
    role_ids = {row.name: row.id for row in rows}
    for role in ROLE_BLUEPRINTS:
        parent = role["parent"]
        if parent:
            session.exec(
                text("UPDATE roles SET parent_id = :parent_id WHERE name = :name"),
                {"name": role["name"], "parent_id": role_ids[parent]},
            )
    session.commit()
    return role_ids


def _seed_permissions(session: Session) -> dict[str, int]:
    permission_ids: dict[str, int] = {}
    now = datetime.now(UTC)
    for module in MODULES:
        for action in ACTION_SET:
            for scope in SCOPE_SET:
                slug = f"{module}:{action}:{scope}"
                session.exec(
                    text(
                        """
                        INSERT INTO permissions (slug, module, resource_type, action, scope, constraints, description)
                        VALUES (:slug, :module, :resource_type, :action, :scope, NULL, :description)
                        """
                    ),
                    {
                        "slug": slug,
                        "module": module,
                        "resource_type": module,
                        "action": action,
                        "scope": scope,
                        "description": f"{action.title()} {module} ({scope})",
                    },
                )
    session.commit()
    rows = session.exec(text("SELECT id, slug FROM permissions")).all()
    permission_ids = {row.slug: row.id for row in rows}
    return permission_ids


def _seed_role_permissions(session: Session, role_ids: dict[str, int], permission_ids: dict[str, int]) -> None:
    for role_name, (modules, scopes, actions) in ROLE_MODULE_SCOPE.items():
        role_id = role_ids.get(role_name)
        if not role_id:
            continue
        for module in modules:
            for action in actions:
                for scope in scopes:
                    slug = f"{module}:{action}:{scope}"
                    permission_id = permission_ids.get(slug)
                    if not permission_id:
                        continue
                    session.exec(
                        text(
                            "INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :permission_id)"
                        ),
                        {"role_id": role_id, "permission_id": permission_id},
                    )
    session.commit()


def _default_role_name_for_user(user_type: str | None, is_superuser: bool) -> str:
    if is_superuser:
        return "super_admin"
    mapping = {
        "ADMIN": "operations_admin",
        "DEALER": "dealer_owner",
        "DEALER_STAFF": "dealer_manager",
        "SUPPORT_AGENT": "support_agent",
        "LOGISTICS": "logistics_manager",
        "CUSTOMER": "customer",
    }
    return mapping.get((user_type or "CUSTOMER").upper(), "customer")


def _rebuild_user_roles(session: Session, role_ids: dict[str, int]) -> None:
    now = datetime.now(UTC)
    users = session.exec(text("SELECT id, user_type, is_superuser FROM users")).all()
    for row in users:
        role_name = _default_role_name_for_user(row.user_type, bool(row.is_superuser))
        role_id = role_ids.get(role_name)
        if not role_id:
            continue
        session.exec(
            text(
                """
                INSERT INTO user_roles (user_id, role_id, assigned_by, notes, effective_from, expires_at, created_at)
                VALUES (:user_id, :role_id, NULL, :notes, :effective_from, NULL, :created_at)
                """
            ),
            {
                "user_id": row.id,
                "role_id": role_id,
                "notes": "RBAC hard-reset assignment",
                "effective_from": now,
                "created_at": now,
            },
        )
    session.commit()

    session.exec(
        text(
            """
            UPDATE users u
            SET role_id = ur.role_id
            FROM user_roles ur
            WHERE ur.user_id = u.id
              AND ur.effective_from <= :now
              AND (ur.expires_at IS NULL OR ur.expires_at >= :now)
            """
        ),
        {"now": now},
    )
    session.commit()


def _revoke_sessions(session: Session) -> None:
    if _table_exists(session, "user_sessions"):
        session.exec(text("UPDATE user_sessions SET is_active = FALSE WHERE is_active = TRUE"))
    if _table_exists(session, "session_tokens"):
        session.exec(text("UPDATE session_tokens SET is_active = FALSE WHERE is_active = TRUE"))
    session.commit()


def _verify_integrity(session: Session) -> None:
    active_users = session.exec(text("SELECT COUNT(*) AS count FROM users WHERE status = 'ACTIVE'")).one().count
    active_user_roles = session.exec(
        text(
            """
            SELECT COUNT(DISTINCT ur.user_id) AS count
            FROM user_roles ur
            WHERE ur.effective_from <= :now
              AND (ur.expires_at IS NULL OR ur.expires_at >= :now)
            """
        ),
        {"now": datetime.now(UTC)},
    ).one().count
    print(f"ACTIVE_USERS={active_users}")
    print(f"ACTIVE_USER_ROLE_LINKS={active_user_roles}")


def run() -> None:
    with Session(engine) as session:
        print("Starting RBAC hard reset...")
        _add_roles_columns_if_missing(session)
        _backup_tables(session)
        _truncate_rbac(session)
        role_ids = _seed_roles(session)
        permission_ids = _seed_permissions(session)
        _seed_role_permissions(session, role_ids, permission_ids)
        _rebuild_user_roles(session, role_ids)
        _revoke_sessions(session)
        _verify_integrity(session)
        print("RBAC hard reset complete.")


if __name__ == "__main__":
    run()
