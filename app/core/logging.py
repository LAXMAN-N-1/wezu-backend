from __future__ import annotations
import json
import logging
import os
import sys
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any

try:
    import structlog  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - environment fallback
    structlog = None

from app.core.config import settings

_LOGGING_CONFIGURED = False

_SENSITIVE_KEY_MARKERS = {
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "apikey",
    "api_key",
    "access_key",
    "private_key",
    "refresh",
    "otp",
    "pin",
    "passcode",
    "signature",
}
_REDACTED = "***REDACTED***"


def _default_log_meta() -> dict[str, Any]:
    return {
        "service": settings.LOG_SERVICE_NAME or settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "schema_version": settings.LOG_SCHEMA_VERSION,
    }


def _truncate_string(value: str, max_len: int) -> str:
    if max_len <= 0:
        return value
    if len(value) <= max_len:
        return value
    return f"{value[:max_len]}...(truncated:{len(value) - max_len})"


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def sanitize_for_logging(value: Any, *, _depth: int = 0) -> Any:
    """Convert arbitrary objects into JSON-safe, bounded logging payloads."""
    max_items = max(1, int(settings.LOG_MAX_COLLECTION_ITEMS or 50))
    max_field_len = max(32, int(settings.LOG_MAX_FIELD_LENGTH or 2048))
    redact = bool(settings.LOG_REDACT_SENSITIVE_FIELDS)

    if _depth > 5:
        return "<max_depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        decoded = value.decode("utf-8", errors="replace")
        return _truncate_string(decoded, max_field_len)
    if isinstance(value, str):
        return _truncate_string(value, max_field_len)

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for idx, (raw_key, raw_val) in enumerate(value.items()):
            if idx >= max_items:
                out["__truncated_items__"] = len(value) - max_items
                break
            key = _truncate_string(str(raw_key), 128)
            if redact and _is_sensitive_key(key):
                out[key] = _REDACTED
                continue
            out[key] = sanitize_for_logging(raw_val, _depth=_depth + 1)
        return out

    if isinstance(value, (list, tuple, set, frozenset)):
        normalized = list(value)
        result = [sanitize_for_logging(item, _depth=_depth + 1) for item in normalized[:max_items]]
        if len(normalized) > max_items:
            result.append(f"...(truncated:{len(normalized) - max_items})")
        return result

    if hasattr(value, "model_dump"):
        try:
            return sanitize_for_logging(value.model_dump(), _depth=_depth + 1)
        except Exception:
            return _truncate_string(repr(value), max_field_len)
    if hasattr(value, "dict"):
        try:
            return sanitize_for_logging(value.dict(), _depth=_depth + 1)
        except Exception:
            return _truncate_string(repr(value), max_field_len)

    try:
        json.dumps(value)
        return value
    except Exception:
        return _truncate_string(repr(value), max_field_len)


class _FallbackBoundLogger:
    """Minimal structlog-like adapter for environments without structlog."""

    def __init__(self, logger: logging.Logger, context: dict[str, Any] | None = None):
        self._logger = logger
        self._context = context or {}

    def bind(self, **kwargs: Any) -> "_FallbackBoundLogger":
        merged = dict(self._context)
        merged.update(kwargs)
        return _FallbackBoundLogger(self._logger, merged)

    def _emit(self, level: int, event: str, *args: Any, **kwargs: Any) -> None:
        event_text = event % args if args else event
        payload = sanitize_for_logging({**_default_log_meta(), **self._context, **kwargs})
        if payload:
            self._logger.log(level, "%s %s", event_text, json.dumps(payload, ensure_ascii=False))
        else:
            self._logger.log(level, "%s", event_text)

    def debug(self, event: str, *args: Any, **kwargs: Any) -> None:
        self._emit(logging.DEBUG, event, *args, **kwargs)

    def info(self, event: str, *args: Any, **kwargs: Any) -> None:
        self._emit(logging.INFO, event, *args, **kwargs)

    def warning(self, event: str, *args: Any, **kwargs: Any) -> None:
        self._emit(logging.WARNING, event, *args, **kwargs)

    def error(self, event: str, *args: Any, **kwargs: Any) -> None:
        self._emit(logging.ERROR, event, *args, **kwargs)

    def exception(self, event: str, *args: Any, **kwargs: Any) -> None:
        event_text = event % args if args else event
        payload = sanitize_for_logging({**_default_log_meta(), **self._context, **kwargs})
        if payload:
            self._logger.exception("%s %s", event_text, json.dumps(payload, ensure_ascii=False))
        else:
            self._logger.exception("%s", event_text)


class _HealthcheckAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if settings.LOG_HEALTHCHECKS:
            return True
        if record.name not in {"uvicorn.access", "gunicorn.access"}:
            return True

        excluded_paths = tuple(p for p in settings.LOG_EXCLUDE_PATHS if p)
        path_hint = ""
        args = getattr(record, "args", None)
        if isinstance(args, tuple) and len(args) >= 3:
            path_hint = str(args[2])

        message = path_hint or record.getMessage()
        return not any(path in message for path in excluded_paths)


def _sanitize_event_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return sanitize_for_logging(event_dict)


def _log_meta_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key, value in _default_log_meta().items():
        event_dict.setdefault(key, value)
    return event_dict


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
        _log_meta_processor,
        _sanitize_event_processor,
    ]


def bind_contextvars(**kwargs: Any) -> None:
    if structlog is None:
        return
    structlog.contextvars.bind_contextvars(**sanitize_for_logging(kwargs))


def clear_contextvars() -> None:
    if structlog is None:
        return
    structlog.contextvars.clear_contextvars()


def setup_logging() -> None:
    """Configure stdlib logging and structlog output for production."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
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
        root_logger.setLevel(log_level)
        logging.captureWarnings(True)
    else:
        shared_processors = _shared_processors()
        renderer: Any = (
            structlog.processors.JSONRenderer()
            if settings.ENVIRONMENT == "production"
            else structlog.dev.ConsoleRenderer()
        )

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
        root_logger.setLevel(log_level)
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

    _LOGGING_CONFIGURED = True
    logging.getLogger(__name__).info(
        "logging.setup.complete environment=%s pid=%s level=%s",
        settings.ENVIRONMENT,
        os.getpid(),
        settings.LOG_LEVEL.upper(),
    )


def get_logger(name: str) -> Any:
    if structlog is None:
        return _FallbackBoundLogger(logging.getLogger(name))
    return structlog.get_logger(name)
