from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class LoginRequest(BaseModel):
    username: str # email or phone
    password: str

class RegisterRequest(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    phone_number: str
    password: str
    referrer_code: Optional[str] = None

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenResponse(BaseModel):
    success: bool = True
    message: str = "Login successful"
    data: Token

class OTPRequest(BaseModel):
    phone_number: str
    purpose: str = "login" # login, register, reset_password

class OTPVerify(BaseModel):
    phone_number: str
    otp: str
    purpose: str = "login"

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
