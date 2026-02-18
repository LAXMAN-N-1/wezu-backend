from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, UploadFile, File, Form
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict
from datetime import datetime
from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.address import Address
from app.models.user_profile import UserProfile
from app.schemas.user import UserResponse, UserCreate, UserUpdate, AddressCreate, AddressResponse, AddressUpdate, DeviceCreate, DeviceResponse
from app.services.notification_service import NotificationService
from app.services.user_service import UserService
from app.services.auth_service import AuthService
from app.core.menu_config import MASTER_MENU
from app.schemas.user import (
    UserResponse, UserUpdate, AddressCreate, AddressResponse, AddressUpdate, 
    DeviceCreate, DeviceResponse, UserProfileResponse, StaffAssignmentInfo, 
    UserStatusUpdate, ActivityLogEntry, ActivityLogResponse, MenuItem, MenuConfigResponse,
    FeatureFlagsResponse, KYCDocumentResponse, KYCStatusDetailsResponse, UserSearchResponse, UserSearchItem
)
from app.schemas.dashboard import DashboardConfigResponse
import os
import shutil
import json
from app.core.security import generate_totp_secret, verify_totp, generate_backup_codes, generate_qr_uri

router = APIRouter()

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    current_user: User = Depends(deps.check_permission("users", "create")),
    db: Session = Depends(deps.get_db),
):
    """
    Create a new user. Only accessible by superusers.
    """
    # Check if user already exists
    if user_in.email:
        if UserService.get_by_email(db, user_in.email):
            raise HTTPException(
                status_code=400,
                detail="User with this email already exists"
            )
    
    # Check phone number
    from sqlmodel import select
    statement = select(User).where(User.phone_number == user_in.phone_number)
    if db.exec(statement).first():
        raise HTTPException(
            status_code=400,
            detail="User with this phone number already exists"
        )

    return UserService.create_user(db, user_in)


def calculate_profile_completion(user: User, user_profile: Optional[UserProfile] = None) -> int:
    """Calculate profile completion percentage based on filled fields"""
    fields = [
        user.full_name,
        user.email,
        user.phone_number,
        user.profile_picture,
    ]
    
    if user_profile:
        fields.extend([
            user_profile.address_line_1,
            user_profile.city, 
            user_profile.state,
            user_profile.date_of_birth
        ])
    
    # Weight for KYC verified
    kyc_verified = user.kyc_status == "verified"
    
    filled = sum(1 for f in fields if f)
    total = len(fields)
    
    if total == 0:
        return 0
        
    # Base percentage from fields
    base_percentage = int((filled / total) * 80)
    
    # Add 20% for verified KYC
    kyc_bonus = 20 if kyc_verified else 0
    
    return min(base_percentage + kyc_bonus, 100)


def _build_user_profile_response(user: User, db: Session = None) -> UserProfileResponse:
    """Helper to build consistent UserProfileResponse"""
    
    # Handle Single Role
    current_role = user.role.name if user.role else "customer"
    user_roles = [current_role]
    
    # Get permissions and menu for current role
    permissions = AuthService.get_permissions_for_role(current_role) if current_role else []
    menu = AuthService.get_menu_for_role(current_role) if current_role else []
    
    # Get wallet balance (handle if wallet relationship not loaded but available in session?)
    # Ideally user.wallet should be loaded.
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
    
    # User Profile Data
    profile_data = {}
    if user.user_profile:
        profile_data = {
            "address_line_1": user.user_profile.address_line_1,
            "address_line_2": user.user_profile.address_line_2,
            "city": user.user_profile.city,
            "state": user.user_profile.state,
            "pin_code": user.user_profile.pin_code,
            "country": user.user_profile.country,
            "date_of_birth": user.user_profile.date_of_birth,
            "gender": user.user_profile.gender,
            "preferred_language": user.user_profile.preferred_language,
        }

    # Calculate profile completion
    profile_completion = calculate_profile_completion(user, user.user_profile)
    
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
        updated_at=user.updated_at,
        **profile_data
    )


@router.get("/me", response_model=UserProfileResponse)
async def read_user_me(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get current user's full profile.
    """
    # Reload user with relationships
    statement = select(User).where(User.id == current_user.id).options(
        selectinload(User.role),
        selectinload(User.wallet),
        selectinload(User.staff_profile),
        selectinload(User.user_profile)
    )
    user = db.exec(statement).first()
    
    return _build_user_profile_response(user, db)

@router.put("/me", response_model=UserProfileResponse)
async def update_user_me(
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Update authenticated user's profile.
    Safely separates User table updates from UserProfile table updates.
    """
    from datetime import datetime
    
    # Get fresh user with profile
    user = db.exec(select(User).where(User.id == current_user.id).options(selectinload(User.user_profile))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_in.model_dump(exclude_unset=True)
    
    # 1. Update User Table Fields
    user_fields = ["full_name", "email", "profile_picture", "notification_preferences", "security_question", "security_answer"]
    for field in user_fields:
        if field in update_data:
            setattr(user, field, update_data[field])
            
    # 2. Update UserProfile Table Fields
    profile_fields = ["address_line_1", "address_line_2", "city", "state", "pin_code", "country", "date_of_birth", "gender", "preferred_language"]
    
    if any(k in update_data for k in profile_fields):
        if not user.user_profile:
             # Create if missing
             new_profile = UserProfile(user_id=user.id)
             user.user_profile = new_profile
             
        for field in profile_fields:
            if field in update_data:
                setattr(user.user_profile, field, update_data[field])
                
        user.user_profile.updated_at = datetime.utcnow()
        db.add(user.user_profile)
    
    # Update timestamp
    user.updated_at = datetime.utcnow()
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Reload for response
    statement = select(User).where(User.id == current_user.id).options(
        selectinload(User.role),
        selectinload(User.wallet),
        selectinload(User.staff_profile),
        selectinload(User.user_profile)
    )
    user = db.exec(statement).first()
    
    return _build_user_profile_response(user, db)

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


def _filter_menu_items(items: List[dict], permissions: set, has_all_access: bool) -> List[MenuItem]:
    valid_items = []
    for item in items:
        # Check permission
        required_perm = item.get("permission")
        if required_perm and not has_all_access and required_perm not in permissions:
            continue
            
        # Create MenuItem
        menu_item = MenuItem(
            id=item["id"],
            label=item["label"],
            icon=item.get("icon"),
            route=item["route"],
            order=item.get("order", 0),
            enabled=item.get("enabled", True),
            permission=required_perm
        )
        
        # Process Submenu
        if item.get("submenu"):
            submenu = _filter_menu_items(item["submenu"], permissions, has_all_access)
            if submenu:
                menu_item.submenu = submenu
        
        valid_items.append(menu_item)
        
    return sorted(valid_items, key=lambda x: x.order)


@router.get("/me/menu-config", response_model=MenuConfigResponse)
def get_user_menu_config(
    current_user: User = Depends(deps.get_current_user),
):
    """
    Generate dynamic menu configuration based on user permissions.
    """
    # 1. Get User Permissions
    current_role = current_user.role.name if current_user.role else "customer"
    
    permissions_list = AuthService.get_permissions_for_role(current_role)
    
    user_permissions = set(permissions_list)
    has_all_access = "all" in user_permissions
    
    # 2. Filter Master Menu
    filtered_menu = _filter_menu_items(MASTER_MENU, user_permissions, has_all_access)
    
    return MenuConfigResponse(menu=filtered_menu)


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


@router.delete("/me/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Delete an address"""
    from sqlmodel import select
    statement = select(Address).where(
        (Address.id == address_id) & (Address.user_id == current_user.id)
    )
    address = db.exec(statement).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    db.delete(address)
    db.commit()
    return None


# ===== FEATURE FLAGS & DASHBOARD =====

@router.get("/me/feature-flags", response_model=FeatureFlagsResponse)
def get_user_feature_flags(
    current_user: User = Depends(deps.get_current_user),
):
    """
    Get feature flags status for the current user based on their role.
    """
    current_role = current_user.role.name if current_user.role else "customer"
    
    # Permission checks
    is_admin = current_role in ["admin", "super_admin", "regional_manager"]
    is_vendor = current_role == "vendor_owner"
    
    # Default flags
    features = {
        "dynamic_pricing": True, # Enabled for everyone
        "ml_predictions": True, # Enabled for everyone
        "bulk_transfers": False,
        "advanced_analytics": False
    }
    
    # Role-based overrides
    if is_admin:
        features["advanced_analytics"] = True
        features["bulk_transfers"] = True
        
    if is_vendor:
        features["bulk_transfers"] = True
        
    return FeatureFlagsResponse(features=features)


@router.get("/me/dashboard-widgets", response_model=DashboardConfigResponse)
def get_user_dashboard_config(
    current_user: User = Depends(deps.get_current_user),
):
    """
    Get personalized dashboard widget configuration for the current user.
    """
    from app.core.dashboard_config import MASTER_DASHBOARD_CONFIG
    from app.schemas.dashboard import DashboardWidget

    current_role = current_user.role.name if current_user.role else "customer"
    
    # Determine primary role for dashboard layout
    layout_key = "default"
    
    if current_role in ["admin", "super_admin", "regional_manager"]:
        layout_key = "admin"
    elif current_role == "vendor_owner":
        layout_key = "vendor_owner"
    elif current_role == "customer":
        layout_key = "customer"
        
    widgets_data = MASTER_DASHBOARD_CONFIG.get(layout_key, MASTER_DASHBOARD_CONFIG["default"])
    
    widgets = [DashboardWidget(**w) for w in widgets_data]
    
    return DashboardConfigResponse(layout=widgets)


# ===== NOTIFICATION PREFERENCES =====

from app.schemas.notification import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    EmailPreferences,
    SMSPreferences,
    PushPreferences,
    QuietHours,
)
import json


def _get_default_notification_preferences() -> dict:
    """Return default preferences structure."""
    return {
        "email": EmailPreferences().model_dump(),
        "sms": SMSPreferences().model_dump(),
        "push": PushPreferences().model_dump(),
        "quiet_hours": QuietHours().model_dump(),
    }


@router.get("/me/notification-preferences", response_model=NotificationPreferencesResponse)
def get_notification_preferences(
    current_user: User = Depends(deps.get_current_user),
):
    """
    Get current user's notification preferences.
    """
    prefs = _get_default_notification_preferences()
    
    if current_user.notification_preferences:
        try:
            stored = json.loads(current_user.notification_preferences)
            # Merge stored prefs with defaults (in case new fields were added)
            for key in ["email", "sms", "push", "quiet_hours"]:
                if key in stored:
                    prefs[key].update(stored[key])
        except json.JSONDecodeError:
            pass  # Fallback to defaults
    
    return NotificationPreferencesResponse(
        email=EmailPreferences(**prefs["email"]),
        sms=SMSPreferences(**prefs["sms"]),
        push=PushPreferences(**prefs["push"]),
        quiet_hours=QuietHours(**prefs["quiet_hours"]),
    )


@router.put("/me/notification-preferences", response_model=NotificationPreferencesResponse)
def update_notification_preferences(
    prefs_in: NotificationPreferencesUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Update current user's notification preferences.
    """
    # Load existing or defaults
    current_prefs = _get_default_notification_preferences()
    
    if current_user.notification_preferences:
        try:
            stored = json.loads(current_user.notification_preferences)
            for key in ["email", "sms", "push", "quiet_hours"]:
                if key in stored:
                    current_prefs[key].update(stored[key])
        except json.JSONDecodeError:
            pass
    
    # Merge updates
    if prefs_in.email:
        current_prefs["email"].update(prefs_in.email.model_dump())
    if prefs_in.sms:
        current_prefs["sms"].update(prefs_in.sms.model_dump())
    if prefs_in.push:
        current_prefs["push"].update(prefs_in.push.model_dump())
    if prefs_in.quiet_hours:
        current_prefs["quiet_hours"].update(prefs_in.quiet_hours.model_dump())
    
    # Persist
    current_user.notification_preferences = json.dumps(current_prefs)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    return NotificationPreferencesResponse(
        email=EmailPreferences(**current_prefs["email"]),
        sms=SMSPreferences(**current_prefs["sms"]),
        push=PushPreferences(**current_prefs["push"]),
        quiet_hours=QuietHours(**current_prefs["quiet_hours"]),
    )


# ===== ADMIN ENDPOINTS =====

from sqlalchemy import or_, and_, func

@router.get("/", response_model=UserSearchResponse)
async def read_users(
    # Pagination
    page: int = 1,
    limit: int = 20,
    # Sorting
    sort_by: Optional[str] = "created_at", # created_at, last_login, full_name
    sort_order: Optional[str] = "desc", # asc, desc
    # Filters
    role: Optional[str] = None,
    status: Optional[str] = None, # active, inactive
    # Dependencies
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get all users with pagination, sorting, and filtering (Admin Only).
    """
    # Authorization checks
    current_role = current_user.role.name if current_user.role else "customer"
    
    is_super_admin = current_role == "super_admin" or current_user.is_superuser
    is_admin = current_role == "admin"
    is_regional_manager = current_role == "regional_manager"
    is_vendor_owner = current_role == "vendor_owner"
    
    if not any([is_super_admin, is_admin, is_regional_manager, is_vendor_owner]):
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Only admins can list users"
        )

    # Base Query
    query = select(User).options(selectinload(User.role))
    conditions = []
    join_addresses = False
    
    # Regional Manager Logic
    manager_states = set()
    if is_regional_manager and not is_super_admin and not is_admin:
        manager_addresses = db.exec(select(Address).where(Address.user_id == current_user.id)).all()
        manager_states = {addr.state.lower().strip() for addr in manager_addresses if addr.state}
        if not manager_states:
             return UserSearchResponse(users=[], total_count=0, page=page, limit=limit, filters_applied={})
        join_addresses = True

    # Role filter
    if role:
        from app.models.rbac import Role
        query = query.join(User.role).where(Role.name == role)

    # Status filter
    if status:
        if status.lower() == "active":
            conditions.append(User.is_active == True)
        elif status.lower() == "inactive":
            conditions.append(User.is_active == False)
    
    # Apply Regional Manager Restriction
    if join_addresses:
        query = query.join(User.addresses)
        query = query.where(func.lower(Address.state).in_(manager_states))
    
    # Vendor restriction
    if is_vendor_owner and not is_super_admin and not is_admin:
        from app.models.staff import StaffProfile
        query = query.join(User.staff_profile).where(StaffProfile.dealer_id == current_user.id)
    
    # Apply conditions
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.distinct()
    
    # Total Count
    count_query = select(func.count()).select_from(query.subquery())
    total_count = db.exec(count_query).one()
    
    # Sorting
    if sort_by:
        field = None
        if sort_by == "created_at":
            field = User.created_at
        elif sort_by == "last_login":
            field = User.last_login
        elif sort_by == "full_name":
            field = User.full_name
        
        if field:
            if sort_order == "desc":
                query = query.order_by(field.desc())
            else:
                query = query.order_by(field.asc())
        else:
            # Default sort
             query = query.order_by(User.created_at.desc())
    else:
        query = query.order_by(User.created_at.desc())
    
    # Pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    
    # Execute
    users = db.exec(query).all()
    
    # Response
    user_items = []
    for user in users:
        current_role = user.role.name if user.role else "customer"
        user_items.append(UserSearchItem(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            profile_picture=user.profile_picture,
            is_active=user.is_active,
            kyc_status=user.kyc_status,
            roles=[current_role],
            created_at=user.created_at,
            last_login=user.last_login
        ))
        
    return UserSearchResponse(
        users=user_items,
        total_count=total_count,
        page=page,
        limit=limit,
        filters_applied={
            "sort_by": sort_by,
            "sort_order": sort_order,
            "role": role,
            "status": status
        }
    )

@router.get("/search", response_model=UserSearchResponse)
async def search_users(
    # Query filters
    name: Optional[str] = None,
    # Dependencies
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    # Reusing Read Users logic effectively
    # ... (skipping generic search implementation for now in this snippet)
    return UserSearchResponse(users=[], total_count=0, page=1, limit=10, filters_applied={})
