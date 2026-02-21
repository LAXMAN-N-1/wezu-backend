from google.oauth2 import id_token
from google.auth.transport import requests
from app.core.config import settings
from fastapi import HTTPException, status
from sqlmodel import Session, select
from app.models.user import User
from app.models.biometric import BiometricCredential
from app.core.security import generate_totp_secret, verify_totp, generate_backup_codes, generate_qr_uri
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, ec
from cryptography.hazmat.primitives import serialization
import pyotp
import logging
import base64

logger = logging.getLogger(__name__)

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

    # --- 2FA Logic ---
    @staticmethod
    def initiate_2fa_setup(user: User):
        """Generates secret and QR URI for 2FA setup"""
        secret = generate_totp_secret()
        qr_uri = generate_qr_uri(user.email or user.phone_number, secret)
        return {"secret": secret, "qr_uri": qr_uri}

    @staticmethod
    def verify_and_enable_2fa(db: Session, user: User, code: str, secret: str):
        """Verifies initial 2FA code and enables it for user"""
        if verify_totp(secret, code):
            user.two_factor_enabled = True
            user.two_factor_secret = secret
            user.backup_codes = generate_backup_codes()
            db.add(user)
            db.commit()
            db.refresh(user)
            return user.backup_codes
        return None

    @staticmethod
    def verify_2fa_login(user: User, code: str) -> bool:
        """Verify 2FA code during login process"""
        if not user.two_factor_enabled or not user.two_factor_secret:
            return True # Not enabled
        
        # Check backup codes first
        if user.backup_codes and code in user.backup_codes:
            user.backup_codes.remove(code)
            # db.add(user) # Needs session from caller or internal commit
            return True
            
        return verify_totp(user.two_factor_secret, code)

    # --- Biometric Logic ---
    @staticmethod
    def register_biometric(db: Session, user_id: int, device_id: str, credential_id: str, public_key: str):
        """Register a new biometric public key"""
        # Deactivate old credentials for this user/device if needed
        # ...
        
        cred = BiometricCredential(
            user_id=user_id,
            device_id=device_id,
            credential_id=credential_id,
            public_key=public_key
        )
        db.add(cred)
        db.commit()
        db.refresh(cred)
        return cred

    @staticmethod
    def verify_biometric_signature(db: Session, user_id: int, credential_id: str, signature: str, challenge: str):
        """Verify signed challenge using stored public key (Production Ready)"""
        statement = select(BiometricCredential).where(
            BiometricCredential.user_id == user_id,
            BiometricCredential.credential_id == credential_id
        )
        cred = db.exec(statement).first()
        if not cred:
            return False
            
        try:
            # 1. Decode public key and signature
            # Public key is expected to be PEM or DER encoded Base64
            public_key_bytes = base64.b64decode(cred.public_key)
            signature_bytes = base64.b64decode(signature)
            challenge_bytes = challenge.encode('utf-8')
            
            # 2. Load public key (assuming ECDSA/P-256 which is standard for WebAuthn)
            # Try loading as SubjectPublicKeyInfo (DER) first
            try:
                public_key = serialization.load_der_public_key(public_key_bytes)
            except:
                public_key = serialization.load_pem_public_key(public_key_bytes)
            
            # 3. Verify signature
            if isinstance(public_key, ec.EllipticCurvePublicKey):
                public_key.verify(signature_bytes, challenge_bytes, ec.ECDSA(hashes.SHA256()))
                return True
            
            # Fallback for RSA if needed
            public_key.verify(
                signature_bytes,
                challenge_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
            
        except Exception as e:
            logger.error(f"BIOMETRIC_VERIFICATION_FAILED: {str(e)}")
            return False

    @staticmethod
    def revoke_all_user_sessions(db: Session, user_id: int):
        """Revoke all active sessions for a user (called on deletion/password change)"""
        from app.models.session import UserSession
        statement = select(UserSession).where(UserSession.user_id == user_id, UserSession.is_active == True)
        sessions = db.exec(statement).all()
        for session in sessions:
            session.is_active = False
            session.is_revoked = True
            db.add(session)
        db.commit()
