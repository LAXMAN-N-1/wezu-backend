from google.oauth2 import id_token
from google.auth.transport import requests
from app.core.config import settings
from fastapi import HTTPException, status

class AuthService:
    @staticmethod
    def verify_google_token(token: str):
        try:
            # Specify the CLIENT_ID of the app that accesses the backend:
            idinfo = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                settings.GOOGLE_OAUTH_CLIENT_ID
            )

            # ID token is valid. Get the user's Google Account ID from the decoded token.
            return idinfo
        except ValueError:
            # Invalid token
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token",
            )

    @staticmethod
    def verify_apple_token(token: str):
        try:
            # Apple Sign-In token verification logic
            # Final implementation requires apple-id-token or manual JWT verification
            # against Apple's public keys at https://appleid.apple.com/auth/keys
            payload = jwt.get_unverified_claims(token)
            return payload
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Apple token",
            )
