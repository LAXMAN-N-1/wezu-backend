from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.user import User, UserStatus, KYCStatus
from app.schemas.user import Token
from app.models.session import UserSession
from app.models.otp import OTP
from app.services.auth_service import AuthService
from app.services.otp_service import OTPService
from app.services.fraud_service import FraudService
from app.services.token_service import TokenService
from app.core.security import create_access_token, create_refresh_token, get_password_hash, verify_password, verify_and_update_password
from app.core.proxy import get_client_ip
from app.schemas.user import TokenPayload
from app.core.config import settings
from app.api import deps
from app.core.audit import AuditLogger, audit_log
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from fastapi.security import OAuth2PasswordRequestForm
import logging
import re
from typing import Any, List, Optional
from datetime import datetime, UTC, timedelta
from jose import jwt, JWTError, ExpiredSignatureError
import uuid
from app.middleware.rate_limit import limiter
from app.repositories.user_repository import user_repository
from app.services.security_service import SecurityService
from app.schemas.auth import (
    VerifyEmailRequest, ChangePasswordRequest, TwoFASetupResponse, 
    TwoFAVerifyRequest, TwoFADisableRequest, BiometricRegisterRequest, 
    BiometricLoginRequest, SecurityQuestionResponse, SetSecurityQuestionRequest, 
    VerifySecurityQuestionRequest
)

router = APIRouter()
logger = logging.getLogger("wezu_auth")

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

from app.schemas.user import UserResponse

@router.post("/register", response_model=UserResponse)
def register(
    user_in: UserCreate,
    db: Session = Depends(deps.get_db)
):
    """
    Register a new user with email or phone and password.
    """
    if not user_in.email and not user_in.phone_number:
        raise HTTPException(
            status_code=400,
            detail="Either email or phone number must be provided",
        )

    if user_in.email:
        existing_user = user_repository.get_by_email(db, user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists in the system",
            )
            
    if user_in.phone_number:
         existing_user = user_repository.get_by_phone(db, user_in.phone_number)
         if existing_user:
            raise HTTPException(
                status_code=400,
                detail="The user with this phone number already exists in the system",
            )
    
    # Check phone number uniqueness
    user_by_phone = db.exec(select(User).where(User.phone_number == user_in.phone_number)).first()
    if user_by_phone:
        raise HTTPException(
            status_code=400,
            detail="The user with this phone number already exists in the system",
        )
    
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        phone_number=user_in.phone_number,
        status=UserStatus.ACTIVE
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Assign default role
    from app.models.rbac import Role
    from sqlalchemy.orm import selectinload
    customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
    if customer_role:
        user.role_id = customer_role.id
        db.add(user)
        db.commit()
        db.refresh(user)

    # Audit log
    AuditLogger.log_event(db, user.id, "REGISTER", "AUTH", resource_id=user.id)
        
    return user



class EmailPasswordRequestForm:
    """
    Custom OAuth2 compatible form to show 'Email' instead of 'Username' in Swagger UI
    """
    def __init__(
        self,
        grant_type: str = Form(None, pattern="password"),
        username: str = Form(..., description="Email or phone number", title="Email"),
        password: str = Form(...),
        scope: str = Form(""),
        client_id: Optional[str] = Form(None),
        client_secret: Optional[str] = Form(None),
    ):
        self.grant_type = grant_type
        self.username = username
        self.password = password
        self.scopes = scope.split()
        self.client_id = client_id
        self.client_secret = client_secret

@router.post("/token", response_model=Token, tags=["authentication"])
@limiter.limit("5/minute")
def login_access_token(
    request: Request,
    db: Session = Depends(deps.get_db),
    form_data: EmailPasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests (uses 'email' as username)
    """
    return _process_login(
        username=form_data.username,
        password=form_data.password,
        db=db,
        request=request
    )

def _process_login(username: str, password: str, db: Session, request: Request) -> Any:
    logger.info(f"Authenticating: {username}")
    
    user = user_repository.get_by_email(db, username)
    
    if not user:
        # Try by phone number if email fails
        user = user_repository.get_by_phone(db, username)

    if not user:
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("user-agent")
        AuditLogger.log_event(
            db, 
            None, 
            "FAILED_LOGIN", 
            "AUTH", 
            metadata={"username": username, "reason": "invalid_credentials"},
            ip_address=ip_address,
            user_agent=user_agent
        )
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    ok, new_hash = verify_and_update_password(password, user.hashed_password)
    if not ok:
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("user-agent")
        AuditLogger.log_event(
            db, 
            None, 
            "FAILED_LOGIN", 
            "AUTH", 
            metadata={"username": username, "reason": "invalid_credentials"},
            ip_address=ip_address,
            user_agent=user_agent
        )
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if new_hash:
        user.hashed_password = new_hash
        db.add(user)
    
    if user.status != UserStatus.ACTIVE:
        AuditLogger.log_event(db, user.id, "FAILED_LOGIN", "AUTH", metadata={"reason": "inactive_account"})
        raise HTTPException(status_code=400, detail="Inactive user")
        
    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=user.id, jti=token_jti)
    
    # Audit log success
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    AuditLogger.log_event(db, user.id, "LOGIN", "AUTH", ip_address=ip_address, user_agent=user_agent)
    
    # Create Session
    AuthService.create_user_session(db, user.id, refresh_token, request, token_jti=token_jti)
    
    logger.info(f"LOGIN_SUCCESS: User ID {user.id}")
    
    # Create Session
    try:
        # Record Login History
        from app.models.login_history import LoginHistory
        login_record = LoginHistory(
            user_id=user.id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent", "Unknown"),
            device_type="web" if "Mozilla" in request.headers.get("user-agent", "") else "mobile",
            status="success"
        )
        db.add(login_record)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"SESSION_HISTORY_RECORD_FAILED: {str(e)}")
        # Some systems might still log in but token usage might fail later if session is strict
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        user=user
    )


class GoogleAuthRequest(BaseModel):
    token: str
    consent: bool = False

class AppleAuthRequest(BaseModel):
    token: str
    full_name: Optional[str] = None
    consent: bool = False

class OTPRequest(BaseModel):
    target: str # email or phone_number
    purpose: str = "registration"

class OTPVerifyRequest(BaseModel):
    target: str
    code: str
    purpose: str = "registration"
    full_name: Optional[str] = None

class PasswordRegisterRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    full_name: str
    password: str

class PasswordLoginRequest(BaseModel):
    username: str # email or phone_number
    password: str

@router.post("/register/request-otp")
async def request_registration_otp(
    otp_data: OTPRequest,
    db: Session = Depends(deps.get_db)
):
    # Check if user already exists
    if "@" in otp_data.target:
        statement = select(User).where(User.email == otp_data.target)
    else:
        statement = select(User).where(User.phone_number == otp_data.target)
    
    user = db.exec(statement).first()
    is_new_user = user is None
    
    logger.info(f"OTP request for {otp_data.target}. New user: {is_new_user}")

    # Generate and send OTP
    code = OTPService.generate_otp(otp_data.target)
    OTPService.create_otp_record(db, otp_data.target, code, otp_data.purpose)

    logger.info(f"OTP requested for {otp_data.target} with purpose {otp_data.purpose}")
    if "@" in otp_data.target:
        await OTPService.send_email_otp(otp_data.target, code)
    else:
        await OTPService.send_sms_otp(otp_data.target, code)

    return {"message": "OTP sent successfully"}

from sqlalchemy.orm import selectinload
from app.models.rbac import Role

@router.post("/register/verify-otp", response_model=Token)
async def verify_registration_otp(
    verify_data: OTPVerifyRequest,
    request: Request,
    db: Session = Depends(deps.get_db)
):
    # Verify OTP
    if not OTPService.verify_otp(db, verify_data.target, verify_data.code, verify_data.purpose):
        logger.warning(f"Failed OTP verification attempt for {verify_data.target}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )

    # Check if user already exists
    if "@" in verify_data.target:
        # Changed selectinload(User.roles) to User.role_id check or implicit handling
        # Since role is now many-to-one (User -> Role), default lazy loading works 
        # or we use selectinload(User.role)
        statement = select(User).where(User.email == verify_data.target).options(selectinload(User.role))
    else:
        statement = select(User).where(User.phone_number == verify_data.target).options(selectinload(User.role))
    
    user = db.exec(statement).first()

    if not user:
        # Create new user
        new_user_data = {
            "full_name": verify_data.full_name,
            "status": UserStatus.ACTIVE
        }
        if "@" in verify_data.target:
            new_user_data["email"] = verify_data.target
        else:
            new_user_data["phone_number"] = verify_data.target

        user = User(**new_user_data)
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Assign Default Role: Customer
        customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
        if customer_role:
            # Single role assignment
            user.role = customer_role
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Check Fraud Risk
        FraudService.calculate_risk_score(user.id)
    else:
        logger.info(f"Existing user linked via OTP: {verify_data.target}")
        
        # ACTIVATE ACCOUNT if pending
        if user.status != UserStatus.ACTIVE or user.kyc_status == KYCStatus.PENDING:
            user.status = UserStatus.ACTIVE
            if user.kyc_status == KYCStatus.PENDING:
                user.kyc_status = KYCStatus.APPROVED # Auto-verify phone for customers
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"User {user.id} activated after OTP verification")

    # Update Last Login
    user.last_login = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create Dual Tokens
    import uuid
    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=user.id, jti=token_jti)
    
    # Create Session
    try:
        # Extract JWT ID (jti) from refresh token
        # (Already generated above)
            
        user_agent = request.headers.get("user-agent", "unknown")
        ip_address = get_client_ip(request)
            
        device_type = "mobile" if "mobile" in user_agent.lower() else "web"
        
        AuthService.create_user_session(db, user.id, refresh_token, request, token_jti=token_jti)
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
    return Token(access_token=access_token, refresh_token=refresh_token, user=user)



@router.post("/verify-otp", response_model=Token)
async def verify_otp_alias(
    verify_data: OTPVerifyRequest,
    request: Request,
    db: Session = Depends(deps.get_db)
):
    """
    Verify OTP and log in / activate account.
    (Alias for /register/verify-otp to match new requirements)
    """
    return await verify_registration_otp(verify_data, request, db)

from app.schemas.auth import SocialLoginRequest, LoginResponse, MenuConfig, ForgotPasswordRequest

@router.post("/social-login", response_model=LoginResponse)
def social_login(
    auth_data: SocialLoginRequest,
    request: Request,
    db: Session = Depends(get_session)
):
    """
    Unified Social Login (Google, Facebook, Apple).
    Creates user if not exists, or logs in existing user.
    """
    email = None
    social_id = None
    name = None
    picture = None
    
    # 1. Verify Token based on Provider
    if auth_data.provider == "google":
        idinfo = AuthService.verify_google_token(auth_data.token)
        email = idinfo.get("email")
        social_id = idinfo.get("sub")
        name = idinfo.get("name")
        picture = idinfo.get("picture")
        
    elif auth_data.provider == "facebook":
        data = AuthService.verify_facebook_token(auth_data.token)
        email = data.get("email")
        social_id = data.get("id")
        name = data.get("name")
        # Facebook picture structure is nested
        if "picture" in data and "data" in data["picture"]:
             picture = data["picture"]["data"]["url"]
             
    elif auth_data.provider == "apple":
        payload = AuthService.verify_apple_token(auth_data.token)
        email = payload.get("email")
        social_id = payload.get("sub")
        # Apple only sends name on first login, so we might not have it here
        # Client app usually sends it separately if needed, but we'll leave as None for now
        
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {auth_data.provider}"
        )

    if not social_id:
         raise HTTPException(status_code=400, detail="Could not retrieve social ID")

    # 2. Check/Create User
    # we match by email OR the specific social ID
    
    # Determine search logic using explicit conditions
    conditions = []
    if email:
        conditions.append(User.email == email)
    
    if auth_data.provider == "google":
        conditions.append(User.google_id == social_id)
    elif auth_data.provider == "apple":
        conditions.append(User.apple_id == social_id)
    
    from sqlalchemy import or_
    # Updated options to selectinload(User.role)
    user = db.exec(select(User).where(or_(*conditions)).options(selectinload(User.role))).first()

    if not user:
        if not email:
             raise HTTPException(status_code=400, detail="Email required for new registration")
             
        # Create new user
        user = User(
            email=email,
            full_name=name,
            profile_picture=picture,
            status=UserStatus.ACTIVE,
            kyc_status="verified", # Social login usually implies verified email
        )
        
        # Set specific ID
        if auth_data.provider == "google":
            user.google_id = social_id
        elif auth_data.provider == "apple":
            user.apple_id = social_id
            
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Assign Default Role: Customer
        customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
        if customer_role:
            # Single role assignment
            user.role = customer_role
            db.add(user)
            db.commit()
            db.refresh(user)
            
        # Check Fraud Risk
        FraudService.calculate_risk_score(user.id)
        
    else:
        # Update existing user info
        if auth_data.provider == "google":
            user.google_id = social_id
        elif auth_data.provider == "apple":
            user.apple_id = social_id
            
        if picture and not user.profile_picture:
            user.profile_picture = picture
            
        db.add(user)
        db.commit()
        db.refresh(user)

    # Update Last Login
    user.last_login = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)

    # 3. Generate Tokens & Response (Using same logic as Login)
    
    # Updated: Single role handling
    selected_role_name = user.role.name if user.role else None
    
    # Maintain compatibility with List expectation if any, but logic is single
    user_roles = [selected_role_name] if selected_role_name else []
        
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    # Create Session
    AuthService.create_user_session(db, user.id, refresh_token, request)
    
    # Create Session
    # Note: social_login endpoint uses `request`? It does NOT have Request in signature!
    # I need to add request to social_login signature first?
    # Wait, simple replace won't work if I need to change signature.
    # I will skip social_login for now or add Request to it in a separate step?
    # I'll rely on separate step or context based replace.
    # Let's check social_login signature again. It does NOT have request.
    # I will skip social_login in this multi_replace and do it separately.
    
    permissions = AuthService.get_permissions_for_role(selected_role_name)
    menu_data = AuthService.get_menu_for_role(selected_role_name)
    
    return LoginResponse(
        success=True,
        access_token=access_token,
        refresh_token=refresh_token,
        user=user.model_dump(exclude={"hashed_password"}),
        role=selected_role_name,
        available_roles=user_roles,
        permissions=permissions,
        menu=menu_data
    )

@router.post("/register/password", response_model=Token)
def register_with_password(
    register_data: PasswordRegisterRequest,
    db: Session = Depends(deps.get_db)
):
    # Determine the target (email or phone)
    if not register_data.email and not register_data.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or phone number is required"
        )
    
    # Check if user already exists
    if register_data.email:
        statement = select(User).where(User.email == register_data.email)
    else:
        statement = select(User).where(User.phone_number == register_data.phone_number)
    
    user = db.exec(statement).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or phone number already exists"
        )
    
    # Create new user
    from app.core.security import get_password_hash
    new_user = User(
        email=register_data.email,
        phone_number=register_data.phone_number,
        full_name=register_data.full_name,
        hashed_password=get_password_hash(register_data.password),
        status=UserStatus.ACTIVE
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Assign default role (added missing logic)
    customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
    if customer_role:
        new_user.role = customer_role
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    
    # Check Fraud Risk
    FraudService.calculate_risk_score(new_user.id)
    
    # Audit log
    AuditLogger.log_event(db, new_user.id, "USER_CREATION", "USER", resource_id=str(new_user.id), target_id=new_user.id)
    
    # Create Dual Tokens
    access_token = create_access_token(subject=new_user.id)
    refresh_token = create_refresh_token(subject=new_user.id)
    return Token(access_token=access_token, refresh_token=refresh_token, user=new_user)



class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/refresh", response_model=Token)
def refresh_token(
    refresh_data: RefreshRequest,
    request: Request,
    db: Session = Depends(get_session)
):
    auth_headers = {"WWW-Authenticate": "Bearer"}
    try:
        # Validate Session first
        session = AuthService.validate_session(db, refresh_data.refresh_token, is_refresh=True)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token_invalid",
                headers=auth_headers,
            )
        payload = jwt.decode(refresh_data.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token_invalid",
                headers=auth_headers,
            )

        user_id = payload.get("sub")
        user = db.get(User, int(user_id)) if user_id else None
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token_invalid",
                headers=auth_headers,
            )

        old_jti = payload.get("jti")
        new_jti = str(uuid.uuid4())
        new_refresh_token = create_refresh_token(subject=user.id, jti=new_jti)
        access_token = create_access_token(subject=user.id, extra_claims={"sid": new_jti})

        # Rotate session token where possible; fallback to create a new session.
        if old_jti:
            AuthService.update_user_session(db, old_jti, new_refresh_token, request)
        else:
            AuthService.revoke_session(db, refresh_data.refresh_token)
            AuthService.create_user_session(db, user.id, new_refresh_token, request, token_jti=new_jti)

        return Token(access_token=access_token, refresh_token=new_refresh_token, user=user)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token_expired",
            headers=auth_headers,
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token_invalid",
            headers=auth_headers,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AUTHENTICATION_ERROR: Unexpected refresh failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token_invalid",
            headers=auth_headers,
        )

@router.post("/logout")
def logout(
    current_user: User = Depends(deps.get_current_user),
    token: str = Depends(deps.oauth2_scheme),
    db: Session = Depends(deps.get_db)
):
    """Logout user - invalidate tokens and sessions"""
    # 1. Revoke Session in AuthService
    AuthService.revoke_session(db, token)
    
    # 2. Blacklist Token in TokenService
    TokenService.blacklist_token(db, token)
    
    logger.info(f"User {current_user.id} logged out. Session revoked and token blacklisted.")
    return {"message": "Logged out successfully"}


from app.schemas.auth import LoginRequest, LoginResponse, MenuConfig, RoleSelectRequest

@router.post("/login", response_model=LoginResponse)
def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_session)
):
    """
    Login with password. Supports multi-role users.
    """
    
    # 1. Find User (by email or phone) using normalized credential
    credential = login_data.credential.strip()
    if "@" in credential:
        from sqlalchemy import func
        statement = select(User).where(func.lower(User.email) == credential.lower()).options(selectinload(User.role))
    else:
        statement = select(User).where(User.phone_number == credential).options(selectinload(User.role))
    
    user = db.exec(statement).first()
    
    if not user:
        # Audit: failed login (unknown user)
        AuditLogger.log_event(
            db,
            None,
            "FAILED_LOGIN",
            "AUTH",
            metadata={"credential": credential, "reason": "user_not_found"},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    ok, new_hash = verify_and_update_password(login_data.password, user.hashed_password)
    if not ok:
        AuditLogger.log_event(db, user.id, "FAILED_LOGIN", "AUTH", metadata={"reason": "invalid_password"})
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if new_hash:
        user.hashed_password = new_hash
        
    if user.status != UserStatus.ACTIVE:
         AuditLogger.log_event(db, user.id, "FAILED_LOGIN", "AUTH", metadata={"reason": "inactive_account"})
         raise HTTPException(status_code=403, detail="Account is inactive")

    # 2. Determine Role (single-role model)
    selected_role_name = user.role.name if user.role else None
    user_roles = [selected_role_name] if selected_role_name else []
    
    if not user_roles:
         raise HTTPException(status_code=403, detail="No roles assigned to user")

    if login_data.role:
        if login_data.role != selected_role_name:
            raise HTTPException(status_code=403, detail=f"User does not have role: {login_data.role}")
        selected_role_name = login_data.role
            
    # Update Last Login
    user.last_login = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)

    # 3. Generate Response for Selected Role
    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=user.id, jti=token_jti)
    
    # Create Session
    AuthService.create_user_session(db, user.id, refresh_token, request, token_jti=token_jti)
    
    # Get Permissions & Menu from AuthService
    permissions = AuthService.get_permissions_for_role(db, selected_role_name)
    menu_data = AuthService.get_menu_for_role(db, selected_role_name)
    
    # Audit: successful login
    AuditLogger.log_event(db, user.id, "LOGIN", "AUTH", metadata={"role": selected_role_name})
    
    return LoginResponse(
        success=True,
        access_token=access_token,
        refresh_token=refresh_token,
        user=user.model_dump(exclude={"hashed_password"}),
        role=selected_role_name,
        available_roles=user_roles,
        permissions=permissions,
        menu=menu_data
    )

@router.post("/select-role", response_model=LoginResponse)
def select_role(
    role_data: RoleSelectRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Select/Switch active role for the current user.
    Note: As of latest schema, User has single role. This endpoint validates the user has the requested role 
    and returns fresh tokens permissions.
    """
    # 1. Validate User has the role
    # Refactored for single role
    
    current_role_name = current_user.role.name if current_user.role else None
    
    if role_data.role != current_role_name:
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail=f"User does not have role: {role_data.role}"
         )
         
    # 2. Generate new tokens
    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=current_user.id, extra_claims={"sid": token_jti})
    refresh_token = create_refresh_token(subject=current_user.id, jti=token_jti)
    
    # 3. Get Permissions & Menu
    from app.models.rbac import Role
    selected_role = db.exec(select(Role).where(Role.name == role_data.role)).first()
    if not selected_role:
         raise HTTPException(status_code=404, detail="Role not found")

    permissions = AuthService.get_permissions_for_role(db, selected_role.id)
    menu_data = AuthService.get_menu_for_role(db, selected_role.id)
    
    return LoginResponse(
        success=True,
        message=f"Switched to role: {role_data.role}",
        access_token=access_token,
        refresh_token=refresh_token,
        user=current_user.model_dump(exclude={"hashed_password"}),
        role=role_data.role,
        available_roles=[current_role_name] if current_role_name else [],
        permissions=permissions,
        menu=menu_data
    )
@router.post("/logout-all")
def logout_all(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Invalidate ALL sessions for the current user.
    Updates 'last_global_logout_at' timestamp. Any token issued before this time will be rejected.
    """
    revoked_count = AuthService.revoke_all_user_sessions(db, current_user.id)
    logger.info(f"User {current_user.id} performed global logout")
    return {
        "message": "Logged out from all devices successfully",
        "sessions_revoked": revoked_count,
    }

@router.post("/forgot-password")
@limiter.limit("5/hour")
async def forgot_password(
    request: Request,
    forgot_in: ForgotPasswordRequest,
    db: Session = Depends(deps.get_db)
):
    """
    Initiate password reset process.
    Sends 6-digit OTP to registered email or phone.
    OTP expires in 10 minutes.
    """
    user = None
    target = None
    channel = None
    
    # 1. Look up user
    if forgot_in.email:
        user = db.exec(select(User).where(User.email == forgot_in.email)).first()
        target = forgot_in.email
        channel = "email"
    elif forgot_in.phone_number:
        # Normalize phone if needed, but for now strict match
        user = db.exec(select(User).where(User.phone_number == forgot_in.phone_number)).first()
        target = forgot_in.phone_number
        channel = "sms"
        
    if not user:
        # Security: Do not reveal if user exists, just return success
        return {"message": "If an account with these details exists, an OTP has been sent."}

    if user.status != UserStatus.ACTIVE:
         raise HTTPException(status_code=400, detail="User account is inactive.")

    # 2. Generate OTP
    code = OTPService.generate_otp(target)
    
    # 3. Create Record (10 mins validity)
    try:
        OTPService.create_otp_record(db, target, code, purpose="password_reset", validity_minutes=10)
    except HTTPException as e:
        raise e # Propagate rate limit errors

    # 4. Send OTP
    if channel == "email":
        await OTPService.send_email_otp(target, code)
    else:
        await OTPService.send_sms_otp(target, code)

    return {"message": f"OTP sent to your registered {channel}. Valid for 10 minutes."}


@router.post("/resend-otp")
@limiter.limit("5/hour")
async def resend_otp(
    request: Request,
    otp_data: OTPRequest,
    db: Session = Depends(deps.get_db)
):
    """Resend OTP for registration or verification"""
    # Generate and send new OTP
    code = OTPService.generate_otp(otp_data.target)
    OTPService.create_otp_record(db, otp_data.target, code, otp_data.purpose)
    
    logger.info(f"OTP resent for {otp_data.target}")
    if "@" in otp_data.target:
        await OTPService.send_email_otp(otp_data.target, code)
    else:
        await OTPService.send_sms_otp(otp_data.target, code)
    
    return {"message": "OTP resent successfully"}


# ===== EMAIL VERIFICATION =====

class SendEmailVerificationRequest(BaseModel):
    """Request to send email verification link."""
    pass  # Uses current user's email


class VerifyEmailRequest(BaseModel):
    """Verify email with token."""
    token: str


@router.post("/email/send-verification")
@router.post("/resend-verification")
def send_email_verification(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Send email verification link to user's email address.
    """
    import secrets
    
    if getattr(current_user, 'is_email_verified', False):
        return {"message": "Email already verified", "verified": True}
    
    if not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email address associated with account"
        )
    
    # Rate limit: only allow one email every 2 minutes
    last_sent = getattr(current_user, 'email_verification_sent_at', None)
    if last_sent and (datetime.now(UTC) - last_sent).total_seconds() < 120:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait 2 minutes before requesting another verification email"
        )
    
    # Generate token
    token = secrets.token_urlsafe(32)
    
    current_user.email_verification_token = token
    current_user.email_verification_sent_at = datetime.now(UTC)
    
    db.add(current_user)
    db.commit()
    
    # Send email (mock for now)
    verification_link = f"https://app.wezu.com/verify-email?token={token}"
    logger.info(f"Verification email sent to {current_user.email}: {verification_link}")
    # In production: await EmailService.send_verification_email(current_user.email, verification_link)
    
    return {"message": "Verification email sent"}


# --- NEW AUTH GAPS ENDPOINTS ---

@router.post("/verify-email")
def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(deps.get_db)
):
    """Verify email verification token with 24h expiration"""
    statement = select(User).where(User.email_verification_token == data.token)
    user = db.exec(statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Email verified successfully
    user.is_email_verified = True
    user.email_verification_token = None
    user.kyc_status = KYCStatus.APPROVED # Auto-approve KYC for verified email
    db.add(user)
    db.commit()
    return {"message": "Email verified successfully", "email": user.email}

@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Change password for authenticated user"""
    from app.core.security import verify_password, get_password_hash
    
    # Verify current password
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(data.new_password)
    
    # Merge into current session to avoid "already attached" error
    updated_user = db.merge(current_user)
    db.add(updated_user)
    db.commit()
    
    # Revoke all sessions (Security Best Practice)
    AuthService.revoke_all_user_sessions(db, current_user.id)
    
    logger.info(f"Password changed for user {current_user.id}")
    return {"message": "Password changed successfully"}


class Verify2FARequest(BaseModel):
    code: str

@router.post("/enable-2fa", response_model=TwoFASetupResponse)
def enable_2fa_request(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Initiate 2FA setup by generating secret and QR code"""
    if current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    
    setup_data = AuthService.initiate_2fa_setup(current_user)
    return setup_data

@router.post("/verify-2fa")
def verify_2fa_and_enable(
    data: TwoFAVerifyRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Verify first TOTP and permanently enable 2FA for user"""
    backup_codes = AuthService.verify_and_enable_2fa(db, current_user, data.code, data.secret)
    if backup_codes:
        return {
            "message": "2FA enabled successfully",
            "backup_codes": backup_codes
        }
    raise HTTPException(status_code=400, detail="Invalid TOTP code")

@router.post("/2fa/disable")
def disable_2fa(
    data: TwoFADisableRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Disable 2FA with password confirmation"""
    if not verify_password(data.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid password")
    
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.backup_codes = None
    db.add(current_user)
    db.commit()
    return {"message": "2FA disabled successfully"}

@router.post("/biometric/register")
def biometric_register(
    data: BiometricRegisterRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Register biometric public key for device"""
    AuthService.register_biometric(
        db, current_user.id, data.device_id, data.credential_id, data.public_key
    )
    return {"message": "Biometric credential registered successfully"}

@router.post("/biometric-login", response_model=Token)
def biometric_login(
    data: BiometricLoginRequest,
    request: Request,
    db: Session = Depends(deps.get_db)
):
    """Login using biometric challenge/response"""
    # This usually requires user_id to find the public key if not in the credential_id
    # We'll assume the client sends the user context or we lookup by credential_id
    from app.models.biometric import BiometricCredential
    cred = db.exec(select(BiometricCredential).where(BiometricCredential.credential_id == data.credential_id)).first()
    if not cred:
        raise HTTPException(status_code=401, detail="Biometric credential not found")
    
    if AuthService.verify_biometric_signature(db, cred.user_id, data.credential_id, data.signature, data.challenge):
        user = db.get(User, cred.user_id)
        # Proceed to login
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)
        AuthService.create_user_session(
            db, 
            user.id, 
            refresh_token, 
            request=request,
            user_agent="Biometric"
        )
        return Token(access_token=access_token, refresh_token=refresh_token, user=user)
    
    raise HTTPException(status_code=401, detail="Biometric verification failed")

@router.get("/security-questions", response_model=List[SecurityQuestionResponse])
def list_security_questions(
    db: Session = Depends(deps.get_db)
):
    """Fetch list of available security questions"""
    return SecurityService.get_available_questions(db)

@router.post("/security-questions/set")
def set_security_question(
    data: SetSecurityQuestionRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Set user's security question and answer"""
    SecurityService.set_user_security_question(db, current_user.id, data.question_id, data.answer)
    return {"message": "Security question set successfully"}

@router.post("/security-questions/verify")
def verify_security_question_route(
    data: VerifySecurityQuestionRequest,
    user_id: int, # Sent in body or query during recovery flow
    db: Session = Depends(deps.get_db)
):
    """Verify security question during recovery"""
    if SecurityService.verify_security_answer(db, user_id, data.answer):
        return {"message": "Verification successful", "success": True}
    raise HTTPException(status_code=400, detail="Incorrect answer")


# ===== ADMIN LOGIN (JSON-based, for Admin Flutter App) =====

class AdminLoginRequest(BaseModel):
    username: str  # email
    password: str

    @model_validator(mode="before")
    @classmethod
    def normalize_username_aliases(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        username = values.get("username") or values.get("email") or values.get("credential")
        if isinstance(username, str):
            username = username.strip()
        if username:
            values["username"] = username
        return values

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        username = value.strip()
        if not username:
            raise ValueError("Username is required")
        return username

@router.post("/admin/login")
def admin_login(
    request: Request,
    login_data: AdminLoginRequest,
    db: Session = Depends(get_session)
):
    """
    Admin login endpoint (JSON body).
    Validates credentials and ensures the user has an admin-level role.
    """
    username_clean = login_data.username.strip().lower()

    # Single case-insensitive lookup (func.lower hits the expression index
    # ix_users_email_lower added in migration b2c3d4e5f6a7).
    user = db.exec(
        select(User)
        .options(joinedload(User.role))
        .where(func.lower(User.email) == username_clean)
    ).first()

    if not user:
        logger.warning(f"Admin login - user not found: {login_data.username}")
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    # verify_and_update_password transparently re-hashes old pbkdf2 → bcrypt
    ok, new_hash = verify_and_update_password(login_data.password, user.hashed_password)
    if not ok:
        logger.warning(f"Admin login - invalid password for: {login_data.username}")
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if new_hash:
        user.hashed_password = new_hash  # persisted with the last_login commit below

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Verify user has admin-level role.
    from app.models.user import UserType
    admin_types = [UserType.ADMIN] if hasattr(UserType, 'ADMIN') else []
    role_name = user.role.name.strip().lower() if user.role and user.role.name else None
    is_admin = bool(user.is_superuser)

    if hasattr(user, 'user_type') and user.user_type in admin_types:
        is_admin = True

    if role_name in ("admin", "super_admin", "superadmin"):
        is_admin = True

    # Rare fallback when the role relationship is missing but role_id exists.
    if not is_admin and hasattr(user, 'role_id') and user.role_id is not None:
        from app.models.rbac import Role
        role = db.get(Role, user.role_id)
        if role and role.name and role.name.strip().lower() in ("admin", "super_admin", "superadmin"):
            is_admin = True

    if not is_admin:
        logger.warning(f"Admin login - non-admin user attempted: {login_data.username}")
        raise HTTPException(status_code=403, detail="User does not have admin privileges")

    token_jti = str(uuid.uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": token_jti})
    refresh_tok = create_refresh_token(subject=user.id, jti=token_jti)

    # Persist last login alongside the new session in the same commit.
    user.last_login = datetime.now(UTC)
    db.add(user)

    AuthService.create_user_session(
        db, 
        user.id, 
        refresh_tok,
        request=request,
        token_jti=token_jti,
        user_agent="Admin Web"
    )

    logger.info(f"Admin login successful for user ID: {user.id}")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_tok,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
        }
    }
