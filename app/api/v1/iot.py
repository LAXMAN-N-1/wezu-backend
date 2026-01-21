from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
from app.db.session import get_session
from app.models.iot import IoTDevice, DeviceCommand
from app.services.iot_service import IoTService
from app.schemas.common import DataResponse
from pydantic import BaseModel

router = APIRouter()

class DeviceCreate(BaseModel):
    device_id: str
    device_type: str
    battery_id: Optional[int] = None

class CommandRequest(BaseModel):
    command: str
    payload: dict = {}

@router.post("/devices", response_model=DataResponse[IoTDevice])
def register_device(device_in: DeviceCreate, session: Session = Depends(get_session)):
    """Register a new IoT device."""
    existing = session.exec(select(IoTDevice).where(IoTDevice.device_id == device_in.device_id)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device ID already registered")
    
    device = IoTService.register_device(device_in.device_id, device_in.device_type, device_in.battery_id)
    return DataResponse(data=device, message="Device registered successfully")

@router.get("/devices", response_model=DataResponse[List[IoTDevice]])
def list_devices(
    skip: int = 0, 
    limit: int = 100, 
    session: Session = Depends(get_session)
):
    devices = session.exec(select(IoTDevice).offset(skip).limit(limit)).all()
    return DataResponse(data=devices)

@router.post("/devices/{device_id}/command", response_model=DataResponse[DeviceCommand])
def send_command(
    device_id: str, 
    cmd_in: CommandRequest, 
    session: Session = Depends(get_session)
):
    """Send a command to the device."""
    try:
        cmd = IoTService.send_command(device_id, cmd_in.command, cmd_in.payload)
        return DataResponse(data=cmd, message="Command sent")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/devices/{device_id}/pair", response_model=DataResponse[IoTDevice])
def pair_device(
    device_id: str, 
    battery_id: int, 
    session: Session = Depends(get_session)
):
    """Pair a device with a battery."""
    device = session.exec(select(IoTDevice).where(IoTDevice.device_id == device_id)).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device.battery_id = battery_id
    session.add(device)
    session.commit()
    session.refresh(device)
    return DataResponse(data=device, message="Device paired with battery")
