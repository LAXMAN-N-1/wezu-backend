from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.core.database import engine
from app.models.rental import Rental
from app.models.notification_log import NotificationLog
from app.services.station_service import StationService
from app.services.notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)

def run_rental_expiry_job():
    logger.info("Running scheduled rental expiry job...")
    with Session(engine) as db:
        now = datetime.utcnow()
        
        # Step 1: Fetch all active rentals expiring within the next 24 hours
        statement = select(Rental).where(
            Rental.status == "active",
            Rental.expected_end_time <= now + timedelta(hours=24),
            Rental.expected_end_time > now
        )
        expiring_rentals = db.exec(statement).all()

        for rental in expiring_rentals:
            hours_remaining = (rental.expected_end_time - now).total_seconds() / 3600

            # Step 2: Determine which milestones apply and haven't been sent yet
            for milestone in [24, 12, 1]:
                if hours_remaining <= milestone:
                    already_sent = db.exec(
                        select(NotificationLog).where(
                            NotificationLog.rental_id == rental.id,
                            NotificationLog.milestone_hours == milestone
                        )
                    ).first()

                    if not already_sent:
                        # Step 3: Get nearest 3 swap/return stations
                        # Assuming 0.0 fallback if Rental doesn't have live coordinates
                        lat = getattr(rental, 'last_known_lat', 0.0)
                        lng = getattr(rental, 'last_known_lng', 0.0)
                        
                        logger.info(f"Triggering {milestone}h expiry notification for rental {rental.id}")
                        
                        try:
                            nearest_stations = StationService.get_nearby(db=db, lat=lat, lon=lng, radius_km=50.0)
                            nearest_stations = nearest_stations[:3] if nearest_stations else []
                        except Exception as e:
                            logger.error(f"Error getting nearby stations: {e}")
                            nearest_stations = []
                        
                        # Step 4: Send FCM push notification
                        NotificationService.dispatch_expiry_notification(
                            db=db,
                            user_id=rental.user_id,
                            rental=rental,
                            milestone_hours=milestone,
                            stations=nearest_stations
                        )

                        # Step 5: Log to prevent duplicate sends
                        db.add(NotificationLog(
                            rental_id=rental.id,
                            milestone_hours=milestone,
                            sent_at=now
                        ))
                        db.commit()
