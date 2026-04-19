from __future__ import annotations
from datetime import datetime, timedelta, timezone; UTC = timezone.utc
from typing import Any, Union
import uuid

from jose import jwt
from passlib.context import CryptContext
import pyotp
import secrets

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto")


# ── JWT ────────────────────────────────────────────────────────────────────

def create_access_token(
    subject: Union[str, Any],
    expires_delta: timedelta = None,
    extra_claims: dict = None,
) -> str:
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
        "iat": datetime.now(UTC),
    }
    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: Union[str, Any], jti: str = None) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "iat": datetime.now(UTC),
        "jti": jti or str(uuid.uuid4()),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ── Password hashing ──────────────────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# ── TOTP / 2FA ────────────────────────────────────────────────────────────

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code with null-safety and ±1 window tolerance."""
    if not secret or not code:
        return False
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    except Exception:
        return False


def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate backup codes for 2FA recovery."""
    return [secrets.token_hex(4).upper() for _ in range(count)]


def generate_qr_uri(secret: str, user_email: str) -> str:
    """Generate otpauth:// URI for QR code scanning."""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=user_email, issuer_name="Wezu Energy"
    )


# ── RBAC helper ────────────────────────────────────────────────────────────

def verify_permission(user, permission_slug: str) -> bool:
    """
    Check if a user has a specific permission.
    Returns True if user is superuser or has the permission via their roles.
    """
    if user.is_superuser:
        return True
    return user.has_permission(permission_slug)
