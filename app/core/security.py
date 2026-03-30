from datetime import datetime, timedelta
from typing import Any, Union
import uuid
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None, extra_claims: dict = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Access token valid for 24 hours per FR-MOB-AUTH-002
        expire = datetime.utcnow() + timedelta(hours=24)
    
    # Add 'iat' claim for global logout validation
    to_encode = {"exp": expire, "sub": str(subject), "type": "access", "iat": datetime.utcnow()}
    
    if extra_claims:
        to_encode.update(extra_claims)
        
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def create_refresh_token(subject: Union[str, Any], jti: str = None) -> str:
    # This function can now be simplified or removed if create_access_token handles both
    # For now, keeping it as is, but it's redundant with the changes to create_access_token
    expire = datetime.utcnow() + timedelta(days=7) # Refresh token valid for 7 days
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
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_permission(user, permission_slug: str) -> bool:
    """
    Check if a user has a specific permission.
    Returns True if user is superuser or has the permission via their roles.
    """
    if user.is_superuser:
        return True
    return user.has_permission(permission_slug)

import pyotp
import secrets

def generate_totp_secret() -> str:
    return pyotp.random_base32()

def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code)

def generate_backup_codes(num_codes: int = 10, length: int = 8) -> list:
    return [secrets.token_hex(length // 2) for _ in range(num_codes)]

def generate_qr_uri(secret: str, email: str, issuer: str = "WEZU") -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)
