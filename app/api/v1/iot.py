from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.battery import Battery
from app.services.mqtt_service import mqtt_service
from app.api.deps import get_current_active_user
from app.models.user import User

router = APIRouter()

@router.post("/{battery_id}/lock")
def lock_battery(
    battery_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Send LOCK command to battery via IoT
    """
    battery = db.get(Battery, battery_id)
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    
    if not battery.iot_device_id:
        raise HTTPException(status_code=400, detail="Battery has no IoT device assigned")
    
    mqtt_service.send_command(battery.iot_device_id, "LOCK")
    return {"status": "success", "message": f"Lock command sent to battery {battery_id}"}

@router.post("/{battery_id}/unlock")
def unlock_battery(
    battery_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Send UNLOCK command to battery via IoT
    """
    battery = db.get(Battery, battery_id)
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    
    if not battery.iot_device_id:
        raise HTTPException(status_code=400, detail="Battery has no IoT device assigned")
    
    mqtt_service.send_command(battery.iot_device_id, "UNLOCK")
    return {"status": "success", "message": f"Unlock command sent to battery {battery_id}"}

@router.post("/{battery_id}/shutdown")
def shutdown_battery(
    battery_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user) # Maybe restrict to Admins later
):
    """
    Send SHUTDOWN command to battery via IoT (Emergency)
    """
    battery = db.get(Battery, battery_id)
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    
    if not battery.iot_device_id:
        raise HTTPException(status_code=400, detail="Battery has no IoT device assigned")
    
    mqtt_service.send_command(battery.iot_device_id, "SHUTDOWN")
    return {"status": "success", "message": f"Shutdown command sent to battery {battery_id}"}
