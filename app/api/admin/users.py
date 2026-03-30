from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime, UTC
from pydantic import BaseModel
from app.api import deps
from app.models.user import User, UserStatus, UserType
from app.schemas.user import UserResponse
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.rbac import Role


router = APIRouter()


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

    # Get total count
    count_stmt = select(func.count()).select_from(statement.subquery())
    total_count = db.exec(count_stmt).one()

    # Paginate
    statement = statement.order_by(User.created_at.desc()).offset(skip).limit(limit)
    users = db.exec(statement).all()

    role_ids = {u.role_id for u in users if u.role_id}
    from app.models.rbac import Role
    role_map = {r.id: r.name for r in db.exec(select(Role).where(Role.id.in_(role_ids))).all()} if role_ids else {}

    user_list = []
    for u in users:
        role_name = None
        if u.role:
            role_name = u.role.name
        elif u.role_id:
            role_name = role_map.get(u.role_id)

        user_list.append({
            "id": u.id,
            "full_name": u.full_name or "Unknown",
            "email": u.email or "",
            "phone_number": u.phone_number or "",
            "user_type": u.user_type.value if u.user_type else "customer",
            "status": u.status.value if u.status else "active",
            "kyc_status": u.kyc_status.value if u.kyc_status else "not_submitted",
            "is_active": u.is_active,
            "is_superuser": u.is_superuser,
            "profile_picture": u.profile_picture,
            "role": role_name,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login.isoformat() if u.last_login else None,
            "deletion_reason": u.deletion_reason,
        })

    return {
        "items": user_list,
        "total_count": total_count,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
    }


@router.get("/summary")
def get_user_summary(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Get user statistics for admin dashboard."""
    total = db.exec(select(func.count()).where(User.is_deleted == False)).one()
    active = db.exec(select(func.count()).where(
        User.status == UserStatus.ACTIVE, User.is_deleted == False
    )).one()
    suspended = db.exec(select(func.count()).where(
        User.status == UserStatus.SUSPENDED, User.is_deleted == False
    )).one()
    pending_verification = db.exec(select(func.count()).where(
        User.status == UserStatus.PENDING_VERIFICATION, User.is_deleted == False
    )).one()
    
    # Map to frontend expected keys
    return {
        "total_users": total,
        "active_count": active,
        "inactive_count": 0, # Assuming inactive is separate from suspended in some systems
        "suspended_count": suspended,
        "pending_count": pending_verification,
    }


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
        user_list.append({
            "id": u.id,
            "full_name": u.full_name or "Unknown",
            "email": u.email or "",
            "phone_number": u.phone_number or "",
            "user_type": u.user_type.value if u.user_type else "customer",
            "status": u.status.value if u.status else "suspended",
            "kyc_status": u.kyc_status.value if u.kyc_status else "not_submitted",
            "profile_picture": u.profile_picture,
            "suspension_reason": u.deletion_reason,  # Using deletion_reason field for suspension reason
            "suspended_at": u.updated_at.isoformat() if u.updated_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })

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

    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone_number": user.phone_number,
        "user_type": user.user_type.value if user.user_type else "customer",
        "status": user.status.value if user.status else "active",
        "kyc_status": user.kyc_status.value if user.kyc_status else "not_submitted",
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "profile_picture": user.profile_picture,
        "role": role_name,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login.isoformat() if user.last_login else None,
    }


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
    return {"status": "success", "kyc_status": user.kyc_status}
