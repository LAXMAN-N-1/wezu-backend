from app.models.battery import Battery, BatteryLifecycleEvent, BatteryStatus
from app.models.telemetry import Telemetry
from app.models.rental import Rental
from app.schemas.battery import BatteryCreate, BatteryUpdate
from app.services.qr_service import QRCodeService
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlmodel import Session, select, func
from sqlalchemy import desc
from app.models.battery_health_log import BatteryHealthLog as BatteryHealthLogModel
from app.models.battery_catalog import BatterySpec
from app.schemas.station_monitoring import BatteryHealthStatus, BatteryHealthReport, BatteryHealthLog

class BatteryService:
    @staticmethod
    def get_by_id(db: Session, battery_id: int) -> Optional[Battery]:
        return db.get(Battery, battery_id)

    @staticmethod
    def get_by_serial(db: Session, serial: str) -> Optional[Battery]:
        return db.exec(select(Battery).where(Battery.serial_number == serial)).first()

    @staticmethod
    def list_batteries(db: Session, skip: int = 0, limit: int = 100) -> List[BatteryHealthStatus]:
        batteries = db.exec(select(Battery).offset(skip).limit(limit)).all()
        result = []
        for b in batteries:
            # Map percentage to status string
            status = "EXCELLENT"
            if b.health_percentage < 60: status = "DAMAGED"
            elif b.health_percentage < 75: status = "POOR"
            elif b.health_percentage < 85: status = "FAIR"
            elif b.health_percentage < 95: status = "GOOD"
            
            result.append(BatteryHealthStatus(
                battery_id=str(b.id),
                charge_cycles=b.cycle_count,
                state_of_health=b.health_percentage,
                health_status=status,
                last_maintenance_date=b.last_maintenance_date
            ))
        return result


    @staticmethod
    def get_health_report(db: Session, battery_id: int) -> BatteryHealthReport:
        battery = db.get(Battery, battery_id)
        if not battery:
            raise ValueError(f"Battery {battery_id} not found")
        
        # Get history from actual health logs
        logs_db = db.exec(
            select(BatteryHealthLogModel)
            .where(BatteryHealthLogModel.battery_id == battery_id)
            .order_by(BatteryHealthLogModel.timestamp.asc())
        ).all()
        
        logs_schema = [
            BatteryHealthLog(
                timestamp=l.timestamp,
                soh=l.health_percentage,
                status=battery.health_status # Current status
            ) for l in logs_db
        ]
        
        # Recommendations
        recommendation = "Maintain every 500 cycles."
        if battery.charge_cycles > 1000:
            recommendation = "Nearing end of life. Schedule deep inspection."
        if battery.state_of_health < 80:
            recommendation = "Performance degraded. Consider cell balancing."

        return BatteryHealthReport(
            battery_id=str(battery.id),
            state_of_health=battery.state_of_health,
            charge_cycles=battery.charge_cycles,
            temperature_history=battery.temperature_history,
            health_logs=logs_schema,
            maintenance_recommendation=recommendation
        )

    @staticmethod
    def calculate_soh(db: Session, battery: Battery) -> float:
        """
        IEEE Battery Health Standard inspired calculation:
        SOH = (Current Capacity / Rated Capacity) * 100
        Factors in cycle count and temperature exposure.
        """
        if not battery.spec:
            # Try to fetch spec if not loaded
            if battery.spec_id:
                battery.spec = db.get(BatterySpec, battery.spec_id)
            else:
                return battery.state_of_health # Can't calculate without spec

        rated_capacity = battery.spec.capacity_ah * 1000 # convert to mAh
        
        # Get latest health log with capacity reading
        latest_log = db.exec(
            select(BatteryHealthLogModel)
            .where(BatteryHealthLogModel.battery_id == battery.id)
            .where(BatteryHealthLogModel.current_capacity_mah != None)
            .order_by(desc(BatteryHealthLogModel.timestamp))
        ).first()

        current_capacity = latest_log.current_capacity_mah if latest_log else rated_capacity
        
        # Base SOH
        soh = (current_capacity / rated_capacity) * 100
        
        # Degradation factor for cycles (example: 0.01% per cycle beyond rated life)
        if battery.charge_cycles > battery.spec.cycle_life_expectancy:
            excess_cycles = battery.charge_cycles - battery.spec.cycle_life_expectancy
            soh -= (excess_cycles * 0.01)

        # Degradation factor for temperature (example: penalty for high temp readings)
        high_temp_count = sum(1 for t in battery.temperature_history if t > 45)
        soh -= (high_temp_count * 0.05)
        
        return max(0.0, min(100.0, soh))

    @staticmethod
    def update_health_status(db: Session, battery: Battery) -> str:
        """Update health_status based on SOH"""
        soh = battery.state_of_health
        
        status = "EXCELLENT"
        if soh < 70: status = "DAMAGED"
        elif soh < 80: status = "POOR"
        elif soh < 85: status = "FAIR"
        elif soh < 95: status = "GOOD"
        
        battery.health_status = status
        
        if status in ["POOR", "DAMAGED"]:
            # Generate Alert (simulated here with lifecycle event for now)
            event = BatteryLifecycleEvent(
                battery_id=battery.id,
                event_type="health_alert",
                description=f"Battery health dropped to {status} (SOH: {soh:.1f}%)"
            )
            db.add(event)
            
        return status

    @staticmethod
    def record_maintenance(db: Session, battery_id: int, notes: str, actor_id: Optional[int] = None) -> bool:
        battery = db.get(Battery, battery_id)
        if not battery:
            return False
        
        battery.last_maintenance_date = datetime.utcnow()
        battery.updated_at = datetime.utcnow()
        db.add(battery)
        
        # Log event
        event = BatteryLifecycleEvent(
            battery_id=battery_id,
            event_type="maintenance_complete",
            description=notes,
            actor_id=actor_id
        )
        db.add(event)
        
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

