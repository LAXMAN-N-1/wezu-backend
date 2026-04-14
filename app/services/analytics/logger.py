from typing import Dict, Any, Optional

from app.core.logging import get_logger

logger = get_logger("analytics_event_logger")

class AnalyticsLogger:
    """
    Append-only lightweight event logger.
    These logs are picked up by Celery tasks to populate summary tables.
    """
    @staticmethod
    async def log_event(event_type: str, user_id: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None):
        logger.info(
            "analytics.event",
            event_type=event_type,
            user_id=user_id,
            metadata=metadata or {},
        )
        # Next steps for production: write 'log_data' reliably to Redis Streams or a specialized event table.
