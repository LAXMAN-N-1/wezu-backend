from sqlmodel import Session, select
from app.models.alert import Alert
from app.models.station import Station
from app.services.notification_service import NotificationService
from datetime import datetime, UTC
from typing import List, Optional

class AlertService:
    @staticmethod
    def create_alert(
        db: Session,
        station_id: int,
        alert_type: str,
        severity: str,
        message: str
    ) -> Alert:
        alert = Alert(
            station_id=station_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            created_at=datetime.now(UTC)
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        
        # Notify Dealer
        station = db.get(Station, station_id)
        if station and station.dealer:
            user = station.dealer.user
            if user:
                NotificationService.send_notification(
                    db=db,
                    user=user,
                    title=f"Station Alert: {station.name}",
                    message=message,
                    type="warning",
                    channel="email" # As per requirement: email/SMS
                )
        
        return alert

    @staticmethod
    def get_active_alerts(db: Session, skip: int = 0, limit: int = 100) -> List[Alert]:
        return db.exec(
            select(Alert)
            .where(Alert.acknowledged_at == None)
            .order_by(Alert.created_at.desc())
            .offset(skip).limit(limit)
        ).all()

    @staticmethod
    def acknowledge_alert(db: Session, alert_id: int, user_id: int) -> Optional[Alert]:
        alert = db.get(Alert, alert_id)
        if alert:
            alert.acknowledged_at = datetime.now(UTC)
            alert.acknowledged_by = user_id
            db.add(alert)
            db.commit()
            db.refresh(alert)
        return alert
