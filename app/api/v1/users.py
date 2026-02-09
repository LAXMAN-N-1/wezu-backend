from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, UploadFile, File, Form
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.address import Address
from app.services.notification_service import NotificationService
from app.services.user_service import UserService
from app.services.auth_service import AuthService
from app.core.menu_config import MASTER_MENU
from app.schemas.user import (
    UserResponse, UserUpdate, AddressCreate, AddressResponse, AddressUpdate, 
    DeviceCreate, DeviceResponse, UserProfileResponse, StaffAssignmentInfo, 
    UserStatusUpdate, ActivityLogEntry, ActivityLogResponse, MenuItem, MenuConfigResponse,
    UserStatusUpdate, ActivityLogEntry, ActivityLogResponse, MenuItem, MenuConfigResponse,
    FeatureFlagsResponse, KYCDocumentResponse, KYCStatusDetailsResponse
)
from app.schemas.dashboard import DashboardConfigResponse
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


def _build_user_profile_response(user: User, db: Session = None) -> UserProfileResponse:
    """Helper to build consistent UserProfileResponse"""
    # Get roles
    user_roles = [r.name for r in user.roles] if user.roles else []
    current_role = user_roles[0] if user_roles else None
    
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
    
    return _build_user_profile_response(user, db)

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
    user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    current_role = user_roles[0] if user_roles else None
    
    # Use AuthService to get permissions, handling "all" wildcard logic usually found there
    # For now, simplistic retrieval assuming AuthService has this logic or we rely on Role permissions
    
    permissions_list = []
    if current_role:
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

    return address


# ===== FEATURE FLAGS & DASHBOARD =====

@router.get("/me/feature-flags", response_model=FeatureFlagsResponse)
def get_user_feature_flags(
    current_user: User = Depends(deps.get_current_user),
):
    """
    Get feature flags status for the current user based on their role.
    """
    user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    
    # Permission checks
    is_admin = any(r in ["admin", "super_admin", "regional_manager"] for r in user_roles)
    is_vendor = "vendor_owner" in user_roles
    
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

    user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    
    # Determine primary role for dashboard layout
    # Priority: Admin > Vendor > Customer
    layout_key = "default"
    
    if any(r in ["admin", "super_admin", "regional_manager"] for r in user_roles):
        layout_key = "admin"
    elif "vendor_owner" in user_roles:
        layout_key = "vendor_owner"
    elif "customer" in user_roles:
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
    
    Returns structured preferences for:
    - Email notifications (with master toggle)
    - SMS notifications (with master toggle)
    - Push notifications (with master toggle)
    - Quiet hours settings
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
    
    Supports:
    - Enable/disable channels (email, SMS, push) with master toggle
    - Enable/disable individual notification categories
    - Configure quiet hours (start/end time, timezone)
    
    Partial updates supported - only provide fields you want to change.
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


# Search Response Schema
class UserSearchItem(BaseModel):
    """Minimal user info for search results"""
    id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    profile_picture: Optional[str] = None
    is_active: bool
    kyc_status: str
    roles: List[str] = []
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserSearchResponse(BaseModel):
    """Paginated search response"""
    users: List[UserSearchItem]
    total_count: int
    page: int
    limit: int
    filters_applied: dict


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
    
    Authorization:
    - Super Admin: All users
    - Regional Manager: Users in their region (Address State)
    - Vendor Owner: Their staff
    """
    # Authorization checks (Same as Search)
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    is_regional_manager = "regional_manager" in current_user_roles
    is_vendor_owner = "vendor_owner" in current_user_roles
    
    if not any([is_super_admin, is_admin, is_regional_manager, is_vendor_owner]):
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can list users"
        )

    # Base Query
    query = select(User).options(selectinload(User.roles))
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
        query = query.join(User.roles).where(Role.name == role)

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
        user_roles = [r.name for r in user.roles] if user.roles else []
        user_items.append(UserSearchItem(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            profile_picture=user.profile_picture,
            is_active=user.is_active,
            kyc_status=user.kyc_status,
            roles=user_roles,
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
    phone: Optional[str] = None,
    email: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,  # active, suspended, pending
    kyc_status: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    region: Optional[str] = None,
    # Pagination
    page: int = 1,
    limit: int = 20,
    # Dependencies
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Search users with filters (Admin Only).
    
    Query Parameters:
    - name: Partial match on full_name
    - phone: Partial match on phone_number
    - email: Partial match on email
    - role: Filter by role name
    - status: active, suspended, pending
    - kyc_status: pending, verified, rejected
    - created_from/created_to: Date range filter
    - region: Filter by address/region (partial match)
    - page, limit: Pagination
    
    Authorization:
    - Super Admin/Admin: Full access
    - Regional Manager: Users in their region (WIP)
    - Vendor Owner: Their staff only
    """
    # Check admin authorization
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    is_regional_manager = "regional_manager" in current_user_roles
    is_vendor_owner = "vendor_owner" in current_user_roles
    
    if not any([is_super_admin, is_admin, is_regional_manager, is_vendor_owner]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can search users"
        )
    
    # Build base query
    query = select(User).options(selectinload(User.roles))
    conditions = []
    
    # Join candidates (flags to avoid double joins)
    join_addresses = False
    
    if region:
        join_addresses = True
        
    # Regional Manager Logic: Get their regions
    manager_states = set()
    if is_regional_manager and not is_super_admin and not is_admin:
        manager_addresses = db.exec(select(Address).where(Address.user_id == current_user.id)).all()
        manager_states = {addr.state.lower().strip() for addr in manager_addresses if addr.state}
        if not manager_states:
             # Manager has no region, sees nothing
             return UserSearchResponse(
                users=[],
                total_count=0,
                page=page,
                limit=limit,
                filters_applied={}
            )
        join_addresses = True

    # Role filter requires join
    if role:
        from app.models.rbac import Role
        query = query.join(User.roles).where(Role.name == role)
        
    # Join addresses if needed
    if join_addresses:
        query = query.join(User.addresses)
    
    # Apply Regional Manager Restriction
    if is_regional_manager and not is_super_admin and not is_admin:
        # SQLite vs Postgres case sensitivity handling
        # Using func.lower for robust comparison
        query = query.where(func.lower(Address.state).in_(manager_states))
    
    # Apply filters
    if name:
        conditions.append(User.full_name.ilike(f"%{name}%"))
    
    if phone:
        conditions.append(User.phone_number.ilike(f"%{phone}%"))
    
    if email:
        conditions.append(User.email.ilike(f"%{email}%"))
    
    if kyc_status:
        conditions.append(User.kyc_status == kyc_status)
    
    if status:
        if status == "active":
            conditions.append(User.is_active == True)
        elif status == "suspended":
            conditions.append(User.is_active == False)
        elif status == "pending":
            conditions.append(User.kyc_status == "pending")
    
    if created_from:
        conditions.append(User.created_at >= created_from)
    
    if created_to:
        conditions.append(User.created_at <= created_to)
    
    if region:
        # Search distinct on Address fields
        conditions.append(
            or_(
                Address.city.ilike(f"%{region}%"), 
                Address.state.ilike(f"%{region}%"),
                Address.street_address.ilike(f"%{region}%")
            )
        )
    
    # Apply conditions
    if conditions:
        query = query.where(and_(*conditions))
    
    # Use distinct to avoid duplicates from joins (e.g. multiple addresses matching)
    query = query.distinct()
    
    # Vendor owner restriction: only see their staff
    if is_vendor_owner and not is_super_admin and not is_admin:
        from app.models.staff import StaffProfile
        query = query.join(User.staff_profile).where(StaffProfile.dealer_id == current_user.id)
    
    # Get total count before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_count = db.exec(count_query).one()
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(User.created_at.desc())
    
    # Execute query
    users = db.exec(query).all()
    
    # Build response
    user_items = []
    for user in users:
        user_roles = [r.name for r in user.roles] if user.roles else []
        user_items.append(UserSearchItem(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            profile_picture=user.profile_picture,
            is_active=user.is_active,
            kyc_status=user.kyc_status,
            roles=user_roles,
            created_at=user.created_at
        ))
    
    # Build filters applied dict
    filters_applied = {}
    if name:
        filters_applied["name"] = name
    if phone:
        filters_applied["phone"] = phone
    if email:
        filters_applied["email"] = email
    if role:
        filters_applied["role"] = role
    if status:
        filters_applied["status"] = status
    if kyc_status:
        filters_applied["kyc_status"] = kyc_status
    if created_from:
        filters_applied["created_from"] = created_from.isoformat()
    if created_to:
        filters_applied["created_to"] = created_to.isoformat()
    if region:
        filters_applied["region"] = region
    
    return UserSearchResponse(
        users=user_items,
        total_count=total_count,
        page=page,
        limit=limit,
        filters_applied=filters_applied
    )


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
from app.models.session import UserSession
from app.schemas.user import UserSessionResponse



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
        selectinload(User.kyc_documents),
        selectinload(User.addresses)
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
            
    # Regional Manager Check
    if is_regional_manager and not is_super_admin and not is_admin:
        # 1. Get Manager's Region(s) based on their address State
        # We need to query addresses for current_user since they might not be loaded
        manager_addresses = db.exec(select(Address).where(Address.user_id == current_user.id)).all()
        manager_states = {addr.state.lower().strip() for addr in manager_addresses if addr.state}
        
        if not manager_states:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Regional Manager has no assigned region (Address State)"
            )
            
        # 2. Get Target User's Region(s)
        # target_user addresses should be loaded (we added selectinload below)
        target_states = {addr.state.lower().strip() for addr in target_user.addresses if addr.state}
        
        if not manager_states.intersection(target_states):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view users in your region"
            )
    
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


@router.put("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: int,
    status_update: UserStatusUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Update user status (Admin Only).
    
    Actions:
    - Update status (active, suspended, banned)
    - Sync is_active flag
    - Invalidate sessions if suspended/banned
    - Create Audit Log
    - Send Notification
    """
    # 1. Authorization
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    is_regional_manager = "regional_manager" in current_user_roles
    
    if not any([is_super_admin, is_admin, is_regional_manager]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
        
    # 2. Fetch User
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # 3. Regional Manager Scope Check
    if is_regional_manager and not is_super_admin and not is_admin:
        manager_addresses = db.exec(select(Address).where(Address.user_id == current_user.id)).all()
        manager_states = {addr.state.lower().strip() for addr in manager_addresses if addr.state}
        
        target_addresses = db.exec(select(Address).where(Address.user_id == user.id)).all()
        target_states = {addr.state.lower().strip() for addr in target_addresses if addr.state}
        
        if not manager_states.intersection(target_states):
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage users in your region"
            )

    # 4. Update Status
    old_status = user.status
    new_status = status_update.status.lower()
    
    if new_status not in ["active", "suspended", "banned"]:
         raise HTTPException(status_code=400, detail="Invalid status")
         
    user.status = new_status
    if new_status == "active":
        user.is_active = True
    else:
        user.is_active = False
        # Invalidate sessions
        user.last_global_logout_at = datetime.utcnow()
        
    db.add(user)
    
    # 5. Audit Log
    audit_log = AuditLog(
        user_id=current_user.id,
        action="update_user_status",
        resource_type="user",
        resource_id=str(user.id),
        details=f"Changed status from {old_status} to {new_status}. Reason: {status_update.reason}",
        ip_address="0.0.0.0", # TODO: Extract from request
        timestamp=datetime.utcnow()
    )
    db.add(audit_log)
    db.commit()
    db.refresh(user)
    
    # 6. Notification
    NotificationService.send_notification(
        db=db,
        user=user,
        title="Account Status Update",
        message=f"Your account status has been updated to {new_status}. Reason: {status_update.reason}",
        type="alert",
        channel="email" # Ensure critical updates are emailed
    )
    
    
    
    # Reload relationships for UserResponse
    # But UserResponse (the return type) is the basic one, not AdminUserProfileResponse
    return user


@router.get("/{user_id}/activity", response_model=ActivityLogResponse)
async def get_user_activity(
    user_id: int,
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get user's activity history.
    
    Authorization:
    - User: Own activity
    - Super Admin / Admin: Any user
    - Regional Manager: Users in their region
    """
    # 1. Authorization
    is_self = current_user.id == user_id
    
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    is_regional_manager = "regional_manager" in current_user_roles
    
    if not is_self and not any([is_super_admin, is_admin, is_regional_manager]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own activity"
        )
        
    # 2. Regional Manager Check (if not self/admin)
    if not is_self and is_regional_manager and not is_super_admin and not is_admin:
        # Check if target user is in region
        user = db.get(User, user_id)
        if not user:
             raise HTTPException(status_code=404, detail="User not found")
             
        manager_addresses = db.exec(select(Address).where(Address.user_id == current_user.id)).all()
        manager_states = {addr.state.lower().strip() for addr in manager_addresses if addr.state}
        
        target_addresses = db.exec(select(Address).where(Address.user_id == user.id)).all()
        target_states = {addr.state.lower().strip() for addr in target_addresses if addr.state}
        
        if not manager_states.intersection(target_states):
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view activity of users in your region"
            )

    # 3. Query Audit Logs
    query = select(AuditLog).where(AuditLog.user_id == user_id)
    
    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_count = db.exec(count_query).one()
    
    # Pagination & Sort
    offset = (page - 1) * limit
    query = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
    
    logs = db.exec(query).all()
    
    log_items = [
        ActivityLogEntry(
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            timestamp=log.timestamp
        )
        for log in logs
    ]
    
    return ActivityLogResponse(
        logs=log_items,
        total_count=total_count,
        page=page,
        limit=limit
    )



@router.delete("/{user_id}", response_model=UserResponse)
async def delete_user(
    user_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Soft delete user (Super Admin Only).
    
    Actions:
    - Mark is_deleted=True, is_active=False
    - Anonymize PII (email, phone, name)
    - Invalidate sessions
    - Audit Log
    """
    # 1. Authorization (Super Admin Only)
    if not current_user.is_superuser:
         # Check role based
         current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
         if "super_admin" not in current_user_roles:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Super Admins can delete users"
            )
            
    # 2. Fetch User
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.is_deleted:
        raise HTTPException(status_code=400, detail="User already deleted")

    # 3. Soft Delete & Anonymize
    import uuid
    # Generate unique suffix to avoid unique constraint violations
    deletion_uuid = uuid.uuid4().hex[:8]
    
    original_email = user.email
    user.is_deleted = True
    user.deleted_at = datetime.utcnow()
    user.is_active = False
    user.status = "deleted"
    
    # Anonymize PII
    user.email = f"deleted_{deletion_uuid}@deleted.wezu"
    # Ensure phone number uniqueness is maintained even for deleted users
    user.phone_number = f"del_{deletion_uuid}" 
    user.full_name = "Deleted User"
    user.profile_picture = None
    user.address = None
    user.emergency_contact = None
    user.security_question = None
    user.security_answer = None
    user.google_id = None
    user.apple_id = None
    
    # Invalidate sessions
    user.last_global_logout_at = datetime.utcnow()
    
    db.add(user)
    
    # 4. Audit Log
    audit_log = AuditLog(
        user_id=current_user.id,
        action="delete_user",
        resource_type="user",
        resource_id=str(user.id),
        details=f"Soft deleted user. Original Email: {original_email}",
        ip_address="0.0.0.0",
        timestamp=datetime.utcnow()
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(user)
    
    return user



@router.get("/me/sessions", response_model=List[UserSessionResponse])
async def get_my_sessions(
    request: Request,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get active login sessions for current user.
    """
    sessions = db.exec(
        select(UserSession)
        .where(UserSession.user_id == current_user.id)
        .where(UserSession.is_active == True)
        .order_by(UserSession.last_active_at.desc())
    ).all()
    
    # Identify current session roughly by IP/UA if possible, or JTI if we had it in request state
    # Ideally we'd compare JTI, but basic matching:
    current_ip = request.client.host if request.client else None
    current_ua = request.headers.get("user-agent")
    
    response = []
    for s in sessions:
        is_current = (s.ip_address == current_ip and s.user_agent == current_ua)
        resp_item = UserSessionResponse.model_validate(s)
        resp_item.is_current = is_current
        response.append(resp_item)
        
    return response

@router.delete("/me/sessions/{session_id}")
async def revoke_session(
    session_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Revoke a specific session.
    """
    session = db.get(UserSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if session.user_id != current_user.id:
         raise HTTPException(status_code=403, detail="Not your session")
         
    session.is_active = False
    db.add(session)
    db.commit()
    
    # Optional: Blacklist token if TokenService is available
    if session.token_id:
        from app.services.token_service import TokenService
        TokenService.blacklist_token(db, session.token_id)
        
    return {"message": "Session revoked"}
@router.post("/me/kyc", response_model=UserResponse)
async def submit_kyc(
    document_type: str = Form(...), # aadhaar, pan, driving_license, passport
    document_number: str = Form(...),
    front_image: UploadFile = File(...),
    back_image: Optional[UploadFile] = File(None),
    selfie: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_session),
):
    """
    Submit KYC documents for verification.
    """
    from app.services.storage_service import StorageService
    from app.models.kyc import KYCDocument
    import json
    
    # 1. Validate Input
    valid_types = ["aadhaar", "pan", "driving_license", "passport"]
    if document_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid document type. Must be one of {valid_types}")
        
    # 2. Upload Files & Create Records
    uploaded_docs = []
    
    # helper
    async def process_file(file: UploadFile, side_meta: dict):
        if not file: return
        
        # Validation (Size/Type) - simplified for now, assuming frontend limits
        if file.size and file.size > 5 * 1024 * 1024: # 5MB
             raise HTTPException(status_code=400, detail=f"File {file.filename} too large")

        url = await StorageService.upload_file(file, directory=f"kyc/{current_user.id}")
        
        doc = KYCDocument(
            user_id=current_user.id,
            document_type=document_type if side_meta.get("type") != "selfie" else "selfie",
            document_number=document_number if side_meta.get("type") != "selfie" else None,
            file_url=url,
            status="pending",
            metadata_=json.dumps(side_meta)
        )
        db.add(doc)
        uploaded_docs.append(doc)

    # Process Front
    await process_file(front_image, {"side": "front"})
    
    # Process Back (if applicable)
    if back_image:
        await process_file(back_image, {"side": "back"})
        
    # Process Selfie
    await process_file(selfie, {"type": "selfie"})
    
    # 3. Update User Status
    current_user.kyc_status = "pending_verification"
    # Also save specific doc numbers if fit in user model (optional, user model has aadhaar/pan fields)
    if document_type == "aadhaar":
        current_user.aadhaar_number = document_number
    elif document_type == "pan":
        current_user.pan_number = document_number
        
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    # 4. Notify Admin/Verification Team (Log for now)
    # create a notification for the user confirming submission
    NotificationService.send_notification(
        db, 
        current_user, 
        "KYC Submitted", 
        "Your KYC documents have been received and are under review.",
        type="kyc"
    )
    
    return current_user

@router.get("/me/kyc/status", response_model=KYCStatusDetailsResponse)
def get_kyc_status(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_session),
):
    """
    Get current KYC verification status and documents.
    """
    from app.models.kyc import KYCDocument
    
    docs = db.exec(select(KYCDocument).where(KYCDocument.user_id == current_user.id)).all()
    
    # Determine next steps
    next_steps = "Please wait for verification."
    if current_user.kyc_status == "rejected":
        next_steps = "Some documents were rejected. Please check the reasons and re-upload."
    elif current_user.kyc_status == "verified":
        next_steps = "Your account is fully verified."
    elif not docs:
        next_steps = "Please submit your KYC documents to activate your account."

    # Manually construct list to avoid metadata collision
    doc_responses = []
    for doc in docs:
        doc_responses.append(KYCDocumentResponse(
            id=doc.id,
            document_type=doc.document_type,
            status=doc.status,
            rejection_reason=doc.verification_response if doc.status == "rejected" else None,
            uploaded_at=doc.uploaded_at,
            metadata=doc.metadata_ # Explicit mapping
        ))

    return KYCStatusDetailsResponse(
        overall_status=current_user.kyc_status or "pending",
        documents=doc_responses,
        next_steps=next_steps
    )


# ===== TWO-FACTOR AUTHENTICATION =====

import secrets
import base64
import hashlib


class TwoFactorSetupResponse(BaseModel):
    secret: str  # Base32 encoded secret
    qr_code_uri: str  # otpauth:// URI for QR code
    backup_codes: List[str]  # One-time backup codes
    message: str


class TwoFactorVerifyRequest(BaseModel):
    code: str  # 6-digit TOTP code


class TwoFactorVerifyResponse(BaseModel):
    success: bool
    message: str
    two_factor_enabled: bool


class TwoFactorDisableRequest(BaseModel):
    password: str
    code: str  # Current TOTP code to verify


class TwoFactorStatusResponse(BaseModel):
    enabled: bool
    created_at: Optional[datetime] = None
    backup_codes_remaining: int


def _generate_totp_secret() -> str:
    """Generate a random base32 encoded secret for TOTP."""
    random_bytes = secrets.token_bytes(20)
    return base64.b32encode(random_bytes).decode('utf-8').rstrip('=')


def _generate_backup_codes(count: int = 10) -> List[str]:
    """Generate backup codes for 2FA recovery."""
    return [secrets.token_hex(4).upper() for _ in range(count)]


def _generate_qr_uri(email: str, secret: str, issuer: str = "Wezu") -> str:
    """Generate otpauth:// URI for QR code scanning."""
    return f"otpauth://totp/{issuer}:{email}?secret={secret}&issuer={issuer}&digits=6&period=30"


def _verify_totp(secret: str, code: str) -> bool:
    """
    Verify a TOTP code against the secret.
    Simple implementation - in production use pyotp library.
    """
    import time
    import hmac
    
    # Pad secret back to proper base32
    padded_secret = secret + '=' * (8 - len(secret) % 8) if len(secret) % 8 else secret
    
    try:
        key = base64.b32decode(padded_secret, casefold=True)
    except Exception:
        return False
    
    # Get current time step (30 second intervals)
    time_step = int(time.time()) // 30
    
    # Check current and adjacent time steps (for clock drift)
    for step_offset in [-1, 0, 1]:
        step = time_step + step_offset
        
        # Create HMAC-SHA1 hash
        msg = step.to_bytes(8, 'big')
        hmac_hash = hmac.new(key, msg, hashlib.sha1).digest()
        
        # Dynamic truncation
        offset = hmac_hash[-1] & 0x0F
        truncated = hmac_hash[offset:offset + 4]
        code_int = int.from_bytes(truncated, 'big') & 0x7FFFFFFF
        totp = str(code_int % 10**6).zfill(6)
        
        if totp == code:
            return True
    
    return False


@router.post("/me/2fa/enable", response_model=TwoFactorSetupResponse)
async def enable_two_factor(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Enable Two-Factor Authentication for the current user.
    
    Process:
    1. Generate TOTP secret
    2. Return QR code URI for authenticator app
    3. Return backup codes
    4. User must verify with code to complete setup
    
    Note: 2FA is not fully enabled until verified via POST /me/2fa/verify
    """
    # Check if 2FA is already enabled
    if getattr(current_user, 'two_factor_enabled', False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is already enabled"
        )
    
    # Generate secret and backup codes
    secret = _generate_totp_secret()
    backup_codes = _generate_backup_codes()
    qr_uri = _generate_qr_uri(current_user.email, secret)
    
    # Store secret temporarily (not enabled until verified)
    # In production, encrypt the secret before storing
    current_user.two_factor_secret = secret
    current_user.two_factor_backup_codes = json.dumps(backup_codes)
    current_user.two_factor_pending = True  # Pending verification
    
    db.add(current_user)
    db.commit()
    
    return TwoFactorSetupResponse(
        secret=secret,
        qr_code_uri=qr_uri,
        backup_codes=backup_codes,
        message="Scan the QR code with your authenticator app, then verify with a code from the app"
    )


@router.post("/me/2fa/verify", response_model=TwoFactorVerifyResponse)
async def verify_two_factor(
    request: TwoFactorVerifyRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Verify 2FA setup with a code from the authenticator app.
    
    This completes the 2FA setup process.
    Must be called after POST /me/2fa/enable.
    """
    secret = getattr(current_user, 'two_factor_secret', None)
    
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA setup not initiated. Call POST /me/2fa/enable first"
        )
    
    # Verify the code
    if not _verify_totp(secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )
    
    # Enable 2FA
    current_user.two_factor_enabled = True
    current_user.two_factor_pending = False
    current_user.two_factor_enabled_at = datetime.utcnow()
    
    db.add(current_user)
    db.commit()
    
    return TwoFactorVerifyResponse(
        success=True,
        message="Two-factor authentication has been enabled successfully",
        two_factor_enabled=True
    )


@router.post("/me/2fa/disable", response_model=TwoFactorVerifyResponse)
async def disable_two_factor(
    request: TwoFactorDisableRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Disable Two-Factor Authentication.
    
    Requires:
    - Current password
    - Valid 2FA code from authenticator
    """
    from app.core.security import verify_password
    
    if not getattr(current_user, 'two_factor_enabled', False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled"
        )
    
    # Verify password
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )
    
    # Verify 2FA code
    secret = getattr(current_user, 'two_factor_secret', '')
    if not _verify_totp(secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA code"
        )
    
    # Disable 2FA
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.two_factor_backup_codes = None
    current_user.two_factor_enabled_at = None
    
    db.add(current_user)
    db.commit()
    
    return TwoFactorVerifyResponse(
        success=True,
        message="Two-factor authentication has been disabled",
        two_factor_enabled=False
    )


@router.get("/me/2fa/status", response_model=TwoFactorStatusResponse)
async def get_two_factor_status(
    current_user: User = Depends(deps.get_current_user),
):
    """Get current 2FA status for the user."""
    enabled = getattr(current_user, 'two_factor_enabled', False)
    enabled_at = getattr(current_user, 'two_factor_enabled_at', None)
    backup_codes_json = getattr(current_user, 'two_factor_backup_codes', None)
    
    backup_codes_remaining = 0
    if backup_codes_json:
        try:
            codes = json.loads(backup_codes_json)
            backup_codes_remaining = len([c for c in codes if c])  # Count non-empty codes
        except Exception:
            pass
    
    return TwoFactorStatusResponse(
        enabled=enabled,
        created_at=enabled_at,
        backup_codes_remaining=backup_codes_remaining
    )


# ===== ENHANCED 2FA FEATURES =====

# Simple in-memory rate limiting (use Redis in production)
_2fa_attempt_tracker: Dict[int, Dict] = {}


def _check_rate_limit(user_id: int, max_attempts: int = 5, window_seconds: int = 300) -> bool:
    """
    Check if user has exceeded rate limit for 2FA attempts.
    Returns True if allowed, False if rate limited.
    """
    import time
    now = time.time()
    
    if user_id not in _2fa_attempt_tracker:
        _2fa_attempt_tracker[user_id] = {"attempts": 0, "window_start": now}
    
    tracker = _2fa_attempt_tracker[user_id]
    
    # Reset window if expired
    if now - tracker["window_start"] > window_seconds:
        tracker["attempts"] = 0
        tracker["window_start"] = now
    
    if tracker["attempts"] >= max_attempts:
        return False
    
    return True


def _record_attempt(user_id: int):
    """Record a 2FA verification attempt."""
    import time
    now = time.time()
    
    if user_id not in _2fa_attempt_tracker:
        _2fa_attempt_tracker[user_id] = {"attempts": 0, "window_start": now}
    
    _2fa_attempt_tracker[user_id]["attempts"] += 1


def _reset_attempts(user_id: int):
    """Reset attempts after successful verification."""
    if user_id in _2fa_attempt_tracker:
        del _2fa_attempt_tracker[user_id]


def _consume_backup_code(backup_codes_json: str, code: str) -> tuple[bool, str]:
    """
    Check if code is a valid backup code and consume it if so.
    Returns (is_valid, updated_codes_json).
    """
    try:
        codes = json.loads(backup_codes_json)
        code_upper = code.upper().replace("-", "").replace(" ", "")
        
        for i, stored_code in enumerate(codes):
            if stored_code and stored_code.upper() == code_upper:
                # Consume the code by setting it to empty
                codes[i] = ""
                return True, json.dumps(codes)
        
        return False, backup_codes_json
    except Exception:
        return False, backup_codes_json


class TwoFactorVerifyWithBackupRequest(BaseModel):
    code: str  # 6-digit TOTP code OR backup code
    is_backup_code: bool = False


class BackupCodeVerifyResponse(BaseModel):
    success: bool
    message: str
    backup_codes_remaining: int


@router.post("/me/2fa/verify-code", response_model=BackupCodeVerifyResponse)
async def verify_2fa_code(
    request: TwoFactorVerifyWithBackupRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Verify a 2FA code (TOTP or backup code) with rate limiting.
    
    Features:
    - Rate limiting: Max 5 attempts per 5 minutes
    - Supports both TOTP and backup codes
    - Backup codes are consumed on use
    - Audit logging for security events
    """
    from app.services.audit_service import AuditService
    
    # 1. Check rate limit
    if not _check_rate_limit(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification attempts. Please try again in 5 minutes."
        )
    
    # 2. Check if 2FA is enabled
    if not getattr(current_user, 'two_factor_enabled', False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled"
        )
    
    secret = getattr(current_user, 'two_factor_secret', '')
    backup_codes_json = getattr(current_user, 'two_factor_backup_codes', '[]')
    
    # 3. Try to verify
    verified = False
    used_backup = False
    backup_codes_remaining = 0
    
    if request.is_backup_code:
        # Try backup code
        is_valid, updated_codes = _consume_backup_code(backup_codes_json, request.code)
        if is_valid:
            verified = True
            used_backup = True
            current_user.two_factor_backup_codes = updated_codes
            db.add(current_user)
            db.commit()
    else:
        # Try TOTP code
        verified = _verify_totp(secret, request.code)
    
    # 4. Record attempt
    _record_attempt(current_user.id)
    
    # Count remaining backup codes
    try:
        codes = json.loads(getattr(current_user, 'two_factor_backup_codes', '[]'))
        backup_codes_remaining = len([c for c in codes if c])
    except Exception:
        pass
    
    # 5. Audit log
    AuditService.log_action(
        db=db,
        user_id=current_user.id,
        action="2fa_verification_attempt",
        resource_type="security",
        resource_id="2fa",
        details=json.dumps({
            "success": verified,
            "used_backup_code": used_backup,
            "backup_codes_remaining": backup_codes_remaining
        })
    )
    
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )
    
    # Reset attempts on success
    _reset_attempts(current_user.id)
    
    message = "Verification successful"
    if used_backup:
        message = f"Verification successful using backup code. {backup_codes_remaining} backup codes remaining."
    
    return BackupCodeVerifyResponse(
        success=True,
        message=message,
        backup_codes_remaining=backup_codes_remaining
    )


class RegenerateBackupCodesRequest(BaseModel):
    password: str
    code: str  # Current 2FA code to verify


class RegenerateBackupCodesResponse(BaseModel):
    backup_codes: List[str]
    message: str


@router.post("/me/2fa/backup-codes/regenerate", response_model=RegenerateBackupCodesResponse)
async def regenerate_backup_codes(
    request: RegenerateBackupCodesRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Regenerate backup codes (invalidates all existing codes).
    
    Requires:
    - Current password
    - Valid 2FA code
    """
    from app.core.security import verify_password
    from app.services.audit_service import AuditService
    
    if not getattr(current_user, 'two_factor_enabled', False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled"
        )
    
    # Verify password
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )
    
    # Verify 2FA code
    secret = getattr(current_user, 'two_factor_secret', '')
    if not _verify_totp(secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA code"
        )
    
    # Generate new backup codes
    new_codes = _generate_backup_codes()
    current_user.two_factor_backup_codes = json.dumps(new_codes)
    
    db.add(current_user)
    db.commit()
    
    # Audit log
    AuditService.log_action(
        db=db,
        user_id=current_user.id,
        action="2fa_backup_codes_regenerated",
        resource_type="security",
        resource_id="2fa",
        details=json.dumps({"new_codes_count": len(new_codes)})
    )
    
    return RegenerateBackupCodesResponse(
        backup_codes=new_codes,
        message="New backup codes generated. Previous codes are no longer valid. Store these securely."
    )
