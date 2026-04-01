"""
Shared CORS utilities used by middleware and error handlers.
Single source of truth to avoid duplication.
"""
import json
from app.core.config import settings


def normalized_cors_origins() -> list[str]:
    """Parse and normalize CORS_ORIGINS from settings."""
    allowed_origins = settings.CORS_ORIGINS
    if isinstance(allowed_origins, str):
        try:
            parsed = json.loads(allowed_origins)
            if isinstance(parsed, list):
                allowed_origins = parsed
            else:
                allowed_origins = [allowed_origins]
        except Exception:
            allowed_origins = [allowed_origins]
    return [origin.rstrip("/") for origin in (allowed_origins or [])]


def cors_headers_for_origin(origin: str) -> dict[str, str]:
    """Return CORS headers if the origin is allowed, else empty dict."""
    if not origin:
        return {}
    allowed_origins = normalized_cors_origins()
    normalized_origin = origin.rstrip("/")
    if "*" in allowed_origins or normalized_origin in allowed_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}
