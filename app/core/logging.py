import logging
import logging.config
import sys
from typing import Any

try:
    import structlog  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - environment fallback
    structlog = None

from app.core.config import settings


class _FallbackBoundLogger:
    """Minimal structlog-like adapter for environments without structlog."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def bind(self, **kwargs: Any) -> "_FallbackBoundLogger":
        return self

    def _emit(self, level: int, event: str, **kwargs: Any) -> None:
        if kwargs:
            self._logger.log(level, "%s | %s", event, kwargs)
        else:
            self._logger.log(level, "%s", event)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.DEBUG, event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.ERROR, event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.ERROR, event, **kwargs)


class _HealthcheckAccessFilter(logging.Filter):
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
        return "/health" not in message and "/ready" not in message


def _shared_processors() -> list[Any]:
    if structlog is None:
        return []
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
    Configure stdlib logging and structlog so all logs end up on stdout/stderr
    with request context attached. This is the only logging bootstrap path the
    API should use.
    """
    if structlog is None:
        handler = logging.StreamHandler(sys.stdout)
        handler.addFilter(_HealthcheckAccessFilter())
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
        root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        logging.captureWarnings(True)
    else:
        shared_processors = _shared_processors()
        renderer: Any
        if settings.ENVIRONMENT == "production":
            renderer = structlog.processors.JSONRenderer()
        else:
            renderer = structlog.dev.ConsoleRenderer()

        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processor=renderer,
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.addFilter(_HealthcheckAccessFilter())

        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
        root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

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
        "uvicorn.access": access_log_level,
        "gunicorn": logging.INFO,
        "gunicorn.error": logging.INFO,
        "gunicorn.access": access_log_level,
        "sqlalchemy.engine": logging.INFO if settings.SQLALCHEMY_ECHO else logging.WARNING,
        "aiosqlite": logging.WARNING,
        "asyncio": logging.WARNING,
    }
    for logger_name, level in quiet_loggers.items():
        library_logger = logging.getLogger(logger_name)
        library_logger.handlers.clear()
        library_logger.propagate = True
        library_logger.setLevel(level)


def get_logger(name: str) -> Any:
    if structlog is None:
        return _FallbackBoundLogger(logging.getLogger(name))
    return structlog.get_logger(name)
