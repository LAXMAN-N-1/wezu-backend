#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import importlib
import json
import sys
import traceback
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"


def _iter_python_files(base_dir: Path) -> list[Path]:
    return sorted(path for path in base_dir.rglob("*.py") if path.is_file())


def _has_future_annotations(module: ast.Module) -> bool:
    for stmt in module.body:
        if not isinstance(stmt, ast.ImportFrom):
            continue
        if stmt.module != "__future__":
            continue
        if any(alias.name == "annotations" for alias in stmt.names):
            return True
    return False


def _is_depends_without_callable(node: ast.AST | None) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if node.args or node.keywords:
        return False

    call_name: str | None = None
    if isinstance(node.func, ast.Name):
        call_name = node.func.id
    elif isinstance(node.func, ast.Attribute):
        call_name = node.func.attr
    return call_name == "Depends"


def _iter_function_args_with_defaults(node: ast.FunctionDef | ast.AsyncFunctionDef):
    positional = list(node.args.posonlyargs) + list(node.args.args)
    defaults = list(node.args.defaults)
    positional_defaults = [None] * (len(positional) - len(defaults)) + defaults

    for arg_node, default_node in zip(positional, positional_defaults):
        yield arg_node, default_node
    for arg_node, default_node in zip(node.args.kwonlyargs, node.args.kw_defaults):
        yield arg_node, default_node


def _scan_unsafe_depends_patterns() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for file_path in _iter_python_files(APP_DIR):
        source = file_path.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(file_path))
        if not _has_future_annotations(module):
            continue

        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for arg_node, default_node in _iter_function_args_with_defaults(node):
                if arg_node.annotation is None:
                    continue
                if not _is_depends_without_callable(default_node):
                    continue
                findings.append(
                    {
                        "file": str(file_path.relative_to(ROOT_DIR)),
                        "line": int(getattr(arg_node, "lineno", getattr(node, "lineno", 1))),
                        "function": node.name,
                        "arg": arg_node.arg,
                    }
                )
    return findings


def _render_human_report(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("WEZU VPS preflight report")
    lines.append(f"workspace: {ROOT_DIR}")
    lines.append(f"python: {sys.version.split()[0]}")

    settings_info = payload.get("settings") or {}
    if settings_info.get("status") == "ok":
        lines.append(
            f"env: {settings_info.get('environment')} | enforce_prod_safety: "
            f"{settings_info.get('enforce_production_safety')}"
        )
    else:
        lines.append(f"settings: ERROR - {settings_info.get('error')}")

    depends_issues = payload.get("depends_safety", {}).get("issues", [])
    if depends_issues:
        lines.append("unsafe FastAPI Depends() usage found:")
        for item in depends_issues:
            lines.append(
                f"  - {item['file']}:{item['line']} "
                f"({item['function']} -> {item['arg']})"
            )
    else:
        lines.append("depends safety: OK")

    app_import = payload.get("app_import") or {}
    if app_import.get("status") == "ok":
        lines.append("app import: OK")
    else:
        lines.append(f"app import: ERROR - {app_import.get('error')}")

    production_safety = payload.get("production_safety") or {}
    if production_safety.get("status") == "ok":
        lines.append("production safety check: OK")
    elif production_safety.get("status") == "skipped":
        lines.append(f"production safety check: SKIPPED ({production_safety.get('reason')})")
    else:
        lines.append(f"production safety check: ERROR - {production_safety.get('error')}")

    diagnostics = payload.get("startup_diagnostics") or {}
    if diagnostics:
        lines.append(f"startup diagnostics overall: {diagnostics.get('overall_status')}")
        required_failures = diagnostics.get("required_failures", [])
        if required_failures:
            lines.append("required dependency failures:")
            for component in required_failures:
                status = diagnostics.get("components", {}).get(component)
                lines.append(f"  - {component}: {status}")
        else:
            lines.append("required dependency failures: none")

    summary = payload.get("summary") or {}
    lines.append(
        f"result: {'PASS' if summary.get('ok') else 'FAIL'} "
        f"(errors={summary.get('error_count', 0)})"
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deployment preflight checks for VPS production startup."
    )
    parser.add_argument(
        "--allow-required-failures",
        action="store_true",
        help="Do not fail if StartupDiagnosticsService reports required component failures.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )
    args = parser.parse_args()

    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    errors: list[str] = []
    report: dict[str, Any] = {}

    depends_issues: list[dict[str, Any]]
    try:
        depends_issues = _scan_unsafe_depends_patterns()
    except Exception as exc:
        depends_issues = []
        errors.append("depends_safety_scan_failed")
        report["depends_safety"] = {
            "status": "error",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    else:
        report["depends_safety"] = {
            "status": "ok" if not depends_issues else "error",
            "issues": depends_issues,
        }
        if depends_issues:
            errors.append("depends_safety")

    settings = None
    try:
        from app.core.config import settings as app_settings

        settings = app_settings
        report["settings"] = {
            "status": "ok",
            "environment": settings.ENVIRONMENT,
            "enforce_production_safety": bool(settings.ENFORCE_PRODUCTION_SAFETY),
            "db_url_scheme": str(settings.DATABASE_URL).split("://", 1)[0],
            "redis_url_scheme": str(settings.REDIS_URL).split("://", 1)[0],
        }
    except Exception as exc:
        errors.append("settings_load")
        report["settings"] = {
            "status": "error",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

    app_main = None
    try:
        app_main = importlib.import_module("app.main")
        report["app_import"] = {"status": "ok"}
    except Exception as exc:
        errors.append("app_import")
        report["app_import"] = {
            "status": "error",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

    if app_main is not None and settings is not None:
        if hasattr(app_main, "_validate_production_safety"):
            try:
                app_main._validate_production_safety()
                report["production_safety"] = {"status": "ok"}
            except Exception as exc:
                errors.append("production_safety")
                report["production_safety"] = {
                    "status": "error",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
        else:
            report["production_safety"] = {
                "status": "skipped",
                "reason": "_validate_production_safety not found in app.main",
            }
    elif settings is not None:
        report["production_safety"] = {
            "status": "skipped",
            "reason": "app.main import failed",
        }

    if settings is not None:
        try:
            from app.services.startup_diagnostics_service import StartupDiagnosticsService

            diagnostics = StartupDiagnosticsService.collect_report()
            report["startup_diagnostics"] = {
                "overall_status": diagnostics.get("overall_status"),
                "required_failures": diagnostics.get("required_failures", []),
                "components": {
                    name: component.get("status")
                    for name, component in (diagnostics.get("components") or {}).items()
                },
            }
            required_failures = diagnostics.get("required_failures") or []
            if required_failures and not args.allow_required_failures:
                errors.append("required_dependencies")
        except Exception as exc:
            errors.append("startup_diagnostics")
            report["startup_diagnostics"] = {
                "status": "error",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }

    report["summary"] = {"ok": not errors, "errors": errors, "error_count": len(errors)}

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_render_human_report(report))

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
