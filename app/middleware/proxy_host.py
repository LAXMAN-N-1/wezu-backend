from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.proxy import is_trusted_proxy


def _extract_forwarded_host(forwarded_header: str | None) -> str | None:
    if not forwarded_header:
        return None

    # RFC 7239 format example:
    # Forwarded: for=192.0.2.43;proto=https;host=example.com
    first_hop = forwarded_header.split(",", 1)[0].strip()
    if not first_hop:
        return None

    for part in first_hop.split(";"):
        key, sep, value = part.partition("=")
        if sep != "=":
            continue
        if key.strip().lower() != "host":
            continue
        host = value.strip().strip('"').strip("'")
        return host or None

    return None


def _normalize_forwarded_host(raw_host: str | None) -> str | None:
    if not raw_host:
        return None

    host = raw_host.split(",", 1)[0].strip()
    if not host:
        return None
    return host


class ProxyHostRewriteMiddleware(BaseHTTPMiddleware):
    """
    Rewrite Host from trusted proxy headers before TrustedHostMiddleware runs.

    Traefik commonly forwards the public host in X-Forwarded-Host while the
    upstream Host can be an internal service name depending on router settings.
    This middleware keeps strict host checks intact by only trusting forwarded
    host values when the immediate source IP is from a trusted proxy CIDR.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if settings.TRUST_X_FORWARDED_HOST:
            source_ip = request.client.host if request.client else None
            if is_trusted_proxy(source_ip):
                forwarded_host = _normalize_forwarded_host(
                    request.headers.get("x-forwarded-host")
                    or _extract_forwarded_host(request.headers.get("forwarded"))
                )
                if forwarded_host:
                    MutableHeaders(scope=request.scope)["host"] = forwarded_host

        return await call_next(request)
