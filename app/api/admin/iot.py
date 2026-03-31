from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, desc
from typing import List, Optional
from datetime import datetime, UTC, timedelta
from app.api import deps
from app.models.user import User
from app.models.battery import Battery
from app.models.station import Station
from app.models.telemetry import Telemetry
from app.models.iot import IoTDevice, DeviceCommand
from app.models.geofence import Geofence
from app.models.alert import Alert
from app.core.database import get_db

router = APIRouter()

@router.get("/stats")
def get_iot_stats(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Get aggregated IoT device statistics."""
    total = db.exec(select(func.count(IoTDevice.id))).one()
    online = db.exec(select(func.count(IoTDevice.id)).where(IoTDevice.status == "online")).one()
    errors = db.exec(select(func.count(Alert.id)).where(Alert.acknowledged_at == None)).one()
    
    return {
        "total_devices": total,
        "online_devices": online,
        "offline_devices": total - online,
        "active_alerts": errors,
        "health_score": 98.5 # Mock metric for dashboard
    }

@router.get("/devices", response_model=List[IoTDevice])
def list_iot_devices(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """List all IoT devices with optional status filtering."""
    query = select(IoTDevice)
    if status:
        query = query.where(IoTDevice.status == status)
    return db.exec(query.offset(skip).limit(limit)).all()

@router.post("/commands")
def send_device_command(
    device_id: int,
    command_type: str,
    payload: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Send a remote command to an IoT device."""
    device = db.get(IoTDevice, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    new_command = DeviceCommand(
        device_id=device_id,
        command_type=command_type,
        payload=payload,
        status="queued"
    )
    db.add(new_command)
    db.commit()
    db.refresh(new_command)
    return new_command

@router.get("/commands/history", response_model=List[DeviceCommand])
def get_command_history(
    device_id: Optional[int] = None,
    limit: int = 50,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Get history of commands sent to devices."""
    query = select(DeviceCommand).order_by(desc(DeviceCommand.created_at))
    if device_id:
        query = query.where(DeviceCommand.device_id == device_id)
    return db.exec(query.limit(limit)).all()

@router.get("/geofences", response_model=List[Geofence])
def list_geofences(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """List all configured geofences."""
    return db.exec(select(Geofence)).all()

@router.post("/geofences", response_model=Geofence)
def create_geofence(
    geofence: Geofence,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Create a new geofence zone."""
    db.add(geofence)
    db.commit()
    db.refresh(geofence)
    return geofence

@router.get("/alerts", response_model=List[Alert])
def list_alerts(
    severity: Optional[str] = None,
    active_only: bool = True,
    limit: int = 50,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """List system alerts with filtering."""
    query = select(Alert).order_by(desc(Alert.created_at))
    if severity:
        query = query.where(Alert.severity == severity)
    if active_only:
        query = query.where(Alert.acknowledged_at == None)
    return db.exec(query.limit(limit)).all()

@router.put("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Acknowledge and resolve an alert."""
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.acknowledged_at = datetime.now(UTC)
    alert.acknowledged_by = current_user.id
    db.add(alert)
    db.commit()
    return {"status": "success"}

@router.get("/batteries/health")
def get_battery_health_overview(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Get health status distribution of all batteries."""
    batteries = db.exec(select(Battery)).all()
    health_summary = {
        "total": len(batteries),
        "healthy": len([b for b in batteries if b.health_percentage >= 80]),
        "warning": len([b for b in batteries if 50 <= b.health_percentage < 80]),
        "critical": len([b for b in batteries if b.health_percentage < 50]),
    }
    return health_summary

@router.get("/telematics/{battery_id}")
def get_battery_telematics(
    battery_id: int,
    hours: int = 24,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Get historical telematics for a specific battery."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    statement = select(Telemetry).where(
        Telemetry.battery_id == battery_id,
        Telemetry.timestamp >= since
    ).order_by(Telemetry.timestamp.desc())
    
    logs = db.exec(statement).all()
    return logs
