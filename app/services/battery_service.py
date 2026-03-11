from app.models.battery import Battery, BatteryLifecycleEvent, BatteryStatus, BatteryAuditLog, BatteryHealthHistory
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

    def create_battery(db: Session, battery_in: BatteryCreate, current_user_id: Optional[int] = None) -> Battery:
        data = battery_in.model_dump()
        # Map spec_id to sku_id if present
        if 'spec_id' in data and data['spec_id'] is not None:
            data['sku_id'] = data.pop('spec_id')
        
        # Remove deprecated model field if it conflicts or use it
        if 'model' in data: data.pop('model')
            
        battery = Battery(**data)
        db.add(battery)
        db.commit()
        db.refresh(battery)
        
        # 1. Generate QR Code Data
        battery.qr_code_data = f"wezu://battery/{battery.id}"
        db.add(battery)
        
        # 2. Record Health History initial entry
        health_history = BatteryHealthHistory(
            battery_id=battery.id,
            health_percentage=battery.health_percentage,
            recorded_at=datetime.utcnow()
        )
        db.add(health_history)

        # 3. Log initial lifecycle event
        BatteryService.log_lifecycle_event(
            db, battery.id, "created", "Battery initialized in system"
        )
        
        # 4. Record Audit Log for Creation
        audit = BatteryAuditLog(
            battery_id=battery.id,
            changed_by=current_user_id,
            field_changed="id",
            old_value=None,
            new_value=str(battery.id),
            reason="Initial registration",
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        
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
    def record_audit(
        db: Session,
        battery_id: int,
        field: str,
        old_val: Any,
        new_val: Any,
        reason: Optional[str] = None,
        user_id: Optional[int] = None
    ):
        audit = BatteryAuditLog(
            battery_id=battery_id,
            changed_by=user_id,
            field_changed=field,
            old_value=str(old_val) if old_val is not None else None,
            new_value=str(new_val) if new_val is not None else None,
            reason=reason,
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        db.commit()

    def update_status(db: Session, battery_id: int, status: BatteryStatus, description: str, current_user_id: Optional[int] = None) -> Optional[Battery]:
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

        # Record Audit Log
        audit = BatteryAuditLog(
            battery_id=battery_id,
            changed_by=current_user_id,
            field_changed="status",
            old_value=str(old_status),
            new_value=str(status),
            reason=description,
            timestamp=datetime.utcnow()
        )
        db.add(audit)

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

    def get_health_history(db: Session, battery_id: int, limit: int = 50) -> List[BatteryHealthHistory]:
        return db.exec(
            select(BatteryHealthHistory)
            .where(BatteryHealthHistory.battery_id == battery_id)
            .order_by(BatteryHealthHistory.recorded_at.desc())
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
