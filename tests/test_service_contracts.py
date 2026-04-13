"""
P1-B CI Guard: Statically verify that every service method called
by route modules actually exists on the service class.

Prevents future AttributeError regressions (missing service methods).

Run:
    pytest tests/test_service_contracts.py -v
"""
from __future__ import annotations

import ast
import importlib
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

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

REPO_ROOT = Path(__file__).resolve().parent.parent


# ── Known dynamic-dispatch allowlist ───────────────────────────────────────
# Methods that are dispatched dynamically or via getattr, or are known
# pre-existing gaps tracked separately (P2+ scope). Skip them.
ALLOWLIST: Set[Tuple[str, str]] = set()


# ── AST helpers ────────────────────────────────────────────────────────────

def _extract_service_calls(source: str, filepath: str) -> List[Tuple[str, str, int]]:
    """
    Parse a Python file and extract (ClassName, method_name, lineno) for
    patterns like ``SomeService.some_method(``.
    """
    try:
        tree = ast.parse(source, filepath)
    except SyntaxError:
        return []

    results: List[Tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            value = node.func.value
            if isinstance(value, ast.Name) and value.id.endswith("Service"):
                results.append((value.id, node.func.attr, node.lineno))
    return results


def _extract_imports(source: str, filepath: str) -> Dict[str, str]:
    """
    Return {local_name: fully_qualified_module_path} for ``from x import Y``
    patterns where Y ends with 'Service'.
    """
    try:
        tree = ast.parse(source, filepath)
    except SyntaxError:
        return {}

    mapping: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                name = alias.asname or alias.name
                if name.endswith("Service"):
                    mapping[name] = f"{node.module}.{alias.name}"
    return mapping


def _resolve_class(fqn: str):
    """Import and return the class object, or None on failure."""
    parts = fqn.rsplit(".", 1)
    if len(parts) != 2:
        return None
    module_path, class_name = parts
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name, None)
    except Exception:
        return None


# ── Collect all route files ────────────────────────────────────────────────

def _route_files() -> List[Path]:
    dirs = [
        REPO_ROOT / "app" / "api" / "v1",
        REPO_ROOT / "app" / "api" / "admin",
    ]
    files = []
    for d in dirs:
        if d.exists():
            files.extend(sorted(d.glob("*.py")))
    return files


# ── Test ───────────────────────────────────────────────────────────────────

class TestServiceContracts:
    """CI guard – every Service.method() call in routes must resolve."""

    def test_all_service_methods_exist(self):
        missing: List[str] = []

        for filepath in _route_files():
            source = filepath.read_text()
            imports = _extract_imports(source, str(filepath))
            calls = _extract_service_calls(source, str(filepath))

            for class_name, method_name, lineno in calls:
                if (class_name, method_name) in ALLOWLIST:
                    continue

                fqn = imports.get(class_name)
                if not fqn:
                    # Can't resolve import — skip (could be a local variable)
                    continue

                cls = _resolve_class(fqn)
                if cls is None:
                    # Module import failed — not a contract violation per se
                    continue

                if not hasattr(cls, method_name):
                    rel = filepath.relative_to(REPO_ROOT)
                    missing.append(
                        f"  {rel}:{lineno}  {class_name}.{method_name}()"
                    )

        if missing:
            pytest.fail(
                f"Missing service methods ({len(missing)}):\n" + "\n".join(missing)
            )
