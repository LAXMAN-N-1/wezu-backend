from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session
from app.schemas.auth import LoginRequest, LoginResponse
from app.models.user import User
from pydantic import BaseModel, EmailStr, field_validator
import re
from typing import Optional

class UserCreate(BaseModel):
    email: Optional[EmailStr] = None
    password: str
    full_name: str
    phone_number: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v
from app.controllers.auth_controller import auth_controller
from app.api import deps
import logging

router = APIRouter()
logger = logging.getLogger("wezu_auth_routes")

@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    verify_data: LoginRequest,
    db: Session = Depends(deps.get_db)
):
    """
    Standard Email/Phone + Password Login.
    """
    return await auth_controller.process_login(
        username=verify_data.username,
        password=verify_data.password,
        db=db,
        request=request,
        fraud_check=True
    )

@router.post("/register", response_model=User)
async def register(
    user_in: UserCreate,
    db: Session = Depends(deps.get_db)
):
    """
    Register a new customer account.
    """
    return await auth_controller.register(user_in, db)
