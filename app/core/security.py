from datetime import datetime, timedelta, UTC
from typing import Any, Union
import uuid
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated=["bcrypt"])

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None, extra_claims: dict = None) -> str:
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        # Access token valid for 24 hours per FR-MOB-AUTH-002
        expire = datetime.now(UTC) + timedelta(hours=24)
    
    # Add 'iat' claim for global logout validation
    to_encode = {"exp": expire, "sub": str(subject), "type": "access", "iat": datetime.now(UTC)}
    
    if extra_claims:
        to_encode.update(extra_claims)
        
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def create_refresh_token(subject: Union[str, Any], jti: str = None) -> str:
    # This function can now be simplified or removed if create_access_token handles both
    # For now, keeping it as is, but it's redundant with the changes to create_access_token
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "exp": expire, 
        "sub": str(subject), 
        "type": "refresh",
        "jti": jti or str(uuid.uuid4()) # Unique identifier to ensure token rotation works even if timestamps are identical
    }
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Corrupted or unrecognizable hash in DB — treat as invalid credentials
        import structlog
        structlog.get_logger().warning(
            "verify_password: hash could not be identified, treating as invalid",
            hash_prefix=hashed_password[:20] if hashed_password else "EMPTY",
        )
        return False

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


import pyotp
import secrets

def generate_totp_secret() -> str:
    return pyotp.random_base32()

def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code)

def generate_backup_codes(count: int = 10) -> list:
    return [secrets.token_hex(4).upper() for _ in range(count)]

def generate_qr_uri(secret: str, user_email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=user_email, issuer_name="Wezu Energy"
    )

def verify_permission(user, permission_slug: str) -> bool:
    """
    Check if a user has a specific permission.
    Returns True if user is superuser or has the permission via their roles.
    """
    if user.is_superuser:
        return True
    return user.has_permission(permission_slug)

