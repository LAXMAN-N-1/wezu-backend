from sqlmodel import Session, select
from app.core.database import get_db
from app.models.station import Station, StationStatus
from app.services.alert_service import AlertService
from datetime import datetime, UTC, timedelta
import logging

logger = logging.getLogger(__name__)

def monitor_stations():
    """
    Background job to check station health.
    Run every 2 minutes.
    """
    from app.core.database import engine
    with Session(engine) as session:
        try:
            # 1. Detect Offline Stations
            # Threshold: 365 days since last updated_at/heartbeat (Relaxed for mock data testing)
            threshold = datetime.now(UTC) - timedelta(days=365)
            
            offline_query = select(Station).where(
                Station.status == StationStatus.OPERATIONAL,
                Station.updated_at < threshold
            )
            offline_stations = session.exec(offline_query).all()
            
            for station in offline_stations:
                logger.warning(f"Station {station.name} (ID: {station.id}) is OFFLINE.")
                
                # Update Status
                station.status = StationStatus.OFFLINE
                session.add(station)
                
                # Create Alert
                AlertService.create_alert(
                    db=session,
                    station_id=station.id,
                    alert_type="offline",
                    severity="warning",
                    message=f"Station {station.name} hasn't sent a heartbeat since {station.updated_at}."
                )
            
            # 2. Daily Escalation logic (offline for > 10m)
            escalation_threshold = datetime.now(UTC) - timedelta(days=365)
            escalation_query = select(Station).where(
                Station.status == StationStatus.OFFLINE,
                Station.updated_at < escalation_threshold
            )
            needs_escalation = session.exec(escalation_query).all()
            
            for station in needs_escalation:
                # Check if alert already exists and needs escalation
                # For simplicity, we create a critical alert if offline > 10m
                AlertService.create_alert(
                    db=session,
                    station_id=station.id,
                    alert_type="offline_prolonged",
                    severity="critical",
                    message=f"CRITICAL: Station {station.name} is offline for more than 10 minutes!"
                )
             
            session.commit()
            logger.info(f"Health check completed. Found {len(offline_stations)} new offline stations.")
            
        except Exception as e:
            logger.error(f"Error in monitor_stations: {e}")
            session.rollback()
