from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, select
from app.api import deps
from app.models.user import User
from app.models.logistics import BatteryTransfer
from app.models.inventory_audit import InventoryAuditLog
from app.schemas.inventory import TransferCreate, TransferResponse, AuditLogResponse
from app.services.inventory_service import InventoryService
import csv
import io

router = APIRouter()

@router.post("/transfers", response_model=TransferResponse)
def create_transfer_order(
    *,
    session: Session = Depends(deps.get_db),
    transfer_in: TransferCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Create a transfer order to move batteries between stations"""
    try:
        return InventoryService.create_transfer(session, transfer_in, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/transfers", response_model=List[TransferResponse])
def list_transfers(
    *,
    session: Session = Depends(deps.get_db),
    status: Optional[str] = None,
    battery_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """List all transfer orders with status"""
    statement = select(BatteryTransfer)
    if status:
        statement = statement.where(BatteryTransfer.status == status)
    if battery_id:
        statement = statement.where(BatteryTransfer.battery_id == battery_id)
        
    return session.exec(statement.offset(skip).limit(limit)).all()

@router.get("/low-stock", response_model=List[dict])
def get_low_stock_alerts(
    threshold: int = Query(5, description="Low stock threshold"),
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Admin: stations or warehouses with battery counts below threshold"""
    from app.models.station import Station, StationSlot
    from sqlmodel import func
    
    # Query stations with few 'ready' batteries
    stmt = select(Station.id, Station.name, func.count(StationSlot.id).label("ready_count")).join(StationSlot).where(StationSlot.status == "ready").group_by(Station.id).having(func.count(StationSlot.id) < threshold)
    results = session.execute(stmt).all()
    
    return [
        {"location_id": r[0], "location_name": r[1], "count": r[2], "type": "station"}
        for r in results
    ]

@router.get("/transfers/{id}", response_model=TransferResponse)
def get_transfer_detail(
    *,
    session: Session = Depends(deps.get_db),
    id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Transfer order detail"""
    transfer = session.get(BatteryTransfer, id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return transfer

@router.put("/transfers/{id}/confirm", response_model=TransferResponse)
def confirm_transfer_receipt(
    *,
    session: Session = Depends(deps.get_db),
    id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Confirm batteries received at destination station"""
    try:
        return InventoryService.confirm_receipt(session, id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/audit-trail", response_model=List[AuditLogResponse])
def get_inventory_audit_trail(
    *,
    session: Session = Depends(deps.get_db),
    battery_id: Optional[int] = None,
    action: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Full audit log of inventory changes with filters"""
    statement = select(InventoryAuditLog)
    if battery_id:
        statement = statement.where(InventoryAuditLog.battery_id == battery_id)
    if action:
        statement = statement.where(InventoryAuditLog.action_type == action)
    
    statement = statement.order_by(InventoryAuditLog.timestamp.desc())
    return session.exec(statement.offset(skip).limit(limit)).all()

@router.post("/audit-trail/export")
def export_inventory_audit(
    *,
    session: Session = Depends(deps.get_db),
    battery_id: Optional[int] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Export audit trail as CSV"""
    statement = select(InventoryAuditLog)
    if battery_id:
        statement = statement.where(InventoryAuditLog.battery_id == battery_id)
        
    logs = session.exec(statement.order_by(InventoryAuditLog.timestamp.desc()).limit(10000)).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Battery ID", "Action", "From Type", "From ID", "To Type", "To ID", "Actor ID", "Timestamp", "Notes"])
    
    for log in logs:
        writer.writerow([
            log.id, log.battery_id, log.action_type,
            log.from_location_type, log.from_location_id,
            log.to_location_type, log.to_location_id,
            log.actor_id, log.timestamp.isoformat(), log.notes
        ])
        
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_audit_trail.csv"}
    )
