from __future__ import annotations

from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp


def _merge_server_timing(existing_header: str | None, metric: str) -> str:
    if existing_header:
        return f"{existing_header}, {metric}"
    return metric


class ServerTimingMiddleware(BaseHTTPMiddleware):
    """
    Adds RFC-compliant Server-Timing header for browser waterfall diagnostics.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        start = perf_counter()
        response = await call_next(request)
        duration_ms = (perf_counter() - start) * 1000.0
        metric = f'app;dur={duration_ms:.2f};desc="app_total"'
        response.headers["Server-Timing"] = _merge_server_timing(
            response.headers.get("Server-Timing"),
            metric,
        )
        return response

