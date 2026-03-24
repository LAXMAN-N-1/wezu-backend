"""
Dealer Portal Auth — Login, Register, Refresh, Change Password
Dedicated auth endpoints for the dealer portal frontend.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import logging
import uuid
from datetime import datetime

from app.api import deps
from app.db.session import get_session
from app.models.user import User, UserStatus, UserType
from app.models.dealer import DealerProfile, DealerApplication
from app.models.rbac import Role
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.repositories.user_repository import user_repository

router = APIRouter()
logger = logging.getLogger("wezu_dealer_auth")


# ── Schemas ──────────────────────────────────────────────

class DealerLoginRequest(BaseModel):
    email: str
    password: str


class DealerRegisterRequest(BaseModel):
    # User fields
    email: EmailStr
    phone_number: str
    full_name: str
    password: str
    # Dealer profile fields (Stage 1)
    business_name: str
    business_type: str = "proprietorship"  # proprietorship/partnership/company
    contact_person: str
    address_line1: str
    city: str
    state: str
    pincode: str
    description: Optional[str] = None
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class DealerAuthUser(BaseModel):
    id: int
    email: Optional[str] = None
    phone_number: Optional[str] = None
    full_name: Optional[str] = None
    user_type: Optional[str] = None
    profile_picture: Optional[str] = None
    dealer_id: Optional[int] = None
    business_name: Optional[str] = None
    is_approved: bool = False
    application_stage: Optional[str] = None

    class Config:
        from_attributes = True


class DealerAuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: DealerAuthUser


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ── Helpers ──────────────────────────────────────────────

def _build_dealer_auth_user(user: User, db: Session) -> DealerAuthUser:
    """Build auth response user object with dealer-specific fields."""
    dealer_profile = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == user.id)
    ).first()

    application_stage = None
    is_approved = False
    dealer_id = None
    business_name = None

    if dealer_profile:
        dealer_id = dealer_profile.id
        business_name = dealer_profile.business_name
        is_approved = dealer_profile.is_active

        app = db.exec(
            select(DealerApplication).where(
                DealerApplication.dealer_id == dealer_profile.id
            )
        ).first()
        if app:
            application_stage = app.current_stage

    return DealerAuthUser(
        id=user.id,
        email=user.email,
        phone_number=user.phone_number,
        full_name=user.full_name,
        user_type="dealer",
        profile_picture=user.profile_picture,
        dealer_id=dealer_id,
        business_name=business_name,
        is_approved=is_approved,
        application_stage=application_stage,
    )


# ── Endpoints ────────────────────────────────────────────

@router.post("/login", response_model=DealerAuthResponse)
async def dealer_login(
    login_data: DealerLoginRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
):
    """Dealer login with email/phone + password."""
    identifier = login_data.email.strip()
    logger.info(f"Dealer login attempt: {identifier}")

    user = user_repository.get_by_email(db, identifier)
    if not user:
        user = user_repository.get_by_phone(db, identifier)

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account is inactive or suspended")

    # Generate tokens
    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=user.id, jti=token_jti)

    user.last_login = datetime.utcnow()
    db.add(user)
    db.commit()

    # Session
    try:
        from app.services.auth_service import AuthService
        AuthService.create_user_session(db, user.id, refresh_token, request, token_jti=token_jti)
    except Exception as e:
        logger.warning(f"Session creation warning: {e}")

    return DealerAuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_build_dealer_auth_user(user, db),
    )


@router.post("/register", response_model=DealerAuthResponse)
async def dealer_register(
    data: DealerRegisterRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
):
    """Stage 1: Create dealer user + profile + application."""
    # Check duplicates
    if user_repository.get_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if user_repository.get_by_phone(db, data.phone_number):
        raise HTTPException(status_code=400, detail="Phone number already registered")

    # Create user
    user = User(
        email=data.email,
        phone_number=data.phone_number,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        user_type=UserType.DEALER,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Assign dealer role
    try:
        dealer_role = db.exec(select(Role).where(Role.name == "dealer")).first()
        if dealer_role:
            user.role_id = dealer_role.id
            db.add(user)
            db.commit()
            db.refresh(user)
    except Exception as e:
        logger.warning(f"Role assignment warning: {e}")

    # Create dealer profile
    profile = DealerProfile(
        user_id=user.id,
        business_name=data.business_name,
        contact_person=data.contact_person,
        contact_email=data.email,
        contact_phone=data.phone_number,
        address_line1=data.address_line1,
        city=data.city,
        state=data.state,
        pincode=data.pincode,
        gst_number=data.gst_number,
        pan_number=data.pan_number,
        is_active=False,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    # Create application
    application = DealerApplication(
        dealer_id=profile.id,
        current_stage="SUBMITTED",
        status_history=[{
            "stage": "SUBMITTED",
            "timestamp": str(datetime.utcnow()),
            "note": "Digital application submitted",
        }],
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    # Generate tokens
    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=user.id, jti=token_jti)

    try:
        from app.services.auth_service import AuthService
        AuthService.create_user_session(db, user.id, refresh_token, request, token_jti=token_jti)
    except Exception as e:
        logger.warning(f"Session creation warning: {e}")

    logger.info(f"Dealer registered: user_id={user.id}, dealer_id={profile.id}")

    return DealerAuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_build_dealer_auth_user(user, db),
    )


@router.get("/register/status")
def registration_status(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get dealer's registration/onboarding status."""
    profile = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == current_user.id)
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Dealer profile not found")

    app = db.exec(
        select(DealerApplication).where(DealerApplication.dealer_id == profile.id)
    ).first()

    return {
        "dealer_id": profile.id,
        "business_name": profile.business_name,
        "is_active": profile.is_active,
        "current_stage": app.current_stage if app else "NOT_STARTED",
        "status_history": app.status_history if app else [],
        "created_at": str(profile.created_at),
    }


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Change dealer's password."""
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.hashed_password = get_password_hash(data.new_password)
    current_user.password_changed_at = datetime.utcnow()
    db.add(current_user)
    db.commit()

    return {"message": "Password changed successfully"}


@router.post("/refresh", response_model=DealerAuthResponse)
def refresh_token(
    data: RefreshTokenRequest,
    db: Session = Depends(deps.get_db),
):
    """Refresh JWT token."""
    from jose import jwt, JWTError
    from app.core.config import settings

    try:
        payload = jwt.decode(data.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        user_id = int(payload.get("sub"))
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        token_jti = str(uuid.uuid4())
        access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
        new_refresh = create_refresh_token(subject=user.id, jti=token_jti)

        return DealerAuthResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            user=_build_dealer_auth_user(user, db),
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
