from sqlmodel import Session, select
from app.core.database import get_db
from app.models.station import Station, StationStatus
from app.services.alert_service import AlertService
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def monitor_stations():
    """
    Background job to check station health.
    Run every 2 minutes.
    """
    # Get DB session from generator
    db_gen = get_db()
    db: Session = next(db_gen)
    
    try:
        # 1. Detect Offline Stations
        # Threshold: 5 minutes since last updated_at/heartbeat
        threshold = datetime.utcnow() - timedelta(minutes=5)
        
        offline_query = select(Station).where(
            Station.status == StationStatus.OPERATIONAL,
            Station.updated_at < threshold
        )
        offline_stations = db.exec(offline_query).all()
        
        for station in offline_stations:
            logger.warning(f"Station {station.name} (ID: {station.id}) is OFFLINE.")
            
            # Update Status
            station.status = StationStatus.OFFLINE
            db.add(station)
            
            # Create Alert
            AlertService.create_alert(
                db=db,
                station_id=station.id,
                alert_type="offline",
                severity="warning",
                message=f"Station {station.name} hasn't sent a heartbeat since {station.updated_at}."
            )
        
        # 2. Daily Escalation logic (offline for > 10m)
        escalation_threshold = datetime.utcnow() - timedelta(minutes=10)
        escalation_query = select(Station).where(
            Station.status == StationStatus.OFFLINE,
            Station.updated_at < escalation_threshold
        )
        needs_escalation = db.exec(escalation_query).all()
        
        for station in needs_escalation:
             # Check if alert already exists and needs escalation
             # For simplicity, we create a critical alert if offline > 10m
             AlertService.create_alert(
                db=db,
                station_id=station.id,
                alert_type="offline_prolonged",
                severity="critical",
                message=f"CRITICAL: Station {station.name} is offline for more than 10 minutes!"
            )
             
        db.commit()
        logger.info(f"Health check completed. Found {len(offline_stations)} new offline stations.")
        
    except Exception as e:
        logger.error(f"Error in monitor_stations: {e}")
        db.rollback()
    finally:
        # If it's a generator, we should close it if needed, 
        # but typical FastAPI get_db doesn't need explicit close here 
        # as it's handled by the 'with' or yield.
        pass
