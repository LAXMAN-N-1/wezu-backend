from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import json
import logging
import random
import time
from typing import Any, Callable, Optional
from uuid import uuid4

from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)


@dataclass
class CacheComputeResult:
    payload: Any
    source: str
    lock_backend_checked: bool
    stale_served: bool


class DistributedCacheService:
    """Redis-backed cache helper with anti-stampede and stale-if-error fallback."""

    @staticmethod
    def build_key(namespace: str, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        digest = sha1(raw.encode("utf-8")).hexdigest()[:20]
        return f"{namespace}:{digest}"

    @staticmethod
    def _decode(raw: Any, *, decoder: Optional[Callable[[Any], Any]]) -> Any | None:
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            if decoder:
                return decoder(parsed)
            return parsed
        except Exception:
            logger.warning("cache.decode_failed", exc_info=True)
            return None

    @staticmethod
    def get_json(cache_key: str, *, decoder: Optional[Callable[[Any], Any]] = None) -> Any | None:
        client = RedisService.get_client()
        if client is None:
            return None
        try:
            return DistributedCacheService._decode(client.get(cache_key), decoder=decoder)
        except Exception:
            logger.exception("Cache read failed key=%s", cache_key)
            return None

    @staticmethod
    def set_json(
        cache_key: str,
        payload: Any,
        *,
        ttl_seconds: int,
        encoder: Optional[Callable[[Any], Any]] = None,
        ttl_jitter_seconds: int = 0,
    ) -> None:
        client = RedisService.get_client()
        if client is None:
            return
        try:
            encoded = encoder(payload) if encoder else payload
            ttl = max(1, int(ttl_seconds))
            if ttl_jitter_seconds > 0:
                ttl += random.randint(0, max(0, int(ttl_jitter_seconds)))
            client.setex(
                cache_key,
                ttl,
                json.dumps(encoded, ensure_ascii=False, separators=(",", ":")),
            )
        except Exception:
            logger.exception("Cache write failed key=%s", cache_key)

    @staticmethod
    def _acquire_lock(
        cache_key: str,
        *,
        lock_ttl_seconds: int,
    ) -> tuple[str | None, bool]:
        client = RedisService.get_client()
        if client is None:
            return None, False
        token = uuid4().hex
        lock_key = f"{cache_key}:lock"
        try:
            acquired = client.set(lock_key, token, ex=max(1, int(lock_ttl_seconds)), nx=True)
            return (token if acquired else None), True
        except Exception:
            logger.exception("Cache lock acquire failed key=%s", cache_key)
            return None, False

    @staticmethod
    def _release_lock(cache_key: str, token: str) -> None:
        client = RedisService.get_client()
        if client is None:
            return
        lock_key = f"{cache_key}:lock"
        script = (
            "if redis.call('get', KEYS[1]) == ARGV[1] "
            "then return redis.call('del', KEYS[1]) "
            "else return 0 end"
        )
        try:
            client.eval(script, 1, lock_key, token)
        except Exception:
            logger.exception("Cache lock release failed key=%s", cache_key)

    @staticmethod
    def _stale_key(cache_key: str) -> str:
        return f"{cache_key}:stale"

    @staticmethod
    def get_or_compute_json(
        *,
        cache_key: str,
        ttl_seconds: int,
        compute: Callable[[], Any],
        lock_ttl_seconds: int,
        lock_wait_ms: int,
        lock_poll_ms: int,
        ttl_jitter_seconds: int,
        stale_ttl_seconds: int,
        allow_stale_on_error: bool,
        encoder: Optional[Callable[[Any], Any]] = None,
        decoder: Optional[Callable[[Any], Any]] = None,
        log_label: str,
    ) -> CacheComputeResult:
        cached = DistributedCacheService.get_json(cache_key, decoder=decoder)
        if cached is not None:
            logger.debug("cache.hit label=%s key=%s", log_label, cache_key)
            return CacheComputeResult(
                payload=cached,
                source="hit",
                lock_backend_checked=False,
                stale_served=False,
            )

        lock_token: str | None = None
        lock_checked = False
        waited_ms = 0
        try:
            lock_token, lock_checked = DistributedCacheService._acquire_lock(
                cache_key,
                lock_ttl_seconds=lock_ttl_seconds,
            )

            if lock_checked and lock_token is None:
                poll_ms = max(10, int(lock_poll_ms))
                budget_ms = max(0, int(lock_wait_ms))
                while waited_ms < budget_ms:
                    time.sleep(poll_ms / 1000)
                    waited_ms += poll_ms
                    cached_retry = DistributedCacheService.get_json(cache_key, decoder=decoder)
                    if cached_retry is not None:
                        logger.debug(
                            "cache.wait_hit label=%s key=%s waited_ms=%s",
                            log_label,
                            cache_key,
                            waited_ms,
                        )
                        return CacheComputeResult(
                            payload=cached_retry,
                            source="wait_hit",
                            lock_backend_checked=True,
                            stale_served=False,
                        )

            try:
                payload = compute()
            except Exception:
                if allow_stale_on_error and stale_ttl_seconds > 0:
                    stale_payload = DistributedCacheService.get_json(
                        DistributedCacheService._stale_key(cache_key),
                        decoder=decoder,
                    )
                    if stale_payload is not None:
                        logger.warning(
                            "cache.stale_on_error label=%s key=%s waited_ms=%s",
                            log_label,
                            cache_key,
                            waited_ms,
                        )
                        return CacheComputeResult(
                            payload=stale_payload,
                            source="stale",
                            lock_backend_checked=lock_checked,
                            stale_served=True,
                        )
                raise

            DistributedCacheService.set_json(
                cache_key,
                payload,
                ttl_seconds=ttl_seconds,
                encoder=encoder,
                ttl_jitter_seconds=ttl_jitter_seconds,
            )
            if stale_ttl_seconds > 0:
                DistributedCacheService.set_json(
                    DistributedCacheService._stale_key(cache_key),
                    payload,
                    ttl_seconds=stale_ttl_seconds,
                    encoder=encoder,
                    ttl_jitter_seconds=min(ttl_jitter_seconds, 5),
                )
            source = "compute" if lock_token is not None else "compute_no_lock"
            logger.debug(
                "cache.%s label=%s key=%s waited_ms=%s",
                source,
                log_label,
                cache_key,
                waited_ms,
            )
            return CacheComputeResult(
                payload=payload,
                source=source,
                lock_backend_checked=lock_checked,
                stale_served=False,
            )
        finally:
            if lock_token is not None:
                DistributedCacheService._release_lock(cache_key, lock_token)
