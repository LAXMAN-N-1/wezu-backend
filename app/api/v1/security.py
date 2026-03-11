from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.models.user import User
from app.models.two_factor_auth import TwoFactorAuth
from app.models.audit_log import SecurityEvent
from app.api import deps
import pyotp
from typing import List
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class Enable2FAResponse(BaseModel):
    secret_key: str
    provisioning_uri: str
    backup_codes: List[str]

@router.post("/enable-2fa", response_model=Enable2FAResponse)
async def enable_2fa(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Generate 2FA secret and enable it"""
    # 1. Generate Secret
    secret = pyotp.random_base32()
    
    # 2. Create Provisioning URI
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user.email or current_user.phone_number,
        issuer_name="Wezu Battery"
    )
    
    # 3. Store in DB
    two_fa = db.exec(select(TwoFactorAuth).where(TwoFactorAuth.user_id == current_user.id)).first()
    if not two_fa:
        two_fa = TwoFactorAuth(user_id=current_user.id, secret_key=secret)
    else:
        two_fa.secret_key = secret # Reset secret
    
    two_fa.is_enabled = False # Require verification to enable
    db.add(two_fa)
    db.commit()
    
    return {
        "secret_key": secret,
        "provisioning_uri": provisioning_uri,
        "backup_codes": ["123456", "789012"] # Mock backup codes
    }

class Verify2FARequest(BaseModel):
    code: str

@router.post("/verify-enable-2fa")
async def verify_enable_2fa(
    request: Verify2FARequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Verify code to finalize 2FA enabling"""
    two_fa = db.exec(select(TwoFactorAuth).where(TwoFactorAuth.user_id == current_user.id)).first()
    if not two_fa or not two_fa.secret_key:
        raise HTTPException(status_code=400, detail="2FA setup not initiated")
        
    totp = pyotp.TOTP(two_fa.secret_key)
    if not totp.verify(request.code):
        raise HTTPException(status_code=400, detail="Invalid code")
        
    two_fa.is_enabled = True
    current_user.two_factor_enabled = True
    db.add(two_fa)
    db.add(current_user)
    db.commit()
    
    return {"message": "2FA successfully enabled"}

@router.get("/activity-logs")
async def get_activity_logs(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 50
):
    """Get security activity logs"""
    statement = select(SecurityEvent).where(SecurityEvent.user_id == current_user.id).offset(skip).limit(limit).order_by(SecurityEvent.timestamp.desc())
    logs = db.exec(statement).all()
    return logs
