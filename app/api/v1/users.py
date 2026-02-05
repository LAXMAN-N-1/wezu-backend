from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.address import Address
from app.schemas.user import UserResponse, UserUpdate, AddressCreate, AddressResponse, AddressUpdate, DeviceCreate, DeviceResponse, UserProfileResponse, StaffAssignmentInfo
from app.services.user_service import UserService
from app.services.auth_service import AuthService
import os
import shutil

router = APIRouter()


def calculate_profile_completion(user: User) -> int:
    """Calculate profile completion percentage based on filled fields"""
    fields = [
        user.full_name,
        user.email,
        user.phone_number,
        user.profile_picture,
        user.address,
    ]
    
    # Weight for KYC verified
    kyc_verified = user.kyc_status == "verified"
    
    filled = sum(1 for f in fields if f)
    total = len(fields)
    
    # Base percentage from fields
    base_percentage = int((filled / total) * 80)
    
    # Add 20% for verified KYC
    kyc_bonus = 20 if kyc_verified else 0
    
    return min(base_percentage + kyc_bonus, 100)


@router.get("/me", response_model=UserProfileResponse)
async def read_user_me(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get current user's full profile including:
    - Basic info
    - Roles and permissions
    - Menu configuration
    - Wallet balance
    - Staff assignments (if applicable)
    - Profile completion percentage
    """
    # Reload user with relationships
    statement = select(User).where(User.id == current_user.id).options(
        selectinload(User.roles),
        selectinload(User.wallet),
        selectinload(User.staff_profile)
    )
    user = db.exec(statement).first()
    
    # Get roles
    user_roles = [r.name for r in user.roles] if user.roles else []
    current_role = user_roles[0] if user_roles else None
    
    # Get permissions and menu for current role
    permissions = AuthService.get_permissions_for_role(current_role) if current_role else []
    menu = AuthService.get_menu_for_role(current_role) if current_role else []
    
    # Get wallet balance
    wallet_balance = user.wallet.balance if user.wallet else 0.0
    
    # Get staff assignment info
    staff_assignment = None
    if user.staff_profile:
        staff_assignment = StaffAssignmentInfo(
            staff_type=user.staff_profile.staff_type,
            station_id=user.staff_profile.station_id,
            dealer_id=user.staff_profile.dealer_id,
            employment_id=user.staff_profile.employment_id,
            is_active=user.staff_profile.is_active
        )
    
    # Calculate profile completion
    profile_completion = calculate_profile_completion(user)
    
    return UserProfileResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
        profile_picture=user.profile_picture,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        kyc_status=user.kyc_status,
        current_role=current_role,
        available_roles=user_roles,
        permissions=permissions,
        menu=menu,
        wallet_balance=wallet_balance,
        staff_assignment=staff_assignment,
        profile_completion_percentage=profile_completion,
        created_at=user.created_at,
        updated_at=user.updated_at
    )

@router.put("/me", response_model=UserProfileResponse)
async def update_user_me(
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Update authenticated user's profile.
    
    Allowed fields:
    - full_name, email, profile_picture, address
    - emergency_contact, notification_preferences
    - security_question, security_answer
    
    NOT allowed (ignored if sent):
    - phone_number (requires verification)
    - role (admin only)
    - kyc_status, is_active (admin only)
    """
    from datetime import datetime
    
    # Get fresh user from current session
    user = db.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update allowed fields only
    update_data = user_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(user, field):
            setattr(user, field, value)
    
    # Update timestamp
    user.updated_at = datetime.utcnow()
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Return full profile response
    user_roles = [r.name for r in user.roles] if user.roles else []
    current_role = user_roles[0] if user_roles else None
    permissions = AuthService.get_permissions_for_role(current_role) if current_role else []
    menu = AuthService.get_menu_for_role(current_role) if current_role else []
    wallet_balance = user.wallet.balance if user.wallet else 0.0
    
    staff_assignment = None
    if user.staff_profile:
        staff_assignment = StaffAssignmentInfo(
            staff_type=user.staff_profile.staff_type,
            station_id=user.staff_profile.station_id,
            dealer_id=user.staff_profile.dealer_id,
            employment_id=user.staff_profile.employment_id,
            is_active=user.staff_profile.is_active
        )
    
    return UserProfileResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
        profile_picture=user.profile_picture,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        kyc_status=user.kyc_status,
        current_role=current_role,
        available_roles=user_roles,
        permissions=permissions,
        menu=menu,
        wallet_balance=wallet_balance,
        staff_assignment=staff_assignment,
        profile_completion_percentage=calculate_profile_completion(user),
        created_at=user.created_at,
        updated_at=user.updated_at
    )

# Profile Picture Upload Response
class ProfilePictureResponse(BaseModel):
    url: str
    message: str = "Profile picture uploaded successfully"


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_PROFILE_PICTURE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/me/profile-picture", response_model=ProfilePictureResponse)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Upload profile picture for authenticated user.
    
    - Accepts: JPEG, PNG, GIF, WebP
    - Max size: 5MB
    - Returns: URL of uploaded image
    """
    from app.services.storage_service import StorageService
    from datetime import datetime
    import uuid
    
    # Validate file type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}"
        )
    
    # Validate file size
    content = await file.read()
    if len(content) > MAX_PROFILE_PICTURE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: 5MB"
        )
    
    # Reset file position for upload
    await file.seek(0)
    
    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    unique_filename = f"profile_{current_user.id}_{uuid.uuid4().hex[:8]}{file_ext}"
    
    # Create a new UploadFile with the unique filename
    file.filename = unique_filename
    
    # Upload to storage (local or cloud based on config)
    file_url = await StorageService.upload_file(file, "profile-pictures")
    
    # Update user record
    user = db.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.profile_picture = file_url
    user.updated_at = datetime.utcnow()
    db.add(user)
    db.commit()
    
    return ProfilePictureResponse(url=file_url)


# Legacy avatar endpoint (keep for backward compatibility)
@router.post("/me/avatar", response_model=UserResponse, deprecated=True)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    DEPRECATED: Use POST /users/me/profile-picture instead.
    """
    MAX_SIZE = 2 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 2MB)")
    await file.seek(0)
    
    # Ensure uploads dir exists
    os.makedirs("uploads/avatars", exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"avatar_{current_user.id}{file_ext}"
    file_path = f"uploads/avatars/{file_name}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    user_in = UserUpdate(profile_picture=f"/static/{file_path}")
    user = UserService.update_user(db, current_user, user_in)
    return user

# Address Endpoints
@router.post("/me/addresses", response_model=AddressResponse)
async def create_address(
    address_in: AddressCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    return UserService.create_address(db, current_user.id, address_in)

@router.get("/me/addresses", response_model=List[AddressResponse])
async def read_addresses(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    return UserService.get_addresses(db, current_user.id)

# ===== MISSING PROFILE ENDPOINTS =====

@router.patch("/me", response_model=UserResponse)
async def partial_update_user_me(
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Partial update of user profile"""
    user = UserService.update_user(db, current_user, user_in)
    return user


@router.delete("/me/avatar", response_model=UserResponse)
async def delete_avatar(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Delete user avatar"""
    if current_user.profile_picture:
        file_path = current_user.profile_picture
        if os.path.exists(file_path):
            os.remove(file_path)
        current_user.profile_picture = None
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
    return current_user


@router.patch("/me/addresses/{address_id}/default", response_model=AddressResponse)
async def set_default_address(
    address_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Set an address as default"""
    from sqlmodel import select
    statement = select(Address).where(
        (Address.id == address_id) & (Address.user_id == current_user.id)
    )
    address = db.exec(statement).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Unset all other defaults
    all_addresses = db.exec(select(Address).where(Address.user_id == current_user.id)).all()
    for addr in all_addresses:
        addr.is_default = False
        db.add(addr)
    
    address.is_default = True
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


# ===== ADMIN ENDPOINTS =====

# Admin Response Schemas
class KYCDocumentInfo(BaseModel):
    id: int
    document_type: str
    document_number: Optional[str] = None
    file_url: str
    status: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ActivityLogEntry(BaseModel):
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class LoginHistoryEntry(BaseModel):
    ip_address: Optional[str] = None
    timestamp: datetime
    details: Optional[str] = None

    class Config:
        from_attributes = True


class AdminUserProfileResponse(BaseModel):
    """Complete user profile for admin view"""
    # Basic Info
    id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    profile_picture: Optional[str] = None
    address: Optional[str] = None
    
    # Status
    is_active: bool
    is_superuser: bool
    kyc_status: str
    
    # Roles & Permissions
    roles: List[str] = []
    permissions: List[str] = []
    
    # Financial
    wallet_balance: float = 0.0
    
    # Staff Info (if applicable)
    staff_assignment: Optional[StaffAssignmentInfo] = None
    
    # KYC Documents
    kyc_documents: List[KYCDocumentInfo] = []
    
    # Activity & Login History
    activity_history: List[ActivityLogEntry] = []
    login_history: List[LoginHistoryEntry] = []
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


from datetime import datetime
from app.models.audit_log import AuditLog
from app.models.kyc import KYCDocument


@router.get("/{user_id}", response_model=AdminUserProfileResponse)
async def get_user_by_id(
    user_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get user profile by ID (Admin Only).
    
    Authorization:
    - Super Admin: Can view all users
    - Regional Manager: Can view users in their region
    - Vendor Owner: Can view their staff only
    """
    # Get current user's roles
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    
    # Check admin authorization
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    is_regional_manager = "regional_manager" in current_user_roles
    is_vendor_owner = "vendor_owner" in current_user_roles
    
    if not any([is_super_admin, is_admin, is_regional_manager, is_vendor_owner]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view other user profiles"
        )
    
    # Fetch target user with relationships
    statement = select(User).where(User.id == user_id).options(
        selectinload(User.roles),
        selectinload(User.wallet),
        selectinload(User.staff_profile),
        selectinload(User.kyc_documents)
    )
    target_user = db.exec(statement).first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Authorization checks based on role
    if is_vendor_owner and not is_super_admin and not is_admin:
        # Vendor owner can only see their staff
        if target_user.staff_profile:
            if target_user.staff_profile.dealer_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own staff profiles"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view staff profiles"
            )
    
    # Note: Regional manager check would require region data on users
    # For now, regional managers have same access as admin
    
    # Get roles and permissions
    user_roles = [r.name for r in target_user.roles] if target_user.roles else []
    primary_role = user_roles[0] if user_roles else None
    permissions = AuthService.get_permissions_for_role(primary_role) if primary_role else []
    
    # Get wallet balance
    wallet_balance = target_user.wallet.balance if target_user.wallet else 0.0
    
    # Get staff assignment
    staff_assignment = None
    if target_user.staff_profile:
        staff_assignment = StaffAssignmentInfo(
            staff_type=target_user.staff_profile.staff_type,
            station_id=target_user.staff_profile.station_id,
            dealer_id=target_user.staff_profile.dealer_id,
            employment_id=target_user.staff_profile.employment_id,
            is_active=target_user.staff_profile.is_active
        )
    
    # Get KYC documents
    kyc_docs = [
        KYCDocumentInfo(
            id=doc.id,
            document_type=doc.document_type,
            document_number=doc.document_number,
            file_url=doc.file_url,
            status=doc.status,
            uploaded_at=doc.uploaded_at
        )
        for doc in (target_user.kyc_documents or [])
    ]
    
    # Get activity history (last 50 actions)
    activity_statement = select(AuditLog).where(
        AuditLog.user_id == user_id
    ).order_by(AuditLog.timestamp.desc()).limit(50)
    activities = db.exec(activity_statement).all()
    
    activity_history = [
        ActivityLogEntry(
            action=a.action,
            resource_type=a.resource_type,
            resource_id=a.resource_id,
            details=a.details,
            ip_address=a.ip_address,
            timestamp=a.timestamp
        )
        for a in activities
    ]
    
    # Get login history (filter activities for login actions)
    login_statement = select(AuditLog).where(
        (AuditLog.user_id == user_id) & 
        (AuditLog.action.in_(["login", "login_success", "login_failed"]))
    ).order_by(AuditLog.timestamp.desc()).limit(20)
    logins = db.exec(login_statement).all()
    
    login_history = [
        LoginHistoryEntry(
            ip_address=l.ip_address,
            timestamp=l.timestamp,
            details=l.details
        )
        for l in logins
    ]
    
    return AdminUserProfileResponse(
        id=target_user.id,
        full_name=target_user.full_name,
        email=target_user.email,
        phone_number=target_user.phone_number,
        profile_picture=target_user.profile_picture,
        address=target_user.address,
        is_active=target_user.is_active,
        is_superuser=target_user.is_superuser,
        kyc_status=target_user.kyc_status,
        roles=user_roles,
        permissions=permissions,
        wallet_balance=wallet_balance,
        staff_assignment=staff_assignment,
        kyc_documents=kyc_docs,
        activity_history=activity_history,
        login_history=login_history,
        created_at=target_user.created_at,
        updated_at=target_user.updated_at
    )
