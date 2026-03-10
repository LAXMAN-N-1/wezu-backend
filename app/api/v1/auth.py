from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from app.models.user import User, UserStatus, KYCStatus
from app.schemas.user import Token
from app.models.session import UserSession
from app.models.otp import OTP
from app.services.auth_service import AuthService
from app.services.otp_service import OTPService
from app.services.fraud_service import FraudService
from app.services.token_service import TokenService
from app.core.security import create_access_token, create_refresh_token, get_password_hash, verify_password
from app.schemas.user import TokenPayload
from app.core.config import settings
from app.api import deps
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.schemas.auth import (
    LoginRequest, LoginResponse, SocialLoginRequest, RoleSelectRequest, ForgotPasswordRequest,
    ChangePasswordRequest, TwoFASetupResponse, TwoFAVerifyRequest, TwoFADisableRequest,
    VerifyEmailRequest, BiometricRegisterRequest, BiometricLoginRequest,
    SecurityQuestionResponse, SetSecurityQuestionRequest, VerifySecurityQuestionRequest
)
from app.services.security_service import SecurityService
from app.middleware.rate_limit import limiter
import logging
import re
from typing import Any, List, Optional
from datetime import datetime, timedelta
from jose import jwt, JWTError

router = APIRouter()
logger = logging.getLogger("wezu_auth")
logging.basicConfig(level=logging.INFO)

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

@router.post("/register", response_model=User)
async def register(
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
        user = db.exec(select(User).where(User.email == user_in.email)).first()
        if user:
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists in the system",
            )
            
    if user_in.phone_number:
         user = db.exec(select(User).where(User.phone_number == user_in.phone_number)).first()
         if user:
            raise HTTPException(
                status_code=400,
                detail="The user with this phone number already exists in the system",
            )
    
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        phone_number=user_in.phone_number,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Assign default role
    from app.models.rbac import Role
    from sqlalchemy.orm import selectinload
    customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
    if customer_role:
        # Changed from user.roles.append(customer_role) to single role assignment
        user.role = customer_role
        db.add(user)
        db.commit()
        db.refresh(user)
        
    return user

@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login_json(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    JSON based login for cleaner UI (uses 'email' field)
    """
    return await _process_login(
        username=login_data.email,
        password=login_data.password,
        db=db,
        request=request
    )

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

@router.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login_access_token(
    request: Request,
    db: Session = Depends(deps.get_db),
    form_data: EmailPasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests (uses 'email' as username)
    """
    return await _process_login(
        username=form_data.username,
        password=form_data.password,
        db=db,
        request=request
    )

async def _process_login(username: str, password: str, db: Session, request: Request) -> Any:
    logger.info(f"Authenticating: {username}")
    
    # Try by email
    statement = select(User).where(User.email == username)
    user = db.exec(statement).first()
    
    if not user:
        # Try by phone number if email fails
        statement = select(User).where(User.phone_number == username)
        user = db.exec(statement).first()

    if not user:
        logger.warning(f"USER_NOT_FOUND: {username}")
        raise HTTPException(status_code=400, detail="Incorrect email/phone or password")

    if not verify_password(password, user.hashed_password):
        logger.warning(f"INVALID_PASSWORD: {username}")
        # Log Failure via Audit Service
        try:
            from app.services.audit_service import AuditService
            AuditService.log_action(
                db=db,
                user_id=user.id,
                action="login_failed",
                resource_type="user",
                resource_id=str(user.id),
                details=f"Login failed for {username}. Reason: Incorrect credentials",
                ip_address=request.client.host
            )
        except Exception as e:
            logger.error(f"AUDIT_LOG_FAILED: {str(e)}")
            
        raise HTTPException(status_code=401, detail="Incorrect email/phone or password")
    
    if not user.is_active:
        logger.warning(f"INACTIVE_USER: {username}")
        raise HTTPException(status_code=400, detail="Inactive user")

    # Update last login
    try:
        user.last_login_at = datetime.utcnow()
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        logger.error(f"UPDATE_LOGIN_TIME_FAILED: {str(e)}")
        # Continue anyway

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    logger.info(f"LOGIN_SUCCESS: User ID {user.id}")
    
    # Create Session
    try:
        AuthService.create_session(
            db=db, 
            user_id=user.id, 
            access_token=access_token, 
            refresh_token=refresh_token, 
            device_info=request.headers.get("user-agent", "Unknown"), 
            ip_address=request.client.host
        )
        
        # Record Login History
        from app.models.login_history import LoginHistory
        login_record = LoginHistory(
            user_id=user.id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", "Unknown"),
            device_type="web" if "Mozilla" in request.headers.get("user-agent", "") else "mobile",
            status="success"
        )
        db.add(login_record)
        db.commit()
    except Exception as e:
        logger.error(f"SESSION_CREATION_FAILED: {str(e)}")
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
            "is_active": True
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
        if not user.is_active or user.status == UserStatus.PENDING_VERIFICATION:
            user.is_active = True
            if user.kyc_status == KYCStatus.PENDING:
                user.kyc_status = KYCStatus.APPROVED # Auto-verify phone for customers
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"User {user.id} activated after OTP verification")

    # Update Last Login
    user.last_login = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create Dual Tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    # Create Session
    try:
        # Extract JWT ID (jti) from refresh token
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            token_jti = payload.get("jti")
        except:
            import uuid
            token_jti = str(uuid.uuid4()) # Fallback
            
        user_agent = request.headers.get("user-agent", "unknown")
        ip_address = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip_address = forwarded.split(",")[0]
            
        device_type = "mobile" if "mobile" in user_agent.lower() else "web"
        
        # Legacy session creation (if still needed by some parts of the system)
        AuthService.create_session(db, user.id, access_token, refresh_token, device_info=device_type, ip_address=ip_address)
        
        # Newer UserSession model
        session = UserSession(
            user_id=user.id,
            token_id=token_jti,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        db.add(session)
        db.commit()
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
async def social_login(
    auth_data: SocialLoginRequest,
    db: Session = Depends(deps.get_db)
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
            is_active=True,
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
    user.last_login = datetime.utcnow()
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
    AuthService.create_session(db, user.id, access_token, refresh_token, device_info=f"OAuth {auth_data.provider.capitalize()}", ip_address=None)

    permissions = AuthService.get_permissions_for_role(db, user.role_id)
    menu_data = AuthService.get_menu_for_role(db, user.role_id)
    
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
async def register_with_password(
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
        is_active=True
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
    
    # Create Dual Tokens
    access_token = create_access_token(subject=new_user.id)
    refresh_token = create_refresh_token(subject=new_user.id)
    return Token(access_token=access_token, refresh_token=refresh_token, user=new_user)

# Removed redundant login_with_password

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: RefreshRequest,
    db: Session = Depends(deps.get_db)
):
    try:
        # Validate Session first
        session = AuthService.validate_session(db, refresh_data.refresh_token, is_refresh=True)
        if not session:
             raise HTTPException(status_code=401, detail="Session expired or invalid")
             
        payload = jwt.decode(
            refresh_data.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user_id = payload.get("sub")
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        new_access_token = create_access_token(subject=user.id)
        # We can rotate refresh token too, or keep it. Let's rotate.
        new_refresh_token = create_refresh_token(subject=user.id)
        
        # Revoke old session and create new one (Session Rotation)
        AuthService.revoke_session(db, refresh_data.refresh_token)
        AuthService.create_session(db, user.id, new_access_token, new_refresh_token, device_info=session.device_type, ip_address=session.ip_address)
        
        return Token(access_token=new_access_token, refresh_token=new_refresh_token)
    except JWTError as e:
        logger.error(f"AUTHENTICATION_ERROR: Refresh JWT failure: {str(e)}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    except Exception as e:
        logger.error(f"AUTHENTICATION_ERROR: Unexpected refresh failure: {str(e)}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")

@router.post("/logout")
async def logout(
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

@router.post("/select-role", response_model=LoginResponse)
async def select_role(
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
    access_token = create_access_token(subject=current_user.id)
    refresh_token = create_refresh_token(subject=current_user.id)
    
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
async def logout_all(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Invalidate ALL sessions for the current user.
    Updates 'last_global_logout_at' timestamp. Any token issued before this time will be rejected.
    """
    current_user.last_global_logout_at = datetime.utcnow()
    # Merge into current session to avoid "already attached to session" error
    # if current_user came from a different dependency session context
    updated_user = db.merge(current_user)
    db.add(updated_user)
    db.commit()
    
    logger.info(f"User {current_user.id} performed global logout")
    return {"message": "Logged out from all devices successfully"}

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

    if not user.status == UserStatus.ACTIVE:
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
async def send_email_verification(
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
    if last_sent and (datetime.utcnow() - last_sent).total_seconds() < 120:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait 2 minutes before requesting another verification email"
        )
    
    # Generate token
    token = secrets.token_urlsafe(32)
    
    current_user.email_verification_token = token
    current_user.email_verification_sent_at = datetime.utcnow()
    
    db.add(current_user)
    db.commit()
    
    # Send email (mock for now)
    verification_link = f"https://app.wezu.com/verify-email?token={token}"
    logger.info(f"Verification email sent to {current_user.email}: {verification_link}")
    # In production: await EmailService.send_verification_email(current_user.email, verification_link)
    
    return {"message": "Verification email sent"}


# --- NEW AUTH GAPS ENDPOINTS ---

@router.post("/verify-email")
async def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(deps.get_db)
):
    """Verify email verification token with 24h expiration"""
    statement = select(User).where(User.email_verification_token == data.token)
    user = db.exec(statement).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    
    # Check expiry (24 hours)
    if user.email_verification_sent_at:
        expiry = user.email_verification_sent_at + timedelta(hours=24)
        if datetime.utcnow() > expiry:
            raise HTTPException(status_code=400, detail="Verification token has expired")

    user.is_email_verified = True
    user.email_verification_token = None
    user.kyc_status = KYCStatus.APPROVED # Auto-approve KYC for verified email
    db.add(user)
    db.commit()
    return {"message": "Email verified successfully", "email": user.email}

@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Authenticated user changing their current password"""
    SecurityService.change_password(db, current_user, data.current_password, data.new_password)
    return {"message": "Password updated successfully"}

@router.post("/enable-2fa", response_model=TwoFASetupResponse)
async def enable_2fa_request(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Initiate 2FA setup by generating secret and QR code"""
    if current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    
    setup_data = AuthService.initiate_2fa_setup(current_user)
    return setup_data

@router.post("/verify-2fa")
async def verify_2fa_and_enable(
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
async def disable_2fa(
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
async def biometric_register(
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
async def biometric_login(
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
        AuthService.create_session(db, user.id, access_token, refresh_token, device_info="Biometric", ip_address=request.client.host)
        return Token(access_token=access_token, refresh_token=refresh_token, user=user)
    
    raise HTTPException(status_code=401, detail="Biometric verification failed")

@router.get("/security-questions", response_model=List[SecurityQuestionResponse])
async def list_security_questions(
    db: Session = Depends(deps.get_db)
):
    """Fetch list of available security questions"""
    return SecurityService.get_available_questions(db)

@router.post("/security-questions/set")
async def set_security_question(
    data: SetSecurityQuestionRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Set user's security question and answer"""
    SecurityService.set_user_security_question(db, current_user.id, data.question_id, data.answer)
    return {"message": "Security question set successfully"}

@router.post("/security-questions/verify")
async def verify_security_question_route(
    data: VerifySecurityQuestionRequest,
    user_id: int, # Sent in body or query during recovery flow
    db: Session = Depends(deps.get_db)
):
    """Verify security question during recovery"""
    if SecurityService.verify_security_answer(db, user_id, data.answer):
        return {"message": "Verification successful", "success": True}
    raise HTTPException(status_code=400, detail="Incorrect answer")
