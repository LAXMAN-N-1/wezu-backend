from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio
import json
import logging
from typing import Any, Optional
from uuid import uuid4

from app.core.config import settings
from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)


@dataclass
class BackgroundRuntimeDecision:
    mode: str
    run_scheduler: bool
    run_outbox_dispatch: bool
    leader_acquired: bool
    lock_backend_checked: bool
    lock_backend_available: bool
    dedicated_scheduler_alive: bool
    reason: str


class BackgroundRuntimeService:
    _leader_token: str | None = None
    _leader_renew_task: Optional[asyncio.Task] = None
    _state: dict[str, Any] = {
        "mode": "auto",
        "run_scheduler": False,
        "run_outbox_dispatch": False,
        "leader_acquired": False,
        "lock_backend_checked": False,
        "lock_backend_available": False,
        "dedicated_scheduler_alive": False,
        "reason": "not_initialized",
        "lock_key": "",
        "lock_ttl_seconds": 0,
    }

    @classmethod
    def _normalized_mode(cls) -> str:
        raw = str(getattr(settings, "BACKGROUND_RUNTIME_MODE", "auto") or "auto").strip().lower()
        if raw not in {"auto", "api_only", "workers_only"}:
            return "auto"
        return raw

    @classmethod
    def _lock_key(cls) -> str:
        return str(
            getattr(
                settings,
                "BACKGROUND_RUNTIME_LEADER_LOCK_KEY",
                "wezu:background:runtime:leader",
            )
        )

    @classmethod
    def _lock_ttl_seconds(cls) -> int:
        raw = int(getattr(settings, "BACKGROUND_RUNTIME_LEADER_LOCK_TTL_SECONDS", 30) or 30)
        return max(10, min(120, raw))

    @classmethod
    def _lock_required_when_unavailable(cls) -> bool:
        return bool(getattr(settings, "BACKGROUND_RUNTIME_LOCK_REQUIRED", True))

    @classmethod
    def _scheduler_heartbeat_alive(cls) -> bool:
        client = RedisService.get_client()
        if client is None:
            return False
        key = str(getattr(settings, "SCHEDULER_HEARTBEAT_KEY", "wezu:scheduler:heartbeat"))
        ttl_seconds = max(5, int(getattr(settings, "SCHEDULER_HEARTBEAT_TTL_SECONDS", 30) or 30))
        try:
            raw = client.get(key)
            if not raw:
                return False
            payload = json.loads(raw)
            ts_raw = payload.get("timestamp") if isinstance(payload, dict) else None
            if not ts_raw:
                return False
            parsed = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
            return age <= ttl_seconds
        except Exception:
            return False

    @classmethod
    def _acquire_leader_lock(cls) -> tuple[str | None, bool]:
        client = RedisService.get_client()
        if client is None:
            return None, False
        token = uuid4().hex
        try:
            acquired = client.set(
                cls._lock_key(),
                token,
                ex=cls._lock_ttl_seconds(),
                nx=True,
            )
            return (token if acquired else None), True
        except Exception:
            logger.exception("Background runtime leader lock acquire failed")
            return None, False

    @classmethod
    async def _renew_leader_loop(cls, token: str) -> None:
        lock_key = cls._lock_key()
        ttl_seconds = cls._lock_ttl_seconds()
        refresh_sleep_seconds = max(3, ttl_seconds // 3)
        script = (
            "if redis.call('get', KEYS[1]) == ARGV[1] "
            "then return redis.call('expire', KEYS[1], ARGV[2]) "
            "else return 0 end"
        )

        while True:
            await asyncio.sleep(refresh_sleep_seconds)
            client = RedisService.get_client()
            if client is None:
                logger.warning("Background runtime lock renew skipped: redis unavailable")
                continue
            try:
                refreshed = client.eval(script, 1, lock_key, token, int(ttl_seconds))
                if int(refreshed or 0) != 1:
                    logger.warning("Background runtime lock no longer owned; embedded background work may migrate")
                    return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Background runtime lock renew failed")

    @classmethod
    async def initialize(cls) -> BackgroundRuntimeDecision:
        mode = cls._normalized_mode()
        dedicated_scheduler_alive = cls._scheduler_heartbeat_alive()

        desired_scheduler = bool(getattr(settings, "RUN_SCHEDULER_IN_API", True))
        desired_outbox = bool(getattr(settings, "ORDER_REALTIME_OUTBOX_ENABLED", True))

        if mode == "workers_only":
            desired_scheduler = False
            desired_outbox = False
        elif mode == "auto":
            if dedicated_scheduler_alive:
                desired_scheduler = False

        needs_embedded_leader = desired_scheduler or desired_outbox

        leader_acquired = False
        lock_checked = False
        lock_available = False
        reason = ""

        if needs_embedded_leader:
            token, lock_checked = cls._acquire_leader_lock()
            lock_available = lock_checked
            if token:
                leader_acquired = True
                cls._leader_token = token
                cls._leader_renew_task = asyncio.create_task(cls._renew_leader_loop(token))
                reason = "embedded_leader_acquired"
            elif lock_checked:
                reason = "embedded_leader_already_held"
            else:
                if cls._lock_required_when_unavailable():
                    desired_scheduler = False
                    desired_outbox = False
                    reason = "redis_lock_backend_unavailable_embedded_disabled"
                else:
                    leader_acquired = True
                    reason = "redis_lock_backend_unavailable_fallback_local"
        else:
            reason = "embedded_background_not_required"

        if needs_embedded_leader and not leader_acquired and lock_checked:
            desired_scheduler = False
            desired_outbox = False

        decision = BackgroundRuntimeDecision(
            mode=mode,
            run_scheduler=bool(desired_scheduler),
            run_outbox_dispatch=bool(desired_outbox),
            leader_acquired=leader_acquired,
            lock_backend_checked=lock_checked,
            lock_backend_available=lock_available,
            dedicated_scheduler_alive=dedicated_scheduler_alive,
            reason=reason,
        )

        cls._state = {
            "mode": decision.mode,
            "run_scheduler": decision.run_scheduler,
            "run_outbox_dispatch": decision.run_outbox_dispatch,
            "leader_acquired": decision.leader_acquired,
            "lock_backend_checked": decision.lock_backend_checked,
            "lock_backend_available": decision.lock_backend_available,
            "dedicated_scheduler_alive": decision.dedicated_scheduler_alive,
            "reason": decision.reason,
            "lock_key": cls._lock_key(),
            "lock_ttl_seconds": cls._lock_ttl_seconds(),
        }

        logger.info(
            "Background runtime decision mode=%s run_scheduler=%s run_outbox_dispatch=%s "
            "leader_acquired=%s lock_backend_available=%s dedicated_scheduler_alive=%s reason=%s",
            decision.mode,
            decision.run_scheduler,
            decision.run_outbox_dispatch,
            decision.leader_acquired,
            decision.lock_backend_available,
            decision.dedicated_scheduler_alive,
            decision.reason,
        )
        return decision

    @classmethod
    def state(cls) -> dict[str, Any]:
        return dict(cls._state)

    @classmethod
    async def shutdown(cls) -> None:
        renew_task = cls._leader_renew_task
        cls._leader_renew_task = None
        if renew_task is not None:
            renew_task.cancel()
            try:
                await renew_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Background runtime lock renew task shutdown failed")

        token = cls._leader_token
        cls._leader_token = None
        if not token:
            return

        client = RedisService.get_client()
        if client is None:
            return

        script = (
            "if redis.call('get', KEYS[1]) == ARGV[1] "
            "then return redis.call('del', KEYS[1]) "
            "else return 0 end"
        )
        try:
            client.eval(script, 1, cls._lock_key(), token)
        except Exception:
            logger.exception("Background runtime lock release failed")
