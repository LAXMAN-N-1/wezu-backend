from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select
from typing import List
import os
import shutil
from PIL import Image
import json

from app.models.user import User
from app.models.address import Address
from app.models.session import UserSession
from app.models.login_history import LoginHistory

from app.schemas.user import (
    UserResponse,
    UserUpdate,
    AddressCreate,
    AddressUpdate,
    AddressResponse,
)

from app.api import deps
from app.core.security import verify_password, get_password_hash

router = APIRouter()

# -------------------------
# PROFILE ENDPOINTS
# -------------------------

@router.get("", response_model=UserResponse)
def get_profile(current_user: User = Depends(deps.get_current_user)):
    """Get full customer profile"""
    return current_user


@router.put("", response_model=UserResponse)
def update_profile(
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Update profile details"""

    if user_in.full_name:
        current_user.full_name = user_in.full_name

    if user_in.phone:
        current_user.phone = user_in.phone

    if user_in.date_of_birth:
        current_user.date_of_birth = user_in.date_of_birth

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return current_user


@router.delete("/account")
def deactivate_account(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Deactivate customer account"""

    current_user.is_active = False
    db.add(current_user)
    db.commit()

    return {"message": "Account deactivated successfully"}


# -------------------------
# ADDRESS MANAGEMENT
# -------------------------

@router.get("/addresses", response_model=List[AddressResponse])
def get_addresses(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get all user addresses"""

    addresses = db.exec(
        select(Address).where(Address.user_id == current_user.id)
    ).all()

    return addresses


@router.post("/addresses", response_model=AddressResponse)
def create_address(
    address_in: AddressCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Create new address"""

    address = Address(
        user_id=current_user.id,
        address_line1=address_in.street_address,
        city=address_in.city,
        state=address_in.state,
        postal_code=address_in.postal_code,
        country=address_in.country,
        type=address_in.type,
        latitude=address_in.latitude,
        longitude=address_in.longitude,
        is_default=address_in.is_default,
    )

    if address.is_default:

        existing_defaults = db.exec(
            select(Address).where(
                Address.user_id == current_user.id,
                Address.is_default == True,
            )
        ).all()

        for addr in existing_defaults:
            addr.is_default = False
            db.add(addr)

    db.add(address)
    db.commit()
    db.refresh(address)

    return address


@router.put("/addresses/{address_id}", response_model=AddressResponse)
def update_address(
    address_id: int,
    address_in: AddressUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Update address"""

    address = db.get(Address, address_id)

    if not address or address.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Address not found")

    if address_in.street_address:
        address.address_line1 = address_in.street_address

    if address_in.city:
        address.city = address_in.city

    if address_in.state:
        address.state = address_in.state

    if address_in.postal_code:
        address.postal_code = address_in.postal_code

    if address_in.type:
        address.type = address_in.type

    db.add(address)
    db.commit()
    db.refresh(address)

    return address


@router.delete("/addresses/{address_id}")
def delete_address(
    address_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Delete address"""

    address = db.get(Address, address_id)

    if not address or address.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Address not found")

    db.delete(address)
    db.commit()

    return {"message": "Address deleted successfully"}


# -------------------------
# PREFERENCES CONFIGURATION
# -------------------------

@router.get("/preferences")
def get_preferences(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get notification preferences"""
    from app.models.notification_preference import NotificationPreference
    from sqlmodel import select
    
    pref = db.exec(
        select(NotificationPreference).where(NotificationPreference.user_id == current_user.id)
    ).first()

    if pref:
        dump = pref.model_dump(exclude={"id", "user_id", "updated_at"})
        if dump.get('quiet_hours_start'):
            dump['quiet_hours_start'] = dump['quiet_hours_start'].strftime("%H:%M")
        if dump.get('quiet_hours_end'):
            dump['quiet_hours_end'] = dump['quiet_hours_end'].strftime("%H:%M")
        return dump

    return {}


@router.put("/preferences")
def update_preferences(
    preferences: dict,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Update preferences"""
    from app.models.notification_preference import NotificationPreference
    from sqlmodel import select
    
    pref = db.exec(
        select(NotificationPreference).where(NotificationPreference.user_id == current_user.id)
    ).first()

    if not pref:
        pref = NotificationPreference(user_id=current_user.id)
        db.add(pref)
        
    for key, value in preferences.items():
        if hasattr(pref, key) and key not in ["id", "user_id"]:
            setattr(pref, key, value)

    db.commit()

    return {"message": "Preferences updated"}


# -------------------------
# PROFILE PICTURE
# -------------------------

@router.post("/picture", response_model=UserResponse)
def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Upload profile picture and resize"""

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    upload_dir = "uploads/profiles"
    os.makedirs(upload_dir, exist_ok=True)

    file_path = f"{upload_dir}/{current_user.id}.jpg"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    img = Image.open(file_path)
    img = img.resize((300, 300))
    img.save(file_path)

    current_user.profile_picture = file_path

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return current_user


# -------------------------
# ACCOUNT SECURITY
# -------------------------

@router.post("/change-password")
def change_password(
    data: dict,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Change password"""

    if not verify_password(data["old_password"], current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")

    current_user.hashed_password = get_password_hash(data["new_password"])

    db.add(current_user)
    db.commit()

    return {"message": "Password updated successfully"}


@router.get("/login-history")
def login_history(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get login history"""

    history = db.exec(
        select(LoginHistory).where(LoginHistory.user_id == current_user.id)
    ).all()

    return history


@router.get("/sessions")
def get_sessions(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """List active sessions"""

    sessions = db.exec(
        select(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.is_active == True,
        )
    ).all()

    return sessions


@router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Revoke session"""

    session = db.get(UserSession, session_id)

    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_active = False

    db.add(session)
    db.commit()

    return {"message": "Session revoked"}