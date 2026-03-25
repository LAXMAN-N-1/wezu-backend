"""
Schemas for Dealer Portal User Management (Credentials & Login Flow).
"""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ── Enums ────────────────────────────────────────────────

class CredentialMode(str, Enum):
    INVITE = "invite"       # Send email invitation
    MANUAL = "manual"       # Admin sets password manually


class BulkActionType(str, Enum):
    CHANGE_ROLE = "change_role"
    DEACTIVATE = "deactivate"
    DELETE = "delete"


# ── Create / Update ──────────────────────────────────────

class DealerUserCreate(BaseModel):
    """Create a new user under the dealer — supports both invite and manual password modes."""
    # Step 1: Personal Info
    full_name: str
    email: EmailStr
    phone_number: Optional[str] = None
    department: Optional[str] = None
    notes: Optional[str] = None  # Internal admin notes

    # Step 2: Role
    role_id: int
    station_id: Optional[int] = None  # For station-scoped roles

    # Step 3: Credentials
    credential_mode: CredentialMode = CredentialMode.INVITE
    password: Optional[str] = None          # Required if manual mode
    force_password_change: bool = True       # Require change on first login
    invitation_message: Optional[str] = None # Custom invite email text
    send_sms: bool = False                   # Also send via SMS

    # Step 4: Status
    initial_status: str = "active"  # active | inactive

    @field_validator("password")
    @classmethod
    def validate_password(cls, v, info):
        if info.data.get("credential_mode") == CredentialMode.MANUAL:
            if not v or len(v) < 8:
                raise ValueError("Password must be at least 8 characters for manual mode")
        return v


class DealerUserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    department: Optional[str] = None
    notes: Optional[str] = None
    role_id: Optional[int] = None
    station_id: Optional[int] = None


class DealerUserStatusUpdate(BaseModel):
    status: str  # active | inactive | suspended


class DealerUserPasswordReset(BaseModel):
    mode: str  # "email" or "manual"
    password: Optional[str] = None
    force_password_change: bool = True

    @field_validator("password")
    @classmethod
    def validate_password(cls, v, info):
        if info.data.get("mode") == "manual":
            if not v or len(v) < 8:
                raise ValueError("Password must be at least 8 characters")
        return v


class EmailCheckRequest(BaseModel):
    email: EmailStr


class EmailCheckResponse(BaseModel):
    available: bool
    message: str


# ── Activation & Auth ────────────────────────────────────

class AccountActivationRequest(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(not c.isalnum() for c in v)
        if not (has_upper and has_lower and has_digit and has_special):
            raise ValueError("Password must include uppercase, lowercase, number, and special character")
        return v


class ForceChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class InviteValidationResponse(BaseModel):
    valid: bool
    email: Optional[str] = None
    full_name: Optional[str] = None
    role_name: Optional[str] = None
    role_color: Optional[str] = None
    dealer_name: Optional[str] = None
    expired: bool = False


# ── Read / Response ──────────────────────────────────────

class DealerUserRead(BaseModel):
    id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    department: Optional[str] = None
    profile_picture: Optional[str] = None
    status: str
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    role_icon: Optional[str] = None
    role_color: Optional[str] = None
    station_id: Optional[int] = None
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None  # Name of user who created

    class Config:
        from_attributes = True


class SessionRead(BaseModel):
    id: int
    device_type: str
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    location: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_active_at: Optional[datetime] = None


class LoginHistoryEntry(BaseModel):
    timestamp: datetime
    ip_address: Optional[str] = None
    device: Optional[str] = None
    location: Optional[str] = None
    success: bool


class DealerUserDetail(DealerUserRead):
    notes: Optional[str] = None
    force_password_change: bool = False
    invite_sent_at: Optional[datetime] = None
    sessions: List[SessionRead] = []
    login_history: List[LoginHistoryEntry] = []
    permissions: Dict[str, List[str]] = {}  # module -> [actions]


class UserStats(BaseModel):
    total: int = 0
    active: int = 0
    pending: int = 0
    inactive: int = 0


# ── Bulk Actions ─────────────────────────────────────────

class BulkActionRequest(BaseModel):
    user_ids: List[int]
    action: BulkActionType
    role_id: Optional[int] = None  # For CHANGE_ROLE action


# ── Auth Responses ───────────────────────────────────────

class PortalLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_password: bool = False
    user: Dict[str, Any]
