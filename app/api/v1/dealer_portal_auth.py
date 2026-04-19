from __future__ import annotations
"""
Dealer Portal Auth — Login, Register, Refresh, Change Password
Dedicated auth endpoints for the dealer portal frontend.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select
from sqlalchemy import update as sa_update
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from typing import Optional
import logging
import uuid
from datetime import datetime, timedelta, timezone; UTC = timezone.utc

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

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


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

    model_config = ConfigDict(from_attributes=True)


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
    dealer_profile = deps.get_dealer_profile_for_user(db, user)

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
        user_type=str(getattr(user.user_type, "value", user.user_type)) if user.user_type else "dealer",
        profile_picture=user.profile_picture,
        dealer_id=dealer_id,
        business_name=business_name,
        is_approved=is_approved,
        application_stage=application_stage,
    )


# ── Endpoints ────────────────────────────────────────────

@router.post("/login")
async def dealer_login(
    login_data: DealerLoginRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
):
    """Dealer login with email/phone + password. Supports both dealer owners and dealer staff."""
    identifier = login_data.email.strip()
    logger.info(f"Dealer login attempt: {identifier}")

    user = user_repository.get_by_email(db, identifier)
    if not user:
        user = user_repository.get_by_phone(db, identifier)

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Brute-force protection
    if user.locked_until and user.locked_until > datetime.now(UTC):
        remaining = int((user.locked_until - datetime.now(UTC)).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=423,
            detail=f"Account locked due to too many failed attempts. Try again in {remaining} minutes."
        )

    if not verify_password(login_data.password, user.hashed_password):
        # Atomic increment — SQL-level to avoid the read-modify-write race
        # between concurrent failed logins against the same account.
        result = db.execute(
            sa_update(User)
            .where(User.id == user.id)
            .values(failed_login_attempts=User.failed_login_attempts + 1)
            .returning(User.failed_login_attempts)
        )
        new_count = int(result.scalar_one() or 0)

        if new_count >= MAX_LOGIN_ATTEMPTS:
            # Compare-and-set lockout: only the losing request whose
            # increment actually crossed the threshold flips the lock.
            db.execute(
                sa_update(User)
                .where(
                    User.id == user.id,
                    User.failed_login_attempts >= MAX_LOGIN_ATTEMPTS,
                )
                .values(
                    failed_login_attempts=0,
                    locked_until=datetime.now(UTC) + timedelta(minutes=LOCKOUT_MINUTES),
                )
            )
            db.commit()
            raise HTTPException(
                status_code=423,
                detail=f"Account locked for {LOCKOUT_MINUTES} minutes after {MAX_LOGIN_ATTEMPTS} failed attempts."
            )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.status not in [UserStatus.ACTIVE, UserStatus.PENDING_VERIFICATION]:
        if user.status == UserStatus.PENDING:
            raise HTTPException(status_code=403, detail="Account is pending activation. Check your email for the invite link.")
        raise HTTPException(status_code=403, detail="Account is inactive or suspended")

    dealer_profile = deps.get_dealer_profile_for_user(db, user)
    if not dealer_profile:
        raise HTTPException(status_code=403, detail="Dealer portal access denied")

    # Generate tokens
    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=user.id, jti=token_jti)

    # Atomic reset of counters + last_login — avoids clobbering any
    # concurrent failed-login increments that may have landed between the
    # password check and this write.
    now = datetime.now(UTC)
    db.execute(
        sa_update(User)
        .where(User.id == user.id)
        .values(
            failed_login_attempts=0,
            locked_until=None,
            last_login=now,
        )
    )
    db.commit()
    # Refresh the in-memory user object so downstream code sees the reset.
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = now

    # Session
    try:
        from app.services.auth_service import AuthService
        AuthService.create_user_session(db, user.id, refresh_token, request, token_jti=token_jti)
    except Exception as e:
        logger.warning(f"Session creation warning: {e}")

    # Build user response with role info
    auth_user = _build_dealer_auth_user(user, db)
    user_dict = auth_user.dict() if hasattr(auth_user, 'dict') else auth_user.model_dump()

    # Add role info for staff users
    if user.role_id:
        role = db.get(Role, user.role_id)
        if role:
            user_dict["role_name"] = role.name
            user_dict["role_icon"] = role.icon
            user_dict["role_color"] = role.color
            # Build permissions bitmask
            perms = {}
            for p in role.permissions:
                mod = p.module
                if mod not in perms:
                    perms[mod] = []
                perms[mod].append(p.action)
            user_dict["permissions"] = perms

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "must_change_password": bool(user.force_password_change),
        "user": user_dict,
    }


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
            "timestamp": str(datetime.now(UTC)),
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
    profile = deps.get_dealer_profile_for_user(db, current_user)
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
    current_user.password_changed_at = datetime.now(UTC)
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


# ── Invite Token Activation ──────────────────────────────

class ActivateAccountRequest(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


@router.get("/validate-invite/{token}")
def validate_invite_token(
    token: str,
    db: Session = Depends(deps.get_db),
):
    """Validate an invite token before showing the activation form."""
    user = db.exec(select(User).where(User.invite_token == token)).first()
    if not user:
        return {"valid": False, "expired": False, "message": "Invalid invitation link"}

    if user.invite_token_expires and user.invite_token_expires < datetime.now(UTC):
        return {
            "valid": False, "expired": True,
            "email": user.email, "full_name": user.full_name,
            "message": "This invitation has expired"
        }

    # Get role and dealer info
    role_name = role_color = None
    if user.role_id:
        role = db.get(Role, user.role_id)
        if role:
            role_name = role.name
            role_color = role.color

    dealer_name = None
    if user.created_by_dealer_id:
        dealer = db.get(DealerProfile, user.created_by_dealer_id)
        if dealer:
            dealer_name = dealer.business_name

    return {
        "valid": True, "expired": False,
        "email": user.email,
        "full_name": user.full_name,
        "role_name": role_name,
        "role_color": role_color,
        "dealer_name": dealer_name,
    }


@router.post("/activate/{token}")
def activate_account(
    token: str,
    data: ActivateAccountRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
):
    """Activate a pending account using the invite token — sets password and logs in."""
    user = db.exec(select(User).where(User.invite_token == token)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid activation link")

    if user.invite_token_expires and user.invite_token_expires < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Invitation has expired. Please request a new one.")

    # Set password, activate
    user.hashed_password = get_password_hash(data.password)
    user.status = UserStatus.ACTIVE
    user.invite_token = None
    user.invite_token_expires = None
    user.force_password_change = False
    user.last_login = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)

    # Generate tokens
    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=user.id, jti=token_jti)

    # Create session
    try:
        from app.services.auth_service import AuthService
        AuthService.create_user_session(db, user.id, refresh_token, request, token_jti=token_jti)
    except Exception as e:
        logger.warning(f"Session creation warning: {e}")

    # Audit
    from app.models.audit_log import AuditLog, AuditActionType
    db.add(AuditLog(
        user_id=user.id,
        action=AuditActionType.ACCOUNT_ACTIVATION,
        resource_type="DEALER_USER",
        target_id=user.id,
        details=f"Account activated for {user.email}",
    ))
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "must_change_password": False,
        "user": _build_dealer_auth_user(user, db).dict() if hasattr(_build_dealer_auth_user(user, db), 'dict') else _build_dealer_auth_user(user, db).model_dump(),
    }


class ForceChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


@router.post("/force-change-password")
def force_change_password(
    data: ForceChangePasswordRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Force password change on first login after admin-set password."""
    if not current_user.force_password_change:
        raise HTTPException(status_code=400, detail="Password change not required")

    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.hashed_password = get_password_hash(data.new_password)
    current_user.force_password_change = False
    current_user.password_changed_at = datetime.now(UTC)
    current_user.updated_at = datetime.now(UTC)
    db.add(current_user)
    db.commit()

    return {"message": "Password changed successfully", "must_change_password": False}
