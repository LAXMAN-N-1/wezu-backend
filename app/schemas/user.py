from __future__ import annotations
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from app.models.user import User

class AddressBase(BaseModel):
    street_address: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str = "India"
    type: str = "home"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_default: bool = False

class AddressCreate(AddressBase):
    pass

class AddressUpdate(BaseModel):
    street_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    type: Optional[str] = None
    is_default: Optional[bool] = None

class AddressResponse(AddressBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

class UserBase(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None

class UserCreate(UserBase):
    password: str
    phone_number: str  # Required for creation
    is_active: bool = True
    role_id: Optional[int] = None

class UserInviteRequest(BaseModel):
    email: str
    role: str
    full_name: Optional[str] = None

class UserUpdate(BaseModel):
    """
    Allowed fields for self-profile update.
    NOT allowed: phone_number (requires verification), role (admin only), verification status
    """
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_picture: Optional[str] = None
    is_active: Optional[bool] = None
    role_id: Optional[int] = None
    
    # Extended Profile Fields
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pin_code: Optional[str] = None
    country: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    preferred_language: Optional[str] = None
    
    # Legacy / Other
    emergency_contact: Optional[str] = None
    notification_preferences: Optional[str] = None  # JSON: {"push": true, "email": true, "sms": false}
    security_question: Optional[str] = None
    security_answer: Optional[str] = None

class UserStatusUpdate(BaseModel):
    status: str # active, suspended, banned
    reason: str

from app.schemas.rbac import RoleResponse

class UserResponse(UserBase):
    id: int
    is_active: Optional[bool] = True
    is_superuser: bool
    profile_picture: Optional[str] = None
    kyc_status: str
    wallet_balance: float = 0.0 # Virtual field
    addresses: List[AddressResponse] = []
    # roles: List[RoleResponse] = [] # Deprecated
    role: Optional[RoleResponse] = None # New single role
    
    model_config = ConfigDict(from_attributes=True)

class UserNavigationResponse(BaseModel):
    user_id: int
    roles: List[str]
    permissions: List[str]
    menu_config: dict # JSON object following requested structure


class DeviceCreate(BaseModel):
    fcm_token: str
    device_type: str
    device_id: str

class DeviceResponse(DeviceCreate):
    id: int
    is_active: bool
    last_active_at: datetime

# Enhanced User Profile Response
class StaffAssignmentInfo(BaseModel):
    """Staff assignment details for profile"""
    staff_type: Optional[str] = None
    station_id: Optional[int] = None
    dealer_id: Optional[int] = None
    employment_id: Optional[str] = None
    is_active: bool = False

    model_config = ConfigDict(from_attributes=True)

class MenuItem(BaseModel):
    """Menu item for role"""
    id: str
    label: str
    icon: Optional[str] = None
    route: str
    order: int = 0
    enabled: bool = True
    submenu: Optional[List["MenuItem"]] = None
    permission: Optional[str] = None

class MenuConfigResponse(BaseModel):
    menu: List[MenuItem]

class FeatureFlagsResponse(BaseModel):
    features: Dict[str, bool]

class UserProfileResponse(BaseModel):
    """Complete user profile with all details"""
    # Basic Info
    id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    profile_picture: Optional[str] = None
    
    # Extended Profile Info from UserProfile
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pin_code: Optional[str] = None
    country: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    preferred_language: Optional[str] = None
    
    # Status
    is_active: Optional[bool] = True
    is_superuser: bool
    kyc_status: str
    
    # Roles & Permissions
    current_role: Optional[str] = None
    available_roles: List[str] = [] # Legacy compatibility
    permissions: List[str] = []
    menu: List[MenuItem] = []
    
    # Financial
    wallet_balance: float = 0.0
    
    # Staff Info (if applicable)
    staff_assignment: Optional[StaffAssignmentInfo] = None
    
    # Profile Completion
    profile_completion_percentage: int = 0
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ActivityLogEntry(BaseModel):
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class ActivityLogResponse(BaseModel):
    logs: List[ActivityLogEntry]
    total_count: int
    page: int
    limit: int

class UserSessionResponse(BaseModel):
    id: int
    # user_id: int # Implicit from context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    location: Optional[str] = None
    device_type: str
    is_active: bool
    last_active_at: datetime
    created_at: datetime
    is_current: bool = False # Helper field

    model_config = ConfigDict(from_attributes=True)

class KYCDocumentResponse(BaseModel):
    id: int
    document_type: str
    status: str
    rejection_reason: Optional[str] = None
    uploaded_at: datetime
    metadata_: Optional[Any] = Field(default=None, alias="metadata") 

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class KYCStatusDetailsResponse(BaseModel):
    overall_status: str
    documents: List[KYCDocumentResponse]
    next_steps: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)

class TokenPayload(BaseModel):
    sub: Optional[str] = None

# Profile Gaps Schemas
class AccountDeletionRequest(BaseModel):
    reason: str

class MembershipResponse(BaseModel):
    tier: str
    points_balance: float
    status: str
    tier_expiry: Optional[datetime] = None
    benefits: List[str] = []
    upgrade_eligibility: Dict[str, Any] = {}

class DashboardSummaryResponse(BaseModel):
    total_spent_this_month: float
    active_rentals_count: int
    lifetime_rentals_count: int
    membership_tier: str
    wallet_balance: float
    carbon_saved_kg: float
    quick_stats: Dict[str, Any] = {}

class LoginHistoryResponse(BaseModel):
    sessions: List[UserSessionResponse]
    total_count: int
    page: int
    limit: int

class UserSearchItem(BaseModel):
    id: int
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    profile_picture: Optional[str] = None
    is_active: Optional[bool] = True
    kyc_status: str
    roles: List[str]
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
class UserSearchResponse(BaseModel):
    users: List[UserSearchItem]
    total_count: int
    page: int
    limit: int
    filters_applied: Dict[str, Any] = {}
