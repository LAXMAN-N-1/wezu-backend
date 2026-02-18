from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlmodel import Session, select
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.db.session import get_session
from app.models.battery import Battery, BatteryLifecycleEvent
from app.models.user import User
from app.api import deps
from app.schemas.battery import (
    BatteryCreate, BatteryBulkCreate, BatteryResponse, 
    BatteryDetailResponse, BatteryUpdate
)
from app.services.qr_service import QRCodeService
from app.services.mqtt_service import mqtt_service
from app.services.websocket_service import manager
from app.schemas.common import DataResponse

router = APIRouter()

class QRCodeRequest(BaseModel):
    qr_code_data: str

class QRGenerateRequest(BaseModel):
    battery_id: int

class QRVerifyRequest(BaseModel):
    qr_data: str

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
    session: Session = Depends(get_session),
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
            selectinload(Battery.spec), 
            selectinload(Battery.batch),
            selectinload(Battery.iot_device),
            selectinload(Battery.lifecycle_events)
        )
    ).first()
    
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    return battery

@router.post("/qr/generate", response_model=DataResponse[dict])
def generate_qr_code(
    request: QRGenerateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
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
    session: Session = Depends(get_session)
):
    """Verify scanned QR code and get battery details"""
    battery_data = QRCodeService.verify_qr_code(request.qr_data, session)
    if not battery_data:
        raise HTTPException(status_code=400, detail="Invalid or expired QR code")
    
    return DataResponse(success=True, data=battery_data)

@router.get("/", response_model=List[BatteryResponse])
def read_batteries(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
) -> Any:
    """Retrieve batteries."""
    batteries = session.exec(
        select(Battery)
        .options(
             selectinload(Battery.spec), 
             selectinload(Battery.batch),
             selectinload(Battery.iot_device)
        )
        .offset(skip).limit(limit)
    ).all()
    return batteries

@router.get("/{battery_id}/telemetry", response_model=DataResponse[BatteryTelemetryResponse])
def get_battery_telemetry(
    battery_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
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
            timestamp=telemetry.get('timestamp', datetime.utcnow().isoformat()),
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
                timestamp=datetime.utcnow().isoformat()
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
    session: Session = Depends(get_session),
    battery_id: int,
) -> Any:
    """Get battery by ID with history."""
    battery = session.exec(
        select(Battery)
        .where(Battery.id == battery_id)
        .options(
            selectinload(Battery.spec), 
            selectinload(Battery.batch),
            selectinload(Battery.iot_device),
            selectinload(Battery.lifecycle_events)
        )
    ).first()
    
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    return battery
