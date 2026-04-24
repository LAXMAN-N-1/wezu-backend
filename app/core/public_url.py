from __future__ import annotations

from typing import Optional

from app.core.config import settings


def get_public_api_base_url() -> Optional[str]:
    """
    Resolve the canonical public base URL for API-served assets.

    Priority:
    1) API_PUBLIC_BASE_URL (explicit backend/public API origin)
    2) MEDIA_BASE_URL (backward-compatible fallback)
    """
    for candidate in (settings.API_PUBLIC_BASE_URL, settings.MEDIA_BASE_URL):
        value = (candidate or "").strip()
        if not value:
            continue
        if value.startswith(("http://", "https://")):
            return value.rstrip("/")
    return None


def to_public_url(raw_path_or_url: str) -> str:
    value = (raw_path_or_url or "").strip()
    if not value:
        return value

    lowered = value.lower()
    if lowered.startswith(("http://", "https://")):
        return value

    if value.startswith("uploads/"):
        value = f"/{value}"

    base_url = get_public_api_base_url()
    if not base_url:
        return value

    if value.startswith("/"):
        return f"{base_url}{value}"
    return f"{base_url}/{value.lstrip('/')}"
