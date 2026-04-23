from __future__ import annotations
"""
Customer-specific authentication endpoints.
JSON-based login/register for the Flutter customer app.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import text
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from typing import Optional
import logging
import uuid
import re
from datetime import datetime, timezone; UTC = timezone.utc

from app.api import deps
from app.db.session import get_session
from app.models.user import User, UserStatus, UserType
from app.models.rbac import Role
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.repositories.user_repository import user_repository
from app.services.auth_service import AuthService

router = APIRouter()
logger = logging.getLogger("wezu_customer_auth")


_LEGACY_USER_TYPE_VALUES = (
    "customer",
    "admin",
    "dealer",
    "dealer_staff",
    "support_agent",
    "logistics",
)


def _normalize_legacy_user_type_values(db: Session) -> None:
    """
    Repair lowercase legacy enum values so SQLAlchemy can hydrate User rows safely.
    """
    legacy_values_sql = ", ".join(f"'{value}'" for value in _LEGACY_USER_TYPE_VALUES)
    legacy_rows = db.execute(
        text(
            f"""
            SELECT id, CAST(user_type AS TEXT) AS user_type_text
            FROM users
            WHERE LOWER(CAST(user_type AS TEXT)) IN ({legacy_values_sql})
            """
        )
    ).all()
    if not legacy_rows:
        return

    for row in legacy_rows:
        db.execute(
            text("UPDATE users SET user_type = :normalized_value WHERE id = :user_id"),
            {"normalized_value": str(row.user_type_text).upper(), "user_id": row.id},
        )

    db.commit()
    logger.warning(
        "Normalized legacy lowercase user_type values before customer login",
        extra={"updated_rows": len(legacy_rows)},
    )


# ── Schemas ────────────────────────────────────────────────────────

class CustomerLoginRequest(BaseModel):
    email: str  # can be email OR phone number
    password: str


class CustomerRegisterRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    full_name: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class CustomerAuthUser(BaseModel):
    id: int
    email: Optional[str] = None
    phone_number: Optional[str] = None
    full_name: Optional[str] = None
    user_type: Optional[str] = None
    kyc_status: Optional[str] = None
    profile_picture: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CustomerAuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: CustomerAuthUser


# ── Endpoints ──────────────────────────────────────────────────────

@router.post("/login", response_model=CustomerAuthResponse)
async def customer_login(
    request: Request,
    db: Session = Depends(deps.get_db),
):
    """
    Customer login. Supports JSON and form payloads.
    Accepted identifier keys: email, username, phone_number.
    """
    payload: dict = {}
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            body = await request.json()
            payload = body if isinstance(body, dict) else {}
        except Exception:
            payload = {}
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form_data = await request.form()
        payload = dict(form_data)
    else:
        # Best effort for unknown content types
        try:
            body = await request.json()
            payload = body if isinstance(body, dict) else {}
        except Exception:
            payload = {}

    identifier = str(
        payload.get("email")
        or payload.get("username")
        or payload.get("phone_number")
        or ""
    ).strip()
    password = str(payload.get("password") or "")

    if not identifier or not password:
        raise HTTPException(status_code=422, detail="email/username and password are required")

    logger.info(f"Customer login attempt: {identifier}")

    # Repair known legacy enum values written by older releases.
    _normalize_legacy_user_type_values(db)

    # Look up by email first, then phone
    user = user_repository.get_by_email(db, identifier)
    if not user:
        user = user_repository.get_by_phone(db, identifier)

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email/phone or password")

    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email/phone or password")

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account is inactive or suspended")

    # Generate tokens
    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=user.id, jti=token_jti)

    # Update last login
    user.last_login = datetime.now(UTC)
    db.add(user)
    db.commit()

    # Create session
    try:
        AuthService.create_user_session(db, user.id, refresh_token, request, token_jti=token_jti)
    except Exception as e:
        logger.warning(f"Session creation warning: {e}")

    return CustomerAuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=CustomerAuthUser(
            id=user.id,
            email=user.email,
            phone_number=user.phone_number,
            full_name=user.full_name,
            user_type=user.user_type.value if user.user_type else "customer",
            kyc_status=user.kyc_status.value if user.kyc_status else "not_submitted",
            profile_picture=user.profile_picture,
        ),
    )


@router.post("/register", response_model=CustomerAuthResponse)
async def customer_register(
    register_data: CustomerRegisterRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
):
    """
    Customer JSON registration. Creates user, hashes password, returns tokens.
    """
    if not register_data.email and not register_data.phone_number:
        raise HTTPException(status_code=400, detail="Email or phone number is required")

    # Check duplicates
    if register_data.email:
        existing = user_repository.get_by_email(db, register_data.email)
        if existing:
            raise HTTPException(status_code=400, detail="A user with this email already exists")

    if register_data.phone_number:
        existing = user_repository.get_by_phone(db, register_data.phone_number)
        if existing:
            raise HTTPException(status_code=400, detail="A user with this phone number already exists")

    # Create user
    user = User(
        email=register_data.email,
        phone_number=register_data.phone_number,
        full_name=register_data.full_name,
        hashed_password=get_password_hash(register_data.password),
        user_type=UserType.CUSTOMER,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Assign customer role
    try:
        customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
        if customer_role:
            user.role_id = customer_role.id
            db.add(user)
            db.commit()
            db.refresh(user)
    except Exception as e:
        logger.warning(f"Role assignment warning: {e}")

    # Generate tokens
    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=user.id, jti=token_jti)

    # Create session
    try:
        AuthService.create_user_session(db, user.id, refresh_token, request, token_jti=token_jti)
    except Exception as e:
        logger.warning(f"Session creation warning: {e}")

    logger.info(f"Customer registered: {user.id}")

    return CustomerAuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=CustomerAuthUser(
            id=user.id,
            email=user.email,
            phone_number=user.phone_number,
            full_name=user.full_name,
            user_type="customer",
            kyc_status="not_submitted",
            profile_picture=None,
        ),
    )
