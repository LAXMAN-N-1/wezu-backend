"""
P0-C CI Guard: Assert zero duplicate route registrations.

This test imports the live FastAPI app, walks every registered route,
and fails if any (method, path) pair appears more than once.
It also snapshots the total route count to catch accidental regressions
(e.g. re-introducing an ``_enhanced`` handler that shadows a base router).

Run:
    pytest tests/test_route_collisions.py -v
"""
from __future__ import annotations

import os
import sys
from collections import Counter

import pytest

# ── Bootstrap mocks (same as conftest.py) ──────────────────────────────────
from unittest.mock import MagicMock
import datetime as _datetime

if not hasattr(_datetime, "UTC"):
    _datetime.UTC = _datetime.timezone.utc

for mod_name in (
    "firebase_admin", "firebase_admin.credentials", "firebase_admin.messaging",
    "sentry_sdk", "sentry_sdk.integrations.fastapi",
):
    if mod_name not in sys.modules:
        m = MagicMock()
        if mod_name == "sentry_sdk.integrations.fastapi":
            setattr(m, "FastApiIntegration", MagicMock())
        sys.modules[mod_name] = m

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_wezu.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test_secret_for_ci_only")
os.environ.setdefault("ENVIRONMENT", "testing")

from app.main import app  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────
def _all_routes() -> list[tuple[str, str, str]]:
    """Return (method, path, handler) for every route registration."""
    results: list[tuple[str, str, str]] = []
    for route in app.routes:
        methods = getattr(route, "methods", None)
        if methods is None:
            continue
        path: str = getattr(route, "path", "")
        endpoint = getattr(route, "endpoint", None)
        handler = (
            f"{endpoint.__module__}:{endpoint.__name__}" if endpoint else "unknown"
        )
        for method in sorted(methods):
            results.append((method, path, handler))
    return results


def _duplicates(routes: list[tuple[str, str, str]]) -> dict[tuple[str, str], list[str]]:
    """Map (method, path) → [handlers] for entries appearing >1 time."""
    counter: Counter[tuple[str, str]] = Counter()
    handler_map: dict[tuple[str, str], list[str]] = {}
    for method, path, handler in routes:
        key = (method, path)
        counter[key] += 1
        handler_map.setdefault(key, []).append(handler)
    return {k: v for k, v in handler_map.items() if counter[k] > 1}


# ── Tests ──────────────────────────────────────────────────────────────────
class TestRouteCollisions:
    """CI guard – route collision detection."""

    def test_no_duplicate_routes(self):
        """Every (HTTP-method, path) pair MUST be registered exactly once."""
        routes = _all_routes()
        dupes = _duplicates(routes)

        if dupes:
            lines = ["Duplicate route registrations detected:\n"]
            for (method, path), handlers in sorted(dupes.items()):
                lines.append(f"  {method:7s} {path}")
                for h in handlers:
                    lines.append(f"          ↳ {h}")
            pytest.fail("\n".join(lines))

    def test_no_orphan_head_options(self):
        """HEAD / OPTIONS should only appear where GET / POST exist for same path."""
        routes = _all_routes()
        paths_with_methods: dict[str, set[str]] = {}
        for method, path, _ in routes:
            paths_with_methods.setdefault(path, set()).add(method)

        # The CORS middleware registers a catch-all OPTIONS /{full_path:path}
        # which is expected and not an orphan.
        CORS_CATCHALL = {"/{full_path:path}"}

        orphans = []
        for path, methods in paths_with_methods.items():
            if path in CORS_CATCHALL:
                continue
            if "HEAD" in methods and "GET" not in methods:
                orphans.append(f"HEAD without GET: {path}")
            # OPTIONS without any real method is suspicious
            if methods == {"OPTIONS"}:
                orphans.append(f"OPTIONS-only: {path}")

        if orphans:
            pytest.fail("Orphan routes:\n  " + "\n  ".join(orphans))

    def test_route_count_sanity(self):
        """
        Smoke check: total route count should be within expected bounds.
        Update the bounds after intentional bulk additions/removals.
        """
        routes = _all_routes()
        total = len(routes)
        # After P0 deconfliction the count should be < 950.
        # Adjust these bounds as the project evolves.
        assert 400 < total < 1200, (
            f"Route count {total} is outside expected range (400, 1200). "
            "If you intentionally added/removed many routes, update this test."
        )
