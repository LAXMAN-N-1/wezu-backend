import logging
import logging.config
import sys

import structlog

from app.core.config import settings


_HEALTH_PATHS = frozenset({"/health", "/live", "/ready", "/healthz", "/livez", "/readyz"})


class _HealthcheckAccessFilter(logging.Filter):
    """Suppress healthcheck noise from uvicorn/gunicorn access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if settings.LOG_HEALTHCHECKS:
            return True
        if record.name not in {"uvicorn.access", "gunicorn.access"}:
            return True

        path_hint = ""
        args = getattr(record, "args", None)
        if isinstance(args, tuple) and len(args) >= 3:
            path_hint = str(args[2])

        message = path_hint or record.getMessage()
        return not any(p in message for p in _HEALTH_PATHS)


def _shared_processors() -> list[structlog.types.Processor]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def setup_logging() -> None:
    """
    Configure stdlib logging and structlog so **all** logs end up on
    stderr (the stream Docker/Dozzle/Coolify capture by default) with
    request context attached.

    Key design choices for container environments:
    • Write to **sys.stderr** — Docker's log driver captures stderr
      line-by-line; gunicorn's --capture-output only intercepts
      sys.stdout, so using stderr avoids the double-pipe buffering
      that makes logs disappear.
    • Flush after every record so nothing stays stuck in a buffer.
    • Do NOT clear handlers on gunicorn.error / gunicorn.access —
      let gunicorn's own handlers coexist; we only ensure propagation
      reaches our root handler.
    """
    shared_processors = _shared_processors()
    renderer: structlog.types.Processor
    env = settings.ENVIRONMENT.lower()
    if env == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processor=renderer,
    )

    # --- stderr handler with immediate flush ---
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    handler.addFilter(_HealthcheckAccessFilter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    logging.captureWarnings(True)

    # Emit a raw stderr line BEFORE structlog is configured so we can
    # verify the renderer choice even if structlog itself is misconfigured.
    print(
        f"[logging-setup] ENVIRONMENT={settings.ENVIRONMENT!r} "
        f"resolved_env={env!r} renderer={renderer.__class__.__name__}",
        file=sys.stderr,
        flush=True,
    )

    logging.captureWarnings(True)

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    access_log_level = logging.INFO if settings.LOG_ACCESS_LOGS else logging.WARNING
    quiet_loggers = {
        "uvicorn": logging.INFO,
        "uvicorn.error": logging.INFO,
        # Silence uvicorn.access completely — our RequestLoggingMiddleware
        # already emits richer structured request logs with request_id,
        # duration_ms, user_id, etc.  Keeping uvicorn.access on causes
        # every request to appear twice.
        "uvicorn.access": logging.WARNING,
        "gunicorn.error": logging.INFO,
        "gunicorn.access": access_log_level,
        "sqlalchemy.engine": logging.INFO if settings.SQLALCHEMY_ECHO else logging.WARNING,
        "aiosqlite": logging.WARNING,
        "asyncio": logging.WARNING,
    }
    for logger_name, level in quiet_loggers.items():
        library_logger = logging.getLogger(logger_name)
        # Let library loggers propagate to root (which has our stderr
        # handler) instead of clearing their handlers — gunicorn adds
        # its own handler that we must not remove.
        library_logger.propagate = True
        library_logger.setLevel(level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
