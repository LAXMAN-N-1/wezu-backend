"""
P3-B: Observability primitives for service-level SLO instrumentation.

Provides:
  - ``flow_id()``           — deterministic alias for request_id (or fresh UUID)
  - ``SLOTimer``            — context manager that logs wall-clock duration and
                              emits a structured ``slo.breach`` event when a call
                              exceeds its budget.
  - ``emit_slo_event()``    — low-level structured log helper for SLO metrics.
  - ``measure()``           — decorator for automatically timing any function.

Usage::

    from app.core.observability import SLOTimer, flow_id

    async def handle_payment(request):
        fid = flow_id(request)
        with SLOTimer("wallet.add_balance", budget_ms=500, flow_id=fid):
            WalletService.add_balance(db, user_id, amount)
"""

from __future__ import annotations

import functools
import logging
from contextlib import contextmanager
from time import perf_counter
from typing import Any, Optional
from uuid import uuid4

import structlog

logger = logging.getLogger("wezu_observability")
_slog = structlog.get_logger("wezu_observability")


# ── Flow ID ─────────────────────────────────────────────────────────────

def flow_id(request: Any = None) -> str:
    """Return the current request_id, or generate a fresh UUID for non-request contexts."""
    if request is not None:
        rid = getattr(getattr(request, "state", None), "request_id", None)
        if rid:
            return str(rid)
    return str(uuid4())


# ── SLO Timer ────────────────────────────────────────────────────────────

@contextmanager
def SLOTimer(
    operation: str,
    *,
    budget_ms: float = 2000.0,
    flow_id: Optional[str] = None,
    extra: Optional[dict] = None,
):
    """Context manager that measures wall-clock time and logs SLO breaches.

    Args:
        operation:  Dot-separated operation name (e.g. "wallet.add_balance").
        budget_ms:  SLO budget in milliseconds.  If exceeded, a ``slo.breach``
                    event is emitted at WARNING level.
        flow_id:    Optional correlation/flow identifier.
        extra:      Additional key-value pairs attached to every log line.
    """
    fid = flow_id or str(uuid4())
    meta = {"operation": operation, "flow_id": fid, "budget_ms": budget_ms}
    if extra:
        meta.update(extra)

    start = perf_counter()
    try:
        yield meta  # caller can read/extend meta dict
    finally:
        elapsed_ms = round((perf_counter() - start) * 1000, 2)
        meta["elapsed_ms"] = elapsed_ms
        if elapsed_ms > budget_ms:
            _slog.warning("slo.breach", **meta)
        else:
            _slog.info("slo.ok", **meta)


# ── Structured SLO event emitter ─────────────────────────────────────────

def emit_slo_event(
    event: str,
    operation: str,
    elapsed_ms: float,
    budget_ms: float = 2000.0,
    *,
    flow_id: Optional[str] = None,
    **extra: Any,
) -> None:
    """Emit a structured SLO metric log line.

    Use this for one-shot measurements where ``SLOTimer`` is too heavy.
    """
    payload = {
        "operation": operation,
        "elapsed_ms": elapsed_ms,
        "budget_ms": budget_ms,
        "flow_id": flow_id or "",
        **extra,
    }
    if elapsed_ms > budget_ms:
        _slog.warning(event, **payload)
    else:
        _slog.info(event, **payload)


# ── Decorator for automatic timing ──────────────────────────────────────

def measure(operation: str, *, budget_ms: float = 2000.0):
    """Decorator that wraps a function in an SLOTimer.

    Works with both sync and async functions.

    Example::

        @measure("wallet.deduct_balance", budget_ms=300)
        def deduct_balance(db, user_id, amount):
            ...
    """

    def decorator(fn):
        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            with SLOTimer(operation, budget_ms=budget_ms):
                return fn(*args, **kwargs)

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            with SLOTimer(operation, budget_ms=budget_ms):
                return await fn(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    return decorator
