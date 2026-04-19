from __future__ import annotations
from sqlmodel import Session, select
from app.core.database import engine
from app.models.battery import Battery
from app.services.battery_service import BatteryService
from datetime import datetime, timezone; UTC = timezone.utc
import logging

logger = logging.getLogger(__name__)

def monitor_battery_health():
    """
    Background task to process health data for all active batteries.
    - Calculates SOH
    - Updates health status
    - Flags DAMAGED/POOR batteries
    """
    logger.info("Starting periodic battery health monitor task...")
    
    with Session(engine) as session:
        # We only monitor batteries that are available, in use, or charging
        stmt = select(Battery).where(Battery.status.in_(["available", "rented", "charging"]))
        batteries = session.exec(stmt).all()
        
        updated_count = 0
        for battery in batteries:
            try:
                # 1. Re-calculate SOH
                new_soh = BatteryService.calculate_soh(session, battery)
                battery.state_of_health = new_soh
                
                # 2. Update status and log alerts if necessary
                BatteryService.update_health_status(session, battery)
                
                battery.updated_at = datetime.now(UTC)
                session.add(battery)
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to monitor health for battery {battery.id}: {str(e)}")
        
        session.commit()
        logger.info(f"Battery health monitor completed. Updated {updated_count} batteries.")

if __name__ == "__main__":
    monitor_battery_health()
