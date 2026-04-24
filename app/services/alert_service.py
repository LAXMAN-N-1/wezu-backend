from __future__ import annotations
from sqlmodel import Session, select
from app.models.alert import Alert
from app.models.station import Station
from app.services.notification_service import NotificationService
from datetime import datetime, timezone; UTC = timezone.utc
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

    @staticmethod
    def process_battery_telemetry(
        db: Session,
        battery_id: str,
        charge_percent: float = None,
        health_percent: float = None,
        temp_celsius: float = None,
        days_to_maintenance: int = None
    ):
        from app.models.rental import Rental
        from app.models.user_alert_config import UserAlertConfig
        from app.models.battery_health import BatteryHealthAlert, AlertType, AlertSeverity
        
        statement = select(Rental).where(
            Rental.battery_id == battery_id, 
            Rental.status == "active"
        )
        rental = db.exec(statement).first()
        if not rental:
            return 

        config = db.exec(select(UserAlertConfig).where(UserAlertConfig.user_id == rental.user_id)).first()
        if not config:
            config = UserAlertConfig(user_id=rental.user_id)
            
        if not config.alerts_enabled:
            return

        alerts_to_create = []
        
        if charge_percent is not None and charge_percent < config.low_charge_percent:
            alerts_to_create.append((
                AlertType.CRITICAL_HEALTH,
                AlertSeverity.WARNING,
                f"Battery charge dropped to {charge_percent}% (Below {config.low_charge_percent}% threshold)."
            ))
            
        if health_percent is not None and health_percent < config.low_health_percent:
            alerts_to_create.append((
                AlertType.RAPID_DEGRADATION,
                AlertSeverity.CRITICAL,
                f"Battery health degraded to {health_percent}% (Below {config.low_health_percent}% threshold)."
            ))
            
        if temp_celsius is not None and temp_celsius > config.high_temp_celsius:
            alerts_to_create.append((
                AlertType.HIGH_TEMP,
                AlertSeverity.CRITICAL,
                f"Battery temperature is {temp_celsius}°C (Above {config.high_temp_celsius}°C threshold)."
            ))
            
        if days_to_maintenance is not None and days_to_maintenance <= config.maintenance_reminder_days:
            alerts_to_create.append((
                AlertType.OVERDUE_SERVICE,
                AlertSeverity.INFO,
                f"Maintenance is due in {days_to_maintenance} days."
            ))
            
        for a_type, severity, msg in alerts_to_create:
            existing = db.exec(
                select(BatteryHealthAlert).where(
                    BatteryHealthAlert.battery_id == battery_id,
                    BatteryHealthAlert.alert_type == a_type,
                    BatteryHealthAlert.is_resolved == False
                )
            ).first()
            
            if not existing:
                new_alert = BatteryHealthAlert(
                    battery_id=battery_id,
                    alert_type=a_type,
                    severity=severity,
                    message=msg,
                    is_resolved=False
                )
                db.add(new_alert)
        db.commit()

