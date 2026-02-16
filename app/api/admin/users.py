from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.schemas.user import UserResponse
from app.db.session import get_session

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_session),
):
    """List all users with pagination and search."""
    statement = select(User)
    if search:
        statement = statement.where(
            (User.full_name.ilike(f"%{search}%")) | 
            (User.email.ilike(f"%{search}%")) | 
            (User.phone_number.ilike(f"%{search}%"))
        )
    statement = statement.offset(skip).limit(limit)
    users = db.exec(statement).all()
    return users

@router.get("/{user_id}", response_model=UserResponse)
def get_user_detail(
    user_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_session),
):
    """Get detailed view of a specific user."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_session),
):
    """Block or unblock a user."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = not user.is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "success", "is_active": user.is_active}

@router.put("/{user_id}/kyc-status")
def update_user_kyc_status(
    user_id: int,
    status: str = Query(..., regex="^(pending|verified|rejected)$"),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_session),
):
    """Update user KYC status."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.kyc_status = status
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "success", "kyc_status": user.kyc_status}
