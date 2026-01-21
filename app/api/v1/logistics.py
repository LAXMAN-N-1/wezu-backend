from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from app.db.session import get_session
from app.models.logistics import DeliveryAssignment, DriverProfile
from app.models.user import User
from app.services.logistics_service import LogisticsService
from app.services.driver_service import DriverService
from app.api.deps import get_current_user
from app.schemas.common import DataResponse
from pydantic import BaseModel

router = APIRouter()

# Schemas
class DriverOnboard(BaseModel):
    license_number: str
    vehicle_type: str
    vehicle_plate: str

class LocationUpdate(BaseModel):
    lat: float
    lng: float

class StatusUpdate(BaseModel):
    is_online: bool

class AssignRequest(BaseModel):
    delivery_id: int
    driver_id: int

class DeliveryStatusUpdate(BaseModel):
    status: str # PICKED_UP, DELIVERED, FAILED
    pod_img: Optional[str] = None
    signature: Optional[str] = None

# Driver Endpoints
@router.post("/drivers/onboard", response_model=DataResponse[DriverProfile])
def onboard_driver(
    data: DriverOnboard,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    existing = DriverService.get_profile(current_user.id)
    if existing:
        raise HTTPException(status_code=400, detail="Driver profile already exists")
    
    profile = DriverService.create_profile(current_user.id, data.dict())
    return DataResponse(data=profile)

@router.post("/drivers/status", response_model=DataResponse[dict])
def update_driver_status(
    status: StatusUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    profile = DriverService.get_profile(current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a driver")
    
    DriverService.toggle_status(profile.id, status.is_online)
    return DataResponse(data={"status": "online" if status.is_online else "offline"})

@router.post("/drivers/location", response_model=DataResponse[dict])
def update_location(
    loc: LocationUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    profile = DriverService.get_profile(current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a driver")
    
    DriverService.update_location(profile.id, loc.lat, loc.lng)
    return DataResponse(data={"message": "Location updated"})

@router.get("/drivers/deliveries", response_model=DataResponse[List[DeliveryAssignment]])
def get_driver_deliveries(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    profile = DriverService.get_profile(current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a driver")
    
    query = select(DeliveryAssignment).where(DeliveryAssignment.driver_id == profile.id)
    if status:
        query = query.where(DeliveryAssignment.status == status)
    
    deliveries = session.exec(query).all()
    return DataResponse(data=deliveries)

# Delivery Ops (Admin/System)
@router.post("/deliveries/assign", response_model=DataResponse[DeliveryAssignment])
def assign_delivery(
    req: AssignRequest,
    current_user: User = Depends(get_current_user), # Admin check needed
    session: Session = Depends(get_session)
):
    try:
        delivery = LogisticsService.assign_driver(req.delivery_id, req.driver_id)
        return DataResponse(data=delivery)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/deliveries/{id}/status", response_model=DataResponse[DeliveryAssignment])
def update_delivery_status_endpoint(
    id: int,
    update: DeliveryStatusUpdate,
    current_user: User = Depends(get_current_user), # Driver check needed
    session: Session = Depends(get_session)
):
    # Verify driver owns this delivery
    profile = DriverService.get_profile(current_user.id)
    delivery = session.get(DeliveryAssignment, id)
    if not delivery:
         raise HTTPException(status_code=404, detail="Delivery not found")
         
    if profile and delivery.driver_id != profile.id:
        raise HTTPException(status_code=403, detail="Not assigned to this delivery")

    try:
        updated = LogisticsService.update_delivery_status(id, update.status, update.pod_img, update.signature)
        return DataResponse(data=updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
