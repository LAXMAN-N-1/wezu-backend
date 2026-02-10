from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    email: Optional[str] = Field(default=None, index=True, unique=True)
    phone_number: Optional[str] = Field(default=None, index=True, unique=True)
    full_name: Optional[str] = None
    hashed_password: Optional[str] = None
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    
    role_id: Optional[int] = Field(default=None, foreign_key="roles.id")
    
    # OAuth specific
    google_id: Optional[str] = Field(default=None, index=True)
    apple_id: Optional[str] = Field(default=None, index=True)
    profile_picture: Optional[str] = None
    
    # Profile & KYC
    address: Optional[str] = None
    kyc_status: str = Field(default="verified") # pending, verified, rejected (Default 'verified' for development)
    aadhaar_number: Optional[str] = None
    pan_number: Optional[str] = None
    kyc_video_url: Optional[str] = None
    utility_bill_url: Optional[str] = None
    
    # Consent
    consent_captured: bool = Field(default=False)
    consent_date: Optional[datetime] = None

    # Security
    two_factor_enabled: bool = Field(default=False)
    biometric_login_enabled: bool = Field(default=False)
    security_question: Optional[str] = None
    security_answer: Optional[str] = None
    reset_token: Optional[str] = Field(default=None, index=True)
    reset_token_expires: Optional[datetime] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship
    role: Optional["Role"] = Relationship(back_populates="users")
    wallet: Optional["Wallet"] = Relationship(back_populates="user")
    addresses: List["Address"] = Relationship(back_populates="user")
    kyc_documents: List["KYCDocument"] = Relationship(back_populates="user")
    devices: List["Device"] = Relationship(back_populates="user")
    dealer_profile: Optional["DealerProfile"] = Relationship(back_populates="user")
    driver_profile: Optional["DriverProfile"] = Relationship(back_populates="user")

# OTP class removed (moved to app/models/otp.py)

class Token(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Optional[User] = None

class TokenPayload(SQLModel):
    sub: Optional[str] = None
