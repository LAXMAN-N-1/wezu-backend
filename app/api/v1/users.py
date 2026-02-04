from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlmodel import Session
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.models.address import Address
from app.schemas.user import UserResponse, UserUpdate, AddressCreate, AddressResponse, AddressUpdate, DeviceCreate, DeviceResponse
from app.services.user_service import UserService
import os
import shutil

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def read_user_me(
    current_user: User = Depends(deps.get_current_user),
):
    return current_user

from app.schemas.user import UserNavigationResponse
from app.services.rbac_service import RBACService
from sqlmodel import Session

@router.get("/me/navigation", response_model=UserNavigationResponse)
async def get_user_navigation(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Returns the dynamic menu and permissions for the current user.
    """
    permissions = RBACService.get_user_permissions(db, current_user.id)
    menu = RBACService.generate_menu_config(permissions)
    
    return UserNavigationResponse(
        user_id=current_user.id,
        roles=[r.name for r in current_user.roles],
        permissions=list(permissions),
        menu_config=menu
    )

@router.put("/me", response_model=UserResponse)
async def update_user_me(
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    user = UserService.update_user(db, current_user, user_in)
    return user

@router.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
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
