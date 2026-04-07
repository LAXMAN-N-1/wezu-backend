from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger
from app.core.proxy import get_client_ip

logger = get_logger(__name__)

_HEALTH_PATHS = frozenset({"/health", "/live", "/ready", "/healthz", "/livez", "/readyz"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = perf_counter()
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        correlation_id = request.headers.get("X-Correlation-ID") or request_id
        client_ip = get_client_ip(request)

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request.state.client_ip = client_ip

        # Skip heavy structlog context binding for healthcheck probes
        is_health = request.url.path in _HEALTH_PATHS

        if not is_health:
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(
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
            if not is_health:
                logger.exception(
                    "request.failed",
                    duration_ms=duration_ms,
                    query_keys=sorted(request.query_params.keys()),
                    auth_error=getattr(request.state, "auth_error", None),
                    user_id=getattr(getattr(request.state, "user", None), "id", None),
                )
                structlog.contextvars.clear_contextvars()
            raise

        duration_ms = round((perf_counter() - start) * 1000, 2)
        response.headers.setdefault("X-Request-ID", request_id)
        response.headers.setdefault("X-Correlation-ID", correlation_id)

        # Skip logging for healthcheck probes entirely
        if is_health:
            return response

        user_id = (
            getattr(getattr(request.state, "user", None), "id", None)
            or getattr(request.state, "user_id", None)
            or getattr(request.state, "token_user_id", None)
        )
        auth_error = getattr(request.state, "auth_error", None)

        if settings.LOG_REQUESTS:
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
                query_keys=sorted(request.query_params.keys()),
            )

        structlog.contextvars.clear_contextvars()
        return response
