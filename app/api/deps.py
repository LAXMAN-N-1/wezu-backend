from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlmodel import Session
from app.core import security
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.role_right import RoleRight
from app.schemas.user import TokenPayload
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

def check_permission(menu_name: str, permission_type: str = "view"):
    """
    Dependency to check if user has specific permission for a menu by name
    """
    def permission_checker(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ) -> User:
        # Superuser always has access
        if current_user.is_superuser:
            return current_user
        
        if not current_user.role_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no role assigned"
            )

        # Check role rights by joining with Menu to filter by name
        from app.models.menu import Menu
        role_right = db.query(RoleRight).join(Menu).filter(
            RoleRight.role_id == current_user.role_id,
            Menu.name == menu_name
        ).first()
        
        if not role_right:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No access to resource: {menu_name}"
            )
        
        # Check specific permission
        permission_map = {
            "view": role_right.can_view,
            "create": role_right.can_create,
            "edit": role_right.can_edit,
            "delete": role_right.can_delete
        }
        
        if not permission_map.get(permission_type, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {permission_type} on {menu_name}"
            )
        
        return current_user
    
    return permission_checker

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
