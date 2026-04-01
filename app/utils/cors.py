"""
Shared CORS utilities used by middleware and error handlers.
Single source of truth to avoid duplication.
"""
from app.core.config import settings


def normalized_cors_origins() -> list[str]:
    """Normalize configured CORS origins (no trailing slash)."""
    return [origin.rstrip("/") for origin in (settings.CORS_ORIGINS or []) if origin]


def cors_headers_for_origin(origin: str) -> dict[str, str]:
    """Return CORS headers if the origin is allowed, else empty dict."""
    if not origin:
        return {}
    if settings.is_origin_allowed(origin):
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}
