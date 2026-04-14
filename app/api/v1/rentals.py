from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List, Optional, Any
from datetime import datetime, UTC, date, timedelta
from pydantic import BaseModel
from app.api import deps
from app.models.user import User
from app.models.rental import Rental, RentalStatus
from app.schemas.rental import (
    RentalCreate, RentalResponse, ActiveRentalResponse,
    RentalAnalyticsResponse, LateFeeBreakdown, ReturnResponse
)
from app.services.rental_service import RentalService
from app.services.late_fee_service import LateFeeService
from app.services.invoice_service import InvoiceService
from fastapi.responses import StreamingResponse

class PriceCalculationRequest(BaseModel):
    battery_id: int
    duration_days: int
    promo_code: Optional[str] = None

class PriceCalculationResponse(BaseModel):
    daily_rate: float
    duration_days: int
    rental_cost: float
    discount: float
    deposit: float
    total_payable: float
    promo_code_id: Optional[int] = None

class ConfirmRentalRequest(BaseModel):
    payment_reference: str

router = APIRouter()

@router.get("/admin/all", response_model=List[RentalResponse])
@router.get("/", response_model=List[RentalResponse])
async def read_rentals(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    station_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    """Admin: paginated list of all rentals with filters."""
    from sqlmodel import select
    statement = select(Rental)
    if status:
        statement = statement.where(Rental.status == status)
    if user_id:
        statement = statement.where(Rental.user_id == user_id)
    if station_id:
        statement = statement.where(Rental.start_station_id == station_id)
    if start_date:
        statement = statement.where(Rental.start_time >= start_date)
        
    return db.exec(statement.offset(skip).limit(limit)).all()

@router.get("/my", response_model=List[RentalResponse])
async def read_my_rentals(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Customer: own rental history paginated."""
    return RentalService.get_history(db, current_user.id)[skip : skip + limit]

@router.post("/", response_model=RentalResponse)
async def create_rental(
    rental_in: RentalCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    # Check if user has active rental? Logic in service or here.
    # Service doesn't check, let's assume multiple rentals allowed or enforced globally.
    # Enforce station operational hours and maintenance schedules
    from app.services.dealer_station_service import DealerStationService
    is_operational, msg = DealerStationService.is_station_operational(db, rental_in.start_station_id)
    if not is_operational:
         raise HTTPException(status_code=400, detail=msg)
         
    return RentalService.create_rental(db, current_user.id, rental_in)

@router.get("/active", response_model=List[RentalResponse])
async def read_active_rentals(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get list of active rentals (usually just one)"""
    return RentalService.get_active_rentals(db, current_user.id)

@router.get("/active/current", response_model=Optional[RentalResponse])
async def read_current_active_rental(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get the single current active or pending rental"""
    return RentalService.get_current_rental(db, current_user.id)

@router.get("/history", response_model=List[RentalResponse])
async def read_rental_history(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    return RentalService.get_history(db, current_user.id)

@router.post("/{rental_id}/return", response_model=RentalResponse)
async def return_rental_battery(
    rental_id: int,
    station_id: int, # Pass as query param or body? Usually body. Simplifying to query for now or fix schema.
    # Let's use query param for simplicity or body if complex.
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    # Verify rental belongs to user
    # logic in service usually, but service.return_battery(rental_id) assumes valid rental_id
    # We should verify ownership here.
    rental = RentalService.return_battery(db, rental_id, station_id)
    if rental.user_id != current_user.id:
         raise HTTPException(status_code=403, detail="Not authorized")
    return rental

# Rental Modifications
from pydantic import BaseModel
from app.models.rental_modification import RentalExtension, RentalPause
from app.models.late_fee import LateFee, LateFeeWaiver

class ExtensionRequest(BaseModel):
    requested_end_date: datetime
    reason: Optional[str] = None

class PauseRequest(BaseModel):
    pause_start_date: datetime
    pause_end_date: datetime
    reason: str

class WaiverRequest(BaseModel):
    requested_waiver_amount: float
    reason: str
    supporting_documents: Optional[str] = None

@router.post("/{rental_id}/extend", response_model=RentalExtension)
async def request_extension(
    rental_id: int,
    req: ExtensionRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Request rental extension"""
    from app.models.rental import Rental
    from sqlmodel import select
    
    rental = db.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rental not found")
    
    if rental.status != "active":
        raise HTTPException(status_code=400, detail="Rental is not active")
    
    # Calculate extension days and cost
    extension_days = (req.requested_end_date - rental.end_time).days if rental.end_time else 0
    if extension_days <= 0:
        raise HTTPException(status_code=400, detail="Extension date must be after current end date")
    
    # Compute daily rate from total_amount and original duration
    duration_secs = (rental.expected_end_time - rental.start_time).total_seconds() if rental.expected_end_time else 86400
    original_days = max(1, int(duration_secs / 86400))
    daily_rate = rental.total_amount / original_days if original_days > 0 else 0
    additional_cost = extension_days * daily_rate
    
    extension = RentalExtension(
        rental_id=rental_id,
        user_id=current_user.id,
        current_end_date=rental.end_time,
        requested_end_date=req.requested_end_date,
        extension_days=extension_days,
        additional_cost=additional_cost,
        reason=req.reason,
        status="PENDING"
    )
    db.add(extension)
    db.commit()
    db.refresh(extension)
    return extension

@router.post("/{rental_id}/pause", response_model=RentalPause)
async def request_pause(
    rental_id: int,
    req: PauseRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Request rental pause"""
    from app.models.rental import Rental
    
    rental = db.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rental not found")
    
    if rental.status != "active":
        raise HTTPException(status_code=400, detail="Rental is not active")
    
    pause_days = (req.pause_end_date - req.pause_start_date).days
    if pause_days <= 0:
        raise HTTPException(status_code=400, detail="Invalid pause period")
    
    # Compute daily rate from total_amount and original duration
    duration_secs = (rental.expected_end_time - rental.start_time).total_seconds() if rental.expected_end_time else 86400
    original_days = max(1, int(duration_secs / 86400))
    daily_rate = rental.total_amount / original_days if original_days > 0 else 0
    # Reduced rate during pause (e.g., 20% of daily rate)
    daily_pause_charge = daily_rate * 0.2
    total_pause_cost = daily_pause_charge * pause_days
    
    pause = RentalPause(
        rental_id=rental_id,
        user_id=current_user.id,
        pause_start_date=req.pause_start_date,
        pause_end_date=req.pause_end_date,
        pause_days=pause_days,
        reason=req.reason,
        daily_pause_charge=daily_pause_charge,
        total_pause_cost=total_pause_cost,
        status="PENDING"
    )
    db.add(pause)
    db.commit()
    db.refresh(pause)
    return pause

@router.post("/{rental_id}/resume")
async def resume_rental(
    rental_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Resume paused rental"""
    from sqlmodel import select
    
    pause = db.exec(
        select(RentalPause)
        .where(RentalPause.rental_id == rental_id)
        .where(RentalPause.status == "ACTIVE")
    ).first()
    
    if not pause:
        raise HTTPException(status_code=404, detail="No active pause found")
    
    if pause.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    pause.status = "COMPLETED"
    pause.battery_reclaimed_at = datetime.now(UTC)
    db.add(pause)
    db.commit()
    
    return {"status": "resumed", "message": "Rental resumed successfully"}

@router.get("/{rental_id}/late-fees")
async def get_late_fees(
    rental_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get late fee details with hourly breakdown"""
    rental = db.get(Rental, rental_id)
    if not rental or (rental.user_id != current_user.id and not current_user.is_superuser):
        raise HTTPException(status_code=404, detail="Rental not found")
    
    # Calculate live fee
    fee_details = LateFeeService.calculate_late_fee(rental_id, db)
    
    return {
        "rental_id": rental_id,
        "is_late": fee_details["is_late"],
        "hours_overdue": fee_details["hours_late"],
        "chargeable_hours": fee_details.get("chargeable_hours", 0),
        "hourly_rate": fee_details.get("hourly_rate", 0),
        "total_late_fee": fee_details["late_fee"],
        "breakdown": {
            "grace_period_hours": 2, # Standardized or from settings
            "hourly_penalty_multiplier": 1.5,
            "calculation": f"{fee_details.get('chargeable_hours', 0)} chargeable hours x ₹{fee_details.get('hourly_rate', 0)}/hr x 1.5 multiplier"
        }
    }

@router.post("/{rental_id}/late-fees/waiver", response_model=LateFeeWaiver)
async def request_late_fee_waiver(
    rental_id: int,
    req: WaiverRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Request late fee waiver"""
    from sqlmodel import select
    
    late_fee = db.exec(
        select(LateFee).where(LateFee.rental_id == rental_id)
    ).first()
    
    if not late_fee:
        raise HTTPException(status_code=404, detail="No late fees found")
    
    if late_fee.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if late_fee.amount_outstanding == 0:
        raise HTTPException(status_code=400, detail="No outstanding late fees")
    
    waiver = LateFeeWaiver(
        late_fee_id=late_fee.id,
        user_id=current_user.id,
        requested_waiver_amount=req.requested_waiver_amount,
        reason=req.reason,
        supporting_documents=req.supporting_documents,
        status="PENDING"
    )
    db.add(waiver)
    db.commit()
    db.refresh(waiver)
    return waiver

from app.services.station_service import StationService
from app.models.battery import Battery
from app.models.battery_catalog import BatteryCatalog
from app.schemas.station import NearbyStationResponse

class SwapRequest(BaseModel):
    station_id: int
    reason: str = "health_check"

@router.get("/{rental_id}/swap-suggestions", response_model=List[NearbyStationResponse])
async def get_swap_suggestions(
    rental_id: int,
    lat: float,
    lon: float,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    FR-MOB-ACTIVE-006: Intelligent Swap Suggestions.
    Suggests the top 3 nearest stations that have a compatible, fully charged battery.
    """
    rental = db.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rental not found")
        
    if rental.status != "active":
        raise HTTPException(status_code=400, detail="Rental is not active")
        
    battery = db.get(Battery, rental.battery_id)
    if not battery:
        raise HTTPException(status_code=404, detail="Original battery not found")
        
    # Get the spec of the current battery to find compatible ones
    catalog = db.get(BatteryCatalog, battery.sku_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Battery specs not found")
        
    # Query nearby stations filtering by the same battery type and minimum capacity
    stations = StationService.get_nearby(
        db, lat, lon, radius_km=15.0,
        status="active",
        battery_type=catalog.battery_type,
        min_capacity=catalog.capacity_mah,
        sort_by="distance"
    )
    
    # Return top 3
    return stations[:3]

@router.post("/{rental_id}/swap-request", response_model=RentalResponse)
async def request_battery_swap(
    rental_id: int,
    req: SwapRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Initiate a battery swap"""
    rental = db.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
         raise HTTPException(status_code=404, detail="Rental not found")
         
    if rental.status != "active":
         raise HTTPException(status_code=400, detail="Rental is not active")
    
    # Record swap request as a RentalEvent (Rental model has no swap fields)
    from app.models.rental_event import RentalEvent as SwapRentalEvent
    swap_event = SwapRentalEvent(
        rental_id=rental.id,
        event_type="swap_requested",
        station_id=req.station_id,
        battery_id=rental.battery_id,
        description=f"Swap requested at station #{req.station_id}: {req.reason}",
    )
    db.add(swap_event)
    db.add(rental)
    db.commit()
    db.refresh(rental)
    
    return rental

# DECONFLICTED P0-B: POST /{rental_id}/report-issue removed.
# Canonical handler lives in app/api/v1/rentals_enhanced.py
# (uses WorkflowAutomationService for ticket notification).
# Removed 2026-04-06.

# DECONFLICTED P0-B: GET /{rental_id}/receipt removed.
# Canonical handler lives in app/api/v1/rentals_enhanced.py
# (returns structured receipt JSON instead of requiring InvoiceService PDF).
# Removed 2026-04-06.
