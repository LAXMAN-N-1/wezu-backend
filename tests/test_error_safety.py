"""
P4-A CI Guard — Error Detail-Leak Prevention
=============================================
Scans route handler files for patterns that leak internal exception
details to API clients via HTTPException or response dicts.

Rules:
  • 500-level HTTPException must NEVER contain str(e) or f"...{str(e)}".
  • Response dicts must NEVER contain "error": str(e).
  • 400-level ValueError catches MAY pass str(e) only if the ValueError
    originates from our own service-layer validation (allowlisted).

Run:
  DATABASE_URL=sqlite:///./test_wezu.db REDIS_URL=redis://localhost:6379/0 \
  SECRET_KEY=test_secret_for_ci_only ENVIRONMENT=testing \
  python3.11 -m pytest tests/test_error_safety.py -v
"""

import ast
import os
import textwrap
from pathlib import Path

import pytest

ROUTE_DIRS = [
    Path("app/api/v1"),
    Path("app/api/admin"),
]

MIDDLEWARE_DIR = Path("app/middleware")


class _LeakVisitor(ast.NodeVisitor):
    """Walk AST looking for str(e) leaking into HTTP responses."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.violations: list[dict] = []

    # ── helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _is_str_e(node: ast.AST) -> bool:
        """Return True if node is `str(e)` or `str(exc)` etc."""
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "str":
                if len(node.args) == 1 and isinstance(node.args[0], ast.Name):
                    return True
        return False

    @staticmethod
    def _fstring_contains_str_e(node: ast.JoinedStr) -> bool:
        """Return True if an f-string contains a {str(e)} expression."""
        for val in node.values:
            if isinstance(val, ast.FormattedValue):
                if _LeakVisitor._is_str_e(val.value):
                    return True
        return False

    @staticmethod
    def _get_status_code(keywords: list[ast.keyword]) -> int | None:
        """Extract literal status_code from HTTPException(status_code=N)."""
        for kw in keywords:
            if kw.arg == "status_code":
                if isinstance(kw.value, ast.Constant):
                    return kw.value.value
                # status.HTTP_500_... → attribute name encodes the code
                if isinstance(kw.value, ast.Attribute):
                    name = kw.value.attr  # e.g. "HTTP_500_INTERNAL_SERVER_ERROR"
                    parts = name.split("_")
                    for p in parts:
                        if p.isdigit():
                            return int(p)
        return None

    # ── visitor ───────────────────────────────────────────────────────
    def visit_Raise(self, node: ast.Raise):
        """Check `raise HTTPException(status_code=5xx, detail=str(e))`."""
        if node.exc and isinstance(node.exc, ast.Call):
            func = node.exc.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name == "HTTPException":
                code = self._get_status_code(node.exc.keywords)
                for kw in node.exc.keywords:
                    if kw.arg == "detail":
                        has_leak = False
                        if self._is_str_e(kw.value):
                            has_leak = True
                        elif isinstance(kw.value, ast.JoinedStr):
                            has_leak = self._fstring_contains_str_e(kw.value)
                        if has_leak and code is not None and code >= 500:
                            self.violations.append({
                                "file": self.filepath,
                                "line": node.lineno,
                                "kind": f"HTTPException({code}) leaks str(e)",
                            })
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return):
        """Check `return {"error": str(e)}` in response dicts."""
        if node.value is not None:
            self._check_dict_leak(node.value, node.lineno)
        self.generic_visit(node)

    def _check_dict_leak(self, node: ast.AST, lineno: int):
        """Recursively check for {"error": str(e)} in a dict expression."""
        if isinstance(node, ast.Dict):
            for key, val in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "error":
                    if self._is_str_e(val):
                        self.violations.append({
                            "file": self.filepath,
                            "line": lineno,
                            "kind": 'Response dict "error" leaks str(e)',
                        })
        # Also check if it's a JSONResponse(..., content={...})
        if isinstance(node, ast.Call):
            for kw in getattr(node, 'keywords', []):
                if kw.arg == "content" and isinstance(kw.value, ast.Dict):
                    self._check_dict_leak(kw.value, lineno)
        self.generic_visit(node)


def _collect_violations() -> list[dict]:
    violations = []
    for route_dir in ROUTE_DIRS:
        if not route_dir.exists():
            continue
        for pyfile in sorted(route_dir.glob("*.py")):
            source = pyfile.read_text()
            try:
                tree = ast.parse(source, filename=str(pyfile))
            except SyntaxError:
                continue
            visitor = _LeakVisitor(str(pyfile))
            visitor.visit(tree)
            violations.extend(visitor.violations)
    return violations


def _collect_middleware_violations() -> list[dict]:
    violations = []
    if not MIDDLEWARE_DIR.exists():
        return violations
    for pyfile in sorted(MIDDLEWARE_DIR.glob("*.py")):
        source = pyfile.read_text()
        try:
            tree = ast.parse(source, filename=str(pyfile))
        except SyntaxError:
            continue
        visitor = _LeakVisitor(str(pyfile))
        visitor.visit(tree)
        violations.extend(visitor.violations)
    return violations


# ── Tests ─────────────────────────────────────────────────────────────

class TestErrorSafety:

    def test_no_500_level_str_e_leaks_in_routes(self):
        """No route handler should leak str(e) in 500-level HTTPException."""
        violations = _collect_violations()
        http_leaks = [v for v in violations if "HTTPException" in v["kind"]]
        if http_leaks:
            report = "\n".join(
                f"  {v['file']}:{v['line']} — {v['kind']}" for v in http_leaks
            )
            pytest.fail(
                f"{len(http_leaks)} route(s) leak internal errors to clients:\n{report}"
            )

    def test_no_response_dict_str_e_leaks(self):
        """No route handler should return {\"error\": str(e)} to clients."""
        violations = _collect_violations()
        dict_leaks = [v for v in violations if "Response dict" in v["kind"]]
        if dict_leaks:
            report = "\n".join(
                f"  {v['file']}:{v['line']} — {v['kind']}" for v in dict_leaks
            )
            pytest.fail(
                f"{len(dict_leaks)} route(s) leak internal errors in response dicts:\n{report}"
            )

    def test_error_handler_middleware_safe(self):
        """Global error handler must not leak str(e) in 500 responses."""
        violations = _collect_middleware_violations()
        if violations:
            report = "\n".join(
                f"  {v['file']}:{v['line']} — {v['kind']}" for v in violations
            )
            pytest.fail(
                f"Middleware leaks internal errors:\n{report}"
            )

    def test_error_handler_uses_request_id(self):
        """ErrorHandlerMiddleware must include request_id for correlation."""
        handler_path = MIDDLEWARE_DIR / "error_handler.py"
        assert handler_path.exists(), "error_handler.py not found"
        source = handler_path.read_text()
        assert "request_id" in source, (
            "ErrorHandlerMiddleware should include request_id in error responses "
            "for log correlation"
        )
