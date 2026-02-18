from google.oauth2 import id_token
from google.auth.transport import requests
from app.core.config import settings
from fastapi import HTTPException, status

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
    def get_permissions_for_role(db: Session, role_id: int) -> list[str]:
        from app.services.rbac_service import rbac_service
        permissions = rbac_service.get_user_permissions(db, role_id)
        if not permissions and role_id:
             # Development fallback or logging
             pass
        return permissions

    @staticmethod
    def get_menu_for_role(db: Session, role_id: int) -> list[dict]:
        from app.services.rbac_service import rbac_service
        menu = rbac_service.get_menu_for_role(db, role_id)
        if not menu and role_id:
            # Development fallback for customer if data missing
            from app.models.rbac import Role
            role = db.get(Role, role_id)
            if role and role.name == "customer":
                return [
                    {"label": "Dashboard", "path": "/dashboard", "icon": "home"},
                    {"label": "My Vehicle", "path": "/vehicle", "icon": "car"},
                    {"label": "Find Stations", "path": "/stations", "icon": "map"},
                ]
        return menu

    @staticmethod
    def create_session(
        db, 
        user_id: int, 
        access_token: str, 
        refresh_token: str, 
        device_info: str = None, 
        ip_address: str = None
    ):
        from app.models.session import UserSession
        from datetime import datetime, timedelta
        
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        session = UserSession(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            device_type=device_info,
            ip_address=ip_address,
            expires_at=expires_at
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def revoke_session(db, token: str):
        from app.models.session import UserSession
        from datetime import datetime
        
        session = db.query(UserSession).filter(
            (UserSession.access_token == token) | (UserSession.refresh_token == token)
        ).first()
        
        if session:
            session.is_revoked = True
            session.revoked_at = datetime.utcnow()
            session.is_active = False
            db.add(session)
            db.commit()
            return True
        return False

    @staticmethod
    def validate_session(db, token: str, is_refresh: bool = False):
        from app.models.session import UserSession
        from datetime import datetime
        
        query = db.query(UserSession).filter(
            UserSession.is_revoked == False,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        )
        
        if is_refresh:
            session = query.filter(UserSession.refresh_token == token).first()
        else:
            session = query.filter(UserSession.access_token == token).first()
            
        if session:
            session.last_active_at = datetime.utcnow()
            db.add(session)
            db.commit()
            return session
        return None
