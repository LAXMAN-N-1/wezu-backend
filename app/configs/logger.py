from typing import Any

from app.core.logging import get_logger


def setup_logger(name: str) -> Any:
    # Backward-compatible shim: route legacy imports into unified logging stack.
    return get_logger(name)


app_logger = setup_logger("wezu_platform")
