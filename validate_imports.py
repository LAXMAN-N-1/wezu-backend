"""
WEZU Backend – Comprehensive Import & Schema Validation Script
Checks every module, model, service, API router, middleware, and worker.
"""
import sys
import importlib
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
results = {"ok": [], "fail": []}

def check_import(module_path: str):
    try:
        importlib.import_module(module_path)
        results["ok"].append(module_path)
    except Exception as e:
        results["fail"].append((module_path, str(e), traceback.format_exc()))

# ── 1. Core ──────────────────────────────────────────────────────────────
print("=" * 60)
print("PHASE 1: Core modules")
print("=" * 60)
for mod in [
    "app.core.config",
    "app.core.database",
    "app.core.security",
    "app.core.logging",
]:
    check_import(mod)
    status = "OK" if mod in [r for r in results["ok"]] else "FAIL"
    print(f"  {mod}: {status}")

# ── 2. Models ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("PHASE 2: Models")
print("=" * 60)
models_dir = ROOT / "app" / "models"
for f in sorted(models_dir.glob("*.py")):
    if f.name.startswith("_"):
        continue
    mod = f"app.models.{f.stem}"
    check_import(mod)
    status = "OK" if mod in results["ok"] else "FAIL"
    print(f"  {mod}: {status}")

# ── 3. Schemas ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("PHASE 3: Schemas")
print("=" * 60)
schemas_dir = ROOT / "app" / "schemas"
for f in sorted(schemas_dir.glob("*.py")):
    if f.name.startswith("_"):
        continue
    mod = f"app.schemas.{f.stem}"
    check_import(mod)
    status = "OK" if mod in results["ok"] else "FAIL"
    print(f"  {mod}: {status}")

# ── 4. Services ───────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("PHASE 4: Services")
print("=" * 60)
services_dir = ROOT / "app" / "services"
for f in sorted(services_dir.glob("*.py")):
    if f.name.startswith("_"):
        continue
    mod = f"app.services.{f.stem}"
    check_import(mod)
    status = "OK" if mod in results["ok"] else "FAIL"
    print(f"  {mod}: {status}")

# ── 5. API Routers ────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("PHASE 5: API v1 routers")
print("=" * 60)
api_dir = ROOT / "app" / "api" / "v1"
for f in sorted(api_dir.glob("*.py")):
    if f.name.startswith("_"):
        continue
    mod = f"app.api.v1.{f.stem}"
    check_import(mod)
    status = "OK" if mod in results["ok"] else "FAIL"
    print(f"  {mod}: {status}")

# ── 6. Middleware ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("PHASE 6: Middleware")
print("=" * 60)
mw_dir = ROOT / "app" / "middleware"
for f in sorted(mw_dir.glob("*.py")):
    if f.name.startswith("_"):
        continue
    mod = f"app.middleware.{f.stem}"
    check_import(mod)
    status = "OK" if mod in results["ok"] else "FAIL"
    print(f"  {mod}: {status}")

# ── 7. Workers ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("PHASE 7: Workers")
print("=" * 60)
workers_dir = ROOT / "app" / "workers"
for f in sorted(workers_dir.glob("*.py")):
    if f.name.startswith("_"):
        continue
    mod = f"app.workers.{f.stem}"
    check_import(mod)
    status = "OK" if mod in results["ok"] else "FAIL"
    print(f"  {mod}: {status}")

# ── 8. DB modules ─────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("PHASE 8: DB modules")
print("=" * 60)
db_dir = ROOT / "app" / "db"
for f in sorted(db_dir.glob("*.py")):
    if f.name.startswith("_"):
        continue
    mod = f"app.db.{f.stem}"
    check_import(mod)
    status = "OK" if mod in results["ok"] else "FAIL"
    print(f"  {mod}: {status}")

# ── Summary ───────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  PASSED: {len(results['ok'])}")
print(f"  FAILED: {len(results['fail'])}")

if results["fail"]:
    print("\n--- FAILURES ---")
    for mod, err, tb in results["fail"]:
        print(f"\n  MODULE: {mod}")
        print(f"  ERROR:  {err}")
        # Print last 5 lines of traceback
        tb_lines = tb.strip().split("\n")
        for line in tb_lines[-5:]:
            print(f"    {line}")

sys.exit(1 if results["fail"] else 0)
