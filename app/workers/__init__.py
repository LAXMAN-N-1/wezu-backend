from __future__ import annotations
"""
Background Workers Package
Handles all scheduled and background tasks
"""
from app.workers.scheduler import scheduler, start_scheduler, stop_scheduler, get_scheduler_runtime_state


def get_stream_worker_state() -> dict:
    """Return event-stream worker state for diagnostics (stub)."""
    return {"status": "not_configured", "events_processed": 0}


__all__ = ['scheduler', 'start_scheduler', 'stop_scheduler', 'get_scheduler_runtime_state', 'get_stream_worker_state']
