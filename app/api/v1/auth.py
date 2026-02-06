from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.user import User, Token
from app.models.session import UserSession
from app.models.otp import OTP
from app.services.auth_service import AuthService
from app.services.otp_service import OTPService
from app.services.fraud_service import FraudService
from app.services.token_service import TokenService
from app.core.security import create_access_token, create_refresh_token, get_password_hash, verify_password
from app.core.config import settings
from app.api import deps
from pydantic import BaseModel, EmailStr, Field
from fastapi.security import OAuth2PasswordRequestForm
import logging
from typing import Any, List, Optional
from datetime import datetime, timedelta
from jose import jwt, JWTError

router = APIRouter()
logger = logging.getLogger("wezu_auth")
logging.basicConfig(level=logging.INFO)

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone_number: str

@router.post("/register", response_model=User)
async def register(
    user_in: UserCreate,
    db: Session = Depends(get_session)
):
    """
    Register a new user with email and password.
    """
    user = db.exec(select(User).where(User.email == user_in.email)).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
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
        user.roles.append(customer_role)
        db.add(user)
        db.commit()
        db.refresh(user)
        
    return user

@router.post("/login", response_model=Token)
@router.post("/token", response_model=Token)
async def login_access_token(
    db: Session = Depends(get_session),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    # Try by email
    statement = select(User).where(User.email == form_data.username)
    user = db.exec(statement).first()
    
    if not user:
        # Try by phone number if email fails (optional, but good UX)
        statement = select(User).where(User.phone_number == form_data.username)
        user = db.exec(statement).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        user=user # Helper: include user info
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

@router.post("/register/request-otp")
async def request_registration_otp(
    otp_data: OTPRequest,
    db: Session = Depends(get_session)
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
    db: Session = Depends(get_session)
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
        statement = select(User).where(User.email == verify_data.target).options(selectinload(User.roles))
    else:
        statement = select(User).where(User.phone_number == verify_data.target).options(selectinload(User.roles))
    
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
            user.roles.append(customer_role)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Check Fraud Risk
        FraudService.calculate_risk_score(user.id)
    else:
        logger.info(f"Existing user linked via OTP: {verify_data.target}")
        
        # ACTIVATE ACCOUNT if pending
        if not user.is_active or user.kyc_status == "pending_verification":
            user.is_active = True
            if user.kyc_status == "pending_verification":
                user.kyc_status = "verified" # Auto-verify phone for customers
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
            token_jti = str(uuid.uuid4()) # Fallback if no jti in token logic yet
            
        user_agent = request.headers.get("user-agent", "unknown")
        ip_address = request.client.host if request.client else "unknown"
        # X-Forwarded-For if behind proxy
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip_address = forwarded.split(",")[0]
            
        device_type = "mobile" if "mobile" in user_agent.lower() else "web"
        
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
    db: Session = Depends(get_session)
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
    statement = select(User).where(
        (User.email == email) | 
        (getattr(User, f"{auth_data.provider}_id", None) == social_id)
    ).options(selectinload(User.roles))
    
    # Note: getattr handles dynamic field access like User.google_id
    # But for safety/clarity in sqlmodel/sqlalchemy, explicit checks are often better 
    # to avoiding building invalid queries if the column doesn't exist.
    # Let's use explicit conditions:
    conditions = []
    if email:
        conditions.append(User.email == email)
    
    if auth_data.provider == "google":
        conditions.append(User.google_id == social_id)
    elif auth_data.provider == "apple":
        conditions.append(User.apple_id == social_id)
    # Note: Facebook ID column needs to be added to User model if we want to store it explicitly
    # For now, we'll rely on email matching for Facebook if the column is missing
    
    # Re-constructing the query properly
    from sqlalchemy import or_
    user = db.exec(select(User).where(or_(*conditions)).options(selectinload(User.roles))).first()

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
            user.roles.append(customer_role)
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
    # Determine Role (Social login usually defaults to single role or auto-selects)
    # But we should respect the same logic
    user_roles = [r.name for r in user.roles]
    selected_role_name = None
    
    if user_roles:
        selected_role_name = user_roles[0] # Default to first role for social login
        
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
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

# Keeping old endpoints for backward compatibility if needed, 
# but redirecting logic would be better. For now, replacing them completely as per plan.


class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: RefreshRequest,
    db: Session = Depends(get_session)
):
    try:
        payload = jwt.decode(
            refresh_data.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user_id = payload.get("sub")
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)
        
        # Blacklist the old refresh token so it can't be reused
        TokenService.blacklist_token(db, refresh_data.refresh_token)
        
        return Token(access_token=access_token, refresh_token=refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    except Exception as e:
        logger.error(f"Refresh error: {str(e)}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")


from app.schemas.auth import LoginRequest, LoginResponse, MenuConfig, RoleSelectRequest

@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_session)
):
    """
    Login with password. Supports multi-role users.
    """
    from app.core.security import verify_password
    
    # 1. Find User (by email or phone)
    if "@" in login_data.username:
        statement = select(User).where(User.email == login_data.username).options(selectinload(User.roles))
    else:
        statement = select(User).where(User.phone_number == login_data.username).options(selectinload(User.roles))
    
    user = db.exec(statement).first()
    
    if not user:
        # Avoid user enumeration
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    if not user.is_active:
         raise HTTPException(status_code=403, detail="Account is inactive")

    # 2. Determine Role
    user_roles = [r.name for r in user.roles]
    selected_role_name = None
    
    if not user_roles:
         raise HTTPException(status_code=403, detail="No roles assigned to user")

    if login_data.role:
        if login_data.role not in user_roles:
            raise HTTPException(status_code=403, detail=f"User does not have role: {login_data.role}")
        selected_role_name = login_data.role
    else:
        # Auto-select if only 1 role
        if len(user_roles) == 1:
            selected_role_name = user_roles[0]
        else:
            # Require selection
            return LoginResponse(
                success=False,
                message="Please select a role to continue",
                requires_role_selection=True,
                available_roles=user_roles,
                user=user.model_dump(exclude={"hashed_password"})
            )
            
    # Update Last Login
    user.last_login = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    # 3. Generate Response for Selected Role
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    # Get Permissions & Menu from AuthService
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

@router.post("/select-role", response_model=LoginResponse)
async def select_role(
    role_data: RoleSelectRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """
    Select/Switch active role for the current user.
    """
    # 1. Validate User has the role
    user_roles = [r.name for r in current_user.roles]
    
    if role_data.role not in user_roles:
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail=f"User does not have role: {role_data.role}"
         )
         
    # 2. Generate new tokens
    access_token = create_access_token(subject=current_user.id)
    refresh_token = create_refresh_token(subject=current_user.id)
    
    # 3. Get Permissions & Menu
    permissions = AuthService.get_permissions_for_role(role_data.role)
    menu_data = AuthService.get_menu_for_role(role_data.role)
    
    return LoginResponse(
        success=True,
        message=f"Switched to role: {role_data.role}",
        access_token=access_token,
        refresh_token=refresh_token,
        user=current_user.model_dump(exclude={"hashed_password"}),
        role=role_data.role,
        available_roles=user_roles,
        permissions=permissions,
        menu=menu_data
    )
# ===== NEW MISSING ENDPOINTS =====

@router.post("/logout")
async def logout(
    current_user: User = Depends(deps.get_current_user),
    token: str = Depends(deps.oauth2_scheme),
    db: Session = Depends(get_session)
):
    """Logout user - invalidate tokens"""
    TokenService.blacklist_token(db, token)
    logger.info(f"User {current_user.id} logged out and token blacklisted")
    TokenService.blacklist_token(db, token)
    logger.info(f"User {current_user.id} logged out and token blacklisted")
    return {"message": "Logged out successfully"}


@router.post("/logout-all")
async def logout_all(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
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
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_session)
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
    if request.email:
        user = db.exec(select(User).where(User.email == request.email)).first()
        target = request.email
        channel = "email"
    elif request.phone_number:
        # Normalize phone if needed, but for now strict match
        user = db.exec(select(User).where(User.phone_number == request.phone_number)).first()
        target = request.phone_number
        channel = "sms"
        
    if not user:
        # Security: Do not reveal if user exists, just return success
        # But for development/UX, we might want to hint? 
        # Standard practice: "If an account exists, an OTP has been sent."
        # We will return 200 OK regardless to prevent user enumeration.
        return {"message": "If an account with these details exists, an OTP has been sent."}

    if not user.is_active:
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
async def resend_otp(
    otp_data: OTPRequest,
    db: Session = Depends(get_session)
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





from app.schemas.auth import ResetPasswordRequest, ChangePasswordRequest


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_session)
):
    """
    Reset password using OTP.
    - Verifies OTP.
    - Updates password.
    - Invalidates all existing sessions (Global Logout).
    """
    target = request.email or request.phone_number
    
    # 1. Verify OTP
    if not OTPService.verify_otp(db, target, request.otp, "password_reset"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    
    # 2. Get user
    if request.email:
        statement = select(User).where(User.email == request.email)
    else:
        statement = select(User).where(User.phone_number == request.phone_number)
        
    user = db.exec(statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 3. Update password
    from app.core.security import get_password_hash
    user.hashed_password = get_password_hash(request.new_password)
    
    # 4. Global Logout (Security Best Practice)
    user.last_global_logout_at = datetime.utcnow()
    
    db.add(user)
    db.commit()
    
    logger.info(f"Password reset successful for {target}. Global logout triggered.")
    return {"message": "Password reset successful. You have been logged out from all devices."}





@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Change password for authenticated user"""
    from app.core.security import verify_password, get_password_hash
    
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(request.new_password)
    
    # Merge into current session to avoid "already attached" error
    updated_user = db.merge(current_user)
    db.add(updated_user)
    db.commit()
    
    logger.info(f"Password changed for user {current_user.id}")
    return {"message": "Password changed successfully"}


class Verify2FARequest(BaseModel):
    code: str


@router.post("/verify-2fa")
async def verify_2fa(
    request: Verify2FARequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Verify 2FA code during login"""
    from app.models.two_factor_auth import TwoFactorAuth
    
    # Get user's 2FA settings
    statement = select(TwoFactorAuth).where(TwoFactorAuth.user_id == current_user.id)
    two_fa = db.exec(statement).first()
    
    if not two_fa or not two_fa.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled for this user"
        )
    
    # Verify TOTP code
    import pyotp
    totp = pyotp.TOTP(two_fa.secret_key)
    
    if not totp.verify(request.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA code"
        )
    
    logger.info(f"2FA verified for user {current_user.id}")
    return {"message": "2FA verification successful", "verified": True}


# ===== CUSTOMER REGISTRATION =====

from app.schemas.auth import CustomerRegisterRequest, CustomerRegisterResponse, VehicleCreate
from app.models.vehicle import Vehicle
from app.services.referral_service import ReferralService


class CustomerVerificationToken(BaseModel):
    user_id: int
    phone_number: str
    purpose: str = "customer_registration"


@router.post("/register/customer", response_model=CustomerRegisterResponse)
async def register_customer(
    register_data: CustomerRegisterRequest,
    db: Session = Depends(get_session)
):
    """
    Register a new customer (EV owner).
    
    Process:
    1. Validate phone number is not already registered
    2. Validate referral code if provided
    3. Create user with role "customer" and status "pending_verification"
    4. Create vehicle record
    5. Send OTP to phone
    6. Return user_id, confirmation, and verification token
    """
    # 1. Check if phone number already exists
    existing_user = db.exec(
        select(User).where(User.phone_number == register_data.phone_number)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )
    
    # 2. Check if email already exists (if provided)
    if register_data.email:
        existing_email = db.exec(
            select(User).where(User.email == register_data.email)
        ).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # 3. Validate referral code if provided
    referral = None
    if register_data.referral_code:
        from app.models.referral import Referral
        referral = db.exec(
            select(Referral).where(
                Referral.referral_code == register_data.referral_code,
                Referral.status == "pending"
            )
        ).first()
        if not referral:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid referral code"
            )
    
    # 4. Check if vehicle registration number already exists
    existing_vehicle = db.exec(
        select(Vehicle).where(
            Vehicle.registration_number == register_data.vehicle.registration_number
        )
    ).first()
    if existing_vehicle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vehicle registration number already exists"
        )
    
    # 5. Create user with pending_verification status
    from app.core.security import get_password_hash
    
    new_user = User(
        phone_number=register_data.phone_number,
        full_name=register_data.full_name,
        email=register_data.email,
        hashed_password=get_password_hash(register_data.password),
        is_active=False,  # Will be activated after OTP verification
        kyc_status="pending_verification"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 6. Assign customer role
    from app.models.rbac import Role
    customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
    if customer_role:
        new_user.roles.append(customer_role)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    
    # 7. Create vehicle record
    new_vehicle = Vehicle(
        user_id=new_user.id,
        make=register_data.vehicle.make,
        model=register_data.vehicle.model,
        registration_number=register_data.vehicle.registration_number,
        compatible_battery_type=register_data.vehicle.vehicle_type,
        is_active=True,
        is_verified=False
    )
    db.add(new_vehicle)
    db.commit()
    
    # 8. Claim referral if provided
    if referral:
        try:
            ReferralService.claim_referral(
                db, register_data.referral_code, new_user.id
            )
        except Exception as e:
            logger.warning(f"Failed to claim referral: {e}")
    
    # 9. Generate and send OTP
    code = OTPService.generate_otp(register_data.phone_number)
    OTPService.create_otp_record(
        db, register_data.phone_number, code, "customer_registration"
    )
    await OTPService.send_sms_otp(register_data.phone_number, code)
    
    # 10. Generate verification token
    verification_token = create_access_token(
        subject=f"{new_user.id}:customer_registration",
        expires_delta=timedelta(minutes=15)
    )
    
    logger.info(f"Customer registered: {new_user.id}, OTP sent to {register_data.phone_number}")
    
    return CustomerRegisterResponse(
        user_id=new_user.id,
        message="OTP sent successfully",
        verification_token=verification_token
    )


# ===== DEALER REGISTRATION =====

from app.schemas.auth import DealerRegisterRequest, DealerRegisterResponse
from app.models.dealer import DealerProfile, DealerDocument, DealerApplication
from app.models.station import Station

@router.post("/register/dealer", response_model=DealerRegisterResponse)
async def register_dealer(
    register_data: DealerRegisterRequest,
    db: Session = Depends(get_session)
):
    """
    Register a new dealer/vendor.
    
    Process:
    1. Validate email/phone uniqueness
    2. Create User with role "vendor_owner" and status "active=False"
    3. Create DealerProfile with business & bank details
    4. Create DealerDocument records
    5. Create DealerApplication (SUBMITTED)
    6. Create Proposed Stations
    7. Trigger Admin Notification (Log)
    8. Return application ID and status
    """
    
    # 1. Check existing user
    existing_user = db.exec(
        select(User).where(
            (User.email == register_data.owner_email) | 
            (User.phone_number == register_data.owner_phone)
        )
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or phone already exists"
        )
        
    # 2. Check existing business (optional, e.g. GST)
    # existing_dealer = db.exec(select(DealerProfile).where(DealerProfile.gst_number == register_data.gst_number)).first()
    # if existing_dealer: ... 
    
    # 3. Create User
    from app.core.security import get_password_hash
    
    new_user = User(
        full_name=register_data.owner_name,
        email=register_data.owner_email,
        phone_number=register_data.owner_phone,
        hashed_password=get_password_hash(register_data.password),
        is_active=False, # Wait for admin approval
        kyc_status="pending_approval"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Assign vendor_owner role
    vendor_role = db.exec(select(Role).where(Role.name == "vendor_owner")).first()
    if vendor_role:
        new_user.roles.append(vendor_role)
    else:
        # Fallback or error log
        logger.warning("Role 'vendor_owner' not found during dealer registration")
        
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 4. Create Dealer Profile
    dealer_profile = DealerProfile(
        user_id=new_user.id,
        business_name=register_data.business_name,
        gst_number=register_data.gst_number,
        contact_person=register_data.owner_name,
        contact_email=register_data.owner_email,
        contact_phone=register_data.owner_phone,
        address_line1=register_data.business_address,
        city=register_data.city,
        state=register_data.state,
        pincode=register_data.pincode,
        bank_details=register_data.bank_details.model_dump(),
        is_active=False
    )
    db.add(dealer_profile)
    db.commit()
    db.refresh(dealer_profile)
    
    # 5. Add Documents
    for doc_url in register_data.registration_documents:
        # Simple logic to guess type or default to 'registration'
        doc = DealerDocument(
            dealer_id=dealer_profile.id,
            document_type="registration", # Could be enhanced to accept type from frontend
            file_url=doc_url,
            is_verified=False
        )
        db.add(doc)
    
    # 6. Create Application
    application = DealerApplication(
        dealer_id=dealer_profile.id,
        current_stage="SUBMITTED",
        status_history=[{
            "stage": "SUBMITTED", 
            "timestamp": str(datetime.utcnow()), 
            "notes": "Initial submission"
        }]
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    
    # 7. Log Proposed Stations (Placeholder)
    logger.info(f"Proposed stations for {dealer_profile.business_name}: {register_data.proposed_stations}")
    
    # 8. Notify Admin (Mock)
    logger.info(f"New Dealer Application Submitted: {application.id} by {new_user.email}")
    
    # Generate verification token
    verification_token = create_access_token(
        subject=f"{new_user.id}:dealer_registration",
        expires_delta=timedelta(hours=24)
    )

    return DealerRegisterResponse(
        application_id=application.id,
        user_id=new_user.id,
        status="pending_approval",
        message="Application submitted successfully. Compliance team will contact you.",
        verification_token=verification_token
    )

# ===== STAFF REGISTRATION =====

from app.schemas.auth import StaffRegisterRequest, StaffRegisterResponse
from app.models.staff import StaffProfile
import secrets
import string

@router.post("/register/staff", response_model=StaffRegisterResponse)
async def register_staff(
    register_data: StaffRegisterRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """
    Register a new staff member (Station Manager, Technician, etc.).
    
    Authorization:
    - Admin/Super Admin: Can create staff for any dealer/station (or no dealer).
    - Vendor Owner: Can ONLY create staff for their own dealer profile.
    
    Process:
    1. Check permissions and validate dealer ownership.
    2. Check if user exists.
    3. Generate temporary password.
    4. Create User (active=True).
    5. Assign Role.
    6. Create StaffProfile.
    7. Send credentials (Mock).
    """
    
    # 1. Authorization & Validation
    user_roles = [r.name for r in current_user.roles]
    is_admin = "admin" in user_roles or "super_admin" in user_roles
    is_vendor = "vendor_owner" in user_roles
    is_regional_manager = "regional_manager" in user_roles
    
    if not (is_admin or is_vendor or is_regional_manager):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create staff accounts"
        )
        
    dealer_id_to_assign = None
    
    if is_vendor:
        # ensuring vendor has a dealer profile
        statement = select(DealerProfile).where(DealerProfile.user_id == current_user.id)
        dealer_profile = db.exec(statement).first()
        
        if not dealer_profile:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vendor does not have a valid dealer profile"
            )
        dealer_id_to_assign = dealer_profile.id
        
        # If station_id is provided, verify it belongs to this dealer
        if register_data.station_id:
            station = db.get(Station, register_data.station_id)
            if not station or station.dealer_id != dealer_profile.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Station not found or does not belong to your dealership"
                )
    
    # 2. Check if user exists
    existing_user = db.exec(
        select(User).where(
            (User.email == register_data.email) | 
            (User.phone_number == register_data.phone_number)
        )
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or phone already exists"
        )

    # 3. Generate Temporary Password
    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for i in range(10))
    
    # 4. Create User
    from app.core.security import get_password_hash
    
    new_user = User(
        full_name=register_data.full_name,
        email=register_data.email,
        phone_number=register_data.phone_number,
        hashed_password=get_password_hash(temp_password),
        is_active=True,
        kyc_status="verified" # Staff created by admin/vendor are trusted initially
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 5. Assign Role
    # Try to find specific role based on staff_type, fallback to 'staff'
    role_name = register_data.staff_type if register_data.staff_type in ["station_manager", "technician"] else "staff"
    
    role = db.exec(select(Role).where(Role.name == role_name)).first()
    if not role:
        # Fallback to 'staff' generic role if specific one doesn't exist
        role = db.exec(select(Role).where(Role.name == "staff")).first()
        
    if role:
        new_user.roles.append(role)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    else:
        logger.warning(f"Role '{role_name}' or 'staff' not found for new user {new_user.id}")

    # 6. Create Staff Profile
    staff_profile = StaffProfile(
        user_id=new_user.id,
        dealer_id=dealer_id_to_assign,
        station_id=register_data.station_id,
        staff_type=register_data.staff_type,
        employment_id=register_data.employment_id,
        reporting_manager_id=register_data.reporting_manager_id
    )
    db.add(staff_profile)
    db.commit()
    db.refresh(staff_profile)
    
    # 7. Notify (Mock)
    logger.info(f"Staff account created: {new_user.email} with pwd {temp_password}")
    # In production: await NotificationService.send_credentials(...)
    
    return StaffRegisterResponse(
        user_id=new_user.id,
        username=new_user.email,
        temporary_password=temp_password,
        role=role.name if role else "none",
        message="Staff account created successfully. Credentials sent."
    )
