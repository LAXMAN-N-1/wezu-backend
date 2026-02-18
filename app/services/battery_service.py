from sqlmodel import Session, select
from app.models.battery import Battery, BatteryLifecycleEvent
from app.schemas.battery import BatteryCreate
from app.services.qr_service import QRCodeService
from typing import List, Optional
from datetime import datetime

class BatteryService:
    @staticmethod
    def get_by_id(db: Session, battery_id: int) -> Optional[Battery]:
        return db.get(Battery, battery_id)

    @staticmethod
    def get_by_serial(db: Session, serial: str) -> Optional[Battery]:
        return db.exec(select(Battery).where(Battery.serial_number == serial)).first()

    @staticmethod
    def create_battery(db: Session, battery_in: BatteryCreate) -> Battery:
        battery = Battery(**battery_in.dict())
        db.add(battery)
        db.commit()
        db.refresh(battery)
        
        # Generate QR Code Data
        battery.qr_code_data = f"wezu://battery/{battery.id}"
        db.add(battery)
        
        # Log initial lifecycle event
        BatteryService.log_lifecycle_event(
            db, battery.id, "created", "Battery initialized in system"
        )
        
        db.commit()
        db.refresh(battery)
        return battery

    @staticmethod
    def log_lifecycle_event(
        db: Session, 
        battery_id: int, 
        event_type: str, 
        description: str,
        metadata: Optional[dict] = None
    ):
        event = BatteryLifecycleEvent(
            battery_id=battery_id,
            event_type=event_type,
            description=description,
            timestamp=datetime.utcnow()
        )
        db.add(event)
        db.commit()

    @staticmethod
    def update_metrics(
        db: Session, 
        battery_id: int, 
        soc: float, 
        soh: float, 
        charge_cycles: Optional[int] = None
    ):
        battery = db.get(Battery, battery_id)
        if battery:
            battery.current_soc = soc
            battery.current_soh = soh
            if charge_cycles is not None:
                battery.charge_cycles = charge_cycles
            battery.updated_at = datetime.utcnow()
            db.add(battery)
            db.commit()
            db.refresh(battery)
        return battery
