from __future__ import annotations

import argparse
import logging
import signal
import threading

from app.core.config import settings
from app.core.logging import setup_logging
from app.workers.event_stream_worker import (
    run_notification_worker,
    run_telematics_ingest_worker,
    run_webhook_worker,
)

logger = logging.getLogger(__name__)
_stop_event = threading.Event()


def _request_stop(signum: int, _frame: object) -> None:
    logger.info("Event runner received signal=%s; stopping", signum)
    _stop_event.set()


def _run_mode(mode: str) -> None:
    if mode == "telematics":
        run_telematics_ingest_worker(_stop_event)
        return
    if mode == "webhook":
        run_webhook_worker(_stop_event)
        return
    if mode == "notification":
        run_notification_worker(_stop_event)
        return
    if mode == "all":
        threads = [
            threading.Thread(target=run_telematics_ingest_worker, args=(_stop_event,), daemon=True, name="telematics-worker"),
            threading.Thread(target=run_webhook_worker, args=(_stop_event,), daemon=True, name="webhook-worker"),
            threading.Thread(target=run_notification_worker, args=(_stop_event,), daemon=True, name="notification-worker"),
        ]
        for thread in threads:
            thread.start()
        while not _stop_event.is_set():
            _stop_event.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=5)
        return
    raise ValueError(f"Unsupported mode: {mode}")


def main() -> int:
    try:
        parser = argparse.ArgumentParser(description="Run Redis stream event workers.")
        parser.add_argument("--mode", choices=["all", "telematics", "webhook", "notification"], default="all")
        args = parser.parse_args()

        setup_logging()
        signal.signal(signal.SIGTERM, _request_stop)
        signal.signal(signal.SIGINT, _request_stop)
        if not bool(getattr(settings, "ENABLE_EVENT_STREAMS", True)):
            logger.info("Event streams are disabled; idling to avoid restart loops")
            while not _stop_event.is_set():
                _stop_event.wait(timeout=30)
            return 0
        logger.info("Starting event runner mode=%s", args.mode)
        _run_mode(args.mode)
        logger.info("Event runner stopped")
        return 0
    except Exception as exc:
        logger.exception("Fatal error in event runner. Sleeping 10s to prevent crash loop.")
        import time
        time.sleep(10)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
