from __future__ import annotations
import ipaddress
import re
from functools import lru_cache
from typing import Optional

from fastapi import Request

from app.core.config import settings

HOST_TOKEN_RE = re.compile(r"^[A-Za-z0-9.\-]+$")


@lru_cache(maxsize=1)
def _trusted_proxy_networks() -> tuple[ipaddress._BaseNetwork, ...]:
    networks: list[ipaddress._BaseNetwork] = []
    for value in settings.FORWARDED_ALLOW_IPS:
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            continue
    return tuple(networks)


def _parse_ip(candidate: Optional[str]) -> Optional[str]:
    if not candidate:
        return None
    raw = candidate.strip().strip('"')
    if not raw:
        return None
    if raw.lower() == "unknown" or raw.startswith("_"):
        return None

    # RFC7239 format: for="[2001:db8:cafe::17]:4711"
    if raw.startswith("["):
        end = raw.find("]")
        if end == -1:
            return None
        raw = raw[1:end]
    elif raw.count(":") == 1 and "." in raw.split(":", 1)[0]:
        # IPv4 with port: 203.0.113.5:12345
        raw = raw.split(":", 1)[0]

    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


def _source_ip(request: Request) -> Optional[str]:
    client = request.client
    if not client:
        return None
    return _parse_ip(client.host)


def _is_trusted_proxy_source(request: Request) -> bool:
    source_ip = _source_ip(request)
    if not source_ip:
        return False
    source_addr = ipaddress.ip_address(source_ip)
    return any(source_addr in network for network in _trusted_proxy_networks())


def _first_x_forwarded_for_ip(request: Request) -> Optional[str]:
    value = request.headers.get("x-forwarded-for")
    if not value:
        return None
    for part in value.split(","):
        parsed = _parse_ip(part)
        if parsed:
            return parsed
    return None


def _first_forwarded_for_ip(request: Request) -> Optional[str]:
    value = request.headers.get("forwarded")
    if not value:
        return None
    for element in value.split(","):
        for token in element.split(";"):
            if "=" not in token:
                continue
            key, raw = token.split("=", 1)
            if key.strip().lower() != "for":
                continue
            parsed = _parse_ip(raw)
            if parsed:
                return parsed
    return None


def _x_real_ip(request: Request) -> Optional[str]:
    return _parse_ip(request.headers.get("x-real-ip"))


def get_client_ip(request: Request) -> str:
    cached = getattr(request.state, "client_ip", None)
    if cached:
        return cached

    source_ip = _source_ip(request) or "unknown"
    if not _is_trusted_proxy_source(request):
        request.state.client_ip = source_ip
        return source_ip

    trusted_forwarded_ip = (
        _first_x_forwarded_for_ip(request)
        or _first_forwarded_for_ip(request)
        or _x_real_ip(request)
        or source_ip
    )
    request.state.client_ip = trusted_forwarded_ip
    return trusted_forwarded_ip


def _normalize_host(candidate: str) -> Optional[str]:
    host = candidate.strip().strip('"').split(",", 1)[0].strip()
    if not host or " " in host or "/" in host:
        return None

    if "://" in host:
        return None

    # IPv6 host in brackets with optional port.
    if host.startswith("["):
        end = host.find("]")
        if end == -1:
            return None
        ip_part = host[1:end]
        try:
            ipaddress.ip_address(ip_part)
        except ValueError:
            return None
        suffix = host[end + 1 :]
        if suffix and (not suffix.startswith(":") or not suffix[1:].isdigit()):
            return None
        return host

    host_part = host
    if ":" in host and host.count(":") == 1:
        host_part, port = host.rsplit(":", 1)
        if not port.isdigit():
            return None

    if not host_part:
        return None

    try:
        ipaddress.ip_address(host_part)
    except ValueError:
        labels = host_part.split(".")
        if any(
            (not label)
            or label.startswith("-")
            or label.endswith("-")
            or not HOST_TOKEN_RE.match(label)
            for label in labels
        ):
            return None

    return host.lower()


def get_forwarded_host(request: Request) -> Optional[str]:
    if not settings.TRUST_X_FORWARDED_HOST or not _is_trusted_proxy_source(request):
        return None

    x_forwarded_host = request.headers.get("x-forwarded-host")
    if x_forwarded_host:
        normalized = _normalize_host(x_forwarded_host)
        if normalized:
            return normalized

    forwarded = request.headers.get("forwarded")
    if not forwarded:
        return None

    for element in forwarded.split(","):
        for token in element.split(";"):
            if "=" not in token:
                continue
            key, raw = token.split("=", 1)
            if key.strip().lower() != "host":
                continue
            normalized = _normalize_host(raw)
            if normalized:
                return normalized
    return None


def rewrite_host_header(scope: dict, host: str) -> None:
    encoded = host.encode("latin-1")
    headers = [
        (key, value)
        for key, value in scope.get("headers", [])
        if key.lower() != b"host"
    ]
    headers.append((b"host", encoded))
    scope["headers"] = headers


# ── Standalone helpers (used by hardened middleware / passkeys) ─────────────

_FORWARDED_FOR_PATTERN = re.compile(
    r"""for\s*=\s*["']?(?P<value>[^"',;\s]+)""", re.IGNORECASE
)


def is_trusted_proxy(source_ip: str | None) -> bool:
    """Check if a raw IP string belongs to a trusted proxy network."""
    if not source_ip:
        return False
    try:
        source_addr = ipaddress.ip_address(source_ip)
    except ValueError:
        return False
    return any(source_addr in network for network in _trusted_proxy_networks())


def _extract_valid_ip(candidates: list[str]) -> str | None:
    for raw in candidates:
        client_ip = raw.strip().strip('"').strip("'")
        if not client_ip:
            continue
        if client_ip.startswith("[") and "]" in client_ip:
            client_ip = client_ip[1 : client_ip.index("]")]
        elif client_ip.count(":") == 1 and "." in client_ip:
            client_ip = client_ip.split(":", 1)[0]
        try:
            ipaddress.ip_address(client_ip)
        except ValueError:
            continue
        return client_ip
    return None


def _extract_from_forwarded_header(forwarded: str | None) -> str | None:
    if not forwarded:
        return None
    for hop in forwarded.split(","):
        match = _FORWARDED_FOR_PATTERN.search(hop)
        if not match:
            continue
        parsed = _extract_valid_ip([match.group("value")])
        if parsed:
            return parsed
    return None


def extract_forwarded_client_ip(
    source_ip: str | None,
    forwarded_for: str | None,
    forwarded: str | None = None,
    x_real_ip: str | None = None,
) -> str | None:
    """
    Resolve the real client IP from proxy headers.
    Returns the source_ip if the source is not a trusted proxy.
    """
    if not is_trusted_proxy(source_ip):
        return source_ip

    from_xff = _extract_valid_ip((forwarded_for or "").split(","))
    if from_xff:
        return from_xff

    from_forwarded = _extract_from_forwarded_header(forwarded)
    if from_forwarded:
        return from_forwarded

    from_real_ip = _extract_valid_ip([x_real_ip or ""])
    if from_real_ip:
        return from_real_ip

    return source_ip

