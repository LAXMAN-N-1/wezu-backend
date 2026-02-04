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
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_picture: Optional[str] = None
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
