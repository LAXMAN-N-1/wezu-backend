from dataclasses import dataclass
import hashlib
from threading import Lock
from time import monotonic
from typing import Generator, Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError, ExpiredSignatureError
from pydantic import ValidationError
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from app.core import security
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.role_right import RoleRight
from app.schemas.user import TokenPayload
from app.models.oauth import BlacklistedToken
import logging

logger = logging.getLogger(__name__)


@dataclass
class _ValidatedToken:
    user_id: int
    sid: Optional[str]
    issued_at: Optional[int]


_auth_cache: dict[str, tuple[float, _ValidatedToken]] = {}
_auth_cache_lock = Lock()
_auth_user_index: dict[int, set[str]] = {}


def _auth_cache_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _prune_auth_cache(now: float) -> None:
    expired = [key for key, (expires_at, _) in _auth_cache.items() if expires_at <= now]
    for key in expired:
        _, cached = _auth_cache.pop(key, (0.0, None))
        if cached:
            user_keys = _auth_user_index.get(cached.user_id)
            if user_keys:
                user_keys.discard(key)
                if not user_keys:
                    _auth_user_index.pop(cached.user_id, None)


def _store_validated_token(token: str, validated: _ValidatedToken) -> None:
    ttl = settings.AUTH_TOKEN_CACHE_TTL_SECONDS
    if ttl <= 0:
        return
    now = monotonic()
    cache_key = _auth_cache_key(token)
    with _auth_cache_lock:
        _prune_auth_cache(now)
        previous = _auth_cache.get(cache_key)
        if previous:
            prior_user = previous[1].user_id
            user_keys = _auth_user_index.get(prior_user)
            if user_keys:
                user_keys.discard(cache_key)
                if not user_keys:
                    _auth_user_index.pop(prior_user, None)
        _auth_cache[cache_key] = (now + ttl, validated)
        _auth_user_index.setdefault(validated.user_id, set()).add(cache_key)


def _get_validated_token(token: str) -> Optional[_ValidatedToken]:
    ttl = settings.AUTH_TOKEN_CACHE_TTL_SECONDS
    if ttl <= 0:
        return None
    now = monotonic()
    cache_key = _auth_cache_key(token)
    with _auth_cache_lock:
        _prune_auth_cache(now)
        cached = _auth_cache.get(cache_key)
        if not cached or cached[0] <= now:
            return None
        return cached[1]


def invalidate_token_cache(token: Optional[str]) -> None:
    if not token:
        return
    cache_key = _auth_cache_key(token)
    with _auth_cache_lock:
        cached = _auth_cache.pop(cache_key, None)
        if cached:
            user_keys = _auth_user_index.get(cached[1].user_id)
            if user_keys:
                user_keys.discard(cache_key)
                if not user_keys:
                    _auth_user_index.pop(cached[1].user_id, None)


def invalidate_user_token_cache(user_id: int) -> None:
    with _auth_cache_lock:
        cache_keys = _auth_user_index.pop(user_id, set())
        for cache_key in cache_keys:
            _auth_cache.pop(cache_key, None)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token",
    description="Please enter your **Email** address (e.g., admin@wezu.com) in the **username** field below.",
    auto_error=False,
)

def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme)
) -> User:
    if not token or token.lower() in ["null", "undefined"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token_missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    validated = _get_validated_token(token)
    payload = None

    if validated is None:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            token_data = TokenPayload(**payload)
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token_expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except (JWTError, ValidationError) as e:
            logger.warning("auth.token_decode_failed", extra={"error": str(e)})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token_invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )

        blacklisted = db.exec(select(BlacklistedToken).where(BlacklistedToken.token == token)).first()
        if blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token_invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )

        sid = payload.get("sid")
        if sid:
            from app.models.session import UserSession
            user_session = db.exec(select(UserSession).where(UserSession.token_id == sid)).first()
            if not user_session or not user_session.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="token_invalid",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        validated = _ValidatedToken(
            user_id=int(token_data.sub),
            sid=sid,
            issued_at=payload.get("iat"),
        )
        _store_validated_token(token, validated)
    else:
        token_data = TokenPayload(sub=str(validated.user_id))
    
    # Check if we are using SQLModel (which uses .get) or pure SQLAlchemy
    # User model inherits from SQLModel, so we can use db.get(User, id) or query.
    # To be safe and consistent with typical patterns:
    user = db.exec(
        select(User)
        .where(User.id == validated.user_id)
        .options(joinedload(User.role))
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token_invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_permissions",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_permissions",
        )
        
    # Global Logout Check
    if getattr(user, "last_global_logout_at", None):
        # Get 'iat' (Issued At) from token
        iat = validated.issued_at
        if iat:
            from datetime import datetime, UTC
            # Use UTC-aware timestamp for comparison
            token_issued_at = datetime.fromtimestamp(iat, UTC).replace(tzinfo=None)
             
            if token_issued_at < user.last_global_logout_at:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="token_invalid",
                    headers={"WWW-Authenticate": "Bearer"},
                )
    
    return user

def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_permissions",
        )
    return current_user

def get_current_active_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    from app.models.user import UserType
    if not (current_user.is_superuser or current_user.user_type == UserType.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_permissions",
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
                detail="insufficient_permissions",
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
                detail="insufficient_permissions",
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
                detail="insufficient_permissions",
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
            detail="insufficient_permissions",
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
            detail="insufficient_permissions",
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
            detail="insufficient_permissions",
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
            detail="insufficient_permissions",
        )
    return current_user


def require_internal_operator(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require admin or warehouse/logistics operator role."""
    if current_user.is_superuser:
        return current_user
    user_role_names = {r.name.lower() for r in current_user.roles}
    if current_user.role:
        user_role_names.add(current_user.role.name.lower())
    allowed = {"admin", "operator", "warehouse_manager", "logistics"}
    if not user_role_names & allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_permissions",
        )
    return current_user


def require_internal_service_token(
    x_internal_service_token: Optional[str] = Header(default=None, alias="X-Internal-Service-Token"),
) -> bool:
    configured = (settings.INTERNAL_SERVICE_TOKEN or "").strip()
    if not configured:
        if settings.ENVIRONMENT.lower() == "production":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Internal service token is not configured",
            )
        return True

    if not x_internal_service_token or x_internal_service_token.strip() != configured:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service token",
        )
    return True
