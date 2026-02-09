from sqlmodel import SQLModel, Field, Relationship
from app.models.rbac import UserRole
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.financial import Wallet
    from app.models.location import Address
    from app.models.kyc import KYCDocument
    from app.models.iot import Device
    from app.models.vehicle import Vehicle
    from app.models.dealer import DealerProfile
    from app.models.driver_profile import DriverProfile
    from app.models.staff import StaffProfile
    from app.models.staff import StaffProfile
    from app.models.rbac import Role, UserAccessPath
    from app.models.session import UserSession

class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    email: Optional[str] = Field(default=None, index=True, unique=True)
    phone_number: Optional[str] = Field(default=None, index=True, unique=True)
    full_name: Optional[str] = None
    hashed_password: Optional[str] = None
    is_active: bool = Field(default=True)
    status: str = Field(default="active") # active, suspended, banned
    is_superuser: bool = Field(default=False)
    tenant_id: Optional[str] = Field(default="default", index=True)

    
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
    kyc_rejection_reason: Optional[str] = None # Reason for overall rejection
    
    # Contact & Preferences
    emergency_contact: Optional[str] = None  # Emergency contact phone/name
    notification_preferences: Optional[str] = None  # JSON string: {"push": true, "email": true, "sms": false}
    
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
    reset_token_expires: Optional[datetime] = None
    last_global_logout_at: Optional[datetime] = None
    last_login: Optional[datetime] = Field(default=None, index=True)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Soft Delete
    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = None

    # Relationship
    wallet: Optional["Wallet"] = Relationship(back_populates="user")
    addresses: List["Address"] = Relationship(back_populates="user")
    kyc_documents: List["KYCDocument"] = Relationship(back_populates="user")
    devices: List["Device"] = Relationship(back_populates="user")
    vehicles: List["Vehicle"] = Relationship(back_populates="user")
    dealer_profile: Optional["DealerProfile"] = Relationship(back_populates="user")
    driver_profile: Optional["DriverProfile"] = Relationship(back_populates="user")
    staff_profile: Optional["StaffProfile"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"foreign_keys": "[StaffProfile.user_id]"}
    )
    
    # RBAC
    roles: List["Role"] = Relationship(back_populates="users", link_model=UserRole)
    
    # Sessions
    sessions: List["UserSession"] = Relationship(back_populates="user")

    # Access Paths
    access_paths: List["UserAccessPath"] = Relationship(back_populates="user")

# OTP class removed (moved to app/models/otp.py)

class Token(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Optional[User] = None

class TokenPayload(SQLModel):
    sub: Optional[str] = None
