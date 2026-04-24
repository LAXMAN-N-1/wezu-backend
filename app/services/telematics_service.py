from __future__ import annotations
from datetime import datetime, timezone; UTC = timezone.utc
from sqlmodel import Session, select
from app.models.battery import Battery, BatteryLifecycleEvent
from app.services.geofence_service import GeofenceService
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
            
        # Geofence Check
        lat, lon = data.get("lat"), data.get("lon")
        if lat and lon:
            is_valid, message = GeofenceService.check_boundary(db, lat, lon)
            if not is_valid:
                logger.error(f"GEOFENCE VIOLATION for battery {serial_number}: {message}")
                self.log_anomaly(db, battery.id, f"GEOFENCE_VIOLATION: {message}")
                # We also need to notify via MQTTService/WebSocket, but MQTTService calls this, 
                # so we can return the violation detail for MQTTService to broadcast
                data["geofence_violation"] = message
            
        battery.updated_at = datetime.now(UTC)
        db.add(battery)
        
        # Log update event if status changed or periodically
        # (Avoid logging every 30s heartbeat to DB, maybe log only on anomalies)
        
        db.commit()
        db.refresh(battery)
        
        # 3. Create Telemetry Log entry (TimescaleDB hypertable)
        from app.models.telemetry import Telemetry
        telemetry_log = Telemetry(
            battery_id=battery.id,
            device_id=battery.iot_device_id or "unknown",
            voltage=data.get("voltage"),
            current=data.get("current"),
            temperature=data.get("temp") or data.get("temperature"),
            soc=data.get("soc"),
            soh=data.get("soh") or data.get("health"),
            latitude=data.get("lat"),
            longitude=data.get("lon"),
            timestamp=datetime.now(UTC)
        )
        db.add(telemetry_log)
        db.commit()
        
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
