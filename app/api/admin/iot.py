from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, desc
from typing import List, Optional
from sqlmodel import Session, select, func, col
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict
from app.api import deps
from app.models.user import User
from app.models.battery import Battery
from app.models.station import Station
from app.models.telemetry import Telemetry
from app.models.iot import IoTDevice, DeviceCommand
from app.models.geofence import Geofence
from app.models.alert import Alert
from app.models.station_heartbeat import StationHeartbeat
from app.core.database import get_db
import json

router = APIRouter()

@router.get("/stats")
def get_iot_stats(
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """Get history of commands sent to devices."""
    query = select(DeviceCommand).order_by(desc(DeviceCommand.created_at))
    if device_id:
        query = query.where(DeviceCommand.device_id == device_id)
    return db.exec(query.limit(limit)).all()

@router.get("/geofences", response_model=List[Geofence])
def list_geofences(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """List all configured geofences."""
    return db.exec(select(Geofence)).all()

@router.post("/geofences", response_model=Geofence)
def create_geofence(
    geofence: Geofence,
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """Acknowledge and resolve an alert."""
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = current_user.id
    db.add(alert)
    db.commit()
    return {"status": "success"}

# ── Response Schemas ────────────────────────────────────────────────

class IoTStationStatus(BaseModel):
    """Enriched IoT status view for a single station."""
    station_id: int
    name: str
    status: str                           # active / maintenance / closed
    iot_status: str                       # online / error / offline
    last_heartbeat: Optional[datetime] = None
    uptime_24h_pct: float = 0.0
    temperature: Optional[float] = None
    power_output_w: Optional[float] = None
    network_latency_ms: Optional[float] = None
    total_slots: int = 0
    available_batteries: int = 0

    model_config = ConfigDict(from_attributes=True)


class IoTStationStatusList(BaseModel):
    stations: List[IoTStationStatus]
    total: int


class HeartbeatEntry(BaseModel):
    id: int
    timestamp: datetime
    status: str                           # online / maintenance / error
    temperature: Optional[float] = None
    power_output_w: Optional[float] = None
    network_latency_ms: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class IoTStationHistory(BaseModel):
    station_id: int
    station_name: str
    period_hours: int
    entries: List[HeartbeatEntry]
    summary: Dict[str, int]               # {"online": n, "error": n, "offline": n}
    total_entries: int


# ── Existing Endpoints ──────────────────────────────────────────────

@router.get("/batteries/health")
def get_battery_health_overview(
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """Get historical telematics for a specific battery."""
    since = datetime.utcnow() - timedelta(hours=hours)
    statement = select(Telemetry).where(
        Telemetry.battery_id == battery_id,
        Telemetry.timestamp >= since
    ).order_by(Telemetry.timestamp.desc())

    logs = db.exec(statement).all()
    return logs


# ── NEW: IoT Station Status (Enriched Schema) ──────────────────────

def _parse_metrics(raw: Optional[str]) -> dict:
    """Safely parse the JSON metrics blob from StationHeartbeat."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


@router.get("/stations/status", response_model=IoTStationStatusList)
def get_stations_status(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """
    Get real-time IoT status of all charging stations.
    Enriched with latest heartbeat data, uptime percentage, and sensor readings.
    """
    stations = db.exec(select(Station)).all()

    threshold_24h = datetime.utcnow() - timedelta(hours=24)
    max_heartbeats = 24 * 60  # 1 per minute expected

    results: List[IoTStationStatus] = []

    for s in stations:
        # Latest heartbeat
        latest_hb = db.exec(
            select(StationHeartbeat)
            .where(StationHeartbeat.station_id == s.id)
            .order_by(StationHeartbeat.timestamp.desc())
            .limit(1)
        ).first()

        # 24h heartbeat count → uptime
        hb_count = db.exec(
            select(func.count(StationHeartbeat.id))
            .where(StationHeartbeat.station_id == s.id, StationHeartbeat.timestamp >= threshold_24h)
        ).one()
        uptime = min((hb_count / max_heartbeats) * 100, 100.0) if hb_count else 0.0

        metrics = _parse_metrics(latest_hb.metrics if latest_hb else None)

        # Determine IoT status
        if latest_hb and latest_hb.status == "error":
            iot_status = "error"
        elif latest_hb and latest_hb.timestamp >= threshold_24h:
            iot_status = "online"
        else:
            iot_status = "offline"

        from app.models.battery import Battery
        
        # Count available batteries for this station
        available_batteries = db.exec(
            select(func.count(Battery.id))
            .where(Battery.station_id == s.id, Battery.status == "available")
        ).first() or 0

        results.append(IoTStationStatus(
            station_id=s.id,
            name=s.name,
            status=s.status or "unknown",
            iot_status=iot_status,
            last_heartbeat=latest_hb.timestamp if latest_hb else None,
            uptime_24h_pct=round(uptime, 2),
            temperature=metrics.get("temperature"),
            power_output_w=metrics.get("power_w"),
            network_latency_ms=metrics.get("network_latency") or metrics.get("latency_ms"),
            total_slots=s.total_slots or 0,
            available_batteries=available_batteries,
        ))

    return IoTStationStatusList(stations=results, total=len(results))


# ── NEW: IoT Station History ───────────────────────────────────────

@router.get("/stations/{station_id}/history", response_model=IoTStationHistory)
def get_station_iot_history(
    station_id: int,
    hours: int = Query(24, ge=1, le=168, description="Lookback window in hours (max 7 days)"),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """
    Historical IoT timeline for a station: online / error / offline entries.
    Returns heartbeat entries and a status summary.
    """
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    since = datetime.utcnow() - timedelta(hours=hours)

    heartbeats = db.exec(
        select(StationHeartbeat)
        .where(StationHeartbeat.station_id == station_id, StationHeartbeat.timestamp >= since)
        .order_by(StationHeartbeat.timestamp.desc())
    ).all()

    # Build entries with parsed metrics
    entries: List[HeartbeatEntry] = []
    summary: Dict[str, int] = {"online": 0, "maintenance": 0, "error": 0}

    for hb in heartbeats:
        metrics = _parse_metrics(hb.metrics)
        summary[hb.status] = summary.get(hb.status, 0) + 1

        entries.append(HeartbeatEntry(
            id=hb.id,
            timestamp=hb.timestamp,
            status=hb.status,
            temperature=metrics.get("temperature"),
            power_output_w=metrics.get("power_w"),
            network_latency_ms=metrics.get("network_latency") or metrics.get("latency_ms"),
        ))

    return IoTStationHistory(
        station_id=station.id,
        station_name=station.name,
        period_hours=hours,
        entries=entries,
        summary=summary,
        total_entries=len(entries),
    )
