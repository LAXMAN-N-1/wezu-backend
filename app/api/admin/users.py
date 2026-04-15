from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from sqlalchemy import case
from typing import List, Optional
from datetime import datetime, UTC
from pydantic import BaseModel
from app.api import deps
from app.models.user import User, UserStatus, UserType
from app.schemas.user import UserResponse
from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.rbac import Role, UserRole
from app.core.rbac import canonical_role_name
from app.utils.runtime_cache import cached_call, invalidate_cache


router = APIRouter()


def _invalidate_admin_user_cache() -> None:
    invalidate_cache("admin-users")


class AdminUserCreateRequest(BaseModel):
    full_name: str
    email: str
    phone_number: Optional[str] = None
    password: Optional[str] = None
    role_name: Optional[str] = "customer"
    user_type: Optional[UserType] = UserType.CUSTOMER
    status: Optional[UserStatus] = UserStatus.ACTIVE


@router.post("/", response_model=dict)
def admin_create_user(
    payload: AdminUserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    """Admin: Directly create a new user."""
    # 1. Duplicate check
    existing = db.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    if payload.phone_number:
        phone_exists = db.exec(select(User).where(User.phone_number == payload.phone_number)).first()
        if phone_exists:
            raise HTTPException(status_code=400, detail="Phone number already exists")

    # 2. Resolve role (case-insensitive lookup)
    role_id = None
    resolved_role = None
    if payload.role_name:
        resolved_role = db.exec(
            select(Role).where(func.lower(Role.name) == payload.role_name.lower())
        ).first()
        if resolved_role:
            role_id = resolved_role.id

    # 3. Derive user_type from role if possible, otherwise use payload
    user_type = payload.user_type or UserType.CUSTOMER
    if resolved_role:
        role_lower = canonical_role_name(resolved_role.name)
        if role_lower in ("super_admin", "operations_admin", "security_admin", "finance_admin", "support_manager", "support_agent"):
            user_type = UserType.ADMIN
        elif role_lower == "dealer_owner":
            user_type = UserType.DEALER
        elif role_lower == "customer":
            user_type = UserType.CUSTOMER
        elif role_lower in {"dealer_manager", "dealer_inventory_staff", "dealer_finance_staff", "dealer_support_staff"}:
            user_type = UserType.DEALER_STAFF
        elif role_lower in {"logistics_manager", "dispatcher", "fleet_manager", "warehouse_manager", "driver"}:
            user_type = UserType.LOGISTICS

    # 4. Create
    new_user = User(
        email=payload.email,
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        hashed_password=get_password_hash(payload.password or "Welcome@123"),
        user_type=user_type,
        status=payload.status or UserStatus.ACTIVE,
        role_id=role_id,
        is_superuser=False,
        created_at=datetime.now(UTC),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    if role_id:
        existing_link = db.exec(
            select(UserRole).where(
                UserRole.user_id == new_user.id,
                UserRole.role_id == role_id,
            )
        ).first()
        if not existing_link:
            db.add(
                UserRole(
                    user_id=new_user.id,
                    role_id=role_id,
                    effective_from=datetime.now(UTC),
                )
            )
            db.commit()
    _invalidate_admin_user_cache()

    return {
        "id": new_user.id,
        "email": new_user.email,
        "full_name": new_user.full_name,
        "status": new_user.status.value,
        "role_name": payload.role_name,
    }


class PaginatedUsersResponse(BaseModel):
    users: List[dict]
    total_count: int
    page: int
    page_size: int


class SuspendRequest(BaseModel):
    reason: str


class ReactivateRequest(BaseModel):
    notes: Optional[str] = None


class AdminUserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None


class AdminPasswordResetRequest(BaseModel):
    new_password: Optional[str] = None
    password: Optional[str] = None
    force_reset: bool = True


def _serialize_user(user: User, role_name: Optional[str] = None) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name or "Unknown",
        "email": user.email or "",
        "phone_number": user.phone_number or "",
        "user_type": user.user_type.value if user.user_type else "customer",
        "status": user.status.value if user.status else "active",
        "kyc_status": user.kyc_status.value if user.kyc_status else "not_submitted",
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "profile_picture": user.profile_picture,
        "role": role_name,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "last_login_at": user.last_login.isoformat() if user.last_login else None,
        "deletion_reason": user.deletion_reason,
        "force_password_reset": user.force_password_change,
        "invited_by": None,
    }


@router.get("/")
def list_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None,
    user_type: Optional[str] = None,
    kyc_status: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """List all users with pagination, search, and filters."""
    def _load_users() -> dict:
        statement = select(User).where(User.is_deleted == False)

        if search:
            statement = statement.where(
                (User.full_name.ilike(f"%{search}%")) |
                (User.email.ilike(f"%{search}%")) |
                (User.phone_number.ilike(f"%{search}%"))
            )

        if status:
            statement = statement.where(User.status == status.lower())

        if user_type:
            statement = statement.where(User.user_type == user_type)

        if kyc_status:
            statement = statement.where(User.kyc_status == kyc_status)

        total_count = db.exec(select(func.count()).select_from(statement.subquery())).one()
        users = db.exec(statement.order_by(User.created_at.desc()).offset(skip).limit(limit)).all()

        role_ids = {u.role_id for u in users if u.role_id}
        role_map = (
            {r.id: r.name for r in db.exec(select(Role).where(Role.id.in_(role_ids))).all()}
            if role_ids else {}
        )

        user_list = []
        for u in users:
            role_name = None
            if u.role:
                role_name = u.role.name
            elif u.role_id:
                role_name = role_map.get(u.role_id)
            user_list.append(_serialize_user(u, role_name=role_name))

        return {
            "items": user_list,
            "total_count": total_count,
            "page": skip // limit + 1 if limit > 0 else 1,
            "page_size": limit,
        }

    return cached_call(
        "admin-users",
        "list",
        current_user.id,
        skip,
        limit,
        search or "",
        status or "",
        user_type or "",
        kyc_status or "",
        ttl_seconds=settings.USER_ADMIN_CACHE_TTL_SECONDS,
        call=_load_users,
    )


@router.get("/summary")
def get_user_summary(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Get user statistics for admin dashboard."""
    def _load_summary() -> dict:
        total, active, suspended, pending_verification, inactive = db.exec(
            select(
                func.count(User.id),
                func.coalesce(func.sum(case((User.status == UserStatus.ACTIVE, 1), else_=0)), 0),
                func.coalesce(func.sum(case((User.status == UserStatus.SUSPENDED, 1), else_=0)), 0),
                func.coalesce(func.sum(case((User.status == UserStatus.PENDING_VERIFICATION, 1), else_=0)), 0),
                func.coalesce(func.sum(case((User.is_active == False, 1), else_=0)), 0),
            ).where(User.is_deleted == False)
        ).one()

        return {
            "total_users": total,
            "active_count": active,
            "inactive_count": inactive,
            "suspended_count": suspended,
            "pending_count": pending_verification,
        }

    return cached_call(
        "admin-users",
        "summary",
        current_user.id,
        ttl_seconds=settings.USER_ADMIN_CACHE_TTL_SECONDS,
        call=_load_summary,
    )


@router.get("/suspended")
def list_suspended_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """List all suspended users."""
    statement = select(User).where(
        User.status == UserStatus.SUSPENDED,
        User.is_deleted == False
    )

    if search:
        statement = statement.where(
            (User.full_name.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%")) |
            (User.phone_number.ilike(f"%{search}%"))
        )

    count_stmt = select(func.count()).select_from(statement.subquery())
    total_count = db.exec(count_stmt).one()

    statement = statement.order_by(User.updated_at.desc()).offset(skip).limit(limit)
    users = db.exec(statement).all()

    user_list = []
    for u in users:
        serialized = _serialize_user(u, role_name=None)
        serialized["suspension_reason"] = u.deletion_reason
        serialized["suspended_at"] = u.updated_at.isoformat() if u.updated_at else None
        user_list.append(serialized)

    return {
        "items": user_list,
        "total_count": total_count,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
    }


@router.get("/{user_id}")
def get_user_detail(
    user_id: int,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Get detailed view of a specific user."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role_name = None
    if user.role_id:
        from app.models.rbac import Role
        role = db.get(Role, user.role_id)
        role_name = role.name if role else None

    return _serialize_user(user, role_name=role_name)


@router.put("/{user_id}")
def update_user_detail(
    user_id: int,
    payload: AdminUserUpdateRequest,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "email" in update_data and update_data["email"] != user.email:
        existing = db.exec(select(User).where(User.email == update_data["email"], User.id != user_id)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")
    if "phone_number" in update_data and update_data["phone_number"] != user.phone_number:
        existing_phone = db.exec(
            select(User).where(User.phone_number == update_data["phone_number"], User.id != user_id)
        ).first()
        if existing_phone:
            raise HTTPException(status_code=400, detail="Phone number already exists")

    for key, value in update_data.items():
        setattr(user, key, value)
    user.updated_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)
    _invalidate_admin_user_cache()

    role_name = db.get(Role, user.role_id).name if user.role_id and db.get(Role, user.role_id) else None
    return _serialize_user(user, role_name=role_name)


# DECONFLICTED P0-B: POST /{user_id}/reset-password removed.
# Canonical handler lives in app/api/v1/admin_users.py::admin_reset_password
# (has richer audit trail).  Removed 2026-04-06.


@router.put("/{user_id}/password")
def update_user_password(
    user_id: int,
    payload: AdminPasswordResetRequest,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    raw_password = payload.new_password or payload.password
    if not raw_password:
        raise HTTPException(status_code=400, detail="new_password is required")

    user.hashed_password = get_password_hash(raw_password)
    user.force_password_change = payload.force_reset
    user.updated_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    _invalidate_admin_user_cache()
    return {"status": "success", "message": "Password reset successful"}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_deleted = True
    user.deleted_at = datetime.now(UTC)
    user.status = UserStatus.DELETED
    user.updated_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    _invalidate_admin_user_cache()
    return {"status": "success", "message": f"User {user.full_name or user.email} deleted"}


@router.put("/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Block or unblock a user."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active
    user.updated_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)
    _invalidate_admin_user_cache()
    return {"status": "success", "is_active": user.is_active}


@router.put("/{user_id}/suspend")
def suspend_user(
    user_id: int,
    request: SuspendRequest,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Suspend a user account with a reason."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(status_code=400, detail="User is already suspended")

    user.status = UserStatus.SUSPENDED
    user.deletion_reason = request.reason  # Reusing for suspension reason
    user.updated_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)
    _invalidate_admin_user_cache()

    return {
        "status": "success",
        "message": f"User {user.full_name} has been suspended",
        "user_status": user.status.value,
    }


@router.put("/{user_id}/reactivate")
def reactivate_user(
    user_id: int,
    request: ReactivateRequest = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Reactivate a suspended user account."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.status != UserStatus.SUSPENDED:
        raise HTTPException(status_code=400, detail="User is not suspended")

    user.status = UserStatus.ACTIVE
    user.deletion_reason = None  # Clear suspension reason
    user.updated_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)
    _invalidate_admin_user_cache()

    return {
        "status": "success",
        "message": f"User {user.full_name} has been reactivated",
        "user_status": user.status.value,
    }


@router.put("/{user_id}/kyc-status")
def update_user_kyc_status(
    user_id: int,
    status: str = Query(..., pattern="^(pending|verified|rejected)$"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Update user KYC status."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.kyc_status = status
    user.updated_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)
    _invalidate_admin_user_cache()
    return {"status": "success", "kyc_status": user.kyc_status}
