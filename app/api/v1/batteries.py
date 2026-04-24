from __future__ import annotations
from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, UploadFile, File
from sqlmodel import Session, select
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone; UTC = timezone.utc
import csv
import io

from app.db.session import get_session
from app.models.battery import Battery, BatteryLifecycleEvent, BatteryAuditLog, BatteryHealthHistory
from app.models.user import User
from app.api import deps
from app.schemas.battery import (
    BatteryCreate, BatteryBulkCreate, BatteryResponse, 
    BatteryDetailResponse, BatteryUpdate, BatteryHealthReading,
    BatteryUtilizationResponse, BatteryMaintenanceCreate,
    BatteryAuditLogResponse, BatteryHealthHistoryResponse
)
from app.api import deps
from app.schemas.common import DataResponse
from app.schemas.station_monitoring import BatteryListResponse, BatteryHealthReport
from app.services.battery_service import BatteryService
from app.services.maintenance_service import MaintenanceService
from app.services.qr_service import QRCodeService
from app.services.battery_batch_service import battery_batch_service
from app.services.mqtt_service import mqtt_service
from app.services.websocket_service import manager
from app.core.audit import audit_log
from app.models.station import Station

router = APIRouter()

class QRGenerateRequest(BaseModel):
    battery_id: int

class QRVerifyRequest(BaseModel):
    qr_data: str

class QRCodeRequest(BaseModel):
    qr_code_data: str

class BatteryTelemetryResponse(BaseModel):
    battery_id: int
    voltage: Optional[float]
    current: Optional[float]
    temperature: Optional[float]
    soc: Optional[float]
    health: Optional[float]
    timestamp: str
    is_realtime: bool

class BatteryAlertResponse(BaseModel):
    type: str
    severity: str
    message: str
    timestamp: str

@router.post("/scan-qr", response_model=BatteryDetailResponse)
def scan_battery_qr(
    *,
    session: Session = Depends(deps.get_db),
    qr_in: QRCodeRequest,
) -> Any:
    """
    Scan QR code to get battery details.
    """
    # Eager load relationships
    battery = session.exec(
        select(Battery)
        .where(Battery.qr_code_data == qr_in.qr_code_data)
        .options(
            selectinload(Battery.sku), 
            selectinload(Battery.iot_device),
            selectinload(Battery.lifecycle_events)
        )
    ).first()
    
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    return battery

@router.get("/{battery_id}/health-history", response_model=DataResponse[List[BatteryHealthHistoryResponse]])
def get_battery_health_history(
    battery_id: int,
    session: Session = Depends(deps.get_db),
    limit: int = Query(50, le=200)
):
    """Historical health percentage (SOH) readings over time."""
    history = BatteryService.get_health_history(session, battery_id, limit)
    return DataResponse(success=True, data=history)

@router.get("/{battery_id}/audit-logs", response_model=DataResponse[List[BatteryAuditLogResponse]])
def get_battery_audit_logs(
    battery_id: int,
    session: Session = Depends(deps.get_db),
    limit: int = Query(50, le=200)
):
    """Audit trail of all changes to this battery."""
    logs = session.exec(
        select(BatteryAuditLog)
        .where(BatteryAuditLog.battery_id == battery_id)
        .order_by(BatteryAuditLog.timestamp.desc())
        .limit(limit)
    ).all()
    
    # We could join with User to get names, or just return as is
    return DataResponse(success=True, data=logs)

@router.get("/{battery_id}/rental-history")
def get_battery_rental_history(
    battery_id: int,
    session: Session = Depends(deps.get_db),
    limit: int = Query(20, le=100)
):
    """All past rentals associated with this battery."""
    return BatteryService.get_rental_history(session, battery_id, limit)

@router.post("/{battery_id}/maintenance")
def log_battery_maintenance(
    battery_id: int,
    maintenance_in: BatteryMaintenanceCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Log a maintenance event on a battery."""
    data = maintenance_in.model_dump()
    data.update({"entity_type": "battery", "entity_id": battery_id})
    return MaintenanceService.record_maintenance(session, current_user.id, data)

@router.get("/{battery_id}/maintenance-history")
def get_battery_maintenance_history(
    battery_id: int,
    session: Session = Depends(deps.get_db)
):
    """All maintenance records for a battery."""
    return MaintenanceService.get_maintenance_history(session, battery_id)

@router.put("/{battery_id}/status")
def update_battery_status(
    battery_id: int,
    status: str,
    description: str = "Manual status update",
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Manually change battery status (available/maintenance/retired)."""
    battery = BatteryService.update_status(session, battery_id, status, description, current_user.id)
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    return battery

@router.post("/{battery_id}/assign-station")
def assign_battery_station(
    battery_id: int,
    station_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Assign a battery to a specific station."""
    battery = BatteryService.assign_station(session, battery_id, station_id)
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    return battery

@router.post("/{battery_id}/transfer")
def transfer_battery(
    battery_id: int,
    to_station_id: int,
    notes: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Transfer battery from one station to another (logs movement)."""
    # Simply re-use assign_station but with better logging description
    battery = session.get(Battery, battery_id)
    if not battery:
         raise HTTPException(status_code=404, detail="Battery not found")
    
    from_station_id = battery.station_id
    battery.station_id = to_station_id
    battery.updated_at = datetime.now(UTC)
    
    BatteryService.log_lifecycle_event(
        session, battery_id, "transfer", 
        f"Transferred from Station {from_station_id} to {to_station_id}. Notes: {notes}"
    )
    session.add(battery)
    session.commit()
    return battery

@router.get("/low-health", response_model=List[BatteryResponse])
def get_low_health_batteries(
    threshold: float = Query(80.0, description="Health percentage threshold"),
    session: Session = Depends(deps.get_db)
):
    """List all batteries below a configurable health threshold."""
    batteries = session.exec(
        select(Battery).where(Battery.health_percentage < threshold)
    ).all()
    return batteries

@router.get("/utilization-report", response_model=BatteryUtilizationResponse)
def get_battery_utilization_report(
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Utilization percentage across fleet."""
    return BatteryService.get_utilization_report(session)

@router.post("/qr/generate", response_model=DataResponse[dict])
def generate_qr_code(
    request: QRGenerateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Generate QR code for battery verification"""
    qr_image = QRCodeService.generate_battery_qr(request.battery_id, session)
    if not qr_image:
        raise HTTPException(status_code=500, detail="Failed to generate QR code")
    
    return DataResponse(
        success=True,
        data={
            "battery_id": request.battery_id,
            "qr_code": qr_image,
            "expires_in_hours": 24
        }
    )

@router.post("/qr/verify", response_model=DataResponse[dict])
def verify_qr_code(
    request: QRVerifyRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Verify scanned QR code and get battery details"""
    battery_data = QRCodeService.verify_qr_code(request.qr_data, session)
    if not battery_data:
        raise HTTPException(status_code=400, detail="Invalid or expired QR code")
    
    return DataResponse(success=True, data=battery_data)

@router.get("/", response_model=List[BatteryResponse])
def read_batteries(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    include_pagination: bool = False,
    current_user: User = Depends(deps.require_permission("battery:read")),
    session: Session = Depends(get_session),
) -> Any:
    """
    Retrieve batteries with row-level security:
    - Admin/Superuser: all batteries
    - Dealer: only batteries at their stations
    - Driver: only batteries assigned to them
    """
    # NOTE:
    # `include_pagination` is accepted for client compatibility with generic
    # table widgets used by multiple portals. This endpoint intentionally
    # returns a plain list response model.
    _ = include_pagination

    query = select(Battery)
    
    if not current_user.is_superuser:
        # Driver filtering: batteries assigned to this driver
        if current_user.driver_profile:
            query = query.where(
                Battery.location_type == "driver",
                Battery.location_id == current_user.driver_profile.id
            )
        # Dealer filtering: batteries at their stations
        elif current_user.dealer_profile:
            query = query.join(Station, Battery.location_id == Station.id).where(
                Battery.location_type == "station",
                Station.dealer_id == current_user.dealer_profile.id
            )
    
    batteries = session.exec(query.order_by(Battery.id.desc()).offset(skip).limit(limit)).all()
    return batteries

@router.post("/", response_model=BatteryResponse)
@audit_log("CREATE_BATTERY", "BATTERY")
def create_battery(
    *,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
    battery_in: BatteryCreate,
) -> Any:
    """Create a new battery record manually."""
    return BatteryService.create_battery(session, battery_in, current_user.id)

@router.put("/{battery_id}", response_model=BatteryResponse)
def update_battery(
    *,
    session: Session = Depends(deps.get_db),
    battery_id: int,
    battery_in: BatteryUpdate,
    current_user: User = Depends(deps.get_current_active_superuser)
) -> Any:
    """Update battery specs/metadata."""
    battery = session.get(Battery, battery_id)
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
        
    update_data = battery_in.model_dump(exclude_unset=True)
    description = update_data.pop("description", "Manual update")
    
    for key, value in update_data.items():
        old_val = getattr(battery, key)
        if old_val != value:
            setattr(battery, key, value)
            # Record Audit for each change
            BatteryService.record_audit(
                session, battery_id, key, old_val, value, 
                reason=description, user_id=current_user.id
            )
    
    battery.updated_at = datetime.now(UTC)
    session.add(battery)
    session.commit()
    session.refresh(battery)
    return battery

@router.delete("/{battery_id}")
def decommission_battery(
    *,
    session: Session = Depends(deps.get_db),
    battery_id: int,
    current_user: User = Depends(deps.get_current_active_superuser)
) -> Any:
    """Retire/decommission a battery from circulation."""
    battery = BatteryService.update_status(session, battery_id, "retired", "Manual decommission")
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    return {"status": "success", "message": "Battery retired"}

@router.post("/batch/import", response_model=DataResponse[dict])
def import_batteries_csv(
    file: UploadFile = File(...),
    dry_run: bool = Query(False, description="If true, validation only; no commit"),
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Import batteries via CSV"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    content = file.file.read().decode("utf-8")
    parsed_data = battery_batch_service.parse_import_csv(content)
    result = battery_batch_service.process_import(session, parsed_data, dry_run=dry_run)
    
    return DataResponse(success=True, data=result, message=f"Processed {len(parsed_data)} items")

@router.get("/batch/export")
def export_batteries_csv(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Export battery inventory to CSV"""
    csv_str = battery_batch_service.generate_export_csv(session)
    
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=batteries_export_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"}
    )

@router.put("/batch/update", response_model=DataResponse[dict])
def update_batteries_batch(
    updates: List[Dict[str, Any]],
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """
    Batch update batteries. 
    Payload: [{"serial_number": "SN123", "status": "rented", ...}]
    """
    if not updates or len(updates) > 1000:
        raise HTTPException(status_code=400, detail="Invalid payload. Max 1000 updates allowed per request.")
    
    result = battery_batch_service.process_bulk_update(session, updates)
    return DataResponse(success=True, data=result, message="Batch update complete")

@router.get("/{battery_id}/telemetry", response_model=DataResponse[BatteryTelemetryResponse])
def get_battery_telemetry(
    battery_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Get real-time battery telemetry data"""
    telemetry = mqtt_service.get_realtime_data(battery_id)
    if not telemetry:
        raise HTTPException(status_code=404, detail="No telemetry data available")
    
    return DataResponse(
        success=True,
        data=BatteryTelemetryResponse(
            battery_id=battery_id,
            voltage=telemetry.get('voltage'),
            current=telemetry.get('current'),
            temperature=telemetry.get('temperature'),
            soc=telemetry.get('soc'),
            health=telemetry.get('health'),
            timestamp=telemetry.get('timestamp', datetime.now(UTC).isoformat()),
            is_realtime=True
        )
    )

@router.get("/{battery_id}/alerts", response_model=DataResponse[list])
def get_battery_alerts(
    battery_id: int,
    current_user: User = Depends(deps.get_current_user)
):
    """Get active alerts for battery"""
    alerts = mqtt_service.get_alerts(battery_id)
    return DataResponse(
        success=True,
        data=[
            BatteryAlertResponse(
                type=alert['type'],
                severity=alert['severity'],
                message=alert['message'],
                timestamp=datetime.now(UTC).isoformat()
            )
            for alert in alerts
        ]
    )

@router.websocket("/{battery_id}/stream")
async def battery_telemetry_stream(
    websocket: WebSocket,
    battery_id: int,
    token: str
):
    """WebSocket endpoint for real-time battery telemetry streaming"""
    try:
        user_id = 1 # Placeholder for token verification logic
        await manager.connect(websocket, user_id)
        await manager.subscribe_battery(user_id, battery_id)
        
        while True:
            try:
                data = await websocket.receive_json()
                if data.get('command') == 'ping':
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                manager.disconnect(websocket, user_id)
                break
    except Exception as e:
        await websocket.close()

@router.get("/{battery_id}", response_model=BatteryDetailResponse)
def read_battery(
    *,
    session: Session = Depends(deps.get_db),
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
@audit_log("STATUS_CHANGE", "BATTERY", resource_id_param="battery_id")
def update_battery_lifecycle(
    *,
    request: Request,
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
    
    # Apply updates
    if update_in.status:
        battery.status = update_in.status
        event = BatteryLifecycleEvent(
            battery_id=battery.id,
            event_type="status_change",
            description=f"Status changed to {update_in.status}. {update_in.description or ''}"
        )
        session.add(event)
    if update_in.health_status:
        battery.health_status = update_in.health_status
    if update_in.health_percentage is not None:
        battery.health_percentage = update_in.health_percentage
    if update_in.location_type:
        battery.location_type = update_in.location_type
    if update_in.station_id is not None:
        battery.station_id = update_in.station_id
    if update_in.notes:
        battery.notes = update_in.notes
    if update_in.description:
        battery.notes = (battery.notes or "") + f" {update_in.description}".strip()

    session.add(battery)
    session.commit()
    session.refresh(battery)
    return battery
