from __future__ import annotations

import logging
import signal
import threading

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.logistics_schema_guard import validate_logistics_schema
from app.db.session import init_db
from app.services.startup_diagnostics_service import StartupDiagnosticsService
from app.workers.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)
_stop_event = threading.Event()


def _request_stop(signum: int, _frame: object) -> None:
    logger.info("Scheduler runner received signal=%s; stopping", signum)
    _stop_event.set()


def main() -> int:
    try:
        setup_logging()

        signal.signal(signal.SIGTERM, _request_stop)
        signal.signal(signal.SIGINT, _request_stop)

        if not settings.SCHEDULER_ENABLED:
            logger.info("Scheduler runner is disabled (SCHEDULER_ENABLED=false); idling to avoid restart loops")
            while not _stop_event.is_set():
                _stop_event.wait(timeout=30)
            return 0

        scheduler_started = False
        try:
            while not _stop_event.is_set():
                try:
                    init_db(
                        create_tables=settings.AUTO_CREATE_TABLES,
                        seed_roles=settings.AUTO_SEED_ROLES,
                    )
                    if settings.LOGISTICS_SCHEMA_CHECK_ENABLED:
                        validate_logistics_schema(strict=settings.LOGISTICS_SCHEMA_STRICT)
                    StartupDiagnosticsService.enforce_required_dependencies()
                    start_scheduler()
                    scheduler_started = True
                    logger.info("Scheduler runner started")
                    break
                except Exception:
                    if not bool(getattr(settings, "ALLOW_START_WITHOUT_DB", False)):
                        raise
                    logger.exception(
                        "Scheduler bootstrap failed with ALLOW_START_WITHOUT_DB=true; retrying in 15s"
                    )
                    _stop_event.wait(timeout=15)

            while not _stop_event.is_set():
                _stop_event.wait(timeout=5)
        finally:
            if scheduler_started:
                stop_scheduler()
                logger.info("Scheduler runner stopped")

        return 0
    except Exception:
        logger.exception("Fatal error in scheduler runner. Sleeping 10s to prevent crash loop.")
        import time
        time.sleep(10)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
