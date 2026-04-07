"""
P4-B CI Guard — Input Contract Enforcement
===========================================
Scans route handler files for POST/PUT/PATCH handlers that accept
raw `dict` body parameters instead of typed Pydantic schemas.

Run:
  DATABASE_URL=sqlite:///./test_wezu.db REDIS_URL=redis://localhost:6379/0 \
  SECRET_KEY=test_secret_for_ci_only ENVIRONMENT=testing \
  python3.11 -m pytest tests/test_input_contracts.py -v
"""

import ast
import os
from pathlib import Path

import pytest

ROUTE_DIRS = [
    Path("app/api/v1"),
    Path("app/api/admin"),
]


def _find_raw_dict_params() -> list[dict]:
    """AST scan: find POST/PUT/PATCH handlers with `param: dict`."""
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

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for dec in node.decorator_list:
                    if not isinstance(dec, ast.Call):
                        continue
                    func = dec.func
                    method = None
                    if isinstance(func, ast.Attribute):
                        method = func.attr
                    elif isinstance(func, ast.Name):
                        method = func.id
                    if method not in ("post", "put", "patch"):
                        continue

                    for arg in node.args.args:
                        if arg.annotation is None:
                            continue
                        ann = arg.annotation
                        name = None
                        if isinstance(ann, ast.Name):
                            name = ann.id
                        elif isinstance(ann, ast.Attribute):
                            name = ann.attr
                        if name == "dict":
                            violations.append({
                                "file": str(pyfile),
                                "line": node.lineno,
                                "handler": node.name,
                                "param": arg.arg,
                            })
    return violations


class TestInputContracts:

    def test_no_raw_dict_body_params(self):
        """No POST/PUT/PATCH handler should accept bare `dict` body params."""
        violations = _find_raw_dict_params()
        if violations:
            report = "\n".join(
                f"  {v['file']}:{v['line']} {v['handler']}({v['param']}: dict)"
                for v in violations
            )
            pytest.fail(
                f"{len(violations)} handler(s) accept raw dict input:\n{report}\n"
                "Replace with a Pydantic schema from app/schemas/input_contracts.py"
            )

    def test_input_contracts_schema_exists(self):
        """The shared input contracts schema module must exist."""
        path = Path("app/schemas/input_contracts.py")
        assert path.exists(), "app/schemas/input_contracts.py not found"

    def test_input_contracts_importable(self):
        """All schemas in input_contracts must be importable."""
        from app.schemas.input_contracts import (
            PreferencesUpdate,
            ChangePasswordRequest,
            DealerPromotionCreate,
            DealerPromotionUpdate,
            BankAccountUpdate,
            NotificationPreferencesUpdate,
            DealerDocumentUpload,
            MaintenanceTaskCreate,
        )
        # Verify they are real Pydantic models
        for cls in [
            PreferencesUpdate,
            ChangePasswordRequest,
            DealerPromotionCreate,
            DealerPromotionUpdate,
            BankAccountUpdate,
            NotificationPreferencesUpdate,
            DealerDocumentUpload,
            MaintenanceTaskCreate,
        ]:
            assert hasattr(cls, "model_fields"), f"{cls.__name__} is not a Pydantic model"
