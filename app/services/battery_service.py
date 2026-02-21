from app.models.battery import Battery, BatteryLifecycleEvent, BatteryStatus
from app.models.telemetry import Telemetry
from app.models.rental import Rental
from app.schemas.battery import BatteryCreate, BatteryUpdate
from app.services.qr_service import QRCodeService
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlmodel import Session, select, func

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

        return battery

    @staticmethod
    def update_status(db: Session, battery_id: int, status: BatteryStatus, description: str) -> Optional[Battery]:
        battery = db.get(Battery, battery_id)
        if not battery:
            return None
        
        old_status = battery.status
        battery.status = status
        battery.updated_at = datetime.utcnow()
        db.add(battery)
        
        BatteryService.log_lifecycle_event(
            db, battery_id, "status_change", 
            f"Status changed from {old_status} to {status}. Reason: {description}"
        )
        db.commit()
        return battery

    @staticmethod
    def assign_station(db: Session, battery_id: int, station_id: int) -> Optional[Battery]:
        battery = db.get(Battery, battery_id)
        if not battery:
            return None
            
        battery.station_id = station_id
        battery.updated_at = datetime.utcnow()
        db.add(battery)
        
        BatteryService.log_lifecycle_event(
            db, battery_id, "station_assigned", f"Assigned to station ID: {station_id}"
        )
        db.commit()
        return battery

    @staticmethod
    def get_health_history(db: Session, battery_id: int, limit: int = 50) -> List[Telemetry]:
        return db.exec(
            select(Telemetry)
            .where(Telemetry.battery_id == battery_id)
            .order_by(Telemetry.timestamp.desc())
            .limit(limit)
        ).all()

    @staticmethod
    def get_rental_history(db: Session, battery_id: int, limit: int = 20) -> List[Rental]:
        return db.exec(
            select(Rental)
            .where(Rental.battery_id == battery_id)
            .order_by(Rental.start_time.desc())
            .limit(limit)
        ).all()

    @staticmethod
    def get_utilization_report(db: Session) -> Dict[str, Any]:
        total = db.exec(select(func.count(Battery.id))).one() or 0
        rented = db.exec(select(func.count(Battery.id)).where(Battery.status == BatteryStatus.RENTED)).one() or 0
        available = db.exec(select(func.count(Battery.id)).where(Battery.status == BatteryStatus.AVAILABLE)).one() or 0
        maintenance = db.exec(select(func.count(Battery.id)).where(Battery.status == BatteryStatus.MAINTENANCE)).one() or 0
        retired = db.exec(select(func.count(Battery.id)).where(Battery.status == BatteryStatus.RETIRED)).one() or 0
        
        utilization = (rented / total * 100) if total > 0 else 0.0
        
        return {
            "total_batteries": total,
            "available_count": available,
            "rented_count": rented,
            "maintenance_count": maintenance,
            "retired_count": retired,
            "utilization_percentage": round(utilization, 2)
        }
