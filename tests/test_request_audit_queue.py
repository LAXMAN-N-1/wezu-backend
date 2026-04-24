import asyncio

import pytest

from app.services.request_audit_queue import RequestAuditQueueService


def _event(idx: int) -> dict:
    return {
        "user_id": idx,
        "action": "GET",
        "resource_type": "api_request",
        "resource_id": f"/resource/{idx}",
        "details": "Status: success",
        "metadata": {"idx": idx},
        "ip_address": "127.0.0.1",
        "user_agent": "pytest",
    }


@pytest.mark.asyncio
async def test_enqueue_drops_when_queue_is_full():
    service = RequestAuditQueueService(
        maxsize=1,
        batch_size=10,
        flush_ms=5000,
        drop_warn_every=1,
        workers=1,
    )
    # Simulate a running service without draining worker to force queue-full.
    service._running = True

    assert service.enqueue(**_event(1)) is True
    assert service.enqueue(**_event(2)) is False

    stats = service.stats()
    assert stats["enqueued"] == 1
    assert stats["dropped"] == 1


@pytest.mark.asyncio
async def test_worker_flushes_batched_events(monkeypatch):
    service = RequestAuditQueueService(
        maxsize=100,
        batch_size=2,
        flush_ms=50,
        drop_warn_every=10,
        workers=1,
    )

    flushed_batches: list[list[dict]] = []

    async def fake_flush(batch):
        flushed_batches.append(list(batch))

    monkeypatch.setattr(service, "_flush_batch", fake_flush)

    await service.start()
    service.enqueue(**_event(1))
    service.enqueue(**_event(2))
    service.enqueue(**_event(3))

    await asyncio.sleep(0.2)
    await service.stop()

    assert sum(len(batch) for batch in flushed_batches) == 3
