from dataclasses import dataclass, field
import json
import logging
from threading import Event, Lock
from time import monotonic
from typing import Any, Callable, Hashable, Optional
from urllib.parse import quote

from app.core.config import settings

try:
    import redis
except Exception:  # pragma: no cover - import safety only
    redis = None


@dataclass
class _InFlightCall:
    event: Event = field(default_factory=Event)
    result: Any = None
    failed: bool = False


_runtime_cache: dict[tuple[Hashable, ...], tuple[float, Any]] = {}
_runtime_cache_lock = Lock()
_runtime_inflight: dict[tuple[Hashable, ...], _InFlightCall] = {}
_redis_client = None
_redis_lock = Lock()
logger = logging.getLogger(__name__)


def _prune_expired(now: float) -> None:
    expired_keys = [
        key for key, (expires_at, _) in _runtime_cache.items()
        if expires_at <= now
    ]
    for key in expired_keys:
        _runtime_cache.pop(key, None)


def _redis_key(*parts: Hashable) -> str:
    encoded = [quote(str(part), safe="") for part in parts]
    return "runtime-cache:" + ":".join(encoded)


def _get_redis_client():
    global _redis_client

    if redis is None or not settings.REDIS_URL:
        return None

    if _redis_client is not None:
        return _redis_client

    with _redis_lock:
        if _redis_client is None:
            try:
                _redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=0.2,
                    socket_timeout=0.2,
                    health_check_interval=30,
                )
            except Exception:
                logger.exception("runtime_cache.redis_init_failed")
                _redis_client = False

    return _redis_client if _redis_client is not False else None


def cached_call(
    namespace: str,
    *cache_parts: Hashable,
    ttl_seconds: int,
    call: Callable[[], Any],
) -> Any:
    if ttl_seconds <= 0:
        return call()

    cache_key = (namespace,) + tuple(cache_parts)
    is_leader = False
    inflight: Optional[_InFlightCall] = None
    now = monotonic()
    redis_key = _redis_key(*cache_key)

    with _runtime_cache_lock:
        cached = _runtime_cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

        _prune_expired(now)
        inflight = _runtime_inflight.get(cache_key)
        if inflight is None:
            inflight = _InFlightCall()
            _runtime_inflight[cache_key] = inflight
            is_leader = True

    redis_client = _get_redis_client()
    if redis_client is not None:
        try:
            payload = redis_client.get(redis_key)
            if payload is not None:
                result = json.loads(payload)
                with _runtime_cache_lock:
                    _runtime_cache[cache_key] = (monotonic() + ttl_seconds, result)
                    current = _runtime_inflight.pop(cache_key, None)
                    if current:
                        current.result = result
                        current.event.set()
                return result
        except Exception:
            logger.warning("runtime_cache.redis_read_failed", exc_info=True)

    if not is_leader:
        completed = inflight.event.wait(timeout=max(ttl_seconds, 30))
        if completed and not inflight.failed:
            return inflight.result
        return call()

    try:
        result = call()
    except Exception:
        with _runtime_cache_lock:
            current = _runtime_inflight.pop(cache_key, None)
            if current:
                current.failed = True
                current.event.set()
        raise

    with _runtime_cache_lock:
        _runtime_cache[cache_key] = (monotonic() + ttl_seconds, result)
        current = _runtime_inflight.pop(cache_key, None)
        if current:
            current.result = result
            current.event.set()

    if redis_client is not None:
        try:
            redis_client.setex(redis_key, ttl_seconds, json.dumps(result, default=str))
        except Exception:
            logger.warning("runtime_cache.redis_write_failed", exc_info=True)

    return result


def invalidate_cache(namespace: str, *prefix_parts: Hashable) -> None:
    prefix = (namespace,) + tuple(prefix_parts)
    with _runtime_cache_lock:
        cache_keys = [key for key in _runtime_cache if key[:len(prefix)] == prefix]
        for key in cache_keys:
            _runtime_cache.pop(key, None)

        inflight_keys = [key for key in _runtime_inflight if key[:len(prefix)] == prefix]
        for key in inflight_keys:
            current = _runtime_inflight.pop(key, None)
            if current:
                current.failed = True
                current.event.set()

    redis_client = _get_redis_client()
    if redis_client is not None:
        prefix = _redis_key(namespace, *prefix_parts)
        try:
            for redis_key in redis_client.scan_iter(match=f"{prefix}*"):
                redis_client.delete(redis_key)
        except Exception:
            logger.warning("runtime_cache.redis_invalidate_failed", exc_info=True)
