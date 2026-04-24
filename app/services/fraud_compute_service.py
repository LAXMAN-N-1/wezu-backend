from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable
from urllib import request

from app.core.config import settings

logger = logging.getLogger(__name__)

_state_lock = threading.Lock()
_consecutive_failures = 0
_circuit_open_until = 0.0


def _record_success() -> None:
    global _consecutive_failures, _circuit_open_until
    with _state_lock:
        _consecutive_failures = 0
        _circuit_open_until = 0.0


def _record_failure() -> None:
    global _consecutive_failures, _circuit_open_until
    threshold = max(1, int(getattr(settings, "FRAUD_COMPUTE_FAILURE_THRESHOLD", 5)))
    cooldown = max(5, int(getattr(settings, "FRAUD_COMPUTE_OPEN_SECONDS", 30)))
    with _state_lock:
        _consecutive_failures += 1
        if _consecutive_failures >= threshold:
            _circuit_open_until = time.monotonic() + cooldown


def _circuit_open() -> bool:
    with _state_lock:
        return _circuit_open_until > time.monotonic()


class FraudComputeService:
    """External compute scorer with resilient fallback to local Python scoring."""

    @staticmethod
    def score_or_fallback(
        *,
        user_id: int,
        local_scoring_fn: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        enabled = bool(getattr(settings, "FRAUD_COMPUTE_SERVICE_ENABLED", False))
        base_url = (getattr(settings, "FRAUD_COMPUTE_SERVICE_URL", None) or "").strip()
        if not enabled or not base_url:
            return local_scoring_fn()

        if _circuit_open():
            logger.warning("Fraud compute circuit open; using local scorer user_id=%s", user_id)
            return local_scoring_fn()

        payload = json.dumps({"user_id": user_id}).encode("utf-8")
        timeout_seconds = max(1, int(getattr(settings, "FRAUD_COMPUTE_SERVICE_TIMEOUT_SECONDS", 2)))
        url = f"{base_url.rstrip('/')}/score"
        req = request.Request(
            url=url,
            method="POST",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        api_key = (getattr(settings, "FRAUD_COMPUTE_SERVICE_API_KEY", None) or "").strip()
        if api_key:
            req.add_header("X-Compute-Api-Key", api_key)

        try:
            with request.urlopen(req, timeout=timeout_seconds) as resp:
                body = resp.read()
                response_data = json.loads(body.decode("utf-8"))

            if not isinstance(response_data, dict):
                raise ValueError("Compute service response is not an object")
            if "risk_score" not in response_data:
                raise ValueError("Compute service response missing risk_score")

            _record_success()
            return response_data
        except Exception as exc:
            _record_failure()
            logger.warning("Fraud compute service unavailable; falling back to local scorer: %s", exc)
            return local_scoring_fn()
