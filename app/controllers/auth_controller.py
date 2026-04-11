from fastapi import HTTPException, Request
from sqlmodel import Session
from app.schemas.auth import LoginRequest, LoginResponse
from app.models.user import User
from app.repositories.user_repository import user_repository
from app.services.auth_service import AuthService
from app.services.fraud_service import FraudService
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.core.proxy import get_client_ip
import logging

logger = logging.getLogger(__name__)

class AuthController:
    """Handles HTTP Request Validation and Formatting for Authentication"""
    
    @staticmethod
    async def process_login(username: str, password: str, db: Session, request: Request, fraud_check: bool = True) -> LoginResponse:
        """Core login controller logic"""
        logger.info(f"Authenticating login request for: {username}")
        
        # 1. Fetch user via Repository
        user = user_repository.get_by_email(db, username)
        if not user:
            user = user_repository.get_by_phone(db, username)
            
        if not user:
            logger.warning(f"USER_NOT_FOUND: {username}")
            raise HTTPException(status_code=400, detail="Incorrect email/phone or password")
            
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Account is suspended or inactive")
            
        # 2. Verify password
        if not verify_password(password, user.hashed_password):
            logger.warning(f"INVALID_PASSWORD: {username}")
            raise HTTPException(status_code=400, detail="Incorrect email/phone or password")

        # 3. Handle Fraud Analysis natively via Service
        if fraud_check:
            client_ip = get_client_ip(request)
            user_agent = request.headers.get("User-Agent", "unknown")
            fraud_score = await FraudService.analyze_login_attempt(
                user_id=user.id,
                ip_address=client_ip,
                device_fingerprint=user_agent
            )
            if fraud_score.get("action") == "block":
                logger.error(f"LOGIN_BLOCKED_FRAUD: {username}")
                raise HTTPException(status_code=403, detail="Login blocked due to suspicious activity")

        # 4. Generate Tokens
        access_token_expires = AuthService.get_access_token_expires()
        refresh_token_expires = AuthService.get_refresh_token_expires()
        
        access_token = create_access_token(
            user.id, {"type": user.user_type}, access_token_expires
        )
        refresh_token = create_refresh_token(
            user.id, {"type": user.user_type}, refresh_token_expires
        )
        
        # 5. Create Session
        AuthService.create_session(
            db=db,
            user_id=user.id,
            access_token=access_token,
            refresh_token=refresh_token,
            device_info=request.headers.get("User-Agent", "unknown"),
            ip_address=get_client_ip(request)
        )
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user={
                "id": user.id,
                "email": user.email,
                "phone_number": user.phone_number,
                "full_name": user.full_name,
                "user_type": user.user_type,
                "kyc_status": user.kyc_status
            }
        )

    @staticmethod
    async def register(user_in: "UserCreate", db: Session) -> User:
        """Core registration logic extracting DB insertion and checks"""
        logger.info(f"Initiating registration for: {user_in.email or user_in.phone_number}")
        
        # 1. Validation Checks via Repository
        if user_in.email:
            existing_user = user_repository.get_by_email(db, user_in.email)
            if existing_user:
                raise HTTPException(status_code=400, detail="The user with this email already exists")
                
        if user_in.phone_number:
            existing_user = user_repository.get_by_phone(db, user_in.phone_number)
            if existing_user:
                raise HTTPException(status_code=400, detail="The user with this phone number already exists")
                
        # 2. Assign Default Role (Customer)
        from app.models.rbac import Role
        from sqlmodel import select
        customer_role = db.exec(select(Role).where(Role.name == "customer")).first()
        role_id = customer_role.id if customer_role else None
        
        # 3. Create User Profile
        user = User(
            email=user_in.email,
            phone_number=user_in.phone_number,
            full_name=user_in.full_name,
            hashed_password=get_password_hash(user_in.password),
            user_type="customer",
            role_id=role_id,
            status="active"
        )
        
        # 4. Save to Repository
        try:
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"User created successfully: {user.id}")
            return user
        except Exception as e:
            db.rollback()
            logger.error(f"Error during user registration: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create user account")

auth_controller = AuthController()
