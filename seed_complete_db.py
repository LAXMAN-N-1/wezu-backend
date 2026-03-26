#!/usr/bin/env python3
"""
Comprehensive Neon PostgreSQL seeder for the Wezu project.

This script is intentionally reflection-driven:
- it reads the live schema from the connected database,
- inserts realistic, interconnected data for the main business tables,
- then backfills any remaining empty application tables so nothing is left blank.

Behavior:
- safe to rerun: it looks up existing rows by deterministic keys where possible
- non-destructive: it does not truncate existing data
- seeds both the `public` schema and the split application schemas when present
"""

from __future__ import annotations

import os
import random
import secrets
import string
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import MetaData, Table, and_, create_engine, func, inspect, select
from sqlalchemy.dialects.postgresql import ENUM, UUID, insert as pg_insert
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import JSON, Boolean, Date, DateTime, Float, Integer, Numeric, String, Text, Time


BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

try:
    from app.core.security import get_password_hash
except Exception:  # pragma: no cover - fallback only if app imports break
    def get_password_hash(password: str) -> str:
        return password


APP_SCHEMAS = ["public", "core", "dealers", "finance", "inventory", "logistics", "rentals", "stations"]
SKIP_TABLES = {"alembic_version"}
RANDOM = random.Random(20260317)
BASE_TIME = datetime(2026, 3, 17, 9, 0, 0)
DEFAULT_PASSWORD = "Wezu@123"
PASSWORD_HASH = get_password_hash(DEFAULT_PASSWORD)


CITY_BLUEPRINTS = [
    {"city": "Hyderabad", "state": "Telangana", "lat": 17.4416, "lng": 78.3823},
    {"city": "Bengaluru", "state": "Karnataka", "lat": 12.9716, "lng": 77.5946},
    {"city": "Chennai", "state": "Tamil Nadu", "lat": 13.0827, "lng": 80.2707},
    {"city": "Mumbai", "state": "Maharashtra", "lat": 19.0760, "lng": 72.8777},
    {"city": "Pune", "state": "Maharashtra", "lat": 18.5204, "lng": 73.8567},
    {"city": "Delhi", "state": "Delhi", "lat": 28.6139, "lng": 77.2090},
    {"city": "Jaipur", "state": "Rajasthan", "lat": 26.9124, "lng": 75.7873},
    {"city": "Ahmedabad", "state": "Gujarat", "lat": 23.0225, "lng": 72.5714},
    {"city": "Kolkata", "state": "West Bengal", "lat": 22.5726, "lng": 88.3639},
    {"city": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8467, "lng": 80.9462},
]

BATT_CATALOG = [
    {
        "name": "Wezu PowerCell 48V/30Ah",
        "brand": "Wezu",
        "model": "WZ-PC-4830",
        "description": "Daily commute battery pack with strong cycle life for urban riders.",
        "capacity_mah": 30000,
        "capacity_ah": 30.0,
        "cycle_life_expectancy": 2000,
        "voltage": 48.0,
        "battery_type": "LFP",
        "weight_kg": 12.4,
        "dimensions": "420x210x150 mm",
        "price_full_purchase": 44999.0,
        "price_per_day": 149.0,
        "warranty_months": 24,
    },
    {
        "name": "Wezu UrbanFlow 48V/25Ah",
        "brand": "Wezu",
        "model": "WZ-UF-4825",
        "description": "Balanced city-use battery with improved thermal stability.",
        "capacity_mah": 25000,
        "capacity_ah": 25.0,
        "cycle_life_expectancy": 1800,
        "voltage": 48.0,
        "battery_type": "LITHIUM_ION",
        "weight_kg": 10.8,
        "dimensions": "400x200x145 mm",
        "price_full_purchase": 38499.0,
        "price_per_day": 129.0,
        "warranty_months": 24,
    },
    {
        "name": "Wezu TurboMax 60V/40Ah",
        "brand": "Wezu",
        "model": "WZ-TM-6040",
        "description": "Fleet-grade high output battery designed for heavy duty commercial usage.",
        "capacity_mah": 40000,
        "capacity_ah": 40.0,
        "cycle_life_expectancy": 2500,
        "voltage": 60.0,
        "battery_type": "NMC",
        "weight_kg": 16.3,
        "dimensions": "455x230x180 mm",
        "price_full_purchase": 61999.0,
        "price_per_day": 209.0,
        "warranty_months": 36,
    },
    {
        "name": "Wezu FleetPower 72V/50Ah",
        "brand": "Wezu",
        "model": "WZ-FP-7250",
        "description": "High-capacity commercial battery for long distance and logistics operations.",
        "capacity_mah": 50000,
        "capacity_ah": 50.0,
        "cycle_life_expectancy": 3000,
        "voltage": 72.0,
        "battery_type": "LFP",
        "weight_kg": 22.5,
        "dimensions": "500x255x205 mm",
        "price_full_purchase": 84999.0,
        "price_per_day": 299.0,
        "warranty_months": 48,
    },
    {
        "name": "Wezu EcoRide 36V/20Ah",
        "brand": "Wezu",
        "model": "WZ-ER-3620",
        "description": "Compact last-mile battery for low-load mobility applications.",
        "capacity_mah": 20000,
        "capacity_ah": 20.0,
        "cycle_life_expectancy": 1500,
        "voltage": 36.0,
        "battery_type": "LITHIUM_ION",
        "weight_kg": 8.6,
        "dimensions": "360x180x135 mm",
        "price_full_purchase": 29999.0,
        "price_per_day": 99.0,
        "warranty_months": 18,
    },
]

ORG_BLUEPRINTS = [
    {"code": "WEZU", "name": "Wezu Energy Pvt Ltd", "website": "https://wezu.energy"},
    {"code": "POWERFILL", "name": "PowerFill Mobility Services", "website": "https://powerfill.wezu.energy"},
]

ROLE_BLUEPRINTS = [
    {"name": "Super Admin", "description": "Full access to all operational modules.", "category": "SYSTEM", "level": 100, "is_system_role": True},
    {"name": "Operations Admin", "description": "Administrative operations across customers, rentals, and support.", "category": "SYSTEM", "level": 90, "is_system_role": True},
    {"name": "Customer", "description": "End customer using rentals, swaps, and purchases.", "category": "CUSTOMER", "level": 10, "is_system_role": False},
    {"name": "Dealer", "description": "Dealer account responsible for local business operations.", "category": "PARTNER", "level": 50, "is_system_role": False},
    {"name": "Support Agent", "description": "Customer support and ticket handling.", "category": "STAFF", "level": 40, "is_system_role": False},
    {"name": "Logistics Executive", "description": "Logistics and delivery execution.", "category": "STAFF", "level": 35, "is_system_role": False},
    {"name": "Finance Manager", "description": "Finance and settlement oversight.", "category": "STAFF", "level": 60, "is_system_role": False},
    {"name": "Station Manager", "description": "Station operations and inventory supervision.", "category": "STAFF", "level": 45, "is_system_role": False},
]

PERMISSION_MODULES = [
    "users",
    "roles",
    "stations",
    "batteries",
    "rentals",
    "swaps",
    "orders",
    "support",
    "finance",
    "logistics",
    "analytics",
]
PERMISSION_ACTIONS = ["view", "create", "update", "delete"]

ADMIN_BLUEPRINTS = [
    {"email": "murari.admin@seed.wezu.energy", "name": "Murari Reddy", "role": "Super Admin", "city": "Hyderabad"},
    {"email": "srilaxmi.ops@seed.wezu.energy", "name": "Srilaxmi Ravi", "role": "Operations Admin", "city": "Bengaluru"},
    {"email": "priya.ops@seed.wezu.energy", "name": "Priya Sharma", "role": "Operations Admin", "city": "Chennai"},
    {"email": "amit.finance@seed.wezu.energy", "name": "Amit Singh", "role": "Finance Manager", "city": "Mumbai"},
    {"email": "rajesh.station@seed.wezu.energy", "name": "Rajesh Kumar", "role": "Station Manager", "city": "Pune"},
]

CUSTOMER_BLUEPRINTS = [
    "Laxman",
    "Sneha Patel",
    "Arjun Reddy",
    "Kavya Nair",
    "Vikram Joshi",
    "Meera Iyer",
    "Rohan Gupta",
    "Ananya Das",
    "Karthik Subramanian",
    "Divya Mehta",
    "Aditya Chauhan",
    "Pooja Srinivasan",
    "Nikhil Malhotra",
    "Riya Banerjee",
    "Saurabh Tiwari",
    "Lakshmi Menon",
    "Varun Kapoor",
    "Swati Mishra",
    "Deepak Rao",
    "Nisha Agarwal",
]

DEALER_BLUEPRINTS = [
    {"email": "dealer.hyd@seed.wezu.energy", "owner_name": "Suresh Reddy", "business_name": "Wezu Green Grid Hyderabad", "city": "Hyderabad"},
    {"email": "dealer.blr@seed.wezu.energy", "owner_name": "Manoj Kumar", "business_name": "Wezu EV Junction Bengaluru", "city": "Bengaluru"},
    {"email": "dealer.chn@seed.wezu.energy", "owner_name": "Dinesh Raman", "business_name": "Wezu ChargeHub Chennai", "city": "Chennai"},
    {"email": "dealer.mum@seed.wezu.energy", "owner_name": "Ashok Nair", "business_name": "Wezu Battery Port Mumbai", "city": "Mumbai"},
    {"email": "dealer.pun@seed.wezu.energy", "owner_name": "Harsha Patil", "business_name": "Wezu Mobility Pune", "city": "Pune"},
]

SUPPORT_BLUEPRINTS = [
    {"email": "support.asha@seed.wezu.energy", "name": "Asha Menon", "city": "Hyderabad"},
    {"email": "support.ravi@seed.wezu.energy", "name": "Ravi Teja", "city": "Bengaluru"},
    {"email": "support.neha@seed.wezu.energy", "name": "Neha Khanna", "city": "Mumbai"},
]

LOGISTICS_BLUEPRINTS = [
    {"email": "logistics.manoj@seed.wezu.energy", "name": "Manoj Driver", "city": "Hyderabad"},
    {"email": "logistics.sunil@seed.wezu.energy", "name": "Sunil Transport", "city": "Bengaluru"},
    {"email": "logistics.prakash@seed.wezu.energy", "name": "Prakash Delivery", "city": "Chennai"},
]

VENDOR_BLUEPRINTS = [
    {"email": "vendor.alpha@seed.wezu.energy", "name": "Alpha Vendor Network", "city": "Hyderabad"},
    {"email": "vendor.beta@seed.wezu.energy", "name": "Beta Charge Services", "city": "Bengaluru"},
    {"email": "vendor.gamma@seed.wezu.energy", "name": "Gamma Mobility Ops", "city": "Mumbai"},
]

STATION_BLUEPRINTS = [
    {"name": "Wezu Hub Madhapur", "city": "Hyderabad", "zone_suffix": "North"},
    {"name": "Wezu Station Gachibowli", "city": "Hyderabad", "zone_suffix": "South"},
    {"name": "Wezu Point Koramangala", "city": "Bengaluru", "zone_suffix": "North"},
    {"name": "Wezu Dock HSR Layout", "city": "Bengaluru", "zone_suffix": "South"},
    {"name": "Wezu Port T Nagar", "city": "Chennai", "zone_suffix": "North"},
    {"name": "Wezu Bay Velachery", "city": "Chennai", "zone_suffix": "South"},
    {"name": "Wezu Park Andheri East", "city": "Mumbai", "zone_suffix": "North"},
    {"name": "Wezu Center Bandra", "city": "Mumbai", "zone_suffix": "South"},
    {"name": "Wezu Junction Hinjawadi", "city": "Pune", "zone_suffix": "North"},
    {"name": "Wezu Zone Kharadi", "city": "Pune", "zone_suffix": "South"},
]

PRODUCT_BLUEPRINTS = [
    {"sku": "BAT-WZ-4830", "name": "Wezu PowerCell 48V Battery", "category": "BATTERY", "brand": "Wezu", "model": "WZ-PC-4830", "price": 44999.0, "original_price": 49999.0},
    {"sku": "BAT-WZ-6040", "name": "Wezu TurboMax 60V Battery", "category": "BATTERY", "brand": "Wezu", "model": "WZ-TM-6040", "price": 61999.0, "original_price": 69999.0},
    {"sku": "CHR-WZ-FAST48", "name": "Wezu Fast Charger 48V", "category": "CHARGER", "brand": "Wezu", "model": "WZ-CHR-48", "price": 5499.0, "original_price": 6499.0},
    {"sku": "ACC-WZ-BMS", "name": "Wezu Smart BMS Monitor", "category": "ACCESSORY", "brand": "Wezu", "model": "WZ-BMS-01", "price": 2499.0, "original_price": 2999.0},
    {"sku": "ACC-WZ-CASE", "name": "Wezu Battery Carry Case", "category": "ACCESSORY", "brand": "Wezu", "model": "WZ-CASE-01", "price": 1799.0, "original_price": 2199.0},
    {"sku": "BND-WZ-START", "name": "Wezu Starter Bundle", "category": "BUNDLE", "brand": "Wezu", "model": "WZ-BND-01", "price": 49999.0, "original_price": 56999.0},
]

ECOM_BLUEPRINTS = [
    {"sku": "ECM-HELMET-01", "name": "Wezu Safety Helmet", "category": "accessory", "price": 1999.0},
    {"sku": "ECM-GLOVE-01", "name": "Wezu Riding Gloves", "category": "accessory", "price": 899.0},
    {"sku": "ECM-RAIN-01", "name": "Wezu Rain Cover Kit", "category": "accessory", "price": 1299.0},
    {"sku": "ECM-CHARGER-01", "name": "Wezu Portable Charger", "category": "charger", "price": 3999.0},
    {"sku": "ECM-MOUNT-01", "name": "Wezu Handlebar Mount", "category": "accessory", "price": 599.0},
    {"sku": "ECM-CABLE-01", "name": "Wezu Charge Cable", "category": "battery", "price": 799.0},
]

FAQ_ROWS = [
    ("How do I start a rental?", "Scan the station QR, pick a ready battery, and confirm the rental in the app."),
    ("How do battery swaps work?", "Visit a station, return the low-charge battery, and collect a charged one."),
    ("How are late fees calculated?", "Late fees apply per overdue day based on your rental plan and waiver status."),
    ("Can dealers manage stock online?", "Yes. Dealer dashboards expose inventory, reorder, and transfer workflows."),
    ("How long does KYC take?", "Most complete KYC submissions are reviewed the same business day."),
]

SECURITY_QUESTION_ROWS = [
    "What is your favorite school subject?",
    "What was the name of your first vehicle?",
    "What city were you born in?",
    "What is your mother's first name?",
    "What was your childhood nickname?",
]

PROMO_ROWS = [
    {"code": "WELCOME50", "description": "Welcome discount for first rental", "discount_amount": 50.0},
    {"code": "SWAP20", "description": "Discount on swap fee for active customers", "discount_percentage": 20.0},
    {"code": "FLEET100", "description": "Flat dealer onboarding credit", "discount_amount": 100.0},
    {"code": "WEZU500", "description": "Large first-purchase order discount", "discount_amount": 500.0},
]

BANNER_ROWS = [
    {"title": "Ride Further With Fresh Swaps", "deep_link": "wezu://swaps", "external_url": None},
    {"title": "Dealer Onboarding Open", "deep_link": "wezu://dealer/apply", "external_url": None},
    {"title": "Summer Service Camp", "deep_link": "wezu://maintenance", "external_url": None},
]

BLOG_ROWS = [
    {"slug": "battery-swap-best-practices", "title": "Battery Swap Best Practices", "category": "operations"},
    {"slug": "fleet-battery-maintenance-playbook", "title": "Fleet Battery Maintenance Playbook", "category": "maintenance"},
    {"slug": "dealer-network-growth-2026", "title": "Dealer Network Growth In 2026", "category": "business"},
]

LEGAL_ROWS = [
    {"slug": "terms-of-service", "title": "Terms of Service"},
    {"slug": "privacy-policy", "title": "Privacy Policy"},
    {"slug": "refund-policy", "title": "Refund Policy"},
]


def load_database_url() -> str:
    load_dotenv(BASE_DIR / ".env")
    load_dotenv(BASE_DIR.parent / ".env")
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL was not found in backend/.env, repo .env, or environment.")
    return database_url


def dt(days: int = 0, hours: int = 0, minutes: int = 0) -> datetime:
    return BASE_TIME + timedelta(days=days, hours=hours, minutes=minutes)


def slugify(value: str) -> str:
    slug = value.lower().strip()
    cleaned = []
    for char in slug:
        if char.isalnum():
            cleaned.append(char)
        elif not cleaned or cleaned[-1] != "-":
            cleaned.append("-")
    result = "".join(cleaned).strip("-")
    return result or "seed"


def city_data(city_name: str) -> dict[str, Any]:
    return next(row for row in CITY_BLUEPRINTS if row["city"] == city_name)


def make_phone(seed_index: int) -> str:
    return f"+9196{seed_index:08d}"[:13]


def make_gst(seed_index: int) -> str:
    prefix = f"{(seed_index % 28) + 1:02d}"
    middle = f"AABCU{9000 + seed_index:04d}F"
    return f"{prefix}{middle}1Z{seed_index % 9}"


def make_pan(seed_index: int) -> str:
    return f"AABCU{9000 + seed_index:04d}F"


def safe_dict(value: dict[str, Any]) -> dict[str, Any]:
    return dict(value)


@dataclass
class Resolver:
    label: str
    table_to_schema: dict[str, str]

    def schema_for(self, table_name: str) -> str | None:
        return self.table_to_schema.get(table_name)

    def schemas(self) -> list[str]:
        return sorted(set(self.table_to_schema.values()))


class SeedRuntime:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.inspector = inspect(engine)
        self.metadata = MetaData()
        self._table_cache: dict[tuple[str, str], Table] = {}
        self._column_cache: dict[tuple[str, str], dict[str, Column[Any]]] = {}
        self._fk_cache: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
        self._unique_cache: dict[tuple[str, str], set[tuple[str, ...]]] = {}

    def has_table(self, schema: str | None, table_name: str) -> bool:
        if not schema:
            return False
        return table_name in self.inspector.get_table_names(schema=schema)

    def table(self, schema: str, table_name: str, conn: Connection | None = None) -> Table:
        key = (schema, table_name)
        if key not in self._table_cache:
            autoload_source = conn if conn is not None else self.engine
            self._table_cache[key] = Table(table_name, self.metadata, schema=schema, autoload_with=autoload_source)
        return self._table_cache[key]

    def columns(self, schema: str, table_name: str, conn: Connection | None = None) -> dict[str, Column[Any]]:
        key = (schema, table_name)
        if key not in self._column_cache:
            self._column_cache[key] = {column.name: column for column in self.table(schema, table_name, conn=conn).columns}
        return self._column_cache[key]

    def primary_keys(self, schema: str, table_name: str) -> list[str]:
        return list(self.inspector.get_pk_constraint(table_name, schema=schema).get("constrained_columns") or [])

    def fk_map(self, schema: str, table_name: str) -> dict[str, dict[str, Any]]:
        key = (schema, table_name)
        if key not in self._fk_cache:
            fk_by_column: dict[str, dict[str, Any]] = {}
            for fk in self.inspector.get_foreign_keys(table_name, schema=schema):
                for constrained in fk.get("constrained_columns") or []:
                    fk_by_column[constrained] = fk
            self._fk_cache[key] = fk_by_column
        return self._fk_cache[key]

    def unique_key_sets(self, schema: str, table_name: str) -> set[tuple[str, ...]]:
        key = (schema, table_name)
        if key not in self._unique_cache:
            unique_sets: set[tuple[str, ...]] = set()
            pk = tuple(self.primary_keys(schema, table_name))
            if pk:
                unique_sets.add(pk)
            for constraint in self.inspector.get_unique_constraints(table_name, schema=schema):
                columns = tuple(constraint.get("column_names") or [])
                if columns:
                    unique_sets.add(columns)
            self._unique_cache[key] = unique_sets
        return self._unique_cache[key]

    def can_conflict_on(self, schema: str, table_name: str, key_columns: tuple[str, ...]) -> bool:
        if not key_columns:
            return False
        return tuple(key_columns) in self.unique_key_sets(schema, table_name)

    def count_rows(self, conn: Connection, schema: str, table_name: str) -> int:
        table = self.table(schema, table_name, conn=conn)
        return int(conn.execute(select(func.count()).select_from(table)).scalar_one())

    def fetch_ids(self, conn: Connection, schema: str, table_name: str, limit: int | None = None) -> list[Any]:
        table = self.table(schema, table_name, conn=conn)
        pk_columns = self.primary_keys(schema, table_name)
        if not pk_columns:
            return []
        pk = table.c[pk_columns[0]]
        stmt = select(pk).order_by(pk)
        if limit:
            stmt = stmt.limit(limit)
        return list(conn.execute(stmt).scalars())

    def fetch_map(self, conn: Connection, schema: str, table_name: str, key_column: str, value_column: str = "id") -> dict[Any, Any]:
        table = self.table(schema, table_name, conn=conn)
        if key_column not in table.c or value_column not in table.c:
            return {}
        stmt = select(table.c[key_column], table.c[value_column])
        return {row[0]: row[1] for row in conn.execute(stmt)}

    def sample_reference(self, conn: Connection, schema: str, table_name: str, column_name: str = "id") -> Any:
        if not self.has_table(schema, table_name):
            return None
        table = self.table(schema, table_name, conn=conn)
        if column_name not in table.c:
            return None
        stmt = select(table.c[column_name]).order_by(table.c[column_name]).limit(1)
        return conn.execute(stmt).scalar()

    def sample_by_keys(self, conn: Connection, schema: str, table_name: str, key_columns: tuple[str, ...], values: dict[str, Any]) -> Any:
        table = self.table(schema, table_name, conn=conn)
        if not key_columns:
            return None
        pk_columns = self.primary_keys(schema, table_name)
        if not pk_columns:
            return None
        stmt = select(*[table.c[col] for col in pk_columns]).limit(1)
        clauses = []
        for key in key_columns:
            if key not in table.c:
                return None
            value = values.get(key)
            clauses.append(table.c[key].is_(None) if value is None else table.c[key] == value)
        if clauses:
            stmt = stmt.where(and_(*clauses))
        row = conn.execute(stmt).first()
        return row

    def normalize_value(self, column: Column[Any], value: Any) -> Any:
        if value is None:
            return None

        column_type = column.type
        if isinstance(column_type, ENUM):
            value_str = str(value)
            if value_str in column_type.enums:
                return value_str
            lowered = value_str.lower()
            for enum_value in column_type.enums:
                if enum_value.lower() == lowered:
                    return enum_value
            return column_type.enums[0]

        if isinstance(column_type, (DateTime, Date)):
            if isinstance(value, datetime):
                return value
            if isinstance(value, date):
                return value

        if isinstance(column_type, Time):
            if isinstance(value, time):
                return value

        if isinstance(column_type, (Boolean, Integer, Float, Numeric)):
            return value

        if isinstance(column_type, JSON):
            return value

        if isinstance(value, (dict, list)):
            return str(value).replace("'", '"')

        return value

    def enum_value_for_column(self, table_name: str, column_name: str, enum_values: list[str], index: int) -> str:
        preferred = {
            "users.user_type": "CUSTOMER",
            "users.status": "ACTIVE",
            "users.kyc_status": "APPROVED",
            "batteries.status": "AVAILABLE",
            "batteries.health_status": "GOOD",
            "batteries.location_type": "STATION",
            "stations.status": "OPERATIONAL",
            "support_tickets.status": "OPEN",
            "support_tickets.priority": "MEDIUM",
            "rentals.status": "COMPLETED",
            "transactions.status": "SUCCESS",
            "transactions.transaction_type": "RENTAL_PAYMENT",
            "delivery_orders.status": "ASSIGNED",
            "delivery_orders.order_type": "CUSTOMER_DELIVERY",
            "payment_transactions.status": "SUCCESS",
        }
        key = f"{table_name}.{column_name}"
        if key in preferred and preferred[key] in enum_values:
            return preferred[key]
        for fallback in ("ACTIVE", "AVAILABLE", "SUCCESS", "COMPLETED", "APPROVED", "PENDING"):
            if fallback in enum_values:
                return fallback
        return enum_values[index % len(enum_values)]

    def generic_value(self, schema: str, table_name: str, column: Column[Any], index: int = 0) -> Any:
        name = column.name.lower()
        column_type = column.type

        if isinstance(column_type, ENUM):
            return self.enum_value_for_column(table_name, column.name, list(column_type.enums), index)

        if isinstance(column_type, Boolean):
            if any(token in name for token in ("is_active", "enabled", "verified", "approved", "primary", "featured")):
                return True
            if any(token in name for token in ("deleted", "hidden", "locked", "frozen", "suspended")):
                return False
            return False

        if isinstance(column_type, Integer):
            if "priority" in name or "rank" in name or "sequence" in name or "slot_number" in name:
                return index + 1
            if "rating" in name:
                return 4
            if any(token in name for token in ("count", "quantity", "stock", "slots", "capacity", "volume")):
                return 10 + index
            if "percentage" in name:
                return 80
            if "minute" in name:
                return 15
            if "day" in name:
                return 7
            return index + 1

        if isinstance(column_type, (Float, Numeric)):
            if any(token in name for token in ("lat", "latitude")):
                return 17.4 + (index * 0.01)
            if any(token in name for token in ("lng", "longitude")):
                return 78.3 + (index * 0.01)
            if any(token in name for token in ("rating", "score", "probability", "confidence", "soh", "soc", "health", "percentage")):
                return round(80.0 + (index % 15), 2)
            if any(token in name for token in ("amount", "price", "balance", "fee", "cost", "revenue", "commission", "deposit", "tax")):
                return round(100.0 + index * 25.0, 2)
            return round(1.0 + index, 2)

        if isinstance(column_type, Time):
            return time(22, 0) if "start" in name else time(7, 0)

        if isinstance(column_type, Date):
            if any(token in name for token in ("expiry", "until", "end", "delivery", "forecast", "prediction")):
                return (BASE_TIME + timedelta(days=7 + index)).date()
            return (BASE_TIME - timedelta(days=7 + index)).date()

        if isinstance(column_type, DateTime):
            if any(token in name for token in ("updated", "processed", "verified", "approved", "scheduled", "sent", "started", "assigned")):
                return BASE_TIME - timedelta(days=max(index, 1))
            if any(token in name for token in ("completed", "delivered", "paid", "closed", "resolved", "end", "fulfilled", "reviewed")):
                return BASE_TIME - timedelta(days=max(index, 1)) + timedelta(hours=3)
            if any(token in name for token in ("next", "expires", "expected", "valid_until")):
                return BASE_TIME + timedelta(days=7 + index)
            return BASE_TIME - timedelta(days=index)

        if isinstance(column_type, UUID) or "uuid" in name:
            return str(secrets.token_hex(16)) if isinstance(column_type, String) else secrets.token_hex(16)

        if isinstance(column_type, JSON):
            return {"source": "seed_complete_db", "schema": schema, "table": table_name, "index": index}

        if any(token in name for token in ("email",)):
            return f"{slugify(table_name)}-{index}@seed.wezu.energy"
        if any(token in name for token in ("phone", "mobile", "contact_number")):
            return make_phone(1000 + index)
        if any(token in name for token in ("url", "image", "file_path", "file_url", "pdf_url", "proof", "tracking")):
            return f"https://seed.wezu.energy/{schema}/{table_name}/{column.name}/{index}"
        if any(token in name for token in ("slug",)):
            return f"{slugify(table_name)}-{index}"
        if any(token in name for token in ("code", "sku", "serial", "reference", "license", "manifest", "invoice", "tracking_number")):
            return f"{table_name[:4].upper()}-{index:04d}"
        if any(token in name for token in ("checksum", "signature", "token", "secret", "auth", "hash")):
            return secrets.token_hex(16)
        if name in {"currency"}:
            return "INR"
        if name in {"country"}:
            return "India"
        if name in {"city", "shipping_city"}:
            return CITY_BLUEPRINTS[index % len(CITY_BLUEPRINTS)]["city"]
        if name in {"state", "shipping_state"}:
            return CITY_BLUEPRINTS[index % len(CITY_BLUEPRINTS)]["state"]
        if "postal" in name or "pincode" in name:
            return f"560{index:03d}"[:6]
        if "address" in name:
            return f"{10 + index} Seed Mobility Road"
        if "name" in name:
            return f"{table_name.replace('_', ' ').title()} {index + 1}"
        if "status" in name:
            return "ACTIVE"
        if "type" in name:
            return "GENERAL"
        if "question" in name:
            return f"Seed question {index + 1}?"
        if "answer" in name:
            return f"seed-answer-{index + 1}"
        if "comment" in name or "description" in name or "message" in name or "reason" in name or "notes" in name or "content" in name or "summary" in name:
            return f"Seeded {table_name.replace('_', ' ')} content {index + 1}"
        return f"{table_name}_{column.name}_{index + 1}"

    def complete_row(self, conn: Connection, schema: str, table_name: str, row: dict[str, Any], index: int = 0) -> dict[str, Any]:
        table = self.table(schema, table_name, conn=conn)
        prepared: dict[str, Any] = {}
        fk_by_column = self.fk_map(schema, table_name)
        primary_keys = set(self.primary_keys(schema, table_name))

        for key, value in row.items():
            if key in table.c:
                prepared[key] = self.normalize_value(table.c[key], value)

        for column in table.columns:
            if column.name in prepared:
                continue
            if column.name in primary_keys:
                # If it's a PK and has a default (like SERIAL), let the DB handle it
                if column.default is not None or column.server_default is not None:
                    continue
            fk = fk_by_column.get(column.name)
            if fk:
                referred_schema = fk.get("referred_schema") or schema
                referred_table = fk["referred_table"]
                referred_columns = fk.get("referred_columns") or ["id"]
                sample = self.sample_reference(conn, referred_schema, referred_table, referred_columns[0])
                if sample is not None:
                    prepared[column.name] = sample
                    continue
            if not column.nullable and column.default is None and column.server_default is None:
                prepared[column.name] = self.normalize_value(column, self.generic_value(schema, table_name, column, index))
                continue
            if column.name in {"created_at", "updated_at", "timestamp"} and column.name not in prepared:
                prepared[column.name] = self.normalize_value(column, self.generic_value(schema, table_name, column, index))
        return prepared

    def ensure_rows(
        self,
        conn: Connection,
        schema: str | None,
        table_name: str,
        key_columns: tuple[str, ...],
        rows: list[dict[str, Any]],
    ) -> None:
        if not schema or not self.has_table(schema, table_name):
            return
        table = self.table(schema, table_name, conn=conn)
        use_conflict_target = self.can_conflict_on(schema, table_name, key_columns)
        for index, row in enumerate(rows):
            prepared = self.complete_row(conn, schema, table_name, row, index)
            if key_columns and not use_conflict_target:
                existing = self.sample_by_keys(conn, schema, table_name, key_columns, prepared)
                if existing is not None:
                    continue
            stmt = pg_insert(table).values(prepared)
            if key_columns and use_conflict_target:
                stmt = stmt.on_conflict_do_nothing(index_elements=list(key_columns))
            try:
                conn.execute(stmt)
            except Exception as e:
                print(f"ERROR inserting into {schema}.{table_name}")
                print(f"Row: {prepared}")
                print(f"Error: {e}")
                raise

    def empty_tables(self, conn: Connection, schemas: list[str]) -> list[str]:
        remaining: list[str] = []
        for schema in schemas:
            for table_name in sorted(self.inspector.get_table_names(schema=schema)):
                if table_name in SKIP_TABLES:
                    continue
                if self.count_rows(conn, schema, table_name) == 0:
                    remaining.append(f"{schema}.{table_name}")
        return remaining


def build_public_resolver(runtime: SeedRuntime) -> Resolver:
    mapping = {table_name: "public" for table_name in runtime.inspector.get_table_names(schema="public")}
    return Resolver(label="public", table_to_schema=mapping)


def build_namespaced_resolver(runtime: SeedRuntime) -> Resolver:
    mapping: dict[str, str] = {}
    for schema in APP_SCHEMAS:
        if schema == "public":
            continue
        for table_name in runtime.inspector.get_table_names(schema=schema):
            mapping[table_name] = schema
    return Resolver(label="namespaced", table_to_schema=mapping)


def seed_locations(runtime: SeedRuntime, conn: Connection, resolver: Resolver, ctx: dict[str, Any]) -> None:
    continent_schema = resolver.schema_for("continents")
    country_schema = resolver.schema_for("countries")
    region_schema = resolver.schema_for("regions")
    city_schema = resolver.schema_for("cities")
    zone_schema = resolver.schema_for("zones")

    runtime.ensure_rows(conn, continent_schema, "continents", ("name",), [{"name": "Asia"}])
    continent_ids = runtime.fetch_map(conn, continent_schema, "continents", "name") if continent_schema else {}
    asia_id = continent_ids.get("Asia")

    runtime.ensure_rows(
        conn,
        country_schema,
        "countries",
        ("name",),
        [{"name": "India", "continent_id": asia_id}],
    )
    country_ids = runtime.fetch_map(conn, country_schema, "countries", "name") if country_schema else {}
    india_id = country_ids.get("India")

    region_rows = [{"name": item["state"], "country_id": india_id} for item in CITY_BLUEPRINTS]
    runtime.ensure_rows(conn, region_schema, "regions", ("name",), region_rows)
    region_ids = runtime.fetch_map(conn, region_schema, "regions", "name") if region_schema else {}

    city_rows = [{"name": item["city"], "region_id": region_ids.get(item["state"])} for item in CITY_BLUEPRINTS]
    runtime.ensure_rows(conn, city_schema, "cities", ("name",), city_rows)
    city_ids = runtime.fetch_map(conn, city_schema, "cities", "name") if city_schema else {}

    zone_rows = []
    for item in CITY_BLUEPRINTS:
        zone_rows.append({"name": f"{item['city']} North", "city_id": city_ids.get(item["city"])})
        zone_rows.append({"name": f"{item['city']} South", "city_id": city_ids.get(item["city"])})
    runtime.ensure_rows(conn, zone_schema, "zones", ("name",), zone_rows)
    zone_ids = runtime.fetch_map(conn, zone_schema, "zones", "name") if zone_schema else {}

    ctx["continent_ids"] = continent_ids
    ctx["country_ids"] = country_ids
    ctx["region_ids"] = region_ids
    ctx["city_ids"] = city_ids
    ctx["zone_ids"] = zone_ids


def seed_access_control(runtime: SeedRuntime, conn: Connection, resolver: Resolver, ctx: dict[str, Any]) -> None:
    roles_schema = resolver.schema_for("roles")
    permissions_schema = resolver.schema_for("permissions")
    role_permissions_schema = resolver.schema_for("role_permissions")

    runtime.ensure_rows(conn, roles_schema, "roles", ("name",), ROLE_BLUEPRINTS)

    permission_rows = []
    for module in PERMISSION_MODULES:
        for action in PERMISSION_ACTIONS:
            permission_rows.append(
                {
                    "slug": f"{module}:{action}:all",
                    "module": module,
                    "resource_type": module,
                    "action": action,
                    "scope": "global",
                    "description": f"{action.title()} access for {module}.",
                }
            )
    runtime.ensure_rows(conn, permissions_schema, "permissions", ("slug",), permission_rows)

    role_ids = runtime.fetch_map(conn, roles_schema, "roles", "name") if roles_schema else {}
    permission_ids = runtime.fetch_map(conn, permissions_schema, "permissions", "slug") if permissions_schema else {}

    role_permission_rows = []
    for slug, permission_id in permission_ids.items():
        role_permission_rows.append({"role_id": role_ids.get("Super Admin"), "permission_id": permission_id})
        if slug.split(":")[0] not in {"finance"}:
            role_permission_rows.append({"role_id": role_ids.get("Operations Admin"), "permission_id": permission_id})
    runtime.ensure_rows(conn, role_permissions_schema, "role_permissions", ("role_id", "permission_id"), role_permission_rows)

    ctx["role_ids"] = role_ids
    ctx["permission_ids"] = permission_ids


def seed_organizations(runtime: SeedRuntime, conn: Connection, resolver: Resolver, ctx: dict[str, Any]) -> None:
    org_schema = resolver.schema_for("organizations")
    social_schema = resolver.schema_for("organization_social_links")
    branch_schema = resolver.schema_for("branches")
    warehouse_schema = resolver.schema_for("warehouses")

    runtime.ensure_rows(conn, org_schema, "organizations", ("code",), ORG_BLUEPRINTS)
    org_ids = runtime.fetch_map(conn, org_schema, "organizations", "code") if org_schema else {}

    social_rows = [
        {"organization_id": org_ids.get("WEZU"), "platform": "website", "url": "https://wezu.energy"},
        {"organization_id": org_ids.get("WEZU"), "platform": "linkedin", "url": "https://www.linkedin.com/company/wezu-energy"},
        {"organization_id": org_ids.get("POWERFILL"), "platform": "website", "url": "https://powerfill.wezu.energy"},
    ]
    runtime.ensure_rows(conn, social_schema, "organization_social_links", ("organization_id", "platform"), social_rows)

    branch_rows = []
    for index, item in enumerate(CITY_BLUEPRINTS[:5], start=1):
        branch_rows.append(
            {
                "code": f"BR-{item['city'][:3].upper()}-{index:02d}",
                "name": f"Wezu {item['city']} Branch",
                "address": f"Plot {100 + index}, EV Industrial Zone, {item['city']}",
                "city": item["city"],
                "state": item["state"],
                "pincode": f"560{index:03d}"[:6],
                "organization_id": org_ids.get("WEZU"),
                "contact_number": make_phone(200 + index),
                "is_active": True,
                "created_at": dt(days=-120 + index),
                "updated_at": dt(days=-5),
            }
        )
    runtime.ensure_rows(conn, branch_schema, "branches", ("code",), branch_rows)
    branch_ids = runtime.fetch_map(conn, branch_schema, "branches", "code") if branch_schema else {}

    warehouse_rows = []
    for index, item in enumerate(CITY_BLUEPRINTS[:3], start=1):
        warehouse_rows.append(
            {
                "code": f"WH-{item['city'][:3].upper()}-{index:02d}",
                "name": f"Wezu Warehouse {item['city']}",
                "address": f"Warehouse Cluster {index}, {item['city']}",
                "city": item["city"],
                "state": item["state"],
                "pincode": f"500{index:03d}"[:6],
                "branch_id": branch_ids.get(f"BR-{item['city'][:3].upper()}-{index:02d}"),
                "latitude": item["lat"] + 0.02,
                "longitude": item["lng"] + 0.02,
                "is_active": True,
                "created_at": dt(days=-90 + index),
                "updated_at": dt(days=-3),
            }
        )
    runtime.ensure_rows(conn, warehouse_schema, "warehouses", ("code",), warehouse_rows)

    ctx["org_ids"] = org_ids
    ctx["branch_ids"] = branch_ids
    ctx["warehouse_codes"] = [row["code"] for row in warehouse_rows]


def seed_users(runtime: SeedRuntime, conn: Connection, resolver: Resolver, ctx: dict[str, Any]) -> None:
    users_schema = resolver.schema_for("users")
    admin_users_schema = resolver.schema_for("admin_users")
    admin_user_roles_schema = resolver.schema_for("admin_user_roles")
    user_roles_schema = resolver.schema_for("user_roles")
    addresses_schema = resolver.schema_for("addresses")
    profiles_schema = resolver.schema_for("user_profiles")
    notification_pref_schema = resolver.schema_for("notification_preferences")
    security_questions_schema = resolver.schema_for("security_questions")
    user_security_schema = resolver.schema_for("user_security_questions")
    memberships_schema = resolver.schema_for("user_memberships")
    two_factor_schema = resolver.schema_for("two_factor_auth")

    users_rows = []
    for index, blueprint in enumerate(ADMIN_BLUEPRINTS, start=1):
        users_rows.append(
            {
                "email": blueprint["email"],
                "phone_number": make_phone(index),
                "full_name": blueprint["name"],
                "hashed_password": PASSWORD_HASH,
                "user_type": "ADMIN",
                "status": "ACTIVE",
                "is_superuser": blueprint["role"] == "Super Admin",
                "role_id": ctx["role_ids"].get(blueprint["role"]),
                "kyc_status": "APPROVED",
                "two_factor_enabled": index <= 2,
                "is_email_verified": True,
                "security_question": SECURITY_QUESTION_ROWS[index % len(SECURITY_QUESTION_ROWS)],
                "security_answer": f"answer-{index}",
                "created_at": dt(days=-180 + index),
                "updated_at": dt(days=-2),
                "last_login_at": dt(days=-index),
                "last_login": dt(days=-index),
                "password_changed_at": dt(days=-30),
            }
        )

    for index, full_name in enumerate(CUSTOMER_BLUEPRINTS, start=1):
        users_rows.append(
            {
                "email": "laxmanlaxman1629@gmail.com" if full_name == "Laxman" else f"{slugify(full_name)}@seed.wezu.customer",
                "phone_number": make_phone(9999 + index) if full_name == "Laxman" else make_phone(100 + index),
                "full_name": full_name,
                "hashed_password": get_password_hash("laxman123") if full_name == "Laxman" else PASSWORD_HASH,
                "user_type": "CUSTOMER",
                "status": "ACTIVE",
                "is_superuser": False,
                "role_id": ctx["role_ids"].get("Customer"),
                "kyc_status": "APPROVED" if index <= 14 else "PENDING",
                "two_factor_enabled": False,
                "is_email_verified": True,
                "created_at": dt(days=-90 + index),
                "updated_at": dt(days=-2),
                "last_login_at": dt(days=-(index % 10)),
                "last_login": dt(days=-(index % 10)),
            }
        )

    for index, blueprint in enumerate(DEALER_BLUEPRINTS, start=1):
        users_rows.append(
            {
                "email": blueprint["email"],
                "phone_number": make_phone(300 + index),
                "full_name": blueprint["owner_name"],
                "hashed_password": PASSWORD_HASH,
                "user_type": "DEALER",
                "status": "ACTIVE",
                "role_id": ctx["role_ids"].get("Dealer"),
                "kyc_status": "APPROVED",
                "is_email_verified": True,
                "created_at": dt(days=-75 + index),
                "updated_at": dt(days=-2),
            }
        )

    for index, blueprint in enumerate(SUPPORT_BLUEPRINTS, start=1):
        users_rows.append(
            {
                "email": blueprint["email"],
                "phone_number": make_phone(400 + index),
                "full_name": blueprint["name"],
                "hashed_password": PASSWORD_HASH,
                "user_type": "SUPPORT_AGENT",
                "status": "ACTIVE",
                "role_id": ctx["role_ids"].get("Support Agent"),
                "kyc_status": "APPROVED",
                "is_email_verified": True,
                "created_at": dt(days=-60 + index),
                "updated_at": dt(days=-2),
            }
        )

    for index, blueprint in enumerate(LOGISTICS_BLUEPRINTS, start=1):
        users_rows.append(
            {
                "email": blueprint["email"],
                "phone_number": make_phone(500 + index),
                "full_name": blueprint["name"],
                "hashed_password": PASSWORD_HASH,
                "user_type": "LOGISTICS",
                "status": "ACTIVE",
                "role_id": ctx["role_ids"].get("Logistics Executive"),
                "kyc_status": "APPROVED",
                "is_email_verified": True,
                "created_at": dt(days=-50 + index),
                "updated_at": dt(days=-2),
            }
        )

    runtime.ensure_rows(conn, users_schema, "users", ("email",), users_rows)
    user_ids = runtime.fetch_map(conn, users_schema, "users", "email") if users_schema else {}

    admin_rows = [
        {
            "email": blueprint["email"],
            "hashed_password": PASSWORD_HASH,
            "full_name": blueprint["name"],
            "is_active": True,
            "created_at": dt(days=-180 + idx),
        }
        for idx, blueprint in enumerate(ADMIN_BLUEPRINTS, start=1)
    ]
    runtime.ensure_rows(conn, admin_users_schema, "admin_users", ("email",), admin_rows)
    admin_user_ids = runtime.fetch_map(conn, admin_users_schema, "admin_users", "email") if admin_users_schema else {}

    runtime.ensure_rows(
        conn,
        admin_user_roles_schema,
        "admin_user_roles",
        ("admin_id", "role_id"),
        [
            {"admin_id": admin_user_ids.get(blueprint["email"]), "role_id": ctx["role_ids"].get(blueprint["role"]), "assigned_at": dt(days=-10)}
            for blueprint in ADMIN_BLUEPRINTS
        ],
    )

    runtime.ensure_rows(
        conn,
        user_roles_schema,
        "user_roles",
        ("user_id", "role_id"),
        [{"user_id": user_ids[row["email"]], "role_id": row["role_id"], "created_at": dt(days=-10), "effective_from": dt(days=-10)} for row in users_rows if row["email"] in user_ids],
    )

    profile_rows = []
    all_user_rows = users_rows[:]
    for index, row in enumerate(all_user_rows, start=1):
        email = row["email"]
        city_info = CITY_BLUEPRINTS[(index - 1) % len(CITY_BLUEPRINTS)]
        profile_rows.append(
            {
                "user_id": user_ids.get(email),
                "date_of_birth": date(1990 + (index % 8), ((index - 1) % 12) + 1, ((index - 1) % 26) + 1),
                "gender": "male" if index % 2 else "female",
                "occupation": "Operations" if row["user_type"] == "ADMIN" else "Rider",
                "emergency_contact_name": f"Emergency Contact {index}",
                "emergency_contact_phone": make_phone(800 + index),
                "preferred_language": "en",
                "city": city_info["city"],
                "state": city_info["state"],
            }
        )
    runtime.ensure_rows(conn, profiles_schema, "user_profiles", ("user_id",), profile_rows)

    address_rows = []
    for index, row in enumerate(all_user_rows, start=1):
        city_info = CITY_BLUEPRINTS[(index - 1) % len(CITY_BLUEPRINTS)]
        address_rows.append(
            {
                "user_id": user_ids.get(row["email"]),
                "address_line1": f"House {index}, {city_info['city']} EV Colony",
                "address_line2": "Near Wezu Service Road",
                "street_address": f"{index} Battery Street",
                "city": city_info["city"],
                "state": city_info["state"],
                "postal_code": f"560{index:03d}"[:6],
                "country": "India",
                "is_default": True,
                "type": "home",
                "latitude": city_info["lat"],
                "longitude": city_info["lng"],
                "created_at": dt(days=-70 + index),
                "updated_at": dt(days=-2),
            }
        )
    runtime.ensure_rows(conn, addresses_schema, "addresses", ("user_id", "type"), address_rows)

    pref_rows = [{"user_id": user_ids.get(row["email"]), "preferred_language": "en", "updated_at": dt(days=-1)} for row in all_user_rows]
    runtime.ensure_rows(conn, notification_pref_schema, "notification_preferences", ("user_id",), pref_rows)

    security_rows = [{"question_text": question, "is_active": True, "created_at": dt(days=-40)} for question in SECURITY_QUESTION_ROWS]
    runtime.ensure_rows(conn, security_questions_schema, "security_questions", ("question_text",), security_rows)
    question_ids = runtime.fetch_map(conn, security_questions_schema, "security_questions", "question_text") if security_questions_schema else {}

    user_security_rows = []
    for index, row in enumerate(all_user_rows[:12], start=1):
        question = SECURITY_QUESTION_ROWS[(index - 1) % len(SECURITY_QUESTION_ROWS)]
        user_security_rows.append(
            {
                "user_id": user_ids.get(row["email"]),
                "question_id": question_ids.get(question),
                "hashed_answer": PASSWORD_HASH,
                "created_at": dt(days=-20 + index),
                "updated_at": dt(days=-2),
            }
        )
    runtime.ensure_rows(conn, user_security_schema, "user_security_questions", ("user_id", "question_id"), user_security_rows)

    membership_rows = []
    customer_emails = ["laxmanlaxman1629@gmail.com" if name == "Laxman" else f"{slugify(name)}@seed.wezu.customer" for name in CUSTOMER_BLUEPRINTS[:10]]
    for index, email in enumerate(customer_emails, start=1):
        membership_rows.append(
            {
                "user_id": user_ids.get(email),
                "membership_type": "PREMIUM",
                "status": "ACTIVE",
                "start_date": dt(days=-30),
                "end_date": dt(days=335),
                "created_at": dt(days=-30),
                "updated_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, memberships_schema, "user_memberships", ("user_id",), membership_rows)

    tfa_rows = [
        {
            "user_id": user_ids.get(blueprint["email"]),
            "is_enabled": True,
            "secret": secrets.token_hex(8),
            "backup_codes": [secrets.token_hex(4).upper() for _ in range(3)],
            "created_at": dt(days=-14),
            "updated_at": dt(days=-1),
        }
        for blueprint in ADMIN_BLUEPRINTS[:2]
    ]
    runtime.ensure_rows(conn, two_factor_schema, "two_factor_auth", ("user_id",), tfa_rows)

    ctx["user_ids"] = user_ids
    ctx["admin_user_ids"] = admin_user_ids
    ctx["customer_emails"] = ["laxmanlaxman1629@gmail.com" if name == "Laxman" else f"{slugify(name)}@seed.wezu.customer" for name in CUSTOMER_BLUEPRINTS]
    ctx["dealer_emails"] = [row["email"] for row in DEALER_BLUEPRINTS]
    ctx["support_emails"] = [row["email"] for row in SUPPORT_BLUEPRINTS]
    ctx["logistics_emails"] = [row["email"] for row in LOGISTICS_BLUEPRINTS]


def seed_partner_network(runtime: SeedRuntime, conn: Connection, resolver: Resolver, ctx: dict[str, Any]) -> None:
    vendors_schema = resolver.schema_for("vendors")
    vendor_docs_schema = resolver.schema_for("vendor_documents")
    dealer_schema = resolver.schema_for("dealer_profiles")
    dealer_docs_schema = resolver.schema_for("dealer_documents")
    dealer_apps_schema = resolver.schema_for("dealer_applications")
    dealer_kyc_schema = resolver.schema_for("dealer_kyc_applications")
    dealer_kyc_transition_schema = resolver.schema_for("kyc_state_transitions")
    field_visits_schema = resolver.schema_for("field_visits")
    driver_schema = resolver.schema_for("driver_profiles")

    vendor_rows = []
    for index, blueprint in enumerate(VENDOR_BLUEPRINTS, start=1):
        city_info = city_data(blueprint["city"])
        vendor_rows.append(
            {
                "name": blueprint["name"],
                "email": blueprint["email"],
                "phone": make_phone(600 + index),
                "license_number": f"VEN-LIC-{2026 + index:04d}",
                "commission_rate": 10.0 + index,
                "contract_start_date": dt(days=-90 + index),
                "contract_end_date": dt(days=365),
                "status": "ACTIVE",
                "zone_id": ctx["zone_ids"].get(f"{blueprint['city']} North"),
                "address": f"{blueprint['city']} Vendor Park {index}",
                "gps_coordinates": f"{city_info['lat']},{city_info['lng']}",
                "created_at": dt(days=-90 + index),
                "updated_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, vendors_schema, "vendors", ("email",), vendor_rows)
    vendor_ids = runtime.fetch_map(conn, vendors_schema, "vendors", "email") if vendors_schema else {}

    vendor_doc_rows = []
    for index, blueprint in enumerate(VENDOR_BLUEPRINTS, start=1):
        vendor_doc_rows.extend(
            [
                {
                    "vendor_id": vendor_ids.get(blueprint["email"]),
                    "document_type": "license",
                    "file_path": f"https://seed.wezu.energy/vendors/{index}/license.pdf",
                    "is_verified": True,
                    "uploaded_at": dt(days=-60 + index),
                },
                {
                    "vendor_id": vendor_ids.get(blueprint["email"]),
                    "document_type": "agreement",
                    "file_path": f"https://seed.wezu.energy/vendors/{index}/agreement.pdf",
                    "is_verified": True,
                    "uploaded_at": dt(days=-60 + index),
                },
            ]
        )
    runtime.ensure_rows(conn, vendor_docs_schema, "vendor_documents", ("vendor_id", "document_type"), vendor_doc_rows)

    dealer_rows = []
    for index, blueprint in enumerate(DEALER_BLUEPRINTS, start=1):
        city_info = city_data(blueprint["city"])
        dealer_rows.append(
            {
                "user_id": ctx["user_ids"].get(blueprint["email"]),
                "business_name": blueprint["business_name"],
                "gst_number": make_gst(index),
                "pan_number": make_pan(index),
                "contact_person": blueprint["owner_name"],
                "contact_email": blueprint["email"],
                "contact_phone": make_phone(700 + index),
                "address_line1": f"Dealer Plot {index}, {blueprint['city']}",
                "city": city_info["city"],
                "state": city_info["state"],
                "pincode": f"500{index:03d}"[:6],
                "bank_details": {"bank_name": "HDFC Bank", "account_number": f"1000{index:04d}", "ifsc": "HDFC0001234"},
                "is_active": True,
                "created_at": dt(days=-75 + index),
            }
        )
    runtime.ensure_rows(conn, dealer_schema, "dealer_profiles", ("user_id",), dealer_rows)
    dealer_ids = runtime.fetch_map(conn, dealer_schema, "dealer_profiles", "business_name") if dealer_schema else {}

    dealer_doc_rows = []
    for index, blueprint in enumerate(DEALER_BLUEPRINTS, start=1):
        dealer_doc_rows.extend(
            [
                {
                    "dealer_id": dealer_ids.get(blueprint["business_name"]),
                    "document_type": "gst",
                    "file_url": f"https://seed.wezu.energy/dealers/{index}/gst.pdf",
                    "uploaded_at": dt(days=-70 + index),
                    "is_verified": True,
                },
                {
                    "dealer_id": dealer_ids.get(blueprint["business_name"]),
                    "document_type": "pan",
                    "file_url": f"https://seed.wezu.energy/dealers/{index}/pan.pdf",
                    "uploaded_at": dt(days=-70 + index),
                    "is_verified": True,
                },
            ]
        )
    runtime.ensure_rows(conn, dealer_docs_schema, "dealer_documents", ("dealer_id", "document_type"), dealer_doc_rows)

    dealer_app_rows = []
    for index, blueprint in enumerate(DEALER_BLUEPRINTS, start=1):
        dealer_app_rows.append(
            {
                "dealer_id": dealer_ids.get(blueprint["business_name"]),
                "current_stage": "APPROVED",
                "risk_score": round(0.1 + index * 0.03, 2),
                "status_history": [
                    {"stage": "SUBMITTED", "timestamp": dt(days=-80 + index).isoformat()},
                    {"stage": "APPROVED", "timestamp": dt(days=-60 + index).isoformat()},
                ],
                "created_at": dt(days=-80 + index),
                "updated_at": dt(days=-3),
            }
        )
    runtime.ensure_rows(conn, dealer_apps_schema, "dealer_applications", ("dealer_id",), dealer_app_rows)

    dealer_app_id_by_dealer = {}
    if dealer_apps_schema and runtime.has_table(dealer_apps_schema, "dealer_applications"):
        table = runtime.table(dealer_apps_schema, "dealer_applications", conn=conn)
        if "dealer_id" in table.c and "id" in table.c:
            dealer_app_id_by_dealer = {row[0]: row[1] for row in conn.execute(select(table.c.dealer_id, table.c.id))}

    dealer_kyc_rows = []
    for index, blueprint in enumerate(DEALER_BLUEPRINTS, start=1):
        dealer_kyc_rows.append(
            {
                "user_id": ctx["user_ids"].get(blueprint["email"]),
                "company_name": blueprint["business_name"],
                "pan_number": make_pan(index),
                "gst_number": make_gst(index),
                "bank_details_json": '{"bank_name":"HDFC Bank","account_number":"seed"}',
                "pan_doc_url": f"https://seed.wezu.energy/dealers/{index}/pan.pdf",
                "gst_doc_url": f"https://seed.wezu.energy/dealers/{index}/gst.pdf",
                "reg_cert_url": f"https://seed.wezu.energy/dealers/{index}/registration.pdf",
                "application_state": "APPROVED",
                "created_at": dt(days=-80 + index),
                "updated_at": dt(days=-2),
            }
        )
    runtime.ensure_rows(conn, dealer_kyc_schema, "dealer_kyc_applications", ("user_id",), dealer_kyc_rows)

    dealer_kyc_ids = runtime.fetch_map(conn, dealer_kyc_schema, "dealer_kyc_applications", "user_id") if dealer_kyc_schema else {}
    kyc_transition_rows = []
    for index, blueprint in enumerate(DEALER_BLUEPRINTS, start=1):
        app_id = dealer_kyc_ids.get(ctx["user_ids"].get(blueprint["email"]))
        if not app_id:
            continue
        kyc_transition_rows.extend(
            [
                {
                    "application_id": app_id,
                    "from_state": "REGISTRATION",
                    "to_state": "DOC_SUBMITTED",
                    "reason": "Documents uploaded",
                    "changed_by_user_id": ctx["user_ids"].get(ADMIN_BLUEPRINTS[0]["email"]),
                    "created_at": dt(days=-70 + index),
                },
                {
                    "application_id": app_id,
                    "from_state": "DOC_SUBMITTED",
                    "to_state": "APPROVED",
                    "reason": "Compliance review passed",
                    "changed_by_user_id": ctx["user_ids"].get(ADMIN_BLUEPRINTS[1]["email"]),
                    "created_at": dt(days=-65 + index),
                },
            ]
        )
    runtime.ensure_rows(conn, dealer_kyc_transition_schema, "kyc_state_transitions", ("application_id", "from_state", "to_state"), kyc_transition_rows)

    field_visit_rows = []
    support_user_id = ctx["user_ids"].get(SUPPORT_BLUEPRINTS[0]["email"])
    for index, blueprint in enumerate(DEALER_BLUEPRINTS, start=1):
        field_visit_rows.append(
            {
                "application_id": dealer_app_id_by_dealer.get(dealer_ids.get(blueprint["business_name"])),
                "officer_id": support_user_id,
                "scheduled_date": dt(days=-58 + index),
                "completed_date": dt(days=-57 + index),
                "status": "COMPLETED",
                "report_data": {"site_readiness": "good", "power_backup": True},
                "images": [f"https://seed.wezu.energy/visits/{index}/1.jpg"],
                "created_at": dt(days=-58 + index),
            }
        )
    runtime.ensure_rows(conn, field_visits_schema, "field_visits", ("application_id", "scheduled_date"), field_visit_rows)

    driver_rows = []
    for index, blueprint in enumerate(LOGISTICS_BLUEPRINTS, start=1):
        city_info = city_data(blueprint["city"])
        driver_rows.append(
            {
                "user_id": ctx["user_ids"].get(blueprint["email"]),
                "license_number": f"DL-SEED-{index:04d}",
                "vehicle_type": "e-van" if index == 1 else "scooter",
                "vehicle_plate": f"TS09SE{index:04d}",
                "is_online": True,
                "current_latitude": city_info["lat"],
                "current_longitude": city_info["lng"],
                "last_location_update": dt(hours=-1),
                "rating": 4.6 + (index * 0.1),
                "total_deliveries": 100 + (index * 15),
                "on_time_deliveries": 95 + (index * 12),
                "total_delivery_time_seconds": 7200 + (index * 600),
                "satisfaction_sum": 400.0 + (index * 15),
                "created_at": dt(days=-45 + index),
            }
        )
    runtime.ensure_rows(conn, driver_schema, "driver_profiles", ("user_id",), driver_rows)

    ctx["vendor_ids"] = vendor_ids
    ctx["dealer_profile_ids"] = dealer_ids


def seed_stations_inventory(runtime: SeedRuntime, conn: Connection, resolver: Resolver, ctx: dict[str, Any]) -> None:
    stations_schema = resolver.schema_for("stations")
    images_schema = resolver.schema_for("station_images")
    slots_schema = resolver.schema_for("station_slots")
    heartbeats_schema = resolver.schema_for("station_heartbeats")
    stock_config_schema = resolver.schema_for("station_stock_configs")
    downtime_schema = resolver.schema_for("station_downtimes")
    catalog_schema = resolver.schema_for("battery_catalog")
    batches_schema = resolver.schema_for("battery_batches")
    batteries_schema = resolver.schema_for("batteries")
    iot_schema = resolver.schema_for("iot_devices")
    commands_schema = resolver.schema_for("device_commands")
    firmware_schema = resolver.schema_for("firmware_updates")
    telemetry_schema = resolver.schema_for("telemetry")
    lifecycle_schema = resolver.schema_for("battery_lifecycle_events")
    battery_audit_schema = resolver.schema_for("battery_audit_logs")
    battery_health_hist_schema = resolver.schema_for("battery_health_history")
    battery_health_snapshot_schema = resolver.schema_for("battery_health_snapshots")
    maintenance_sched_schema = resolver.schema_for("battery_maintenance_schedules")
    battery_health_alert_schema = resolver.schema_for("battery_health_alerts")
    stock_schema = resolver.schema_for("stocks")
    stock_move_schema = resolver.schema_for("stock_movements")
    reorder_schema = resolver.schema_for("reorder_requests")
    dismissal_schema = resolver.schema_for("stock_alert_dismissals")
    reservation_schema = resolver.schema_for("battery_reservations")
    inventory_audit_schema = resolver.schema_for("inventory_audit_logs")
    maintenance_record_schema = resolver.schema_for("maintenance_records")
    maintenance_schedule_schema = resolver.schema_for("maintenance_schedules")

    dealer_names = [row["business_name"] for row in DEALER_BLUEPRINTS]
    vendor_emails = [row["email"] for row in VENDOR_BLUEPRINTS]

    station_rows = []
    for index, blueprint in enumerate(STATION_BLUEPRINTS, start=1):
        city_info = city_data(blueprint["city"])
        station_rows.append(
            {
                "name": blueprint["name"],
                "address": f"{blueprint['city']} EV Corridor {index}",
                "city": city_info["city"],
                "latitude": city_info["lat"] + (index * 0.004),
                "longitude": city_info["lng"] + (index * 0.004),
                "zone_id": ctx["zone_ids"].get(f"{blueprint['city']} {blueprint['zone_suffix']}"),
                "owner_id": ctx["user_ids"].get(DEALER_BLUEPRINTS[(index - 1) % len(DEALER_BLUEPRINTS)]["email"]),
                "vendor_id": ctx["vendor_ids"].get(vendor_emails[(index - 1) % len(vendor_emails)]),
                "dealer_id": ctx["dealer_profile_ids"].get(dealer_names[(index - 1) % len(dealer_names)]),
                "station_type": "AUTOMATED" if index % 2 else "HYBRID",
                "total_slots": 10,
                "power_rating_kw": 30.0 + index,
                "max_capacity": 24,
                "charger_type": "FAST_DC",
                "temperature_control": True,
                "safety_features": "fire_suppression,cctv,remote_lock",
                "status": "OPERATIONAL",
                "available_batteries": 6,
                "available_slots": 4,
                "contact_phone": make_phone(900 + index),
                "operating_hours": '{"all_days":"06:00-23:00"}',
                "is_24x7": index % 3 == 0,
                "amenities": "parking,wifi,restroom",
                "image_url": f"https://seed.wezu.energy/stations/{index}.jpg",
                "rating": 4.2 + ((index % 3) * 0.2),
                "total_reviews": 15 + index,
                "last_heartbeat": dt(hours=-1),
                "created_at": dt(days=-60 + index),
                "updated_at": dt(days=-1),
            }
        )
    print(f"   [stations] seeding {len(station_rows)} rows...")
    runtime.ensure_rows(conn, stations_schema, "stations", ("name",), station_rows)
    station_ids = runtime.fetch_map(conn, stations_schema, "stations", "name") if stations_schema else {}

    station_image_rows = [
        {"station_id": station_ids.get(row["name"]), "url": f"https://seed.wezu.energy/stations/{idx}.jpg", "is_primary": True, "created_at": dt(days=-15)}
        for idx, row in enumerate(station_rows, start=1)
    ]
    print(f"   [station_images] seeding {len(station_image_rows)} rows...")
    runtime.ensure_rows(conn, images_schema, "station_images", ("station_id", "url"), station_image_rows)

    slot_rows = []
    for station_index, row in enumerate(station_rows, start=1):
        for slot_number in range(1, 11):
            slot_rows.append(
                {
                    "station_id": station_ids.get(row["name"]),
                    "slot_number": slot_number,
                    "status": "READY" if slot_number <= 6 else "EMPTY",
                    "is_locked": False,
                    "current_power_w": 420.0 if slot_number <= 6 else 0.0,
                    "last_heartbeat": dt(hours=-1),
                }
            )
    print(f"   [station_slots] seeding {len(slot_rows)} rows...")
    runtime.ensure_rows(conn, slots_schema, "station_slots", ("station_id", "slot_number"), slot_rows)

    heartbeat_rows = [
        {
            "station_id": station_ids.get(row["name"]),
            "status": "ONLINE",
            "temperature_c": 29.0 + idx,
            "power_kw": 12.0 + idx,
            "created_at": dt(hours=-1),
            "recorded_at": dt(hours=-1),
            "last_seen_at": dt(hours=-1),
        }
        for idx, row in enumerate(station_rows, start=1)
    ]
    print(f"   [station_heartbeats] seeding {len(heartbeat_rows)} rows...")
    runtime.ensure_rows(conn, heartbeats_schema, "station_heartbeats", ("station_id",), heartbeat_rows)

    stock_config_rows = [
        {
            "station_id": station_ids.get(row["name"]),
            "max_capacity": 24,
            "reorder_point": 6,
            "reorder_quantity": 8,
            "manager_email": ADMIN_BLUEPRINTS[4]["email"],
            "manager_phone": make_phone(990 + idx),
            "updated_by": ctx["user_ids"].get(ADMIN_BLUEPRINTS[4]["email"]),
            "updated_at": dt(days=-1),
        }
        for idx, row in enumerate(station_rows, start=1)
    ]
    print(f"   [station_stock_configs] seeding {len(stock_config_rows)} rows...")
    runtime.ensure_rows(conn, stock_config_schema, "station_stock_configs", ("station_id",), stock_config_rows)

    downtime_rows = [
        {
            "station_id": station_ids.get(station_rows[1]["name"]),
            "start_time": dt(days=-12, hours=2),
            "end_time": dt(days=-12, hours=6),
            "reason": "Scheduled inverter maintenance",
        },
        {
            "station_id": station_ids.get(station_rows[6]["name"]),
            "start_time": dt(days=-4, hours=1),
            "end_time": dt(days=-4, hours=3),
            "reason": "Cooling system inspection",
        },
    ]
    print(f"   [station_downtimes] seeding {len(downtime_rows)} rows...")
    runtime.ensure_rows(conn, downtime_schema, "station_downtimes", ("station_id", "start_time"), downtime_rows)

    catalog_rows = []
    for index, item in enumerate(BATT_CATALOG, start=1):
        row = safe_dict(item)
        row["image_url"] = f"https://seed.wezu.energy/catalog/battery-{index}.png"
        row["is_active"] = True
        row["created_at"] = dt(days=-120 + index)
        row["updated_at"] = dt(days=-2)
        catalog_rows.append(row)
    print(f"   [battery_catalog] seeding {len(catalog_rows)} rows...")
    runtime.ensure_rows(conn, catalog_schema, "battery_catalog", ("model",), catalog_rows)
    catalog_ids = runtime.fetch_map(conn, catalog_schema, "battery_catalog", "model") if catalog_schema else {}

    batch_rows = []
    for index, item in enumerate(BATT_CATALOG, start=1):
        batch_rows.append(
            {
                "batch_number": f"BATCH-2026-{index:03d}",
                "manufacturer": item["brand"],
                "production_date": dt(days=-150 + (index * 10)),
            }
        )
    print(f"   [battery_batches] seeding {len(batch_rows)} rows...")
    runtime.ensure_rows(conn, batches_schema, "battery_batches", ("batch_number",), batch_rows)

    customer_ids = [ctx["user_ids"][email] for email in ctx["customer_emails"]]
    station_id_list = [station_ids[row["name"]] for row in station_rows if row["name"] in station_ids]

    battery_rows = []
    for index in range(1, 51):
        sku = BATT_CATALOG[(index - 1) % len(BATT_CATALOG)]
        station_id = station_id_list[(index - 1) % len(station_id_list)]
        rented = index % 8 == 0
        status = "RENTED" if rented else ("CHARGING" if index % 6 == 0 else ("MAINTENANCE" if index % 11 == 0 else "AVAILABLE"))
        current_user_id = customer_ids[(index - 1) % len(customer_ids)] if rented else None
        battery_rows.append(
            {
                "serial_number": f"WZ-SEED-BAT-{index:03d}",
                "qr_code_data": f"WZ-QR-{index:03d}",
                "iot_device_id": f"IOT-SEED-{index:03d}",
                "sku_id": catalog_ids.get(sku["model"]),
                "spec_id": catalog_ids.get(sku["model"]),
                "station_id": None if rented else station_id,
                "current_user_id": current_user_id,
                "created_by": ctx["user_ids"].get(ADMIN_BLUEPRINTS[0]["email"]),
                "status": status,
                "health_status": "EXCELLENT" if index % 5 else "GOOD",
                "current_charge": 94.0 - (index % 50),
                "health_percentage": 98.0 - (index % 12),
                "cycle_count": 40 + index,
                "total_cycles": 1800 + (index * 5),
                "temperature_c": 28.0 + (index % 7),
                "manufacturer": "Wezu",
                "battery_type": f"{int(sku['voltage'])}V/{int(sku['capacity_ah'])}Ah",
                "notes": "Seeded production-like battery record",
                "location_type": "WAREHOUSE" if rented else "STATION",
                "manufacture_date": dt(days=-180 + index),
                "purchase_date": dt(days=-160 + index),
                "warranty_expiry": dt(days=540 + index),
                "last_charged_at": dt(days=-(index % 7)),
                "last_inspected_at": dt(days=-(index % 14)),
                "last_maintenance_date": dt(days=-(index % 21)),
                "last_maintenance_cycles": 20 + index,
                "state_of_health": 97.0 - (index % 8),
                "temperature_history": [27.8, 28.1, 28.4],
                "charge_cycles": 30 + index,
                "location_id": station_id,
                "last_telemetry_at": dt(hours=-2),
                "created_at": dt(days=-120 + index),
                "updated_at": dt(days=-1),
            }
        )
    print(f"   [batteries] seeding {len(battery_rows)} rows...")
    runtime.ensure_rows(conn, batteries_schema, "batteries", ("serial_number",), battery_rows)
    battery_ids = runtime.fetch_map(conn, batteries_schema, "batteries", "serial_number") if batteries_schema else {}

    iot_rows = []
    for index in range(1, 21):
        battery_id = battery_ids.get(f"WZ-SEED-BAT-{index:03d}")
        iot_rows.append(
            {
                "device_id": f"IOT-SEED-{index:03d}",
                "device_type": "tracker_v2" if index % 2 else "smart_bms",
                "firmware_version": f"v2.{index % 5}.{index % 3}",
                "status": "ONLINE",
                "communication_protocol": "mqtt",
                "battery_id": battery_id,
                "auth_token": secrets.token_hex(12),
                "last_heartbeat": dt(hours=-1),
                "last_ip_address": f"10.20.30.{index}",
                "created_at": dt(days=-90 + index),
                "updated_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, iot_schema, "iot_devices", ("device_id",), iot_rows)
    iot_ids = runtime.fetch_map(conn, iot_schema, "iot_devices", "device_id") if iot_schema else {}

    command_rows = []
    for index in range(1, 11):
        command_rows.append(
            {
                "device_id": iot_ids.get(f"IOT-SEED-{index:03d}"),
                "command_type": "DIAGNOSTIC" if index % 2 else "REBOOT",
                "payload": '{"requested_by":"seed"}',
                "status": "EXECUTED",
                "created_at": dt(days=-5, hours=index),
                "sent_at": dt(days=-5, hours=index, minutes=5),
                "executed_at": dt(days=-5, hours=index, minutes=8),
                "response_data": '{"ok":true}',
            }
        )
    runtime.ensure_rows(conn, commands_schema, "device_commands", ("device_id", "command_type", "created_at"), command_rows)

    firmware_rows = [
        {"version": "v2.0.0", "file_url": "https://seed.wezu.energy/fw/tracker_v2_200.bin", "checksum": secrets.token_hex(16), "device_type": "tracker_v2", "is_critical": True, "created_at": dt(days=-20)},
        {"version": "v2.1.0", "file_url": "https://seed.wezu.energy/fw/smart_bms_210.bin", "checksum": secrets.token_hex(16), "device_type": "smart_bms", "is_critical": False, "created_at": dt(days=-10)},
    ]
    runtime.ensure_rows(conn, firmware_schema, "firmware_updates", ("version", "device_type"), firmware_rows)

    telemetry_rows = []
    for index in range(1, 31):
        station = STATION_BLUEPRINTS[(index - 1) % len(STATION_BLUEPRINTS)]
        city_info = city_data(station["city"])
        telemetry_rows.append(
            {
                "device_id": f"IOT-SEED-{((index - 1) % 20) + 1:03d}",
                "battery_id": battery_ids.get(f"WZ-SEED-BAT-{((index - 1) % 50) + 1:03d}"),
                "rental_id": None,
                "latitude": city_info["lat"] + 0.005,
                "longitude": city_info["lng"] + 0.005,
                "speed_kmph": 0.0 if index % 3 else 18.0,
                "voltage": 48.0 + (index % 5),
                "current": 6.5 + (index % 3),
                "temperature": 28.0 + (index % 4),
                "soc": 90.0 - (index % 25),
                "soh": 95.0 - (index % 6),
                "range_remaining_km": 55.0 - index,
                "timestamp": dt(hours=-index),
                "metadata_json": '{"source":"seed"}',
            }
        )
    runtime.ensure_rows(conn, telemetry_schema, "telemetry", ("device_id", "timestamp"), telemetry_rows)

    lifecycle_rows = []
    audit_rows = []
    health_history_rows = []
    snapshot_rows = []
    maintenance_rows = []
    health_alert_rows = []
    for index in range(1, 51):
        battery_id = battery_ids.get(f"WZ-SEED-BAT-{index:03d}")
        actor_id = ctx["user_ids"].get(ADMIN_BLUEPRINTS[0]["email"])
        lifecycle_rows.extend(
            [
                {"battery_id": battery_id, "event_type": "created", "description": "Battery record created", "actor_id": actor_id, "timestamp": dt(days=-120 + index)},
                {"battery_id": battery_id, "event_type": "assigned", "description": "Battery assigned to active inventory pool", "actor_id": actor_id, "timestamp": dt(days=-90 + index)},
            ]
        )
        audit_rows.append(
            {
                "battery_id": battery_id,
                "changed_by": actor_id,
                "field_changed": "status",
                "old_value": "NEW",
                "new_value": "AVAILABLE",
                "reason": "Initial commissioning",
                "timestamp": dt(days=-90 + index),
            }
        )
        for offset in (60, 20, 5):
            health_history_rows.append(
                {
                    "battery_id": battery_id,
                    "health_percentage": 98.0 - ((index + offset) % 10),
                    "recorded_at": dt(days=-offset),
                }
            )
            snapshot_rows.append(
                {
                    "battery_id": battery_id,
                    "health_percentage": 98.0 - ((index + offset) % 10),
                    "voltage": 48.0 + (index % 5),
                    "temperature": 27.0 + (index % 6),
                    "internal_resistance": 14.0 + (index % 3),
                    "charge_cycles": 25 + index,
                    "snapshot_type": "IOT_SYNC" if offset == 5 else "AUTOMATED",
                    "recorded_by": actor_id,
                    "recorded_at": dt(days=-offset),
                }
            )
        if index <= 15:
            maintenance_rows.append(
                {
                    "battery_id": battery_id,
                    "scheduled_date": dt(days=3 + index),
                    "maintenance_type": "INSPECTION",
                    "priority": "MEDIUM",
                    "assigned_to": ctx["user_ids"].get(SUPPORT_BLUEPRINTS[index % len(SUPPORT_BLUEPRINTS)]["email"]),
                    "status": "SCHEDULED",
                    "notes": "Routine preventive inspection",
                    "health_before": 92.0,
                    "created_by": actor_id,
                    "created_at": dt(days=-2),
                }
            )
        if index <= 10:
            health_alert_rows.append(
                {
                    "battery_id": battery_id,
                    "alert_type": "HIGH_TEMP",
                    "severity": "WARNING",
                    "message": "Temperature trended above preferred threshold during peak hours.",
                    "is_resolved": index % 2 == 0,
                    "resolved_by": actor_id if index % 2 == 0 else None,
                    "resolved_at": dt(days=-1) if index % 2 == 0 else None,
                    "resolution_reason": "Cooling inspection completed" if index % 2 == 0 else None,
                    "created_at": dt(days=-3),
                }
            )
    runtime.ensure_rows(conn, lifecycle_schema, "battery_lifecycle_events", ("battery_id", "event_type", "timestamp"), lifecycle_rows)
    runtime.ensure_rows(conn, battery_audit_schema, "battery_audit_logs", ("battery_id", "field_changed", "timestamp"), audit_rows)
    runtime.ensure_rows(conn, battery_health_hist_schema, "battery_health_history", ("battery_id", "recorded_at"), health_history_rows)
    runtime.ensure_rows(conn, battery_health_snapshot_schema, "battery_health_snapshots", ("battery_id", "recorded_at"), snapshot_rows)
    runtime.ensure_rows(conn, maintenance_sched_schema, "battery_maintenance_schedules", ("battery_id", "scheduled_date"), maintenance_rows)
    runtime.ensure_rows(conn, battery_health_alert_schema, "battery_health_alerts", ("battery_id", "alert_type", "created_at"), health_alert_rows)

    warehouse_schema = resolver.schema_for("warehouses")
    warehouse_table = runtime.table(warehouse_schema, "warehouses", conn=conn) if warehouse_schema and runtime.has_table(warehouse_schema, "warehouses") else None
    warehouse_ids = list(conn.execute(select(warehouse_table.c.id).order_by(warehouse_table.c.id)).scalars()) if warehouse_table is not None else []
    stock_rows = []
    for warehouse_index, warehouse_id in enumerate(warehouse_ids, start=1):
        for catalog_index, catalog_item in enumerate(BATT_CATALOG, start=1):
            stock_rows.append(
                {
                    "warehouse_id": warehouse_id,
                    "product_id": catalog_ids.get(catalog_item["model"]),
                    "quantity_on_hand": 20 + catalog_index,
                    "quantity_available": 18 + catalog_index,
                    "quantity_reserved": 2,
                    "quantity_damaged": 0,
                    "quantity_in_transit": 1,
                    "reorder_level": 8,
                    "created_at": dt(days=-20),
                    "updated_at": dt(days=-1),
                }
            )
    runtime.ensure_rows(conn, stock_schema, "stocks", ("warehouse_id", "product_id"), stock_rows)

    stock_table = runtime.table(stock_schema, "stocks", conn=conn) if stock_schema and runtime.has_table(stock_schema, "stocks") else None
    stock_lookup = {}
    if stock_table is not None and "warehouse_id" in stock_table.c and "product_id" in stock_table.c and "id" in stock_table.c:
        stock_lookup = {(row[0], row[1]): row[2] for row in conn.execute(select(stock_table.c.warehouse_id, stock_table.c.product_id, stock_table.c.id))}

    stock_movement_rows = []
    for warehouse_index, warehouse_id in enumerate(warehouse_ids, start=1):
        for catalog_item in BATT_CATALOG[:2]:
            stock_id = stock_lookup.get((warehouse_id, catalog_ids.get(catalog_item["model"])))
            stock_movement_rows.append(
                {
                    "stock_id": stock_id,
                    "transaction_type": "GRN",
                    "quantity": 10,
                    "direction": "IN",
                    "reference_type": "GRN",
                    "reference_id": f"GRN-{warehouse_id}-{catalog_item['model']}",
                    "battery_ids": "[1,2,3]",
                    "notes": "Initial stock intake",
                    "created_at": dt(days=-18),
                    "created_by": ctx["user_ids"].get(ADMIN_BLUEPRINTS[0]["email"]),
                }
            )
    runtime.ensure_rows(conn, stock_move_schema, "stock_movements", ("stock_id", "reference_id"), stock_movement_rows)

    reorder_rows = []
    for index, row in enumerate(station_rows[:3], start=1):
        reorder_rows.append(
            {
                "station_id": station_ids.get(row["name"]),
                "requested_quantity": 6 + index,
                "reason": "Weekend demand forecast spike",
                "status": "APPROVED",
                "created_by": ctx["user_ids"].get(ADMIN_BLUEPRINTS[4]["email"]),
                "created_at": dt(days=-3),
                "fulfilled_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, reorder_schema, "reorder_requests", ("station_id", "created_at"), reorder_rows)

    dismissal_rows = [
        {
            "station_id": station_ids.get(station_rows[0]["name"]),
            "reason": "Handled via local restock",
            "dismissed_by": ctx["user_ids"].get(ADMIN_BLUEPRINTS[4]["email"]),
            "dismissed_at": dt(days=-2),
            "is_active": True,
        }
    ]
    runtime.ensure_rows(conn, dismissal_schema, "stock_alert_dismissals", ("station_id", "dismissed_at"), dismissal_rows)

    reservation_rows = []
    for index, email in enumerate(ctx["customer_emails"][:5], start=1):
        reservation_rows.append(
            {
                "user_id": ctx["user_ids"].get(email),
                "station_id": station_ids.get(station_rows[index - 1]["name"]),
                "battery_id": battery_ids.get(f"WZ-SEED-BAT-{index:03d}"),
                "start_time": dt(hours=index),
                "end_time": dt(hours=index + 2),
                "status": "ACTIVE",
                "created_at": dt(hours=index),
                "updated_at": dt(hours=index),
            }
        )
    runtime.ensure_rows(conn, reservation_schema, "battery_reservations", ("user_id", "station_id", "start_time"), reservation_rows)

    inventory_audit_rows = []
    for index in range(1, 11):
        inventory_audit_rows.append(
            {
                "battery_id": battery_ids.get(f"WZ-SEED-BAT-{index:03d}"),
                "action_type": "RESTOCK",
                "from_location_type": "warehouse",
                "from_location_id": warehouse_ids[(index - 1) % len(warehouse_ids)] if warehouse_ids else None,
                "to_location_type": "station",
                "to_location_id": station_id_list[(index - 1) % len(station_id_list)],
                "actor_id": ctx["user_ids"].get(ADMIN_BLUEPRINTS[0]["email"]),
                "notes": "Seed inventory movement",
                "timestamp": dt(days=-14 + index),
            }
        )
    runtime.ensure_rows(conn, inventory_audit_schema, "inventory_audit_logs", ("battery_id", "timestamp"), inventory_audit_rows)

    maintenance_record_rows = [
        {
            "entity_type": "battery",
            "entity_id": battery_ids.get("WZ-SEED-BAT-005"),
            "technician_id": ctx["user_ids"].get(SUPPORT_BLUEPRINTS[0]["email"]),
            "maintenance_type": "preventive",
            "description": "Connector tightening and health calibration",
            "cost": 450.0,
            "parts_replaced": '["thermal_pad"]',
            "status": "completed",
            "performed_at": dt(days=-8),
        },
        {
            "entity_type": "station",
            "entity_id": station_ids.get(station_rows[0]["name"]),
            "technician_id": ctx["user_ids"].get(SUPPORT_BLUEPRINTS[1]["email"]),
            "maintenance_type": "preventive",
            "description": "Power cabinet cleaning and diagnostics",
            "cost": 1200.0,
            "parts_replaced": '["fan_filter"]',
            "status": "completed",
            "performed_at": dt(days=-6),
        },
    ]
    runtime.ensure_rows(conn, maintenance_record_schema, "maintenance_records", ("entity_type", "entity_id", "performed_at"), maintenance_record_rows)

    maintenance_schedule_rows = [
        {
            "entity_type": "battery",
            "model_name": "WZ-PC-4830",
            "interval_days": 30,
            "interval_cycles": 100,
            "last_maintenance_date": dt(days=-8),
            "next_maintenance_date": dt(days=22),
            "checklist": '["visual_check","connector_check","calibration"]',
            "created_at": dt(days=-30),
        },
        {
            "entity_type": "station",
            "model_name": "Station Cabinet v2",
            "interval_days": 45,
            "checklist": '["power_check","fire_system","network_check"]',
            "last_maintenance_date": dt(days=-6),
            "next_maintenance_date": dt(days=39),
            "created_at": dt(days=-45),
        },
    ]
    runtime.ensure_rows(conn, maintenance_schedule_schema, "maintenance_schedules", ("entity_type", "model_name"), maintenance_schedule_rows)

    ctx["station_ids"] = station_ids
    ctx["station_id_list"] = station_id_list
    ctx["battery_ids"] = battery_ids
    ctx["catalog_ids"] = catalog_ids


def seed_finance_and_rentals(runtime: SeedRuntime, conn: Connection, resolver: Resolver, ctx: dict[str, Any]) -> None:
    wallet_schema = resolver.schema_for("wallets")
    withdrawal_schema = resolver.schema_for("wallet_withdrawal_requests")
    rentals_schema = resolver.schema_for("rentals")
    rental_events_schema = resolver.schema_for("rental_events")
    swap_schema = resolver.schema_for("swap_sessions")
    swap_pref_schema = resolver.schema_for("swap_preferences")
    swap_suggestion_schema = resolver.schema_for("swap_suggestions")
    rental_extension_schema = resolver.schema_for("rental_extensions")
    rental_pause_schema = resolver.schema_for("rental_pauses")
    purchase_schema = resolver.schema_for("purchases")
    late_fee_schema = resolver.schema_for("late_fees")
    waiver_schema = resolver.schema_for("late_fee_waivers")
    transaction_schema = resolver.schema_for("transactions")
    payment_schema = resolver.schema_for("payment_transactions")
    invoice_schema = resolver.schema_for("invoices")
    refund_schema = resolver.schema_for("refunds")
    chargeback_schema = resolver.schema_for("chargebacks")
    settlement_schema = resolver.schema_for("settlements")
    settlement_dispute_schema = resolver.schema_for("settlement_disputes")
    commission_cfg_schema = resolver.schema_for("commission_configs")
    commission_tier_schema = resolver.schema_for("commission_tiers")
    commission_log_schema = resolver.schema_for("commission_logs")
    commission_schema = resolver.schema_for("commissions")

    user_ids = ctx["user_ids"]
    customer_ids = [user_ids[email] for email in ctx["customer_emails"]]

    wallet_rows = []
    for index, user_id in enumerate(user_ids.values(), start=1):
        wallet_rows.append(
            {
                "user_id": user_id,
                "balance": 1500.0 + (index * 50),
                "cashback_balance": 80.0 + (index % 5) * 10,
                "currency": "INR",
                "is_frozen": False,
                "updated_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, wallet_schema, "wallets", ("user_id",), wallet_rows)
    wallet_by_user = {}
    if wallet_schema:
        wallet_table = runtime.table(wallet_schema, "wallets", conn=conn)
        if "user_id" in wallet_table.c and "id" in wallet_table.c:
            wallet_by_user = {row[0]: row[1] for row in conn.execute(select(wallet_table.c.user_id, wallet_table.c.id))}

    withdrawal_rows = []
    for index, email in enumerate(ctx["dealer_emails"][:3], start=1):
        wallet_id = wallet_by_user.get(user_ids[email])
        withdrawal_rows.append(
            {
                "wallet_id": wallet_id,
                "amount": 2500.0 + (index * 500),
                "status": "processed",
                "bank_details": '{"bank":"HDFC","account":"seed"}',
                "created_at": dt(days=-10 + index),
                "processed_at": dt(days=-8 + index),
            }
        )
    runtime.ensure_rows(conn, withdrawal_schema, "wallet_withdrawal_requests", ("wallet_id", "created_at"), withdrawal_rows)

    rental_rows = []
    for index in range(1, 31):
        customer_id = customer_ids[(index - 1) % len(customer_ids)]
        battery_key = f"WZ-SEED-BAT-{index:03d}"
        battery_id = ctx["battery_ids"].get(battery_key)
        start_station_id = ctx["station_id_list"][(index - 1) % len(ctx["station_id_list"])]
        end_station_id = ctx["station_id_list"][index % len(ctx["station_id_list"])]
        start_time = dt(days=-(index + 2))
        expected_end = start_time + timedelta(days=3)
        completed = index <= 20
        overdue = 20 < index <= 25
        status = "COMPLETED" if completed else ("OVERDUE" if overdue else "ACTIVE")
        end_time = expected_end + timedelta(hours=6) if completed or overdue else None
        rental_rows.append(
            {
                "user_id": customer_id,
                "battery_id": battery_id,
                "start_station_id": start_station_id,
                "end_station_id": end_station_id if completed or overdue else None,
                "start_time": start_time,
                "expected_end_time": expected_end,
                "end_time": end_time if completed else None,
                "total_amount": 600.0 + (index * 20),
                "security_deposit": 500.0,
                "late_fee": 150.0 if overdue else 0.0,
                "currency": "INR",
                "is_deposit_refunded": completed,
                "status": status,
                "start_battery_level": 96.0,
                "end_battery_level": 24.0 if completed or overdue else 0.0,
                "distance_traveled_km": 28.0 + index,
                "created_at": start_time,
                "updated_at": end_time or dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, rentals_schema, "rentals", ("user_id", "battery_id", "start_time"), rental_rows)

    rental_ids: list[int] = runtime.fetch_ids(conn, rentals_schema, "rentals")
    rental_rows_by_id = dict(zip(rental_ids[: len(rental_rows)], rental_rows))

    rental_event_rows = []
    for rental_id in rental_ids[:30]:
        row = rental_rows_by_id.get(rental_id)
        if not row:
            continue
        rental_event_rows.extend(
            [
                {
                    "rental_id": rental_id,
                    "event_type": "STARTED",
                    "description": "Rental started from station inventory",
                    "station_id": row["start_station_id"],
                    "battery_id": row["battery_id"],
                    "created_at": row["start_time"],
                },
                {
                    "rental_id": rental_id,
                    "event_type": "RETURNED" if row["status"] == "COMPLETED" else "IN_USE",
                    "description": "Rental progress update",
                    "station_id": row["end_station_id"] or row["start_station_id"],
                    "battery_id": row["battery_id"],
                    "created_at": row["updated_at"],
                },
            ]
        )
    runtime.ensure_rows(conn, rental_events_schema, "rental_events", ("rental_id", "event_type", "created_at"), rental_event_rows)

    swap_rows = []
    for index in range(1, 16):
        rental_id = rental_ids[index - 1]
        current_row = rental_rows_by_id[rental_id]
        swap_rows.append(
            {
                "rental_id": rental_id,
                "user_id": current_row["user_id"],
                "station_id": current_row["start_station_id"],
                "old_battery_id": current_row["battery_id"],
                "new_battery_id": ctx["battery_ids"].get(f"WZ-SEED-BAT-{30 + index:03d}"),
                "old_battery_soc": 15.0 + index,
                "new_battery_soc": 96.0,
                "swap_amount": 79.0 + index,
                "currency": "INR",
                "status": "COMPLETED",
                "payment_status": "PAID",
                "created_at": current_row["start_time"] + timedelta(days=1),
                "completed_at": current_row["start_time"] + timedelta(days=1, minutes=10),
            }
        )
    runtime.ensure_rows(conn, swap_schema, "swap_sessions", ("user_id", "station_id", "created_at"), swap_rows)

    swap_pref_rows = []
    for index, email in enumerate(ctx["customer_emails"][:10], start=1):
        swap_pref_rows.append(
            {
                "user_id": user_ids[email],
                "favorite_station_ids": f"[{ctx['station_id_list'][0]}]",
                "blacklisted_station_ids": "[]",
                "preferred_swap_time": "evening",
                "max_acceptable_distance_km": 8.0 + (index % 3),
                "notify_when_battery_below": 25,
                "notify_suggestion_radius_km": 5.0,
                "updated_at": dt(days=-2),
            }
        )
    runtime.ensure_rows(conn, swap_pref_schema, "swap_preferences", ("user_id",), swap_pref_rows)

    swap_suggestion_rows = []
    for index, rental_id in enumerate(rental_ids[:10], start=1):
        row = rental_rows_by_id[rental_id]
        station_choice = ctx["station_id_list"][(index + 1) % len(ctx["station_id_list"])]
        swap_suggestion_rows.append(
            {
                "user_id": row["user_id"],
                "rental_id": rental_id,
                "current_battery_soc": 19.0 + index,
                "current_location_lat": 17.42 + (index * 0.01),
                "current_location_lng": 78.38 + (index * 0.01),
                "suggested_station_id": station_choice,
                "priority_rank": 1,
                "distance_km": 2.5 + index,
                "estimated_travel_time_minutes": 8 + index,
                "station_availability_score": 88.0,
                "station_rating": 4.5,
                "predicted_wait_time_minutes": 6,
                "predicted_battery_availability": 5,
                "preference_match_score": 82.0,
                "total_score": 86.0,
                "was_accepted": index % 2 == 0,
                "accepted_at": dt(days=-1) if index % 2 == 0 else None,
                "created_at": dt(days=-2),
            }
        )
    runtime.ensure_rows(conn, swap_suggestion_schema, "swap_suggestions", ("user_id", "rental_id", "suggested_station_id"), swap_suggestion_rows)

    payment_rows = []
    for index in range(1, 41):
        payment_rows.append(
            {
                "user_id": customer_ids[(index - 1) % len(customer_ids)],
                "amount": 550.0 + (index * 30),
                "currency": "INR",
                "status": "SUCCESS" if index <= 35 else "PENDING",
                "payment_method": "UPI" if index % 2 else "CARD",
                "razorpay_order_id": f"order_seed_{index:04d}",
                "razorpay_payment_id": f"pay_seed_{index:04d}",
                "razorpay_signature": f"sig_seed_{index:04d}",
                "created_at": dt(days=-(index % 20)),
                "updated_at": dt(days=-(index % 20)),
            }
        )
    runtime.ensure_rows(conn, payment_schema, "payment_transactions", ("razorpay_order_id",), payment_rows)

    payment_table = runtime.table(payment_schema, "payment_transactions", conn=conn) if payment_schema and runtime.has_table(payment_schema, "payment_transactions") else None
    payment_id_by_order = {}
    if payment_table is not None and "razorpay_order_id" in payment_table.c and "id" in payment_table.c:
        payment_id_by_order = {row[0]: row[1] for row in conn.execute(select(payment_table.c.razorpay_order_id, payment_table.c.id))}

    transaction_rows = []
    transaction_types = ["RENTAL_PAYMENT", "SECURITY_DEPOSIT", "WALLET_TOPUP", "SWAP_FEE", "LATE_FEE"]
    for index in range(1, 41):
        user_id = customer_ids[(index - 1) % len(customer_ids)]
        rental_id = rental_ids[(index - 1) % len(rental_ids)] if index <= len(rental_ids) else None
        transaction_rows.append(
            {
                "user_id": user_id,
                "rental_id": rental_id,
                "wallet_id": wallet_by_user.get(user_id),
                "amount": 450.0 + (index * 25),
                "currency": "INR",
                "transaction_type": transaction_types[(index - 1) % len(transaction_types)],
                "status": "SUCCESS" if index <= 36 else "PENDING",
                "payment_method": "UPI" if index % 2 else "CARD",
                "payment_gateway_ref": f"txn_seed_{index:04d}",
                "description": f"Seed transaction {index}",
                "created_at": dt(days=-(index % 18)),
                "updated_at": dt(days=-(index % 18)),
            }
        )
    runtime.ensure_rows(conn, transaction_schema, "transactions", ("payment_gateway_ref",), transaction_rows)

    transaction_table = runtime.table(transaction_schema, "transactions", conn=conn) if transaction_schema and runtime.has_table(transaction_schema, "transactions") else None
    transaction_id_by_ref = {}
    if transaction_table is not None and "payment_gateway_ref" in transaction_table.c and "id" in transaction_table.c:
        transaction_id_by_ref = {row[0]: row[1] for row in conn.execute(select(transaction_table.c.payment_gateway_ref, transaction_table.c.id))}

    extension_rows = []
    for index in range(1, 6):
        rental_id = rental_ids[index - 1]
        base_row = rental_rows_by_id[rental_id]
        extension_rows.append(
            {
                "rental_id": rental_id,
                "user_id": base_row["user_id"],
                "current_end_date": base_row["expected_end_time"],
                "requested_end_date": base_row["expected_end_time"] + timedelta(days=2),
                "extension_days": 2,
                "status": "APPROVED",
                "additional_cost": 120.0,
                "payment_status": "PAID",
                "payment_transaction_id": payment_id_by_order.get(f"order_seed_{index:04d}"),
                "reason": "Customer requested weekend extension",
                "approved_by": user_ids[ADMIN_BLUEPRINTS[1]["email"]],
                "approved_at": dt(days=-1),
                "created_at": dt(days=-2),
                "updated_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, rental_extension_schema, "rental_extensions", ("rental_id", "requested_end_date"), extension_rows)

    pause_rows = []
    for index in range(6, 9):
        rental_id = rental_ids[index - 1]
        base_row = rental_rows_by_id[rental_id]
        pause_rows.append(
            {
                "rental_id": rental_id,
                "user_id": base_row["user_id"],
                "pause_start_date": dt(days=-3),
                "pause_end_date": dt(days=1),
                "pause_days": 4,
                "status": "APPROVED",
                "reason": "Customer travel request",
                "daily_pause_charge": 20.0,
                "total_pause_cost": 80.0,
                "battery_returned_to_station_id": base_row["start_station_id"],
                "battery_returned_at": dt(days=-3),
                "approved_by": user_ids[ADMIN_BLUEPRINTS[1]["email"]],
                "approved_at": dt(days=-3),
                "created_at": dt(days=-4),
                "updated_at": dt(days=-3),
            }
        )
    runtime.ensure_rows(conn, rental_pause_schema, "rental_pauses", ("rental_id", "pause_start_date"), pause_rows)

    purchase_rows = []
    for index in range(1, 6):
        purchase_rows.append(
            {
                "user_id": customer_ids[index - 1],
                "battery_id": ctx["battery_ids"].get(f"WZ-SEED-BAT-{40 + index:03d}"),
                "amount": 30000.0 + (index * 2500),
                "timestamp": dt(days=-25 + index),
            }
        )
    runtime.ensure_rows(conn, purchase_schema, "purchases", ("user_id", "battery_id", "timestamp"), purchase_rows)

    invoice_rows = []
    for index in range(1, 21):
        ref = f"txn_seed_{index:04d}"
        transaction_id = transaction_id_by_ref.get(ref)
        user_id = customer_ids[(index - 1) % len(customer_ids)]
        invoice_rows.append(
            {
                "user_id": user_id,
                "transaction_id": transaction_id,
                "invoice_number": f"INV-SEED-{index:05d}",
                "amount": 450.0 + (index * 25),
                "tax_amount": round((450.0 + (index * 25)) * 0.18, 2),
                "gstin": make_gst(index),
                "hsn_code": "85076000",
                "is_late_fee": index > 16,
                "pdf_url": f"https://seed.wezu.energy/invoices/{index}.pdf",
                "created_at": dt(days=-(index % 18)),
            }
        )
    runtime.ensure_rows(conn, invoice_schema, "invoices", ("invoice_number",), invoice_rows)
    invoice_by_number = runtime.fetch_map(conn, invoice_schema, "invoices", "invoice_number") if invoice_schema else {}

    late_fee_rows = []
    waiver_rows = []
    for index in range(21, 26):
        rental_id = rental_ids[index - 1]
        row = rental_rows_by_id[rental_id]
        invoice_number = f"INV-SEED-{index - 5:05d}"
        late_fee_rows.append(
            {
                "rental_id": rental_id,
                "user_id": row["user_id"],
                "original_end_date": row["expected_end_time"],
                "actual_return_date": row["expected_end_time"] + timedelta(days=2),
                "days_overdue": 2,
                "daily_late_fee_rate": 75.0,
                "base_late_fee": 150.0,
                "progressive_penalty": 25.0,
                "total_late_fee": 175.0,
                "amount_paid": 100.0 if index % 2 else 0.0,
                "amount_waived": 50.0 if index % 2 else 0.0,
                "amount_outstanding": 25.0 if index % 2 else 175.0,
                "payment_status": "PARTIAL" if index % 2 else "PENDING",
                "invoice_id": invoice_by_number.get(invoice_number),
                "invoice_generated_at": dt(days=-2),
                "created_at": dt(days=-2),
                "updated_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, late_fee_schema, "late_fees", ("rental_id",), late_fee_rows)

    late_fee_table = runtime.table(late_fee_schema, "late_fees", conn=conn) if late_fee_schema and runtime.has_table(late_fee_schema, "late_fees") else None
    late_fee_by_rental = {}
    if late_fee_table is not None and "rental_id" in late_fee_table.c and "id" in late_fee_table.c:
        late_fee_by_rental = {row[0]: row[1] for row in conn.execute(select(late_fee_table.c.rental_id, late_fee_table.c.id))}

    for index in range(21, 24):
        rental_id = rental_ids[index - 1]
        row = rental_rows_by_id[rental_id]
        waiver_rows.append(
            {
                "late_fee_id": late_fee_by_rental.get(rental_id),
                "user_id": row["user_id"],
                "requested_waiver_amount": 50.0,
                "requested_waiver_percentage": 28.0,
                "reason": "First-time waiver request",
                "supporting_documents": '["https://seed.wezu.energy/waiver/doc.pdf"]',
                "status": "APPROVED" if index % 2 else "PENDING",
                "approved_waiver_amount": 50.0 if index % 2 else None,
                "reviewed_by": user_ids[ADMIN_BLUEPRINTS[1]["email"]],
                "reviewed_at": dt(days=-1) if index % 2 else None,
                "admin_notes": "Approved as goodwill credit",
                "created_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, waiver_schema, "late_fee_waivers", ("late_fee_id",), waiver_rows)

    refund_rows = []
    for index in range(1, 6):
        refund_rows.append(
            {
                "transaction_id": transaction_id_by_ref.get(f"txn_seed_{index:04d}"),
                "amount": 100.0 + (index * 20),
                "reason": "Promotional adjustment",
                "status": "processed",
                "gateway_refund_id": f"rfnd_seed_{index:04d}",
                "processed_at": dt(days=-3),
                "created_at": dt(days=-4),
            }
        )
    runtime.ensure_rows(conn, refund_schema, "refunds", ("gateway_refund_id",), refund_rows)

    chargeback_rows = []
    for index in range(1, 4):
        chargeback_rows.append(
            {
                "transaction_id": transaction_id_by_ref.get(f"txn_seed_{10 + index:04d}"),
                "amount": 275.0 + (index * 30),
                "reason": "Gateway dispute opened",
                "status": "OPEN",
                "created_at": dt(days=-6),
                "updated_at": dt(days=-2),
            }
        )
    runtime.ensure_rows(conn, chargeback_schema, "chargebacks", ("transaction_id",), chargeback_rows)

    settlement_rows = []
    dealer_profile_ids = ctx["dealer_profile_ids"]
    vendor_ids = ctx["vendor_ids"]
    dealer_business_names = [row["business_name"] for row in DEALER_BLUEPRINTS]
    vendor_email_rows = [row["email"] for row in VENDOR_BLUEPRINTS]
    for index in range(1, 6):
        settlement_rows.append(
            {
                "dealer_id": dealer_profile_ids.get(dealer_business_names[index - 1]),
                "vendor_id": vendor_ids.get(vendor_email_rows[(index - 1) % len(vendor_email_rows)]),
                "settlement_month": f"2026-{index:02d}",
                "start_date": dt(days=-60 + (index * 5)),
                "end_date": dt(days=-30 + (index * 5)),
                "total_revenue": 55000.0 + (index * 12000),
                "total_commission": 7500.0 + (index * 1500),
                "chargeback_amount": 150.0 * index,
                "platform_fee": 2500.0 + (index * 300),
                "tax_amount": 1350.0 + (index * 200),
                "net_payable": 43000.0 + (index * 10000),
                "currency": "INR",
                "status": "paid" if index <= 3 else "generated",
                "transaction_reference": f"SETTLE-SEED-{index:04d}",
                "payment_proof_url": f"https://seed.wezu.energy/settlements/{index}.pdf",
                "created_at": dt(days=-25 + index),
                "paid_at": dt(days=-20 + index) if index <= 3 else None,
            }
        )
    runtime.ensure_rows(conn, settlement_schema, "settlements", ("settlement_month", "dealer_id"), settlement_rows)
    settlement_by_ref = runtime.fetch_map(conn, settlement_schema, "settlements", "transaction_reference") if settlement_schema else {}

    commission_cfg_rows = []
    for index, blueprint in enumerate(DEALER_BLUEPRINTS, start=1):
        commission_cfg_rows.append(
            {
                "dealer_id": user_ids[blueprint["email"]],
                "vendor_id": vendor_ids.get(vendor_email_rows[(index - 1) % len(vendor_email_rows)]),
                "transaction_type": "rental",
                "percentage": 12.0,
                "flat_fee": 0.0,
                "effective_from": dt(days=-90),
                "effective_until": dt(days=365),
                "is_active": True,
                "created_at": dt(days=-90),
            }
        )
    runtime.ensure_rows(conn, commission_cfg_schema, "commission_configs", ("dealer_id", "transaction_type"), commission_cfg_rows)

    commission_cfg_table = runtime.table(commission_cfg_schema, "commission_configs", conn=conn) if commission_cfg_schema and runtime.has_table(commission_cfg_schema, "commission_configs") else None
    cfg_by_dealer = {}
    if commission_cfg_table is not None and "dealer_id" in commission_cfg_table.c and "id" in commission_cfg_table.c:
        cfg_by_dealer = {row[0]: row[1] for row in conn.execute(select(commission_cfg_table.c.dealer_id, commission_cfg_table.c.id))}

    commission_tier_rows = []
    for blueprint in DEALER_BLUEPRINTS[:3]:
        cfg_id = cfg_by_dealer.get(user_ids[blueprint["email"]])
        commission_tier_rows.extend(
            [
                {"config_id": cfg_id, "min_volume": 0, "max_volume": 49, "percentage": 10.0, "flat_fee": 0.0, "created_at": dt(days=-60)},
                {"config_id": cfg_id, "min_volume": 50, "max_volume": 199, "percentage": 12.5, "flat_fee": 0.0, "created_at": dt(days=-60)},
            ]
        )
    runtime.ensure_rows(conn, commission_tier_schema, "commission_tiers", ("config_id", "min_volume"), commission_tier_rows)

    commission_log_rows = []
    for index in range(1, 11):
        commission_log_rows.append(
            {
                "transaction_id": transaction_id_by_ref.get(f"txn_seed_{index:04d}"),
                "dealer_id": user_ids[DEALER_BLUEPRINTS[(index - 1) % len(DEALER_BLUEPRINTS)]["email"]],
                "vendor_id": vendor_ids.get(vendor_email_rows[(index - 1) % len(vendor_email_rows)]),
                "amount": 75.0 + (index * 10),
                "status": "paid" if index <= 5 else "pending",
                "settlement_id": settlement_by_ref.get(f"SETTLE-SEED-{((index - 1) % 5) + 1:04d}"),
                "created_at": dt(days=-12 + index),
            }
        )
    runtime.ensure_rows(conn, commission_log_schema, "commission_logs", ("transaction_id",), commission_log_rows)

    commission_rows = [{"transaction_id": transaction_id_by_ref.get(f"txn_seed_{index:04d}")} for index in range(1, 6)]
    runtime.ensure_rows(conn, commission_schema, "commissions", ("transaction_id",), commission_rows)

    # Ensure we have at least one settlement for the dispute
    sample_settle_id = settlement_by_ref.get("SETTLE-SEED-0001") or (list(settlement_by_ref.values())[0] if settlement_by_ref else None)
    
    if sample_settle_id:
        dispute_rows = [
            {
                "settlement_id": sample_settle_id,
                "reason": "Merchant contested a disputed settlement component",
                "status": "OPEN",
                "created_at": dt(days=-3),
            }
        ]
        runtime.ensure_rows(conn, settlement_dispute_schema, "settlement_disputes", ("settlement_id",), dispute_rows)

    ctx["wallet_by_user"] = wallet_by_user
    ctx["rental_ids"] = rental_ids
    ctx["transaction_id_by_ref"] = transaction_id_by_ref


def seed_catalog_orders_logistics(runtime: SeedRuntime, conn: Connection, resolver: Resolver, ctx: dict[str, Any]) -> None:
    product_schema = resolver.schema_for("products")
    product_image_schema = resolver.schema_for("product_images")
    variant_schema = resolver.schema_for("product_variants")
    order_schema = resolver.schema_for("orders")
    order_item_schema = resolver.schema_for("order_items")
    tracking_schema = resolver.schema_for("delivery_tracking")
    delivery_event_schema = resolver.schema_for("delivery_events")
    ecommerce_product_schema = resolver.schema_for("ecommerce_products")
    ecommerce_order_schema = resolver.schema_for("ecommerce_orders")
    ecommerce_item_schema = resolver.schema_for("ecommerce_order_items")
    delivery_order_schema = resolver.schema_for("delivery_orders")
    delivery_assignment_schema = resolver.schema_for("delivery_assignments")
    route_schema = resolver.schema_for("delivery_routes")
    route_stop_schema = resolver.schema_for("route_stops")
    manifest_schema = resolver.schema_for("manifests")
    transfer_schema = resolver.schema_for("battery_transfers")
    return_schema = resolver.schema_for("return_requests")
    inspection_schema = resolver.schema_for("return_inspections")
    promo_schema = resolver.schema_for("promo_codes")
    referral_schema = resolver.schema_for("referrals")
    favorite_schema = resolver.schema_for("favorites")
    review_schema = resolver.schema_for("reviews")
    faq_schema = resolver.schema_for("faqs")
    feedback_schema = resolver.schema_for("feedback")
    search_history_schema = resolver.schema_for("search_histories")
    menu_schema = resolver.schema_for("menus")
    translation_schema = resolver.schema_for("translations")
    notification_schema = resolver.schema_for("notifications")

    product_rows = []
    for index, item in enumerate(PRODUCT_BLUEPRINTS, start=1):
        product_rows.append(
            {
                "sku": item["sku"],
                "name": item["name"],
                "description": f"{item['name']} ready for seed ecommerce flows.",
                "category": item["category"],
                "brand": item["brand"],
                "model": item["model"],
                "price": item["price"],
                "original_price": item["original_price"],
                "discount_percentage": round((item["original_price"] - item["price"]) / item["original_price"] * 100, 2),
                "capacity_mah": BATT_CATALOG[(index - 1) % len(BATT_CATALOG)]["capacity_mah"] if item["category"] == "BATTERY" else None,
                "voltage": BATT_CATALOG[(index - 1) % len(BATT_CATALOG)]["voltage"] if item["category"] == "BATTERY" else None,
                "battery_type": BATT_CATALOG[(index - 1) % len(BATT_CATALOG)]["battery_type"] if item["category"] == "BATTERY" else None,
                "warranty_months": 24 if item["category"] == "BATTERY" else 12,
                "warranty_terms": "Standard limited warranty.",
                "stock_quantity": 30 + (index * 5),
                "low_stock_threshold": 5,
                "status": "ACTIVE",
                "is_featured": index <= 3,
                "is_bestseller": index in {1, 3},
                "tags": "battery,ev,wezu",
                "meta_description": f"{item['name']} for Wezu seed catalog.",
                "average_rating": 4.2 + (index * 0.1),
                "review_count": 10 + index,
                "created_at": dt(days=-60 + index),
                "updated_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, product_schema, "products", ("sku",), product_rows)
    product_ids = runtime.fetch_map(conn, product_schema, "products", "sku") if product_schema else {}

    product_image_rows = [
        {
            "product_id": product_ids.get(item["sku"]),
            "image_url": f"https://seed.wezu.energy/products/{index}.jpg",
            "alt_text": item["name"],
            "display_order": 1,
            "is_primary": True,
            "created_at": dt(days=-30),
        }
        for index, item in enumerate(PRODUCT_BLUEPRINTS, start=1)
    ]
    runtime.ensure_rows(conn, product_image_schema, "product_images", ("product_id", "image_url"), product_image_rows)

    variant_rows = []
    for index, item in enumerate(PRODUCT_BLUEPRINTS[:3], start=1):
        variant_rows.append(
            {
                "product_id": product_ids.get(item["sku"]),
                "variant_name": f"{item['name']} Standard",
                "sku": f"{item['sku']}-STD",
                "price": item["price"],
                "stock_quantity": 12 + index,
                "color": "Black",
                "size": "Standard",
                "capacity_mah": BATT_CATALOG[index - 1]["capacity_mah"],
                "is_active": True,
                "created_at": dt(days=-20),
            }
        )
    runtime.ensure_rows(conn, variant_schema, "product_variants", ("sku",), variant_rows)
    variant_ids = runtime.fetch_map(conn, variant_schema, "product_variants", "sku") if variant_schema else {}

    address_schema = resolver.schema_for("addresses")
    address_table = runtime.table(address_schema, "addresses", conn=conn) if address_schema and runtime.has_table(address_schema, "addresses") else None
    address_by_user = {}
    if address_table is not None and "user_id" in address_table.c and "id" in address_table.c and "is_default" in address_table.c:
        address_by_user = {row[0]: row[1] for row in conn.execute(select(address_table.c.user_id, address_table.c.id).where(address_table.c.is_default.is_(True)))}

    order_rows = []
    customer_ids = [ctx["user_ids"][email] for email in ctx["customer_emails"]]
    for index in range(1, 11):
        user_id = customer_ids[index - 1]
        city_info = CITY_BLUEPRINTS[(index - 1) % len(CITY_BLUEPRINTS)]
        subtotal = 3000.0 + (index * 150)
        tax = round(subtotal * 0.18, 2)
        shipping = 120.0
        total = subtotal + tax + shipping
        order_rows.append(
            {
                "order_number": f"ORD-SEED-{index:05d}",
                "user_id": user_id,
                "subtotal": subtotal,
                "tax_amount": tax,
                "shipping_fee": shipping,
                "discount_amount": 100.0 if index % 2 == 0 else 0.0,
                "total_amount": total,
                "shipping_address": f"{index} EV Market Road",
                "shipping_city": city_info["city"],
                "shipping_state": city_info["state"],
                "shipping_pincode": f"560{index:03d}"[:6],
                "shipping_phone": make_phone(1000 + index),
                "payment_method": "UPI",
                "payment_status": "PAID",
                "payment_id": f"orderpay_seed_{index:04d}",
                "status": "DELIVERED" if index <= 6 else "SHIPPED",
                "created_at": dt(days=-20 + index),
                "confirmed_at": dt(days=-19 + index),
                "shipped_at": dt(days=-18 + index),
                "delivered_at": dt(days=-16 + index) if index <= 6 else None,
                "customer_notes": "Seed catalog order",
            }
        )
    runtime.ensure_rows(conn, order_schema, "orders", ("order_number",), order_rows)
    order_ids = runtime.fetch_map(conn, order_schema, "orders", "order_number") if order_schema else {}

    order_item_rows = []
    for index in range(1, 11):
        order_number = f"ORD-SEED-{index:05d}"
        product = PRODUCT_BLUEPRINTS[(index - 1) % len(PRODUCT_BLUEPRINTS)]
        order_item_rows.append(
            {
                "order_id": order_ids.get(order_number),
                "product_id": product_ids.get(product["sku"]),
                "variant_id": variant_ids.get(f"{product['sku']}-STD"),
                "product_name": product["name"],
                "sku": product["sku"],
                "quantity": 1,
                "unit_price": product["price"],
                "total_price": product["price"],
                "warranty_months": 24 if product["category"] == "BATTERY" else 12,
                "warranty_start_date": dt(days=-15 + index),
            }
        )
    runtime.ensure_rows(conn, order_item_schema, "order_items", ("order_id", "sku"), order_item_rows)

    tracking_rows = []
    delivery_event_rows = []
    for index in range(1, 11):
        order_number = f"ORD-SEED-{index:05d}"
        tracking_number = f"TRK-SEED-{index:05d}"
        tracking_rows.append(
            {
                "order_id": order_ids.get(order_number),
                "tracking_number": tracking_number,
                "courier_name": "Wezu Logistics",
                "courier_contact": make_phone(2000 + index),
                "estimated_delivery_date": dt(days=-14 + index),
                "actual_delivery_date": dt(days=-13 + index) if index <= 6 else None,
                "current_status": "DELIVERED" if index <= 6 else "IN_TRANSIT",
                "current_location": CITY_BLUEPRINTS[(index - 1) % len(CITY_BLUEPRINTS)]["city"],
                "delivery_image_url": f"https://seed.wezu.energy/proof/{index}.jpg" if index <= 6 else None,
                "recipient_name": CUSTOMER_BLUEPRINTS[index - 1],
                "recipient_signature": "signed" if index <= 6 else None,
                "created_at": dt(days=-18 + index),
                "updated_at": dt(days=-13 + index) if index <= 6 else dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, tracking_schema, "delivery_tracking", ("tracking_number",), tracking_rows)

    tracking_by_number = runtime.fetch_map(conn, tracking_schema, "delivery_tracking", "tracking_number") if tracking_schema else {}
    for index in range(1, 11):
        tracking_number = f"TRK-SEED-{index:05d}"
        tracking_id = tracking_by_number.get(tracking_number)
        delivery_event_rows.extend(
            [
                {
                    "tracking_id": tracking_id,
                    "status": "PICKED_UP",
                    "location": "Warehouse",
                    "description": "Shipment picked up from warehouse",
                    "timestamp": dt(days=-18 + index),
                    "event_metadata": '{"checkpoint":"pickup"}',
                },
                {
                    "tracking_id": tracking_id,
                    "status": "IN_TRANSIT",
                    "location": "City Hub",
                    "description": "Shipment moved through city hub",
                    "timestamp": dt(days=-17 + index),
                    "event_metadata": '{"checkpoint":"hub"}',
                },
            ]
        )
    runtime.ensure_rows(conn, delivery_event_schema, "delivery_events", ("tracking_id", "status", "timestamp"), delivery_event_rows)

    ecommerce_rows = []
    for index, item in enumerate(ECOM_BLUEPRINTS, start=1):
        ecommerce_rows.append(
            {
                "sku": item["sku"],
                "name": item["name"],
                "description": f"{item['name']} for customer purchase journeys.",
                "price": item["price"],
                "stock_quantity": 50 + index,
                "category": item["category"],
                "image_url": f"https://seed.wezu.energy/ecom/{index}.jpg",
                "is_active": True,
                "created_at": dt(days=-40 + index),
            }
        )
    runtime.ensure_rows(conn, ecommerce_product_schema, "ecommerce_products", ("sku",), ecommerce_rows)
    ecommerce_product_ids = runtime.fetch_map(conn, ecommerce_product_schema, "ecommerce_products", "sku") if ecommerce_product_schema else {}

    ecommerce_order_rows = []
    for index in range(1, 6):
        user_id = customer_ids[index - 1]
        ecommerce_order_rows.append(
            {
                "user_id": user_id,
                "total_amount": 1800.0 + (index * 400),
                "status": "DELIVERED" if index <= 3 else "PROCESSING",
                "shipping_address_id": address_by_user.get(user_id),
                "payment_transaction_id": None,
                "created_at": dt(days=-12 + index),
                "updated_at": dt(days=-2),
            }
        )
    runtime.ensure_rows(conn, ecommerce_order_schema, "ecommerce_orders", ("user_id", "created_at"), ecommerce_order_rows)
    ecommerce_order_ids = runtime.fetch_ids(conn, ecommerce_order_schema, "ecommerce_orders")

    ecommerce_item_rows = []
    for index, order_id in enumerate(ecommerce_order_ids[:5], start=1):
        item = ECOM_BLUEPRINTS[(index - 1) % len(ECOM_BLUEPRINTS)]
        ecommerce_item_rows.append(
            {
                "order_id": order_id,
                "product_id": ecommerce_product_ids.get(item["sku"]),
                "quantity": 1 + (index % 2),
                "price_per_item": item["price"],
                "total_price": item["price"] * (1 + (index % 2)),
                "created_at": dt(days=-12 + index),
            }
        )
    runtime.ensure_rows(conn, ecommerce_item_schema, "ecommerce_order_items", ("order_id", "product_id"), ecommerce_item_rows)

    driver_schema = resolver.schema_for("driver_profiles")
    driver_table = runtime.table(driver_schema, "driver_profiles", conn=conn) if driver_schema and runtime.has_table(driver_schema, "driver_profiles") else None
    driver_ids = list(conn.execute(select(driver_table.c.id).order_by(driver_table.c.id)).scalars()) if driver_table is not None else []
    logistics_user_ids = [ctx["user_ids"][email] for email in ctx["logistics_emails"]]

    return_rows = []
    for index, order_id in enumerate(ecommerce_order_ids[:3], start=1):
        user_id = customer_ids[index - 1]
        return_rows.append(
            {
                "order_id": order_id,
                "user_id": user_id,
                "reason": "Wrong accessory size",
                "status": "PENDING",
                "refund_amount": 500.0 + (index * 100),
                "inspection_notes": None,
                "created_at": dt(days=-4 + index),
                "updated_at": dt(days=-3 + index),
            }
        )
    runtime.ensure_rows(conn, return_schema, "return_requests", ("order_id", "user_id"), return_rows)
    return_ids = runtime.fetch_ids(conn, return_schema, "return_requests")

    delivery_order_rows = []
    for index in range(1, 11):
        city_info = CITY_BLUEPRINTS[(index - 1) % len(CITY_BLUEPRINTS)]
        delivery_order_rows.append(
            {
                "order_type": "CUSTOMER_DELIVERY" if index <= 7 else "REVERSE_LOGISTICS",
                "status": "DELIVERED" if index <= 4 else "ASSIGNED",
                "origin_address": f"Seed Warehouse {index}",
                "origin_lat": city_info["lat"],
                "origin_lng": city_info["lng"],
                "destination_address": f"{index} Seed Delivery Lane",
                "destination_lat": city_info["lat"] + 0.01,
                "destination_lng": city_info["lng"] + 0.01,
                "assigned_driver_id": logistics_user_ids[(index - 1) % len(logistics_user_ids)],
                "battery_ids_json": "[1,2]" if index > 7 else "[]",
                "scheduled_at": dt(days=-8 + index),
                "started_at": dt(days=-8 + index, hours=1),
                "completed_at": dt(days=-8 + index, hours=4) if index <= 4 else None,
                "tracking_url": f"https://seed.wezu.energy/logistics/order/{index}",
                "proof_of_delivery_url": f"https://seed.wezu.energy/logistics/pod/{index}.jpg" if index <= 4 else None,
                "customer_signature_url": None,
                "otp_verified": index <= 4,
                "completion_otp": f"{1200 + index}",
                "return_request_id": return_ids[index - 8] if index > 7 and len(return_ids) >= (index - 7) else None,
                "created_at": dt(days=-8 + index),
                "updated_at": dt(days=-2),
            }
        )
    runtime.ensure_rows(conn, delivery_order_schema, "delivery_orders", ("tracking_url",), delivery_order_rows)

    delivery_assignment_rows = []
    for index, order_id in enumerate(ecommerce_order_ids[:3], start=1):
        delivery_assignment_rows.append(
            {
                "order_id": order_id,
                "return_request_id": None,
                "driver_id": driver_ids[(index - 1) % len(driver_ids)] if driver_ids else None,
                "status": "delivered",
                "pickup_address": "Seed Warehouse Dock",
                "delivery_address": f"{index} Seed Delivery Lane",
                "assigned_at": dt(days=-6 + index),
                "picked_up_at": dt(days=-6 + index, hours=1),
                "delivered_at": dt(days=-6 + index, hours=3),
                "proof_of_delivery_img": f"https://seed.wezu.energy/assignments/{index}.jpg",
                "customer_signature": "captured",
                "otp_verified": True,
                "created_at": dt(days=-6 + index),
            }
        )
    for index, return_id in enumerate(return_ids[:2], start=1):
        delivery_assignment_rows.append(
            {
                "order_id": None,
                "return_request_id": return_id,
                "driver_id": driver_ids[(index - 1) % len(driver_ids)] if driver_ids else None,
                "status": "assigned",
                "pickup_address": f"Customer Address {index}",
                "delivery_address": "Seed Returns Hub",
                "assigned_at": dt(days=-2 + index),
                "created_at": dt(days=-2 + index),
            }
        )
    runtime.ensure_rows(conn, delivery_assignment_schema, "delivery_assignments", ("order_id", "return_request_id", "assigned_at"), delivery_assignment_rows)

    assignment_ids = runtime.fetch_ids(conn, delivery_assignment_schema, "delivery_assignments")
    route_rows = []
    for index, driver_id in enumerate(driver_ids[:3], start=1):
        route_rows.append(
            {
                "driver_id": driver_id,
                "route_name": f"Seed Route {index}",
                "status": "COMPLETED" if index == 1 else "PLANNED",
                "total_stops": 2,
                "completed_stops": 2 if index == 1 else 0,
                "estimated_distance_km": 18.5 + index,
                "estimated_duration_minutes": 55 + (index * 5),
                "actual_distance_km": 18.0 + index if index == 1 else None,
                "actual_duration_minutes": 50 + (index * 5) if index == 1 else None,
                "optimized_path": {"type": "LineString", "coordinates": [[77.59, 12.97], [77.61, 12.98]]},
                "started_at": dt(days=-1) if index == 1 else None,
                "completed_at": dt(hours=-20) if index == 1 else None,
                "created_at": dt(days=-2),
            }
        )
    runtime.ensure_rows(conn, route_schema, "delivery_routes", ("driver_id", "route_name"), route_rows)
    route_ids = runtime.fetch_ids(conn, route_schema, "delivery_routes")

    route_stop_rows = []
    for index, route_id in enumerate(route_ids[:3], start=1):
        if not assignment_ids:
            break
        route_stop_rows.append(
            {
                "route_id": route_id,
                "delivery_assignment_id": assignment_ids[(index - 1) % len(assignment_ids)],
                "stop_sequence": 1,
                "stop_type": "DELIVERY",
                "address": f"Route Stop {index}",
                "latitude": 12.97 + (index * 0.01),
                "longitude": 77.59 + (index * 0.01),
                "estimated_arrival": dt(hours=2 + index),
                "actual_arrival": dt(hours=3 + index) if index == 1 else None,
                "completed_at": dt(hours=3 + index) if index == 1 else None,
                "status": "COMPLETED" if index == 1 else "PENDING",
                "notes": "Seed stop row",
            }
        )
    runtime.ensure_rows(conn, route_stop_schema, "route_stops", ("route_id", "delivery_assignment_id"), route_stop_rows)

    manifest_rows = []
    for index in range(1, 4):
        manifest_rows.append(
            {
                "manifest_number": f"MAN-SEED-{index:04d}",
                "driver_id": logistics_user_ids[(index - 1) % len(logistics_user_ids)],
                "vehicle_id": f"VEH-SEED-{index:04d}",
                "status": "active" if index == 1 else "assigned",
                "created_at": dt(days=-3),
                "updated_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, manifest_schema, "manifests", ("manifest_number",), manifest_rows)
    manifest_ids = runtime.fetch_map(conn, manifest_schema, "manifests", "manifest_number") if manifest_schema else {}

    transfer_rows = []
    for index in range(1, 6):
        transfer_rows.append(
            {
                "battery_id": ctx["battery_ids"].get(f"WZ-SEED-BAT-{index:03d}"),
                "from_location_type": "warehouse",
                "from_location_id": 1,
                "to_location_type": "station",
                "to_location_id": ctx["station_id_list"][(index - 1) % len(ctx["station_id_list"])],
                "status": "received" if index <= 2 else "in_transit",
                "manifest_id": manifest_ids.get("MAN-SEED-0001"),
                "created_at": dt(days=-3 + index),
                "updated_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, transfer_schema, "battery_transfers", ("battery_id", "created_at"), transfer_rows)

    inspection_rows = []
    for index, return_id in enumerate(return_ids[:3], start=1):
        inspection_rows.append(
            {
                "return_request_id": return_id,
                "inspection_date": dt(days=-1),
                "inspector_id": logistics_user_ids[(index - 1) % len(logistics_user_ids)],
                "condition": "GOOD",
                "notes": "Item inspected and approved for refund",
            }
        )
    runtime.ensure_rows(conn, inspection_schema, "return_inspections", ("return_request_id",), inspection_rows)

    promo_rows = []
    for row in PROMO_ROWS:
        promo_row = safe_dict(row)
        promo_row["is_active"] = True
        promo_row["valid_from"] = dt(days=-10)
        promo_row["valid_until"] = dt(days=90)
        promo_row["usage_limit"] = 500
        promo_row["usage_count"] = 10
        promo_row["min_order_amount"] = 500.0
        promo_row["min_rental_days"] = 1
        promo_row["created_at"] = dt(days=-10)
        promo_rows.append(promo_row)
    runtime.ensure_rows(conn, promo_schema, "promo_codes", ("code",), promo_rows)

    referral_rows = []
    for index in range(1, 6):
        referral_rows.append(
            {
                "referrer_id": customer_ids[index - 1],
                "referred_user_id": customer_ids[index],
                "referral_code": f"REF-SEED-{index:04d}",
                "status": "completed",
                "reward_amount": 100.0,
                "created_at": dt(days=-20 + index),
                "completed_at": dt(days=-18 + index),
            }
        )
    runtime.ensure_rows(conn, referral_schema, "referrals", ("referral_code",), referral_rows)

    favorite_rows = [
        {"user_id": customer_ids[index - 1], "station_id": ctx["station_id_list"][index - 1], "created_at": dt(days=-10 + index)}
        for index in range(1, 6)
    ]
    runtime.ensure_rows(conn, favorite_schema, "favorites", ("user_id", "station_id"), favorite_rows)

    review_rows = []
    for index in range(1, 11):
        review_rows.append(
            {
                "user_id": customer_ids[(index - 1) % len(customer_ids)],
                "station_id": ctx["station_id_list"][(index - 1) % len(ctx["station_id_list"])],
                "battery_id": ctx["battery_ids"].get(f"WZ-SEED-BAT-{index:03d}"),
                "rental_id": ctx["rental_ids"][(index - 1) % len(ctx["rental_ids"])],
                "rating": 4 if index % 3 else 5,
                "comment": "Swap flow was quick and station staff were helpful.",
                "response_from_station": "Thanks for the feedback.",
                "is_verified_rental": True,
                "is_hidden": False,
                "helpful_count": 2 + index,
                "created_at": dt(days=-9 + index),
            }
        )
    runtime.ensure_rows(conn, review_schema, "reviews", ("user_id", "rental_id"), review_rows)

    faq_rows = [{"question": q, "answer": a, "created_at": dt(days=-30)} for q, a in FAQ_ROWS]
    runtime.ensure_rows(conn, faq_schema, "faqs", ("question",), faq_rows)

    feedback_rows = []
    for index in range(1, 6):
        feedback_rows.append(
            {
                "user_id": customer_ids[index - 1],
                "rating": 4 if index % 2 else 5,
                "nps_score": 8 + (index % 2),
                "category": "battery_swap",
                "comment": "Overall seed feedback captured for the customer app experience.",
                "metadata": {"source": "seed"},
                "created_at": dt(days=-8 + index),
            }
        )
    runtime.ensure_rows(conn, feedback_schema, "feedback", ("user_id", "created_at"), feedback_rows)

    search_rows = []
    for index in range(1, 11):
        city_info = CITY_BLUEPRINTS[(index - 1) % len(CITY_BLUEPRINTS)]
        search_rows.append(
            {
                "user_id": customer_ids[(index - 1) % len(customer_ids)],
                "session_id": f"search-seed-{index:04d}",
                "search_query": "battery swap near me",
                "search_type": "STATION",
                "search_latitude": city_info["lat"],
                "search_longitude": city_info["lng"],
                "search_location_name": city_info["city"],
                "filters_applied": '{"rating":4}',
                "results_count": 5,
                "results_shown": 5,
                "clicked_result_id": ctx["station_id_list"][(index - 1) % len(ctx["station_id_list"])],
                "clicked_result_type": "STATION",
                "clicked_result_position": 1,
                "time_to_click_seconds": 12,
                "led_to_rental": index <= 4,
                "led_to_purchase": False,
                "led_to_swap": index <= 6,
                "conversion_id": ctx["rental_ids"][(index - 1) % len(ctx["rental_ids"])],
                "conversion_type": "RENTAL",
                "device_type": "MOBILE",
                "platform": "Android",
                "created_at": dt(days=-7 + index),
            }
        )
    runtime.ensure_rows(conn, search_history_schema, "search_histories", ("session_id",), search_rows)

    menu_rows = [
        {"label": "Dashboard", "path": "/dashboard", "icon": "dashboard", "display_order": 1, "is_active": True},
        {"label": "Batteries", "path": "/batteries", "icon": "battery", "display_order": 2, "is_active": True},
        {"label": "Stations", "path": "/stations", "icon": "charging_station", "display_order": 3, "is_active": True},
        {"label": "Rentals", "path": "/rentals", "icon": "directions_bike", "display_order": 4, "is_active": True},
        {"label": "Orders", "path": "/orders", "icon": "shopping_cart", "display_order": 5, "is_active": True},
        {"label": "Support", "path": "/support", "icon": "support_agent", "display_order": 6, "is_active": True},
    ]
    runtime.ensure_rows(conn, menu_schema, "menus", ("path",), menu_rows)

    translation_rows = [
        {"key": "app.name", "value": "Wezu Energy", "locale": "en", "created_at": dt(days=-100)},
        {"key": "app.tagline", "value": "Swap faster. Ride further.", "locale": "en", "created_at": dt(days=-100)},
        {"key": "rental.start", "value": "Start Rental", "locale": "en", "created_at": dt(days=-100)},
    ]
    runtime.ensure_rows(conn, translation_schema, "translations", ("key", "locale"), translation_rows)

    notification_rows = []
    for index in range(1, 11):
        notification_rows.append(
            {
                "user_id": customer_ids[(index - 1) % len(customer_ids)],
                "title": "Battery Swap Reminder",
                "message": "A nearby station has fresh batteries available.",
                "type": "info",
                "channel": "push",
                "payload": '{"screen":"stations"}',
                "scheduled_at": None,
                "status": "sent",
                "is_read": index % 2 == 0,
                "created_at": dt(days=-index),
            }
        )
    runtime.ensure_rows(conn, notification_schema, "notifications", ("user_id", "title", "created_at"), notification_rows)


def seed_support_content_analytics(runtime: SeedRuntime, conn: Connection, resolver: Resolver, ctx: dict[str, Any]) -> None:
    kyc_record_schema = resolver.schema_for("kyc_records")
    kyc_doc_schema = resolver.schema_for("kyc_documents")
    kyc_request_schema = resolver.schema_for("kyc_requests")
    support_schema = resolver.schema_for("support_tickets")
    ticket_message_schema = resolver.schema_for("ticket_messages")
    chat_schema = resolver.schema_for("chat_sessions")
    chat_message_schema = resolver.schema_for("chat_messages")
    audit_schema = resolver.schema_for("audit_logs")
    security_event_schema = resolver.schema_for("security_events")
    alert_schema = resolver.schema_for("alerts")
    blog_schema = resolver.schema_for("blogs")
    banner_schema = resolver.schema_for("banners")
    legal_schema = resolver.schema_for("legal_documents")
    media_schema = resolver.schema_for("media_assets")
    demand_schema = resolver.schema_for("demand_forecasts")
    churn_schema = resolver.schema_for("churn_predictions")
    pricing_schema = resolver.schema_for("pricing_recommendations")
    risk_schema = resolver.schema_for("risk_scores")
    fraud_schema = resolver.schema_for("fraud_check_logs")
    blacklist_schema = resolver.schema_for("blacklists")
    geofence_schema = resolver.schema_for("geofence")
    revenue_schema = resolver.schema_for("revenue_reports")

    user_ids = ctx["user_ids"]
    customer_ids = [user_ids[email] for email in ctx["customer_emails"]]

    kyc_record_rows = []
    kyc_doc_rows = []
    kyc_request_rows = []
    verifier_id = user_ids[ADMIN_BLUEPRINTS[0]["email"]]
    for index, email in enumerate(ctx["customer_emails"][:10], start=1):
        user_id = user_ids[email]
        kyc_record_rows.append(
            {
                "user_id": user_id,
                "aadhaar_number_enc": secrets.token_hex(8),
                "pan_number_enc": secrets.token_hex(8),
                "aadhaar_front_url": f"https://seed.wezu.energy/kyc/{index}/aadhaar-front.jpg",
                "aadhaar_back_url": f"https://seed.wezu.energy/kyc/{index}/aadhaar-back.jpg",
                "pan_card_url": f"https://seed.wezu.energy/kyc/{index}/pan.jpg",
                "video_kyc_url": f"https://seed.wezu.energy/kyc/{index}/video.mp4",
                "status": "verified" if index <= 7 else "pending",
                "liveness_score": 0.96,
                "verification_response": '{"provider":"seed"}',
                "verified_by": verifier_id if index <= 7 else None,
                "submitted_at": dt(days=-30 + index),
                "verified_at": dt(days=-28 + index) if index <= 7 else None,
                "updated_at": dt(days=-2),
            }
        )
        kyc_doc_rows.append(
            {
                "user_id": user_id,
                "document_type": "AADHAAR" if index % 2 else "PAN",
                "document_number": secrets.token_hex(6),
                "file_url": f"https://seed.wezu.energy/kyc/{index}/doc.pdf",
                "status": "VERIFIED" if index <= 7 else "PENDING",
                "verification_response": '{"status":"ok"}',
                "verified_by": verifier_id if index <= 7 else None,
                "uploaded_at": dt(days=-30 + index),
                "verified_at": dt(days=-28 + index) if index <= 7 else None,
            }
        )
        kyc_request_rows.append(
            {
                "user_id": user_id,
                "status": "approved" if index <= 7 else "pending",
                "request_data": '{"source":"mobile-app"}',
                "created_at": dt(days=-30 + index),
                "updated_at": dt(days=-2),
            }
        )
    runtime.ensure_rows(conn, kyc_record_schema, "kyc_records", ("user_id",), kyc_record_rows)
    runtime.ensure_rows(conn, kyc_doc_schema, "kyc_documents", ("user_id", "document_type"), kyc_doc_rows)
    runtime.ensure_rows(conn, kyc_request_schema, "kyc_requests", ("user_id",), kyc_request_rows)

    support_rows = []
    subjects = [
        "Battery not charging",
        "Swap station error",
        "Billing dispute",
        "App login issue",
        "KYC pending too long",
        "Station offline",
        "Refund still pending",
        "Late fee clarification",
        "Dealer order delay",
        "Card payment failed",
    ]
    for index, subject in enumerate(subjects, start=1):
        support_rows.append(
            {
                "user_id": customer_ids[(index - 1) % len(customer_ids)],
                "assigned_to": user_ids[ctx["support_emails"][(index - 1) % len(ctx["support_emails"])]],
                "subject": subject,
                "description": f"Seed support ticket for: {subject}.",
                "status": "OPEN" if index > 6 else "RESOLVED",
                "priority": "MEDIUM" if index % 3 else "HIGH",
                "category": "technical" if index % 2 else "billing",
                "created_at": dt(days=-12 + index),
                "updated_at": dt(days=-2),
                "resolved_at": dt(days=-1) if index <= 6 else None,
            }
        )
    runtime.ensure_rows(conn, support_schema, "support_tickets", ("user_id", "subject"), support_rows)

    support_ids = runtime.fetch_ids(conn, support_schema, "support_tickets")
    ticket_message_rows = []
    for index, ticket_id in enumerate(support_ids[:10], start=1):
        ticket_message_rows.extend(
            [
                {
                    "ticket_id": ticket_id,
                    "sender_id": customer_ids[(index - 1) % len(customer_ids)],
                    "message": "Customer shared the issue details and requested a quick fix.",
                    "is_internal_note": False,
                    "created_at": dt(days=-11 + index),
                },
                {
                    "ticket_id": ticket_id,
                    "sender_id": user_ids[ctx["support_emails"][(index - 1) % len(ctx["support_emails"])]],
                    "message": "Support reviewed the case and provided a next action.",
                    "is_internal_note": index % 4 == 0,
                    "created_at": dt(days=-10 + index),
                },
            ]
        )
    runtime.ensure_rows(conn, ticket_message_schema, "ticket_messages", ("ticket_id", "sender_id", "created_at"), ticket_message_rows)

    chat_rows = []
    for index, user_id in enumerate(customer_ids[:5], start=1):
        chat_rows.append(
            {
                "user_id": user_id,
                "assigned_agent_id": user_ids[ctx["support_emails"][(index - 1) % len(ctx["support_emails"])]],
                "status": "CLOSED" if index <= 3 else "ACTIVE",
                "created_at": dt(days=-5 + index),
                "updated_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, chat_schema, "chat_sessions", ("user_id", "created_at"), chat_rows)
    chat_ids = runtime.fetch_ids(conn, chat_schema, "chat_sessions")

    chat_message_rows = []
    for index, chat_id in enumerate(chat_ids[:5], start=1):
        chat_message_rows.extend(
            [
                {"session_id": chat_id, "sender_id": customer_ids[(index - 1) % len(customer_ids)], "message": "Need help with station availability.", "created_at": dt(days=-4 + index)},
                {"session_id": chat_id, "sender_id": user_ids[ctx["support_emails"][(index - 1) % len(ctx["support_emails"])]], "message": "Nearest stations with stock were shared.", "created_at": dt(days=-4 + index, hours=1)},
            ]
        )
    runtime.ensure_rows(conn, chat_message_schema, "chat_messages", ("session_id", "sender_id", "created_at"), chat_message_rows)

    audit_rows = []
    for index in range(1, 16):
        audit_rows.append(
            {
                "user_id": user_ids[ADMIN_BLUEPRINTS[(index - 1) % len(ADMIN_BLUEPRINTS)]["email"]],
                "action": "UPDATE",
                "resource_type": "battery" if index % 2 else "station",
                "resource_id": str(index),
                "details": "Seed audit event for operational change.",
                "device_info": "seed-script",
                "ip_address": f"10.0.0.{index}",
                "timestamp": dt(days=-index),
            }
        )
    runtime.ensure_rows(conn, audit_schema, "audit_logs", ("user_id", "resource_type", "resource_id", "timestamp"), audit_rows)

    security_rows = [
        {
            "event_type": "LOGIN_ANOMALY",
            "severity": "LOW",
            "details": "Seeded low-risk event for monitoring data.",
            "source_ip": "10.0.2.1",
            "user_id": verifier_id,
            "timestamp": dt(days=-2),
            "is_resolved": True,
        },
        {
            "event_type": "FAILED_ADMIN_LOGIN",
            "severity": "MEDIUM",
            "details": "Repeated incorrect password attempts.",
            "source_ip": "10.0.2.2",
            "user_id": verifier_id,
            "timestamp": dt(days=-1),
            "is_resolved": False,
        },
    ]
    runtime.ensure_rows(conn, security_event_schema, "security_events", ("event_type", "timestamp"), security_rows)

    alert_rows = [
        {
            "station_id": ctx["station_id_list"][0],
            "alert_type": "PERFORMANCE",
            "severity": "MEDIUM",
            "message": "Charging throughput dipped below baseline during peak hour.",
            "created_at": dt(days=-2),
            "acknowledged_at": None,
            "acknowledged_by": None,
        }
    ]
    runtime.ensure_rows(conn, alert_schema, "alerts", ("station_id", "alert_type", "created_at"), alert_rows)

    blog_rows = []
    for index, row in enumerate(BLOG_ROWS, start=1):
        blog_rows.append(
            {
                "slug": row["slug"],
                "title": row["title"],
                "content": f"{row['title']} content seeded for admin CMS coverage.",
                "summary": f"Summary for {row['title']}.",
                "featured_image_url": f"https://seed.wezu.energy/blogs/{index}.jpg",
                "category": row["category"],
                "author_id": verifier_id,
                "status": "published",
                "views_count": 120 * index,
                "published_at": dt(days=-14 + index),
                "created_at": dt(days=-15 + index),
                "updated_at": dt(days=-2),
            }
        )
    runtime.ensure_rows(conn, blog_schema, "blogs", ("slug",), blog_rows)

    banner_rows = []
    for index, row in enumerate(BANNER_ROWS, start=1):
        banner_rows.append(
            {
                "title": row["title"],
                "image_url": f"https://seed.wezu.energy/banners/{index}.jpg",
                "deep_link": row["deep_link"],
                "external_url": row["external_url"],
                "priority": index,
                "is_active": True,
                "start_date": dt(days=-7),
                "end_date": dt(days=30),
                "click_count": 10 * index,
                "created_at": dt(days=-7),
                "updated_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, banner_schema, "banners", ("title",), banner_rows)

    legal_rows = []
    for index, row in enumerate(LEGAL_ROWS, start=1):
        legal_rows.append(
            {
                "slug": row["slug"],
                "title": row["title"],
                "content": f"Seed legal content for {row['title']}.",
                "version": f"v1.{index}",
                "is_active": True,
                "force_update": index == 1,
                "published_at": dt(days=-30 + index),
                "created_at": dt(days=-30 + index),
                "updated_at": dt(days=-2),
            }
        )
    runtime.ensure_rows(conn, legal_schema, "legal_documents", ("slug",), legal_rows)

    media_rows = [
        {
            "file_name": "dealer-onboarding.pdf",
            "file_type": "application/pdf",
            "file_size_bytes": 125000,
            "url": "https://seed.wezu.energy/media/dealer-onboarding.pdf",
            "alt_text": "Dealer onboarding document",
            "category": "document",
            "uploaded_by_id": verifier_id,
            "created_at": dt(days=-12),
            "updated_at": dt(days=-1),
        },
        {
            "file_name": "station-promo.jpg",
            "file_type": "image/jpeg",
            "file_size_bytes": 98000,
            "url": "https://seed.wezu.energy/media/station-promo.jpg",
            "alt_text": "Station promotional image",
            "category": "marketing",
            "uploaded_by_id": verifier_id,
            "created_at": dt(days=-11),
            "updated_at": dt(days=-1),
        },
    ]
    runtime.ensure_rows(conn, media_schema, "media_assets", ("file_name",), media_rows)

    demand_rows = []
    for index, station_id in enumerate(ctx["station_id_list"][:5], start=1):
        demand_rows.append(
            {
                "forecast_type": "station",
                "entity_id": station_id,
                "entity_name": STATION_BLUEPRINTS[index - 1]["name"],
                "forecast_date": (BASE_TIME + timedelta(days=index)).date(),
                "forecast_hour": 9,
                "predicted_rentals": 10 + index,
                "predicted_swaps": 8 + index,
                "predicted_purchases": 1 + (index % 2),
                "confidence_level": 0.86,
                "lower_bound": 8,
                "upper_bound": 16,
                "actual_rentals": None,
                "actual_swaps": None,
                "actual_purchases": None,
                "forecast_accuracy": None,
                "model_version": "seed-v1",
                "model_features": {"weather": "stable", "traffic": "medium"},
                "created_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, demand_schema, "demand_forecasts", ("entity_name", "forecast_date"), demand_rows)

    churn_rows = []
    for index, email in enumerate(ctx["customer_emails"][:8], start=1):
        churn_rows.append(
            {
                "user_id": user_ids[email],
                "churn_probability": 0.12 + (index * 0.05),
                "churn_risk_level": "LOW" if index <= 3 else ("MEDIUM" if index <= 6 else "HIGH"),
                "days_since_last_activity": index * 3,
                "days_since_last_rental": index * 4,
                "total_rentals": 12 - index,
                "total_spend": 2500.0 + (index * 800),
                "app_opens_last_30_days": 20 - index,
                "searches_last_30_days": 8 + index,
                "support_tickets_last_30_days": index % 3,
                "has_unresolved_issues": index % 4 == 0,
                "has_negative_reviews": index % 5 == 0,
                "payment_failures_count": index % 2,
                "top_churn_factors": ["inactivity", "competitor_offer"],
                "recommended_actions": ["offer_discount", "customer_call"],
                "retention_action_taken": "PROMO_SENT" if index <= 4 else None,
                "retention_action_date": dt(days=-1) if index <= 4 else None,
                "did_churn": False,
                "churn_date": None,
                "model_version": "seed-v1",
                "prediction_date": BASE_TIME.date(),
                "created_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, churn_schema, "churn_predictions", ("user_id", "prediction_date"), churn_rows)

    pricing_rows = []
    for index, station_id in enumerate(ctx["station_id_list"][:5], start=1):
        pricing_rows.append(
            {
                "recommendation_type": "swap_fee",
                "entity_type": "station",
                "entity_id": station_id,
                "current_price": 79.0,
                "recommended_price": 85.0 + index,
                "price_change_percentage": 4.0 + index,
                "demand_factor": 1.2,
                "competition_factor": 0.8,
                "seasonality_factor": 1.1,
                "inventory_factor": 0.9,
                "expected_revenue_change_percentage": 7.5,
                "expected_volume_change_percentage": -1.2,
                "confidence_score": 0.84,
                "risk_level": "LOW",
                "valid_from": dt(days=1),
                "valid_until": dt(days=30),
                "status": "DRAFT",
                "implemented_at": None,
                "implemented_by": None,
                "actual_revenue_change": None,
                "actual_volume_change": None,
                "created_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, pricing_schema, "pricing_recommendations", ("entity_type", "entity_id", "valid_from"), pricing_rows)

    risk_rows = []
    fraud_rows = []
    blacklist_rows = []
    for index, email in enumerate(ctx["customer_emails"][:5], start=1):
        user_id = user_ids[email]
        risk_rows.append(
            {
                "user_id": user_id,
                "risk_score": 20.0 + (index * 5),
                "risk_level": "LOW" if index <= 3 else "MEDIUM",
                "factors_json": '{"velocity":"normal"}',
                "evaluated_at": dt(days=-1),
                "created_at": dt(days=-1),
            }
        )
        fraud_rows.append(
            {
                "user_id": user_id,
                "check_type": "transaction_velocity",
                "result": "pass",
                "score": 18.0 + index,
                "details_json": '{"status":"clear"}',
                "created_at": dt(days=-1),
            }
        )
        blacklist_rows.append(
            {
                "entity_type": "device" if index % 2 else "ip",
                "entity_value": f"seed-entity-{index}",
                "reason": "Seed monitoring dataset",
                "is_active": index == 1,
                "created_at": dt(days=-3),
                "updated_at": dt(days=-1),
            }
        )
    runtime.ensure_rows(conn, risk_schema, "risk_scores", ("user_id",), risk_rows)
    runtime.ensure_rows(conn, fraud_schema, "fraud_check_logs", ("user_id", "check_type"), fraud_rows)
    runtime.ensure_rows(conn, blacklist_schema, "blacklists", ("entity_type", "entity_value"), blacklist_rows)

    geofence_rows = [
        {
            "name": "Hyderabad Core Zone",
            "latitude": 17.4416,
            "longitude": 78.3823,
            "radius_km": 12.0,
            "is_active": True,
            "created_at": dt(days=-20),
            "updated_at": dt(days=-1),
        }
    ]
    runtime.ensure_rows(conn, geofence_schema, "geofence", ("name",), geofence_rows)

    revenue_rows = [
        {
            "report_date": BASE_TIME.date(),
            "gross_revenue": 225000.0,
            "net_revenue": 198500.0,
            "rental_revenue": 145000.0,
            "swap_revenue": 42000.0,
            "ecommerce_revenue": 38500.0,
            "created_at": dt(days=-1),
            "updated_at": dt(days=-1),
        }
    ]
    runtime.ensure_rows(conn, revenue_schema, "revenue_reports", ("report_date",), revenue_rows)


def generic_backfill_schema(runtime: SeedRuntime, conn: Connection, schema: str) -> None:
    table_names = [name for name in runtime.inspector.get_table_names(schema=schema) if name not in SKIP_TABLES]
    dependencies: dict[str, set[str]] = {name: set() for name in table_names}
    reverse: dict[str, set[str]] = defaultdict(set)

    for table_name in table_names:
        for fk in runtime.inspector.get_foreign_keys(table_name, schema=schema):
            referred_schema = fk.get("referred_schema") or schema
            referred_table = fk["referred_table"]
            if referred_schema == schema and referred_table in dependencies and referred_table != table_name:
                dependencies[table_name].add(referred_table)
                reverse[referred_table].add(table_name)

    ready = deque(sorted(name for name, deps in dependencies.items() if not deps))
    ordered: list[str] = []
    pending = {name: set(deps) for name, deps in dependencies.items()}
    while ready:
        current = ready.popleft()
        ordered.append(current)
        for child in reverse.get(current, set()):
            pending[child].discard(current)
            if not pending[child]:
                ready.append(child)
    for name in table_names:
        if name not in ordered:
            ordered.append(name)

    progress = True
    while progress:
        progress = False
        for table_name in ordered:
            if runtime.count_rows(conn, schema, table_name) > 0:
                continue
            row = runtime.complete_row(conn, schema, table_name, {}, 0)
            try:
                runtime.ensure_rows(conn, schema, table_name, tuple(), [row])
                if runtime.count_rows(conn, schema, table_name) > 0:
                    progress = True
            except Exception:
                raise


def print_summary(runtime: SeedRuntime, conn: Connection, label: str, resolver: Resolver) -> None:
    key_tables = [
        "users",
        "dealer_profiles",
        "vendors",
        "stations",
        "batteries",
        "rentals",
        "transactions",
        "orders",
        "ecommerce_orders",
        "support_tickets",
    ]
    print(f"\n[{label}]")
    for table_name in key_tables:
        schema = resolver.schema_for(table_name)
        if schema and runtime.has_table(schema, table_name):
            print(f"  {schema}.{table_name}: {runtime.count_rows(conn, schema, table_name)}")


def main() -> None:
    database_url = load_database_url()
    engine = create_engine(database_url, future=True)
    runtime = SeedRuntime(engine)

    public_resolver = build_public_resolver(runtime)
    namespaced_resolver = build_namespaced_resolver(runtime)

    print("Connected to Neon PostgreSQL")
    print("Running comprehensive seed for public and namespaced schemas")

    seed_steps = [
        seed_locations,
        seed_access_control,
        seed_organizations,
        seed_users,
        seed_partner_network,
        seed_stations_inventory,
        seed_finance_and_rentals,
        seed_catalog_orders_logistics,
        seed_support_content_analytics,
    ]

    for resolver in (public_resolver, namespaced_resolver):
        if not resolver.table_to_schema:
            continue
        ctx: dict[str, Any] = {"resolver": resolver.label}
        for step in seed_steps:
            print(f"[{resolver.label}] {step.__name__}")
            with engine.begin() as conn:
                step(runtime, conn, resolver, ctx)

    for schema in public_resolver.schemas():
        print(f"[generic] public.{schema}")
        with engine.begin() as conn:
            generic_backfill_schema(runtime, conn, schema)
    for schema in namespaced_resolver.schemas():
        print(f"[generic] {schema}")
        with engine.begin() as conn:
            generic_backfill_schema(runtime, conn, schema)

    with engine.connect() as conn:
        public_remaining = runtime.empty_tables(conn, public_resolver.schemas())
        namespaced_remaining = runtime.empty_tables(conn, namespaced_resolver.schemas())

        print_summary(runtime, conn, "public", public_resolver)
        if namespaced_resolver.table_to_schema:
            print_summary(runtime, conn, "namespaced", namespaced_resolver)

        if public_remaining or namespaced_remaining:
            print("\nRemaining empty tables:")
            for table_name in public_remaining + namespaced_remaining:
                print(f"  - {table_name}")
            raise RuntimeError("Seed completed with empty application tables still present.")

    print("\nSeed completed successfully.")
    print(f"Default seeded password for created users: {DEFAULT_PASSWORD}")


if __name__ == "__main__":
    main()
