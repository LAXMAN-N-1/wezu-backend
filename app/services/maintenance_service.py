from sqlmodel import Session, select
from app.core.database import engine
from app.models.maintenance import (
    MaintenanceSchedule,
    MaintenanceRecord,
    StationDowntime,
)
from app.models.maintenance_checklist import MaintenanceChecklistTemplate
from app.models.battery import Battery
from app.models.station import Station
from app.services.battery_consistency import apply_battery_transition
from datetime import datetime, timedelta
import logging
import json
from typing import Any, Optional

logger = logging.getLogger("wezu_maintenance")

class MaintenanceService:
    VALID_ENTITY_TYPES = {"battery", "station"}

    @staticmethod
    def _validate_entity_type(entity_type: str) -> str:
        normalized = (entity_type or "").strip().lower()
        if normalized not in MaintenanceService.VALID_ENTITY_TYPES:
            raise ValueError(
                f"Unsupported entity_type '{entity_type}'. Allowed: {sorted(MaintenanceService.VALID_ENTITY_TYPES)}"
            )
        return normalized

    @staticmethod
    def _parse_interval_days(
        *,
        recurrence_rule: Optional[str],
        interval_days: Optional[int],
    ) -> Optional[int]:
        if interval_days and interval_days > 0:
            return interval_days

        rule = (recurrence_rule or "").strip().upper()
        if not rule:
            return None

        if rule in {"DAILY", "WEEKLY", "MONTHLY"}:
            return {"DAILY": 1, "WEEKLY": 7, "MONTHLY": 30}[rule]

        if rule.startswith("FREQ="):
            parts = {}
            for raw in rule.split(";"):
                if "=" not in raw:
                    continue
                key, value = raw.split("=", 1)
                parts[key.strip()] = value.strip()
            freq = parts.get("FREQ")
            try:
                interval = int(parts.get("INTERVAL", "1"))
            except ValueError:
                interval = 1
            interval = max(1, interval)

            if freq == "DAILY":
                return interval
            if freq == "WEEKLY":
                return 7 * interval
            if freq == "MONTHLY":
                return 30 * interval
        return None

    @staticmethod
    def _compute_next_due_date(
        schedule: MaintenanceSchedule,
        *,
        baseline: datetime,
    ) -> Optional[datetime]:
        interval = MaintenanceService._parse_interval_days(
            recurrence_rule=schedule.recurrence_rule,
            interval_days=schedule.interval_days,
        )
        if interval:
            return baseline + timedelta(days=interval)
        return schedule.next_maintenance_date

    @staticmethod
    def _select_active_schedules(
        db: Session,
        *,
        entity_type: Optional[str] = None,
    ) -> list[MaintenanceSchedule]:
        query = select(MaintenanceSchedule)
        if entity_type:
            query = query.where(MaintenanceSchedule.entity_type == entity_type)
        try:
            return db.exec(query.where(MaintenanceSchedule.is_active == True)).all()  # noqa: E712
        except Exception:
            # Backward compatibility for environments where is_active is not migrated yet.
            return db.exec(query).all()

    @staticmethod
    def auto_generate_schedules(db: Session):
        """
        Check all batteries and stations against maintenance rules and flag them if due.
        """
        # 1. Process Batteries
        battery_schedules = MaintenanceService._select_active_schedules(db, entity_type="battery")
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
                    apply_battery_transition(
                        db,
                        battery=battery,
                        to_status="maintenance",
                        event_type="maintenance_due",
                        event_description=f"Auto-flagged for maintenance: {reason}",
                        actor_id=None,
                    )
                    logger.info(f"Battery {battery.serial_number} flagged for maintenance: {reason}")
                    schedule.last_maintenance_date = schedule.last_maintenance_date or last_date
                    schedule.next_maintenance_date = MaintenanceService._compute_next_due_date(
                        schedule,
                        baseline=schedule.last_maintenance_date,
                    )
                    db.add(schedule)

        # 2. Process Stations
        station_schedules = MaintenanceService._select_active_schedules(db, entity_type="station")
        # Load stations once outside the loop (was inside, causing repeated full-table scans)
        all_non_maint_stations = db.exec(select(Station).where(Station.status != "maintenance")).all()
        for schedule in station_schedules:
            for station in all_non_maint_stations:
                last_date = station.last_maintenance_date or station.created_at
                if schedule.interval_days and (datetime.utcnow() - last_date).days >= schedule.interval_days:
                    station.status = "maintenance"
                    db.add(station)
                    logger.info(f"Station {station.name} flagged for maintenance")
                    schedule.last_maintenance_date = schedule.last_maintenance_date or last_date
                    schedule.next_maintenance_date = MaintenanceService._compute_next_due_date(
                        schedule,
                        baseline=schedule.last_maintenance_date,
                    )
                    db.add(schedule)
        
        db.commit()

    @staticmethod
    def record_maintenance(db: Session, user_id: int, data: dict) -> MaintenanceRecord:
        entity_type = MaintenanceService._validate_entity_type(data.get("entity_type"))
        entity_id = data.get("entity_id")
        if entity_id is None:
            raise ValueError("entity_id is required")

        record = MaintenanceRecord(
            technician_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
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
            if not battery:
                raise ValueError("Battery not found")
            apply_battery_transition(
                db,
                battery=battery,
                to_status="ready",  # Maintenance completed and battery is verified ready.
                event_type="maintenance_completed",
                event_description=f"Maintenance record #{record.id} completed by user #{user_id}",
                actor_id=user_id,
            )
            battery.last_maintenance_date = record.performed_at
            battery.last_maintenance_cycles = battery.cycle_count
            db.add(battery)
        
        elif record.entity_type == "station":
            station = db.get(Station, record.entity_id)
            if not station or station.is_deleted:
                raise ValueError("Station not found")
            station.status = "active"
            station.last_maintenance_date = record.performed_at
            db.add(station)

        schedules = MaintenanceService._select_active_schedules(db, entity_type=record.entity_type)
        for schedule in schedules:
            schedule.last_maintenance_date = record.performed_at
            schedule.next_maintenance_date = MaintenanceService._compute_next_due_date(
                schedule,
                baseline=record.performed_at,
            )
            db.add(schedule)
        
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def get_maintenance_history(db: Session, battery_id: int) -> list[MaintenanceRecord]:
        """
        Return maintenance records for a battery in reverse chronological order.
        """
        return db.exec(
            select(MaintenanceRecord)
            .where(MaintenanceRecord.entity_type == "battery")
            .where(MaintenanceRecord.entity_id == battery_id)
            .order_by(MaintenanceRecord.performed_at.desc())
        ).all()

    @staticmethod
    def get_maintenance_schedule(db: Session, station_id: int) -> dict[str, Any]:
        """
        Build station maintenance dashboard payload:
        - active schedules (upcoming / overdue)
        - recent station maintenance history
        """
        station = db.get(Station, station_id)
        if not station or station.is_deleted:
            raise ValueError("Station not found")

        now = datetime.utcnow()
        schedules = MaintenanceService.list_schedules(db, entity_type="station", active_only=True)
        upcoming: list[dict[str, Any]] = []
        overdue: list[dict[str, Any]] = []

        for schedule in schedules:
            due_date = MaintenanceService.calculate_due_date(schedule)
            item = {
                "schedule_id": schedule.id,
                "entity_type": schedule.entity_type,
                "schedule_name": getattr(schedule, "schedule_name", None),
                "model_name": getattr(schedule, "model_name", None),
                "interval_days": schedule.interval_days,
                "interval_cycles": schedule.interval_cycles,
                "due_date": due_date,
                "template_id": getattr(schedule, "template_id", None),
            }
            if due_date and due_date < now:
                overdue.append(item)
            else:
                upcoming.append(item)

        history = db.exec(
            select(MaintenanceRecord)
            .where(MaintenanceRecord.entity_type == "station")
            .where(MaintenanceRecord.entity_id == station_id)
            .order_by(MaintenanceRecord.performed_at.desc())
            .limit(50)
        ).all()

        return {
            "station_id": station_id,
            "station_status": station.status,
            "upcoming": sorted(upcoming, key=lambda x: x["due_date"] or datetime.max),
            "overdue": sorted(overdue, key=lambda x: x["due_date"] or datetime.max),
            "history": history,
        }

    @staticmethod
    def report_downtime(db: Session, station_id: int, reason: str):
        station = db.get(Station, station_id)
        if not station or station.is_deleted:
            raise ValueError("Station not found")
        dt = StationDowntime(
            station_id=station_id,
            start_time=datetime.utcnow(),
            reason=reason
        )
        db.add(dt)
        db.commit()
        return dt

    @staticmethod
    def create_checklist_template(
        db: Session,
        *,
        name: str,
        entity_type: str,
        items: list[str],
        created_by: Optional[int],
    ) -> MaintenanceChecklistTemplate:
        normalized_entity_type = MaintenanceService._validate_entity_type(entity_type)
        template = MaintenanceChecklistTemplate(
            name=name.strip(),
            entity_type=normalized_entity_type,
            items=json.dumps(items),
            created_by=created_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        return template

    @staticmethod
    def list_checklist_templates(
        db: Session,
        *,
        entity_type: Optional[str] = None,
        active_only: bool = True,
    ) -> list[MaintenanceChecklistTemplate]:
        query = select(MaintenanceChecklistTemplate)
        if active_only:
            query = query.where(MaintenanceChecklistTemplate.is_active == True)  # noqa: E712
        if entity_type:
            query = query.where(MaintenanceChecklistTemplate.entity_type == entity_type.strip().lower())
        return db.exec(query.order_by(MaintenanceChecklistTemplate.created_at.desc())).all()

    @staticmethod
    def create_schedule(
        db: Session,
        *,
        entity_type: str,
        schedule_name: Optional[str],
        model_name: Optional[str],
        interval_days: Optional[int],
        interval_cycles: Optional[int],
        recurrence_rule: Optional[str],
        template_id: Optional[int],
        checklist_items: Optional[list[str]],
        next_maintenance_date: Optional[datetime],
    ) -> MaintenanceSchedule:
        normalized_entity_type = MaintenanceService._validate_entity_type(entity_type)
        checklist_payload = json.dumps(checklist_items or [])
        if template_id:
            template = db.get(MaintenanceChecklistTemplate, template_id)
            if not template or not template.is_active:
                raise ValueError("Checklist template not found or inactive")
            if template.entity_type != normalized_entity_type:
                raise ValueError("Checklist template entity_type mismatch")
            checklist_payload = template.items

        parsed_interval_days = MaintenanceService._parse_interval_days(
            recurrence_rule=recurrence_rule,
            interval_days=interval_days,
        )
        schedule = MaintenanceSchedule(
            entity_type=normalized_entity_type,
            schedule_name=(schedule_name or "").strip() or None,
            model_name=(model_name or "").strip() or None,
            interval_days=parsed_interval_days,
            interval_cycles=interval_cycles,
            recurrence_rule=(recurrence_rule or "").strip() or None,
            template_id=template_id,
            checklist=checklist_payload,
            next_maintenance_date=next_maintenance_date or (
                datetime.utcnow() + timedelta(days=parsed_interval_days)
                if parsed_interval_days
                else None
            ),
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return schedule

    @staticmethod
    def list_schedules(
        db: Session,
        *,
        entity_type: Optional[str] = None,
        active_only: bool = True,
    ) -> list[MaintenanceSchedule]:
        query = select(MaintenanceSchedule)
        if entity_type:
            query = query.where(MaintenanceSchedule.entity_type == entity_type.strip().lower())
        if not active_only:
            return db.exec(query.order_by(MaintenanceSchedule.created_at.desc())).all()
        try:
            query = query.where(MaintenanceSchedule.is_active == True)  # noqa: E712
        except Exception:
            logger.warning("maintenance.is_active_filter_failed", exc_info=True)
        return db.exec(query.order_by(MaintenanceSchedule.created_at.desc())).all()

    @staticmethod
    def calculate_due_date(schedule: MaintenanceSchedule) -> Optional[datetime]:
        if schedule.next_maintenance_date:
            return schedule.next_maintenance_date
        interval = MaintenanceService._parse_interval_days(
            recurrence_rule=schedule.recurrence_rule,
            interval_days=schedule.interval_days,
        )
        if schedule.last_maintenance_date and interval:
            return schedule.last_maintenance_date + timedelta(days=interval)
        return None

    @staticmethod
    def get_overdue_schedules(
        db: Session,
        *,
        entity_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        now = datetime.utcnow()
        schedules = MaintenanceService.list_schedules(db, entity_type=entity_type, active_only=True)
        overdue_items: list[dict[str, Any]] = []
        for schedule in schedules:
            due_date = MaintenanceService.calculate_due_date(schedule)
            if not due_date or due_date >= now:
                continue
            overdue_items.append(
                {
                    "schedule_id": schedule.id,
                    "entity_type": schedule.entity_type,
                    "schedule_name": schedule.schedule_name,
                    "model_name": schedule.model_name,
                    "due_date": due_date,
                    "days_overdue": (now - due_date).days,
                    "template_id": schedule.template_id,
                }
            )
        return overdue_items

    @staticmethod
    def run_schedule_automation(db: Session) -> dict[str, int]:
        """
        Enterprise-style scheduler hook:
        1) Mark due entities via existing auto generation.
        2) Detect overdue schedules and emit notifications.
        """
        from app.services.workflow_automation_service import WorkflowAutomationService

        MaintenanceService.auto_generate_schedules(db)
        overdue_items = MaintenanceService.get_overdue_schedules(db)
        alerts_sent = 0
        for item in overdue_items:
            if WorkflowAutomationService.notify_maintenance_schedule_overdue_ops(
                db,
                entity_type=item.get("entity_type", "unknown"),
                schedule_id=int(item.get("schedule_id")),
                model_name=item.get("model_name"),
                days_overdue=int(item.get("days_overdue", 0)),
            ):
                alerts_sent += 1
        return {
            "overdue_items": len(overdue_items),
            "alerts_sent": alerts_sent,
        }
