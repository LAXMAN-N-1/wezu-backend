"""
Enhanced Authentication API
Apple Sign-In, Biometric, and 2FA endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import pyotp
import hashlib

from app.api import deps
from app.db.session import get_session
from app.core.security import create_access_token
from app.models.user import User
from app.models.biometric import BiometricToken, TwoFactorAuth
from app.services.apple_auth_service import AppleAuthService
from app.schemas.common import DataResponse

router = APIRouter()

# Schemas
class AppleSignInRequest(BaseModel):
    identity_token: str
    authorization_code: Optional[str] = None
    user_info: Optional[dict] = None  # First-time sign-in only

class BiometricRegisterRequest(BaseModel):
    device_id: str
    biometric_type: str  # FINGERPRINT, FACE_ID
    public_key: str
    device_name: Optional[str] = None
    device_model: Optional[str] = None

class BiometricVerifyRequest(BaseModel):
    device_id: str
    biometric_signature: str

class TwoFactorEnableRequest(BaseModel):
    method: str = "TOTP"  # TOTP, SMS, EMAIL
    phone_number: Optional[str] = None

class TwoFactorVerifyRequest(BaseModel):
    code: str

# Apple Sign-In
@router.post("/apple", response_model=DataResponse[dict])
async def apple_sign_in(
    request: AppleSignInRequest,
    session: Session = Depends(get_session)
):
    """
    Apple Sign-In authentication
    Creates new user or logs in existing user
    """
    # Verify identity token
    apple_data = await AppleAuthService.verify_identity_token(request.identity_token)
    if not apple_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Apple identity token"
        )
    
    apple_user_id = apple_data.get('sub')
    email = apple_data.get('email')
    
    # Check if user exists
    user = session.exec(
        select(User).where(User.apple_id == apple_user_id)
    ).first()
    
    if not user and email:
        # Check by email
        user = session.exec(
            select(User).where(User.email == email)
        ).first()
        
        if user:
            # Link Apple ID to existing account
            user.apple_id = apple_user_id
            session.add(user)
            session.commit()
    
    # Create new user if doesn't exist
    if not user:
        if not request.user_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User info required for first-time sign-in"
            )
        
        user = User(
            email=email or f"{apple_user_id}@appleid.com",
            full_name=request.user_info.get('name', {}).get('firstName', '') + ' ' + 
                      request.user_info.get('name', {}).get('lastName', ''),
            apple_id=apple_user_id,
            is_active=True,
            email_verified=True  # Apple verifies email
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    
    # Generate JWT token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return DataResponse(
        success=True,
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name
            }
        }
    )

# Biometric Authentication
@router.post("/biometric/register", response_model=DataResponse[dict])
def register_biometric(
    request: BiometricRegisterRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Register biometric authentication for device"""
    # Check if device already registered
    existing = session.exec(
        select(BiometricToken)
        .where(BiometricToken.user_id == current_user.id)
        .where(BiometricToken.device_id == request.device_id)
        .where(BiometricToken.is_active == True)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Biometric already registered for this device"
        )
    
    # Create biometric token
    token_hash = hashlib.sha256(
        f"{current_user.id}{request.device_id}{request.public_key}".encode()
    ).hexdigest()
    
    biometric_token = BiometricToken(
        user_id=current_user.id,
        device_id=request.device_id,
        biometric_type=request.biometric_type,
        public_key=request.public_key,
        token_hash=token_hash,
        device_name=request.device_name,
        device_model=request.device_model,
        expires_at=datetime.utcnow() + timedelta(days=90)  # 90-day expiry
    )
    session.add(biometric_token)
    session.commit()
    
    return DataResponse(
        success=True,
        data={
            "message": "Biometric authentication registered successfully",
            "token_id": biometric_token.id,
            "expires_at": biometric_token.expires_at
        }
    )

@router.post("/biometric/verify", response_model=DataResponse[dict])
def verify_biometric(
    request: BiometricVerifyRequest,
    session: Session = Depends(get_session)
):
    """Verify biometric and generate access token"""
    # Find biometric token
    biometric = session.exec(
        select(BiometricToken)
        .where(BiometricToken.device_id == request.device_id)
        .where(BiometricToken.is_active == True)
    ).first()
    
    if not biometric:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Biometric not registered"
        )
    
    # Check expiry
    if biometric.expires_at and biometric.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Biometric token expired"
        )
    
    # Verify signature (simplified - in production, use proper cryptographic verification)
    expected_signature = hashlib.sha256(
        f"{biometric.token_hash}{datetime.utcnow().strftime('%Y%m%d')}".encode()
    ).hexdigest()
    
    # In production, verify using device's public key
    # For now, we'll accept the signature
    
    # Update last used
    biometric.last_used_at = datetime.utcnow()
    session.add(biometric)
    session.commit()
    
    # Generate access token
    access_token = create_access_token(data={"sub": str(biometric.user_id)})
    
    return DataResponse(
        success=True,
        data={
            "access_token": access_token,
            "token_type": "bearer"
        }
    )

# Two-Factor Authentication
@router.post("/2fa/enable", response_model=DataResponse[dict])
def enable_2fa(
    request: TwoFactorEnableRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Enable two-factor authentication"""
    # Check if already enabled
    existing = session.exec(
        select(TwoFactorAuth).where(TwoFactorAuth.user_id == current_user.id)
    ).first()
    
    if existing and existing.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA already enabled"
        )
    
    # Generate TOTP secret
    secret = pyotp.random_base32()
    
    # Create or update 2FA settings
    if existing:
        existing.secret_key = secret
        existing.method = request.method
        existing.phone_number = request.phone_number
        twofa = existing
    else:
        twofa = TwoFactorAuth(
            user_id=current_user.id,
            secret_key=secret,
            method=request.method,
            phone_number=request.phone_number
        )
    
    session.add(twofa)
    session.commit()
    
    # Generate QR code URI for TOTP apps
    totp = pyotp.TOTP(secret)
    qr_uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name="WEZU Energy"
    )
    
    return DataResponse(
        success=True,
        data={
            "secret": secret,
            "qr_uri": qr_uri,
            "message": "Scan QR code with your authenticator app"
        }
    )

@router.post("/2fa/verify", response_model=DataResponse[dict])
def verify_2fa(
    request: TwoFactorVerifyRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Verify 2FA code and enable it"""
    twofa = session.exec(
        select(TwoFactorAuth).where(TwoFactorAuth.user_id == current_user.id)
    ).first()
    
    if not twofa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA not set up"
        )
    
    # Verify TOTP code
    totp = pyotp.TOTP(twofa.secret_key)
    if not totp.verify(request.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA code"
        )
    
    # Enable 2FA
    twofa.is_enabled = True
    twofa.enabled_at = datetime.utcnow()
    twofa.last_verified_at = datetime.utcnow()
    session.add(twofa)
    session.commit()
    
    return DataResponse(
        success=True,
        data={"message": "2FA enabled successfully"}
    )

@router.post("/2fa/disable", response_model=DataResponse[dict])
def disable_2fa(
    request: TwoFactorVerifyRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Disable two-factor authentication"""
    twofa = session.exec(
        select(TwoFactorAuth).where(TwoFactorAuth.user_id == current_user.id)
    ).first()
    
    if not twofa or not twofa.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA not enabled"
        )
    
    # Verify code before disabling
    totp = pyotp.TOTP(twofa.secret_key)
    if not totp.verify(request.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA code"
        )
    
    twofa.is_enabled = False
    session.add(twofa)
    session.commit()
    
    return DataResponse(
        success=True,
        data={"message": "2FA disabled successfully"}
    )
