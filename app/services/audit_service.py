from __future__ import annotations
import csv
import io
import json
import logging
from typing import Optional, Dict, Any

from sqlmodel import Session, select, func
from app.core.database import engine
from app.models.audit_log import AuditLog, SecurityEvent
from app.utils.audit_context import log_audit_action
from datetime import datetime, UTC, timedelta, timezone; UTC = timezone.utc

logger = logging.getLogger(__name__)


class AuditService:
    @staticmethod
    def get_dashboard_counts(db: Session) -> Dict[str, Any]:
        """
        Summary counters for audit dashboard top cards.
        """
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)

        def _count_since(start: datetime, *, action: Optional[str] = None, status: Optional[str] = None, level: Optional[str] = None) -> int:
            query = select(func.count(AuditLog.id)).where(AuditLog.timestamp >= start)
            if action is not None:
                query = query.where(AuditLog.action == action)
            if status is not None:
                query = query.where(AuditLog.status == status)
            if level is not None:
                query = query.where(AuditLog.level == level)
            return int(db.exec(query).one() or 0)

        total_requests_today = _count_since(today_start)
        total_requests_yesterday = int(
            db.exec(
                select(func.count(AuditLog.id)).where(
                    AuditLog.timestamp >= yesterday_start,
                    AuditLog.timestamp < today_start,
                )
            ).one() or 0
        )

        failed_logins_today = _count_since(
            today_start,
            action="AUTH_LOGIN",
            status="failure",
        )
        failed_logins_yesterday = int(
            db.exec(
                select(func.count(AuditLog.id)).where(
                    AuditLog.timestamp >= yesterday_start,
                    AuditLog.timestamp < today_start,
                    AuditLog.action == "AUTH_LOGIN",
                    AuditLog.status == "failure",
                )
            ).one() or 0
        )

        critical_events_today = _count_since(today_start, level="CRITICAL")
        critical_events_yesterday = int(
            db.exec(
                select(func.count(AuditLog.id)).where(
                    AuditLog.timestamp >= yesterday_start,
                    AuditLog.timestamp < today_start,
                    AuditLog.level == "CRITICAL",
                )
            ).one() or 0
        )

        unique_users_today = int(
            db.exec(
                select(func.count(func.distinct(AuditLog.user_id))).where(
                    AuditLog.timestamp >= today_start,
                    AuditLog.user_id.is_not(None),
                )
            ).one() or 0
        )

        def _trend(current: int, previous: int) -> str:
            if previous > 0:
                pct = ((current - previous) / previous) * 100
            elif current > 0:
                pct = 100.0
            else:
                pct = 0.0
            sign = "+" if pct >= 0 else ""
            return f"{sign}{round(pct, 1)}%"

        return {
            "total_requests": total_requests_today,
            "failed_logins": failed_logins_today,
            "critical_events": critical_events_today,
            "active_users": unique_users_today,
            "requests_trend": _trend(total_requests_today, total_requests_yesterday),
            "failed_logins_trend": _trend(failed_logins_today, failed_logins_yesterday),
            "critical_trend": _trend(critical_events_today, critical_events_yesterday),
        }

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
            try:
                db.rollback()
            except Exception:
                logger.warning("audit.rollback_failed_after_write", exc_info=True)
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
        """Async version for middleware and high-frequency logging using context-aware logging."""
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
                try:
                    db.rollback()
                except Exception:
                    logger.warning("audit.rollback_failed_after_event", exc_info=True)
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
            try:
                db.rollback()
            except Exception:
                logger.warning("audit.rollback_failed_after_security_event", exc_info=True)
            logger.error(f"Failed to write security event: {e}")

    async def get_logs(self, user_id: int = None, page: int = 1, limit: int = 20):
        """Fetch paginated logs."""
        with Session(engine) as db:
            query = select(AuditLog)
            count_query = select(func.count(AuditLog.id))
            if user_id:
                query = query.where(AuditLog.user_id == user_id)
                count_query = count_query.where(AuditLog.user_id == user_id)

    async def get_logs_advanced(
        self,
        db: Session,
        user_id: int = None,
        action: str = None,
        resource_type: str = None,
        target_id: int = None,
        module: str = None,
        status: str = None,
        trace_id: str = None,
        date_from: datetime = None,
        date_to: datetime = None,
        page: int = 1,
        limit: int = 50,
        level: str = None,
        is_suspicious: bool = None,
        ip_address: str = None,
    ):
        """Standardized enterprise-grade paginated log retrieval."""
        query = self._build_query(
            db=db,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            target_id=target_id,
            module=module,
            status=status,
            trace_id=trace_id,
            date_from=date_from,
            date_to=date_to,
            level=level,
            is_suspicious=is_suspicious,
            ip_address=ip_address
        )
        
        # Count total
        count_query = select(func.count()).select_from(query.alias())
        total_count = db.exec(count_query).one()
        
        # Paginated fetch
        offset = (page - 1) * limit
        logs = db.exec(query.offset(offset).limit(limit)).all()
        
        return {
            "logs": [log.to_dict() if hasattr(log, "to_dict") else log for log in logs],
            "total_count": total_count
        }

    async def get_logs(self, user_id: int = None, page: int = 1, limit: int = 20):
        """Fetch paginated logs."""
        with Session(engine) as db:
            query = select(AuditLog)
            count_query = select(func.count(AuditLog.id))
            if user_id:
                query = query.where(AuditLog.user_id == user_id)
                count_query = count_query.where(AuditLog.user_id == user_id)

            total = int(db.exec(count_query).one() or 0)
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
        module: str = None,
        status: str = None,
        trace_id: str = None,
        level: str = None,
        is_suspicious: bool = None,
        ip_address: str = None,
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
        """Export filtered logs to CSV while iterating rows to avoid large memory spikes."""
        query = AuditService._build_query(db, **filters)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "user_id", "action", "resource_type", "target_id",
            "old_value", "new_value", "ip_address", "user_agent", "timestamp",
        ])
        for log in db.exec(query):
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
            for log in db.exec(query)
        ]

audit_service = AuditService()
