from __future__ import annotations
"""
@audit_action decorator — wraps sensitive FastAPI endpoints to auto-log
the user, action, timestamp, IP, user-agent, and optionally old/new values.

Usage:
    @router.post("/some-action")
    @audit_action(action_type="DATA_MODIFICATION", resource_type="BATTERY")
    async def some_action(request: Request, ...):
        ...
"""

import functools
import logging
from typing import Optional

from fastapi import Request
from sqlmodel import Session

from app.models.audit_log import AuditLog
from app.core.proxy import get_client_ip

logger = logging.getLogger("wezu_audit")


def audit_action(
    action_type: str,
    resource_type: str,
    target_id_param: Optional[str] = None,
):
    """
    Decorator that logs an audit entry after a successful endpoint call.

    Args:
        action_type:    One of AuditActionType values.
        resource_type:  e.g. "USER", "WALLET", "AUTH".
        target_id_param: Name of the path/body param holding the target entity ID.
    """

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            request: Optional[Request] = kwargs.get("request")
            result = await func(*args, **kwargs)
            _write_log(request, kwargs, action_type, resource_type, target_id_param)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            request: Optional[Request] = kwargs.get("request")
            result = func(*args, **kwargs)
            _write_log(request, kwargs, action_type, resource_type, target_id_param)
            return result

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def _write_log(
    request: Optional[Request],
    kwargs: dict,
    action_type: str,
    resource_type: str,
    target_id_param: Optional[str],
):
    """Write the audit log entry, swallowing errors to never break the endpoint."""
    db: Optional[Session] = None
    own_session = False
    try:
        # Extract user info
        user_id = None
        current_user = kwargs.get("current_user")
        if current_user and hasattr(current_user, "id"):
            user_id = current_user.id

        # Extract request metadata
        ip_address = None
        user_agent = None
        if request:
            ip_address = get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")

        # Extract target ID
        target_id = None
        if target_id_param and target_id_param in kwargs:
            try:
                target_id = int(kwargs[target_id_param])
            except (ValueError, TypeError):
                pass

        # Get DB session
        db = kwargs.get("db") or kwargs.get("session")
        if db is None:
            # Fallback: create a new session
            from app.core.database import engine

            db = Session(engine)
            own_session = True

        log = AuditLog(
            user_id=user_id,
            action=action_type,
            resource_type=resource_type,
            target_id=target_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(log)
        db.commit()

        logger.info(
            f"Audit: {action_type} on {resource_type} by user {user_id} from {ip_address}"
        )
    except Exception as e:
        if db is not None:
            try:
                db.rollback()
            except Exception:
                pass
        logger.error(f"Failed to write audit log: {e}")
    finally:
        if own_session and db is not None:
            db.close()
