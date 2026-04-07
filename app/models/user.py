from sqlmodel import SQLModel, Field, Relationship
# NOTE: These eager imports are REQUIRED for SQLAlchemy mapper registration.
# The models below define tables referenced by User's Relationship() declarations.
# Without them, SQLAlchemy cannot resolve back_populates at class-init time.
from app.models.kyc import KYCRecord, KYCDocument
from app.models.rbac import UserRole
from app.models.two_factor_auth import TwoFactorAuth
from app.models.device import Device
from app.models.dealer import DealerProfile
from app.models.staff import StaffProfile

from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, UTC
from enum import Enum
import sqlalchemy as sa

if TYPE_CHECKING:
    from app.models.session import UserSession
    from app.models.financial import Wallet
    from app.models.location import Address
    from app.models.vehicle import Vehicle
    from app.models.driver_profile import DriverProfile
    from app.models.rbac import Role, UserAccessPath
    from app.models.token import SessionToken
    from app.models.notification_preference import NotificationPreference

class UserType(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    DEALER = "dealer"
    DEALER_STAFF = "dealer_staff"
    SUPPORT_AGENT = "support_agent"
    LOGISTICS = "logistics"

class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"
    PENDING = "pending"
    INACTIVE = "inactive"
    VERIFIED = "verified"
    DELETED = "deleted"

class KYCStatus(str, Enum):
    NOT_SUBMITTED = "not_submitted"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class User(SQLModel, table=True):

    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Core Identity
    phone_number: Optional[str] = Field(default=None, unique=True, index=True)
    email: Optional[str] = Field(default=None, unique=True, index=True)
    full_name: Optional[str] = None
    hashed_password: Optional[str] = None
    
    # Classification
    user_type: UserType = Field(default=UserType.CUSTOMER, index=True)
    status: UserStatus = Field(default=UserStatus.ACTIVE, index=True)
    is_superuser: bool = Field(default=False)
    role_id: Optional[int] = Field(default=None, foreign_key="roles.id")
    
    # Dealer Staff Scoping
    created_by_dealer_id: Optional[int] = Field(default=None, foreign_key="dealer_profiles.id", index=True)
    created_by_user_id: Optional[int] = Field(default=None)  # Which admin created this user
    
    # Invite Flow
    invite_token: Optional[str] = Field(default=None, index=True)
    invite_token_expires: Optional[datetime] = None
    invite_sent_at: Optional[datetime] = None
    
    # Staff Metadata
    department: Optional[str] = None
    notes_internal: Optional[str] = None  # Admin-only notes, never shown to user
    
    # Brute Force Protection
    failed_login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = None
    
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
    biometric_login_enabled: bool = Field(default=False)
    security_question: Optional[str] = None
    security_answer: Optional[str] = None
    reset_token: Optional[str] = Field(default=None, index=True)
    reset_token_expires: Optional[datetime] = None
    last_global_logout_at: Optional[datetime] = None
    last_login: Optional[datetime] = Field(default=None, index=True)

    # Password policy
    password_changed_at: Optional[datetime] = None
    force_password_change: bool = Field(default=False)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Soft Delete
    is_deleted: bool = Field(default=False)
    deletion_reason: Optional[str] = None
    deleted_at: Optional[datetime] = None
    

    # Relationship
    role: Optional["Role"] = Relationship(
        back_populates="users",
        sa_relationship_kwargs={"foreign_keys": "[User.role_id]"}
    ) # Primary role relationship
    wallet: Optional["Wallet"] = Relationship(back_populates="user")
    user_profile: Optional["UserProfile"] = Relationship(back_populates="user")
    addresses: List["Address"] = Relationship(back_populates="user")
    
    # Fix for ambiguous foreign keys: explicitly specify which FK on KYCDocument to use.
    kyc_documents: List["KYCDocument"] = Relationship(
        back_populates="user", 
        sa_relationship_kwargs={"foreign_keys": "[KYCDocument.user_id]"}
    )
    
    kyc_records: List["KYCRecord"] = Relationship(back_populates="user", sa_relationship_kwargs={"foreign_keys": "[KYCRecord.user_id]"})
    devices: List["Device"] = Relationship(back_populates="user")
    vehicles: List["Vehicle"] = Relationship(back_populates="user")
    
    # Fix for ambiguous foreign keys: explicitly specify which FK links a user to their OWN dealer profile
    dealer_profile: Optional["DealerProfile"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"foreign_keys": "[DealerProfile.user_id]"}
    )
    
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
    notification_preference: Optional["NotificationPreference"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"uselist": False}
    )

    @property
    def is_active(self) -> bool:
        """Helper for schema compatibility."""
        return self.status == UserStatus.ACTIVE

    @is_active.setter
    def is_active(self, value: bool):
        if value:
            # Only change if currently inactive/suspended
            if self.status in [UserStatus.INACTIVE, UserStatus.SUSPENDED]:
                self.status = UserStatus.ACTIVE
        else:
            # Only change if currently active/verified
            if self.status in [UserStatus.ACTIVE, UserStatus.VERIFIED]:
                self.status = UserStatus.SUSPENDED

    @property
    def roles(self) -> List["Role"]:
        """Backward compatibility for legacy Many-to-Many role checks."""
        return [self.role] if self.role else []

    # --- Granular RBAC Helpers ---
    @property
    def all_permissions(self) -> set:
        """Aggregate all permission slugs from all assigned roles."""
        perms = set()
        for role in self.roles:
            for perm in role.permissions:
                perms.add(perm.slug)
        return perms

    def has_permission(self, slug: str) -> bool:
        """Check if user has a specific permission (superusers always pass)."""
        if self.is_superuser:
            return True
        return slug in self.all_permissions
