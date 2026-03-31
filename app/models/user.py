from sqlmodel import SQLModel, Field, Relationship
from app.models.kyc import KYCRecord
from app.models.rbac import UserRole
from app.models.two_factor_auth import TwoFactorAuth

from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from enum import Enum
import sqlalchemy as sa

from app.models.two_factor_auth import TwoFactorAuth

if TYPE_CHECKING:
    from app.models.session import UserSession
    from app.models.financial import Wallet
    from app.models.location import Address
    from app.models.kyc import KYCDocument, KYCRecord
    from app.models.iot import Device
    from app.models.vehicle import Vehicle
    from app.models.dealer import DealerProfile
    from app.models.driver_profile import DriverProfile
    from app.models.staff import StaffProfile
    from app.models.rbac import Role, UserAccessPath
    from app.models.token import SessionToken

class UserType(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    DEALER = "dealer"
    SUPPORT_AGENT = "support_agent"
    LOGISTICS = "logistics"

class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"
    DELETED = "deleted"

class KYCStatus(str, Enum):
    NOT_SUBMITTED = "not_submitted"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class User(SQLModel, table=True):

    __tablename__ = "users"
    __table_args__ = {"schema": "core"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Core Identity
    phone_number: str = Field(unique=True, index=True)
    email: Optional[str] = Field(default=None, unique=True, index=True)
    full_name: Optional[str] = None
    hashed_password: Optional[str] = None
    
    # Classification
    user_type: UserType = Field(default=UserType.CUSTOMER, index=True)
    status: UserStatus = Field(default=UserStatus.ACTIVE, index=True)
    is_superuser: bool = Field(default=False)
    role_id: Optional[int] = Field(default=None, foreign_key="core.roles.id")
    
    # Profile & Media
    profile_picture: Optional[str] = None
    
    # KYC
    kyc_status: KYCStatus = Field(default=KYCStatus.NOT_SUBMITTED, index=True)
    kyc_rejection_reason: Optional[str] = None

    # OAuth
    google_id: Optional[str] = Field(default=None, index=True)
    apple_id: Optional[str] = Field(default=None, index=True)

    # Security
    two_factor_enabled: bool = Field(default=False)
    two_factor_secret: Optional[str] = None
    backup_codes: Optional[List[str]] = Field(default=None, sa_column=sa.Column(sa.JSON))
    
    # Email Verification
    is_email_verified: bool = Field(default=False)
    email_verification_token: Optional[str] = None
    email_verification_sent_at: Optional[datetime] = None
    
    last_login_at: Optional[datetime] = None
    last_global_logout_at: Optional[datetime] = None
    
    # Soft Delete
    is_deleted: bool = Field(default=False)
    deletion_reason: Optional[str] = None
    deleted_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user_profile: Optional["UserProfile"] = Relationship(back_populates="user")
    role: Optional["Role"] = Relationship(back_populates="users")
    
    # Legacy Relationships (To be refactored or kept for backward compat initially)
    wallet: Optional["Wallet"] = Relationship(back_populates="user")
    addresses: List["Address"] = Relationship(back_populates="user")
    
    # Fix for ambiguous foreign keys: explicitly specify which FK on KYCDocument to use.
    kyc_documents: List["KYCDocument"] = Relationship(
        back_populates="user", 
        sa_relationship_kwargs={"foreign_keys": "[KYCDocument.user_id]"}
    )
    
    kyc_records: List["KYCRecord"] = Relationship(back_populates="user", sa_relationship_kwargs={"foreign_keys": "[KYCRecord.user_id]"})
    devices: List["Device"] = Relationship(back_populates="user")
    vehicles: List["Vehicle"] = Relationship(back_populates="user")
    dealer_profile: Optional["DealerProfile"] = Relationship(back_populates="user")
    driver_profile: Optional["DriverProfile"] = Relationship(back_populates="user")
    staff_profile: Optional["StaffProfile"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"foreign_keys": "[StaffProfile.user_id]"}
    )
    membership: Optional["UserMembership"] = Relationship(back_populates="user")
    
    transactions: List["Transaction"] = Relationship(back_populates="user")
    rentals: List["Rental"] = Relationship(back_populates="user")
    delivery_orders: List["DeliveryOrder"] = Relationship(back_populates="driver")
    
    access_paths: List["UserAccessPath"] = Relationship(back_populates="user")
    sessions: List["UserSession"] = Relationship(back_populates="user")
    session_tokens: List["SessionToken"] = Relationship(back_populates="user")
    two_factor_auth: Optional["TwoFactorAuth"] = Relationship(back_populates="user")

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    @is_active.setter
    def is_active(self, value: bool):
        self.status = UserStatus.ACTIVE if value else UserStatus.SUSPENDED
