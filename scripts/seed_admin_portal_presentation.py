#!/usr/bin/env python3
"""
Seed data for admin-portal presentation readiness.

What this does:
1) Runs the comprehensive, idempotent seed pipeline.
2) Verifies key admin modules have rows so screens render with populated data.

Usage:
  PYTHONPATH=/app python scripts/seed_admin_portal_presentation.py
  PYTHONPATH=/app python scripts/seed_admin_portal_presentation.py --verify-only
  PYTHONPATH=/app python scripts/seed_admin_portal_presentation.py --non-strict
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, text

# Ensure repo root import works when run from scripts/ or docker exec.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.db.seeds.seed_complete_db import load_database_url, main as seed_complete_main


PREFERRED_SCHEMAS = (
    "core",
    "public",
    "inventory",
    "stations",
    "rentals",
    "finance",
    "dealers",
    "logistics",
)


@dataclass(frozen=True)
class ScreenCheck:
    screen: str
    table: str
    min_rows: int = 1


SCREEN_CHECKS: tuple[ScreenCheck, ...] = (
    # Dashboard / top cards / summaries
    ScreenCheck("Dashboard", "users", 5),
    ScreenCheck("Dashboard", "stations", 2),
    ScreenCheck("Dashboard", "batteries", 10),
    ScreenCheck("Dashboard", "rentals", 3),
    ScreenCheck("Dashboard", "transactions", 3),

    # User master / users module
    ScreenCheck("Users", "users", 5),
    ScreenCheck("Users", "user_profiles", 3),
    ScreenCheck("Users", "roles", 2),
    ScreenCheck("Users", "permissions", 4),

    # Stations / fleet ops
    ScreenCheck("Stations", "stations", 2),
    ScreenCheck("Stations", "station_slots", 4),
    ScreenCheck("Stations", "station_heartbeats", 2),

    # Inventory / battery health
    ScreenCheck("Inventory", "batteries", 10),
    ScreenCheck("Inventory", "battery_health_snapshots", 5),
    ScreenCheck("Inventory", "battery_audit_logs", 5),
    ScreenCheck("Inventory", "station_stock_configs", 2),
    ScreenCheck("Inventory", "reorder_requests", 1),

    # Rentals
    ScreenCheck("Rentals", "rentals", 3),
    ScreenCheck("Rentals", "rental_events", 3),
    ScreenCheck("Rentals", "swap_sessions", 2),
    ScreenCheck("Rentals", "late_fees", 1),

    # Finance
    ScreenCheck("Finance", "transactions", 3),
    ScreenCheck("Finance", "invoices", 2),
    ScreenCheck("Finance", "settlements", 1),
    ScreenCheck("Finance", "wallets", 3),

    # Logistics
    ScreenCheck("Logistics", "delivery_orders", 2),
    ScreenCheck("Logistics", "delivery_assignments", 1),
    ScreenCheck("Logistics", "delivery_routes", 1),
    ScreenCheck("Logistics", "return_requests", 1),

    # Dealers
    ScreenCheck("Dealers", "dealer_profiles", 2),
    ScreenCheck("Dealers", "dealer_applications", 1),
    ScreenCheck("Dealers", "vendors", 1),

    # Support / audit / security
    ScreenCheck("Support", "support_tickets", 2),
    ScreenCheck("Support", "ticket_messages", 2),
    ScreenCheck("Audit", "audit_logs", 2),
    ScreenCheck("Security", "security_events", 1),

    # CMS
    ScreenCheck("CMS", "blogs", 1),
    ScreenCheck("CMS", "banners", 1),
    ScreenCheck("CMS", "legal_documents", 1),
    ScreenCheck("CMS", "media_assets", 1),
    ScreenCheck("CMS", "faqs", 1),

    # Notifications / settings
    ScreenCheck("Notifications", "notifications", 2),
    ScreenCheck("Notifications", "push_campaigns", 1),
    ScreenCheck("Notifications", "notification_logs", 1),
    ScreenCheck("Settings", "system_configs", 1),
    ScreenCheck("Settings", "feature_flags", 1),
    ScreenCheck("Settings", "api_key_configs", 1),

    # BESS
    ScreenCheck("BESS", "bess_units", 1),
    ScreenCheck("BESS", "bess_energy_logs", 1),
    ScreenCheck("BESS", "bess_grid_events", 1),
    ScreenCheck("BESS", "bess_reports", 1),

    # Analytics sources
    ScreenCheck("Analytics", "demand_forecasts", 1),
    ScreenCheck("Analytics", "churn_predictions", 1),
    ScreenCheck("Analytics", "pricing_recommendations", 1),
    ScreenCheck("Analytics", "revenue_reports", 1),
)


def _ordered_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _schema_locations(conn, table_name: str) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT table_schema
            FROM information_schema.tables
            WHERE table_name = :table_name
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
            """
        ),
        {"table_name": table_name},
    ).scalars().all()

    preferred = [schema for schema in PREFERRED_SCHEMAS if schema in rows]
    trailing = sorted(schema for schema in rows if schema not in PREFERRED_SCHEMAS)
    return _ordered_unique(preferred + trailing)


def _count_rows(conn, schema: str, table_name: str) -> int:
    return int(
        conn.exec_driver_sql(f'SELECT COUNT(*) FROM "{schema}"."{table_name}"').scalar() or 0
    )


def verify_screen_data(strict: bool) -> int:
    database_url = load_database_url()
    engine = create_engine(database_url, future=True)

    failures: list[str] = []
    print("\n=== Admin Presentation Data Verification ===")

    with engine.connect() as conn:
        search_path = conn.exec_driver_sql("SHOW search_path").scalar()
        print(f"search_path: {search_path}")

        grouped: dict[str, list[ScreenCheck]] = {}
        for check in SCREEN_CHECKS:
            grouped.setdefault(check.screen, []).append(check)

        for screen in sorted(grouped.keys()):
            print(f"\n[{screen}]")
            for check in grouped[screen]:
                locations = _schema_locations(conn, check.table)
                if not locations:
                    msg = f"{check.table}: missing table"
                    print(f"  FAIL - {msg}")
                    failures.append(f"{screen}: {msg}")
                    continue

                schema = locations[0]
                count = _count_rows(conn, schema, check.table)
                if count < check.min_rows:
                    msg = (
                        f"{schema}.{check.table}: {count} rows "
                        f"(expected >= {check.min_rows})"
                    )
                    print(f"  FAIL - {msg}")
                    failures.append(f"{screen}: {msg}")
                else:
                    print(f"  OK   - {schema}.{check.table}: {count}")

    if failures:
        print("\nVerification failures:")
        for entry in failures:
            print(f"  - {entry}")
        if strict:
            print("\nResult: FAILED (strict mode)")
            return 1
        print("\nResult: WARN (non-strict mode)")
        return 0

    print("\nResult: PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed and verify admin portal presentation data."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip seed run and only verify data coverage.",
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        help="Do not fail process when verification finds low/missing data.",
    )
    args = parser.parse_args()

    if not args.verify_only:
        print("Running comprehensive seed pipeline...")
        seed_complete_main()
        print("Seed pipeline finished.")

    return verify_screen_data(strict=not args.non_strict)


if __name__ == "__main__":
    raise SystemExit(main())
