
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.session import UserSession
from app.core.audit import AuditLogger
from datetime import datetime

router = APIRouter()

@router.post("/{user_id}/force-logout")
async def force_logout_user(
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Admin: Force logout a user from all devices.
    """
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    
    # Revoke all sessions via AuthService
    from app.services.auth_service import AuthService
    revoked_count = AuthService.revoke_all_user_sessions(db, user_id)
    
    # 3. Audit Log
    AuditLogger.log_event(
        db, 
        current_user.id, 
        "FORCE_LOGOUT", 
        "USER", 
        resource_id=user_id,
        metadata={"target_user_email": target_user.email, "sessions_revoked": revoked_count}
    )
    
    return {"message": f"User {target_user.email} has been logged out from {revoked_count} active sessions."}


@router.post("/{user_id}/ban")
async def ban_user(
    user_id: int,
    reason: str = "Violation of terms",
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Admin: Ban a user (deactivate account and revoke sessions).
    """
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if target_user.is_superuser:
        raise HTTPException(status_code=400, detail="Cannot ban a superuser")
        
    # 1. Deactivate
    target_user.is_active = False
    db.add(target_user)
    
    # 2. Revoke Sessions
    from app.services.auth_service import AuthService
    revoked_count = AuthService.revoke_all_user_sessions(db, user_id)
    
    db.commit()
    
    # 3. Audit Log
    AuditLogger.log_event(
        db, 
        current_user.id, 
        "BAN_USER", 
        "USER", 
        resource_id=user_id,
        metadata={
            "target_user_email": target_user.email, 
            "reason": reason,
            "sessions_revoked": revoked_count
        }
    )
    
    return {
        "message": f"User {target_user.email} has been banned.",
        "sessions_revoked": revoked_count
    }


@router.post("/{user_id}/unban")
async def unban_user(
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Admin: Unban a user (reactivate account).
    """
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # 1. Reactivate
    target_user.is_active = True
    db.add(target_user)
    db.commit()
    
    # 2. Audit Log
    AuditLogger.log_event(
        db, 
        current_user.id, 
        "UNBAN_USER", 
        "USER", 
        resource_id=user_id,
        metadata={"target_user_email": target_user.email}
    )
    
    return {"message": f"User {target_user.email} has been unbanned."}
