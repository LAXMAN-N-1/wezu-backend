from sqlmodel import Session
from app.core.database import engine
from app.models.audit_log import AuditLog, SecurityEvent
import logging

logger = logging.getLogger(__name__)

class AuditService:
    @staticmethod
    def log_action(db: Session, action: str, resource_type: str, user_id: int = None, resource_id: str = None, details: str = None, ip_address: str = None):
        try:
            log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    @staticmethod
    def log_security_event(db: Session, event_type: str, severity: str, details: str = None, source_ip: str = None, user_id: int = None):
        try:
            event = SecurityEvent(
                event_type=event_type,
                severity=severity,
                details=details,
                source_ip=source_ip,
                user_id=user_id
            )
            db.add(event)
            db.commit()
            
            # Trigger alert if critical (Mock)
            if severity == "critical":
                logger.critical(f"SECURITY ALERT: {event_type} from {source_ip}")
                
        except Exception as e:
            logger.error(f"Failed to write security event: {e}")
