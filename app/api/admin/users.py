from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.api import deps
from app.models.user import User, UserStatus, UserType
from app.schemas.user import UserResponse
from app.core.database import get_db

router = APIRouter()


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
    current_user: User = Depends(deps.get_current_active_superuser),
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
        statement = statement.where(User.status == status)

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

    user_list = []
    for u in users:
        role_name = None
        if u.role:
            role_name = u.role.name
        elif u.role_id:
            from app.models.rbac import Role
            role = db.get(Role, u.role_id)
            role_name = role.name if role else None

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
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "deletion_reason": u.deletion_reason,
        })

    return {
        "users": user_list,
        "total_count": total_count,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
    }


@router.get("/stats")
def get_user_stats(
    current_user: User = Depends(deps.get_current_active_superuser),
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
    pending_kyc = db.exec(select(func.count()).where(
        User.kyc_status == "pending", User.is_deleted == False
    )).one()

    return {
        "total_users": total,
        "active_users": active,
        "suspended_users": suspended,
        "pending_verification": pending_verification,
        "pending_kyc": pending_kyc,
    }


@router.get("/suspended")
def list_suspended_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
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
        "users": user_list,
        "total_count": total_count,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
    }


@router.get("/{user_id}")
def get_user_detail(
    user_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
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
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


@router.put("/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """Block or unblock a user."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active
    user.updated_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "success", "is_active": user.is_active}


@router.put("/{user_id}/suspend")
def suspend_user(
    user_id: int,
    request: SuspendRequest,
    current_user: User = Depends(deps.get_current_active_superuser),
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
    user.updated_at = datetime.utcnow()
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
    current_user: User = Depends(deps.get_current_active_superuser),
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
    user.updated_at = datetime.utcnow()
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
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """Update user KYC status."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.kyc_status = status
    user.updated_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "success", "kyc_status": user.kyc_status}
