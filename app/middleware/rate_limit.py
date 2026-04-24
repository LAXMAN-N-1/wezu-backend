from __future__ import annotations

import logging

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.proxy import extract_forwarded_client_ip
from app.utils.endpoint_signature import preserve_endpoint_signature

logger = logging.getLogger(__name__)


def _get_rate_limit_key(request: Request) -> str:
    source_ip = request.client.host if request.client else None
    client_ip = extract_forwarded_client_ip(
        source_ip,
        request.headers.get("x-forwarded-for"),
        request.headers.get("forwarded"),
        request.headers.get("x-real-ip"),
    )
    return client_ip or get_remote_address(request)


def _resolve_rate_limit_storage_url() -> str:
    explicit_url = (settings.RATE_LIMIT_STORAGE_URL or "").strip()
    if explicit_url:
        return explicit_url

    # Reuse Redis as the distributed limiter backend by default in production-safe deployments.
    redis_url = (settings.REDIS_URL or "").strip()
    if redis_url:
        return redis_url

    return "memory://"


try:
    limiter = Limiter(key_func=_get_rate_limit_key, storage_uri=_resolve_rate_limit_storage_url())
except Exception as exc:
    logger.warning("Failed to initialize distributed rate limiter backend; falling back to in-memory: %s", exc)
    limiter = Limiter(key_func=_get_rate_limit_key, storage_uri="memory://")

_base_limit_decorator_factory = limiter.limit


def _limit_with_preserved_signature(limit_value: str):
    base_decorator = _base_limit_decorator_factory(limit_value)

    def decorator(func):
        wrapped = base_decorator(func)
        return preserve_endpoint_signature(wrapped, func)

    return decorator


limiter.limit = _limit_with_preserved_signature  # type: ignore[assignment]

# Can serve as dependency or direct import
def limit(limit_value: str):
    return limiter.limit(limit_value)
