from sqlmodel import Session, select
from app.core.database import engine
from app.models.maintenance import MaintenanceSchedule, MaintenanceRecord, StationDowntime
from app.models.battery import Battery
from app.models.station import Station
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("wezu_maintenance")

class MaintenanceService:
    @staticmethod
    def auto_generate_schedules(db: Session):
        """
        Check all batteries and stations against maintenance rules and flag them if due.
        """
        # 1. Process Batteries
        battery_schedules = db.exec(select(MaintenanceSchedule).where(MaintenanceSchedule.entity_type == "battery")).all()
        for schedule in battery_schedules:
            # Simple logic: check cycles or time since last maintenance
            # We match by model_name if available, or apply globally
            stmt = select(Battery).where(Battery.status != "maintenance")
            if schedule.model_name:
                # Assuming Battery has a way to match model_name via speculation or catalog
                pass 
                
            batteries = db.exec(stmt).all()
            for battery in batteries:
                is_due = False
                
                # Check Cycles
                if schedule.interval_cycles and (battery.cycle_count - battery.last_maintenance_cycles) >= schedule.interval_cycles:
                    is_due = True
                    reason = f"Cycle count threshold reached ({battery.cycle_count})"
                
                # Check Time
                elif schedule.interval_days:
                    last_date = battery.last_maintenance_date or battery.created_at
                    if (datetime.utcnow() - last_date).days >= schedule.interval_days:
                        is_due = True
                        reason = f"Time threshold reached (Last: {last_date.date()})"
                
                if is_due:
                    battery.status = "maintenance"
                    db.add(battery)
                    logger.info(f"Battery {battery.serial_number} flagged for maintenance: {reason}")

        # 2. Process Stations
        station_schedules = db.exec(select(MaintenanceSchedule).where(MaintenanceSchedule.entity_type == "station")).all()
        for schedule in station_schedules:
            stations = db.exec(select(Station).where(Station.status != "maintenance")).all()
            for station in stations:
                last_date = station.last_maintenance_date or station.created_at
                if schedule.interval_days and (datetime.utcnow() - last_date).days >= schedule.interval_days:
                    station.status = "maintenance"
                    db.add(station)
                    logger.info(f"Station {station.name} flagged for maintenance")
        
        db.commit()

    @staticmethod
    def record_maintenance(db: Session, user_id: int, data: dict) -> MaintenanceRecord:
        record = MaintenanceRecord(
            technician_id=user_id,
            entity_type=data.get("entity_type"),
            entity_id=data.get("entity_id"),
            maintenance_type=data.get("maintenance_type", "preventive"),
            description=data.get("description"),
            cost=data.get("cost", 0.0),
            parts_replaced=data.get("parts_replaced"),
            performed_at=datetime.utcnow()
        )
        db.add(record)
        
        # Update entity status and last maintenance info
        if record.entity_type == "battery":
            battery = db.get(Battery, record.entity_id)
            if battery:
                battery.status = "ready" # Assuming it was fixed
                battery.last_maintenance_date = record.performed_at
                battery.last_maintenance_cycles = battery.cycle_count
                db.add(battery)
        
        elif record.entity_type == "station":
            station = db.get(Station, record.entity_id)
            if station:
                station.status = "active"
                station.last_maintenance_date = record.performed_at
                db.add(station)
        
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def report_downtime(db: Session, station_id: int, reason: str):
        dt = StationDowntime(
            station_id=station_id,
            start_time=datetime.utcnow(),
            reason=reason
        )
        db.add(dt)
        db.commit()
        return dt

    @staticmethod
    def get_maintenance_history(db: Session, entity_id: int, entity_type: str = "battery") -> List[MaintenanceRecord]:
        return db.exec(
            select(MaintenanceRecord)
            .where(MaintenanceRecord.entity_id == entity_id, MaintenanceRecord.entity_type == entity_type)
            .order_by(MaintenanceRecord.performed_at.desc())
        ).all()

    @staticmethod
    def get_maintenance_schedule(db: Session, entity_id: int, entity_type: str = "station") -> List[MaintenanceSchedule]:
        # In this model, schedules are templates, but we can return records marked as pending if they existed.
        # However, the SRS implies a task list. Let's use records with status='pending' or just history.
        return db.exec(
            select(MaintenanceRecord)
            .where(MaintenanceRecord.entity_id == entity_id, MaintenanceRecord.entity_type == entity_type)
            .order_by(MaintenanceRecord.performed_at.asc())
        ).all()
