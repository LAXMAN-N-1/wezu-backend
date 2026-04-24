"""
Seed script: populate the permissions table with all standard WEZU admin modules.
Run from the backend/ directory:
    python scripts/seed_permissions.py
"""
from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.admin_user import AdminUser  # noqa: F401 – must be imported before AdminGroup mapper resolves
import app.models.all  # noqa: F401  – register all SQLModel mappers
from app.models.rbac import Permission

# Each entry: (slug, module, action, scope, description)
PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    # ── Dashboard ──────────────────────────────────────────────────────────
    ("dashboard:view:global",       "dashboard",       "view",    "global", "View admin dashboard & analytics"),

    # ── User Management ────────────────────────────────────────────────────
    ("users:view:global",           "users",           "view",    "global", "View all users"),
    ("users:create:global",         "users",           "create",  "global", "Create new users"),
    ("users:edit:global",           "users",           "edit",    "global", "Edit user details"),
    ("users:delete:global",         "users",           "delete",  "global", "Delete users"),
    ("users:suspend:global",        "users",           "suspend", "global", "Suspend / reactivate users"),
    ("users:export:global",         "users",           "export",  "global", "Export user data"),
    ("users:bulk_import:global",    "users",           "bulk_import", "global", "Bulk import users"),

    # ── Roles & Permissions ────────────────────────────────────────────────
    ("roles:view:global",           "roles",           "view",    "global", "View roles"),
    ("roles:create:global",         "roles",           "create",  "global", "Create custom roles"),
    ("roles:edit:global",           "roles",           "edit",    "global", "Edit role permissions"),
    ("roles:delete:global",         "roles",           "delete",  "global", "Delete roles"),
    ("roles:assign:global",         "roles",           "assign",  "global", "Assign roles to users"),

    # ── Fleet & Inventory (Batteries) ─────────────────────────────────────
    ("batteries:view:global",       "batteries",       "view",    "global", "View all batteries"),
    ("batteries:create:global",     "batteries",       "create",  "global", "Register new batteries"),
    ("batteries:edit:global",       "batteries",       "edit",    "global", "Edit battery details"),
    ("batteries:delete:global",     "batteries",       "delete",  "global", "Retire / delete batteries"),
    ("batteries:export:global",     "batteries",       "export",  "global", "Export battery data"),
    ("batteries:bulk_update:global","batteries",       "bulk_update","global","Bulk update battery status"),
    ("batteries:import:global",     "batteries",       "import",  "global", "Bulk import batteries via CSV"),

    # ── Stock Levels ───────────────────────────────────────────────────────
    ("stock:view:global",           "stock",           "view",    "global", "View stock levels across all stations"),
    ("stock:reorder:global",        "stock",           "reorder", "global", "Create reorder requests"),
    ("stock:config:global",         "stock",           "config",  "global", "Update station stock configuration"),
    ("stock:alerts:global",         "stock",           "alerts",  "global", "View & dismiss stock alerts"),

    # ── Stations ───────────────────────────────────────────────────────────
    ("stations:view:global",        "stations",        "view",    "global", "View all stations"),
    ("stations:create:global",      "stations",        "create",  "global", "Create new stations"),
    ("stations:edit:global",        "stations",        "edit",    "global", "Edit station details"),
    ("stations:delete:global",      "stations",        "delete",  "global", "Delete / deactivate stations"),
    ("stations:export:global",      "stations",        "export",  "global", "Export station data"),

    # ── Dealers ────────────────────────────────────────────────────────────
    ("dealers:view:global",         "dealers",         "view",    "global", "View all dealers"),
    ("dealers:create:global",       "dealers",         "create",  "global", "Onboard new dealers"),
    ("dealers:edit:global",         "dealers",         "edit",    "global", "Edit dealer details"),
    ("dealers:delete:global",       "dealers",         "delete",  "global", "Remove dealers"),
    ("dealers:approve:global",      "dealers",         "approve", "global", "Approve dealer applications"),

    # ── Rentals & Orders ───────────────────────────────────────────────────
    ("rentals:view:global",         "rentals",         "view",    "global", "View all rental orders"),
    ("rentals:manage:global",       "rentals",         "manage",  "global", "Manage / cancel rentals"),
    ("rentals:export:global",       "rentals",         "export",  "global", "Export rental data"),

    # ── Logistics ─────────────────────────────────────────────────────────
    ("logistics:view:global",       "logistics",       "view",    "global", "View logistics orders"),
    ("logistics:create:global",     "logistics",       "create",  "global", "Create logistics orders"),
    ("logistics:manage:global",     "logistics",       "manage",  "global", "Manage / dispatch logistics"),
    ("logistics:assign:global",     "logistics",       "assign",  "global", "Assign drivers to orders"),

    # ── Fleet Operations ───────────────────────────────────────────────────
    ("fleet_ops:view:global",       "fleet_ops",       "view",    "global", "View fleet operations & telematics"),
    ("fleet_ops:manage:global",     "fleet_ops",       "manage",  "global", "Manage fleet operations"),
    ("fleet_ops:alerts:global",     "fleet_ops",       "alerts",  "global", "View & respond to fleet alerts"),

    # ── Analytics ─────────────────────────────────────────────────────────
    ("analytics:view:global",       "analytics",       "view",    "global", "View analytics & reports"),
    ("analytics:export:global",     "analytics",       "export",  "global", "Export analytics data"),

    # ── Audit Logs ────────────────────────────────────────────────────────
    ("audit_logs:view:global",      "audit_logs",      "view",    "global", "View audit trail & access logs"),
    ("audit_logs:export:global",    "audit_logs",      "export",  "global", "Export audit logs"),

    # ── Finance ───────────────────────────────────────────────────────────
    ("finance:view:global",         "finance",         "view",    "global", "View financial reports & invoices"),
    ("finance:manage:global",       "finance",         "manage",  "global", "Manage payouts & settlements"),
    ("finance:export:global",       "finance",         "export",  "global", "Export financial data"),

    # ── Support ───────────────────────────────────────────────────────────
    ("support:view:global",         "support",         "view",    "global", "View support tickets"),
    ("support:manage:global",       "support",         "manage",  "global", "Manage & resolve support tickets"),

    # ── KYC ───────────────────────────────────────────────────────────────
    ("kyc:view:global",             "kyc",             "view",    "global", "View KYC submissions"),
    ("kyc:approve:global",          "kyc",             "approve", "global", "Approve / reject KYC documents"),

    # ── Notifications ─────────────────────────────────────────────────────
    ("notifications:view:global",   "notifications",   "view",    "global", "View notification campaigns"),
    ("notifications:create:global", "notifications",   "create",  "global", "Create & send notifications"),
    ("notifications:manage:global", "notifications",   "manage",  "global", "Manage notification settings"),

    # ── System Settings ───────────────────────────────────────────────────
    ("settings:view:global",        "settings",        "view",    "global", "View system settings"),
    ("settings:edit:global",        "settings",        "edit",    "global", "Edit system settings"),
    ("settings:maintenance:global", "settings",        "maintenance","global","Toggle maintenance mode"),

    # ── Admin Groups ──────────────────────────────────────────────────────
    ("admin_groups:view:global",    "admin_groups",    "view",    "global", "View admin groups"),
    ("admin_groups:manage:global",  "admin_groups",    "manage",  "global", "Manage admin groups & members"),
]


def seed(drop_existing: bool = False) -> None:
    with Session(engine) as db:
        existing_slugs: set[str] = {
            p.slug for p in db.exec(select(Permission)).all()
        }

        added = 0
        for slug, module, action, scope, description in PERMISSIONS:
            if slug in existing_slugs:
                continue
            perm = Permission(
                slug=slug,
                module=module,
                action=action,
                scope=scope,
                description=description,
            )
            db.add(perm)
            added += 1

        db.commit()
        print(f"✓ Seeded {added} permissions ({len(existing_slugs)} already existed).")


if __name__ == "__main__":
    seed()
