from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class BiometricCredential(SQLModel, table=True):
    __tablename__ = "biometric_credentials"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    device_id: str = Field(index=True) # Mobile Device ID
    
    credential_id: str = Field(unique=True, index=True)
    public_key: str # Base64 encoded public key
    
    friendly_name: Optional[str] = Field(default="My Device") # e.g. "iPhone 15 Pro"
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
