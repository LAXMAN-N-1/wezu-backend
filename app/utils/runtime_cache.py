from dataclasses import dataclass, field
from threading import Event, Lock
from time import monotonic
from typing import Any, Callable, Hashable, Optional


@dataclass
class _InFlightCall:
    event: Event = field(default_factory=Event)
    result: Any = None
    failed: bool = False


_runtime_cache: dict[tuple[Hashable, ...], tuple[float, Any]] = {}
_runtime_cache_lock = Lock()
_runtime_inflight: dict[tuple[Hashable, ...], _InFlightCall] = {}


def _prune_expired(now: float) -> None:
    expired_keys = [
        key for key, (expires_at, _) in _runtime_cache.items()
        if expires_at <= now
    ]
    for key in expired_keys:
        _runtime_cache.pop(key, None)


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
