from slowapi import Limiter
from fastapi import Request

from app.core.config import settings
from app.core.proxy import get_client_ip


def _rate_limit_key(request: Request) -> str:
    return get_client_ip(request)

# Distributed rate limiting using Redis as storage
# Use memory fallback for local development if Redis is not reachable
storage_uri = settings.REDIS_URL if settings.ENVIRONMENT == "production" else "memory://"

limiter = Limiter(
<<<<<<< HEAD
    key_func=get_remote_address,
    storage_uri=storage_uri,
=======
    key_func=_rate_limit_key,
    storage_uri=settings.REDIS_URL,
>>>>>>> origin/main
    enabled=(settings.ENVIRONMENT != "test")
)

# Can serve as dependency or direct import
def limit(limit_value: str):
    return limiter.limit(limit_value)
