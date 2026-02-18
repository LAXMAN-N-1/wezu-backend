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
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from fastapi import Request
from sqlmodel import Session

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
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Create an AuditLog record. Never raises — fails silently with logging.

        Args:
            db: Active database session
            user_id: ID of acting user (None for system actions)
            action: Action identifier e.g. LOGIN, CREATE_USER
            resource_type: Entity type e.g. USER, BATTERY, AUTH
            resource_id: Optional entity ID
            metadata: Optional structured JSON context
            ip_address: Client IP address
            user_agent: Client user-agent string
        """
        try:
            log_entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                meta_data=metadata,
                ip_address=ip_address,
                user_agent=user_agent,
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
        @audit_log("CREATE_USER", "USER")
        async def create_user(request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
            ...

    Args:
        action: Action identifier e.g. "LOGIN", "CREATE_USER"
        resource_type: Entity type e.g. "USER", "BATTERY"
        resource_id_param: Name of the kwarg holding the resource ID (e.g. "user_id", "battery_id")
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Execute the original endpoint first
            result = await func(*args, **kwargs)
            # Then log the event (non-blocking failure)
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
        # Extract database session (supports both 'db' and 'session' param names)
        db: Optional[Session] = kwargs.get("db") or kwargs.get("session")
        if db is None:
            logger.warning(f"Audit log skipped (no db session): {action}")
            return

        # Extract request for IP and User-Agent
        request: Optional[Request] = kwargs.get("request")
        ip_address = None
        user_agent_str = None
        if request is not None:
            ip_address = request.client.host if request.client else None
            user_agent_str = request.headers.get("user-agent")

        # Extract current user
        current_user = kwargs.get("current_user")
        user_id = getattr(current_user, "id", None) if current_user else None

        # Extract resource ID
        resource_id = None
        
        # 1. Try from explicit param in input (e.g. update/delete)
        if resource_id_param and resource_id_param in kwargs:
             resource_id = kwargs[resource_id_param]
             
        # 2. Try from result (e.g. create returns the object)
        if not resource_id and result:
            resource_id = getattr(result, "id", None)
            
        # 3. Auto-detect from input kwargs (fallback)
        if not resource_id:
            for key in ("user_id", "battery_id", "station_id", "swap_id", "payment_id", "order_id"):
                if key in kwargs and key != "user_id" or (key == "user_id" and key in kwargs and current_user and kwargs[key] != getattr(current_user, "id", None)):
                    resource_id = kwargs[key]
                    break

        # Extract Metadata: JSON body from kwargs (e.g. battery_in, user_in)
        metadata = {}
        for k, v in kwargs.items():
            if k.endswith("_in") or k == "payload":
                try:
                    # Try to dump pydantic model
                    if hasattr(v, "model_dump"):
                        metadata[k] = v.model_dump()
                    elif hasattr(v, "dict"):
                        metadata[k] = v.dict()
                except:
                    pass

        AuditLogger.log_event(
            db=db,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
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

    Returns:
        Number of deleted records.
    """
    try:
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        result = db.query(AuditLog).filter(AuditLog.timestamp < cutoff).delete()
        db.commit()
        logger.info(f"Audit log cleanup: deleted {result} records older than {retention_days} days")
        return result
    except Exception as e:
        logger.error(f"Audit log cleanup failed: {e}", exc_info=True)
        db.rollback()
        return 0
