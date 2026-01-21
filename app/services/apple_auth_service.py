"""
Apple Sign-In Authentication Service
Handles Apple OAuth authentication for customer app
"""
import jwt
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class AppleAuthService:
    """Apple Sign-In authentication service"""
    
    APPLE_PUBLIC_KEYS_URL = "https://appleid.apple.com/auth/keys"
    APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
    APPLE_ISSUER = "https://appleid.apple.com"
    
    @staticmethod
    def verify_identity_token(identity_token: str) -> Optional[Dict]:
        """
        Verify Apple identity token
        
        Args:
            identity_token: JWT token from Apple Sign-In
            
        Returns:
            Decoded token payload if valid, None otherwise
        """
        try:
            # Get Apple's public keys
            response = requests.get(AppleAuthService.APPLE_PUBLIC_KEYS_URL)
            apple_keys = response.json()
            
            # Decode token header to get key ID
            unverified_header = jwt.get_unverified_header(identity_token)
            key_id = unverified_header.get('kid')
            
            # Find matching public key
            public_key = None
            for key in apple_keys['keys']:
                if key['kid'] == key_id:
                    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                    break
            
            if not public_key:
                logger.error("Apple public key not found")
                return None
            
            # Verify and decode token
            decoded = jwt.decode(
                identity_token,
                public_key,
                algorithms=['RS256'],
                audience=settings.APPLE_CLIENT_ID,
                issuer=AppleAuthService.APPLE_ISSUER
            )
            
            return decoded
            
        except jwt.ExpiredSignatureError:
            logger.error("Apple token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid Apple token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Apple token verification failed: {str(e)}")
            return None
    
    @staticmethod
    def generate_client_secret() -> str:
        """
        Generate client secret for Apple Sign-In
        Required for server-to-server authentication
        
        Returns:
            JWT client secret
        """
        try:
            # Load private key
            with open(settings.APPLE_PRIVATE_KEY_PATH, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                    backend=default_backend()
                )
            
            # Create JWT
            headers = {
                'kid': settings.APPLE_KEY_ID,
                'alg': 'ES256'
            }
            
            payload = {
                'iss': settings.APPLE_TEAM_ID,
                'iat': datetime.utcnow(),
                'exp': datetime.utcnow() + timedelta(days=180),  # Max 6 months
                'aud': AppleAuthService.APPLE_ISSUER,
                'sub': settings.APPLE_CLIENT_ID
            }
            
            client_secret = jwt.encode(
                payload,
                private_key,
                algorithm='ES256',
                headers=headers
            )
            
            return client_secret
            
        except Exception as e:
            logger.error(f"Failed to generate Apple client secret: {str(e)}")
            raise
    
    @staticmethod
    def exchange_authorization_code(authorization_code: str) -> Optional[Dict]:
        """
        Exchange authorization code for tokens
        
        Args:
            authorization_code: Authorization code from Apple
            
        Returns:
            Token response with access_token, refresh_token, id_token
        """
        try:
            client_secret = AppleAuthService.generate_client_secret()
            
            data = {
                'client_id': settings.APPLE_CLIENT_ID,
                'client_secret': client_secret,
                'code': authorization_code,
                'grant_type': 'authorization_code'
            }
            
            response = requests.post(
                AppleAuthService.APPLE_TOKEN_URL,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Apple token exchange failed: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Apple authorization code exchange failed: {str(e)}")
            return None
    
    @staticmethod
    def revoke_token(token: str, token_type: str = 'access_token') -> bool:
        """
        Revoke Apple token
        
        Args:
            token: Token to revoke
            token_type: 'access_token' or 'refresh_token'
            
        Returns:
            True if successful
        """
        try:
            client_secret = AppleAuthService.generate_client_secret()
            
            data = {
                'client_id': settings.APPLE_CLIENT_ID,
                'client_secret': client_secret,
                'token': token,
                'token_type_hint': token_type
            }
            
            response = requests.post(
                'https://appleid.apple.com/auth/revoke',
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Apple token revocation failed: {str(e)}")
            return False
