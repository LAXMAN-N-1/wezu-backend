from __future__ import annotations
"""
Seed a default warehouse manager login for the Wezu Logistics app.

Idempotent behavior:
- creates `warehouse_manager` role if missing
- creates/updates warehouse manager user by email
- ensures `users.role_id` points to warehouse_manager
- ensures `user_roles` contains the same assignment
- ensures role has required logistics app permissions
- ensures at least one active warehouse/rack/shelf exists

Usage:
    cd backend
    python app/db/seeds/seed_logistics_warehouse_manager.py

Optional env overrides:
    WEZU_WAREHOUSE_MANAGER_EMAIL
    WEZU_WAREHOUSE_MANAGER_PASSWORD
    WEZU_WAREHOUSE_MANAGER_PHONE
    WEZU_WAREHOUSE_MANAGER_NAME
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select


BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.security import get_password_hash
from app.core.rbac import canonicalize_permission_slug
from app.core.database import ensure_warehouses_schema_compatibility
from app.db.session import engine
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User, UserStatus, UserType
from app.models.warehouse import Rack, Shelf, Warehouse
import app.models.all  # noqa: F401  # Ensure SQLAlchemy relationships are fully registered.


UTC = timezone.utc
ROLE_NAME = "warehouse_manager"
DEFAULT_EMAIL = "warehouse@wezu.com"
DEFAULT_PASSWORD = "wezutech123"
DEFAULT_PHONE = "9000000510"
DEFAULT_NAME = "Bindu"
REQUIRED_PERMISSION_SLUGS = (
    "battery:view:global",
    "orders:view:global",
    "warehouse:view:global",
    "inventory:view:global",
    "station:view:global",
)
DEFAULT_WAREHOUSE_CODE = "WZU-WH-001"


def _credentials() -> tuple[str, str, Optional[str], str]:
    email = os.getenv("WEZU_WAREHOUSE_MANAGER_EMAIL", DEFAULT_EMAIL).strip().lower()
    password = os.getenv("WEZU_WAREHOUSE_MANAGER_PASSWORD", DEFAULT_PASSWORD)
    phone = os.getenv("WEZU_WAREHOUSE_MANAGER_PHONE", DEFAULT_PHONE).strip() or None
    full_name = os.getenv("WEZU_WAREHOUSE_MANAGER_NAME", DEFAULT_NAME).strip() or DEFAULT_NAME
    return email, password, phone, full_name


def _ensure_role(session: Session) -> Role:
    role = session.exec(select(Role).where(Role.name == ROLE_NAME)).first()
    if role:
        changed = False
        if role.category != "logistics":
            role.category = "logistics"
            changed = True
        if role.level < 55:
            role.level = 55
            changed = True
        if not role.is_active:
            role.is_active = True
            changed = True
        if role.scope_owner != "global":
            role.scope_owner = "global"
            changed = True
        if changed:
            session.add(role)
            session.commit()
            session.refresh(role)
            print(f"✅ Updated role '{ROLE_NAME}' (id={role.id})")
        else:
            print(f"✅ Role '{ROLE_NAME}' already exists (id={role.id})")
        return role

    role = Role(
        name=ROLE_NAME,
        description="Warehouse operations role for logistics app.",
        category="logistics",
        level=55,
        is_system_role=True,
        is_custom_role=False,
        is_active=True,
        scope_owner="global",
    )
    session.add(role)
    session.commit()
    session.refresh(role)
    print(f"✅ Created role '{ROLE_NAME}' (id={role.id})")
    return role


def _resolve_phone(session: Session, target_email: str, requested_phone: Optional[str]) -> Optional[str]:
    if not requested_phone:
        return None
    existing_phone_owner = session.exec(
        select(User).where(User.phone_number == requested_phone)
    ).first()
    if existing_phone_owner and (existing_phone_owner.email or "").strip().lower() != target_email:
        print(
            f"⚠ Requested phone '{requested_phone}' is already used by "
            f"user id={existing_phone_owner.id}. Seeding without phone."
        )
        return None
    return requested_phone


def _upsert_user(
    session: Session,
    role: Role,
    email: str,
    password: str,
    phone: Optional[str],
    full_name: str,
) -> User:
    user = session.exec(select(User).where(User.email == email)).first()
    safe_phone = _resolve_phone(session, email, phone)
    hashed_password = get_password_hash(password)

    if user:
        user.full_name = full_name
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        user.user_type = UserType.LOGISTICS
        user.role_id = role.id
        user.is_deleted = False
        user.deleted_at = None
        user.deletion_reason = None
        if safe_phone is not None:
            user.phone_number = safe_phone
        user.updated_at = datetime.now(UTC)
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"✅ Updated warehouse manager user (id={user.id}, email={email})")
    else:
        user = User(
            email=email,
            phone_number=safe_phone,
            full_name=full_name,
            hashed_password=hashed_password,
            user_type=UserType.LOGISTICS,
            status=UserStatus.ACTIVE,
            role_id=role.id,
            is_superuser=False,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"✅ Created warehouse manager user (id={user.id}, email={email})")

    return user


def _ensure_user_role_mapping(session: Session, user: User, role: Role) -> None:
    mapping = session.exec(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
        )
    ).first()
    if mapping:
        print("✅ user_roles mapping already present")
        return

    now = datetime.now(UTC)
    mapping = UserRole(
        user_id=user.id,
        role_id=role.id,
        created_at=now,
        effective_from=now,
        notes="Seeded by seed_logistics_warehouse_manager.py",
    )
    session.add(mapping)
    session.commit()
    print("✅ Created user_roles mapping")


def _ensure_role_permissions(session: Session, role: Role) -> None:
    linked_slugs: list[str] = []
    for raw_slug in REQUIRED_PERMISSION_SLUGS:
        slug = canonicalize_permission_slug(raw_slug)
        parts = slug.split(":")
        module = parts[0] if len(parts) > 0 else slug
        action = parts[1] if len(parts) > 1 else "view"
        scope = parts[2] if len(parts) > 2 else "global"

        permission = session.exec(
            select(Permission).where(Permission.slug == slug)
        ).first()
        if not permission:
            permission = Permission(
                slug=slug,
                module=module,
                action=action,
                scope=scope,
                resource_type=module,
                description=f"Seeded permission for {ROLE_NAME} login access",
            )
            session.add(permission)
            session.commit()
            session.refresh(permission)
            print(f"✅ Created permission '{slug}'")

        mapping = session.exec(
            select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == permission.id,
            )
        ).first()
        if not mapping:
            session.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=permission.id,
                )
            )
            session.commit()
            print(f"✅ Linked permission '{slug}' to role '{ROLE_NAME}'")
        linked_slugs.append(slug)

    if linked_slugs:
        print(f"✅ Role permissions verified: {', '.join(linked_slugs)}")


def _ensure_default_warehouse_structure(session: Session, manager_user: User) -> None:
    warehouse = session.exec(
        select(Warehouse).where(Warehouse.code == DEFAULT_WAREHOUSE_CODE)
    ).first()
    if not warehouse:
        warehouse = session.exec(
            select(Warehouse).where(Warehouse.is_active == True).order_by(Warehouse.id.asc())
        ).first()

    if warehouse:
        changed = False
        if not warehouse.is_active:
            warehouse.is_active = True
            changed = True
        if manager_user.id is not None and warehouse.manager_id != manager_user.id:
            warehouse.manager_id = manager_user.id
            changed = True
        if changed:
            warehouse.updated_at = datetime.now(UTC)
            session.add(warehouse)
            session.commit()
            session.refresh(warehouse)
            print(f"✅ Updated warehouse '{warehouse.code}' (id={warehouse.id})")
        else:
            print(f"✅ Warehouse exists '{warehouse.code}' (id={warehouse.id})")
    else:
        warehouse = Warehouse(
            name="Wezu Central Warehouse",
            code=DEFAULT_WAREHOUSE_CODE,
            address="Seed Logistics Hub",
            city="Bengaluru",
            state="Karnataka",
            pincode="560001",
            manager_id=manager_user.id,
            capacity=300,
            is_active=True,
        )
        session.add(warehouse)
        session.commit()
        session.refresh(warehouse)
        print(f"✅ Created warehouse '{warehouse.code}' (id={warehouse.id})")

    rack = session.exec(
        select(Rack).where(Rack.warehouse_id == warehouse.id).order_by(Rack.id.asc())
    ).first()
    if not rack:
        rack = Rack(warehouse_id=warehouse.id, name="Rack A")
        session.add(rack)
        session.commit()
        session.refresh(rack)
        print(f"✅ Created default rack (id={rack.id})")
    else:
        print(f"✅ Rack exists (id={rack.id})")

    shelf = session.exec(
        select(Shelf).where(Shelf.rack_id == rack.id).order_by(Shelf.id.asc())
    ).first()
    if not shelf:
        shelf = Shelf(rack_id=rack.id, name="Shelf A1", capacity=50)
        session.add(shelf)
        session.commit()
        session.refresh(shelf)
        print(f"✅ Created default shelf (id={shelf.id})")
    else:
        print(f"✅ Shelf exists (id={shelf.id})")


def seed() -> None:
    email, password, phone, full_name = _credentials()
    ensure_warehouses_schema_compatibility()

    with Session(engine) as session:
        role = _ensure_role(session)
        user = _upsert_user(session, role, email, password, phone, full_name)
        _ensure_user_role_mapping(session, user, role)
        _ensure_role_permissions(session, role)
        _ensure_default_warehouse_structure(session, user)

        print("\nSeed summary:")
        print(f"  role: {ROLE_NAME} (id={role.id})")
        print(f"  user_id: {user.id}")
        print(f"  email: {email}")
        print(f"  password: {password}")
        print(f"  phone: {user.phone_number or '(none)'}")


if __name__ == "__main__":
    seed()
