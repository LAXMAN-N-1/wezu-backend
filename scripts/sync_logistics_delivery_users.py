"""
Synchronize logistics and delivery app login users for local/dev environments.

What this script enforces:
1) Removes legacy warehouse login `warehouse.manager@seed.wezu.energy`.
2) Ensures warehouse manager user is:
   - email: warehouse@wezu.com
   - password: wezutech123
   - name: Bindu
3) Ensures delivery partner user is:
   - phone: 7997297384
   - name: Ammulu
   - role: driver
   - driver profile present
4) Removes legacy OTP `964056` for the delivery partner target.

Usage:
    cd backend
    python -m scripts.sync_logistics_delivery_users
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from sqlalchemy import delete, func
from sqlmodel import Session, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import ensure_warehouses_schema_compatibility
from app.core.rbac import canonicalize_permission_slug
from app.core.security import get_password_hash
from app.db.seeds.seed_logistics_warehouse_manager import seed as seed_warehouse_manager
from app.db.session import engine
from app.models.driver_profile import DriverProfile
from app.models.otp import OTP
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.session import UserSession
from app.models.token import SessionToken
from app.models.user import User, UserStatus, UserType
from app.models.warehouse import Rack, Shelf, Warehouse


UTC = timezone.utc

LEGACY_WAREHOUSE_EMAIL = "warehouse.manager@seed.wezu.energy"

WAREHOUSE_EMAIL = "warehouse@wezu.com"
WAREHOUSE_PASSWORD = "wezutech123"
WAREHOUSE_NAME = "Bindu"

DELIVERY_NAME = "Ammulu"
DELIVERY_PHONE = "7997297384"
DELIVERY_LEGACY_OTP = "964056"

DRIVER_ROLE_NAME = "driver"
DRIVER_PERMISSION_SLUGS = (
    "logistics:view:global",
    "orders:view:global",
    "orders:update:global",
)
DEFAULT_DRIVER_LICENSE = "DL-WEZU-AMMULU-001"
DEFAULT_DRIVER_VEHICLE_TYPE = "e-bike"
DEFAULT_DRIVER_VEHICLE_PLATE = "TS09WEZU1234"


def _normalize_phone(raw: str | None) -> str:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    return digits


def _ensure_driver_role(session: Session) -> Role:
    role = session.exec(select(Role).where(Role.name == DRIVER_ROLE_NAME)).first()
    if role is None:
        role = Role(
            name=DRIVER_ROLE_NAME,
            description="Delivery driver role",
            category="logistics",
            level=40,
            is_system_role=True,
            is_active=True,
            scope_owner="global",
        )
        session.add(role)
        session.commit()
        session.refresh(role)
        print(f"Created role: {DRIVER_ROLE_NAME} (id={role.id})")
    return role


def _ensure_role_permissions(
    session: Session,
    role: Role,
    permission_slugs: tuple[str, ...],
) -> None:
    for raw_slug in permission_slugs:
        slug = canonicalize_permission_slug(raw_slug)
        module, action, scope = (slug.split(":") + ["view", "global"])[:3]

        permission = session.exec(select(Permission).where(Permission.slug == slug)).first()
        if permission is None:
            permission = Permission(
                slug=slug,
                module=module,
                action=action,
                scope=scope,
                resource_type=module,
                description=f"Seeded permission for {role.name}",
            )
            session.add(permission)
            session.commit()
            session.refresh(permission)

        mapping = session.exec(
            select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == permission.id,
            )
        ).first()
        if mapping is None:
            session.add(RolePermission(role_id=role.id, permission_id=permission.id))
            session.commit()


def _ensure_user_role(session: Session, user: User, role: Role) -> None:
    mapping = session.exec(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
        )
    ).first()
    if mapping is None:
        session.add(
            UserRole(
                user_id=user.id,
                role_id=role.id,
                effective_from=datetime.now(UTC),
                notes="Synced by sync_logistics_delivery_users.py",
            )
        )
        session.commit()


def _cleanup_legacy_user(session: Session, email: str) -> None:
    legacy = session.exec(
        select(User).where(func.lower(User.email) == email.lower())
    ).first()
    if legacy is None:
        return

    try:
        session.exec(delete(UserRole).where(UserRole.user_id == legacy.id))
        session.exec(delete(UserSession).where(UserSession.user_id == legacy.id))
        session.exec(delete(SessionToken).where(SessionToken.user_id == legacy.id))
        session.exec(delete(DriverProfile).where(DriverProfile.user_id == legacy.id))
        session.delete(legacy)
        session.commit()
        print(f"Deleted legacy user: {email}")
    except Exception:
        session.rollback()
        # Fallback to secure soft-delete when hard delete is blocked by FK constraints.
        legacy.status = UserStatus.DELETED
        legacy.is_deleted = True
        legacy.deleted_at = datetime.now(UTC)
        legacy.deletion_reason = "Replaced by warehouse@wezu.com"
        legacy.hashed_password = None
        legacy.email = f"deleted+{legacy.id}@wezu.local"
        legacy.phone_number = None
        session.add(legacy)
        session.commit()
        print(f"Soft-deleted legacy user (FK-protected): {email}")


def _ensure_warehouse_manager_user(session: Session) -> User:
    user = session.exec(
        select(User).where(func.lower(User.email) == WAREHOUSE_EMAIL.lower())
    ).first()
    hashed = get_password_hash(WAREHOUSE_PASSWORD)
    if user is None:
        user = User(
            email=WAREHOUSE_EMAIL,
            full_name=WAREHOUSE_NAME,
            hashed_password=hashed,
            user_type=UserType.LOGISTICS,
            status=UserStatus.ACTIVE,
            is_superuser=False,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    else:
        user.full_name = WAREHOUSE_NAME
        user.hashed_password = hashed
        user.user_type = UserType.LOGISTICS
        user.status = UserStatus.ACTIVE
        user.is_deleted = False
        user.deleted_at = None
        user.deletion_reason = None
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def _ensure_delivery_driver_user(session: Session, role: Role) -> User:
    target_phone = _normalize_phone(DELIVERY_PHONE)
    user = session.exec(select(User).where(User.phone_number == target_phone)).first()
    if user is None:
        user = User(
            phone_number=target_phone,
            full_name=DELIVERY_NAME,
            user_type=UserType.LOGISTICS,
            status=UserStatus.ACTIVE,
            role_id=role.id,
            is_superuser=False,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"Created delivery partner user phone={target_phone} id={user.id}")
    else:
        user.full_name = DELIVERY_NAME
        user.user_type = UserType.LOGISTICS
        user.status = UserStatus.ACTIVE
        user.role_id = role.id
        user.is_deleted = False
        user.deleted_at = None
        user.deletion_reason = None
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"Updated delivery partner user phone={target_phone} id={user.id}")

    _ensure_user_role(session, user, role)

    profile = session.exec(
        select(DriverProfile).where(DriverProfile.user_id == user.id)
    ).first()
    if profile is None:
        profile = DriverProfile(
            user_id=user.id,
            name=DELIVERY_NAME,
            phone_number=target_phone,
            status="active",
            license_number=DEFAULT_DRIVER_LICENSE,
            vehicle_type=DEFAULT_DRIVER_VEHICLE_TYPE,
            vehicle_plate=DEFAULT_DRIVER_VEHICLE_PLATE,
            is_online=False,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        print(f"Created driver profile id={profile.id} for user_id={user.id}")
    else:
        profile.name = DELIVERY_NAME
        profile.phone_number = target_phone
        profile.status = "active"
        if not profile.license_number:
            profile.license_number = DEFAULT_DRIVER_LICENSE
        if not profile.vehicle_type:
            profile.vehicle_type = DEFAULT_DRIVER_VEHICLE_TYPE
        if not profile.vehicle_plate:
            profile.vehicle_plate = DEFAULT_DRIVER_VEHICLE_PLATE
        session.add(profile)
        session.commit()
        session.refresh(profile)

    return user


def _ensure_default_warehouse(session: Session, manager_user: User) -> None:
    warehouse = session.exec(
        select(Warehouse)
        .where(Warehouse.is_active == True)
        .order_by(Warehouse.id.asc())
    ).first()
    if warehouse is None:
        warehouse = Warehouse(
            name="Wezu Central Warehouse",
            code="WZU-WH-001",
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
        print(f"Created default warehouse id={warehouse.id}")
    else:
        if manager_user.id is not None:
            warehouse.manager_id = manager_user.id
        warehouse.is_active = True
        session.add(warehouse)
        session.commit()
        session.refresh(warehouse)

    rack = session.exec(
        select(Rack).where(Rack.warehouse_id == warehouse.id).order_by(Rack.id.asc())
    ).first()
    if rack is None:
        rack = Rack(warehouse_id=warehouse.id, name="Rack A")
        session.add(rack)
        session.commit()
        session.refresh(rack)

    shelf = session.exec(
        select(Shelf).where(Shelf.rack_id == rack.id).order_by(Shelf.id.asc())
    ).first()
    if shelf is None:
        shelf = Shelf(rack_id=rack.id, name="Shelf A1", capacity=50)
        session.add(shelf)
        session.commit()


def _cleanup_legacy_otps(session: Session) -> None:
    normalized_phone = _normalize_phone(DELIVERY_PHONE)
    candidate_targets = {
        normalized_phone,
        f"+91{normalized_phone}",
        f"91{normalized_phone}",
    }

    # Remove the previously shared OTP requested in the bug report.
    session.exec(
        delete(OTP).where(
            OTP.target.in_(candidate_targets),
            OTP.code == DELIVERY_LEGACY_OTP,
        )
    )

    # Keep OTP table clean for this target.
    session.exec(
        delete(OTP).where(
            OTP.target.in_(candidate_targets),
            OTP.purpose == "login",
            OTP.expires_at < (datetime.now(UTC) - timedelta(days=1)),
        )
    )
    session.commit()


def sync() -> None:
    ensure_warehouses_schema_compatibility()

    # Seed and repair warehouse manager baseline (role + permissions + warehouse structure).
    seed_warehouse_manager()

    with Session(engine) as session:
        _cleanup_legacy_user(session, LEGACY_WAREHOUSE_EMAIL)

        warehouse_user = _ensure_warehouse_manager_user(session)

        warehouse_role = session.exec(select(Role).where(Role.name == "warehouse_manager")).first()
        if warehouse_role is not None:
            _ensure_user_role(session, warehouse_user, warehouse_role)
            warehouse_user.role_id = warehouse_role.id
            session.add(warehouse_user)
            session.commit()

        _ensure_default_warehouse(session, warehouse_user)

        driver_role = _ensure_driver_role(session)
        _ensure_role_permissions(session, driver_role, DRIVER_PERMISSION_SLUGS)
        delivery_user = _ensure_delivery_driver_user(session, driver_role)

        _cleanup_legacy_otps(session)

        print("\nSynced logistics app users:")
        print(f"  Delivery partner: {DELIVERY_NAME} / {DELIVERY_PHONE}")
        print(f"  Warehouse manager: {WAREHOUSE_NAME} / {WAREHOUSE_EMAIL} / {WAREHOUSE_PASSWORD}")
        print(f"  Delivery user id: {delivery_user.id}")
        print(f"  Warehouse user id: {warehouse_user.id}")


if __name__ == "__main__":
    sync()
