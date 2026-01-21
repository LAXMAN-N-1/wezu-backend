"""
Real-time Battery Monitoring API
WebSocket and REST endpoints for battery telemetry
"""
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.services.mqtt_service import mqtt_service
from app.services.websocket_service import manager
from app.schemas.common import DataResponse

router = APIRouter()

# Schemas
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

# REST Endpoints
@router.get("/{battery_id}/telemetry", response_model=DataResponse[BatteryTelemetryResponse])
def get_battery_telemetry(
    battery_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get real-time battery telemetry data
    Returns cached data from Redis if available
    """
    # Get real-time data from MQTT service
    telemetry = mqtt_service.get_realtime_data(battery_id)
    
    if not telemetry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No telemetry data available"
        )
    
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

# WebSocket Endpoint
@router.websocket("/{battery_id}/stream")
async def battery_telemetry_stream(
    websocket: WebSocket,
    battery_id: int,
    token: str  # JWT token as query parameter
):
    """
    WebSocket endpoint for real-time battery telemetry streaming
    
    Usage:
    ws://localhost:8000/api/v1/batteries/{battery_id}/stream?token=<jwt_token>
    """
    # Verify token and get user
    # In production, properly verify JWT token
    try:
        # For now, accept connection
        # TODO: Implement proper JWT verification for WebSocket
        user_id = 1  # Placeholder
        
        await manager.connect(websocket, user_id)
        await manager.subscribe_battery(user_id, battery_id)
        
        # Send initial telemetry data
        telemetry = mqtt_service.get_realtime_data(battery_id)
        if telemetry:
            await websocket.send_json({
                "type": "telemetry",
                "battery_id": battery_id,
                "data": telemetry
            })
        
        # Keep connection alive and handle messages
        while True:
            try:
                # Receive messages from client
                data = await websocket.receive_json()
                
                # Handle client commands
                if data.get('command') == 'ping':
                    await websocket.send_json({"type": "pong"})
                
            except WebSocketDisconnect:
                manager.disconnect(websocket, user_id)
                break
            except Exception as e:
                print(f"WebSocket error: {str(e)}")
                break
                
    except Exception as e:
        print(f"WebSocket connection error: {str(e)}")
        await websocket.close()
