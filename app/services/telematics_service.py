from datetime import datetime
from sqlmodel import Session, select
from app.models.battery import Battery, BatteryLifecycleEvent
import logging

logger = logging.getLogger("wezu_telematics")

class TelematicsService:
    @staticmethod
    def process_telemetry(db: Session, serial_number: str, data: dict):
        """
        Process raw telemetry data from IoT device.
        Example data: {"soc": 85.5, "soh": 98.2, "voltage": 62.4, "current": 2.1, "temp": 34.5}
        """
        statement = select(Battery).where(Battery.serial_number == serial_number)
        battery = db.exec(statement).first()
        
        if not battery:
            logger.error(f"Telemetry received for unknown battery: {serial_number}")
            return None

        # Update core metrics
        old_soc = battery.current_charge
        battery.current_charge = data.get("soc", battery.current_charge)
        battery.health_percentage = data.get("soh", battery.health_percentage)
        
        # Cycle counting logic (Simplified: if charge increases significantly, consider it part of a cycle)
        # In production, this would be more complex (accumulating Ah or tracking full 0-100-0)
        if battery.current_charge > old_soc + 20: 
             # Rough heuristic: significant charge increase
             pass 

        # Potential alert logic
        if battery.current_charge < 15:
            logger.warning(f"Battery {serial_number} is critically low: {battery.current_charge}%")
            # Logic to notify user or system
            
        battery.updated_at = datetime.utcnow()
        db.add(battery)
        
        # Log update event if status changed or periodically
        # (Avoid logging every 30s heartbeat to DB, maybe log only on anomalies)
        
        db.commit()
        db.refresh(battery)
        return battery

    @staticmethod
    def log_anomaly(db: Session, battery_id: int, description: str):
        event = BatteryLifecycleEvent(
            battery_id=battery_id,
            event_type="anomaly",
            description=description
        )
        db.add(event)
        db.commit()
