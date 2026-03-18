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

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token",
    description="Please enter your **Email** address (e.g., admin@wezu.com) in the **username** field below."
)

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    if not token or token.lower() in ["bearer null", "bearer undefined", "null", "undefined"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid token required",
        )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError) as e:
        import logging
        logging.error(f"AUTHENTICATION_ERROR: JWT/Validation failure: {str(e)} | Token provided: {token[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Could not validate credentials: {str(e)}",
        )
    
    # Check if token is blacklisted
    blacklisted = db.query(BlacklistedToken).filter(BlacklistedToken.token == token).first()
    if blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
        
    # --- SESSION VERIFICATION ---
    # Extract Session ID (sid) from token
    # Access tokens should have 'sid' claim linking to UserSession.token_id
    sid = payload.get("sid")
    if sid:
        from app.models.session import UserSession
        # Verify session exists and is active
        # We query by token_id (which is the JTI/SID)
        user_session = db.query(UserSession).filter(UserSession.token_id == sid).first()
        
        if not user_session:
            # Session not found (maybe deleted?)
            # Valid token but no session = Unauthorized (Revoked)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found or expired",
            )
            
        if not user_session.is_active:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked",
            )
            
        # Update last_active_at (optional, but good for tracking)
        # However, updating DB on every request can be heavy.
        # Let's skip updating for now to avoid performance hit, 
        # or only update if > 5 minutes passed? 
        # For strict security, we just read.
    
    # Check if we are using SQLModel (which uses .get) or pure SQLAlchemy
    # User model inherits from SQLModel, so we can use db.get(User, id) or query.
    # To be safe and consistent with typical patterns:
    from sqlalchemy.orm import selectinload
    user = db.query(User).filter(User.id == int(token_data.sub)).options(selectinload(User.role)).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has been deleted"
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    # Global Logout Check
    
    # Global Logout Check
    if getattr(user, "last_global_logout_at", None):
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

def get_current_active_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    from app.models.user import UserType
    if not (current_user.is_superuser or current_user.user_type == UserType.ADMIN):
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges (Admin required)"
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

        from app.services.rbac_service import rbac_service
        if not rbac_service.check_menu_access(db, current_user.role_id, menu_name, permission_type):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {permission_type} on {menu_name}"
            )
        
        return current_user
    
    return permission_checker

# Alias for compatibility
get_current_active_user = get_current_user

# --- Granular RBAC Dependencies ---

def require_role(role_name: str):
    """
    Dependency: Verify current user has a specific role.
    Usage: current_user: User = Depends(require_role("Driver"))
    """
    def role_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.is_superuser:
            return current_user
        
        user_role_names = [r.name for r in current_user.roles]
        if role_name not in user_role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role_name}' required"
            )
        return current_user
    
    return role_checker


def require_permission(permission_slug: str):
    """
    Dependency: Verify current user has a specific permission.
    Usage: current_user: User = Depends(require_permission("battery:read"))
    """
    def permission_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.is_superuser:
            return current_user
        
        if not current_user.has_permission(permission_slug):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission_slug}' required"
            )
        return current_user
    
    return permission_checker

from app.models.roles import RoleEnum

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.is_superuser:
        return current_user
        
    user_role_names = [r.name.lower() for r in current_user.roles]
    if current_user.role:
        user_role_names.append(current_user.role.name.lower())
        
    if RoleEnum.ADMIN.value not in user_role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

def get_current_dealer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.is_superuser:
        return current_user
        
    user_role_names = [r.name.lower() for r in current_user.roles]
    if current_user.role:
        user_role_names.append(current_user.role.name.lower())
        
    if RoleEnum.DEALER.value not in user_role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dealer privileges required"
        )
    return current_user

def get_current_driver(current_user: User = Depends(get_current_user)) -> User:
    if current_user.is_superuser:
        return current_user
        
    user_role_names = [r.name.lower() for r in current_user.roles]
    if current_user.role:
        user_role_names.append(current_user.role.name.lower())
        
    if RoleEnum.DRIVER.value not in user_role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Driver privileges required"
        )
    return current_user

def get_current_customer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.is_superuser:
        return current_user
        
    user_role_names = [r.name.lower() for r in current_user.roles]
    if current_user.role:
        user_role_names.append(current_user.role.name.lower())
        
    if RoleEnum.CUSTOMER.value not in user_role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer privileges required"
        )
    return current_user



from fastapi import Header

def get_current_tenant(
    x_tenant_id: str = Header(default="default")
) -> str:
    """
    Extract tenant_id from the 'X-Tenant-ID' header.
    """
    return x_tenant_id

def get_optional_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(OAuth2PasswordBearer(
        tokenUrl=f"{settings.API_V1_STR}/auth/token",
        auto_error=False
    ))
) -> Optional[User]:
    if not token or token.lower() in ["bearer null", "bearer undefined", "null", "undefined"]:
        return None
    try:
        return get_current_user(db=db, token=token)
    except HTTPException:
        return None
