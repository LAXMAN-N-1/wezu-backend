from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, UploadFile, File
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
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
    UserStatusUpdate, ActivityLogEntry, ActivityLogResponse, MenuItem, MenuConfigResponse
)
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

    class Config:
        from_attributes = True


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
