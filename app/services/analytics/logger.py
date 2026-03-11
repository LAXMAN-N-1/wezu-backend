import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("analytics_event_logger")

class AnalyticsLogger:
    """
    Append-only lightweight event logger.
    These logs are picked up by Celery tasks to populate summary tables.
    """
    @staticmethod
    async def log_event(event_type: str, user_id: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None):
        log_data = {
            "event_type": event_type,
            "user_id": user_id,
            "metadata": metadata or {}
        }
        logger.info(f"ANALYTICS_EVENT: {log_data}")
        # Next steps for production: write 'log_data' reliably to Redis Streams or a specialized event table.
