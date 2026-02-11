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
        if role_name == "customer":
            return ["vehicle:read", "station:read"]
        elif role_name in ["vendor_owner", "dealer"]:
            return ["station:create", "staff:create", "finance:read"]
        elif role_name in ["admin", "super_admin"]:
            return ["all"]
        return []

    @staticmethod
    def get_menu_for_role(role_name: str) -> list[dict]:
        # Avoiding circular import by returning dicts or importing locally if needed
        # But returning dicts is safer for service layer decoupling if schema isn't strictly needed here 
        # However, for type safety let's use the schema if possible, but for now dicts are fine as they serialize to JSON
        if role_name == "customer":
            return [
                {"label": "Dashboard", "path": "/dashboard", "icon": "home"},
                {"label": "My Vehicle", "path": "/vehicle", "icon": "car"},
                {"label": "Find Stations", "path": "/stations", "icon": "map"},
            ]
        elif role_name in ["vendor_owner", "dealer"]:
            return [
                {"label": "Dashboard", "path": "/dashboard", "icon": "home"},
                {"label": "Stations", "path": "/stations", "icon": "fuel"},
                {"label": "Staff", "path": "/staff", "icon": "users"},
                {"label": "Finance", "path": "/finance", "icon": "dollar-sign"},
            ]
        elif role_name in ["admin", "super_admin"]:
            return [
                {"label": "Dashboard", "path": "/admin/dashboard", "icon": "activity"},
                {"label": "Users", "path": "/admin/users", "icon": "users"},
                {"label": "Dealers", "path": "/admin/users", "icon": "briefcase"},
                {"label": "Settings", "path": "/admin/settings", "icon": "settings"},
            ]
        return []
