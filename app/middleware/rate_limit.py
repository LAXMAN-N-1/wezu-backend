from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

from app.core.config import settings

# Distributed rate limiting using Redis as storage
# This ensures rate limits are shared across multiple API instances in production
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    enabled=(settings.ENVIRONMENT != "test")
)

# Can serve as dependency or direct import
def limit(limit_value: str):
    return limiter.limit(limit_value)
