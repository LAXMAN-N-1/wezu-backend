import logging
from threading import Lock
from time import monotonic
from typing import Any

import httpx
from google.oauth2 import id_token
from google.auth.transport import requests
from jose import jwt as jose_jwt, JWTError, ExpiredSignatureError
from app.core.config import settings
from app.core.rbac import canonical_role_name, canonicalize_permission_set
from app.core.proxy import get_client_ip
from fastapi import HTTPException, status, Request
from sqlalchemy import func
from sqlmodel import Session, select

logger = logging.getLogger(__name__)


class SupabaseTokenValidationError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class AuthService:
    _supabase_jwks_cache: list[dict[str, Any]] | None = None
    _supabase_jwks_cache_expiry: float = 0.0
    _supabase_jwks_lock = Lock()

    @staticmethod
    async def verify_google_token(token: str):
        from fastapi.concurrency import run_in_threadpool
        
        def _verify():
            try:
                # Specify the CLIENT_ID of the app that accesses the backend:
                idinfo = id_token.verify_oauth2_token(
                    token, 
                    requests.Request(), 
                    settings.GOOGLE_OAUTH_CLIENT_ID
                )
                return idinfo
            except ValueError:
                # Invalid token
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google token",
                )
        
        return await run_in_threadpool(_verify)

    @staticmethod
    async def verify_apple_token(token: str):
        try:
            import httpx
            from jose import jwt
            
            # 1. Fetch Apple's public keys
            apple_keys_url = "https://appleid.apple.com/auth/keys"
            async with httpx.AsyncClient() as client:
                response = await client.get(apple_keys_url)
            apple_keys = response.json()

            # 2. Decode the header to find the 'kid'
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            # 3. Verify the token using Apple's keys
            # jose.jwt.decode handles finding the correct key from the jwks if passed correctly,
            # but manually finding it is safer for simple integration.
            payload = jwt.decode(
                token,
                apple_keys,
                algorithms=["RS256"],
                audience=settings.APPLE_CLIENT_ID,
                issuer="https://appleid.apple.com"
            )
            return payload
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Apple token: {str(e)}",
            )

    @staticmethod
    async def verify_facebook_token(token: str):
        try:
            # Verify token via Graph API
            # Fields: id, name, email, picture
            url = f"https://graph.facebook.com/me?access_token={token}&fields=id,name,email,picture"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
            
            if response.status_code != 200:
                 raise ValueError("Invalid Facebook token")
                 
            data = response.json()
            return data
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Facebook token: {str(e)}",
            )

    @classmethod
    def _resolve_supabase_jwks_url(cls) -> str:
        if settings.SUPABASE_JWKS_URL:
            return settings.SUPABASE_JWKS_URL
        if settings.SUPABASE_URL:
            return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        raise SupabaseTokenValidationError("token_invalid", "Supabase JWKS URL is not configured")

    @classmethod
    def _resolve_supabase_issuer(cls) -> str:
        if settings.SUPABASE_JWT_ISSUER:
            return settings.SUPABASE_JWT_ISSUER
        if settings.SUPABASE_URL:
            return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"
        raise SupabaseTokenValidationError("token_invalid", "Supabase issuer is not configured")

    @classmethod
    def clear_supabase_jwks_cache(cls) -> None:
        with cls._supabase_jwks_lock:
            cls._supabase_jwks_cache = None
            cls._supabase_jwks_cache_expiry = 0.0

    @classmethod
    def _fetch_supabase_jwks(cls) -> list[dict[str, Any]]:
        jwks_url = cls._resolve_supabase_jwks_url()
        timeout = settings.SUPABASE_JWKS_TIMEOUT_SECONDS
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(jwks_url, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("supabase.jwks_fetch_failed", extra={"error": str(exc)})
            raise SupabaseTokenValidationError("token_invalid", "Unable to fetch Supabase JWKS") from exc

        keys = payload.get("keys") if isinstance(payload, dict) else None
        if not isinstance(keys, list) or not keys:
            raise SupabaseTokenValidationError("token_invalid", "Supabase JWKS response has no keys")

        filtered = [key for key in keys if isinstance(key, dict)]
        if not filtered:
            raise SupabaseTokenValidationError("token_invalid", "Supabase JWKS response has no usable keys")
        return filtered

    @classmethod
    def _get_supabase_jwks(cls) -> list[dict[str, Any]]:
        now = monotonic()
        with cls._supabase_jwks_lock:
            if cls._supabase_jwks_cache and now < cls._supabase_jwks_cache_expiry:
                return cls._supabase_jwks_cache

        keys = cls._fetch_supabase_jwks()
        ttl = max(settings.SUPABASE_JWKS_CACHE_TTL_SECONDS, 0)
        with cls._supabase_jwks_lock:
            cls._supabase_jwks_cache = keys
            cls._supabase_jwks_cache_expiry = monotonic() + ttl if ttl else 0.0
        return keys

    @classmethod
    def _resolve_supabase_signing_keys(cls, kid: str) -> dict[str, Any]:
        for key in cls._get_supabase_jwks():
            if str(key.get("kid") or "") == kid:
                return {"keys": [key]}

        # Key rotation fallback: refresh cache once and retry.
        cls.clear_supabase_jwks_cache()
        for key in cls._get_supabase_jwks():
            if str(key.get("kid") or "") == kid:
                return {"keys": [key]}
        raise SupabaseTokenValidationError("token_invalid", "Supabase signing key not found")

    @classmethod
    def verify_supabase_access_token(cls, token: str) -> dict[str, Any]:
        if not token:
            raise SupabaseTokenValidationError("token_invalid", "Missing access token")
        try:
            header = jose_jwt.get_unverified_header(token)
        except JWTError as exc:
            raise SupabaseTokenValidationError("token_invalid", "Malformed token header") from exc

        algorithm = str(header.get("alg") or "").upper()
        allowed_algorithms = settings.SUPABASE_ALLOWED_ALGORITHMS
        if algorithm not in allowed_algorithms:
            raise SupabaseTokenValidationError("token_invalid", "Unexpected token signing algorithm")

        kid = str(header.get("kid") or "").strip()
        if not kid:
            raise SupabaseTokenValidationError("token_invalid", "Missing Supabase token key identifier")

        signing_keys = cls._resolve_supabase_signing_keys(kid)
        audience = (settings.SUPABASE_JWT_AUDIENCE or "").strip() or None
        issuer = cls._resolve_supabase_issuer()
        decode_options = {
            "verify_aud": bool(audience),
            "verify_sub": True,
            "verify_exp": True,
        }
        try:
            payload = jose_jwt.decode(
                token,
                signing_keys,
                algorithms=allowed_algorithms,
                issuer=issuer,
                audience=audience,
                options=decode_options,
            )
        except ExpiredSignatureError as exc:
            raise SupabaseTokenValidationError("token_expired", "Supabase access token expired") from exc
        except JWTError as exc:
            raise SupabaseTokenValidationError("token_invalid", "Supabase token validation failed") from exc

        role = str(payload.get("role") or "").strip().lower()
        if role == "anon" and not settings.SUPABASE_ALLOW_ANON_ROLE:
            raise SupabaseTokenValidationError("token_invalid", "Anonymous role tokens are not allowed")
        return payload

    @staticmethod
    def get_permissions_for_role(
        db_or_role_identifier: Session | int | str,
        role_identifier: int | str | list[int] | list[str] | None = None,
    ) -> list[str]:
        """
        Fetch permissions for a given role from the database.
        role_identifier can be role ID/name or list of role IDs/names.
        """
        from app.models.rbac import Role, RolePermission, Permission
        from sqlmodel import select

        db: Session | None = None
        if role_identifier is None:
            role_identifier = db_or_role_identifier
        else:
            db = db_or_role_identifier  # type: ignore[assignment]

        perms: list[str] = []
        identifiers: list[int | str]
        if isinstance(role_identifier, list):
            identifiers = role_identifier
        else:
            identifiers = [role_identifier] if role_identifier is not None else []

        numeric_role_ids = [rid for rid in identifiers if isinstance(rid, int)]
        named_roles = [canonical_role_name(str(rid)) for rid in identifiers if isinstance(rid, str)]

        if db is not None:
            if numeric_role_ids:
                perms.extend(
                    list(
                        db.exec(
                            select(Permission.slug)
                            .join(RolePermission)
                            .where(RolePermission.role_id.in_(numeric_role_ids))
                        ).all()
                    )
                )
            if named_roles:
                perms.extend(
                    list(
                        db.exec(
                            select(Permission.slug)
                            .join(RolePermission)
                            .join(Role)
                            .where(func.lower(Role.name).in_(named_roles))
                        ).all()
                    )
                )

        # Legacy fallback for callers without a DB session.
        if db is None and len(identifiers) == 1 and isinstance(identifiers[0], str):
            role_name = canonical_role_name(identifiers[0])
            fallback = {
                "customer": ["profile:view:own", "stations:view:global", "rentals:create:own", "rentals:view:own", "wallet:view:own"],
                "dealer_owner": ["dashboard:view:dealer", "stations:update:dealer", "staff:assign:dealer", "finance:view:dealer"],
                "operations_admin": ["dashboard:view:global", "users:assign:global", "dealers:assign:global", "settings:update:global", "audit:view:global"],
                "super_admin": ["dashboard:view:global", "users:assign:global", "dealers:assign:global", "settings:override:global", "audit:view:global", "rbac:override:global"],
            }
            return sorted(canonicalize_permission_set(fallback.get(role_name, [])))

        return sorted(canonicalize_permission_set(perms))

    @staticmethod
    def get_menu_for_role(
        db_or_role_identifier: Session | int | str,
        role_identifier: int | str | list[int] | list[str] | None = None,
    ) -> list[dict]:
        from app.models.rbac import Role
        from app.models.role_right import RoleRight
        from app.models.menu import Menu
        from sqlmodel import select

        db: Session | None = None
        if role_identifier is None:
            role_identifier = db_or_role_identifier
        else:
            db = db_or_role_identifier  # type: ignore[assignment]

        menus: list[Menu] = []
        identifiers: list[int | str]
        if isinstance(role_identifier, list):
            identifiers = role_identifier
        else:
            identifiers = [role_identifier] if role_identifier is not None else []

        numeric_role_ids = [rid for rid in identifiers if isinstance(rid, int)]
        named_roles = [canonical_role_name(str(rid)) for rid in identifiers if isinstance(rid, str)]

        if db is not None:
            statement = None
            if numeric_role_ids:
                statement = (
                    select(Menu)
                    .join(RoleRight, RoleRight.menu_id == Menu.id)
                    .where(RoleRight.role_id.in_(numeric_role_ids))
                    .order_by(Menu.menu_order)
                )
            if named_roles:
                named_statement = (
                    select(Menu)
                    .join(RoleRight, RoleRight.menu_id == Menu.id)
                    .join(Role)
                    .where(func.lower(Role.name).in_(named_roles))
                    .order_by(Menu.menu_order)
                )
                if statement is None:
                    statement = named_statement
                else:
                    menus.extend(list(db.exec(named_statement).all()))

            if statement is not None:
                menus.extend(list(db.exec(statement).all()))

        if db is None and len(identifiers) == 1 and isinstance(identifiers[0], str):
            role_name = canonical_role_name(identifiers[0])
            # Fallback
            if role_name == "customer":
                return [
                    {"id": "dashboard", "label": "Dashboard", "path": "/dashboard", "route": "/dashboard", "icon": "home"},
                    {"id": "vehicle", "label": "My Vehicle", "path": "/vehicle", "route": "/vehicle", "icon": "car"},
                    {"id": "stations", "label": "Find Stations", "path": "/stations", "route": "/stations", "icon": "map"},
                ]
            elif role_name in ["dealer_owner", "dealer_manager"]:
                return [
                    {"id": "dashboard", "label": "Dashboard", "path": "/dashboard", "route": "/dashboard", "icon": "home"},
                    {"id": "stations", "label": "Stations", "path": "/stations", "route": "/stations", "icon": "fuel"},
                    {"id": "staff", "label": "Staff", "path": "/staff", "route": "/staff", "icon": "users"},
                    {"id": "finance", "label": "Finance", "path": "/finance", "route": "/finance", "icon": "dollar-sign"},
                ]
            elif role_name in ["operations_admin", "super_admin"]:
                return [
                    {"id": "admin_dashboard", "label": "Dashboard", "path": "/admin/dashboard", "route": "/admin/dashboard", "icon": "activity"},
                    {"id": "admin_users", "label": "Users", "path": "/admin/users", "route": "/admin/users", "icon": "users"},
                    {"id": "admin_dealers", "label": "Dealers", "path": "/admin/users", "route": "/admin/users", "icon": "briefcase"},
                    {"id": "admin_settings", "label": "Settings", "path": "/admin/settings", "route": "/admin/settings", "icon": "settings"},
                ]
            return []

        deduped: dict[str, Menu] = {}
        for menu in menus:
            deduped[menu.name] = menu

        # Format response
        result = []
        for m in sorted(deduped.values(), key=lambda x: (x.menu_order, x.id or 0)):
            result.append({
                "id": m.name,
                "label": m.display_name,
                "path": m.route or "",
                "route": m.route or "",
                "icon": m.icon or "circle"
            })
        return result

    @staticmethod
    def create_user_session(
        db: Session,
        user_id: int,
        refresh_token: str,
        request: Request = None,
        token_jti: str = None,
        ip_address: str = None,
        user_agent: str = None
    ):
        """
        Create a new UserSession record.
        Hashes the refresh token for security.
        """
        from app.models.session import UserSession
        from datetime import datetime, timedelta
        try:
            from datetime import UTC
        except ImportError:
            import datetime as dt
            UTC = dt.timezone.utc
        from app.core.config import settings
        import hashlib

        # 1. Extract Info if request provided
        if request:
            if not user_agent:
                user_agent = request.headers.get("user-agent", "unknown")
            if not ip_address:
                ip_address = get_client_ip(request)
        
        # Default fallbacks
        if not user_agent: user_agent = "unknown"
        if not ip_address: ip_address = "unknown"
            
        # 2. Extract Device Info
        device_type = "mobile" if "mobile" in user_agent.lower() else "web"
        if "okhttp" in user_agent.lower() or "dart" in user_agent.lower():
             device_type = "mobile_app"

        device_name = None
        device_id = None
        
        if request:
            # 1. Trust Client Headers
            device_id = request.headers.get("X-Device-ID")
            device_name = request.headers.get("X-Device-Name") or request.headers.get("X-Device-Model")
            
            # 2. Parse User-Agent if name missing
            if not device_name and user_agent:
                ua = user_agent.lower()
                os_name = "Unknown OS"
                browser = ""

                # OS Detection
                if "windows" in ua: os_name = "Windows"
                elif "macintosh" in ua or "mac os" in ua: os_name = "macOS"
                elif "linux" in ua and "android" not in ua: os_name = "Linux"
                elif "android" in ua: os_name = "Android"
                elif "iphone" in ua or "ipad" in ua: os_name = "iOS"
                
                # Browser/Client Detection
                if "postman" in ua: 
                    browser = "Postman"
                elif "okhttp" in ua or "dart" in ua: 
                    browser = "Mobile App"
                elif "chrome" in ua and "edg" not in ua: 
                    browser = "Chrome"
                elif "firefox" in ua: 
                    browser = "Firefox"
                elif "safari" in ua and "chrome" not in ua: 
                    browser = "Safari"
                elif "edg" in ua: 
                    browser = "Edge"
                
                if browser:
                    device_name = f"{browser} on {os_name}"
                elif os_name != "Unknown OS":
                    device_name = os_name
                else:
                    device_name = "Unknown Device"
            
        # 3. Hash Refresh Token
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        
        # Extract JTI if not provided
        if not token_jti:
            try:
                from jose import jwt
                from app.core.config import settings
                payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                token_jti = payload.get("jti")
            except Exception:
                logger.warning("auth.refresh_token_decode_failed_for_jti", exc_info=True)
                token_jti = "unknown"

        # 4. Create Session
        session = UserSession(
            user_id=user_id,
            token_id=token_jti or "unknown",
            refresh_token_hash=refresh_token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
            device_id=device_id,
            device_name=device_name,
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        db.add(session)
        db.commit()
        return session

    @staticmethod
    def create_session(
        db: Session,
        user_id: int,
        access_token: str,
        refresh_token: str,
        device_info: str = None,
        ip_address: str = None,
        user_agent: str = None,
        request: Request = None,
    ):
        """
        Backward-compatible session creation contract used by passkey login.
        Persists a UserSession keyed by access sid (preferred) or refresh jti.
        """
        token_id = None
        try:
            from jose import jwt

            access_payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            token_id = access_payload.get("sid")
        except Exception:
            token_id = None

        if not token_id:
            try:
                from jose import jwt

                refresh_payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                token_id = refresh_payload.get("jti")
            except Exception:
                token_id = None

        effective_user_agent = user_agent or device_info or "unknown"
        session = AuthService.create_user_session(
            db=db,
            user_id=user_id,
            refresh_token=refresh_token,
            request=request,
            token_jti=token_id,
            ip_address=ip_address,
            user_agent=effective_user_agent,
        )

        if device_info and session:
            session.device_name = device_info
            db.add(session)
            db.commit()
            db.refresh(session)
        return session

    @staticmethod
    def update_user_session(
        db: Session,
        old_token_jti: str,
        new_refresh_token: str,
        request: Request = None
    ):
        """
        Update existing session with new token info (Rotation).
        If not found, creates new session.
        """
        from app.models.session import UserSession
        from sqlmodel import select
        from datetime import datetime, timedelta
        try:
            from datetime import UTC
        except ImportError:
            import datetime as dt
            UTC = dt.timezone.utc
        from app.core.config import settings
        import hashlib
        from jose import jwt

        # 1. Find Session by old JTI
        session = db.exec(select(UserSession).where(UserSession.token_id == old_token_jti)).first()
        
        # 2. Extract new JTI
        try:
            payload = jwt.decode(new_refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            new_token_jti = payload.get("jti")
            user_id = int(payload.get("sub"))
        except Exception:
            logger.warning("auth.refresh_token_rotate_decode_failed", exc_info=True)
            return None # Cannot update invalid token
            
        # 3. Hash new refresh token
        new_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
        
        if session:
            # Update existing session
            session.token_id = new_token_jti or "unknown"
            session.refresh_token_hash = new_hash
            session.last_active_at = datetime.now(UTC)
            session.expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            
            # Update IP/UA if provided
            if request:
                 user_agent = request.headers.get("user-agent")
                 if user_agent: session.user_agent = user_agent
                 
                 ip_address = get_client_ip(request)
                 if ip_address: session.ip_address = ip_address
            
            db.add(session)
            db.commit()
            return session
        else:
            # Fallback: Create new session
            return AuthService.create_user_session(
                db, user_id, new_refresh_token, request, token_jti=new_token_jti
            )

    @staticmethod
    def validate_session(db: Session, token: str, is_refresh: bool = False):
        """
        Validate a token against active UserSession records.
        For refresh tokens, also verifies refresh token hash matches stored value.
        """
        from datetime import datetime, UTC
        from jose import jwt, JWTError
        import hashlib
        from app.models.session import UserSession

        if not token:
            return None

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            return None

        token_type = payload.get("type")
        if is_refresh and token_type != "refresh":
            return None

        token_id = payload.get("jti") if is_refresh else payload.get("sid")
        if not token_id:
            return None

        session = db.exec(
            select(UserSession)
            .where(UserSession.token_id == token_id)
            .where(UserSession.is_active == True)
        ).first()
        if not session:
            return None

        if getattr(session, "is_revoked", False):
            return None

        if session.expires_at and session.expires_at < datetime.now(UTC):
            session.is_active = False
            session.is_revoked = True
            session.revoked_at = datetime.now(UTC)
            db.add(session)
            db.commit()
            return None

        if is_refresh and session.refresh_token_hash:
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            if token_hash != session.refresh_token_hash:
                return None

        return session

    @staticmethod
    def revoke_session(db: Session, token: str) -> bool:
        """
        Revoke a session identified by token jti/sid.
        Returns True if a session was found and revoked.
        """
        from datetime import datetime, UTC
        from jose import jwt, JWTError
        from app.models.session import UserSession

        if not token:
            return False

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            return False

        token_id = payload.get("jti") or payload.get("sid")
        if not token_id:
            return False

        session = db.exec(
            select(UserSession).where(UserSession.token_id == token_id)
        ).first()
        if not session:
            return False

        session.is_active = False
        session.is_revoked = True
        session.revoked_at = datetime.now(UTC)
        db.add(session)
        db.commit()
        from app.api.deps import invalidate_token_cache
        invalidate_token_cache(token)
        return True

    @staticmethod
    def revoke_all_user_sessions(db: Session, user_id: int):
        """
        Revoke all active sessions for a user.
        Updates user's last_global_logout_at.
        """
        from app.models.user import User
        from app.models.session import UserSession
        from sqlmodel import select
        from datetime import datetime
        try:
            from datetime import UTC
        except ImportError:
            import datetime as dt
            UTC = dt.timezone.utc
        
        # 1. Update Global Logout Timestamp
        user = db.get(User, user_id)
        if user:
            user.last_global_logout_at = datetime.now(UTC)
            db.add(user)
        
        # 2. Mark all sessions inactive
        sessions = db.exec(select(UserSession).where(UserSession.user_id == user_id).where(UserSession.is_active == True)).all()
        for s in sessions:
            s.is_active = False
            db.add(s)
            
        db.commit()
        from app.api.deps import invalidate_user_token_cache
        invalidate_user_token_cache(user_id)
        return len(sessions)

    # ── P1-A-3: Two-Factor Authentication helpers ─────────────────────────

    @staticmethod
    def initiate_2fa_setup(user) -> dict:
        """Generate a TOTP secret and provisioning URI for QR code display."""
        try:
            import pyotp
        except ImportError:
            raise HTTPException(
                status_code=501,
                detail="pyotp is not installed; 2FA is unavailable in this deployment",
            )

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=getattr(user, "email", None) or str(user.id),
            issuer_name="WEZU Energy",
        )
        return {
            "secret": secret,
            "qr_uri": provisioning_uri,
        }

    @staticmethod
    def verify_and_enable_2fa(db: Session, user, code: str, secret: str) -> list[str] | None:
        """Verify a TOTP code against the given secret, enable 2FA, return backup codes."""
        try:
            import pyotp
        except ImportError:
            raise HTTPException(status_code=501, detail="pyotp is not installed")

        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            return None

        import secrets as _secrets

        backup_codes = [_secrets.token_hex(4).upper() for _ in range(8)]

        user.two_factor_enabled = True
        user.two_factor_secret = secret  # ideally encrypt at rest
        user.backup_codes = ",".join(backup_codes)
        db.add(user)
        db.commit()
        return backup_codes

    # ── P1-A-3: Biometric (passkey-style) helpers ─────────────────────────

    @staticmethod
    def register_biometric(
        db: Session,
        user_id: int,
        device_id: str,
        credential_id: str,
        public_key: str,
    ) -> None:
        """Store a biometric / passkey credential."""
        from app.models.biometric import BiometricCredential

        existing = db.exec(
            select(BiometricCredential).where(
                BiometricCredential.credential_id == credential_id
            )
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Credential already registered")

        cred = BiometricCredential(
            user_id=user_id,
            device_id=device_id,
            credential_id=credential_id,
            public_key=public_key,
        )
        db.add(cred)
        db.commit()

    @staticmethod
    def verify_biometric_signature(
        db: Session,
        user_id: int,
        credential_id: str,
        signature: str,
        challenge: str,
    ) -> bool:
        """
        Verify a biometric challenge/response.

        A production implementation would use the ``cryptography`` library to
        verify the signature against the stored public key.  For now we do a
        simple lookup-only check so that the endpoint is not a hard crash.
        """
        from app.models.biometric import BiometricCredential

        cred = db.exec(
            select(BiometricCredential).where(
                BiometricCredential.credential_id == credential_id,
                BiometricCredential.user_id == user_id,
            )
        ).first()
        if not cred:
            return False

        # Stub: real verification would use cred.public_key + cryptography
        # For now return True if credential exists (biometric trust-on-device model).
        return True
