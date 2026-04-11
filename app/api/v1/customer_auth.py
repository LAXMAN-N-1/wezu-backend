"""Customer-specific auth endpoints for mobile clients."""

from datetime import UTC, datetime
import logging
from typing import Any, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from sqlmodel import Session, select

from app.api import deps
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_and_update_password,
)
from app.models.rbac import Role
from app.models.user import User, UserStatus
from app.repositories.user_repository import user_repository
from app.services.auth_service import AuthService
from app.services.otp_service import OTPService

router = APIRouter()
logger = logging.getLogger("wezu_customer_auth")


class CustomerRegisterRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    full_name: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return value


class CustomerOTPRequest(BaseModel):
    target: str
    purpose: str = "registration"


class CustomerOTPVerifyRequest(BaseModel):
    target: str
    code: str
    purpose: str = "registration"
    full_name: Optional[str] = None


class CustomerRefreshRequest(BaseModel):
    refresh_token: str


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


def _enum_value(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    return value.value if hasattr(value, "value") else str(value)


def _find_user_by_identifier(db: Session, identifier: str) -> Optional[User]:
    user = user_repository.get_by_email(db, identifier)
    if not user:
        user = user_repository.get_by_phone(db, identifier)
    return user


def _build_auth_response(user: User, access_token: str, refresh_token: str) -> CustomerAuthResponse:
    return CustomerAuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=CustomerAuthUser(
            id=user.id,
            email=user.email,
            phone_number=user.phone_number,
            full_name=user.full_name,
            user_type=_enum_value(user.user_type, "customer"),
            kyc_status=_enum_value(user.kyc_status, "not_submitted"),
            profile_picture=user.profile_picture,
        ),
    )


async def _extract_login_credentials(request: Request) -> tuple[str, str]:
    content_type = (request.headers.get("content-type") or "").lower()
    payload: dict[str, Any] = {}

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        payload = dict(await request.form())
    else:
        try:
            body = await request.json()
            if isinstance(body, dict):
                payload = body
        except Exception:
            payload = {}

    identifier = str(
        payload.get("email")
        or payload.get("username")
        or payload.get("credential")
        or ""
    ).strip()
    password = str(payload.get("password") or "").strip()

    if not identifier or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Both username/email and password are required",
        )
    return identifier, password


def _create_customer_session(
    db: Session,
    user: User,
    refresh_token: str,
    request: Request,
    token_jti: str,
) -> None:
    try:
        AuthService.create_user_session(db, user.id, refresh_token, request, token_jti=token_jti)
    except Exception as exc:
        logger.warning("Session creation warning: %s", exc)


@router.post("/login", response_model=CustomerAuthResponse)
async def customer_login(
    request: Request,
    db: Session = Depends(deps.get_db),
):
    """
    Customer login supporting `application/x-www-form-urlencoded` and JSON bodies.
    Accepts `email`, `username`, or `credential` as the identifier field.
    """
    identifier, password = await _extract_login_credentials(request)
    logger.info("Customer login attempt: %s", identifier)

    user = _find_user_by_identifier(db, identifier)
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email/phone or password")

    ok, new_hash = verify_and_update_password(password, user.hashed_password)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid email/phone or password")

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account is inactive or suspended")

    if new_hash:
        user.hashed_password = new_hash

    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=user.id, jti=token_jti)

    user.last_login = datetime.now(UTC)
    db.add(user)
    db.commit()

    _create_customer_session(db, user, refresh_token, request, token_jti)

    return _build_auth_response(user, access_token, refresh_token)


@router.post("/register", response_model=CustomerAuthResponse)
def customer_register(
    register_data: CustomerRegisterRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
):
    """
    Customer password registration endpoint.
    """
    if not register_data.email and not register_data.phone_number:
        raise HTTPException(status_code=400, detail="Email or phone number is required")

    if register_data.email:
        existing = user_repository.get_by_email(db, register_data.email)
        if existing:
            raise HTTPException(status_code=400, detail="A user with this email already exists")

    if register_data.phone_number:
        existing = user_repository.get_by_phone(db, register_data.phone_number)
        if existing:
            raise HTTPException(status_code=400, detail="A user with this phone number already exists")

    user = User(
        email=register_data.email,
        phone_number=register_data.phone_number,
        full_name=register_data.full_name,
        hashed_password=get_password_hash(register_data.password),
        user_type="customer",
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
        if customer_role:
            user.role_id = customer_role.id
            db.add(user)
            db.commit()
            db.refresh(user)
    except Exception as exc:
        logger.warning("Role assignment warning: %s", exc)

    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=user.id, jti=token_jti)
    _create_customer_session(db, user, refresh_token, request, token_jti)

    logger.info("Customer registered: %s", user.id)
    return _build_auth_response(user, access_token, refresh_token)


@router.post("/register/request-otp")
async def request_registration_otp(
    otp_data: CustomerOTPRequest,
    db: Session = Depends(deps.get_db),
):
    target = otp_data.target.strip()
    if not target:
        raise HTTPException(status_code=400, detail="Target is required")

    code = OTPService.generate_otp(target, otp_data.purpose)
    OTPService.create_otp_record(db, target, code, otp_data.purpose)

    if "@" in target:
        await OTPService.send_email_otp(target, code)
    else:
        await OTPService.send_sms_otp(target, code)

    return {"detail": "OTP sent successfully"}


@router.post("/register/verify-otp", response_model=CustomerAuthResponse)
async def verify_registration_otp(
    verify_data: CustomerOTPVerifyRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
):
    target = verify_data.target.strip()
    if not OTPService.verify_otp(db, target, verify_data.code, verify_data.purpose):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )

    user = _find_user_by_identifier(db, target)
    if not user:
        user_data: dict[str, Any] = {
            "full_name": (verify_data.full_name or "").strip() or "Customer",
            "status": UserStatus.ACTIVE,
            "user_type": "customer",
        }
        if "@" in target:
            user_data["email"] = target
        else:
            user_data["phone_number"] = target

        user = User(**user_data)
        db.add(user)
        db.commit()
        db.refresh(user)

        customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
        if customer_role:
            user.role_id = customer_role.id
            db.add(user)
            db.commit()
            db.refresh(user)
    elif user.status != UserStatus.ACTIVE:
        user.status = UserStatus.ACTIVE

    user.last_login = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)

    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=user.id, jti=token_jti)
    _create_customer_session(db, user, refresh_token, request, token_jti)

    return _build_auth_response(user, access_token, refresh_token)


@router.post("/refresh", response_model=CustomerAuthResponse)
def refresh_customer_token(
    data: CustomerRefreshRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
):
    auth_headers = {"WWW-Authenticate": "Bearer"}
    try:
        session = AuthService.validate_session(db, data.refresh_token, is_refresh=True)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token_invalid",
                headers=auth_headers,
            )

        payload = jwt.decode(data.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token_invalid",
                headers=auth_headers,
            )

        user_id = payload.get("sub")
        user = db.get(User, int(user_id)) if user_id else None
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token_invalid",
                headers=auth_headers,
            )
        if user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive or suspended",
            )

        old_jti = payload.get("jti")
        new_jti = str(uuid.uuid4())
        new_refresh_token = create_refresh_token(subject=user.id, jti=new_jti)
        access_token = create_access_token(subject=user.id, extra_claims={"sid": new_jti})

        if old_jti:
            AuthService.update_user_session(db, old_jti, new_refresh_token, request)
        else:
            AuthService.revoke_session(db, data.refresh_token)
            AuthService.create_user_session(db, user.id, new_refresh_token, request, token_jti=new_jti)

        return _build_auth_response(user, access_token, new_refresh_token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token_expired",
            headers=auth_headers,
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token_invalid",
            headers=auth_headers,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected refresh failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token_invalid",
            headers=auth_headers,
        )
