from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.api import deps
from app.models.user import User
from app.schemas.battery import BatteryResponse, BatteryCreate
from app.services.battery_service import BatteryService

router = APIRouter()

@router.get("/{serial_number}", response_model=BatteryResponse)
async def read_battery(
    serial_number: str,
    db: Session = Depends(deps.get_db),
):
    battery = BatteryService.get_by_serial(db, serial_number)
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    return battery

@router.post("/", response_model=BatteryResponse)
async def create_battery(
    battery_in: BatteryCreate,
    current_user: User = Depends(deps.check_permission("batteries", "create")),
    db: Session = Depends(deps.get_db),
):
    # Check if exists
    if BatteryService.get_by_serial(db, battery_in.serial_number):
         raise HTTPException(status_code=400, detail="Battery already exists")
    return BatteryService.create_battery(db, battery_in)
