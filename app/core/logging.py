import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict

import structlog
from app.core.config import settings

def setup_logging():
    """
    Configures structured JSON logging for production.
    Uses structlog for high-performance, structured logging.
    """
    
    # Processors for structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if settings.ENVIRONMENT == "production":
        # JSON output for CloudWatch/ELK
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Pretty console output for local development
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Bridge standard logging to structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )
    
    # Silence chatty libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)

def get_logger(name: str):
    """Utility to get a structured logger"""
    return structlog.get_logger(name)
