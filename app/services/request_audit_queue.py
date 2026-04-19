from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone; UTC = timezone.utc
from typing import Any, Dict, Optional

from sqlmodel import Session

from app.core.config import settings
from app.core.database import engine
from app.core.logging import sanitize_for_logging
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class RequestAuditQueueService:
    """Bounded, batched, non-blocking request audit pipeline."""

    def __init__(
        self,
        maxsize: int,
        batch_size: int,
        flush_ms: int,
        drop_warn_every: int,
        workers: int,
    ) -> None:
        self._queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue(
            maxsize=max(1, maxsize)
        )
        self._batch_size = max(1, batch_size)
        self._flush_seconds = max(0.01, flush_ms / 1000.0)
        self._drop_warn_every = max(1, drop_warn_every)
        self._workers = max(1, workers)

        self._running = False
        self._worker_tasks: list[asyncio.Task[None]] = []

        self._enqueued = 0
        self._dropped = 0
        self._flushed = 0
        self._flush_errors = 0

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_tasks = [
            asyncio.create_task(self._worker_loop(), name=f"request-audit-{idx}")
            for idx in range(self._workers)
        ]
        logger.info(
            "Request audit queue started (workers=%s maxsize=%s batch=%s flush_ms=%s)",
            self._workers,
            self._queue.maxsize,
            self._batch_size,
            int(self._flush_seconds * 1000),
        )

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        for _ in range(self._workers):
            await self._queue.put(None)

        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
            self._worker_tasks = []

        logger.info(
            "Request audit queue stopped (enqueued=%s dropped=%s flushed=%s errors=%s)",
            self._enqueued,
            self._dropped,
            self._flushed,
            self._flush_errors,
        )

    def enqueue(
        self,
        *,
        user_id: Optional[int],
        action: str,
        resource_type: str,
        resource_id: str,
        details: str,
        metadata: Dict[str, Any],
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> bool:
        """Best-effort enqueue. Never blocks and never raises."""
        if not self._running:
            return False

        event = {
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id)[:255],
            "details": str(details)[:512],
            "meta_data": sanitize_for_logging(metadata),
            "ip_address": ip_address,
            "user_agent": str(user_agent or "")[:512] if user_agent else None,
            "timestamp": datetime.now(UTC),
        }

        try:
            self._queue.put_nowait(event)
            self._enqueued += 1
            return True
        except asyncio.QueueFull:
            self._dropped += 1
            if self._dropped % self._drop_warn_every == 0:
                logger.warning(
                    "Request audit queue full; dropped=%s enqueued=%s maxsize=%s",
                    self._dropped,
                    self._enqueued,
                    self._queue.maxsize,
                )
            return False

    def stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "workers": self._workers,
            "queue_size": self._queue.qsize(),
            "queue_maxsize": self._queue.maxsize,
            "enqueued": self._enqueued,
            "dropped": self._dropped,
            "flushed": self._flushed,
            "flush_errors": self._flush_errors,
        }

    async def _worker_loop(self) -> None:
        pending_batch: list[Dict[str, Any]] = []
        stop_requested = False

        while not stop_requested:
            item = await self._queue.get()
            self._queue.task_done()

            if item is None:
                stop_requested = True
            else:
                pending_batch.append(item)

            deadline = asyncio.get_running_loop().time() + self._flush_seconds

            while len(pending_batch) < self._batch_size and not stop_requested:
                timeout = max(0.0, deadline - asyncio.get_running_loop().time())
                if timeout <= 0:
                    break
                try:
                    next_item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    break

                self._queue.task_done()
                if next_item is None:
                    stop_requested = True
                    break
                pending_batch.append(next_item)

            if pending_batch:
                await self._flush_batch(pending_batch)
                pending_batch = []

    async def _flush_batch(self, batch: list[Dict[str, Any]]) -> None:
        db: Optional[Session] = None
        try:
            with Session(engine) as db:
                logs = [AuditLog(**event) for event in batch]
                db.add_all(logs)
                db.commit()
            self._flushed += len(batch)
        except Exception as exc:  # pragma: no cover - defensive path
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    # Defensive rollback path; avoid surfacing secondary errors.
                    pass
            self._flush_errors += 1
            logger.error("Failed request-audit batch flush: %s", exc)


request_audit_queue = RequestAuditQueueService(
    maxsize=settings.AUDIT_REQUEST_QUEUE_MAXSIZE,
    batch_size=settings.AUDIT_REQUEST_BATCH_SIZE,
    flush_ms=settings.AUDIT_REQUEST_FLUSH_MS,
    drop_warn_every=settings.AUDIT_REQUEST_DROP_WARN_EVERY,
    workers=settings.AUDIT_REQUEST_WORKERS,
)
