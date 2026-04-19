from __future__ import annotations
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import bind_contextvars, clear_contextvars, get_logger
from app.core.proxy import get_client_ip

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = perf_counter()
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        correlation_id = request.headers.get("X-Correlation-ID") or request_id
        client_ip = get_client_ip(request)

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request.state.client_ip = client_ip

        clear_contextvars()
        bind_contextvars(
            request_id=request_id,
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
        )

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((perf_counter() - start) * 1000, 2)
            logger.exception(
                "request.failed",
                duration_ms=duration_ms,
                query_keys=sorted(request.query_params.keys()),
                auth_error=getattr(request.state, "auth_error", None),
                user_id=getattr(getattr(request.state, "user", None), "id", None),
            )
            clear_contextvars()
            raise

        duration_ms = round((perf_counter() - start) * 1000, 2)
        response.headers.setdefault("X-Request-ID", request_id)
        response.headers.setdefault("X-Correlation-ID", correlation_id)

        user_id = getattr(getattr(request.state, "user", None), "id", None) or getattr(
            request.state, "user_id", None
        )
        auth_error = getattr(request.state, "auth_error", None)
        route = request.scope.get("route")
        route_name = getattr(route, "name", None)
        excluded_paths = set(settings.LOG_EXCLUDE_PATHS or [])
        should_log = settings.LOG_REQUESTS and (
            settings.LOG_HEALTHCHECKS or request.url.path not in excluded_paths
        )

        if should_log:
            log_fn = logger.info
            event_name = "request.completed"
            if response.status_code >= 500:
                log_fn = logger.error
            elif duration_ms >= settings.LOG_SLOW_REQUEST_THRESHOLD_MS:
                log_fn = logger.warning
                event_name = "request.slow"
            elif response.status_code >= 400:
                log_fn = logger.warning
            log_fn(
                event_name,
                status_code=response.status_code,
                duration_ms=duration_ms,
                user_id=user_id,
                auth_error=auth_error,
                route_name=route_name,
                query_keys=sorted(request.query_params.keys()),
            )

        clear_contextvars()
        return response
