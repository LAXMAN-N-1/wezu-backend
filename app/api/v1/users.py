from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import List, Optional
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
