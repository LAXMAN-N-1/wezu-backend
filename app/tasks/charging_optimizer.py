from sqlmodel import Session, select
from app.core.database import engine
from app.models.station import Station
from app.models.battery import Battery
from app.models.charging_queue import ChargingQueue
from app.services.charging_service import ChargingService
from app.schemas.station_monitoring import OptimizationBattery
import logging

logger = logging.getLogger(__name__)

def optimize_charging_queues():
    """
    Background task to re-calculate charging priorities for all stations.
    - Iterates through active stations
    - Gets batteries currently at the station (charging or ready)
    - Re-runs prioritization algorithm
    - Updates ChargingQueue table
    """
    logger.info("Starting charging queue optimization task...")
    
    with Session(engine) as session:
        stations = session.exec(select(Station).where(Station.status == "active")).all()
        
        for station in stations:
            try:
                # 1. Get batteries currently in slots at this station
                # We reuse the logic from ChargingService.get_charging_queue but persist the result
                queue_items = ChargingService.get_charging_queue(session, station.id)
                
                if not queue_items:
                    continue
                    
                # 2. Update/Clear existing queue for this station
                # (Simple approach: Clear and rebuild)
                existing = session.exec(select(ChargingQueue).where(ChargingQueue.station_id == station.id)).all()
                for e in existing:
                    session.delete(e)
                
                # 3. Persist new optimized queue
                for item in queue_items:
                    db_item = ChargingQueue(
                        station_id=station.id,
                        battery_id=int(item.battery_id),
                        priority_score=item.priority_score,
                        queue_position=item.queue_position,
                        estimated_completion_time=item.estimated_completion_time
                    )
                    session.add(db_item)
                
                session.commit()
                logger.debug(f"Optimized queue for station {station.id}: {len(queue_items)} batteries.")
                
            except Exception as e:
                logger.error(f"Failed to optimize queue for station {station.id}: {str(e)}")
                session.rollback()
        
        logger.info("Charging queue optimization completed.")

if __name__ == "__main__":
    optimize_charging_queues()
