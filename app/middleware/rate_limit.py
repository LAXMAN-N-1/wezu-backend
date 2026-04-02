from slowapi import Limiter
from fastapi import Request

from app.core.config import settings
from app.core.proxy import get_client_ip


def _rate_limit_key(request: Request) -> str:
    return get_client_ip(request)

import redis
import logging

logger = logging.getLogger(__name__)

def get_limiter_storage():
    """Attempt to connect to Redis, falback to memory if unavailable."""
    if not hasattr(settings, "REDIS_URL") or not settings.REDIS_URL:
        return "memory://"
        
    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        r.ping()
        return settings.REDIS_URL
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
        logger.warning("Redis is unavailable. Falling back to MemoryStorage for rate limiting.")
        return "memory://"

# Distributed rate limiting using Redis as storage (with memory fallback)
# This ensures rate limits are shared across multiple API instances in production
limiter = Limiter(
    key_func=_rate_limit_key,
    storage_uri=get_limiter_storage(),
    enabled=(settings.ENVIRONMENT != "test")
)

# Can serve as dependency or direct import
def limit(limit_value: str):
    return limiter.limit(limit_value)
