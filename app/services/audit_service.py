import csv
import io
import json
import logging
from typing import Optional, Dict, Any

from sqlmodel import Session, select
from app.core.database import engine
from app.models.audit_log import AuditLog, SecurityEvent
from datetime import datetime

logger = logging.getLogger(__name__)


class AuditService:
    @staticmethod
    def log_action(
        db: Session,
        action: str,
        resource_type: str,
        user_id: int = None,
        resource_id: str = None,
        target_id: int = None,
        details: str = None,
        ip_address: str = None,
        user_agent: str = None,
        old_value: Dict[str, Any] = None,
        new_value: Dict[str, Any] = None,
    ):
        """Create an audit log entry with full change tracking."""
        try:
            log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                target_id=target_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                old_value=old_value,
                new_value=new_value,
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    async def log_event(
        self,
        event_type: str,
        user_id: Optional[int],
        resource: str,
        action: str,
        status: str,
        metadata: Dict[str, Any],
        ip_address: Optional[str] = None
    ):
        """Async version for middleware and high-frequency logging."""
        with Session(engine) as db:
            try:
                log = AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_type=event_type,
                    resource_id=resource,
                    details=f"Status: {status}",
                    ip_address=ip_address,
                    meta_data=metadata
                )
                db.add(log)
                db.commit()
            except Exception as e:
                logger.error(f"Failed to log event: {e}")

    async def log_security_event(self, user_id: int, event: str, metadata: Dict[str, Any]):
        """Specialized helper for security-related events like login/password change"""
        await self.log_event(
            event_type="security",
            user_id=user_id,
            resource="auth",
            action=event,
            status="success",
            metadata=metadata
        )

    @staticmethod
    def log_security_event_sync(
        db: Session,
        event_type: str,
        severity: str,
        details: str = None,
        source_ip: str = None,
        user_id: int = None,
    ):
        try:
            event = SecurityEvent(
                event_type=event_type,
                severity=severity,
                details=details,
                source_ip=source_ip,
                user_id=user_id,
            )
            db.add(event)
            db.commit()

            if severity == "critical":
                logger.critical(f"SECURITY ALERT: {event_type} from {source_ip}")
        except Exception as e:
            logger.error(f"Failed to write security event: {e}")

    async def get_logs(self, user_id: int = None, page: int = 1, limit: int = 20):
        """Fetch paginated logs."""
        with Session(engine) as db:
            query = select(AuditLog)
            if user_id:
                query = query.where(AuditLog.user_id == user_id)
            
            total = len(db.exec(query).all())
            query = query.order_by(AuditLog.timestamp.desc()).offset((page - 1) * limit).limit(limit)
            logs = db.exec(query).all()
            
            return {
                "logs": [log.to_dict() if hasattr(log, "to_dict") else log for log in logs],
                "total_count": total
            }

    @staticmethod
    def _build_query(
        db: Session,
        user_id: int = None,
        action: str = None,
        resource_type: str = None,
        target_id: int = None,
        date_from: datetime = None,
        date_to: datetime = None,
    ):
        """Build a filtered query for audit logs (shared by list/export)."""
        query = select(AuditLog)
        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)
        if action is not None:
            query = query.where(AuditLog.action == action)
        if resource_type is not None:
            query = query.where(AuditLog.resource_type == resource_type)
        if target_id is not None:
            query = query.where(AuditLog.target_id == target_id)
        if date_from is not None:
            query = query.where(AuditLog.timestamp >= date_from)
        if date_to is not None:
            query = query.where(AuditLog.timestamp <= date_to)
        return query.order_by(AuditLog.timestamp.desc())

    @staticmethod
    def export_logs_csv(
        db: Session, **filters
    ) -> str:
        """Export filtered logs to a CSV string. Handles 100k+ records in-memory."""
        query = AuditService._build_query(db, **filters)
        logs = db.exec(query).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "user_id", "action", "resource_type", "target_id",
            "old_value", "new_value", "ip_address", "user_agent", "timestamp",
        ])
        for log in logs:
            writer.writerow([
                log.id, log.user_id, log.action, log.resource_type, log.target_id,
                json.dumps(log.old_value) if log.old_value else "",
                json.dumps(log.new_value) if log.new_value else "",
                log.ip_address, log.user_agent,
                log.timestamp.isoformat() if log.timestamp else "",
            ])
        return output.getvalue()

    @staticmethod
    def export_logs_json(
        db: Session, **filters
    ) -> list:
        """Export filtered logs as a JSON-serializable list."""
        query = AuditService._build_query(db, **filters)
        logs = db.exec(query).all()
        return [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "target_id": log.target_id,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in logs
        ]

audit_service = AuditService()
