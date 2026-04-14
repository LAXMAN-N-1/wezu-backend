#!/usr/bin/env python3
"""
Generate a machine-readable route manifest and detect duplicate registrations.

Usage:
    python scripts/generate_route_manifest.py          # write manifest + print summary
    python scripts/generate_route_manifest.py --check  # exit 1 if duplicates found (CI mode)

Output: docs/audit/route_manifest.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ── Bootstrap ──────────────────────────────────────────────────────────────
# Ensure repo root is on sys.path so `app` is importable.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Minimal env vars so app.main can be imported without crashing.
os.environ.setdefault("DATABASE_URL", "sqlite:///./dev_route_check.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "route-manifest-generation-only")
os.environ.setdefault("ENVIRONMENT", "development")

# Mock heavy optional deps that aren't needed for route introspection.
from unittest.mock import MagicMock  # noqa: E402

for mod_name in (
    "firebase_admin", "firebase_admin.credentials", "firebase_admin.messaging",
    "sentry_sdk", "sentry_sdk.integrations.fastapi",
):
    if mod_name not in sys.modules:
        m = MagicMock()
        if mod_name == "sentry_sdk.integrations.fastapi":
            setattr(m, "FastApiIntegration", MagicMock())
        sys.modules[mod_name] = m

from app.main import app  # noqa: E402


# ── Route extraction ──────────────────────────────────────────────────────
def extract_routes(application) -> list[dict]:
    """Walk FastAPI's route tree and return a list of route descriptors."""
    routes: list[dict] = []
    for route in application.routes:
        methods = getattr(route, "methods", None)
        if methods is None:
            continue  # Mount / static
        path: str = getattr(route, "path", "")
        endpoint = getattr(route, "endpoint", None)
        module = getattr(endpoint, "__module__", "") if endpoint else ""
        func_name = getattr(endpoint, "__name__", "") if endpoint else ""
        tags = list(getattr(route, "tags", []))
        for method in sorted(methods):
            routes.append({
                "method": method,
                "path": path,
                "handler": f"{module}:{func_name}",
                "tags": tags,
            })
    return routes


def find_duplicates(routes: list[dict]) -> list[dict]:
    """Return list of (method, path) keys that appear more than once."""
    counter: Counter[tuple[str, str]] = Counter()
    handler_map: dict[tuple[str, str], list[str]] = {}
    for r in routes:
        key = (r["method"], r["path"])
        counter[key] += 1
        handler_map.setdefault(key, []).append(r["handler"])

    duplicates = []
    for (method, path), count in counter.items():
        if count > 1:
            duplicates.append({
                "method": method,
                "path": path,
                "count": count,
                "handlers": handler_map[(method, path)],
            })
    return sorted(duplicates, key=lambda d: (d["path"], d["method"]))


# ── Main ──────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Generate route manifest")
    parser.add_argument(
        "--check", action="store_true",
        help="CI mode: exit 1 if duplicates are found",
    )
    parser.add_argument(
        "--output", type=str,
        default=str(REPO_ROOT / "docs" / "audit" / "route_manifest.json"),
        help="Path for manifest output file",
    )
    args = parser.parse_args()

    routes = extract_routes(app)
    duplicates = find_duplicates(routes)

    unique_paths = {r["path"] for r in routes}

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_registrations": len(routes),
        "unique_paths": len(unique_paths),
        "duplicate_count": len(duplicates),
        "duplicates": duplicates,
        "routes": routes,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"✅  Manifest written to {out_path}")
    print(f"    Total registrations : {len(routes)}")
    print(f"    Unique paths        : {len(unique_paths)}")
    print(f"    Duplicates          : {len(duplicates)}")

    if duplicates:
        print("\n⚠️  Duplicate routes detected:")
        for d in duplicates:
            print(f"    {d['method']:7s} {d['path']}")
            for h in d["handlers"]:
                print(f"            ↳ {h}")

    if args.check and duplicates:
        print(f"\n❌  CI FAIL: {len(duplicates)} duplicate route(s) found.")
        return 1

    if not duplicates:
        print("\n🎉  Zero duplicate routes — clean!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
