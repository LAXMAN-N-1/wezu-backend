from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.user import User
from app.models.address import Address
from app.schemas.user import UserResponse, UserUpdate, AddressCreate, AddressUpdate, AddressResponse
from app.api import deps
import shutil
import os
from typing import List

router = APIRouter()

@router.get("/", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(deps.get_current_user),
):
    """Get current user's profile"""
    return current_user

@router.put("/", response_model=UserResponse)
async def update_profile(
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Update user profile details"""
    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name
    if user_in.email is not None:
        # Check uniqueness if email changes
        if user_in.email != current_user.email:
            existing = db.exec(select(User).where(User.email == user_in.email)).first()
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use")
            current_user.email = user_in.email
            # Trigger email verification logic here if needed
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/picture", response_model=UserResponse)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Upload profile picture"""
    # 1. Validate file size/type (Basic validation)
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
        
    # 2. Save file (Local storage for MVP)
    upload_dir = "uploads/profiles"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = f"{upload_dir}/{current_user.id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 3. Update User
    # In production, this would be a CDN URL
    current_user.profile_picture = file_path
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

# Address Management

@router.post("/address", response_model=AddressResponse)
async def create_address(
    address_in: AddressCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Add a new address"""
    # Create Address object
    # Note: Address model has address_line1, address_line2 but schema uses street_address
    # Mapping for backward compatibility or updating schema is needed.
    # checking schema from view_file earlier: AddressCreate (AddressBase) has street_address.
    # model has address_line1. We map street_address -> address_line1
    
    address = Address(
        user_id=current_user.id,
        address_line1=address_in.street_address, # Mapping
        city=address_in.city,
        state=address_in.state,
        postal_code=address_in.postal_code,
        country=address_in.country,
        type=address_in.type,
        latitude=address_in.latitude,
        longitude=address_in.longitude,
        is_default=address_in.is_default
    )
    
    if address.is_default:
        # Unset other defaults
        existing_defaults = db.exec(select(Address).where(Address.user_id == current_user.id, Address.is_default == True)).all()
        for addr in existing_defaults:
            addr.is_default = False
            db.add(addr)
    
    db.add(address)
    db.commit()
    db.refresh(address)
    return address

@router.put("/address/{address_id}", response_model=AddressResponse)
async def update_address(
    address_id: int,
    address_in: AddressUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Update an existing address"""
    address = db.get(Address, address_id)
    if not address or address.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Address not found")
        
    if address_in.street_address is not None:
        address.address_line1 = address_in.street_address
    if address_in.city is not None:
        address.city = address_in.city
    if address_in.state is not None:
        address.state = address_in.state
    if address_in.postal_code is not None:
        address.postal_code = address_in.postal_code
    if address_in.type is not None:
        address.type = address_in.type
    if address_in.is_default is not None:
        address.is_default = address_in.is_default
        if address.is_default:
             # Unset other defaults
            existing_defaults = db.exec(select(Address).where(Address.user_id == current_user.id, Address.is_default == True, Address.id != address_id)).all()
            for addr in existing_defaults:
                addr.is_default = False
                db.add(addr)
                
    db.add(address)
    db.commit()
    db.refresh(address)
    return address

@router.delete("/address/{address_id}")
async def delete_address(
    address_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Delete an address"""
    address = db.get(Address, address_id)
    if not address or address.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Address not found")
        
    db.delete(address)
    db.commit()
    return {"message": "Address deleted successfully"}
