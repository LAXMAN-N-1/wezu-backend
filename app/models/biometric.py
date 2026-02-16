"""
Biometric Authentication Models
Support for fingerprint and face recognition login
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
from enum import Enum

class BiometricType(str, Enum):
    FINGERPRINT = "FINGERPRINT"
    FACE_ID = "FACE_ID"
    IRIS = "IRIS"

class BiometricToken(SQLModel, table=True):
    """Biometric authentication tokens"""
    __tablename__ = "biometric_tokens"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    device_id: str = Field(index=True)
    biometric_type: str  # FINGERPRINT, FACE_ID
    public_key: str  # Device public key for verification
    token_hash: str  # Hashed biometric token
    is_active: bool = Field(default=True)
    last_used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Metadata
    device_name: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None


