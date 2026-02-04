from datetime import datetime
from jose import jwt
from sqlmodel import Session
from app.models.oauth import BlacklistedToken
from app.core.config import settings

class TokenService:
    @staticmethod
    def blacklist_token(db: Session, token: str):
        """Add token to blacklist"""
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            exp = payload.get("exp")
            if exp:
                expires_at = datetime.fromtimestamp(exp)
            else:
                expires_at = datetime.utcnow() # Fallback
            
            # Check if already blacklisted to avoid unique constraint error
            existing = db.query(BlacklistedToken).filter(BlacklistedToken.token == token).first()
            if not existing:
                blacklisted = BlacklistedToken(
                    token=token,
                    expires_at=expires_at
                )
                db.add(blacklisted)
                db.commit()
        except Exception:
            # If token is already invalid, just ignore
            pass

    @staticmethod
    def cleanup_expired_tokens(db: Session):
        """Remove tokens from blacklist that have already expired in time"""
        db.query(BlacklistedToken).filter(BlacklistedToken.expires_at < datetime.utcnow()).delete()
        db.commit()
