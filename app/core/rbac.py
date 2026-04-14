from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable


CANONICAL_PERMISSION_ACTIONS = {
    "view",
    "create",
    "update",
    "delete",
    "assign",
    "approve",
    "export",
    "override",
}

CANONICAL_PERMISSION_SCOPES = {"own", "dealer", "region", "global"}


ROLE_NAME_ALIASES = {
    "admin": "operations_admin",
    "dealer": "dealer_owner",
    "dealer_staff": "dealer_manager",
    "vendor_owner": "dealer_owner",
    "logistics": "logistics_manager",
    "operator": "dispatcher",
    "dispatch": "dispatcher",
    "superadmin": "super_admin",
}


def canonical_role_name(role_name: str | None) -> str:
    if not role_name:
        return ""
    cleaned = role_name.strip().lower()
    return ROLE_NAME_ALIASES.get(cleaned, cleaned)


def canonicalize_permission_slug(permission_slug: str | None) -> str:
    """
    Canonical slug format: module:action:scope
    Legacy aliases:
    - module:read -> module:view:global
    - module:action -> module:action:global
    - module:action:all -> module:action:global
    """
    if not permission_slug:
        return ""

    raw = permission_slug.strip().lower()
    if not raw:
        return ""

    parts = raw.split(":")
    if len(parts) == 1:
        return raw

    module = parts[0]
    action = parts[1]
    scope = parts[2] if len(parts) > 2 else "global"

    if action == "read":
        action = "view"
    elif action == "edit":
        action = "update"

    if scope == "all":
        scope = "global"

    # Keep unknown action/scope as-is to avoid destructive rejection paths.
    return f"{module}:{action}:{scope}"


def canonicalize_permission_set(permissions: Iterable[str]) -> set[str]:
    return {slug for slug in (canonicalize_permission_slug(p) for p in permissions) if slug}


def role_sort_key(role_name: str | None) -> tuple[int, str]:
    order = {
        "super_admin": 0,
        "operations_admin": 1,
        "security_admin": 2,
        "finance_admin": 3,
        "support_manager": 4,
        "support_agent": 5,
        "logistics_manager": 6,
        "dispatcher": 7,
        "fleet_manager": 8,
        "warehouse_manager": 9,
        "dealer_owner": 10,
        "dealer_manager": 11,
        "dealer_inventory_staff": 12,
        "dealer_finance_staff": 13,
        "dealer_support_staff": 14,
        "driver": 15,
        "customer": 16,
    }
    canonical = canonical_role_name(role_name)
    return (order.get(canonical, 999), canonical)


@dataclass(frozen=True)
class RoleWindow:
    effective_from: datetime | None
    expires_at: datetime | None

    def is_active(self, now: datetime | None = None) -> bool:
        at = now or datetime.now(UTC)
        if self.effective_from and self.effective_from > at:
            return False
        if self.expires_at and self.expires_at < at:
            return False
        return True
