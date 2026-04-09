from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlmodel import Session, select, func
from sqlalchemy import case
from sqlalchemy.orm import load_only
from typing import List, Optional
from datetime import datetime, UTC
from pydantic import BaseModel
from app.api import deps
from app.models.user import User, UserStatus, UserType
from app.schemas.user import UserResponse
from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.rbac import Role
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
        role_lower = resolved_role.name.lower()
        # Any organizational role that is NOT 'customer' or 'driver' should be an ADMIN type for the portal
        if role_lower in ('admin', 'super_admin', 'superadmin', 'fleet_manager', 'manager', 'support_agent', 'support'):
            user_type = UserType.ADMIN
        elif role_lower == 'dealer':
            user_type = UserType.DEALER
        elif role_lower == 'customer':
            user_type = UserType.CUSTOMER
        elif role_lower in ('station_manager', 'technician', 'logistics_manager',
                            'driver', 'warehouse_manager', 'support_agent',
                            'finance_manager', 'inspector', 'franchise_owner',
                            'marketing_manager', 'analyst'):
            user_type = UserType.ADMIN  # operational staff roles

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


@router.get("", include_in_schema=False)
@router.get("/")
def list_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None,
    user_type: Optional[str] = None,
    kyc_status: Optional[str] = None,
    fields: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """List all users with pagination, search, and filters."""
    def _load_users() -> dict:
        filters = [User.is_deleted == False]

        if search:
            filters.append(
                (User.full_name.ilike(f"%{search}%")) |
                (User.email.ilike(f"%{search}%")) |
                (User.phone_number.ilike(f"%{search}%"))
            )

        if status:
            filters.append(User.status == status.lower())

        if user_type:
            filters.append(User.user_type == user_type)

        if kyc_status:
            filters.append(User.kyc_status == kyc_status)

        total_count = db.exec(select(func.count(User.id)).where(*filters)).one() or 0
        user_list = []
        
        if fields:
            field_names = {"id"} | {f.strip() for f in fields.split(",")}
            valid_cols = [getattr(User, fn) for fn in field_names if hasattr(User, fn)]
            if valid_cols:
                # Add role mapping injection if role is requested
                fetch_roles = "role" in field_names or "role_name" in field_names
                if fetch_roles and User.role_id not in valid_cols:
                    valid_cols.append(User.role_id)
                    
                users = db.exec(select(*valid_cols).where(*filters).order_by(User.created_at.desc()).offset(skip).limit(limit)).all()
                keys = [c.name for c in valid_cols]
                
                role_map = {}
                if fetch_roles:
                    # 'users' is a list of tuples, we must find the index of role_id
                    rid_idx = keys.index("role_id")
                    role_ids = {row[rid_idx] for row in users if row[rid_idx]}
                    role_map = {r.id: r.name for r in db.exec(select(Role).where(Role.id.in_(role_ids))).all()} if role_ids else {}

                for row in users:
                    if len(valid_cols) == 1:
                        row_dict = {keys[0]: row}
                    else:
                        row_dict = dict(zip(keys, row))
                    
                    if fetch_roles:
                        row_dict["role"] = role_map.get(row_dict.get("role_id"))
                        
                    for k, v in row_dict.items():
                        if hasattr(v, 'isoformat'): row_dict[k] = v.isoformat()
                        elif hasattr(v, 'value'): row_dict[k] = v.value
                    user_list.append(row_dict)
        else:
            users = db.exec(
                select(User)
                .where(*filters)
                .options(
                    load_only(
                        User.id,
                        User.full_name,
                        User.email,
                        User.phone_number,
                        User.user_type,
                        User.status,
                        User.kyc_status,
                        User.profile_picture,
                        User.role_id,
                        User.is_superuser,
                        User.created_at,
                        User.last_login,
                        User.deletion_reason,
                        User.force_password_change,
                    )
                )
                .order_by(User.created_at.desc())
                .offset(skip)
                .limit(limit)
            ).all()

            role_ids = {u.role_id for u in users if u.role_id}
            role_map = (
                {r.id: r.name for r in db.exec(select(Role).where(Role.id.in_(role_ids))).all()}
                if role_ids else {}
            )

            for u in users:
                role_name = role_map.get(u.role_id) if u.role_id else None
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
        skip,
        limit,
        search or "",
        status or "",
        user_type or "",
        kyc_status or "",
        fields or "",
        ttl_seconds=max(settings.USER_ADMIN_CACHE_TTL_SECONDS, 120),
        call=_load_users,
    )


@router.get("/summary")
def get_user_summary(
    background_tasks: BackgroundTasks,
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
        ttl_seconds=max(settings.USER_ADMIN_CACHE_TTL_SECONDS, 120),
        call=_load_summary,
        stale_while_revalidate_seconds=3600,  # 1 hour stale tolerance
        background_tasks=background_tasks,
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


@router.post("/{user_id}/reset-password")
def reset_user_password(
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


@router.put("/{user_id}/password")
def update_user_password(
    user_id: int,
    payload: AdminPasswordResetRequest,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    return reset_user_password(user_id=user_id, payload=payload, current_user=current_user, db=db)


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
