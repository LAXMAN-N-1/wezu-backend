from sqlmodel import Session, select
from app.core.database import engine
from app.models.maintenance import MaintenanceSchedule, MaintenanceRecord, StationDowntime
from app.models.battery import Battery
from datetime import datetime, timedelta

class MaintenanceService:
    @staticmethod
    def check_batteries_due():
        with Session(engine) as session:
            schedules = session.exec(select(MaintenanceSchedule).where(MaintenanceSchedule.entity_type == "battery")).all()
            if not schedules:
                return
            
            batteries = session.exec(select(Battery)).all()
            for battery in batteries:
                # Mock logic: Check cycles count if trackable, or time
                # Ideally, we check against specific schedule for model
                pass
                # if due, create Notification or Alert

    @staticmethod
    def record_maintenance(user_id: int, data: dict) -> MaintenanceRecord:
        with Session(engine) as session:
            record = MaintenanceRecord(
                technician_id=user_id,
                **data,
                performed_at=datetime.utcnow()
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    @staticmethod
    def report_downtime(station_id: int, reason: str):
         with Session(engine) as session:
             dt = StationDowntime(
                 station_id=station_id,
                 start_time=datetime.utcnow(),
                 reason=reason
             )
             session.add(dt)
             session.commit()
