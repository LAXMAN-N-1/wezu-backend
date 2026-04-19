from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from app.db.session import get_session
from app.models.driver_profile import DriverProfile
from app.models.user import User
from app.services.driver_service import DriverService
from app.api.deps import get_current_user
from app.schemas.common import DataResponse
from pydantic import BaseModel

router = APIRouter()

class DriverProfileCreate(BaseModel):
    license_number: str
    vehicle_type: str # e.g., "bike", "scooter", "truck"
    vehicle_plate: str

@router.post("/onboard", response_model=DataResponse[DriverProfile])
def onboard_driver(
    profile_in: DriverProfileCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Onboard a new driver.
    Creates a DriverProfile linked to the current user.
    """
    # 1. Check if profile already exists
    existing_profile = DriverService.get_profile(session, current_user.id)
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Driver profile already exists for this user"
        )
    
    # 2. Create Profile
    try:
        profile = DriverService.create_profile(session, current_user.id, profile_in.model_dump())
        
        # 3. Assign 'Driver' role if not present
        from app.models.rbac import Role, UserRole
        
        driver_role = session.exec(select(Role).where(Role.name == "driver")).first()
        
        if driver_role:
            # Check existence in link table directly
            existing_link = session.exec(
                select(UserRole).where(
                    UserRole.user_id == current_user.id,
                    UserRole.role_id == driver_role.id
                )
            ).first()
            
            if not existing_link:
                # Add new link
                new_link = UserRole(user_id=current_user.id, role_id=driver_role.id)
                session.add(new_link)
                session.commit()
            
        return DataResponse(data=profile, message="Driver onboarded successfully")
        
    except Exception as e:
        # Check for unique violation (user already has profile)
        if "unique constraint" in str(e).lower() and "driver_profiles" in str(e).lower():
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Driver profile already exists"
            )
            
        # If it's the role uniqueness violation, we can ignore it as the goal is achieved
        if "unique constraint" in str(e).lower() and "user_roles" in str(e).lower():
            # Role already exists, which is fine
            return DataResponse(data=profile, message="Driver onboarded successfully (Role already assigned)")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create driver profile"
        )

@router.get("/me", response_model=DataResponse[DriverProfile])
def get_my_driver_profile(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get current user's driver profile."""
    profile = DriverService.get_profile(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Driver profile not found")
        
    return DataResponse(data=profile)

@router.get("/routes")
def get_assigned_routes(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get driver's assigned routes."""
    from app.models.delivery_route import DeliveryRoute
    from app.models.roles import RoleEnum
    
    # Check driver profile existence
    profile = DriverService.get_profile(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Driver profile not found")
        
    query = select(DeliveryRoute)
    
    # Auto-filter: Driver context can ONLY see assigned routes
    user_role = getattr(request.state, 'user_role', None)
    if user_role == RoleEnum.DRIVER:
        query = query.where(DeliveryRoute.driver_id == profile.id)
        
    routes = session.exec(query).all()
    # Safe dump since we do not have a response model here setup yet
    return DataResponse(data=routes)

