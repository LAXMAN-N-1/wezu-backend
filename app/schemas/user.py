from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.models.user import User

class AddressBase(BaseModel):
    street_address: str
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


class UserUpdate(BaseModel):
    """
    Allowed fields for self-profile update.
    NOT allowed: phone_number (requires verification), role (admin only), verification status
    """
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_picture: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    notification_preferences: Optional[str] = None  # JSON: {"push": true, "email": true, "sms": false}
    security_question: Optional[str] = None
    security_answer: Optional[str] = None

from app.schemas.role import RoleResponse

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    profile_picture: Optional[str] = None
    kyc_status: str
    wallet_balance: float = 0.0 # Virtual field
    addresses: List[AddressResponse] = []
    roles: List[RoleResponse] = []
    
    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True


class MenuConfig(BaseModel):
    """Menu configuration for role"""
    label: str
    icon: Optional[str] = None
    path: str
    children: Optional[List["MenuConfig"]] = None


class UserProfileResponse(BaseModel):
    """Complete user profile with all details"""
    # Basic Info
    id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    profile_picture: Optional[str] = None
    
    # Status
    is_active: bool
    is_superuser: bool
    kyc_status: str
    
    # Roles & Permissions
    current_role: Optional[str] = None
    available_roles: List[str] = []
    permissions: List[str] = []
    menu: List[MenuConfig] = []
    
    # Financial
    wallet_balance: float = 0.0
    
    # Staff Info (if applicable)
    staff_assignment: Optional[StaffAssignmentInfo] = None
    
    # Profile Completion
    profile_completion_percentage: int = 0
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
