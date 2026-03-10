from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from datetime import datetime
from app.models.telemetry import Telemetry
from app.models.battery import Battery, BatteryLifecycleEvent
from app.schemas.telematics import TelematicsDataIngest, TelematicsDataResponse
from app.api import deps

router = APIRouter()

def process_alerts(session: Session, data: TelematicsDataIngest, battery_id: int):
    """
    Background logic to check for critical conditions
    """
    # 1. Temperature Check
    if data.temperature > 45.0:
        event = BatteryLifecycleEvent(
            battery_id=battery_id,
            event_type="alert_overheating",
            description=f"Critical temperature detected: {data.temperature}C"
        )
        session.add(event)
        
    # 2. Low SoC Check
    if data.soc < 10.0:
         event = BatteryLifecycleEvent(
            battery_id=battery_id,
            event_type="alert_low_battery",
            description=f"Critically low charge: {data.soc}%"
        )
         session.add(event)
    
    session.commit()

@router.post("/ingest", response_model=TelemeticsDataResponse)
def ingest_telemetry(
    *,
    session: Session = Depends(deps.get_db),
    data_in: TelematicsDataIngest,
    background_tasks: BackgroundTasks
) -> Any:
    """
    Ingest data point from IoT device.
    Updates the Battery's 'live' status and appends to time-series history.
    """
    # 1. Verify Battery Exists
    battery = session.get(Battery, data_in.battery_id)
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
        
    # 2. Save Time-Series Data
    if not data_in.timestamp:
        data_in.timestamp = datetime.utcnow()
        
    telemetry_entry = Telemetry.model_validate(data_in)
    session.add(telemetry_entry)
    
    # 3. Update Battery "Current State" (Snapshot)
    battery.current_charge = data_in.soc
    battery.temp = data_in.temperature # Assuming 'temp' field or 'temperature'
    battery.voltage = data_in.voltage
    battery.health_percentage = data_in.soh
    
    # Update GPS if provided
    if data_in.gps_latitude and data_in.gps_longitude:
        battery.last_latitude = data_in.gps_latitude
        battery.last_longitude = data_in.gps_longitude

    session.add(battery)
    session.commit()
    session.refresh(telemetry_entry)
    
    # 4. Trigger Background Analysis (Alerts)
    background_tasks.add_task(process_alerts, session, data_in, battery.id)
    
    return telemetry_entry

@router.get("/battery/{battery_id}/latest", response_model=TelematicsDataResponse)
def get_latest_telemetry(
    *,
    session: Session = Depends(deps.get_db),
    battery_id: int
) -> Any:
    """
    Get the most recent telemetry packet for a battery.
    """
    statement = select(Telemetry).where(Telemetry.battery_id == battery_id).order_by(Telemetry.timestamp.desc()).limit(1)
    result = session.exec(statement).first()
    if not result:
        raise HTTPException(status_code=404, detail="No data found")
    return result