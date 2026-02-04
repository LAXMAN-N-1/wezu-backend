from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.battery import Battery, BatteryLifecycleEvent
from app.schemas.battery import (
    BatteryCreate, BatteryBulkCreate, BatteryResponse, 
    BatteryDetailResponse, BatteryUpdate
)

router = APIRouter()

@router.get("/", response_model=List[BatteryResponse])
def read_batteries(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
) -> Any:
    """
    Retrieve batteries.
    """
    batteries = session.exec(select(Battery).offset(skip).limit(limit)).all()
    return batteries

@router.post("/", response_model=BatteryResponse)
def create_battery(
    *,
    session: Session = Depends(get_session),
    battery_in: BatteryCreate,
) -> Any:
    """
    Create a new battery.
    """
    battery = Battery.from_orm(battery_in)
    session.add(battery)
    session.commit()
    session.refresh(battery)
    
    # Log creation event
    event = BatteryLifecycleEvent(
        battery_id=battery.id,
        event_type="created",
        description="Initial inventory registration"
    )
    session.add(event)
    session.commit()
    
    return battery

@router.post("/bulk", response_model=List[BatteryResponse])
def bulk_create_batteries(
    *,
    session: Session = Depends(get_session),
    bulk_in: BatteryBulkCreate,
) -> Any:
    """
    Bulk create batteries.
    """
    new_batteries = []
    for item in bulk_in.items:
        # Check duplicate
        existing = session.exec(select(Battery).where(Battery.serial_number == item.serial_number)).first()
        if existing:
            continue # Skip duplicates or handle error
            
        battery = Battery.from_orm(item)
        session.add(battery)
        session.commit() 
        session.refresh(battery)
        
        event = BatteryLifecycleEvent(
            battery_id=battery.id,
            event_type="created",
            description="Bulk upload"
        )
        session.add(event)
        new_batteries.append(battery)
        
    session.commit()
    return new_batteries

@router.get("/{battery_id}", response_model=BatteryDetailResponse)
def read_battery(
    *,
    session: Session = Depends(get_session),
    battery_id: int,
) -> Any:
    """
    Get battery by ID with history.
    """
    battery = session.get(Battery, battery_id)
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    return battery

@router.put("/{battery_id}/lifecycle", response_model=BatteryResponse)
def update_battery_lifecycle(
    *,
    session: Session = Depends(get_session),
    battery_id: int,
    update_in: BatteryUpdate,
) -> Any:
    """
    Update battery status/lifecycle.
    """
    battery = session.get(Battery, battery_id)
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    
    if update_in.status:
        battery.status = update_in.status
        
        # Log event
        event = BatteryLifecycleEvent(
            battery_id=battery.id,
            event_type="status_change",
            description=f"Status changed to {update_in.status}. {update_in.description or ''}"
        )
        session.add(event)
        
    if update_in.location_type:
        battery.location_type = update_in.location_type
    if update_in.location_id:
        battery.location_id = update_in.location_id
        
    session.add(battery)
    session.commit()
    session.refresh(battery)
    return battery
