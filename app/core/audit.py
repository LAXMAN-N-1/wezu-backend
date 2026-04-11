"""
Audit Logging System — Core Module

Provides:
- AuditLogger: Static utility class to log events
- @audit_log: Decorator factory for FastAPI endpoints
- cleanup_old_logs: Retention cleanup function for APScheduler
"""

import asyncio
import functools
import logging
from datetime import datetime, UTC, timedelta
from typing import Any, Callable, Dict, Optional

from fastapi import Request
from sqlmodel import select, Session

from app.core.proxy import get_client_ip
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditLogger:
    """Static utility class for direct audit event logging."""

    @staticmethod
    def log_event(
        db: Session,
        user_id: Optional[int],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        target_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
    ) -> Optional[AuditLog]:
        """
        Create an AuditLog record. Never raises — fails silently with logging.

        Args:
            db: Active database session
            user_id: ID of acting user (None for system actions)
            action: Action identifier e.g. AUTH_LOGIN, USER_CREATION
            resource_type: Entity type e.g. USER, BATTERY, AUTH
            resource_id: Optional entity ID (string, backward compat)
            target_id: Optional typed entity ID (int, indexed)
            metadata: Optional structured JSON context
            ip_address: Client IP address
            user_agent: Client user-agent string
            old_value: JSON dict of previous values (change tracking)
            new_value: JSON dict of new values (change tracking)
        """
        try:
            log_entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                target_id=target_id,
                meta_data=metadata,
                ip_address=ip_address,
                user_agent=user_agent,
                old_value=old_value,
                new_value=new_value,
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)
            logger.debug(f"Audit log created: {action} on {resource_type} by user {user_id}")
            return log_entry
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}", exc_info=True)
            db.rollback()
            return None


def audit_log(action: str, resource_type: str, resource_id_param: Optional[str] = None):
    """
    Decorator factory for FastAPI endpoints. Logs the action after successful execution.

    Usage:
        @router.post("/users/")
        @audit_log("USER_CREATION", "USER")
        async def create_user(request: Request, db: Session = Depends(get_db), ...):
            ...

    Args:
        action: Action identifier e.g. "AUTH_LOGIN", "USER_CREATION"
        resource_type: Entity type e.g. "USER", "BATTERY"
        resource_id_param: Name of the kwarg holding the resource ID
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            _log_from_context(kwargs, result, action, resource_type, resource_id_param)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            _log_from_context(kwargs, result, action, resource_type, resource_id_param)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def _log_from_context(
    kwargs: dict,
    result: Any,
    action: str,
    resource_type: str,
    resource_id_param: Optional[str] = None,
):
    """Extract request context from FastAPI kwargs and result, then log the event."""
    try:
        # Extract database session
        db: Optional[Session] = kwargs.get("db") or kwargs.get("session")
        if db is None:
            logger.warning(f"Audit log skipped (no db session): {action}")
            return

        # Extract request for IP and User-Agent
        request: Optional[Request] = kwargs.get("request") or kwargs.get("http_request")
        ip_address = None
        user_agent_str = None
        if request is not None:
            ip_address = get_client_ip(request)
            user_agent_str = request.headers.get("user-agent")

        # Extract current user
        current_user = kwargs.get("current_user")
        user_id = getattr(current_user, "id", None) if current_user else None

        # Extract resource ID
        resource_id = None
        target_id = None

        # 1. Try from explicit param in input
        if resource_id_param and resource_id_param in kwargs:
            resource_id = kwargs[resource_id_param]
            try:
                target_id = int(resource_id)
            except (ValueError, TypeError):
                pass

        # 2. Try from result (e.g. create returns the object)
        if not resource_id and result:
            resource_id = getattr(result, "id", None)
            if resource_id:
                try:
                    target_id = int(resource_id)
                except (ValueError, TypeError):
                    pass

        # 3. Auto-detect from input kwargs (fallback)
        if not resource_id:
            for key in ("user_id", "battery_id", "station_id", "swap_id", "payment_id", "order_id"):
                if key in kwargs and key != "user_id" or (
                    key == "user_id"
                    and key in kwargs
                    and current_user
                    and kwargs[key] != getattr(current_user, "id", None)
                ):
                    resource_id = kwargs[key]
                    try:
                        target_id = int(resource_id)
                    except (ValueError, TypeError):
                        pass
                    break

        # Extract Metadata: JSON body from kwargs
        metadata = {}
        for k, v in kwargs.items():
            if k.endswith("_in") or k == "payload":
                try:
                    if hasattr(v, "model_dump"):
                        metadata[k] = v.model_dump()
                    elif hasattr(v, "dict"):
                        metadata[k] = v.dict()
                except Exception:
                    pass

        AuditLogger.log_event(
            db=db,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            target_id=target_id,
            metadata=metadata if metadata else None,
            ip_address=ip_address,
            user_agent=user_agent_str,
        )
    except Exception as e:
        logger.error(f"Audit decorator failed to log: {e}", exc_info=True)


def cleanup_old_logs(db: Session, retention_days: int = 90) -> int:
    """
    Delete AuditLog records older than retention_days.
    Intended to be called by APScheduler or a management command.
    """
    try:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        result = db.execute(delete(AuditLog).where(AuditLog.timestamp < cutoff))
        db.commit()
        logger.info(f"Audit log cleanup: deleted {result} records older than {retention_days} days")
        return result
    except Exception as e:
        logger.error(f"Audit log cleanup failed: {e}", exc_info=True)
        db.rollback()
        return 0
