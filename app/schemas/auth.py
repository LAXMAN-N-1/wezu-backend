from pydantic import BaseModel, EmailStr, Field, validator, root_validator
from typing import Optional, List

class LoginRequest(BaseModel):
    username: str # email or phone
    password: str
    role: Optional[str] = None
    device_fingerprint: Optional[str] = None
    remember_me: bool = False

class RoleSelectRequest(BaseModel):
    role: str

class SocialLoginRequest(BaseModel):
    provider: str # google, facebook, apple
    token: str
    device_fingerprint: Optional[str] = None
    consent: bool = False

class MenuConfig(BaseModel):
    label: str
    icon: Optional[str] = None
    path: str
    children: Optional[List["MenuConfig"]] = None

class LoginResponse(BaseModel):
    success: bool = True
    message: str = "Login successful"
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[dict] = None # Full user object
    role: Optional[str] = None # Current active role
    permissions: List[str] = []
    menu: List[MenuConfig] = []
    available_roles: List[str] = []
    requires_role_selection: bool = False

class OTPRequest(BaseModel):
    phone_number: str
    purpose: str = "login" # login, register, reset_password

class OTPVerify(BaseModel):
    phone_number: str
    otp: str
    purpose: str = "login"

class ForgotPasswordRequest(BaseModel):
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None

    @validator("phone_number")
    def validate_phone(cls, v):
        if v:
             # Basic check, allows international format handling later
             if not v.isdigit() and not v.startswith("+"):
                 raise ValueError("Phone number must contain only digits or start with +")
        return v
    
    @validator("email")
    def validate_either_email_or_phone(cls, v, values):
        if not v and not values.get("phone_number"):
            raise ValueError("Either email or phone number must be provided")
        return v

class ResetPasswordRequest(BaseModel):
    token: Optional[str] = None # Deprecated/Optional for backward compatibility or link-based reset
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    otp: str
    new_password: str

    @validator("phone_number")
    def validate_phone(cls, v):
        if v and not v.isdigit() and not v.startswith("+"):
             raise ValueError("Phone number must contain only digits or start with +")
        return v
    
    @validator("new_password")
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @root_validator(pre=True)
    def validate_target(cls, values):
        email = values.get("email")
        phone = values.get("phone_number")
        if not email and not phone:
            raise ValueError("Either email or phone number must be provided")
        return values


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @validator("new_password")
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @root_validator(skip_on_failure=True)
    def validate_passwords_different(cls, values):
        current = values.get("current_password")
        new = values.get("new_password")
        if current and new and current == new:
            raise ValueError("New password must be different from the current password")
        return values


# Customer Registration Schemas
class VehicleCreate(BaseModel):
    """Vehicle details for customer registration"""
    vehicle_type: str  # e.g., "two_wheeler", "three_wheeler"
    model: str
    make: str
    registration_number: str


class CustomerRegisterRequest(BaseModel):
    """Customer registration request"""
    phone_number: str
    full_name: str
    email: Optional[EmailStr] = None
    password: str
    vehicle: VehicleCreate
    referral_code: Optional[str] = None


class CustomerRegisterResponse(BaseModel):
    """Customer registration response"""
    user_id: int
    message: str = "OTP sent successfully"
    verification_token: str


class BankDetails(BaseModel):
    account_number: str
    ifsc_code: str
    bank_name: str
    account_holder_name: str

class StationLocationCreate(BaseModel):
    latitude: float
    longitude: float
    address: str
    city: str
    state: str

class DealerRegisterRequest(BaseModel):
    # Owner Details
    owner_name: str
    owner_email: EmailStr
    owner_phone: str
    password: str
    
    # Business Details
    business_name: str
    gst_number: str
    business_address: str
    city: str
    state: str
    pincode: str
    
    # Bank Details
    bank_details: BankDetails
    
    # Documents (URLs from frontend upload)
    registration_documents: List[str] 
    
    # Proposed Locations
    proposed_stations: List[StationLocationCreate]

class DealerRegisterResponse(BaseModel):
    application_id: int
    user_id: int
    status: str
    message: str
    verification_token: str

class StaffRegisterRequest(BaseModel):
    full_name: str
    phone_number: str
    email: EmailStr
    staff_type: str # station_manager, technician
    employment_id: str
    
    # Optional Assignments
    station_id: Optional[int] = None
    reporting_manager_id: Optional[int] = None

class StaffRegisterResponse(BaseModel):
    user_id: int
    username: str # email or phone
    temporary_password: str
    role: str
    message: str
