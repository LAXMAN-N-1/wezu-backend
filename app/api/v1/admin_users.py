
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


# ─── Password Management ───

from pydantic import BaseModel as PydanticBase


class AdminResetPasswordRequest(PydanticBase):
    new_password: str = "TempPass@123"


class StateTransitionRequest(PydanticBase):
    new_status: str


@router.post("/{user_id}/reset-password")
async def admin_reset_password(
    user_id: int,
    request: AdminResetPasswordRequest = AdminResetPasswordRequest(),
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Admin: Reset a user's password and force them to change on next login.
    """
    from app.core.security import get_password_hash
    from app.services.password_service import PasswordService

    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check history
    if not PasswordService.check_password_history(db, user_id, request.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password was used recently. Choose a different password.",
        )

    hashed = get_password_hash(request.new_password)
    target_user.hashed_password = hashed
    db.add(target_user)
    db.commit()

    PasswordService.record_password_change(db, user_id, hashed)

    # Set force-change AFTER recording (record_password_change resets the flag)
    target_user.force_password_change = True
    db.add(target_user)
    db.commit()

    AuditLogger.log_event(
        db, current_user.id, "ADMIN_PASSWORD_RESET", "USER",
        resource_id=user_id,
        metadata={"target_user_email": target_user.email},
    )

    return {
        "message": f"Password reset for {target_user.email}. User must change on next login.",
    }


@router.post("/{user_id}/force-password-change")
async def force_password_change(
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Admin: Set the force-password-change flag for a user."""
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.force_password_change = True
    db.add(target_user)
    db.commit()

    AuditLogger.log_event(
        db, current_user.id, "FORCE_PASSWORD_CHANGE", "USER",
        resource_id=user_id,
    )

    return {"message": f"User {target_user.email} must change password on next login."}


# ─── State Transitions ───

@router.post("/{user_id}/transition")
async def transition_user_state(
    user_id: int,
    request: StateTransitionRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Admin: Transition a user's status through the validated state machine.

    Valid transitions:
    PENDING → VERIFIED → ACTIVE, ACTIVE → SUSPENDED, SUSPENDED → ACTIVE/DELETED.
    """
    from app.services.user_state_service import UserStateService

    try:
        user = UserStateService.transition(
            db, user_id, request.new_status, admin_user_id=current_user.id
        )
        return {
            "message": f"User {user_id} transitioned to '{user.status}'",
            "user_id": user.id,
            "new_status": user.status,
            "allowed_next": UserStateService.get_allowed_transitions(user.status),
        }
    except ValueError as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"error": str(e), "detail": str(e)},
        )

