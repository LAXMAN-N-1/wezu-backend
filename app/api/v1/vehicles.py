from __future__ import annotations
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.api.deps import get_current_user
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleUpdate, VehicleResponse
from app.api import deps

router = APIRouter()

@router.get("/", response_model=List[VehicleResponse])
def read_my_vehicles(
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get current user's vehicles.
    """
    return current_user.vehicles

@router.post("/", response_model=VehicleResponse)
def create_vehicle(
    *,
    session: Session = Depends(deps.get_db),
    vehicle_in: VehicleCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Register a new vehicle for current user.
    """
    # Check if registration already exists
    existing = session.exec(select(Vehicle).where(Vehicle.registration_number == vehicle_in.registration_number)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vehicle with this registration number already registered")
        
    vehicle = Vehicle.from_orm(vehicle_in)
    vehicle.user_id = current_user.id
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return vehicle

@router.delete("/{vehicle_id}")
def delete_vehicle(
    *,
    session: Session = Depends(deps.get_db),
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Delete a vehicle.
    """
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=400, detail="Not enough permissions")
        
    session.delete(vehicle)
    session.commit()
    return {"ok": True}