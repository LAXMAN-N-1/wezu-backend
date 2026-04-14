from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response


# Paths whose GET responses can be cached by CDN/browser.
_CACHEABLE_PREFIXES = (
    "/live",
    "/api/v1/stations/map",
    "/api/v1/stations/heatmap",
    "/api/v1/faqs",
    "/api/v1/i18n",
    "/api/v1/catalog",
    "/api/v1/locations",
)


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' https://fastapi.tiangolo.com data:;"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Apply Cache-Control on safe GET responses for cacheable endpoints.
        if request.method == "GET" and "Cache-Control" not in response.headers:
            path = request.url.path
            if path.startswith(_CACHEABLE_PREFIXES):
                response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=30"
            else:
                response.headers["Cache-Control"] = "no-store"

        return response
