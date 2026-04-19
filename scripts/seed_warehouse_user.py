"""
Create or repair the warehouse logistics login in local/dev databases.

Usage:
    cd backend
    python -m scripts.seed_warehouse_user

This script is idempotent and does all of the following:
1) Ensures `warehouse_manager` role exists and is active.
2) Ensures the role has core logistics permissions (orders/battery/warehouse/inventory).
3) Creates or updates `warehouse@wezu.com` with `user_type=LOGISTICS`.
4) Ensures `user.role_id` and `user_roles` both point to `warehouse_manager`.
"""
import os
import sys
from datetime import UTC, datetime

# Ensure the backend root is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import Session, select

from app.core.security import get_password_hash
from app.db.session import engine
from app.models.all import *  # noqa: F401,F403 - force mapper registration
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User, UserStatus, UserType

# ── Configuration ──────────────────────────────────────────────────────────────
EMAIL = "warehouse@wezu.com"
PASSWORD = "wezutech123"
FULL_NAME = "Bindu"
PHONE = "9000000001"
ROLE_NAME = "warehouse_manager"


REQUIRED_ROLE_PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    ("battery:view:global", "battery", "view", "global", "Read battery inventory"),
    ("battery:update:global", "battery", "update", "global", "Update battery lifecycle"),
    ("orders:view:global", "orders", "view", "global", "View logistics orders"),
    ("orders:create:global", "orders", "create", "global", "Create logistics orders"),
    ("orders:update:global", "orders", "update", "global", "Update logistics orders"),
    ("warehouse:view:global", "warehouse", "view", "global", "View warehouse structures"),
    ("warehouse:update:global", "warehouse", "update", "global", "Manage warehouse structures"),
    ("inventory:view:global", "inventory", "view", "global", "View logistics inventory"),
    ("inventory:update:global", "inventory", "update", "global", "Manage logistics inventory"),
    ("logistics:view:global", "logistics", "view", "global", "View logistics operations"),
    ("drivers:view:global", "drivers", "view", "global", "View fleet driver data"),
]


def _ensure_role(db: Session) -> Role:
    role = db.exec(select(Role).where(Role.name == ROLE_NAME)).first()
    if role is None:
        role = Role(
            name=ROLE_NAME,
            description="Warehouse/Logistics Manager",
            category="logistics",
            level=55,
            is_system_role=True,
            is_active=True,
            scope_owner="global",
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        print(f"✅ Created role: {role.name} (ID={role.id})")
        return role

    updated = False
    if not role.is_active:
        role.is_active = True
        updated = True
    if role.category != "logistics":
        role.category = "logistics"
        updated = True
    if role.level < 55:
        role.level = 55
        updated = True
    if updated:
        db.add(role)
        db.commit()
        db.refresh(role)
        print(f"✅ Updated role metadata: {role.name} (ID={role.id})")
    else:
        print(f"✅ Role exists: {role.name} (ID={role.id})")
    return role


def _ensure_role_permissions(db: Session, role: Role) -> None:
    ensured = 0
    linked = 0
    for slug, module, action, scope, description in REQUIRED_ROLE_PERMISSIONS:
        permission = db.exec(select(Permission).where(Permission.slug == slug)).first()
        if permission is None:
            permission = Permission(
                slug=slug,
                module=module,
                action=action,
                scope=scope,
                description=description,
            )
            db.add(permission)
            db.commit()
            db.refresh(permission)
            ensured += 1

        link = db.exec(
            select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == permission.id,
            )
        ).first()
        if link is None:
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
            db.commit()
            linked += 1

    if ensured:
        print(f"✅ Created {ensured} missing permissions")
    if linked:
        print(f"✅ Linked {linked} permissions to role '{role.name}'")
    if not ensured and not linked:
        print(f"✅ Role '{role.name}' already has required permissions")


def _ensure_user(db: Session, role: Role) -> User:
    user = db.exec(select(User).where(User.email == EMAIL)).first()
    created = False
    if user is None:
        user = User(
            email=EMAIL,
            hashed_password=get_password_hash(PASSWORD),
            full_name=FULL_NAME,
            phone_number=PHONE,
            status=UserStatus.ACTIVE,
            user_type=UserType.LOGISTICS,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        created = True
        print(f"✅ Created warehouse user: {user.email} (ID={user.id})")
    else:
        user.full_name = FULL_NAME
        if not user.phone_number:
            user.phone_number = PHONE
        user.status = UserStatus.ACTIVE
        user.user_type = UserType.LOGISTICS
        user.role_id = role.id
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✅ Updated warehouse user: {user.email} (ID={user.id})")

    role_link = db.exec(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
        )
    ).first()
    if role_link is None:
        db.add(
            UserRole(
                user_id=user.id,
                role_id=role.id,
                effective_from=datetime.now(UTC),
            )
        )
        db.commit()
        print(f"✅ Linked user to role via user_roles: {role.name}")

    if created:
        print(f"\n🔑 Login credentials:")
        print(f"   Email:    {EMAIL}")
        print(f"   Password: {PASSWORD}")
    else:
        print(f"\n🔑 Login credentials (unchanged):")
        print(f"   Email:    {EMAIL}")
        print(f"   Password: {PASSWORD} (reset manually if needed)")

    return user


def seed() -> None:
    with Session(engine) as db:
        role = _ensure_role(db)
        _ensure_role_permissions(db, role)
        _ensure_user(db, role)
        print("\n✅ Warehouse logistics seed completed.")


if __name__ == "__main__":
    seed()
