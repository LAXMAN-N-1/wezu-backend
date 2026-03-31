from sqlmodel import Session, select
from typing import List, Optional
from app.core.database import engine
from app.models.maintenance import MaintenanceSchedule, MaintenanceRecord, StationDowntime, MaintenanceTemplate
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
        import json
        
        # Convert list to JSON string if necessary
        parts_replaced = data.get("parts_replaced")
        if isinstance(parts_replaced, list):
            parts_replaced = json.dumps(parts_replaced)
            
        checklist_submission = data.get("checklist_submission")
        if isinstance(checklist_submission, list):
            checklist_submission = json.dumps(checklist_submission)
            
        checklist_result = data.get("checklist_result")
        if isinstance(checklist_result, dict):
            checklist_result = json.dumps(checklist_result)
            
        
        record = MaintenanceRecord(
            technician_id=user_id,
            schedule_id=data.get("schedule_id"),
            station_id=data.get("station_id"),
            entity_type=data.get("entity_type"),
            entity_id=data.get("entity_id"),
            template_id=data.get("template_id"),
            maintenance_type=data.get("maintenance_type", "preventive"),
            description=data.get("description"),
            notes=data.get("notes"),
            cost=data.get("cost", 0.0),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            parts_replaced=parts_replaced,
            checklist_submission=checklist_submission,
            checklist_result=checklist_result,
            performed_at=datetime.utcnow(),
            status=data.get("status", "completed")
        )
        db.add(record)
        
        if record.schedule_id:
            schedule = db.get(MaintenanceSchedule, record.schedule_id)
            if schedule:
                schedule.status = "completed"
                db.add(schedule)
        
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
    def get_maintenance_schedule(db: Session, entity_id: int, entity_type: str = "station") -> List[MaintenanceRecord]:
        # In this model, schedules are templates, but we can return records marked as pending if they existed.
        # However, the SRS implies a task list. Let's use records with status='pending' or just history.
        return db.exec(
            select(MaintenanceRecord)
            .where(MaintenanceRecord.entity_id == entity_id, MaintenanceRecord.entity_type == entity_type)
            .order_by(MaintenanceRecord.performed_at.asc())
        ).all()

    @staticmethod
    def get_all_submissions(db: Session, skip: int = 0, limit: int = 100) -> List[MaintenanceRecord]:
        """Fetch history of completed maintenance tasks (submissions)"""
        return db.exec(
            select(MaintenanceRecord)
            .where(MaintenanceRecord.status == "completed")
            .offset(skip)
            .limit(limit)
            .order_by(MaintenanceRecord.performed_at.desc())
        ).all()

    @staticmethod
    def create_schedule(db: Session, data: dict) -> MaintenanceSchedule:
        from fastapi import HTTPException
        from sqlalchemy import and_, or_
        
        station_id = data.get("station_id")
        assigned_to = data.get("assigned_to")
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        
        # Conflict detection
        if start_time and end_time and (station_id or assigned_to):
            overlap_condition = and_(
                MaintenanceSchedule.start_time < end_time,
                MaintenanceSchedule.end_time > start_time,
                MaintenanceSchedule.status.in_(["scheduled", "in_progress"])
            )
            entity_condition = []
            if station_id:
                entity_condition.append(MaintenanceSchedule.station_id == station_id)
            if assigned_to:
                entity_condition.append(MaintenanceSchedule.assigned_to == assigned_to)
                
            conflicts = db.exec(select(MaintenanceSchedule).where(overlap_condition).where(or_(*entity_condition))).all()
            if conflicts:
                raise HTTPException(status_code=400, detail="Schedule conflict detected")
                
        schedule = MaintenanceSchedule(**data)
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return schedule

    @staticmethod
    def update_schedule(db: Session, schedule_id: int, update_data: dict) -> MaintenanceSchedule:
        from fastapi import HTTPException
        from sqlalchemy import and_, or_
        
        schedule = db.get(MaintenanceSchedule, schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
            
        new_start = update_data.get("start_time", schedule.start_time)
        new_end = update_data.get("end_time", schedule.end_time)
        new_station = update_data.get("station_id", schedule.station_id)
        new_assigned = update_data.get("assigned_to", schedule.assigned_to)
        
        if new_start and new_end and (new_station or new_assigned):
            overlap_condition = and_(
                MaintenanceSchedule.start_time < new_end,
                MaintenanceSchedule.end_time > new_start,
                MaintenanceSchedule.id != schedule_id,
                MaintenanceSchedule.status.in_(["scheduled", "in_progress"])
            )
            entity_condition = []
            if new_station:
                entity_condition.append(MaintenanceSchedule.station_id == new_station)
            if new_assigned:
                entity_condition.append(MaintenanceSchedule.assigned_to == new_assigned)
                
            conflicts = db.exec(select(MaintenanceSchedule).where(overlap_condition).where(or_(*entity_condition))).all()
            if conflicts:
                raise HTTPException(status_code=400, detail="Schedule conflict detected")
                
        for key, value in update_data.items():
            setattr(schedule, key, value)
            
        schedule.updated_at = datetime.utcnow()
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return schedule

    @staticmethod
    def get_calendar_view(db: Session) -> List[MaintenanceSchedule]:
        return db.exec(
            select(MaintenanceSchedule)
            .where(MaintenanceSchedule.status.in_(["scheduled", "in_progress"]))
            .order_by(MaintenanceSchedule.start_time.asc())
        ).all()

    @staticmethod
    def get_overdue_alerts(db: Session) -> List[dict]:
        now = datetime.utcnow()
        schedules = db.exec(
            select(MaintenanceSchedule)
            .where(MaintenanceSchedule.status == "scheduled")
            .where(MaintenanceSchedule.start_time < now)
        ).all()
        
        alerts = []
        for s in schedules:
            if not s.start_time:
                continue
            delay = int((now - s.start_time).total_seconds() / 60)
            alerts.append({
                "id": s.id,
                "station_id": s.station_id,
                "title": s.title,
                "scheduled_time": s.start_time,
                "status": s.status,
                "delay_minutes": delay
            })
        return alerts
