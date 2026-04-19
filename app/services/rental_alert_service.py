from __future__ import annotations
from datetime import datetime, timedelta, timezone; UTC = timezone.utc
from sqlmodel import Session, select
from app.models.rental import Rental
from typing import List
import logging

logger = logging.getLogger(__name__)

class RentalAlertService:
    @staticmethod
    def get_expiring_rentals(db: Session, hours_remaining: int) -> List[Rental]:
        """
        Identify rentals that will expire exactly (or within a window) around 
        the specified hours_remaining.
        """
        now = datetime.now(UTC)
        # window of 10 minutes to avoid missing due to cron timing
        target_time = now + timedelta(hours=hours_remaining)
        window_start = target_time - timedelta(minutes=5)
        window_end = target_time + timedelta(minutes=5)
        
        statement = select(Rental).where(Rental.status == "active")
        all_active = db.exec(statement).all()
        
        expiring = []
        for rental in all_active:
            expiry = rental.expected_end_time
            if expiry and window_start <= expiry <= window_end:
                expiring.append(rental)
                
        return expiring

    @staticmethod
    def process_expiry_alerts(db: Session):
        """
        Process all expiry alerts (24h, 12h, 1h).
        Typically called by a background task/cron.
        """
        alerts = [24, 12, 1]
        for hours in alerts:
            rentals = RentalAlertService.get_expiring_rentals(db, hours)
            for rental in rentals:
                RentalAlertService.trigger_alert(rental, hours)

    @staticmethod
    def trigger_alert(rental: Rental, hours: int):
        """
        Trigger the actual alert (Push Notification, SMS, etc.)
        """
        logger.info(f"Triggering {hours}h expiry alert for Rental {rental.id} (User {rental.user_id})")
        # In a real app, integrate with NotificationService here
        # NotificationService.send_push(
        #     user_id=rental.user_id,
        #     title="Rental Expiring Soon",
        #     body=f"Your battery rental expires in {hours} hour(s). Please swap or return to avoid late fees."
        # )
