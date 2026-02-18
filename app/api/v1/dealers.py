from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlmodel import Session, select
from typing import List, Optional, Any
from datetime import datetime
from app.db.session import get_session
from app.models.dealer import DealerProfile, DealerApplication
from app.models.user import User
from app.services.dealer_service import DealerService
from app.api.deps import get_current_user
from app.schemas.common import DataResponse
from app.schemas.dealer import DealerProfileCreate, DealerProfileUpdate, DealerProfileResponse
from pydantic import BaseModel

router = APIRouter()


# --- Dealer Profile CRUD ---

@router.post("/", response_model=DataResponse[DealerProfileResponse])
def create_dealer_profile(
    profile_in: DealerProfileCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Create a new dealer profile (Onboarding)."""
    existing = DealerService.get_dealer_by_user(session, current_user.id)
    if existing:
        raise HTTPException(status_code=400, detail="Dealer profile already exists")
    
    profile = DealerService.create_dealer_profile(session, current_user.id, profile_in.dict())
    return DataResponse(data=profile, message="Dealer profile created")

@router.get("/", response_model=DataResponse[List[DealerProfileResponse]])
def read_dealers(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user), # Should be Admin only
    session: Session = Depends(get_session)
):
    """Retrieve all dealers."""
    # Add RBAC check here
    dealers = DealerService.get_dealers(session, skip=skip, limit=limit)
    return DataResponse(data=dealers)

@router.get("/me", response_model=DataResponse[dict])
def get_my_status(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get current user's dealer profile and application status."""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
        
    app = session.exec(select(DealerApplication).where(DealerApplication.dealer_id == profile.id)).first()
    
    return DataResponse(data={
        "profile": profile,
        "application": app
    })

@router.get("/{id}", response_model=DataResponse[DealerProfileResponse])
def read_dealer(
    id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get dealer by ID."""
    dealer = DealerService.get_dealer_by_id(session, id)
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    return DataResponse(data=dealer)

@router.put("/me", response_model=DataResponse[DealerProfileResponse])
def update_my_profile(
    profile_in: DealerProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update current user's dealer profile."""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    
    dealer = DealerService.update_dealer_profile(session, profile.id, profile_in)
    return DataResponse(data=dealer, message="Profile updated")

@router.put("/{id}", response_model=DataResponse[DealerProfileResponse])
def update_dealer(
    id: int,
    profile_in: DealerProfileUpdate,
    current_user: User = Depends(get_current_user), # Should be Admin
    session: Session = Depends(get_session)
):
    """Update a specific dealer profile (Admin)."""
    dealer = DealerService.update_dealer_profile(session, id, profile_in)
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    return DataResponse(data=dealer, message="Profile updated")
