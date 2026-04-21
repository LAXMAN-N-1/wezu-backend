import secrets
import string
from contextvars import ContextVar
from typing import Optional, Dict, Any
from sqlmodel import Session
from app.models.audit_log import AuditLog, AUDIT_MODULES
from app.utils.data_masking import mask_dict

# Context Variables for HTTP Request lifecycle
# These are automatically populated by the Audit Middleware
session_ctx: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
trace_ctx: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
role_prefix_ctx: ContextVar[Optional[str]] = ContextVar("role_prefix", default=None)
user_id_ctx: ContextVar[Optional[int]] = ContextVar("user_id", default=None)


def generate_action_id(prefix: str) -> str:
    """
    Generates a 32-character action ID using a predefined 3-char prefix.
    Example: DLR + 29 random characters
    """
    if not prefix:
        prefix = "SYS"
    prefix = prefix.upper()[:3].ljust(3, "X")
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(29))
    return f"{prefix}{random_part}"


def generate_trace_id() -> str:
    """Generates a 32-char trace ID entirely composed of random alphanumeric characters."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))


def log_audit_action(
    db: Session,
    action: str,
    module: str = "system",
    status: str = "success",
    level: str = "INFO",
    resource_type: Optional[str] = None,
    target_id: Optional[int] = None,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    meta_data: Optional[Dict[str, Any]] = None,
    details: Optional[str] = None,
    response_time_ms: Optional[float] = None
) -> str:
    """
    Creates an AuditLog tying Business Events to the overarching HTTP Trace and Session Context.
    Masking should be applied to `old_value` and `new_value` prior to calling this function.
    Returns the newly minted action_id.
    """
    # 1. Module Validation & Default
    if module not in AUDIT_MODULES:
        module = "system"
        
    current_prefix = role_prefix_ctx.get() or "SYS"
    action_id = generate_action_id(current_prefix)

    log_entry = AuditLog(
        trace_id=trace_ctx.get(),
        session_id=session_ctx.get(),
        action_id=action_id,
        role_prefix=current_prefix,
        user_id=user_id_ctx.get(),
        level=level,
        action=action,
        module=module,
        status=status,
        resource_type=resource_type,
        target_id=target_id,
        old_value=mask_dict(old_value),
        new_value=mask_dict(new_value),
        details=details,
        meta_data=mask_dict(meta_data),
        response_time_ms=response_time_ms
    )
    
    db.add(log_entry)
    
    # Intentionally not calling db.commit() to allow the caller's transaction wrapper 
    # to commit business data and audit logs atomically.
    return action_id
