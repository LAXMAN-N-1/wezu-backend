from sqlmodel import Session, select, func
from app.models.fraud_alert import FraudAlert, FraudAlertStatus
from app.models.user import User
from app.models.audit_log import AuditLog
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC, timedelta

class AdminFraudService:
    @staticmethod
    def get_dashboard_summary(db: Session) -> Dict[str, Any]:
        """Summarize risk alerts for the dashboard."""
        high_risk_count = db.exec(
            select(func.count(FraudAlert.id))
            .where(FraudAlert.status == FraudAlertStatus.OPEN)
            .where(FraudAlert.risk_score >= 80)
        ).one()
        
        investigation_count = db.exec(
            select(func.count(FraudAlert.id))
            .where(FraudAlert.status == FraudAlertStatus.UNDER_INVESTIGATION)
        ).one()
        
        resolved_today = db.exec(
            select(func.count(FraudAlert.id))
            .where(FraudAlert.status == FraudAlertStatus.RESOLVED)
            .where(FraudAlert.resolved_at >= datetime.now(UTC).date())
        ).one()
        
        return {
            "high_risk": high_risk_count,
            "investigating": investigation_count,
            "resolved_today": resolved_today
        }

    @staticmethod
    def get_fraud_trend(db: Session, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch daily fraud detection vs. resolution trend."""
        # This would normally be a grouped by date SQL query
        # For now, a mock-friendly approach for the demo logic
        trend = []
        now = datetime.now(UTC).date()
        for i in range(days):
            date = now - timedelta(days=i)
            # Counts for the day
            detected = db.exec(
                select(func.count(FraudAlert.id))
                .where(func.date(FraudAlert.detected_at) == date)
            ).one()
            
            resolved = db.exec(
                select(func.count(FraudAlert.id))
                .where(func.date(FraudAlert.resolved_at) == date)
            ).one()
            
            trend.append({
                "date": date.isoformat(),
                "detected": detected,
                "resolved": resolved
            })
        
        return trend[::-1] # Newest last

    @staticmethod
    def list_alerts(
        db: Session, 
        status: Optional[str] = None, 
        alert_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[FraudAlert]:
        """List paginated fraud alerts with filters."""
        statement = select(FraudAlert)
        if status:
            statement = statement.where(FraudAlert.status == status)
        if alert_type:
            statement = statement.where(FraudAlert.alert_type == alert_type)
            
        return db.exec(statement.order_by(FraudAlert.detected_at.desc()).offset(skip).limit(limit)).all()

    @staticmethod
    def add_investigation_note(db: Session, alert_id: str, note: str, admin_user: User) -> FraudAlert:
        """Add admin notes to a fraud investigation."""
        alert = db.exec(select(FraudAlert).where(FraudAlert.alert_id == alert_id)).first()
        if not alert:
            raise Exception("Alert not found")
            
        new_note = {
            "admin_id": admin_user.id,
            "admin_name": admin_user.full_name or admin_user.email,
            "note": note,
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        # Use existing investigation_notes but make a copy for JSON update
        notes = list(alert.investigation_notes)
        notes.append(new_note)
        alert.investigation_notes = notes
        
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    @staticmethod
    def update_alert_status(db: Session, alert_id: str, status: str, admin_user: User) -> FraudAlert:
        """Update fraud alert state."""
        alert = db.exec(select(FraudAlert).where(FraudAlert.alert_id == alert_id)).first()
        if not alert:
            raise Exception("Alert not found")
            
        alert.status = status
        if status in [FraudAlertStatus.RESOLVED, FraudAlertStatus.FALSE_POSITIVE]:
            alert.resolved_at = datetime.now(UTC)
            alert.resolved_by_id = admin_user.id
            
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    @staticmethod
    def get_user_activity_timeline(db: Session, user_id: int, limit: int = 20) -> List[AuditLog]:
        """Fetch recent forensic history for a specific user to aid investigations."""
        return db.exec(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        ).all()
