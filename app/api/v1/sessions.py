
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select
from app.api import deps
from app.db.session import get_session
from app.models.session import UserSession
from app.models.user import User
from app.core.security import verify_password
from app.services.token_service import TokenService
from app.core.audit import AuditLogger
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class SessionResponse(BaseModel):
    id: int
    device_type: str
    device_name: str | None = None
    ip_address: str | None = None
    last_active_at: datetime
    is_current: bool
    is_active: bool
    created_at: datetime

@router.get("/list", response_model=List[SessionResponse])
async def list_sessions(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
    token: str = Depends(deps.oauth2_scheme)
) -> Any:
    """
    List all active sessions for the current user.
    """
    sessions = db.exec(select(UserSession).where(UserSession.user_id == current_user.id).where(UserSession.is_active == True)).all()
    
    # Identify current session by token SID claim
    current_sid = None
    try:
        from jose import jwt
        from app.core.config import settings
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        current_sid = payload.get("sid")
    except Exception:
        pass

    results = []
    for s in sessions:
        # Match session by Token JTI (sid)
        is_current = False
        if current_sid and s.token_id == current_sid:
            is_current = True
        
        results.append(SessionResponse(
            id=s.id,
            device_type=s.device_type,
            device_name=s.device_name,
            ip_address=s.ip_address,
            last_active_at=s.last_active_at,
            is_current=is_current,
            is_active=s.is_active,
            created_at=s.created_at
        ))
    return results

@router.post("/revoke/{session_id}")
async def revoke_session(
    session_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Revoke a specific session.
    """
    session = db.get(UserSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to revoke this session")
    
    if not session.is_active:
         return {"message": "Session already revoked"}
         
    # 1. Mark inactive
    session.is_active = False
    db.add(session)
    
    # Note: Access Token revocation is now enforced by `deps.get_current_user` 
    # checking `UserSession.is_active` against the token's `sid`.
    # Therefore, marking session inactive immediately invalidates the access token.
    
    db.commit()
    
    return {"message": "Session revoked"}

