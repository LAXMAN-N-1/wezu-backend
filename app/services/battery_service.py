from sqlmodel import Session, select
from app.models.battery import Battery
from app.schemas.battery import BatteryCreate
from typing import List, Optional

class BatteryService:
    @staticmethod
    def get_by_serial(db: Session, serial: str) -> Optional[Battery]:
        return db.exec(select(Battery).where(Battery.serial_number == serial)).first()

    @staticmethod
    def create_battery(db: Session, battery_in: BatteryCreate) -> Battery:
        battery = Battery(**battery_in.dict())
        db.add(battery)
        db.commit()
        db.refresh(battery)
        return battery
