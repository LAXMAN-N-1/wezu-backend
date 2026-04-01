from google.oauth2 import id_token
from google.auth.transport import requests
from app.core.config import settings
from app.core.proxy import get_client_ip
from fastapi import HTTPException, status, Request
from sqlmodel import Session, select

class AuthService:
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
            # In development, if APPLE_CLIENT_ID is not set, allow unverified for testing (CAUTION)
            if settings.ENVIRONMENT != "production" and not settings.APPLE_CLIENT_ID:
                from jose import jwt as jose_jwt
                return jose_jwt.get_unverified_claims(token)
                
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Apple token: {str(e)}",
            )

    @staticmethod
    @staticmethod
    async def verify_facebook_token(token: str):
        try:
            import httpx
            
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

    @staticmethod
    def get_permissions_for_role(role_name: str) -> list[str]:
        """
        Return default permission slugs for the given role.
        Kept lightweight to avoid login hard-failing if RBAC seed data is incomplete.
        """
        role_permissions = {
            "customer": [
                "profile:read:own",
                "profile:update:own",
                "stations:view:all",
                "rentals:create:own",
                "rentals:view:own",
                "wallet:view:own",
            ],
            "vendor_owner": [
                "dashboard:view:own",
                "stations:manage:own",
                "staff:manage:own",
                "finance:view:own",
            ],
            "dealer": [
                "dashboard:view:own",
                "stations:manage:own",
                "staff:manage:own",
                "finance:view:own",
            ],
            "admin": [
                "dashboard:view:all",
                "users:manage:all",
                "dealers:manage:all",
                "settings:manage:all",
                "audit:read:all",
            ],
            "super_admin": [
                "dashboard:view:all",
                "users:manage:all",
                "dealers:manage:all",
                "settings:manage:all",
                "audit:read:all",
                "rbac:manage:all",
            ],
        }
        return role_permissions.get(role_name, [])

    @staticmethod
    def get_menu_for_role(role_name: str) -> list[dict]:
        # Avoiding circular import by returning dicts or importing locally if needed
        # But returning dicts is safer for service layer decoupling if schema isn't strictly needed here 
        # However, for type safety let's use the schema if possible, but for now dicts are fine as they serialize to JSON
        if role_name == "customer":
            return [
                {"id": "dashboard", "label": "Dashboard", "path": "/dashboard", "route": "/dashboard", "icon": "home"},
                {"id": "vehicle", "label": "My Vehicle", "path": "/vehicle", "route": "/vehicle", "icon": "car"},
                {"id": "stations", "label": "Find Stations", "path": "/stations", "route": "/stations", "icon": "map"},
            ]
        elif role_name in ["vendor_owner", "dealer"]:
            return [
                {"id": "dashboard", "label": "Dashboard", "path": "/dashboard", "route": "/dashboard", "icon": "home"},
                {"id": "stations", "label": "Stations", "path": "/stations", "route": "/stations", "icon": "fuel"},
                {"id": "staff", "label": "Staff", "path": "/staff", "route": "/staff", "icon": "users"},
                {"id": "finance", "label": "Finance", "path": "/finance", "route": "/finance", "icon": "dollar-sign"},
            ]
        elif role_name in ["admin", "super_admin"]:
            return [
                {"id": "admin_dashboard", "label": "Dashboard", "path": "/admin/dashboard", "route": "/admin/dashboard", "icon": "activity"},
                {"id": "admin_users", "label": "Users", "path": "/admin/users", "route": "/admin/users", "icon": "users"},
                {"id": "admin_dealers", "label": "Dealers", "path": "/admin/users", "route": "/admin/users", "icon": "briefcase"},
                {"id": "admin_settings", "label": "Settings", "path": "/admin/settings", "route": "/admin/settings", "icon": "settings"},
            ]
        return []

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
        return len(sessions)
