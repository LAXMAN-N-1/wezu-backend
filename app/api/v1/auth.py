from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.user import User, Token
from app.models.otp import OTP
from app.services.auth_service import AuthService
from app.services.otp_service import OTPService
from app.services.fraud_service import FraudService
from app.services.token_service import TokenService
from app.core.security import create_access_token, create_refresh_token, get_password_hash, verify_password
from app.core.config import settings
from app.api import deps
from pydantic import BaseModel, EmailStr, Field
from fastapi.security import OAuth2PasswordRequestForm
import logging
from typing import Optional, Any
from datetime import datetime
from jose import jwt, JWTError

router = APIRouter()
logger = logging.getLogger("wezu_auth")
logging.basicConfig(level=logging.INFO)

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone_number: str

@router.post("/register", response_model=User)
async def register(
    user_in: UserCreate,
    db: Session = Depends(get_session)
):
    """
    Register a new user with email and password.
    """
    user = db.exec(select(User).where(User.email == user_in.email)).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        phone_number=user_in.phone_number,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Assign default role
    from app.models.rbac import Role
    from sqlalchemy.orm import selectinload
    customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
    if customer_role:
        user.roles.append(customer_role)
        db.add(user)
        db.commit()
        db.refresh(user)
        
    return user

@router.post("/login", response_model=Token)
@router.post("/token", response_model=Token)
async def login_access_token(
    db: Session = Depends(get_session),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    # Try by email
    statement = select(User).where(User.email == form_data.username)
    user = db.exec(statement).first()
    
    if not user:
        # Try by phone number if email fails (optional, but good UX)
        statement = select(User).where(User.phone_number == form_data.username)
        user = db.exec(statement).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        user=user # Helper: include user info
    )

class GoogleAuthRequest(BaseModel):
    token: str
    consent: bool = False

class AppleAuthRequest(BaseModel):
    token: str
    full_name: Optional[str] = None
    consent: bool = False

class OTPRequest(BaseModel):
    target: str # email or phone_number
    purpose: str = "registration"

class OTPVerifyRequest(BaseModel):
    target: str
    code: str
    purpose: str = "registration"
    full_name: Optional[str] = None

@router.post("/register/request-otp")
async def request_registration_otp(
    otp_data: OTPRequest,
    db: Session = Depends(get_session)
):
    # Check if user already exists
    if "@" in otp_data.target:
        statement = select(User).where(User.email == otp_data.target)
    else:
        statement = select(User).where(User.phone_number == otp_data.target)
    
    user = db.exec(statement).first()
    is_new_user = user is None
    
    logger.info(f"OTP request for {otp_data.target}. New user: {is_new_user}")

    # Generate and send OTP
    code = OTPService.generate_otp(otp_data.target)
    OTPService.create_otp_record(db, otp_data.target, code, otp_data.purpose)

    logger.info(f"OTP requested for {otp_data.target} with purpose {otp_data.purpose}")
    if "@" in otp_data.target:
        await OTPService.send_email_otp(otp_data.target, code)
    else:
        await OTPService.send_sms_otp(otp_data.target, code)

    return {"message": "OTP sent successfully"}

from sqlalchemy.orm import selectinload
from app.models.rbac import Role

@router.post("/register/verify-otp", response_model=Token)
async def verify_registration_otp(
    verify_data: OTPVerifyRequest,
    db: Session = Depends(get_session)
):
    # Verify OTP
    if not OTPService.verify_otp(db, verify_data.target, verify_data.code, verify_data.purpose):
        logger.warning(f"Failed OTP verification attempt for {verify_data.target}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )

    # Check if user already exists
    if "@" in verify_data.target:
        statement = select(User).where(User.email == verify_data.target).options(selectinload(User.roles))
    else:
        statement = select(User).where(User.phone_number == verify_data.target).options(selectinload(User.roles))
    
    user = db.exec(statement).first()

    if not user:
        # Create new user
        new_user_data = {
            "full_name": verify_data.full_name,
            "is_active": True
        }
        if "@" in verify_data.target:
            new_user_data["email"] = verify_data.target
        else:
            new_user_data["phone_number"] = verify_data.target

        user = User(**new_user_data)
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Assign Default Role: Customer
        customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
        if customer_role:
            user.roles.append(customer_role)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Check Fraud Risk
        FraudService.calculate_risk_score(user.id)
    else:
        logger.info(f"Existing user linked via OTP: {verify_data.target}")

    # Create Dual Tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    return Token(access_token=access_token, refresh_token=refresh_token, user=user)

@router.post("/google", response_model=Token)
async def authenticate_google(
    auth_data: GoogleAuthRequest,
    db: Session = Depends(get_session)
):
    # 1. Verify Google Token
    idinfo = AuthService.verify_google_token(auth_data.token)
    email = idinfo.get("email")
    google_id = idinfo.get("sub")
    name = idinfo.get("name")
    picture = idinfo.get("picture")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google token does not contain email",
        )

    # 2. Check if user exists
    user = db.exec(select(User).where(User.email == email).options(selectinload(User.roles))).first()

    if not user:
        # Create new user
        user = User(
            email=email,
            full_name=name,
            google_id=google_id,
            profile_picture=picture,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Assign Default Role: Customer
        customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
        if customer_role:
            user.roles.append(customer_role)
            db.add(user)
            db.commit()
            db.refresh(user)
            
        # Check Fraud Risk
        FraudService.calculate_risk_score(user.id)
    else:
        # Update existing user
        user.google_id = google_id
        user.profile_picture = picture
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Save Consent
    if auth_data.consent:
        user.consent_captured = True
        user.consent_date = datetime.utcnow()
        db.add(user)
        db.commit()

    # 3. Create Dual Tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return Token(access_token=access_token, refresh_token=refresh_token)

@router.post("/apple", response_model=Token)
async def authenticate_apple(
    auth_data: AppleAuthRequest,
    db: Session = Depends(get_session)
):
    # 1. Verify Apple Token
    payload = AuthService.verify_apple_token(auth_data.token)
    email = payload.get("email")
    apple_id = payload.get("sub")
    
    if not email:
         # Some Apple logins don't provide email on subsequent sign-ins
         # But the sub (apple_id) is unique and consistent
         pass

    # 2. Check if user exists by apple_id or email
    user = db.exec(select(User).where(
        (User.apple_id == apple_id) | (User.email == email)
    ).options(selectinload(User.roles))).first()

    if not user:
        user = User(
            email=email,
            full_name=auth_data.full_name,
            apple_id=apple_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Assign Default Role: Customer
        customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
        if customer_role:
            user.roles.append(customer_role)
            db.add(user)
            db.commit()
            db.refresh(user)
            
        # Check Fraud Risk
        FraudService.calculate_risk_score(user.id)
    else:
        user.apple_id = apple_id
        if auth_data.full_name:
            user.full_name = auth_data.full_name
        db.add(user)
        db.commit()
        db.refresh(user)

    # Save Consent
    if auth_data.consent:
        user.consent_captured = True
        user.consent_date = datetime.utcnow()
        db.add(user)
        db.commit()

    # 3. Create Dual Tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return Token(access_token=access_token, refresh_token=refresh_token)

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: RefreshRequest,
    db: Session = Depends(get_session)
):
    try:
        payload = jwt.decode(
            refresh_data.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user_id = payload.get("sub")
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)
        
        # Blacklist the old refresh token so it can't be reused
        TokenService.blacklist_token(db, refresh_data.refresh_token)
        
        return Token(access_token=access_token, refresh_token=refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    except Exception as e:
        logger.error(f"Refresh error: {str(e)}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")


# ===== NEW MISSING ENDPOINTS =====

@router.post("/logout")
async def logout(
    current_user: User = Depends(deps.get_current_user),
    token: str = Depends(deps.oauth2_scheme),
    db: Session = Depends(get_session)
):
    """Logout user - invalidate tokens"""
    TokenService.blacklist_token(db, token)
    logger.info(f"User {current_user.id} logged out and token blacklisted")
    return {"message": "Logged out successfully"}


@router.post("/resend-otp")
async def resend_otp(
    otp_data: OTPRequest,
    db: Session = Depends(get_session)
):
    """Resend OTP for registration or verification"""
    # Generate and send new OTP
    code = OTPService.generate_otp(otp_data.target)
    OTPService.create_otp_record(db, otp_data.target, code, otp_data.purpose)
    
    logger.info(f"OTP resent for {otp_data.target}")
    if "@" in otp_data.target:
        await OTPService.send_email_otp(otp_data.target, code)
    else:
        await OTPService.send_sms_otp(otp_data.target, code)
    
    return {"message": "OTP resent successfully"}


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_session)
):
    """Request password reset - sends OTP to email"""
    # Check if user exists
    statement = select(User).where(User.email == request.email)
    user = db.exec(statement).first()
    
    if not user:
        # Don't reveal if email exists or not (security best practice)
        return {"message": "If the email exists, a reset code has been sent"}
    
    # Generate and send OTP
    code = OTPService.generate_otp(request.email)
    OTPService.create_otp_record(db, request.email, code, "password_reset")
    
    logger.info(f"Password reset requested for {request.email}")
    await OTPService.send_email_otp(request.email, code)
    
    return {"message": "If the email exists, a reset code has been sent"}


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_session)
):
    """Reset password using OTP"""
    # Verify OTP
    if not OTPService.verify_otp(db, request.email, request.otp, "password_reset"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    
    # Get user
    statement = select(User).where(User.email == request.email)
    user = db.exec(statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    from app.core.security import get_password_hash
    user.hashed_password = get_password_hash(request.new_password)
    db.add(user)
    db.commit()
    
    logger.info(f"Password reset successful for {request.email}")
    return {"message": "Password reset successful"}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Change password for authenticated user"""
    from app.core.security import verify_password, get_password_hash
    
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(request.new_password)
    db.add(current_user)
    db.commit()
    
    logger.info(f"Password changed for user {current_user.id}")
    return {"message": "Password changed successfully"}


class Verify2FARequest(BaseModel):
    code: str


@router.post("/verify-2fa")
async def verify_2fa(
    request: Verify2FARequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Verify 2FA code during login"""
    from app.models.two_factor_auth import TwoFactorAuth
    
    # Get user's 2FA settings
    statement = select(TwoFactorAuth).where(TwoFactorAuth.user_id == current_user.id)
    two_fa = db.exec(statement).first()
    
    if not two_fa or not two_fa.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled for this user"
        )
    
    # Verify TOTP code
    import pyotp
    totp = pyotp.TOTP(two_fa.secret_key)
    
    if not totp.verify(request.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA code"
        )
    
    logger.info(f"2FA verified for user {current_user.id}")
    return {"message": "2FA verification successful", "verified": True}
