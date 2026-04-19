from __future__ import annotations
from dataclasses import dataclass
import hashlib
from threading import Lock
from time import monotonic
from typing import Any, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError, ExpiredSignatureError
from pydantic import ValidationError
from sqlmodel import Session, select
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from app.core.config import settings
from app.core.rbac import canonical_role_name
from app.core.database import get_db
from app.models.rbac import Role, UserRole
from app.models.user import User
from app.schemas.user import TokenPayload
from app.models.oauth import BlacklistedToken
from app.services.auth_service import AuthService, SupabaseTokenValidationError
import logging

logger = logging.getLogger(__name__)

ADMIN_ROLE_NAMES = {"super_admin", "operations_admin", "security_admin", "finance_admin"}
SUPPORT_ROLE_NAMES = {"support_manager", "support_agent"}
DEALER_OWNER_ROLE_NAMES = {"dealer_owner"}
DEALER_SCOPE_ROLE_NAMES = {
    "dealer_owner",
    "dealer_manager",
    "dealer_inventory_staff",
    "dealer_finance_staff",
    "dealer_support_staff",
}
DRIVER_ROLE_NAMES = {"driver"}
CUSTOMER_ROLE_NAMES = {"customer"}
LOGISTICS_ROLE_NAMES = {"logistics_manager", "dispatcher", "fleet_manager", "warehouse_manager"}
INTERNAL_OPERATOR_ROLE_NAMES = ADMIN_ROLE_NAMES | LOGISTICS_ROLE_NAMES | SUPPORT_ROLE_NAMES


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


def _auth_unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _coerce_iat(raw_iat: Any) -> Optional[int]:
    if isinstance(raw_iat, int):
        return raw_iat
    if isinstance(raw_iat, str) and raw_iat.strip().isdigit():
        return int(raw_iat.strip())
    return None


def _assert_not_blacklisted(db: Session, token: str) -> None:
    blacklisted = db.exec(select(BlacklistedToken).where(BlacklistedToken.token == token)).first()
    if blacklisted:
        raise _auth_unauthorized("token_invalid")


def _validate_local_access_token(db: Session, token: str) -> _ValidatedToken:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except ExpiredSignatureError:
        raise _auth_unauthorized("token_expired")
    except (JWTError, ValidationError) as exc:
        logger.warning("auth.token_decode_failed", extra={"error": str(exc)})
        raise _auth_unauthorized("token_invalid")

    _assert_not_blacklisted(db, token)

    sid = payload.get("sid")
    if sid:
        from app.models.session import UserSession
        user_session = db.exec(select(UserSession).where(UserSession.token_id == sid)).first()
        if not user_session or not user_session.is_active:
            raise _auth_unauthorized("token_invalid")

    try:
        user_id = int(token_data.sub)
    except (TypeError, ValueError):
        raise _auth_unauthorized("token_invalid")

    return _ValidatedToken(
        user_id=user_id,
        sid=sid,
        issued_at=_coerce_iat(payload.get("iat")),
    )


def _find_user_by_email(db: Session, email: str) -> Optional[User]:
    email_normalized = email.strip().lower()
    if not email_normalized:
        return None
    matches = db.exec(
        select(User).where(func.lower(User.email) == email_normalized)
    ).all()
    if not matches:
        return None
    if len(matches) > 1:
        logger.error(
            "auth.supabase_email_collision",
            extra={"email": email_normalized, "match_count": len(matches)},
        )
        raise _auth_unauthorized("token_invalid")
    return matches[0]


def _provision_supabase_user(db: Session, payload: dict[str, Any]) -> User:
    email = str(payload.get("email") or "").strip().lower()
    if not email:
        raise _auth_unauthorized("token_invalid")

    user_metadata = payload.get("user_metadata")
    full_name = None
    if isinstance(user_metadata, dict):
        full_name = user_metadata.get("full_name") or user_metadata.get("name")
    if not full_name:
        full_name = payload.get("name")

    phone_number = payload.get("phone")
    phone_number = str(phone_number).strip() if phone_number else None

    new_user = User(
        email=email,
        full_name=str(full_name).strip() if full_name else None,
        phone_number=phone_number,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    configured_role_name = str(settings.SUPABASE_DEFAULT_ROLE_NAME or "").strip().lower()
    canonical_default_role_name = canonical_role_name(configured_role_name)
    role_candidates = [
        candidate
        for candidate in (
            canonical_default_role_name,
            configured_role_name,
            "customer",
        )
        if candidate
    ]
    role = None
    for candidate in role_candidates:
        role = db.exec(select(Role).where(func.lower(Role.name) == candidate)).first()
        if role:
            break

    if role:
        new_user.role_id = role.id
        db.add(new_user)
        db.add(
            UserRole(
                user_id=new_user.id,
                role_id=role.id,
            )
        )
        db.commit()
        db.refresh(new_user)

    logger.info(
        "auth.supabase_user_provisioned",
        extra={"user_id": new_user.id, "email": email},
    )
    return new_user


def _validate_supabase_access_token(db: Session, token: str) -> _ValidatedToken:
    _assert_not_blacklisted(db, token)
    try:
        payload = AuthService.verify_supabase_access_token(token)
    except SupabaseTokenValidationError as exc:
        if exc.code == "token_expired":
            raise _auth_unauthorized("token_expired")
        raise _auth_unauthorized("token_invalid")

    sub = str(payload.get("sub") or "").strip()
    if not sub:
        raise _auth_unauthorized("token_invalid")

    email = str(payload.get("email") or "").strip()
    if settings.SUPABASE_ENFORCE_EMAIL_VERIFIED and email:
        email_verified = bool(payload.get("email_verified")) or bool(payload.get("email_confirmed_at"))
        if not email_verified:
            raise _auth_unauthorized("token_invalid")

    user = _find_user_by_email(db, email) if email else None
    if not user and settings.SUPABASE_AUTO_PROVISION_USERS:
        user = _provision_supabase_user(db, payload)
    if not user:
        raise _auth_unauthorized("token_invalid")

    return _ValidatedToken(
        user_id=user.id,
        sid=None,
        issued_at=_coerce_iat(payload.get("iat")),
    )


def _validate_access_token_by_mode(db: Session, token: str) -> _ValidatedToken:
    mode = settings.AUTH_PROVIDER
    if mode == "local":
        return _validate_local_access_token(db, token)
    if mode == "supabase":
        return _validate_supabase_access_token(db, token)
    if mode == "hybrid":
        try:
            return _validate_local_access_token(db, token)
        except HTTPException as local_error:
            if local_error.detail != "token_invalid":
                raise
            return _validate_supabase_access_token(db, token)
    logger.error("auth.invalid_provider_mode", extra={"auth_provider": mode})
    raise _auth_unauthorized("token_invalid")


def get_active_roles_for_user_id(
    db: Session,
    user_id: int,
) -> list[Role]:
    from datetime import datetime, timezone; UTC = timezone.utc

    now = datetime.now(UTC)
    active_roles = db.exec(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            Role.is_active == True,  # noqa: E712
            UserRole.effective_from <= now,
            or_(UserRole.expires_at == None, UserRole.expires_at >= now),  # noqa: E711
        )
        .order_by(Role.level.desc(), Role.name.asc())
    ).all()
    return active_roles


def get_user_from_token(
    db: Session,
    token: Optional[str],
    request: Optional[Request] = None,
) -> User:
    if not token or token.lower() in ["null", "undefined"]:
        raise _auth_unauthorized("token_missing")

    validated = _get_validated_token(token)

    if validated is None:
        validated = _validate_access_token_by_mode(db, token)
        _store_validated_token(token, validated)

    user = db.exec(
        select(User)
        .where(User.id == validated.user_id)
        .options(joinedload(User.role))
    ).first()

    if not user:
        raise _auth_unauthorized("token_invalid")
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

    if getattr(user, "last_global_logout_at", None):
        iat = validated.issued_at
        if iat:
            from datetime import datetime, timezone; UTC = timezone.utc
            token_issued_at = datetime.fromtimestamp(iat, UTC).replace(tzinfo=None)
            if token_issued_at < user.last_global_logout_at:
                raise _auth_unauthorized("token_invalid")

    active_roles = get_active_roles_for_user_id(db, user.id)
    setattr(user, "_active_roles_cache", active_roles)

    if not active_roles and user.role:
        setattr(user, "_active_roles_cache", [user.role])
        active_roles = [user.role]

    # Keep active role pointer deterministic and in-sync with active assignments.
    active_role_ids = {role.id for role in active_roles if role.id is not None}
    if active_role_ids and user.role_id not in active_role_ids:
        best_role = active_roles[0]
        if best_role.id is not None:
            user.role_id = best_role.id
            db.add(user)
            db.commit()
            db.refresh(user)
            setattr(user, "_active_roles_cache", active_roles)

    if request is not None:
        request.state.user = user
        request.state.user_id = user.id
        from app.models.roles import RoleEnum
        role_names = get_user_role_names(user)
        if canonical_role_name(RoleEnum.SUPER_ADMIN.value) in role_names:
            request.state.user_role = RoleEnum.SUPER_ADMIN
        elif role_names & ADMIN_ROLE_NAMES:
            request.state.user_role = RoleEnum.ADMIN
        elif role_names & LOGISTICS_ROLE_NAMES:
            request.state.user_role = RoleEnum.LOGISTICS
        elif role_names & DEALER_SCOPE_ROLE_NAMES:
            request.state.user_role = RoleEnum.DEALER
        elif canonical_role_name(RoleEnum.DRIVER.value) in role_names:
            request.state.user_role = RoleEnum.DRIVER
        elif canonical_role_name(RoleEnum.CUSTOMER.value) in role_names:
            request.state.user_role = RoleEnum.CUSTOMER

    return user


def get_user_role_names(user: User) -> set[str]:
    role_names: set[str] = set()

    for role in getattr(user, "roles", []) or []:
        role_name = canonical_role_name((getattr(role, "name", "") or "").strip().lower())
        if role_name:
            role_names.add(role_name)

    primary_role = getattr(user, "role", None)
    primary_role_name = canonical_role_name((getattr(primary_role, "name", "") or "").strip().lower())
    if primary_role_name:
        role_names.add(primary_role_name)

    user_type = getattr(user, "user_type", None)
    if user_type:
        role_names.add(canonical_role_name(str(getattr(user_type, "value", user_type)).strip().lower()))

    if getattr(user, "is_superuser", False):
        role_names.add("super_admin")

    return role_names


def get_dealer_profile_for_user_id(db: Session, user_id: int):
    from app.models.dealer import DealerProfile

    dealer_profile = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == user_id)
    ).first()
    if dealer_profile:
        return dealer_profile

    user = db.get(User, user_id)
    dealer_id = getattr(user, "created_by_dealer_id", None) if user else None
    if dealer_id:
        return db.get(DealerProfile, dealer_id)
    return None


def get_dealer_profile_for_user(db: Session, user: User):
    return get_dealer_profile_for_user_id(db, user.id)


def get_dealer_profile_or_403(
    db: Session,
    user_id: int,
    detail: str = "Not a dealer account",
):
    dealer_profile = get_dealer_profile_for_user_id(db, user_id)
    if not dealer_profile:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return dealer_profile


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme)
) -> User:
    return get_user_from_token(db=db, token=token, request=request)

def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not (current_user.is_superuser or "super_admin" in get_user_role_names(current_user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_permissions",
        )
    return current_user

def get_current_active_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    from app.models.user import UserType

    role_names = get_user_role_names(current_user)
    if not (
        current_user.is_superuser
        or current_user.user_type == UserType.ADMIN
        or bool(role_names & ADMIN_ROLE_NAMES)
    ):
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

        role_ids = [r.id for r in getattr(current_user, "roles", []) if getattr(r, "id", None) is not None]
        if not role_ids and current_user.role_id:
            role_ids = [current_user.role_id]
        if not role_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no role assigned"
            )

        from app.services.rbac_service import rbac_service
        has_access = any(
            rbac_service.check_menu_access(db, role_id, menu_name, permission_type)
            for role_id in role_ids
        )
        if not has_access:
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

        required = canonical_role_name(role_name)
        user_role_names = get_user_role_names(current_user)
        if required not in user_role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="insufficient_permissions",
            )
        return current_user
    
    return role_checker


def require_permission(permission_slug: str):
    """
    Dependency: Verify current user has a specific permission.
    Usage: current_user: User = Depends(require_permission("battery:view:global"))
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

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    from app.models.user import UserType

    user_role_names = get_user_role_names(current_user)
    if not (
        current_user.is_superuser
        or current_user.user_type == UserType.ADMIN
        or bool(user_role_names & ADMIN_ROLE_NAMES)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_permissions",
        )
    return current_user

def get_current_dealer(current_user: User = Depends(get_current_user)) -> User:
    from app.models.user import UserType

    user_role_names = get_user_role_names(current_user)
    if not (
        current_user.is_superuser
        or current_user.user_type == UserType.DEALER
        or bool(user_role_names & DEALER_OWNER_ROLE_NAMES)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_permissions",
        )
    return current_user

def get_current_driver(current_user: User = Depends(get_current_user)) -> User:
    if current_user.is_superuser:
        return current_user

    user_role_names = get_user_role_names(current_user)
    if not (user_role_names & DRIVER_ROLE_NAMES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_permissions",
        )
    return current_user

def get_current_customer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.is_superuser:
        return current_user

    user_role_names = get_user_role_names(current_user)
    if not (user_role_names & CUSTOMER_ROLE_NAMES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_permissions",
        )
    return current_user


def get_current_logistics(current_user: User = Depends(get_current_user)) -> User:
    from app.models.user import UserType

    if current_user.is_superuser:
        return current_user

    user_role_names = get_user_role_names(current_user)
    if not (
        current_user.user_type == UserType.LOGISTICS
        or bool(user_role_names & LOGISTICS_ROLE_NAMES)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_permissions",
        )
    return current_user


def get_current_dealer_scope_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.is_superuser:
        return current_user

    role_names = get_user_role_names(current_user)
    if role_names & DEALER_SCOPE_ROLE_NAMES:
        return current_user

    if get_dealer_profile_for_user(db, current_user):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="insufficient_permissions",
    )


def require_driver_or_internal_operator(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.is_superuser:
        return current_user

    role_names = get_user_role_names(current_user)
    if role_names & (DRIVER_ROLE_NAMES | INTERNAL_OPERATOR_ROLE_NAMES):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="insufficient_permissions",
    )


def require_customer_or_internal_operator(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.is_superuser:
        return current_user

    role_names = get_user_role_names(current_user)
    if role_names & (CUSTOMER_ROLE_NAMES | INTERNAL_OPERATOR_ROLE_NAMES):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="insufficient_permissions",
    )


def require_internal_operator(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require admin or warehouse/logistics operator role."""
    if current_user.is_superuser:
        return current_user

    user_role_names = get_user_role_names(current_user)
    if not user_role_names & INTERNAL_OPERATOR_ROLE_NAMES:
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
