"""P4-C CI Guard – Structured Logging Normalization.

Ensures critical service files use ``app.core.logging.get_logger`` instead of
the stdlib ``logging`` module directly.  Also verifies that log calls in
migrated services use structured keyword-argument style (``event, **kw``)
rather than %-formatting or f-strings.
"""

from __future__ import annotations

import ast
import os
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Services that MUST use get_logger (migrated in P4-C)
CRITICAL_SERVICES = [
    "app/services/wallet_service.py",
    "app/services/settlement_service.py",
    "app/services/kyc_service.py",
    "app/services/notification_service.py",
    "app/services/payment_service.py",
]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text()


# ── Test 1: No stdlib logging.getLogger in critical services ───────────

def test_critical_services_use_get_logger():
    """Critical service files must use ``get_logger`` from ``app.core.logging``,
    not ``logging.getLogger``."""
    violations: list[str] = []
    for rel in CRITICAL_SERVICES:
        src = _read(rel)
        tree = ast.parse(src, filename=rel)
        for node in ast.walk(tree):
            # Detect: logging.getLogger(...)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "getLogger"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "logging"
            ):
                violations.append(f"{rel}:{node.lineno}")
    assert not violations, (
        "Critical services still use logging.getLogger (should use get_logger):\n"
        + "\n".join(f"  • {v}" for v in violations)
    )


# ── Test 2: No bare ``import logging`` in critical services ────────────

def test_no_bare_import_logging_in_critical_services():
    """Critical services must not have ``import logging`` as a top-level import
    (``from app.core.logging import get_logger`` is the canonical form)."""
    violations: list[str] = []
    for rel in CRITICAL_SERVICES:
        src = _read(rel)
        tree = ast.parse(src, filename=rel)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "logging":
                        violations.append(f"{rel}:{node.lineno}")
    assert not violations, (
        "Critical services still have bare ``import logging``:\n"
        + "\n".join(f"  • {v}" for v in violations)
    )


# ── Test 3: get_logger is actually imported in critical services ───────

def test_get_logger_imported():
    """Every critical service must have ``from app.core.logging import get_logger``."""
    missing: list[str] = []
    for rel in CRITICAL_SERVICES:
        src = _read(rel)
        tree = ast.parse(src, filename=rel)
        found = False
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "app.core.logging"
                and any(alias.name == "get_logger" for alias in node.names)
            ):
                found = True
                break
        if not found:
            missing.append(rel)
    assert not missing, (
        "Critical services missing ``from app.core.logging import get_logger``:\n"
        + "\n".join(f"  • {m}" for m in missing)
    )


# ── Test 4: No %-format or f-string log calls in critical services ────

class _FmtVisitor(ast.NodeVisitor):
    """Detect logger.<level>() calls that use %-formatting or f-strings."""

    LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}

    def __init__(self, filename: str):
        self.filename = filename
        self.violations: list[str] = []

    def visit_Call(self, node: ast.Call):
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in self.LOG_METHODS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "logger"
            and node.args  # has positional args
        ):
            first_arg = node.args[0]
            # f-string → JoinedStr node
            if isinstance(first_arg, ast.JoinedStr):
                self.violations.append(
                    f"{self.filename}:{node.lineno} — f-string in logger.{node.func.attr}()"
                )
            # %-format: event string + extra positional args (more than 1 arg)
            elif len(node.args) > 1 and isinstance(first_arg, (ast.Constant, ast.Str)):
                val = getattr(first_arg, "value", getattr(first_arg, "s", ""))
                if isinstance(val, str) and "%" in val:
                    self.violations.append(
                        f"{self.filename}:{node.lineno} — %-format in logger.{node.func.attr}()"
                    )
        self.generic_visit(node)


def test_no_format_string_log_calls_in_critical_services():
    """Log calls in migrated services should use structured kwargs, not
    %-formatting or f-strings."""
    all_violations: list[str] = []
    for rel in CRITICAL_SERVICES:
        src = _read(rel)
        tree = ast.parse(src, filename=rel)
        visitor = _FmtVisitor(rel)
        visitor.visit(tree)
        all_violations.extend(visitor.violations)
    assert not all_violations, (
        "Log calls using %-format or f-strings in critical services:\n"
        + "\n".join(f"  • {v}" for v in all_violations)
    )
