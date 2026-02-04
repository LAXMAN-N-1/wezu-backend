from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.api import deps
from app.db.session import get_session
from app.models.logistics import Warehouse, BatteryTransfer
from app.models.battery import Battery
from app.models.user import User
from app.schemas.logistics import (
    WarehouseCreate, WarehouseResponse,
    BatteryTransferCreate, BatteryTransferResponse
)

router = APIRouter()

# --- Warehouses ---
@router.post("/warehouses", response_model=WarehouseResponse)
def create_warehouse(
    *,
    session: Session = Depends(get_session),
    wh_in: WarehouseCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Create a new warehouse location.
    """
    wh = Warehouse.from_orm(wh_in)
    session.add(wh)
    session.commit()
    session.refresh(wh)
    return wh

@router.get("/warehouses", response_model=List[WarehouseResponse])
def read_warehouses(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List all warehouses.
    """
    return session.exec(select(Warehouse)).all()

# --- Transfers ---
@router.post("/transfers", response_model=BatteryTransferResponse)
def initiate_transfer(
    *,
    session: Session = Depends(get_session),
    transfer_in: BatteryTransferCreate,
    current_user: User = Depends(deps.get_current_user), # Logistics Manager
) -> Any:
    """
    Initiate a battery transfer.
    """
    # 1. Validate Battery
    battery = session.get(Battery, transfer_in.battery_id)
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
        
    # 2. Update Battery Location to 'transit'
    battery.location_type = "transit"
    # location_id logic depends on how we track transit (e.g., vehicle_id or None)
    session.add(battery)
    
    # 3. Create Transfer Record
    transfer = BatteryTransfer.from_orm(transfer_in)
    transfer.status = "in_transit"
    session.add(transfer)
    
    session.commit()
    session.refresh(transfer)
    return transfer

@router.put("/transfers/{transfer_id}/complete", response_model=BatteryTransferResponse)
def complete_transfer(
    *,
    session: Session = Depends(get_session),
    transfer_id: int,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Mark transfer as completed and update battery location.
    """
    transfer = session.get(BatteryTransfer, transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
        
    battery = session.get(Battery, transfer.battery_id)
    
    # Update Status
    transfer.status = "completed"
    transfer.completed_at = datetime.utcnow()
    
    # Update Battery Location
    battery.location_type = transfer.to_location_type
    battery.location_id = transfer.to_location_id
    
    session.add(transfer)
    session.add(battery)
    session.commit()
    session.refresh(transfer)
    return transfer
