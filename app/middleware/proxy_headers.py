from __future__ import annotations
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.proxy import get_client_ip, get_forwarded_host, rewrite_host_header


class TrustedProxyHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Cache trusted client IP for downstream security/rate-limit code paths.
        request.state.client_ip = get_client_ip(request)

        forwarded_host = get_forwarded_host(request)
        if forwarded_host:
            rewrite_host_header(request.scope, forwarded_host)

        return await call_next(request)

