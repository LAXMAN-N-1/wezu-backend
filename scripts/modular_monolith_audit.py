#!/usr/bin/env python3
"""
Generate Phase 0 and Phase 1 modernization audit artifacts.

Usage:
  python scripts/modular_monolith_audit.py phase0
  python scripts/modular_monolith_audit.py phase1
"""
from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "app"
DOCS_DIR = REPO_ROOT / "docs"
AUDIT_DIR = DOCS_DIR / "audit"

V1_API_DIR = APP_DIR / "api" / "v1"
ADMIN_API_DIR = APP_DIR / "api" / "admin"

TARGET_DEAD_FLOW_FILES = [
    "app/api/admin/admin_alerts.py",
    "app/api/admin/admin_analytics.py",
    "app/api/admin/admin_roles.py",
    "app/api/admin/admin_user_bulk.py",
    "app/api/v1/dealer_commission.py",
    "app/api/v1/dealer_documents.py",
    "app/api/v1/dealer_kyc.py",
    "app/api/v1/vendors.py",
]


PARTITIONS = [
    "identity_access",
    "kyc_fraud_compliance",
    "customer_rental_swap",
    "finance_wallet_payments",
    "dealer_portal",
    "logistics_supply",
    "iot_telematics_system",
    "comms_content_engagement",
    "admin_platform_ops",
    "platform_core",
]


PARTITION_DESCRIPTIONS = {
    "identity_access": "Identity, auth, sessions, role resolution, passkeys, token verification.",
    "kyc_fraud_compliance": "KYC, fraud analysis, verification workflows, compliance records.",
    "customer_rental_swap": "Customer rental lifecycle, booking, active rentals, swaps, returns.",
    "finance_wallet_payments": "Wallet balances, payment orders, settlements, refunds, ledgers.",
    "dealer_portal": "Dealer onboarding, dealer station operations, dealer commissions and documents.",
    "logistics_supply": "Driver, route, dispatch, manifests, transfer logistics, inventory movement.",
    "iot_telematics_system": "Battery/station state, telemetry ingestion, maintenance, health tracking.",
    "comms_content_engagement": "Notifications, support, FAQs, content/campaign/promo engagement.",
    "admin_platform_ops": "Admin console APIs, analytics aggregation, audit and operational controls.",
    "platform_core": "Core/shared infrastructure and cross-cutting primitives with no business ownership.",
}


AUTH_NAME_PATTERNS = (
    "current_user",
    "current_active",
    "current_superuser",
    "current_admin",
    "check_permission",
    "require_permission",
    "require_role",
    "verify_token",
    "auth",
)

DB_METHOD_NAMES = {
    "add",
    "add_all",
    "bulk_insert_mappings",
    "bulk_save_objects",
    "bulk_update_mappings",
    "commit",
    "delete",
    "exec",
    "execute",
    "flush",
    "get",
    "merge",
    "query",
    "refresh",
    "rollback",
    "scalar",
    "scalars",
}


@dataclass
class RouteDescriptor:
    module: str
    router_file: str
    function_name: str
    method: str
    raw_path: str
    path: str
    candidate_mount_path: str
    mounted: bool
    has_auth: bool
    does_direct_db: bool
    calls_service: bool
    calls_repository: bool
    response_model: str
    lineno: int


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def posix_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def module_from_path(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def iter_python_files(base: Path) -> list[Path]:
    return sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)


def read_ast(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(), filename=str(path))
    except SyntaxError:
        return None


def normalize_path(path: str) -> str:
    if not path:
        return "/"
    if not path.startswith("/"):
        path = "/" + path
    path = re.sub(r"/+", "/", path)
    return path


def join_paths(a: str, b: str) -> str:
    if not a:
        return normalize_path(b or "/")
    if not b:
        return normalize_path(a)
    return normalize_path(f"{a.rstrip('/')}/{b.lstrip('/')}")


def synthetic_unmounted_prefix(router_file: str) -> str:
    path = Path(router_file)
    rel: Path
    if router_file.startswith("app/api/v1/"):
        rel = path.relative_to("app/api/v1")
        base = Path("/api/v1") / rel.with_suffix("")
    elif router_file.startswith("app/api/admin/"):
        rel = path.relative_to("app/api/admin")
        base = Path("/api/v1/admin") / rel.with_suffix("")
    else:
        base = Path("/api") / path.with_suffix("")
    if base.name == "__init__":
        base = base.parent
    return str(base).replace("_", "-")


def expression_to_str(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    try:
        return ast.unparse(node)  # type: ignore[attr-defined]
    except Exception:
        return ""


def call_target_name(expr: ast.AST | None) -> str:
    if expr is None:
        return ""
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        head = call_target_name(expr.value)
        return f"{head}.{expr.attr}" if head else expr.attr
    if isinstance(expr, ast.Call):
        return call_target_name(expr.func)
    return ""


def is_depends_call(expr: ast.AST | None) -> bool:
    if not isinstance(expr, ast.Call):
        return False
    fn = call_target_name(expr.func).split(".")[-1]
    return fn in {"Depends", "Security"}


def dependency_target(expr: ast.AST | None) -> str:
    if not isinstance(expr, ast.Call):
        return ""
    if not expr.args:
        return ""
    return call_target_name(expr.args[0]).split(".")[-1]


def is_auth_dependency(expr: ast.AST | None) -> bool:
    target = dependency_target(expr).lower()
    return any(pattern in target for pattern in AUTH_NAME_PATTERNS)


def is_db_dependency(expr: ast.AST | None) -> bool:
    target = dependency_target(expr).lower()
    return target in {"get_db", "get_session"}


def extract_router_prefixes(tree: ast.AST) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        target_name = node.targets[0].id
        if not isinstance(node.value, ast.Call):
            continue
        func_name = call_target_name(node.value.func).split(".")[-1]
        if func_name != "APIRouter":
            continue
        prefix = ""
        for kw in node.value.keywords:
            if kw.arg == "prefix":
                prefix = expression_to_str(kw.value)
                break
        prefixes[target_name] = normalize_path(prefix) if prefix else ""
    return prefixes


def iter_fn_args_with_defaults(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[str, ast.AST | None]]:
    args = list(node.args.args)
    defaults = [None] * (len(args) - len(node.args.defaults)) + list(node.args.defaults)
    out: list[tuple[str, ast.AST | None]] = [(arg.arg, default) for arg, default in zip(args, defaults)]
    out.extend((arg.arg, default) for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults))
    return out


def collect_import_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    service_aliases: set[str] = set()
    repo_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                local = alias.asname or alias.name
                if mod.startswith("app.services") or local.endswith("Service"):
                    service_aliases.add(local)
                if mod.startswith("app.repositories") or local.endswith("Repository"):
                    repo_aliases.add(local)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = (alias.asname or alias.name).split(".")[-1]
                if alias.name.startswith("app.services"):
                    service_aliases.add(local)
                if alias.name.startswith("app.repositories"):
                    repo_aliases.add(local)
    return service_aliases, repo_aliases


def analyze_route_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    decorator: ast.Call,
    service_aliases: set[str],
    repo_aliases: set[str],
) -> tuple[bool, bool, bool, bool]:
    has_auth = any(arg_name == "current_user" for arg_name, _ in iter_fn_args_with_defaults(node))
    db_params: set[str] = set()

    for arg_name, default in iter_fn_args_with_defaults(node):
        if is_auth_dependency(default):
            has_auth = True
        if is_db_dependency(default):
            db_params.add(arg_name)

    for kw in decorator.keywords:
        if kw.arg != "dependencies":
            continue
        if isinstance(kw.value, (ast.List, ast.Tuple)):
            for dep in kw.value.elts:
                if is_auth_dependency(dep):
                    has_auth = True

    does_direct_db = False
    calls_service = False
    calls_repository = False

    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            if isinstance(sub.func, ast.Attribute) and isinstance(sub.func.value, ast.Name):
                owner = sub.func.value.id
                attr = sub.func.attr
                if owner in db_params and attr in DB_METHOD_NAMES:
                    does_direct_db = True
                if owner.endswith("Service") or owner in service_aliases:
                    calls_service = True
                if owner.endswith("Repository") or owner in repo_aliases:
                    calls_repository = True
            elif isinstance(sub.func, ast.Name):
                if sub.func.id in service_aliases:
                    calls_service = True
                if sub.func.id in repo_aliases:
                    calls_repository = True

    return has_auth, does_direct_db, calls_service, calls_repository


def parse_routes_from_file(path: Path) -> list[dict[str, Any]]:
    tree = read_ast(path)
    if tree is None:
        return []
    module = module_from_path(path)
    router_file = posix_rel(path)
    router_prefixes = extract_router_prefixes(tree)
    service_aliases, repo_aliases = collect_import_aliases(tree)

    routes: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for deco in node.decorator_list:
            if not isinstance(deco, ast.Call) or not isinstance(deco.func, ast.Attribute):
                continue
            if not isinstance(deco.func.value, ast.Name):
                continue
            router_name = deco.func.value.id
            method_name = deco.func.attr.lower()
            if method_name not in {"get", "post", "put", "patch", "delete", "options", "head", "api_route"}:
                continue

            raw_path = expression_to_str(deco.args[0]) if deco.args else ""
            path_fragment = raw_path if raw_path != "" else ""
            base_prefix = router_prefixes.get(router_name, "")
            if base_prefix and path_fragment:
                local_path = join_paths(base_prefix, path_fragment)
            elif base_prefix and not path_fragment:
                local_path = normalize_path(base_prefix)
            elif not base_prefix and path_fragment:
                local_path = normalize_path(path_fragment)
            else:
                local_path = ""
            response_model = ""
            methods: list[str] = []

            for kw in deco.keywords:
                if kw.arg == "response_model":
                    response_model = expression_to_str(kw.value)
                elif kw.arg == "methods" and method_name == "api_route":
                    if isinstance(kw.value, (ast.List, ast.Tuple)):
                        methods = [
                            expression_to_str(x).upper()
                            for x in kw.value.elts
                            if expression_to_str(x)
                        ]

            if method_name != "api_route":
                methods = [method_name.upper()]

            has_auth, does_direct_db, calls_service, calls_repository = analyze_route_function(
                node,
                deco,
                service_aliases,
                repo_aliases,
            )

            for method in methods:
                routes.append(
                    {
                        "module": module,
                        "router_file": router_file,
                        "function_name": node.name,
                        "method": method,
                        "raw_path": path_fragment,
                        "local_path": local_path,
                        "has_auth": has_auth,
                        "does_direct_db": does_direct_db,
                        "calls_service": calls_service,
                        "calls_repository": calls_repository,
                        "response_model": response_model,
                        "lineno": node.lineno,
                    }
                )
    return routes


def eval_string_expr(node: ast.AST | None, vars_map: dict[str, str]) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Constant):
        return str(node.value) if isinstance(node.value, str) else ""
    if isinstance(node, ast.Name):
        return vars_map.get(node.id, "")
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for val in node.values:
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                parts.append(val.value)
            elif isinstance(val, ast.FormattedValue):
                parts.append(eval_string_expr(val.value, vars_map))
            else:
                parts.append("")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return eval_string_expr(node.left, vars_map) + eval_string_expr(node.right, vars_map)
    if isinstance(node, ast.Attribute):
        # We intentionally do not attempt to resolve runtime settings objects.
        return ""
    return ""


def module_file_for_name(module: str) -> Path | None:
    init_path = REPO_ROOT / (module.replace(".", "/") + "/__init__.py")
    if init_path.exists():
        return init_path
    py_path = REPO_ROOT / (module.replace(".", "/") + ".py")
    if py_path.exists():
        return py_path
    return None


def parse_module_import_aliases(tree: ast.AST, current_module: str, is_package: bool) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    module_aliases: dict[str, str] = {}
    router_aliases: dict[str, tuple[str, str]] = {}

    body_nodes = tree.body if isinstance(tree, ast.Module) else []
    for node in body_nodes:
        if isinstance(node, ast.ImportFrom):
            base = resolve_import_from(node, current_module, is_package)
            for alias in node.names:
                local = alias.asname or alias.name
                candidate = f"{base}.{alias.name}" if alias.name != "router" else base
                module_aliases[local] = candidate
                if alias.name == "router":
                    router_aliases[local] = (base, "router")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = (alias.asname or alias.name).split(".")[-1]
                module_aliases[local] = alias.name
    return module_aliases, router_aliases


def resolve_include_target(
    expr: ast.AST,
    module_aliases: dict[str, str],
    router_aliases: dict[str, tuple[str, str]],
) -> tuple[str, str] | None:
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        owner = expr.value.id
        if expr.attr == "router" and owner in module_aliases:
            return module_aliases[owner], "router"
    if isinstance(expr, ast.Name):
        if expr.id in router_aliases:
            return router_aliases[expr.id]
        if expr.id in module_aliases:
            return module_aliases[expr.id], "router"
    return None


def parse_include_router_calls(
    tree: ast.AST,
    owner_router_var: str,
    module_aliases: dict[str, str],
    router_aliases: dict[str, tuple[str, str]],
    vars_map: dict[str, str],
) -> list[tuple[tuple[str, str], str]]:
    include_calls: list[tuple[tuple[str, str], str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "include_router":
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        if node.func.value.id != owner_router_var:
            continue
        if not node.args:
            continue
        target = resolve_include_target(node.args[0], module_aliases, router_aliases)
        if not target:
            continue
        prefix = ""
        for kw in node.keywords:
            if kw.arg == "prefix":
                prefix = eval_string_expr(kw.value, vars_map)
                break
        include_calls.append((target, normalize_path(prefix) if prefix else ""))
    return include_calls


def build_mount_prefixes() -> dict[str, list[str]]:
    main_path = APP_DIR / "main.py"
    tree = read_ast(main_path)
    if tree is None:
        raise RuntimeError("Unable to parse app/main.py for route mount analysis.")

    current_module = module_from_path(main_path)
    module_aliases, router_aliases = parse_module_import_aliases(tree, current_module, False)
    vars_map: dict[str, str] = {"v1_str": "/api/v1"}
    mounts: dict[str, set[str]] = defaultdict(set)
    route_defs_cache: dict[str, bool] = {}
    parsed_module_cache: dict[str, tuple[ast.AST, dict[str, str], dict[str, tuple[str, str]], bool]] = {}

    def module_has_own_routes(module: str) -> bool:
        if module in route_defs_cache:
            return route_defs_cache[module]
        file_path = module_file_for_name(module)
        if not file_path:
            route_defs_cache[module] = False
            return False
        has_routes = bool(parse_routes_from_file(file_path))
        route_defs_cache[module] = has_routes
        return has_routes

    def load_module_parse(module: str) -> tuple[ast.AST, dict[str, str], dict[str, tuple[str, str]], bool] | None:
        if module in parsed_module_cache:
            return parsed_module_cache[module]
        file_path = module_file_for_name(module)
        if not file_path:
            return None
        mod_tree = read_ast(file_path)
        if mod_tree is None:
            return None
        mod_name = module_from_path(file_path)
        is_pkg = file_path.name == "__init__.py"
        mod_aliases, mod_router_aliases = parse_module_import_aliases(mod_tree, mod_name, is_pkg)
        parsed_module_cache[module] = (mod_tree, mod_aliases, mod_router_aliases, is_pkg)
        return parsed_module_cache[module]

    recursion_guard: set[tuple[str, str, str]] = set()

    def recurse_module(module: str, router_var: str, prefix: str) -> None:
        guard_key = (module, router_var, prefix)
        if guard_key in recursion_guard:
            return
        recursion_guard.add(guard_key)
        parsed = load_module_parse(module)
        if not parsed:
            return
        mod_tree, mod_aliases, mod_router_aliases, _ = parsed
        module_file = module_file_for_name(module)
        router_file = posix_rel(module_file) if module_file else ""

        child_vars_map = {
            "v1_str": "/api/v1",
            "admin_api": "/api/v1/admin",
            "dealer_api": "/api/v1/dealer",
        }
        include_calls = parse_include_router_calls(
            mod_tree,
            owner_router_var=router_var,
            module_aliases=mod_aliases,
            router_aliases=mod_router_aliases,
            vars_map=child_vars_map,
        )
        if module_has_own_routes(module) and router_file:
            mounts[router_file].add(normalize_path(prefix or "/"))
        for (child_module, child_router), child_prefix in include_calls:
            merged = join_paths(prefix or "/", child_prefix or "/")
            recurse_module(child_module, child_router, merged)

    # Parse app/main.py in statement order so derived vars are available.
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            name = stmt.targets[0].id
            value = eval_string_expr(stmt.value, vars_map)
            if value:
                vars_map[name] = normalize_path(value)
            elif name == "v1_str":
                vars_map[name] = "/api/v1"
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr != "include_router":
                continue
            if not isinstance(call.func.value, ast.Name) or call.func.value.id != "app":
                continue
            if not call.args:
                continue
            target = resolve_include_target(call.args[0], module_aliases, router_aliases)
            if not target:
                continue
            prefix = ""
            for kw in call.keywords:
                if kw.arg == "prefix":
                    prefix = eval_string_expr(kw.value, vars_map)
                    break
            recurse_module(target[0], target[1], normalize_path(prefix or "/"))

    return {router_file: sorted(prefixes) for router_file, prefixes in mounts.items()}


def generate_phase0_route_manifest() -> tuple[list[RouteDescriptor], list[dict[str, Any]]]:
    route_files = iter_python_files(V1_API_DIR) + iter_python_files(ADMIN_API_DIR)
    static_routes: list[dict[str, Any]] = []
    for rf in route_files:
        static_routes.extend(parse_routes_from_file(rf))

    mount_prefixes = build_mount_prefixes()

    descriptors: list[RouteDescriptor] = []
    dedupe_guard: set[tuple[str, str, str, str, int]] = set()
    for r in static_routes:
        module_prefixes = mount_prefixes.get(r["router_file"], [])
        if not module_prefixes:
            synthetic = synthetic_unmounted_prefix(r["router_file"])
            unmounted_path = join_paths(synthetic, r["local_path"])
            manifest_unmounted_path = join_paths(
                f"/__unmounted__/{r['router_file'].replace('.py', '')}",
                r["local_path"],
            )
            key = (r["module"], r["function_name"], r["method"], normalize_path(manifest_unmounted_path), r["lineno"])
            if key not in dedupe_guard:
                dedupe_guard.add(key)
                descriptors.append(
                    RouteDescriptor(
                        module=r["module"],
                        router_file=r["router_file"],
                        function_name=r["function_name"],
                        method=r["method"],
                        raw_path=r["raw_path"],
                        path=normalize_path(manifest_unmounted_path),
                        candidate_mount_path=normalize_path(unmounted_path),
                        mounted=False,
                        has_auth=r["has_auth"],
                        does_direct_db=r["does_direct_db"],
                        calls_service=r["calls_service"],
                        calls_repository=r["calls_repository"],
                        response_model=r["response_model"],
                        lineno=r["lineno"],
                    )
                )
            continue

        for prefix in module_prefixes:
            final_path = join_paths(prefix, r["local_path"])
            key = (r["module"], r["function_name"], r["method"], normalize_path(final_path), r["lineno"])
            if key in dedupe_guard:
                continue
            dedupe_guard.add(key)
            descriptors.append(
                RouteDescriptor(
                    module=r["module"],
                    router_file=r["router_file"],
                    function_name=r["function_name"],
                    method=r["method"],
                    raw_path=r["raw_path"],
                    path=normalize_path(final_path),
                    candidate_mount_path=normalize_path(final_path),
                    mounted=True,
                    has_auth=r["has_auth"],
                    does_direct_db=r["does_direct_db"],
                    calls_service=r["calls_service"],
                    calls_repository=r["calls_repository"],
                    response_model=r["response_model"],
                    lineno=r["lineno"],
                )
            )

    dup_counter = Counter((d.method, d.path) for d in descriptors)
    duplicates = [
        {"method": method, "path": path, "count": count}
        for (method, path), count in dup_counter.items()
        if count > 1
    ]
    if duplicates:
        duplicate_preview = "\n".join(f"{d['method']} {d['path']} x{d['count']}" for d in duplicates[:20])
        raise RuntimeError(f"Duplicate method+path pairs found in phase0 route manifest:\n{duplicate_preview}")

    payload = {
        "generated_at": utc_now_iso(),
        "total_routes": len(descriptors),
        "live_routes": sum(1 for d in descriptors if d.mounted),
        "dead_routes": sum(1 for d in descriptors if not d.mounted),
        "duplicate_method_path_count": 0,
        "routes": [
            {
                "method": d.method,
                "path": d.path,
                "router_file": d.router_file,
                "function_name": d.function_name,
                "module": d.module,
                "mounted": d.mounted,
                "candidate_mount_path": d.candidate_mount_path,
                "has_auth": d.has_auth,
                "does_direct_db": d.does_direct_db,
                "calls_service": d.calls_service,
                "calls_repository": d.calls_repository,
                "response_model": d.response_model,
                "lineno": d.lineno,
            }
            for d in sorted(descriptors, key=lambda x: (x.path, x.method, x.router_file, x.function_name))
        ],
    }
    out_path = AUDIT_DIR / "phase0_route_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    return descriptors, payload["routes"]


def generate_route_diff(new_routes: list[dict[str, Any]]) -> None:
    baseline_path = AUDIT_DIR / "route_manifest.json"
    baseline = json.loads(baseline_path.read_text()) if baseline_path.exists() else {"routes": []}

    baseline_idx = {(r["method"], r["path"]): r for r in baseline.get("routes", [])}
    comparable_new_routes = [r for r in new_routes if r.get("mounted")]
    new_idx = {(r["method"], r.get("candidate_mount_path", r["path"])): r for r in comparable_new_routes}

    added = [new_idx[k] for k in sorted(new_idx.keys() - baseline_idx.keys())]
    removed = [baseline_idx[k] for k in sorted(baseline_idx.keys() - new_idx.keys())]
    changed: list[dict[str, Any]] = []
    for key in sorted(new_idx.keys() & baseline_idx.keys()):
        old = baseline_idx[key]
        new = new_idx[key]
        old_handler = old.get("handler", "")
        new_handler = f"{new['module']}:{new['function_name']}"
        if old_handler != new_handler:
            changed.append(
                {
                    "method": key[0],
                    "path": key[1],
                    "before": old_handler,
                    "after": new_handler,
                }
            )

    diff_payload = {
        "generated_at": utc_now_iso(),
        "baseline_file": posix_rel(baseline_path),
        "new_file": "docs/audit/phase0_route_manifest.json",
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "added": added,
        "removed": removed,
        "changed": changed,
    }
    (AUDIT_DIR / "phase0_route_diff.json").write_text(json.dumps(diff_payload, indent=2) + "\n")


def all_app_modules() -> tuple[list[Path], dict[str, Path], set[str], set[str]]:
    py_files = iter_python_files(APP_DIR)
    module_map: dict[str, Path] = {}
    package_modules: set[str] = set()
    for p in py_files:
        mod = module_from_path(p)
        module_map[mod] = p
        if p.name == "__init__.py":
            package_modules.add(mod)
    module_set = set(module_map.keys()) | package_modules
    return py_files, module_map, module_set, package_modules


def resolve_import_from(node: ast.ImportFrom, current_module: str, is_package: bool) -> str:
    module = node.module or ""
    if node.level == 0:
        return module
    pkg = current_module if is_package else current_module.rpartition(".")[0]
    rel = "." * node.level + module
    try:
        return importlib.util.resolve_name(rel, pkg)
    except Exception:
        return module


def build_import_graph() -> dict[str, list[str]]:
    py_files, module_map, module_set, _ = all_app_modules()
    graph: dict[str, set[str]] = {module: set() for module in module_map}

    for path in py_files:
        tree = read_ast(path)
        if tree is None:
            continue
        module = module_from_path(path)
        is_package = path.name == "__init__.py"

        deps = graph[module]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dep = alias.name
                    if dep.startswith("app"):
                        deps.add(dep)
            elif isinstance(node, ast.ImportFrom):
                resolved = resolve_import_from(node, module, is_package)
                if not resolved.startswith("app"):
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        deps.add(resolved)
                        continue
                    candidate = f"{resolved}.{alias.name}"
                    if candidate in module_set:
                        deps.add(candidate)
                    else:
                        deps.add(resolved)

        # Keep graph entries only under app namespace, without self-edges.
        cleaned = set()
        for dep in deps:
            if not dep.startswith("app"):
                continue
            if dep == module:
                continue
            cleaned.add(dep)
        graph[module] = cleaned

    out_graph = {k: sorted(v) for k, v in sorted(graph.items())}
    (AUDIT_DIR / "phase0_import_graph.json").write_text(json.dumps(out_graph, indent=2) + "\n")
    return out_graph


def strongly_connected_components(graph: dict[str, list[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    comps: list[list[str]] = []

    sys.setrecursionlimit(max(3000, len(graph) * 2))

    def visit(v: str) -> None:
        nonlocal index
        indices[v] = index
        lowlinks[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in graph.get(v, []):
            if w not in graph:
                continue
            if w not in indices:
                visit(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif w in on_stack:
                lowlinks[v] = min(lowlinks[v], indices[w])

        if lowlinks[v] == indices[v]:
            comp: list[str] = []
            while stack:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            comps.append(sorted(comp))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return comps


def enumerate_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    cyclic_sccs = []
    sccs = strongly_connected_components(graph)
    for comp in sccs:
        if len(comp) > 1:
            cyclic_sccs.append(comp)
        elif comp and comp[0] in graph and comp[0] in graph[comp[0]]:
            cyclic_sccs.append(comp)

    all_cycles: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    max_cycles = 5000

    def canon_cycle(nodes: list[str]) -> tuple[str, ...]:
        # nodes excludes repeated end-node
        rotations = []
        for seq in (nodes, list(reversed(nodes))):
            for i in range(len(seq)):
                rotations.append(tuple(seq[i:] + seq[:i]))
        return min(rotations)

    for comp in sorted(cyclic_sccs, key=lambda c: (len(c), c)):
        comp_set = set(comp)
        order = {n: i for i, n in enumerate(sorted(comp))}

        for start in sorted(comp):
            stack = [start]
            visited = {start}

            def dfs(cur: str) -> None:
                if len(all_cycles) >= max_cycles:
                    return
                for nxt in graph.get(cur, []):
                    if nxt not in comp_set:
                        continue
                    if nxt == start:
                        cyc_nodes = stack[:]
                        key = canon_cycle(cyc_nodes)
                        if key not in seen:
                            seen.add(key)
                            all_cycles.append(cyc_nodes + [start])
                    elif nxt not in visited and order[nxt] >= order[start]:
                        visited.add(nxt)
                        stack.append(nxt)
                        dfs(nxt)
                        stack.pop()
                        visited.remove(nxt)

            dfs(start)
            if len(all_cycles) >= max_cycles:
                break
        if len(all_cycles) >= max_cycles:
            break

    return sorted(all_cycles)


def generate_cycles_artifact(graph: dict[str, list[str]]) -> list[list[str]]:
    cycles = enumerate_cycles(graph)
    payload = {
        "generated_at": utc_now_iso(),
        "cycle_count": len(cycles),
        "cycles": [{"chain": cycle} for cycle in cycles],
    }
    (AUDIT_DIR / "phase0_cycles.json").write_text(json.dumps(payload, indent=2) + "\n")
    return cycles


def generate_boundary_violations() -> list[dict[str, Any]]:
    router_files = iter_python_files(V1_API_DIR) + iter_python_files(ADMIN_API_DIR)
    violations: list[dict[str, Any]] = []
    for path in router_files:
        tree = read_ast(path)
        if tree is None:
            continue
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("app.repositories"):
                        imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod.startswith("app.repositories"):
                    imports.add(mod)
        if imports:
            violations.append(
                {
                    "router_file": posix_rel(path),
                    "imports": sorted(imports),
                }
            )

    payload = {
        "generated_at": utc_now_iso(),
        "violation_count": len(violations),
        "violations": sorted(violations, key=lambda v: v["router_file"]),
    }
    (AUDIT_DIR / "phase0_boundary_violations.json").write_text(json.dumps(payload, indent=2) + "\n")
    return violations


def stem_from_module(module: str) -> str:
    return module.split(".")[-1]


def assign_partition(module: str, kind: str) -> str:
    stem = stem_from_module(module)
    lower_module = module.lower()

    if kind == "routers":
        if module.startswith("app.api.admin.") or module.startswith("app.api.v1.admin."):
            return "admin_platform_ops"
        if stem.startswith("admin_"):
            return "admin_platform_ops"
        if any(x in stem for x in ("dealer", "vendor")) or stem in {"branches", "organizations"}:
            return "dealer_portal"
        if stem in {"kyc", "fraud"}:
            return "kyc_fraud_compliance"
        if stem in {"rentals", "bookings", "swaps", "rentals_enhanced"}:
            return "customer_rental_swap"
        if stem in {"wallet", "wallet_enhanced", "payments", "payments_enhanced", "transactions", "settlements"}:
            return "finance_wallet_payments"
        if stem in {
            "logistics",
            "drivers",
            "routes",
            "orders",
            "orders_realtime",
            "manifests",
            "stock",
            "inventory",
            "warehouse_structure",
            "warehouses",
            "vehicles",
        } or module.endswith(".endpoints.warehouse"):
            return "logistics_supply"
        if stem in {
            "batteries",
            "battery_catalog",
            "stations",
            "station_monitoring",
            "maintenance",
            "telematics",
            "telemetry",
            "iot",
            "location",
            "locations",
        }:
            return "iot_telematics_system"
        if stem in {"auth", "customer_auth", "sessions", "users", "profile", "passkeys", "roles", "role_rights", "menus"}:
            return "identity_access"
        if stem in {"notifications", "notifications_enhanced", "support", "support_enhanced", "favorites", "faqs", "promo", "catalog", "i18n"}:
            return "comms_content_engagement"
        if stem in {"analytics", "analytics_enhanced", "dashboard", "audit", "ml", "system", "utils", "screens"} or module.startswith(
            "app.api.v1.analytics."
        ):
            return "admin_platform_ops"
        return "admin_platform_ops"

    if kind == "repositories":
        if stem in {"battery_repository", "station_repository"}:
            return "iot_telematics_system"
        if stem in {"payment_repository", "wallet_repository"}:
            return "finance_wallet_payments"
        if stem in {"dealer", "branch", "organization"}:
            return "dealer_portal"
        if stem in {"stock", "warehouse"}:
            return "logistics_supply"
        if stem in {"rental_repository"}:
            return "customer_rental_swap"
        if stem in {"user_repository"}:
            return "identity_access"
        if stem in {"notification_repository"}:
            return "comms_content_engagement"
        if stem in {"analytics_dashboard_repository"}:
            return "admin_platform_ops"
        return "platform_core"

    if kind == "models":
        if stem in {"__init__", "all", "enums", "idempotency"}:
            return "platform_core"
        if stem in {"admin_user", "admin_group", "analytics", "analytics_dashboard", "audit_log", "alert", "batch_job", "system", "revenue_report"}:
            return "admin_platform_ops"
        if stem in {"user", "session", "token", "passkey", "otp", "password_history", "oauth", "biometric", "device", "device_fingerprint", "login_history", "security_question", "two_factor_auth", "user_history", "user_profile", "api_key", "staff", "rbac", "roles", "role_right", "menu", "driver_profile"}:
            return "identity_access"
        if stem in {"kyc", "kyc_verification", "dealer_kyc", "video_kyc", "fraud"}:
            return "kyc_fraud_compliance"
        if stem in {"rental", "rental_event", "rental_modification", "battery_reservation", "swap", "swap_suggestion", "late_fee", "cart", "membership", "return_request"}:
            return "customer_rental_swap"
        if stem in {"financial", "payment", "payment_method", "refund", "chargeback", "commission", "settlement", "settlement_dispute", "invoice"}:
            return "finance_wallet_payments"
        if stem in {"dealer", "dealer_inventory", "dealer_promotion", "branch", "organization", "vendor"}:
            return "dealer_portal"
        if stem in {"logistics", "delivery_assignment", "delivery_route", "manifest", "warehouse", "vehicle", "inventory", "inventory_audit", "stock", "stock_movement", "station_stock", "geofence", "gps_log", "order", "order_realtime_outbox", "ecommerce"}:
            return "logistics_supply"
        if stem in {"battery", "battery_catalog", "battery_health", "battery_health_log", "charging_queue", "station", "station_heartbeat", "station_metrics", "maintenance", "maintenance_checklist", "telematics", "telemetry", "iot", "bess", "location"}:
            return "iot_telematics_system"
        if stem in {"notification", "notification_admin", "notification_outbox", "notification_preference", "banner", "blog", "faq", "favorite", "feedback", "promo_code", "referral", "review", "legal", "media", "support", "search_history", "i18n", "catalog"}:
            return "comms_content_engagement"
        return "platform_core"

    if kind == "services":
        if stem in {"background_runtime_service", "bootstrap_service", "distributed_cache_service", "email_service", "event_stream_service", "feature_flag_service", "maps_service", "mqtt_service", "redis_service", "request_audit_queue", "security_service", "sms_service", "startup_diagnostics_service", "storage_service", "timescale_service", "websocket_service", "workflow_automation_service"}:
            return "platform_core"
        if stem in {"auth_service", "apple_auth_service", "otp_service", "passkey_service", "password_service", "rbac_service", "role_service", "role_right_service", "token_service", "user_service", "user_state_service", "menu_service"}:
            return "identity_access"
        if stem in {"kyc_service", "dealer_kyc_service", "video_kyc_service", "fraud_service", "fraud_compute_service", "ml_fraud_service"}:
            return "kyc_fraud_compliance"
        if stem in {"booking_service", "cart_service", "late_fee_service", "membership_service", "rental_alert_service", "rental_service", "swap_service"}:
            return "customer_rental_swap"
        if stem in {"commission_service", "dispute_service", "financial_report_service", "financial_service", "idempotency_service", "invoice_service", "payment_method_service", "payment_service", "razorpay_webhook_service", "receipt_service", "settlement_service", "wallet_service"}:
            return "finance_wallet_payments"
        if stem in {"branch", "dealer_analytics_service", "dealer_ledger_service", "dealer_service", "dealer_station_service", "organization"}:
            return "dealer_portal"
        if stem in {"driver_service", "forecasting_service", "geofence_service", "gps_service", "inventory_service", "logistics_service", "order_realtime_outbox_service", "order_service", "route_service", "stock", "warehouse"}:
            return "logistics_supply"
        if stem in {"battery_batch_service", "battery_consistency", "battery_service", "catalog_service", "charging_service", "demand_predictor", "iot_service", "maintenance_service", "station_metrics_service", "station_service", "telematics_ingest_service", "telematics_service"}:
            return "iot_telematics_system"
        if stem in {"campaign_service", "chat_service", "ecommerce_service", "fcm_service", "i18n_service", "notification_outbox_service", "notification_service", "pdf_service", "promo_service", "qr_service", "referral_service", "review_service", "support_service"}:
            return "comms_content_engagement"
        if stem in {"admin_analytics_service", "analytics_service", "analytics_dashboard_service", "analytics_report_service", "audit_service", "ml_service"} or lower_module.startswith("app.services.analytics."):
            return "admin_platform_ops"
        return "platform_core"

    if kind == "schemas":
        if stem in {"__init__", "common", "input_contracts"}:
            return "platform_core"
        if stem in {"admin_group", "admin_user", "analytics", "audit_log", "dashboard", "job", "ui_config", "system", "alert"} or lower_module.startswith("app.schemas.analytics."):
            return "admin_platform_ops"
        if stem in {"auth", "device", "menu", "rbac", "role", "role_right", "session", "staff", "user", "user_extended"}:
            return "identity_access"
        if stem in {"kyc", "kyc_admin", "fraud", "video_kyc"}:
            return "kyc_fraud_compliance"
        if stem in {"booking", "rental", "rental_event", "swap"}:
            return "customer_rental_swap"
        if stem in {"commission", "finance_ops", "financial", "invoice", "payment", "settlement", "settlement_dispute", "wallet"}:
            return "finance_wallet_payments"
        if stem in {"branch", "dealer", "dealer_inventory", "dealer_kyc", "dealer_ledger", "dealer_promotion", "dealer_user", "organization", "vendor"}:
            return "dealer_portal"
        if stem in {"delivery", "inventory", "logistics", "manifest", "order", "route", "stock", "station_stock", "vehicle", "warehouse", "warehouse_structure"}:
            return "logistics_supply"
        if stem in {"battery", "battery_catalog", "battery_health", "bess", "iot", "location", "maintenance", "station", "station_monitoring", "telematics"}:
            return "iot_telematics_system"
        if stem in {"banner", "blog", "catalog", "ecommerce", "faq", "feedback", "legal", "media", "notification", "notification_admin", "notification_preference", "promo", "review", "support"}:
            return "comms_content_engagement"
        return "platform_core"

    raise ValueError(f"Unknown kind: {kind}")


def collect_domain_inventory() -> dict[str, dict[str, list[str]]]:
    grouped = {p: {"models": [], "services": [], "repositories": [], "schemas": [], "routers": []} for p in PARTITIONS}

    kind_roots = {
        "models": APP_DIR / "models",
        "services": APP_DIR / "services",
        "repositories": APP_DIR / "repositories",
        "schemas": APP_DIR / "schemas",
        "routers": APP_DIR / "api",
    }

    router_files = iter_python_files(V1_API_DIR) + iter_python_files(ADMIN_API_DIR)
    kind_files: dict[str, list[Path]] = {
        "models": iter_python_files(kind_roots["models"]),
        "services": iter_python_files(kind_roots["services"]),
        "repositories": iter_python_files(kind_roots["repositories"]),
        "schemas": iter_python_files(kind_roots["schemas"]),
        "routers": router_files,
    }

    assigned_index: dict[str, str] = {}
    for kind, files in kind_files.items():
        for path in files:
            module = module_from_path(path)
            file_id = posix_rel(path)
            owner = assign_partition(module, kind)
            grouped[owner][kind].append(file_id)
            if file_id in assigned_index:
                raise RuntimeError(f"File assigned more than once across kinds: {file_id}")
            assigned_index[file_id] = owner

    for partition in PARTITIONS:
        for kind in ("models", "services", "repositories", "schemas", "routers"):
            grouped[partition][kind] = sorted(set(grouped[partition][kind]))
    return grouped


def parse_old_domain_entries() -> set[str]:
    src = (DOCS_DIR / "domains.yaml").read_text()
    entries: set[str] = set()
    for line in src.splitlines():
        match = re.match(r"^\s*-\s+(app\.[A-Za-z0-9_.]+)\s*$", line.strip())
        if match:
            entries.add(match.group(1))
    return entries


def render_domains_yaml(grouped: dict[str, dict[str, list[str]]]) -> str:
    lines: list[str] = []
    lines.append("# Repaired domain ownership map")
    lines.append(f"# Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}")
    lines.append("# Authoritative for modernization phases")
    lines.append("domains:")
    for partition in PARTITIONS:
        lines.append(f"  {partition}:")
        lines.append(f"    description: {PARTITION_DESCRIPTIONS[partition]}")
        for kind in ("models", "services", "repositories", "schemas", "routers"):
            lines.append(f"    {kind}:")
            modules = grouped[partition][kind]
            if modules:
                for module in modules:
                    lines.append(f"      - {module}")
            else:
                lines.append("      []")
    lines.append("")
    return "\n".join(lines)


def generate_repaired_domains_yaml() -> tuple[dict[str, dict[str, list[str]]], dict[str, Any]]:
    grouped = collect_domain_inventory()

    current_entries: set[str] = set()
    for partition in PARTITIONS:
        for kind in ("models", "services", "repositories", "schemas", "routers"):
            current_entries.update(grouped[partition][kind])

    current_module_entries = {
        module_from_path(REPO_ROOT / entry)
        for entry in current_entries
        if entry.startswith("app/")
    }

    old_entries = parse_old_domain_entries()
    stale_entries = sorted(e for e in old_entries if e not in current_module_entries)

    # Explicitly ensure stale station_models reference is gone.
    if "app.models.station_models" in current_module_entries:
        raise RuntimeError("Stale app.models.station_models is still present in repaired map.")

    # Ensure all target files are covered exactly once.
    expected_files: set[str] = set()
    expected_files.update(posix_rel(p) for p in iter_python_files(APP_DIR / "models"))
    expected_files.update(posix_rel(p) for p in iter_python_files(APP_DIR / "services"))
    expected_files.update(posix_rel(p) for p in iter_python_files(APP_DIR / "repositories"))
    expected_files.update(posix_rel(p) for p in iter_python_files(APP_DIR / "schemas"))
    expected_files.update(posix_rel(p) for p in iter_python_files(V1_API_DIR))
    expected_files.update(posix_rel(p) for p in iter_python_files(ADMIN_API_DIR))

    missing = sorted(expected_files - current_entries)
    extra = sorted(current_entries - expected_files)
    if missing:
        raise RuntimeError(f"Unassigned entries in repaired domain map: {missing[:20]}")
    if extra:
        raise RuntimeError(f"Unexpected entries in repaired domain map: {extra[:20]}")

    repaired_text = render_domains_yaml(grouped)
    out_path = AUDIT_DIR / "phase0_domains_repaired.yaml"
    out_path.write_text(repaired_text)

    stats = {
        "stale_entries_resolved_count": len(stale_entries),
        "stale_entries_resolved": stale_entries,
        "total_entries_assigned": len(current_entries),
    }
    return grouped, stats


def model_classes_by_module(model_files: list[Path]) -> dict[str, list[str]]:
    by_module: dict[str, list[str]] = {}
    for path in model_files:
        tree = read_ast(path)
        if tree is None:
            continue
        module = module_from_path(path)
        classes: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = {call_target_name(base).split(".")[-1] for base in node.bases}
            has_table_kw = any(kw.arg == "table" for kw in node.keywords)
            if "SQLModel" in base_names or has_table_kw:
                classes.append(node.name)
        if classes:
            by_module[module] = sorted(set(classes))
    return by_module


def collect_imported_models(
    app_files: list[Path],
    model_class_map: dict[str, list[str]],
) -> dict[tuple[str, str], set[str]]:
    imports_for_model: dict[tuple[str, str], set[str]] = defaultdict(set)
    model_modules = set(model_class_map.keys())

    for path in app_files:
        tree = read_ast(path)
        if tree is None:
            continue
        importer = module_from_path(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in model_modules:
                    for alias in node.names:
                        if alias.name == "*":
                            for cls in model_class_map[module]:
                                imports_for_model[(module, cls)].add(importer)
                        elif alias.name in model_class_map[module]:
                            imports_for_model[(module, alias.name)].add(importer)
                elif module == "app.models":
                    for alias in node.names:
                        for mm, classes in model_class_map.items():
                            if alias.name in classes:
                                imports_for_model[(mm, alias.name)].add(importer)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if module in model_modules:
                        for cls in model_class_map[module]:
                            imports_for_model[(module, cls)].add(importer)
    return imports_for_model


def contains_model_name(node: ast.AST, class_names: set[str]) -> set[str]:
    found: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in class_names:
            found.add(sub.id)
    return found


def detect_mutated_models_in_file(path: Path, model_names: set[str]) -> set[str]:
    tree = read_ast(path)
    if tree is None:
        return set()
    mutated: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            if node.func.id in model_names:
                mutated.add(node.func.id)
            if node.func.id in {"insert", "update", "delete"} and node.args:
                mutated.update(contains_model_name(node.args[0], model_names))
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in {"add_all", "bulk_insert_mappings", "bulk_save_objects", "bulk_update_mappings", "delete", "merge"}:
                for arg in node.args:
                    mutated.update(contains_model_name(arg, model_names))
    return mutated


def domain_module_members(grouped: dict[str, dict[str, list[str]]]) -> dict[str, set[str]]:
    members: dict[str, set[str]] = {}
    for partition, sections in grouped.items():
        all_modules = set()
        for kind in ("models", "services", "repositories", "schemas", "routers"):
            for file_id in sections[kind]:
                all_modules.add(module_from_path(REPO_ROOT / file_id))
        members[partition] = all_modules
    return members


def generate_model_coupling(grouped: dict[str, dict[str, list[str]]]) -> tuple[list[dict[str, Any]], int]:
    model_files = iter_python_files(APP_DIR / "models")
    model_class_map = model_classes_by_module(model_files)
    app_files = iter_python_files(APP_DIR)
    imports_map = collect_imported_models(app_files, model_class_map)
    partition_members = domain_module_members(grouped)

    model_owner_by_module: dict[str, str] = {}
    for partition in PARTITIONS:
        for file_id in grouped[partition]["models"]:
            mod = module_from_path(REPO_ROOT / file_id)
            model_owner_by_module[mod] = partition

    model_names = {cls for classes in model_class_map.values() for cls in classes}
    file_mutations_cache: dict[str, set[str]] = {}
    coupling_rows: list[dict[str, Any]] = []
    unowned_models = 0

    for model_module in sorted(model_class_map):
        owner = model_owner_by_module.get(model_module)
        if not owner:
            unowned_models += len(model_class_map[model_module])
        owner_members = partition_members.get(owner or "", set())
        for cls in model_class_map[model_module]:
            imported_by = imports_map.get((model_module, cls), set())
            imported_outside = sorted(m for m in imported_by if m not in owner_members and m != model_module)

            mutated_outside: list[str] = []
            for importer in imported_outside:
                importer_path = REPO_ROOT / (importer.replace(".", "/") + ".py")
                if not importer_path.exists():
                    continue
                if importer not in file_mutations_cache:
                    file_mutations_cache[importer] = detect_mutated_models_in_file(importer_path, model_names)
                if cls in file_mutations_cache[importer]:
                    mutated_outside.append(importer)

            coupling_rows.append(
                {
                    "model": cls,
                    "model_module": model_module,
                    "owned_by": owner or "UNASSIGNED",
                    "imported_outside_domain_by": imported_outside,
                    "mutated_outside_domain_by": sorted(set(mutated_outside)),
                    "is_mutated_outside_domain": bool(mutated_outside),
                }
            )

    payload = {
        "generated_at": utc_now_iso(),
        "total_models": len(coupling_rows),
        "unowned_models": unowned_models,
        "rows": coupling_rows,
    }
    (AUDIT_DIR / "phase0_model_coupling.json").write_text(json.dumps(payload, indent=2) + "\n")
    return coupling_rows, unowned_models


def build_dead_flow_inventory(route_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    live_keys = {(r["method"], r["path"]) for r in route_rows if r["mounted"]}
    rows_by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in route_rows:
        rows_by_file[row["router_file"]].append(row)

    results: list[dict[str, Any]] = []
    for rel in TARGET_DEAD_FLOW_FILES:
        routes = rows_by_file.get(rel, [])
        conflicts = []
        for r in routes:
            candidate_path = r.get("candidate_mount_path", r["path"])
            if (r["method"], candidate_path) in live_keys:
                conflicts.append({"method": r["method"], "path": candidate_path})

        stem = Path(rel).stem.replace("_", "-")
        if "/api/admin/" in rel:
            default_prefix = f"/api/v1/admin/{stem}"
        else:
            default_prefix = f"/api/v1/{stem}"

        status = "safe_to_mount" if not conflicts else "needs_conflict_resolution"
        results.append(
            {
                "file": rel,
                "route_count": len(routes),
                "path_conflicts_with_live": sorted(conflicts, key=lambda x: (x["path"], x["method"])),
                "recommended_prefix": default_prefix,
                "status": status,
            }
        )

    payload = {
        "generated_at": utc_now_iso(),
        "dead_flow_files": results,
    }
    (AUDIT_DIR / "phase0_dead_flows.json").write_text(json.dumps(payload, indent=2) + "\n")
    return results


def extract_contract_status() -> dict[str, Any]:
    contracts = [
        {
            "router_callsite": "app/api/v1/batteries.py:136",
            "target": "MaintenanceService.get_maintenance_history",
        },
        {
            "router_callsite": "app/api/v1/stations.py:194",
            "target": "MaintenanceService.get_maintenance_schedule",
        },
        {
            "router_callsite": "app/api/v1/logistics.py:82",
            "target": "DriverService.get_driver_dashboard_stats",
        },
        {
            "router_callsite": "app/api/v1/passkeys.py:159",
            "target": "AuthService.create_session",
        },
    ]
    status = []
    for item in contracts:
        cls_name, method_name = item["target"].split(".")
        module_name = {
            "MaintenanceService": "app.services.maintenance_service",
            "DriverService": "app.services.driver_service",
            "AuthService": "app.services.auth_service",
        }[cls_name]

        file_path = module_file_for_name(module_name)
        ok = False
        if file_path:
            tree = read_ast(file_path)
            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == cls_name:
                        ok = any(
                            isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == method_name
                            for sub in node.body
                        )
                        break
        status.append({**item, "implemented": ok})
    return {"contracts": status, "all_implemented": all(s["implemented"] for s in status)}


def write_phase0_freeze_manifest(
    route_rows: list[dict[str, Any]],
    cycles: list[list[str]],
    boundary_violations: list[dict[str, Any]],
    unowned_models: int,
    stale_stats: dict[str, Any],
    dead_flow_rows: list[dict[str, Any]],
) -> None:
    contract_status = extract_contract_status()

    total_live = sum(1 for r in route_rows if r["mounted"])
    total_dead = sum(1 for r in route_rows if not r["mounted"])
    dead_files_missing = [x["file"] for x in dead_flow_rows if x["route_count"] == 0]

    lines = []
    lines.append("# Phase 0 Freeze Manifest")
    lines.append("")
    lines.append(f"- Generated at: `{utc_now_iso()}`")
    lines.append(f"- Total live routes: **{total_live}**")
    lines.append(f"- Total dead routes: **{total_dead}**")
    lines.append(f"- Total cycles: **{len(cycles)}**")
    lines.append(f"- Total boundary violations (router -> repository imports): **{len(boundary_violations)}**")
    lines.append(f"- Total unowned models: **{unowned_models}**")
    lines.append(f"- Total stale domain entries resolved: **{stale_stats['stale_entries_resolved_count']}**")
    lines.append("")
    lines.append("## Contract Gaps Status")
    for c in contract_status["contracts"]:
        status = "PASS" if c["implemented"] else "FAIL"
        lines.append(f"- {status}: `{c['router_callsite']}` -> `{c['target']}`")
    lines.append("")
    lines.append(f"- All 4 contract methods implemented: **{contract_status['all_implemented']}**")
    lines.append("")
    lines.append("## Dead Flow Inventory Coverage")
    for row in dead_flow_rows:
        lines.append(
            f"- `{row['file']}`: routes={row['route_count']} status=`{row['status']}` conflicts={len(row['path_conflicts_with_live'])}"
        )
    if dead_files_missing:
        lines.append("")
        lines.append("## Warning")
        lines.append(f"- These configured dead-flow files were not found in tree: {', '.join(dead_files_missing)}")
    lines.append("")

    (AUDIT_DIR / "phase0_freeze_manifest.md").write_text("\n".join(lines))


def load_phase0_domains_map() -> dict[str, dict[str, list[str]]]:
    repaired = AUDIT_DIR / "phase0_domains_repaired.yaml"
    if not repaired.exists():
        raise RuntimeError("Missing docs/audit/phase0_domains_repaired.yaml. Run phase0 first.")

    grouped: dict[str, dict[str, list[str]]] = {}
    current_partition = ""
    current_kind = ""
    for raw in repaired.read_text().splitlines():
        line = raw.rstrip()
        if re.match(r"^\s{2}[a-z_]+:\s*$", line) and not line.strip().startswith(("description", "models", "services", "repositories", "schemas", "routers")):
            current_partition = line.strip().rstrip(":")
            grouped[current_partition] = {"models": [], "services": [], "repositories": [], "schemas": [], "routers": []}
            current_kind = ""
            continue
        kind_match = re.match(r"^\s{4}(models|services|repositories|schemas|routers):\s*$", line)
        if kind_match:
            current_kind = kind_match.group(1)
            continue
        item_match = re.match(r"^\s{6}-\s+(.+)$", line)
        if item_match and current_partition and current_kind:
            value = item_match.group(1).strip()
            if value != "[]":
                grouped[current_partition][current_kind].append(value)
    return grouped


def response_envelope_type(response_model: str) -> str:
    text = (response_model or "").strip()
    if not text:
        return "raw"
    if "PaginatedResponse" in text or "DataResponseWithPagination" in text:
        return "paginated"
    if "DataResponse" in text or "StandardResponse" in text:
        return "standard"
    return "raw"


def generate_partition_ownership_doc(grouped: dict[str, dict[str, list[str]]]) -> None:
    # Locked contract text intentionally mirrors the modernization spec.
    sections = {
        "identity_access": {
            "owns": "User, Session, RefreshToken, Passkey, OTP, AuthLog models and all schemas/services/repositories/routers for identity and authentication flows. Owns JWT encode/decode contract.",
            "depends_on": "platform_core",
            "exposes": "UserService.get_by_id, UserService.get_by_phone, AuthService.verify_token, AuthService.get_current_user",
            "forbidden": "Must not import from any other partition. Other partitions must use exposed interfaces only for user context.",
        },
        "kyc_fraud_compliance": {
            "owns": "KYCDocument, KYCStatus, FraudFlag, ComplianceEvent model space and all KYC/fraud/compliance routes/services/schemas.",
            "depends_on": "platform_core, identity_access (UserService.get_by_id)",
            "exposes": "KYCService.get_status(user_id), KYCService.is_verified(user_id), FraudService.flag_event(user_id, event_type)",
            "forbidden": "Must not write User model directly. Emit events for status changes instead of inline cross-partition mutations.",
        },
        "customer_rental_swap": {
            "owns": "Rental, Swap, RentalPlan, BatteryAssignment, RentalEvent model space and rental lifecycle APIs.",
            "depends_on": "platform_core, identity_access, iot_telematics_system, finance_wallet_payments",
            "exposes": "RentalService.get_active_rental(user_id), RentalService.get_rental_by_id(rental_id), SwapService.get_swap_history(user_id)",
            "forbidden": "Must not write Wallet/Payment models directly; no direct telemetry table queries; no dealer flow mutation.",
        },
        "finance_wallet_payments": {
            "owns": "Wallet, Transaction, PaymentOrder, Refund, Settlement, WalletLedger model space and payment lifecycle APIs.",
            "depends_on": "platform_core, identity_access",
            "exposes": "WalletService.get_balance, WalletService.deduct, WalletService.credit, PaymentService.initiate, PaymentService.get_status",
            "forbidden": "Must not import rental/dealer/IoT models. Every balance mutation must write ledger in same transaction.",
        },
        "dealer_portal": {
            "owns": "Dealer, DealerDocument, DealerKYC, DealerCommission, DealerStation model space and dealer portal workflows.",
            "depends_on": "platform_core, identity_access, kyc_fraud_compliance, finance_wallet_payments",
            "exposes": "DealerService.get_by_id, DealerService.get_stations, CommissionService.get_summary",
            "forbidden": "Must not directly modify rental or customer wallet records.",
        },
        "logistics_supply": {
            "owns": "LogisticsOrder, Driver, DriverAssignment, Vehicle, DeliveryEvent, InventoryTransfer model space and logistics APIs.",
            "depends_on": "platform_core, identity_access, iot_telematics_system",
            "exposes": "LogisticsService.get_order(order_id), DriverService.get_driver_dashboard_stats(driver_id), InventoryService.get_stock(station_id)",
            "forbidden": "Must not initiate payments and must not modify rental state.",
        },
        "iot_telematics_system": {
            "owns": "Battery, Station, BatteryTelemetry, StationTelemetry, MaintenanceRecord, BatteryHealth model space and device-state APIs.",
            "depends_on": "platform_core",
            "exposes": "BatteryService.get_available, BatteryService.get_by_id, StationService.get_by_id, StationService.get_nearby, MaintenanceService.get_maintenance_history, MaintenanceService.get_maintenance_schedule",
            "forbidden": "No imports from business partitions. This partition is a state provider only and does not initiate finance/rental operations.",
        },
        "comms_content_engagement": {
            "owns": "Notification, PushToken, EmailLog, SMSLog, ContentTemplate, AppVersion, FAQ model space and content/notification APIs.",
            "depends_on": "platform_core",
            "exposes": "NotificationService.send(user_id, event_type, payload)",
            "forbidden": "Must not import business partitions directly. Consume inputs via internal events; avoid storing unnecessary PII/financial data.",
        },
        "admin_platform_ops": {
            "owns": "AdminUser, AdminRole, AdminPermission, AuditLog, AlertRule, AnalyticsSnapshot, BulkOperation model space and admin APIs.",
            "depends_on": "platform_core, identity_access, all partitions (read interfaces only)",
            "exposes": "None (consumer partition)",
            "forbidden": "Must not directly mutate records owned by other partitions. All cross-domain writes must go through owner service interfaces.",
        },
        "platform_core": {
            "owns": "app/core and shared infrastructure primitives: config, db, redis, security, middleware, exceptions, events, standard envelopes.",
            "depends_on": "None",
            "exposes": "get_db, get_redis, get_current_user, settings, AppException hierarchy, event bus, StandardResponse, PaginatedResponse",
            "forbidden": "No business logic and no imports from business partitions.",
        },
    }

    lines: list[str] = []
    lines.append("# Partition Ownership Contract")
    lines.append("")
    lines.append("Locked ownership contract for Phases 3-7.")
    lines.append("")
    for partition in PARTITIONS:
        info = sections[partition]
        lines.append(f"## Partition: {partition}")
        lines.append("")
        lines.append("| Field | Contract |")
        lines.append("|---|---|")
        lines.append(f"| Owns | {info['owns']} |")
        lines.append(f"| Depends on | {info['depends_on']} |")
        lines.append(f"| Exposes | {info['exposes']} |")
        lines.append(f"| Forbidden | {info['forbidden']} |")
        lines.append(f"| Owned models/services/repositories/schemas/routers (count) | {sum(len(grouped[partition][k]) for k in ('models','services','repositories','schemas','routers'))} |")
        lines.append("")

    (DOCS_DIR / "PARTITION_OWNERSHIP.md").write_text("\n".join(lines))


def generate_inter_partition_graph() -> None:
    deps = {
        "identity_access": {"platform_core"},
        "kyc_fraud_compliance": {"platform_core", "identity_access"},
        "customer_rental_swap": {"platform_core", "identity_access", "iot_telematics_system", "finance_wallet_payments"},
        "finance_wallet_payments": {"platform_core", "identity_access"},
        "dealer_portal": {"platform_core", "identity_access", "kyc_fraud_compliance", "finance_wallet_payments"},
        "logistics_supply": {"platform_core", "identity_access", "iot_telematics_system"},
        "iot_telematics_system": {"platform_core"},
        "comms_content_engagement": {"platform_core"},
        "admin_platform_ops": {"platform_core", "identity_access", "kyc_fraud_compliance", "customer_rental_swap", "finance_wallet_payments", "dealer_portal", "logistics_supply", "iot_telematics_system", "comms_content_engagement"},
        "platform_core": set(),
    }

    # Cycle check via DFS
    visiting: set[str] = set()
    visited: set[str] = set()
    cycle_paths: list[list[str]] = []

    def dfs(node: str, stack: list[str]) -> None:
        if node in visiting:
            i = stack.index(node)
            cycle_paths.append(stack[i:] + [node])
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for dep in sorted(deps[node]):
            dfs(dep, stack)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for n in PARTITIONS:
        if n not in visited:
            dfs(n, [])
    if cycle_paths:
        raise RuntimeError(f"Partition dependency graph is cyclic: {cycle_paths[0]}")

    lines: list[str] = []
    lines.append("# Inter-Partition Dependency Graph")
    lines.append("")
    lines.append("Graph is validated acyclic.")
    lines.append("")
    lines.append("## Edge List")
    lines.append("")
    for src in PARTITIONS:
        if deps[src]:
            lines.append(f"- `{src}` -> {', '.join(f'`{d}`' for d in sorted(deps[src]))}")
        else:
            lines.append(f"- `{src}` -> (none)")
    lines.append("")
    lines.append("## Mermaid")
    lines.append("")
    lines.append("```mermaid")
    lines.append("graph TD")
    for src in PARTITIONS:
        if not deps[src]:
            lines.append(f'  "{src}"')
        for dep in sorted(deps[src]):
            lines.append(f'  "{src}" --> "{dep}"')
    lines.append("```")
    lines.append("")
    lines.append("Acyclic assertion: **PASS**")
    lines.append("")

    (DOCS_DIR / "INTER_PARTITION_GRAPH.md").write_text("\n".join(lines))


def generate_flow_catalog(grouped: dict[str, dict[str, list[str]]]) -> None:
    manifest = json.loads((AUDIT_DIR / "phase0_route_manifest.json").read_text())
    routes = manifest["routes"]

    router_owner: dict[str, str] = {}
    for partition, sections in grouped.items():
        for router_file in sections["routers"]:
            router_owner[router_file] = partition

    missing_owner = []
    lines: list[str] = []
    lines.append("# Flow Catalog")
    lines.append("")
    lines.append("| method | path | partition_owner | auth_required | response_envelope_type | mounted | router_file |")
    lines.append("|---|---|---|---:|---|---:|---|")
    for r in sorted(routes, key=lambda x: (x["path"], x["method"], x["router_file"], x["function_name"])):
        owner = router_owner.get(r["router_file"])
        if not owner:
            missing_owner.append(r["router_file"])
            owner = "UNASSIGNED"
        display_path = r.get("candidate_mount_path", r["path"])
        lines.append(
            f"| {r['method']} | {display_path} | {owner} | {str(bool(r['has_auth'])).lower()} | {response_envelope_type(r.get('response_model', ''))} | {str(bool(r['mounted'])).lower()} | {r['router_file']} |"
        )

    if missing_owner:
        uniq = sorted(set(missing_owner))
        raise RuntimeError(f"Flow catalog has unassigned route owners for files: {uniq}")

    lines.append("")
    lines.append("## Dead Flow Pre-Assignments")
    lines.append("")
    lines.append("| file | partition_owner |")
    lines.append("|---|---|")
    for dead_file in TARGET_DEAD_FLOW_FILES:
        owner = router_owner.get(dead_file)
        if not owner:
            pseudo_module = dead_file.replace("/", ".").replace(".py", "")
            owner = assign_partition(pseudo_module, "routers")
        lines.append(f"| {dead_file} | {owner} |")

    (DOCS_DIR / "FLOW_CATALOG.md").write_text("\n".join(lines) + "\n")


def run_phase0() -> None:
    descriptors, route_rows = generate_phase0_route_manifest()
    generate_route_diff(route_rows)
    import_graph = build_import_graph()
    cycles = generate_cycles_artifact(import_graph)
    boundary_violations = generate_boundary_violations()
    grouped, stale_stats = generate_repaired_domains_yaml()
    _, unowned_models = generate_model_coupling(grouped)
    dead_flow_rows = build_dead_flow_inventory(route_rows)
    write_phase0_freeze_manifest(
        route_rows=route_rows,
        cycles=cycles,
        boundary_violations=boundary_violations,
        unowned_models=unowned_models,
        stale_stats=stale_stats,
        dead_flow_rows=dead_flow_rows,
    )

    print("Phase 0 artifacts generated:")
    print(f"  - {AUDIT_DIR / 'phase0_route_manifest.json'}")
    print(f"  - {AUDIT_DIR / 'phase0_route_diff.json'}")
    print(f"  - {AUDIT_DIR / 'phase0_import_graph.json'}")
    print(f"  - {AUDIT_DIR / 'phase0_cycles.json'}")
    print(f"  - {AUDIT_DIR / 'phase0_boundary_violations.json'}")
    print(f"  - {AUDIT_DIR / 'phase0_model_coupling.json'}")
    print(f"  - {AUDIT_DIR / 'phase0_domains_repaired.yaml'}")
    print(f"  - {AUDIT_DIR / 'phase0_dead_flows.json'}")
    print(f"  - {AUDIT_DIR / 'phase0_freeze_manifest.md'}")
    print(f"  - route duplicates checked: 0")
    print(f"  - cycles found: {len(cycles)}")
    print(f"  - boundary violations: {len(boundary_violations)}")
    print(f"  - static route declarations parsed: {len(descriptors)}")


def run_phase1() -> None:
    grouped = load_phase0_domains_map()
    generate_partition_ownership_doc(grouped)
    generate_inter_partition_graph()
    generate_flow_catalog(grouped)
    print("Phase 1 artifacts generated:")
    print(f"  - {DOCS_DIR / 'PARTITION_OWNERSHIP.md'}")
    print(f"  - {DOCS_DIR / 'INTER_PARTITION_GRAPH.md'}")
    print(f"  - {DOCS_DIR / 'FLOW_CATALOG.md'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate WEZU modernization artifacts")
    parser.add_argument("phase", choices=["phase0", "phase1"], help="Artifact phase to generate")
    args = parser.parse_args()

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    if args.phase == "phase0":
        run_phase0()
        return 0
    if args.phase == "phase1":
        run_phase1()
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
