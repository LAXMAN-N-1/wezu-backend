from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core import security
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, TokenPayload
from app.models.oauth import BlacklistedToken

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    
    # Check if token is blacklisted
    blacklisted = db.query(BlacklistedToken).filter(BlacklistedToken.token == token).first()
    if blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
    
    # Check if we are using SQLModel (which uses .get) or pure SQLAlchemy
    # User model inherits from SQLModel, so we can use db.get(User, id) or query.
    # To be safe and consistent with typical patterns:
    from sqlalchemy.orm import selectinload
    user = db.query(User).filter(User.id == int(token_data.sub)).options(selectinload(User.roles)).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    # Global Logout Check
    
    # Global Logout Check
    if user.last_global_logout_at:
        # Get 'iat' (Issued At) from token
        iat = payload.get("iat")
        if iat:
            from datetime import datetime
            # Use utcfromtimestamp to compare with utcnow() stored in DB
            token_issued_at = datetime.utcfromtimestamp(iat)
             
            if token_issued_at < user.last_global_logout_at:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired (Logged out from all devices)",
                )
    
    return user

def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return current_user

# Alias for compatibility
get_current_active_user = get_current_user

from fastapi import Header

def get_current_tenant(
    x_tenant_id: str = Header(default="default")
) -> str:
    """
    Extract tenant_id from the 'X-Tenant-ID' header.
    """
    return x_tenant_id
