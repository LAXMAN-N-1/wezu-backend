from __future__ import annotations

import argparse
import importlib
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session, func, select

import app.models.all  # noqa: F401
from app.db.seeds.admin_portal_contract import ADMIN_PORTAL_CONTRACT


ROOT = Path(__file__).resolve().parents[3]
NOW = datetime.now(UTC).replace(microsecond=0)
EMPTY_DB_GUARD_TABLES = ("users", "stations", "batteries", "rentals", "transactions")


@dataclass
class SeedContext:
    now: datetime = NOW
    continents: dict[str, Any] = field(default_factory=dict)
    countries: dict[str, Any] = field(default_factory=dict)
    regions: dict[str, Any] = field(default_factory=dict)
    cities: dict[str, Any] = field(default_factory=dict)
    zones: dict[str, Any] = field(default_factory=dict)
    roles: dict[str, Any] = field(default_factory=dict)
    permissions: dict[str, Any] = field(default_factory=dict)
    menus: dict[str, Any] = field(default_factory=dict)
    groups: dict[str, Any] = field(default_factory=dict)
    admin_users: dict[str, Any] = field(default_factory=dict)
    users: dict[str, Any] = field(default_factory=dict)
    wallets: dict[str, Any] = field(default_factory=dict)
    addresses: dict[str, Any] = field(default_factory=dict)
    questions: dict[str, Any] = field(default_factory=dict)
    dealers: dict[str, Any] = field(default_factory=dict)
    vendors: dict[str, Any] = field(default_factory=dict)
    stations: dict[str, Any] = field(default_factory=dict)
    stock_configs: dict[str, Any] = field(default_factory=dict)
    battery_skus: dict[str, Any] = field(default_factory=dict)
    batteries: dict[str, Any] = field(default_factory=dict)
    devices: dict[str, Any] = field(default_factory=dict)
    rentals: dict[str, Any] = field(default_factory=dict)
    swaps: dict[str, Any] = field(default_factory=dict)
    transactions: dict[str, Any] = field(default_factory=dict)
    payment_transactions: dict[str, Any] = field(default_factory=dict)
    invoices: dict[str, Any] = field(default_factory=dict)
    late_fees: dict[str, Any] = field(default_factory=dict)
    settlements: dict[str, Any] = field(default_factory=dict)
    products: dict[str, Any] = field(default_factory=dict)
    ecommerce_orders: dict[str, Any] = field(default_factory=dict)
    return_requests: dict[str, Any] = field(default_factory=dict)
    driver_profiles: dict[str, Any] = field(default_factory=dict)
    delivery_orders: dict[str, Any] = field(default_factory=dict)
    delivery_assignments: dict[str, Any] = field(default_factory=dict)
    delivery_routes: dict[str, Any] = field(default_factory=dict)
    manifests: dict[str, Any] = field(default_factory=dict)
    support_tickets: dict[str, Any] = field(default_factory=dict)
    campaigns: dict[str, Any] = field(default_factory=dict)
    triggers: dict[str, Any] = field(default_factory=dict)
    bess_units: dict[str, Any] = field(default_factory=dict)


def _ts(days_ago: int = 0, hours_ago: int = 0, minutes_ago: int = 0) -> datetime:
    return NOW - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)


def _future(days_ahead: int = 0, hours_ahead: int = 0) -> datetime:
    return NOW + timedelta(days=days_ahead, hours=hours_ahead)


def resolve_database_url(override: str | None = None) -> str:
    database_url = override or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required. Pass --database-url or export DATABASE_URL.")
    return database_url


def ensure_seed_runtime_env(database_url: str) -> None:
    os.environ.setdefault("DATABASE_URL", database_url)
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("MONGODB_URL", "mongodb://localhost:27017/wezu_audit")
    os.environ.setdefault("SECRET_KEY", "seed-only-secret-key-not-for-production")


def _load_alembic_runtime() -> tuple[Any, Any]:
    original_path = list(sys.path)
    try:
        sys.path = [
            entry
            for entry in sys.path
            if Path(entry or ".").resolve() != ROOT
        ]
        alembic_command = importlib.import_module("alembic.command")
        alembic_config = importlib.import_module("alembic.config")
    finally:
        sys.path = original_path
    return alembic_command, alembic_config.Config


def run_migrations(database_url: str) -> None:
    alembic_command, alembic_config = _load_alembic_runtime()
    config = alembic_config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    alembic_command.upgrade(config, "head")


def assert_database_empty(session: Session) -> None:
    inspector = inspect(session.get_bind())
    if not all(inspector.has_table(name) for name in EMPTY_DB_GUARD_TABLES):
        missing = [name for name in EMPTY_DB_GUARD_TABLES if not inspector.has_table(name)]
        raise RuntimeError(f"Database is missing expected tables after migration: {', '.join(missing)}")

    existing = {}
    for table_name in EMPTY_DB_GUARD_TABLES:
        count_row = session.exec(text(f'SELECT COUNT(*) FROM "{table_name}"')).one()
        existing[table_name] = int(count_row[0])

    populated = {name: count for name, count in existing.items() if count > 0}
    if populated:
        rendered = ", ".join(f"{name}={count}" for name, count in populated.items())
        raise RuntimeError(
            "Admin showcase seed expects an empty database. "
            f"Found existing data in: {rendered}"
        )


def verify_contract(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url, future=True)
    failures: list[str] = []
    counts: dict[str, int] = {}

    with engine.connect() as conn:
        inspector = inspect(conn)
        for requirement in ADMIN_PORTAL_CONTRACT:
            table = requirement.table
            if not inspector.has_table(table):
                failures.append(f"{requirement.screen}: missing table {table}")
                continue
            count = int(conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0)
            counts[table] = max(counts.get(table, 0), count)
            if count < requirement.min_rows:
                failures.append(
                    f"{requirement.screen}: {table} has {count} rows, expected >= {requirement.min_rows}"
                )

    if failures:
        joined = "\n".join(failures)
        raise RuntimeError(f"Admin showcase verification failed:\n{joined}")

    return counts


def seed_showcase_data(session: Session) -> SeedContext:
    ctx = SeedContext()
    if session.get_bind().dialect.name == "sqlite":
        session.exec(text("PRAGMA foreign_keys=ON"))

    seed_geography(session, ctx)
    seed_rbac(session, ctx)
    seed_users(session, ctx)
    seed_dealers_and_vendors(session, ctx)
    seed_stations(session, ctx)
    seed_batteries_and_fleet(session, ctx)
    seed_rentals_and_finance(session, ctx)
    seed_logistics_and_commerce(session, ctx)
    seed_support_and_content(session, ctx)
    seed_notifications(session, ctx)
    seed_settings_security_and_ops(session, ctx)
    seed_bess(session, ctx)
    seed_analytics_tables(session, ctx)
    finalize_station_metrics(session, ctx)

    return ctx


def verify_business_metrics(session: Session, ctx: SeedContext) -> dict[str, Any]:
    from app.models.audit_log import AuditLog
    from app.models.battery import Battery
    from app.models.bess import BessUnit
    from app.models.financial import Transaction, TransactionStatus
    from app.models.notification_admin import NotificationLog
    from app.models.rental import Rental, RentalStatus
    from app.models.revenue_report import RevenueReport
    from app.models.user import KYCStatus, User

    window_start = datetime.now(UTC) - timedelta(days=30)

    checks = {
        "finance_total_revenue": float(
            session.exec(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.status == TransactionStatus.SUCCESS
                )
            ).one()
        ),
        "rentals_active": int(
            session.exec(select(func.count(Rental.id)).where(Rental.status == RentalStatus.ACTIVE)).one()
        ),
        "stock_total_batteries": int(session.exec(select(func.count(Battery.id))).one()),
        "health_total_batteries": int(session.exec(select(func.count(Battery.id))).one()),
        "battery_summary_total": int(session.exec(select(func.count(Battery.id))).one()),
        "monitoring_month_revenue": float(
            session.exec(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.status == TransactionStatus.SUCCESS,
                    Transaction.created_at >= window_start,
                )
            ).one()
        ),
        "notifications_total": int(session.exec(select(func.count(NotificationLog.id))).one()),
        "bess_units": int(session.exec(select(func.count(BessUnit.id))).one()),
        "kyc_pending": int(
            session.exec(select(func.count(User.id)).where(User.kyc_status == KYCStatus.PENDING)).one()
        ),
        "audit_total": int(session.exec(select(func.count(AuditLog.id))).one()),
        "analytics_total_revenue": float(
            session.exec(select(func.coalesce(func.max(RevenueReport.total_revenue), 0))).one()
        ),
    }

    zero_checks = [name for name, value in checks.items() if value <= 0]
    if zero_checks:
        raise RuntimeError(
            "Business metric verification failed for: " + ", ".join(sorted(zero_checks))
        )

    return checks


def seed_geography(session: Session, ctx: SeedContext) -> None:
    from app.models.location import City, Continent, Country, Region, Zone

    continent = session.exec(select(Continent).where(Continent.name == "Asia")).first()
    if continent is None:
        continent = Continent(name="Asia")
        session.add(continent)
        session.flush()

    country = session.exec(select(Country).where(Country.name == "India")).first()
    if country is None:
        country = Country(name="India", continent_id=continent.id)
    else:
        country.continent_id = continent.id
    session.add(country)
    session.flush()

    region = session.exec(
        select(Region).where(Region.name == "Telangana", Region.country_id == country.id)
    ).first()
    if region is None:
        region = Region(name="Telangana", country_id=country.id)
    session.add(region)
    session.flush()

    hyderabad = session.exec(
        select(City).where(City.name == "Hyderabad", City.region_id == region.id)
    ).first()
    if hyderabad is None:
        hyderabad = City(name="Hyderabad", region_id=region.id)
        session.add(hyderabad)

    warangal = session.exec(
        select(City).where(City.name == "Warangal", City.region_id == region.id)
    ).first()
    if warangal is None:
        warangal = City(name="Warangal", region_id=region.id)
        session.add(warangal)
    session.flush()

    zones = {
        "jubilee_hills": Zone(name="Jubilee Hills", city_id=hyderabad.id),
        "hitech_city": Zone(name="HITEC City", city_id=hyderabad.id),
        "kukatpally": Zone(name="Kukatpally", city_id=hyderabad.id),
        "secunderabad": Zone(name="Secunderabad", city_id=hyderabad.id),
        "uppal": Zone(name="Uppal", city_id=hyderabad.id),
        "hanamkonda": Zone(name="Hanamkonda", city_id=warangal.id),
        "kazipet": Zone(name="Kazipet", city_id=warangal.id),
        "madhapur": Zone(name="Madhapur", city_id=hyderabad.id),
    }
    persisted_zones = {}
    for key, zone in zones.items():
        existing_zone = session.exec(
            select(Zone).where(Zone.name == zone.name, Zone.city_id == zone.city_id)
        ).first()
        persisted_zones[key] = existing_zone or zone
        session.add(persisted_zones[key])
    session.flush()

    ctx.continents["asia"] = continent
    ctx.countries["india"] = country
    ctx.regions["telangana"] = region
    ctx.cities["hyderabad"] = hyderabad
    ctx.cities["warangal"] = warangal
    ctx.zones.update(persisted_zones)


def seed_rbac(session: Session, ctx: SeedContext) -> None:
    from app.models.admin_group import AdminGroup
    from app.models.admin_user import AdminUser
    from app.models.menu import Menu
    from app.models.rbac import AdminUserRole, Permission, Role, RolePermission
    from app.models.role_right import RoleRight

    permission_specs = [
        ("dashboard:view", "dashboard", "view", "View executive dashboard"),
        ("analytics:view", "analytics", "view", "View platform analytics"),
        ("user:view", "user", "view", "View users and user profiles"),
        ("user:update", "user", "update", "Update user records"),
        ("role:view", "role", "view", "View RBAC roles"),
        ("role:update", "role", "update", "Manage RBAC roles and permissions"),
        ("group:view", "group", "view", "View admin groups"),
        ("kyc:view", "kyc", "view", "View KYC queues"),
        ("kyc:approve", "kyc", "approve", "Approve or reject KYC"),
        ("dealer:view", "dealer", "view", "View dealer network"),
        ("dealer:update", "dealer", "update", "Update dealer profiles"),
        ("dealer:approve", "dealer", "approve", "Approve dealer onboarding"),
        ("station:view", "station", "view", "View stations"),
        ("station:update", "station", "update", "Manage stations"),
        ("stock:view", "stock", "view", "View stock positions"),
        ("stock:update", "stock", "update", "Manage stock configurations"),
        ("battery:view", "battery", "view", "View batteries"),
        ("battery:update", "battery", "update", "Update battery lifecycle data"),
        ("health:view", "health", "view", "View battery health"),
        ("health:update", "health", "update", "Record maintenance and health actions"),
        ("rental:view", "rental", "view", "View rentals"),
        ("rental:update", "rental", "update", "Terminate or update rentals"),
        ("swap:view", "swap", "view", "View swap operations"),
        ("finance:view", "finance", "view", "View finance dashboards"),
        ("finance:approve", "finance", "approve", "Approve finance workflows"),
        ("settlement:view", "settlement", "view", "View settlements"),
        ("settlement:approve", "settlement", "approve", "Approve settlements"),
        ("logistics:view", "logistics", "view", "View logistics operations"),
        ("logistics:update", "logistics", "update", "Manage logistics workflows"),
        ("support:view", "support", "view", "View support operations"),
        ("support:update", "support", "update", "Manage support workflows"),
        ("notification:view", "notification", "view", "View campaigns and logs"),
        ("notification:update", "notification", "update", "Manage campaigns and configs"),
        ("cms:view", "cms", "view", "View CMS assets"),
        ("cms:update", "cms", "update", "Manage CMS content"),
        ("settings:view", "settings", "view", "View settings"),
        ("settings:update", "settings", "update", "Manage settings"),
        ("security:view", "security", "view", "View security operations"),
        ("security:update", "security", "update", "Manage security controls"),
        ("audit:view", "audit", "view", "View audit trails"),
        ("fraud:view", "fraud", "view", "View fraud risk indicators"),
        ("fraud:update", "fraud", "update", "Take fraud actions"),
        ("bess:view", "bess", "view", "View BESS monitoring"),
        ("jobs:view", "jobs", "view", "View background jobs"),
    ]
    existing_permissions = {
        permission.slug: permission
        for permission in session.exec(
            select(Permission).where(Permission.slug.in_([slug for slug, *_ in permission_specs]))
        ).all()
    }
    permissions: dict[str, Permission] = {}
    for slug, module, action, description in permission_specs:
        permission = existing_permissions.get(slug)
        if permission is None:
            permission = Permission(
                slug=slug,
                module=module,
                action=action,
                scope="global",
                description=description,
            )
        else:
            permission.module = module
            permission.action = action
            permission.scope = "global"
            permission.description = description
        permissions[slug] = permission
        session.add(permission)
    session.flush()
    ctx.permissions.update(permissions)

    role_specs = [
        ("super_admin", "Super Admin", "system", 100, True, "#C0392B", "key"),
        ("operations_director", "Operations Director", "system", 90, False, "#1F618D", "key"),
        ("fleet_manager", "Fleet Manager", "system", 80, False, "#117864", "truck"),
        ("finance_manager", "Finance Manager", "system", 80, False, "#AF601A", "wallet"),
        ("support_lead", "Support Lead", "system", 75, False, "#6C3483", "headphones"),
        ("risk_analyst", "Risk Analyst", "system", 75, False, "#922B21", "shield-alert"),
        ("dealer_success", "Dealer Success Manager", "system", 70, False, "#2874A6", "store"),
        ("logistics_coordinator", "Logistics Coordinator", "system", 70, False, "#1E8449", "map"),
        ("customer", "Customer", "customer", 10, True, "#566573", "user"),
        ("dealer_owner", "Dealer Owner", "partner", 20, False, "#0B5345", "briefcase"),
        ("support_agent", "Support Agent", "system", 40, False, "#7D3C98", "message-square"),
        ("driver", "Driver", "partner", 30, False, "#186A3B", "bike"),
    ]
    existing_roles = {
        role.name: role
        for role in session.exec(select(Role).where(Role.name.in_([name for _, name, *_ in role_specs]))).all()
    }
    roles: dict[str, Role] = {}
    for key, name, category, level, system_role, color, icon in role_specs:
        role = existing_roles.get(name)
        if role is None:
            role = Role(
                name=name,
                description=f"{name} role seeded for admin showcase",
                category=category,
                level=level,
                is_system_role=system_role,
                color=color,
                icon=icon,
            )
        else:
            role.description = f"{name} role seeded for admin showcase"
            role.category = category
            role.level = level
            role.is_system_role = system_role
            role.color = color
            role.icon = icon
            role.is_active = True
        roles[key] = role
        session.add(role)
    session.flush()

    roles["support_agent"].parent_id = roles["support_lead"].id
    roles["driver"].parent_id = roles["logistics_coordinator"].id
    roles["dealer_owner"].parent_id = roles["dealer_success"].id
    session.add_all([roles["support_agent"], roles["driver"], roles["dealer_owner"]])
    session.flush()
    ctx.roles.update(roles)

    role_permissions = {
        "super_admin": list(permissions.keys()),
        "operations_director": [
            "dashboard:view",
            "analytics:view",
            "user:view",
            "dealer:view",
            "station:view",
            "stock:view",
            "battery:view",
            "health:view",
            "rental:view",
            "finance:view",
            "settlement:view",
            "logistics:view",
            "support:view",
            "notification:view",
            "cms:view",
            "settings:view",
            "security:view",
            "audit:view",
            "fraud:view",
            "bess:view",
            "jobs:view",
        ],
        "fleet_manager": [
            "dashboard:view",
            "analytics:view",
            "station:view",
            "station:update",
            "stock:view",
            "stock:update",
            "battery:view",
            "battery:update",
            "health:view",
            "health:update",
            "rental:view",
            "swap:view",
            "logistics:view",
            "logistics:update",
            "audit:view",
        ],
        "finance_manager": [
            "dashboard:view",
            "analytics:view",
            "finance:view",
            "finance:approve",
            "settlement:view",
            "settlement:approve",
            "user:view",
            "audit:view",
        ],
        "support_lead": [
            "dashboard:view",
            "user:view",
            "kyc:view",
            "kyc:approve",
            "support:view",
            "support:update",
            "notification:view",
            "audit:view",
        ],
        "risk_analyst": [
            "dashboard:view",
            "analytics:view",
            "kyc:view",
            "kyc:approve",
            "security:view",
            "security:update",
            "audit:view",
            "fraud:view",
            "fraud:update",
        ],
        "dealer_success": [
            "dashboard:view",
            "dealer:view",
            "dealer:update",
            "dealer:approve",
            "settlement:view",
            "logistics:view",
            "support:view",
            "audit:view",
        ],
        "logistics_coordinator": [
            "dashboard:view",
            "station:view",
            "battery:view",
            "logistics:view",
            "logistics:update",
            "audit:view",
        ],
        "customer": [],
        "dealer_owner": ["dealer:view", "logistics:view"],
        "support_agent": ["support:view", "support:update", "user:view"],
        "driver": ["logistics:view"],
    }
    existing_role_permissions = {
        (row.role_id, row.permission_id)
        for row in session.exec(
            select(RolePermission).where(
                RolePermission.role_id.in_([role.id for role in roles.values()]),
                RolePermission.permission_id.in_([permission.id for permission in permissions.values()]),
            )
        ).all()
    }
    session.add_all(
        [
            RolePermission(role_id=roles[role_key].id, permission_id=permissions[slug].id)
            for role_key, slugs in role_permissions.items()
            for slug in slugs
            if (roles[role_key].id, permissions[slug].id) not in existing_role_permissions
        ]
    )
    session.flush()

    group_specs = [
        ("central_ops", "Central Operations", "National control tower for fleet and logistics"),
        ("revenue_control", "Revenue Control", "Settlements, invoicing, and reconciliations"),
        ("trust_safety", "Trust and Safety", "KYC, fraud, and security operations"),
        ("customer_experience", "Customer Experience", "Support and outbound engagement"),
    ]
    existing_groups = {
        group.name: group
        for group in session.exec(select(AdminGroup).where(AdminGroup.name.in_([name for _, name, _ in group_specs]))).all()
    }
    groups: dict[str, AdminGroup] = {}
    for key, name, description in group_specs:
        group = existing_groups.get(name)
        if group is None:
            group = AdminGroup(name=name, description=description)
        else:
            group.description = description
            group.is_active = True
        groups[key] = group
        session.add(group)
    session.flush()
    ctx.groups.update(groups)

    admin_specs = [
        ("super", "Aarav Menon", "aarav.menon@powerfill.in", "9000001001", "central_ops", True, "super_admin"),
        ("fleet", "Vivek Reddy", "vivek.reddy@powerfill.in", "9000001002", "central_ops", False, "fleet_manager"),
        ("finance", "Sana Khan", "sana.khan@powerfill.in", "9000001003", "revenue_control", False, "finance_manager"),
        ("support", "Meera Iyer", "meera.iyer@powerfill.in", "9000001004", "customer_experience", False, "support_lead"),
        ("risk", "Rizwan Shaik", "rizwan.shaik@powerfill.in", "9000001005", "trust_safety", False, "risk_analyst"),
    ]
    existing_admins = {
        admin.email: admin
        for admin in session.exec(select(AdminUser).where(AdminUser.email.in_([email for _, _, email, *_ in admin_specs]))).all()
    }
    for key, full_name, email, phone, group_key, is_superuser, role_key in admin_specs:
        admin = existing_admins.get(email)
        if admin is None:
            admin = AdminUser(
                full_name=full_name,
                email=email,
                phone_number=phone,
                hashed_password="seed-only-admin-password",
                is_superuser=is_superuser,
                admin_group_id=groups[group_key].id,
            )
        else:
            admin.full_name = full_name
            admin.phone_number = phone
            admin.hashed_password = "seed-only-admin-password"
            admin.is_superuser = is_superuser
            admin.is_active = True
            admin.admin_group_id = groups[group_key].id
        ctx.admin_users[key] = admin
        session.add(admin)
    session.flush()

    super_admin_id = ctx.admin_users["super"].id
    admin_role_links = [
        AdminUserRole(admin_id=ctx.admin_users["super"].id, role_id=roles["super_admin"].id),
        AdminUserRole(admin_id=ctx.admin_users["fleet"].id, role_id=roles["fleet_manager"].id, assigned_by=super_admin_id),
        AdminUserRole(admin_id=ctx.admin_users["finance"].id, role_id=roles["finance_manager"].id, assigned_by=super_admin_id),
        AdminUserRole(admin_id=ctx.admin_users["support"].id, role_id=roles["support_lead"].id, assigned_by=super_admin_id),
        AdminUserRole(admin_id=ctx.admin_users["risk"].id, role_id=roles["risk_analyst"].id, assigned_by=super_admin_id),
    ]
    existing_admin_role_links = {
        (row.admin_id, row.role_id)
        for row in session.exec(
            select(AdminUserRole).where(
                AdminUserRole.admin_id.in_([admin.id for admin in ctx.admin_users.values()]),
                AdminUserRole.role_id.in_([role.id for role in roles.values()]),
            )
        ).all()
    }
    session.add_all(
        [
            row
            for row in admin_role_links
            if (row.admin_id, row.role_id) not in existing_admin_role_links
        ]
    )
    session.flush()

    unique_routes: dict[str, str] = {}
    for requirement in ADMIN_PORTAL_CONTRACT:
        unique_routes.setdefault(requirement.route, requirement.screen)

    existing_menus = {
        menu.route: menu
        for menu in session.exec(select(Menu).where(Menu.route.in_(list(unique_routes.keys())))).all()
    }
    for route, label in unique_routes.items():
        slug = route.strip("/").replace("/", "_") or "dashboard"
        menu = existing_menus.get(route)
        if menu is None:
            menu = Menu(
                name=slug,
                display_name=label,
                route=route,
                icon="grid",
                menu_order=len(ctx.menus) + 1,
                created_by="seed-showcase",
                modified_by="seed-showcase",
            )
        else:
            menu.name = slug
            menu.display_name = label
            menu.icon = "grid"
            menu.menu_order = len(ctx.menus) + 1
            menu.is_active = True
            menu.modified_by = "seed-showcase"
        ctx.menus[slug] = menu
        session.add(menu)
    session.flush()
    # PostgreSQL/Neon can reject role_right inserts if the RBAC parent rows only
    # exist in the current uncommitted unit of work. Persist the RBAC base graph
    # first, then build role_rights from fresh database ids in a new transaction.
    session.commit()

    persisted_roles = {
        name: role_id
        for name, role_id in session.exec(text("SELECT name, id FROM roles")).all()
    }
    persisted_menus = {
        route: menu_id
        for route, menu_id in session.exec(text("SELECT route, id FROM menus")).all()
    }

    finance_routes = {"/dashboard", "/finance", "/finance/invoices", "/finance/settlements", "/audit/logs"}
    fleet_routes = {
        "/dashboard",
        "/fleet/batteries",
        "/fleet/stock",
        "/fleet/health",
        "/fleet/audit",
        "/stations",
        "/stations/maintenance",
        "/fleet-ops/iot",
        "/fleet-ops/geofence",
        "/fleet-ops/alerts",
        "/logistics/orders",
        "/logistics/routes",
    }
    support_routes = {
        "/dashboard",
        "/user-master",
        "/user-master/logs",
        "/support/tickets",
        "/support/knowledge",
        "/notifications",
        "/notifications/logs",
        "/cms/blogs",
        "/cms/banners",
    }
    risk_routes = {
        "/dashboard",
        "/user-master",
        "/user-master/logs",
        "/user-master",
        "/audit/logs",
        "/audit/security-events",
        "/audit/fraud",
        "/settings",
    }
    dealer_routes = {
        "/dashboard",
        "/dealers",
        "/dealers/registrations",
        "/dealers/documents",
        "/dealers/commissions",
        "/finance/settlements",
        "/logistics/orders",
    }
    existing_role_rights = {
        (row.role_id, row.menu_id): row
        for row in session.exec(
            select(RoleRight).where(
                RoleRight.role_id.in_(list(persisted_roles.values())),
                RoleRight.menu_id.in_(list(persisted_menus.values())),
            )
        ).all()
    }
    desired_role_rights: dict[tuple[int, int], dict[str, bool]] = {}
    role_name_map = {
        "super_admin": "Super Admin",
        "fleet_manager": "Fleet Manager",
        "finance_manager": "Finance Manager",
        "support_lead": "Support Lead",
        "risk_analyst": "Risk Analyst",
        "dealer_success": "Dealer Success Manager",
        "logistics_coordinator": "Logistics Coordinator",
    }
    def set_role_right(
        role_key: str,
        menu_id: int,
        *,
        can_view: bool = False,
        can_create: bool = False,
        can_edit: bool = False,
        can_delete: bool = False,
    ) -> None:
        desired_role_rights[(persisted_roles[role_name_map[role_key]], menu_id)] = {
            "can_view": can_view,
            "can_create": can_create,
            "can_edit": can_edit,
            "can_delete": can_delete,
        }

    for route, menu_id in persisted_menus.items():
        route = route or ""
        set_role_right(
            "super_admin",
            menu_id,
            can_view=True,
            can_create=True,
            can_edit=True,
            can_delete=True,
        )
        if route in fleet_routes:
            set_role_right(
                "fleet_manager",
                menu_id,
                can_view=True,
                can_create=route in {"/fleet/audit", "/fleet/stock"},
                can_edit=True,
            )
        if route in finance_routes:
            set_role_right(
                "finance_manager",
                menu_id,
                can_view=True,
                can_create=False,
                can_edit=True,
            )
        if route in support_routes:
            set_role_right(
                "support_lead",
                menu_id,
                can_view=True,
                can_create=True,
                can_edit=True,
            )
        if route in risk_routes:
            set_role_right(
                "risk_analyst",
                menu_id,
                can_view=True,
                can_edit=True,
            )
        if route in dealer_routes:
            set_role_right(
                "dealer_success",
                menu_id,
                can_view=True,
                can_edit=True,
            )
        if route in {"/dashboard", "/logistics/orders", "/logistics/routes", "/logistics/drivers", "/fleet-ops/alerts"}:
            set_role_right(
                "logistics_coordinator",
                menu_id,
                can_view=True,
                can_edit=True,
            )
    for (role_id, menu_id), rights in desired_role_rights.items():
        role_right = existing_role_rights.get((role_id, menu_id))
        if role_right is None:
            role_right = RoleRight(
                role_id=role_id,
                menu_id=menu_id,
                created_by="seed-showcase",
            )
        role_right.can_view = rights["can_view"]
        role_right.can_create = rights["can_create"]
        role_right.can_edit = rights["can_edit"]
        role_right.can_delete = rights["can_delete"]
        role_right.modified_by = "seed-showcase"
        session.add(role_right)
    session.flush()


def seed_users(session: Session, ctx: SeedContext) -> None:
    from app.models.address import Address
    from app.models.biometric import BiometricCredential
    from app.models.kyc import KYCRecord, KYCRequest, KYCDocument, KYCDocumentStatus, KYCDocumentType
    from app.models.rbac import UserAccessPath, UserRole
    from app.models.security_question import SecurityQuestion, UserSecurityQuestion
    from app.models.user import KYCStatus, User, UserStatus, UserType
    from app.models.user_history import UserStatusLog
    from app.models.user_profile import UserProfile
    from app.models.financial import Wallet

    user_specs = [
        ("admin_super", "Aarav Menon", "aarav.menon@powerfill.in", "9000001001", UserType.ADMIN, UserStatus.ACTIVE, "super_admin", "Leadership"),
        ("admin_fleet", "Vivek Reddy", "vivek.reddy@powerfill.in", "9000001002", UserType.ADMIN, UserStatus.ACTIVE, "fleet_manager", "Fleet Ops"),
        ("admin_finance", "Sana Khan", "sana.khan@powerfill.in", "9000001003", UserType.ADMIN, UserStatus.ACTIVE, "finance_manager", "Finance"),
        ("admin_support", "Meera Iyer", "meera.iyer@powerfill.in", "9000001004", UserType.ADMIN, UserStatus.ACTIVE, "support_lead", "Support"),
        ("admin_risk", "Rizwan Shaik", "rizwan.shaik@powerfill.in", "9000001005", UserType.ADMIN, UserStatus.ACTIVE, "risk_analyst", "Risk"),
        ("field_officer", "Sanjay Kumar", "sanjay.kumar@powerfill.in", "9000001011", UserType.ADMIN, UserStatus.ACTIVE, "dealer_success", "Field Ops"),
        ("support_agent_1", "Rakesh Nair", "rakesh.nair@powerfill.in", "9000001012", UserType.SUPPORT_AGENT, UserStatus.ACTIVE, "support_agent", "Support"),
        ("support_agent_2", "Tara Bose", "tara.bose@powerfill.in", "9000001013", UserType.SUPPORT_AGENT, UserStatus.ACTIVE, "support_agent", "Support"),
        ("driver_1", "Manoj Yadav", "manoj.yadav@powerfill.in", "9000001014", UserType.LOGISTICS, UserStatus.ACTIVE, "driver", "Logistics"),
        ("driver_2", "Imran Qureshi", "imran.qureshi@powerfill.in", "9000001015", UserType.LOGISTICS, UserStatus.ACTIVE, "driver", "Logistics"),
        ("driver_3", "Harsha Vemula", "harsha.vemula@powerfill.in", "9000001016", UserType.LOGISTICS, UserStatus.ACTIVE, "driver", "Logistics"),
        ("driver_4", "Shweta Das", "shweta.das@powerfill.in", "9000001017", UserType.LOGISTICS, UserStatus.ACTIVE, "driver", "Logistics"),
        ("dealer_owner_1", "Suresh Rao", "suresh.rao@metroenergy.in", "9000001021", UserType.DEALER, UserStatus.ACTIVE, "dealer_owner", "Dealer Network"),
        ("dealer_owner_2", "Farah Khan", "farah.khan@citycharge.in", "9000001022", UserType.DEALER, UserStatus.ACTIVE, "dealer_owner", "Dealer Network"),
        ("dealer_owner_3", "Mahesh Verma", "mahesh.verma@hanamkondaev.in", "9000001023", UserType.DEALER, UserStatus.PENDING, "dealer_owner", "Dealer Network"),
        ("dealer_owner_4", "Pooja Narang", "pooja.narang@rayalaev.in", "9000001024", UserType.DEALER, UserStatus.PENDING, "dealer_owner", "Dealer Network"),
        ("customer_1", "Ananya Sharma", "ananya.sharma@powerfill.app", "9000002001", UserType.CUSTOMER, UserStatus.ACTIVE, "customer", "Riders"),
        ("customer_2", "Rohan Verma", "rohan.verma@powerfill.app", "9000002002", UserType.CUSTOMER, UserStatus.ACTIVE, "customer", "Riders"),
        ("customer_3", "Priya Nair", "priya.nair@powerfill.app", "9000002003", UserType.CUSTOMER, UserStatus.ACTIVE, "customer", "Riders"),
        ("customer_4", "Dev Patil", "dev.patil@powerfill.app", "9000002004", UserType.CUSTOMER, UserStatus.ACTIVE, "customer", "Riders"),
        ("customer_5", "Neha Reddy", "neha.reddy@powerfill.app", "9000002005", UserType.CUSTOMER, UserStatus.ACTIVE, "customer", "Riders"),
        ("customer_6", "Kiran Singh", "kiran.singh@powerfill.app", "9000002006", UserType.CUSTOMER, UserStatus.ACTIVE, "customer", "Riders"),
        ("customer_7", "Kavya Joshi", "kavya.joshi@powerfill.app", "9000002007", UserType.CUSTOMER, UserStatus.PENDING_VERIFICATION, "customer", "Riders"),
        ("customer_8", "Arjun Malik", "arjun.malik@powerfill.app", "9000002008", UserType.CUSTOMER, UserStatus.ACTIVE, "customer", "Riders"),
        ("customer_9", "Aisha Khan", "aisha.khan@powerfill.app", "9000002009", UserType.CUSTOMER, UserStatus.SUSPENDED, "customer", "Riders"),
        ("customer_10", "Nikhil Gupta", "nikhil.gupta@powerfill.app", "9000002010", UserType.CUSTOMER, UserStatus.ACTIVE, "customer", "Riders"),
    ]

    for key, full_name, email, phone, user_type, status, role_key, department in user_specs:
        user = User(
            full_name=full_name,
            email=email,
            phone_number=phone,
            hashed_password="seed-only-user-password",
            user_type=user_type,
            status=status,
            role_id=ctx.roles[role_key].id,
            department=department,
            last_login=_ts(days_ago=(len(ctx.users) % 6), hours_ago=(len(ctx.users) % 5) * 2),
            password_changed_at=_ts(days_ago=12),
            profile_picture=f"https://assets.powerfill.demo/profiles/{key}.jpg",
            kyc_status=KYCStatus.NOT_SUBMITTED,
            created_at=_ts(days_ago=90 - len(ctx.users) * 2),
            updated_at=_ts(days_ago=max(1, len(ctx.users) % 9)),
        )
        if key.startswith("customer_"):
            user.notes_internal = "Seeded customer account for admin showcase"
        if key.startswith("dealer_owner_"):
            user.notes_internal = "Dealer principal account"
        ctx.users[key] = user
    session.add_all(ctx.users.values())
    session.flush()

    assigned_by_admin_id = ctx.admin_users["super"].id
    session.add_all(
        [
            UserRole(
                user_id=user.id,
                role_id=user.role_id,
                assigned_by=assigned_by_admin_id,
                notes="Seeded role assignment",
                effective_from=_ts(days_ago=45),
            )
            for user in ctx.users.values()
            if user.role_id
        ]
    )

    access_paths = [
        UserAccessPath(user_id=ctx.users["admin_super"].id, path_pattern="India/%", access_level="admin"),
        UserAccessPath(user_id=ctx.users["admin_fleet"].id, path_pattern="India/Telangana/%", access_level="manage"),
        UserAccessPath(user_id=ctx.users["admin_finance"].id, path_pattern="India/%", access_level="view"),
        UserAccessPath(user_id=ctx.users["admin_support"].id, path_pattern="India/Telangana/Hyderabad/%", access_level="manage"),
        UserAccessPath(user_id=ctx.users["admin_risk"].id, path_pattern="India/%", access_level="manage"),
        UserAccessPath(user_id=ctx.users["dealer_owner_1"].id, path_pattern="India/Telangana/Hyderabad/Jubilee Hills/%", access_level="manage"),
        UserAccessPath(user_id=ctx.users["dealer_owner_2"].id, path_pattern="India/Telangana/Hyderabad/HITEC City/%", access_level="manage"),
        UserAccessPath(user_id=ctx.users["dealer_owner_3"].id, path_pattern="India/Telangana/Warangal/%", access_level="view"),
    ]
    for access_path in access_paths:
        access_path.created_by = ctx.admin_users["super"].id
    session.add_all(access_paths)

    profile_specs = {
        "customer_1": ("12 Road No 36", "Banjara Hills", "Hyderabad", "Telangana", "500034"),
        "customer_2": ("My Home Bhooja", "Madhapur", "Hyderabad", "Telangana", "500081"),
        "customer_3": ("KPHB Colony", "Kukatpally", "Hyderabad", "Telangana", "500072"),
        "customer_4": ("Sainikpuri Main Road", "Secunderabad", "Hyderabad", "Telangana", "500094"),
        "customer_5": ("Uppal Depot Road", "Uppal", "Hyderabad", "Telangana", "500039"),
        "customer_6": ("Hanamkonda Cross", "Hanamkonda", "Warangal", "Telangana", "506001"),
        "customer_7": ("Madhapur Lakeside", "Madhapur", "Hyderabad", "Telangana", "500081"),
        "customer_8": ("Kazipet Junction Road", "Kazipet", "Warangal", "Telangana", "506003"),
        "customer_9": ("Kondapur Main Road", "Kondapur", "Hyderabad", "Telangana", "500084"),
        "customer_10": ("Ameerpet Metro Lane", "Ameerpet", "Hyderabad", "Telangana", "500016"),
        "dealer_owner_1": ("Madhapur Trade Centre", "Madhapur", "Hyderabad", "Telangana", "500081"),
        "dealer_owner_2": ("Banjara Business Park", "Banjara Hills", "Hyderabad", "Telangana", "500034"),
        "dealer_owner_3": ("Hanamkonda High Street", "Hanamkonda", "Warangal", "Telangana", "506001"),
        "dealer_owner_4": ("Kondapur Industrial Block", "Kondapur", "Hyderabad", "Telangana", "500084"),
    }
    for key, (line1, line2, city, state, pin_code) in profile_specs.items():
        profile = UserProfile(
            user_id=ctx.users[key].id,
            address_line_1=line1,
            address_line_2=line2,
            city=city,
            state=state,
            pin_code=pin_code,
            preferred_language="en",
            notification_preferences={"push": True, "email": True, "sms": key.startswith("customer_")},
            created_at=_ts(days_ago=85),
            updated_at=_ts(days_ago=3),
        )
        address = Address(
            user_id=ctx.users[key].id,
            address_line1=line1,
            address_line2=line2,
            city=city,
            state=state,
            postal_code=pin_code,
            country="India",
            is_default=True,
            type="home" if key.startswith("customer_") else "office",
            latitude=17.43 if city == "Hyderabad" else 17.98,
            longitude=78.39 if city == "Hyderabad" else 79.59,
            created_at=_ts(days_ago=85),
            updated_at=_ts(days_ago=3),
        )
        ctx.addresses[key] = address
        session.add(profile)
        session.add(address)

    wallet_specs = {
        "customer_1": (1285.0, 120.0),
        "customer_2": (845.0, 0.0),
        "customer_3": (540.0, 40.0),
        "customer_4": (1220.0, 60.0),
        "customer_5": (310.0, 0.0),
        "customer_6": (980.0, 80.0),
        "customer_7": (150.0, 0.0),
        "customer_8": (220.0, 0.0),
        "customer_9": (0.0, 0.0),
        "customer_10": (710.0, 25.0),
        "dealer_owner_1": (22450.0, 0.0),
        "dealer_owner_2": (18230.0, 0.0),
        "dealer_owner_3": (7450.0, 0.0),
        "dealer_owner_4": (3900.0, 0.0),
    }
    for key, (balance, cashback_balance) in wallet_specs.items():
        wallet = Wallet(
            user_id=ctx.users[key].id,
            balance=balance,
            cashback_balance=cashback_balance,
            updated_at=_ts(days_ago=1),
        )
        ctx.wallets[key] = wallet
    session.add_all(ctx.wallets.values())
    session.flush()

    question_texts = {
        "school": "What was the name of your first school?",
        "city": "In which city did your parents meet?",
        "nickname": "What was your childhood nickname?",
    }
    existing_questions = {
        question.question_text: question
        for question in session.exec(
            select(SecurityQuestion).where(SecurityQuestion.question_text.in_(list(question_texts.values())))
        ).all()
    }
    security_questions: dict[str, SecurityQuestion] = {}
    for key, question_text in question_texts.items():
        question = existing_questions.get(question_text)
        if question is None:
            question = SecurityQuestion(question_text=question_text)
        else:
            question.is_active = True
        security_questions[key] = question
        session.add(question)
    session.flush()
    ctx.questions.update(security_questions)

    session.add_all(
        [
            UserSecurityQuestion(
                user_id=ctx.users["customer_1"].id,
                question_id=security_questions["school"].id,
                hashed_answer="seed-answer-1",
            ),
            UserSecurityQuestion(
                user_id=ctx.users["customer_2"].id,
                question_id=security_questions["city"].id,
                hashed_answer="seed-answer-2",
            ),
            UserSecurityQuestion(
                user_id=ctx.users["customer_3"].id,
                question_id=security_questions["nickname"].id,
                hashed_answer="seed-answer-3",
            ),
            UserSecurityQuestion(
                user_id=ctx.users["dealer_owner_1"].id,
                question_id=security_questions["city"].id,
                hashed_answer="dealer-answer-1",
            ),
            UserSecurityQuestion(
                user_id=ctx.users["driver_1"].id,
                question_id=security_questions["school"].id,
                hashed_answer="driver-answer-1",
            ),
        ]
    )

    session.add_all(
        [
            BiometricCredential(
                user_id=ctx.users["customer_1"].id,
                device_id="DEVICE-ANANYA-01",
                credential_id="cred-ananya-01",
                public_key="pk-ananya-01",
                friendly_name="Ananya Pixel 8",
                created_at=_ts(days_ago=20),
                last_used_at=_ts(days_ago=1),
            ),
            BiometricCredential(
                user_id=ctx.users["customer_4"].id,
                device_id="DEVICE-DEV-01",
                credential_id="cred-dev-01",
                public_key="pk-dev-01",
                friendly_name="Dev iPhone 15",
                created_at=_ts(days_ago=18),
                last_used_at=_ts(days_ago=2),
            ),
        ]
    )

    session.add_all(
        [
            UserStatusLog(
                user_id=ctx.users["customer_9"].id,
                actor_id=ctx.users["admin_risk"].id,
                action_type="suspension",
                old_value="active",
                new_value="suspended",
                reason="Chargeback investigation and duplicate-device match",
                created_at=_ts(days_ago=9),
            ),
            UserStatusLog(
                user_id=ctx.users["customer_8"].id,
                actor_id=ctx.users["admin_support"].id,
                action_type="reactivation",
                old_value="pending_verification",
                new_value="active",
                reason="Manual KYC follow-up completed",
                expires_at=_future(days_ahead=30),
                created_at=_ts(days_ago=2),
            ),
            UserStatusLog(
                user_id=ctx.users["support_agent_1"].id,
                actor_id=ctx.users["admin_super"].id,
                action_type="role_change",
                old_value="customer",
                new_value="support_agent",
                reason="Promoted into support desk pilot",
                created_at=_ts(days_ago=14),
            ),
        ]
    )

    kyc_bundle = {
        "customer_1": (KYCStatus.APPROVED, "verified"),
        "customer_2": (KYCStatus.APPROVED, "verified"),
        "customer_3": (KYCStatus.APPROVED, "verified"),
        "customer_4": (KYCStatus.APPROVED, "verified"),
        "customer_5": (KYCStatus.APPROVED, "verified"),
        "customer_6": (KYCStatus.APPROVED, "verified"),
        "customer_7": (KYCStatus.PENDING, "pending"),
        "customer_8": (KYCStatus.PENDING, "pending"),
        "customer_9": (KYCStatus.REJECTED, "rejected"),
    }
    for key, (status, record_status) in kyc_bundle.items():
        user = ctx.users[key]
        user.kyc_status = status
        if status == KYCStatus.REJECTED:
            user.kyc_rejection_reason = "PAN verification failed against submitted document"
        session.add(user)

        kyc_record = KYCRecord(
            user_id=user.id,
            aadhaar_number_enc=f"enc-aadhaar-{key}",
            pan_number_enc=f"enc-pan-{key}",
            aadhaar_front_url=f"https://assets.powerfill.demo/kyc/{key}/aadhaar-front.jpg",
            aadhaar_back_url=f"https://assets.powerfill.demo/kyc/{key}/aadhaar-back.jpg",
            pan_card_url=f"https://assets.powerfill.demo/kyc/{key}/pan.jpg",
            status=record_status,
            submitted_at=_ts(days_ago=40 - int(key.split('_')[-1])),
            verified_at=_ts(days_ago=18) if record_status == "verified" else None,
            verified_by=ctx.users["admin_support"].id if record_status == "verified" else None,
            rejection_reason=user.kyc_rejection_reason if record_status == "rejected" else None,
            updated_at=_ts(days_ago=3),
        )
        session.add(kyc_record)

        request = KYCRequest(
            user_id=user.id,
            status=record_status,
            request_data='{"source":"mobile_app","attempt":1}',
            created_at=_ts(days_ago=40 - int(key.split('_')[-1])),
            updated_at=_ts(days_ago=3),
        )
        session.add(request)

        document_status = {
            "verified": KYCDocumentStatus.VERIFIED,
            "pending": KYCDocumentStatus.PENDING,
            "rejected": KYCDocumentStatus.REJECTED,
        }[record_status]
        session.add_all(
            [
                KYCDocument(
                    user_id=user.id,
                    document_type=KYCDocumentType.AADHAAR,
                    document_number=f"AADHAAR-{key.upper()}",
                    file_url=f"https://assets.powerfill.demo/kyc/{key}/aadhaar-card.pdf",
                    status=document_status,
                    verified_by=ctx.users["admin_support"].id if document_status == KYCDocumentStatus.VERIFIED else None,
                    uploaded_at=_ts(days_ago=39),
                    verified_at=_ts(days_ago=18) if document_status == KYCDocumentStatus.VERIFIED else None,
                    rejection_reason=user.kyc_rejection_reason if document_status == KYCDocumentStatus.REJECTED else None,
                ),
                KYCDocument(
                    user_id=user.id,
                    document_type=KYCDocumentType.PAN,
                    document_number=f"PAN-{key.upper()}",
                    file_url=f"https://assets.powerfill.demo/kyc/{key}/pan-card.pdf",
                    status=document_status,
                    verified_by=ctx.users["admin_support"].id if document_status == KYCDocumentStatus.VERIFIED else None,
                    uploaded_at=_ts(days_ago=39),
                    verified_at=_ts(days_ago=18) if document_status == KYCDocumentStatus.VERIFIED else None,
                    rejection_reason=user.kyc_rejection_reason if document_status == KYCDocumentStatus.REJECTED else None,
                ),
            ]
        )

    session.flush()


def seed_dealers_and_vendors(session: Session, ctx: SeedContext) -> None:
    from app.models.commission import CommissionConfig
    from app.models.dealer import DealerApplication, DealerDocument, DealerProfile, FieldVisit
    from app.models.vendor import Vendor, VendorDocument

    vendor = Vendor(
        name="RapidHaul Mobility Services",
        email="ops@rapidhaul.in",
        phone="+91-9000003001",
        license_number="VND-TS-2025-114",
        commission_rate=6.5,
        contract_start_date=_ts(days_ago=120),
        contract_end_date=_future(days_ahead=240),
        status="active",
        zone_id=ctx.zones["madhapur"].id,
        address="Plot 18, Logistics Park, Madhapur, Hyderabad",
        gps_coordinates="17.4505,78.3918",
        created_at=_ts(days_ago=120),
        updated_at=_ts(days_ago=3),
    )
    ctx.vendors["rapidhaul"] = vendor
    session.add(vendor)
    session.flush()

    session.add_all(
        [
            VendorDocument(
                vendor_id=vendor.id,
                document_type="transport_license",
                file_path="https://assets.powerfill.demo/vendors/rapidhaul/transport-license.pdf",
                uploaded_at=_ts(days_ago=115),
                is_verified=True,
            ),
            VendorDocument(
                vendor_id=vendor.id,
                document_type="insurance_policy",
                file_path="https://assets.powerfill.demo/vendors/rapidhaul/insurance.pdf",
                uploaded_at=_ts(days_ago=112),
                is_verified=True,
            ),
        ]
    )

    dealer_specs = [
        (
            "metro_energy",
            "dealer_owner_1",
            "Metro Energy Partners",
            "Hyderabad",
            "Telangana",
            "500081",
            True,
            "ACTIVE",
            22.5,
        ),
        (
            "city_charge",
            "dealer_owner_2",
            "CityCharge Franchise Network",
            "Hyderabad",
            "Telangana",
            "500034",
            True,
            "ACTIVE",
            14.3,
        ),
        (
            "hanamkonda_mobility",
            "dealer_owner_3",
            "Hanamkonda Mobility Hub",
            "Warangal",
            "Telangana",
            "506001",
            False,
            "FIELD_VISIT_SCHEDULED",
            11.8,
        ),
        (
            "rayala_ev",
            "dealer_owner_4",
            "Rayala EV Traders",
            "Hyderabad",
            "Telangana",
            "500084",
            False,
            "KYC_SUBMITTED",
            18.6,
        ),
    ]
    for key, user_key, business_name, city, state, pincode, is_active, stage, risk_score in dealer_specs:
        user = ctx.users[user_key]
        dealer = DealerProfile(
            user_id=user.id,
            business_name=business_name,
            gst_number=f"36AAC{user.id:04d}1ZP",
            pan_number=f"PAN{user.id:07d}",
            year_established="2021" if city == "Hyderabad" else "2023",
            website_url=f"https://{key}.powerfill.demo",
            business_description=f"{business_name} operates local battery exchange and field support coverage.",
            contact_person=user.full_name,
            contact_email=user.email,
            contact_phone=user.phone_number,
            alternate_phone=f"+91-40-40{user.id:04d}",
            whatsapp_number=user.phone_number,
            support_email=f"support@{key}.powerfill.demo",
            support_phone=f"+91-40-50{user.id:04d}",
            address_line1=f"{business_name}, Distribution Row",
            city=city,
            state=state,
            pincode=pincode,
            bank_details={
                "beneficiary": business_name,
                "bank_name": "HDFC Bank",
                "account_number": f"502000{user.id:06d}",
                "ifsc": "HDFC0001234",
            },
            global_station_defaults={"low_stock_threshold_pct": 18, "heartbeat_grace_minutes": 12},
            global_inventory_rules={"reorder_window_days": 3, "restock_batch_size": 8},
            global_rental_settings={"security_deposit": 1499, "grace_period_minutes": 30},
            holiday_calendar=[{"date": "2026-08-15", "label": "Independence Day"}],
            is_active=is_active,
            created_at=_ts(days_ago=110 - user.id),
        )
        ctx.dealers[key] = dealer
    session.add_all(ctx.dealers.values())
    session.flush()

    for key, _, _, _, _, _, is_active, stage, risk_score in dealer_specs:
        dealer = ctx.dealers[key]
        application = DealerApplication(
            dealer_id=dealer.id,
            current_stage=stage,
            risk_score=risk_score,
            status_history=[
                {"stage": "SUBMITTED", "timestamp": _ts(days_ago=75).isoformat(), "notes": "Initial application submitted"},
                {"stage": "AUTOMATED_CHECKS_PASSED", "timestamp": _ts(days_ago=72).isoformat(), "notes": "Basic validation passed"},
                {"stage": stage, "timestamp": _ts(days_ago=8 if is_active else 3).isoformat(), "notes": "Current pipeline stage"},
            ],
            created_at=_ts(days_ago=75),
            updated_at=_ts(days_ago=2),
        )
        session.add(application)
        session.flush()

        session.add_all(
            [
                DealerDocument(
                    dealer_id=dealer.id,
                    document_type="gst_certificate",
                    category="verification",
                    file_url=f"https://assets.powerfill.demo/dealers/{key}/gst.pdf",
                    version=1,
                    status="VERIFIED" if is_active else "PENDING",
                    uploaded_at=_ts(days_ago=70),
                    is_verified=is_active,
                ),
                DealerDocument(
                    dealer_id=dealer.id,
                    document_type="cancelled_cheque",
                    category="financial",
                    file_url=f"https://assets.powerfill.demo/dealers/{key}/cancelled-cheque.pdf",
                    version=1,
                    status="VERIFIED" if key in {"metro_energy", "city_charge"} else "PENDING",
                    uploaded_at=_ts(days_ago=68),
                    is_verified=key in {"metro_energy", "city_charge"},
                ),
            ]
        )

        if key in {"hanamkonda_mobility", "metro_energy"}:
            session.add(
                FieldVisit(
                    application_id=application.id,
                    officer_id=ctx.users["field_officer"].id,
                    scheduled_date=_future(days_ahead=2 if key == "hanamkonda_mobility" else -12),
                    completed_date=_ts(days_ago=10) if key == "metro_energy" else None,
                    status="COMPLETED" if key == "metro_energy" else "SCHEDULED",
                    report_data={
                        "branding": "strong",
                        "ops_readiness": "good" if key == "metro_energy" else "pending",
                        "storage_capacity": 28 if key == "metro_energy" else 16,
                    },
                    images=[
                        f"https://assets.powerfill.demo/dealers/{key}/field-visit-1.jpg",
                        f"https://assets.powerfill.demo/dealers/{key}/field-visit-2.jpg",
                    ],
                    created_at=_ts(days_ago=15),
                )
            )

    session.add_all(
        [
            CommissionConfig(
                dealer_id=ctx.users["dealer_owner_1"].id,
                transaction_type="RENTAL_PAYMENT",
                percentage=8.5,
                flat_fee=0.0,
                effective_from=_ts(days_ago=90),
                is_active=True,
            ),
            CommissionConfig(
                dealer_id=ctx.users["dealer_owner_2"].id,
                transaction_type="RENTAL_PAYMENT",
                percentage=7.75,
                flat_fee=0.0,
                effective_from=_ts(days_ago=90),
                is_active=True,
            ),
            CommissionConfig(
                dealer_id=ctx.users["dealer_owner_3"].id,
                transaction_type="SWAP_FEE",
                percentage=5.0,
                flat_fee=0.0,
                effective_from=_ts(days_ago=45),
                is_active=True,
            ),
            CommissionConfig(
                vendor_id=vendor.id,
                transaction_type="dealer_restock",
                percentage=0.0,
                flat_fee=250.0,
                effective_from=_ts(days_ago=60),
                is_active=True,
            ),
        ]
    )

    session.flush()


def seed_stations(session: Session, ctx: SeedContext) -> None:
    from app.models.alert import Alert
    from app.models.geofence import Geofence
    from app.models.maintenance import MaintenanceRecord, StationDowntime
    from app.models.station import Station
    from app.models.station_heartbeat import StationHeartbeat
    from app.models.station_stock import ReorderRequest, StationStockConfig, StockAlertDismissal

    station_specs = [
        (
            "jubilee_hills_hub",
            "Jubilee Hills Hub",
            "Road No. 36, Jubilee Hills, Hyderabad",
            "hyderabad",
            "jubilee_hills",
            17.4311,
            78.4075,
            "metro_energy",
            "dealer_owner_1",
            24.0,
            6,
            4.6,
            True,
        ),
        (
            "hitech_city_nexus",
            "HITEC City Nexus",
            "Cyber Towers Link Road, Madhapur, Hyderabad",
            "hyderabad",
            "hitech_city",
            17.4497,
            78.3784,
            "city_charge",
            "dealer_owner_2",
            24.0,
            6,
            4.7,
            True,
        ),
        (
            "kukatpally_exchange",
            "Kukatpally Exchange",
            "KPHB 6th Phase, Kukatpally, Hyderabad",
            "hyderabad",
            "kukatpally",
            17.4933,
            78.3997,
            "metro_energy",
            "dealer_owner_1",
            18.0,
            6,
            4.3,
            False,
        ),
        (
            "secunderabad_central",
            "Secunderabad Central",
            "Sainikpuri Junction, Secunderabad",
            "hyderabad",
            "secunderabad",
            17.4875,
            78.5445,
            "city_charge",
            "dealer_owner_2",
            18.0,
            6,
            4.5,
            False,
        ),
        (
            "uppal_transit_point",
            "Uppal Transit Point",
            "Near Uppal Metro Depot, Hyderabad",
            "hyderabad",
            "uppal",
            17.4058,
            78.5591,
            "metro_energy",
            "dealer_owner_1",
            18.0,
            6,
            4.2,
            True,
        ),
        (
            "warangal_gateway",
            "Warangal Gateway",
            "Hanamkonda Main Road, Warangal",
            "warangal",
            "hanamkonda",
            17.9940,
            79.5688,
            "hanamkonda_mobility",
            "dealer_owner_3",
            12.0,
            6,
            4.1,
            False,
        ),
    ]
    for key, name, address, city_key, zone_key, latitude, longitude, dealer_key, owner_key, power_kw, total_slots, rating, is_24x7 in station_specs:
        station = Station(
            name=name,
            tenant_id="powerfill-demo",
            address=address,
            city=ctx.cities[city_key].name,
            latitude=latitude,
            longitude=longitude,
            zone_id=ctx.zones[zone_key].id,
            owner_id=ctx.users[owner_key].id,
            vendor_id=ctx.vendors["rapidhaul"].id if key in {"hitech_city_nexus", "uppal_transit_point"} else None,
            dealer_id=ctx.dealers[dealer_key].id,
            station_type="automated" if city_key == "hyderabad" else "hybrid",
            total_slots=total_slots,
            power_rating_kw=power_kw,
            max_capacity=24,
            charger_type="fast_dc",
            temperature_control=True,
            safety_features='["thermal_cutoff","surge_protection","door_sensor"]',
            available_batteries=0,
            available_slots=0,
            status="active",
            approval_status="approved",
            contact_phone=ctx.users[owner_key].phone_number,
            operating_hours='{"mon":"06:00-23:00","sun":"07:00-22:00"}',
            is_24x7=is_24x7,
            amenities='["waiting_area","cctv","qr_pay"]',
            image_url=f"https://assets.powerfill.demo/stations/{key}.jpg",
            rating=rating,
            total_reviews=38 if city_key == "hyderabad" else 16,
            last_maintenance_date=_ts(days_ago=14),
            low_stock_threshold_pct=18.0 if key == "warangal_gateway" else 22.0,
            last_heartbeat=_ts(minutes_ago=8),
            created_at=_ts(days_ago=120),
            updated_at=_ts(days_ago=1),
        )
        ctx.stations[key] = station
    session.add_all(ctx.stations.values())
    session.flush()

    session.add_all(
        [
            StationHeartbeat(
                station_id=station.id,
                timestamp=_ts(minutes_ago=index * 3),
                status="online",
                metrics='{"cpu_temp": 44, "door": "closed", "grid": "stable"}',
            )
            for index, station in enumerate(ctx.stations.values(), start=1)
        ]
    )

    session.add_all(
        [
            Geofence(
                name="Hyderabad Safe Coverage",
                latitude=17.4400,
                longitude=78.3950,
                radius_meters=2500,
                type="safe_zone",
                polygon_coords="[[17.43,78.38],[17.45,78.41],[17.44,78.43]]",
                is_active=True,
                created_at=_ts(days_ago=60),
            ),
            Geofence(
                name="Warangal Franchise Perimeter",
                latitude=17.9940,
                longitude=79.5688,
                radius_meters=1800,
                type="station_perimeter",
                polygon_coords="[[17.99,79.56],[18.00,79.57],[17.98,79.58]]",
                is_active=True,
                created_at=_ts(days_ago=48),
            ),
            Geofence(
                name="Metro Depot Restricted Yard",
                latitude=17.4058,
                longitude=78.5591,
                radius_meters=600,
                type="restricted_zone",
                is_active=True,
                created_at=_ts(days_ago=35),
            ),
            Geofence(
                name="RapidHaul Loading Bay",
                latitude=17.4505,
                longitude=78.3918,
                radius_meters=450,
                type="safe_zone",
                is_active=True,
                created_at=_ts(days_ago=28),
            ),
        ]
    )

    session.add_all(
        [
            Alert(
                station_id=ctx.stations["uppal_transit_point"].id,
                alert_type="LOW_STOCK",
                severity="HIGH",
                message="Available battery count fell below reorder point during evening peak.",
                created_at=_ts(hours_ago=6),
            ),
            Alert(
                station_id=ctx.stations["warangal_gateway"].id,
                alert_type="HEARTBEAT_DELAY",
                severity="MEDIUM",
                message="Heartbeat interval exceeded 10 minutes twice in the last day.",
                created_at=_ts(hours_ago=14),
                acknowledged_at=_ts(hours_ago=10),
                acknowledged_by=ctx.users["admin_fleet"].id,
            ),
            Alert(
                station_id=ctx.stations["hitech_city_nexus"].id,
                alert_type="PERFORMANCE",
                severity="LOW",
                message="Minor charge-rate deviation on slot 3 after firmware rollout.",
                created_at=_ts(days_ago=1, hours_ago=3),
            ),
            Alert(
                station_id=ctx.stations["jubilee_hills_hub"].id,
                alert_type="OFFLINE",
                severity="MEDIUM",
                message="Door controller heartbeat dropped briefly during the morning commuter window.",
                created_at=_ts(hours_ago=11),
                acknowledged_at=_ts(hours_ago=9),
                acknowledged_by=ctx.users["admin_fleet"].id,
            ),
            Alert(
                station_id=ctx.stations["kukatpally_exchange"].id,
                alert_type="HARDWARE",
                severity="HIGH",
                message="Slot 4 latch sensor is intermittently misreporting locked state.",
                created_at=_ts(days_ago=2, hours_ago=5),
            ),
            Alert(
                station_id=ctx.stations["secunderabad_central"].id,
                alert_type="POWER_FAIL",
                severity="LOW",
                message="Short utility dip detected; site remained online on backup feed.",
                created_at=_ts(days_ago=3, hours_ago=2),
                acknowledged_at=_ts(days_ago=3, hours_ago=1),
                acknowledged_by=ctx.users["admin_fleet"].id,
            ),
        ]
    )

    session.add_all(
        [
            MaintenanceRecord(
                entity_type="station",
                entity_id=ctx.stations["jubilee_hills_hub"].id,
                technician_id=ctx.users["field_officer"].id,
                maintenance_type="preventive",
                description="Quarterly cabinet inspection and relay recalibration.",
                cost=4200.0,
                parts_replaced='["fan_filter","door_gasket"]',
                status="completed",
                performed_at=_ts(days_ago=14),
            ),
            MaintenanceRecord(
                entity_type="station",
                entity_id=ctx.stations["uppal_transit_point"].id,
                technician_id=ctx.users["field_officer"].id,
                maintenance_type="corrective",
                description="Resolved feeder cable heating issue on bay 2.",
                cost=7800.0,
                parts_replaced='["power_cable"]',
                status="completed",
                performed_at=_ts(days_ago=6),
            ),
            MaintenanceRecord(
                entity_type="station",
                entity_id=ctx.stations["warangal_gateway"].id,
                technician_id=ctx.users["field_officer"].id,
                maintenance_type="inspection",
                description="Pre-activation readiness audit before franchise launch.",
                cost=1850.0,
                status="scheduled",
                performed_at=_future(days_ahead=2),
            ),
        ]
    )

    session.add_all(
        [
            StationDowntime(
                station_id=ctx.stations["uppal_transit_point"].id,
                start_time=_ts(days_ago=6, hours_ago=6),
                end_time=_ts(days_ago=6, hours_ago=2),
                reason="Power feed isolation during cable replacement",
            ),
            StationDowntime(
                station_id=ctx.stations["warangal_gateway"].id,
                start_time=_ts(days_ago=2, hours_ago=4),
                end_time=None,
                reason="Pending final utility meter synchronization",
            ),
        ]
    )

    stock_configs = {
        "jubilee_hills_hub": StationStockConfig(
            station_id=ctx.stations["jubilee_hills_hub"].id,
            max_capacity=24,
            reorder_point=4,
            reorder_quantity=8,
            manager_email="fleet.hyd@powerfill.in",
            manager_phone="+91-40-4000-1001",
            updated_by=ctx.users["admin_fleet"].id,
            updated_at=_ts(days_ago=3),
        ),
        "hitech_city_nexus": StationStockConfig(
            station_id=ctx.stations["hitech_city_nexus"].id,
            max_capacity=24,
            reorder_point=4,
            reorder_quantity=6,
            manager_email="fleet.hyd@powerfill.in",
            manager_phone="+91-40-4000-1002",
            updated_by=ctx.users["admin_fleet"].id,
            updated_at=_ts(days_ago=3),
        ),
        "kukatpally_exchange": StationStockConfig(
            station_id=ctx.stations["kukatpally_exchange"].id,
            max_capacity=20,
            reorder_point=3,
            reorder_quantity=6,
            manager_email="fleet.hyd@powerfill.in",
            manager_phone="+91-40-4000-1003",
            updated_by=ctx.users["admin_fleet"].id,
            updated_at=_ts(days_ago=2),
        ),
        "secunderabad_central": StationStockConfig(
            station_id=ctx.stations["secunderabad_central"].id,
            max_capacity=20,
            reorder_point=3,
            reorder_quantity=5,
            manager_email="fleet.hyd@powerfill.in",
            manager_phone="+91-40-4000-1004",
            updated_by=ctx.users["admin_fleet"].id,
            updated_at=_ts(days_ago=2),
        ),
        "uppal_transit_point": StationStockConfig(
            station_id=ctx.stations["uppal_transit_point"].id,
            max_capacity=18,
            reorder_point=3,
            reorder_quantity=5,
            manager_email="fleet.hyd@powerfill.in",
            manager_phone="+91-40-4000-1005",
            updated_by=ctx.users["admin_fleet"].id,
            updated_at=_ts(days_ago=1),
        ),
        "warangal_gateway": StationStockConfig(
            station_id=ctx.stations["warangal_gateway"].id,
            max_capacity=16,
            reorder_point=3,
            reorder_quantity=6,
            manager_email="fleet.wgl@powerfill.in",
            manager_phone="+91-870-400-1001",
            updated_by=ctx.users["admin_fleet"].id,
            updated_at=_ts(hours_ago=8),
        ),
    }
    ctx.stock_configs.update(stock_configs)
    session.add_all(stock_configs.values())
    session.flush()

    session.add_all(
        [
            ReorderRequest(
                station_id=ctx.stations["warangal_gateway"].id,
                requested_quantity=6,
                reason="Launch-week demand is outpacing inbound stock buffer.",
                status="pending",
                created_by=ctx.users["admin_fleet"].id,
                created_at=_ts(hours_ago=5),
            ),
            ReorderRequest(
                station_id=ctx.stations["uppal_transit_point"].id,
                requested_quantity=5,
                reason="Peak-hour swap volume after metro commuter campaign.",
                status="approved",
                created_by=ctx.users["admin_fleet"].id,
                created_at=_ts(days_ago=1, hours_ago=3),
            ),
            ReorderRequest(
                station_id=ctx.stations["hitech_city_nexus"].id,
                requested_quantity=6,
                reason="Upcoming corporate campus activation expected to lift demand.",
                status="fulfilled",
                created_by=ctx.users["admin_fleet"].id,
                created_at=_ts(days_ago=6),
                fulfilled_at=_ts(days_ago=3),
            ),
            ReorderRequest(
                station_id=ctx.stations["kukatpally_exchange"].id,
                requested_quantity=4,
                reason="One maintenance batch pulled capacity below normal range.",
                status="cancelled",
                created_by=ctx.users["admin_fleet"].id,
                created_at=_ts(days_ago=9),
            ),
        ]
    )

    session.add(
        StockAlertDismissal(
            station_id=ctx.stations["secunderabad_central"].id,
            reason="Alert suppressed after manual count reconciliation showed healthy stock.",
            dismissed_by=ctx.users["admin_fleet"].id,
            dismissed_at=_ts(days_ago=4),
            is_active=False,
        )
    )

    session.flush()


def seed_batteries_and_fleet(session: Session, ctx: SeedContext) -> None:
    from app.models.battery import (
        Battery,
        BatteryAuditLog,
        BatteryHealth,
        BatteryHealthHistory,
        BatteryLifecycleEvent,
        BatteryStatus,
        LocationType,
    )
    from app.models.battery_catalog import BatteryBatch, BatteryCatalog
    from app.models.battery_health import (
        AlertSeverity,
        AlertType,
        BatteryHealthAlert,
        BatteryHealthSnapshot,
        BatteryMaintenanceSchedule,
        MaintenancePriority,
        MaintenanceStatus,
        MaintenanceType,
        SnapshotType,
    )
    from app.models.battery_reservation import BatteryReservation
    from app.models.inventory_audit import InventoryAuditLog
    from app.models.iot import DeviceCommand, FirmwareUpdate, IoTDevice
    from app.models.maintenance import MaintenanceRecord
    from app.models.station import StationSlot
    from app.models.telemetry import Telemetry

    sku_standard = BatteryCatalog(
        name="PowerFill LFP 48V 30Ah",
        brand="VoltEdge",
        model="VE-48-30",
        image_url="https://assets.powerfill.demo/catalog/ve-48-30.png",
        description="Urban commuter pack for daily swap operations.",
        capacity_mah=30000,
        capacity_ah=30.0,
        cycle_life_expectancy=1800,
        voltage=48.0,
        battery_type="lfp",
        weight_kg=14.8,
        dimensions="410x215x155 mm",
        price_full_purchase=28999.0,
        price_per_day=179.0,
        warranty_months=24,
        is_active=True,
        created_at=_ts(days_ago=180),
        updated_at=_ts(days_ago=7),
    )
    sku_long_range = BatteryCatalog(
        name="PowerFill LFP 60V 32Ah",
        brand="VoltEdge",
        model="VE-60-32",
        image_url="https://assets.powerfill.demo/catalog/ve-60-32.png",
        description="Higher-capacity battery for enterprise and dense commute corridors.",
        capacity_mah=32000,
        capacity_ah=32.0,
        cycle_life_expectancy=2000,
        voltage=60.0,
        battery_type="lfp",
        weight_kg=16.2,
        dimensions="430x225x165 mm",
        price_full_purchase=33999.0,
        price_per_day=209.0,
        warranty_months=30,
        is_active=True,
        created_at=_ts(days_ago=180),
        updated_at=_ts(days_ago=7),
    )
    ctx.battery_skus["standard"] = sku_standard
    ctx.battery_skus["long_range"] = sku_long_range
    session.add_all(ctx.battery_skus.values())
    session.flush()

    session.add_all(
        [
            BatteryBatch(
                batch_number="BATCH-HYD-Q4-01",
                manufacturer="VoltEdge",
                production_date=_ts(days_ago=210),
            ),
            BatteryBatch(
                batch_number="BATCH-WGL-Q1-02",
                manufacturer="VoltEdge",
                production_date=_ts(days_ago=140),
            ),
        ]
    )

    battery_specs = [
        ("battery_001", "PF-HYD-24001", "jubilee_hills_hub", BatteryStatus.AVAILABLE, LocationType.STATION, 96.0, 92.0, "standard", "VoltEdge", 120, 120),
        ("battery_002", "PF-HYD-24002", "jubilee_hills_hub", BatteryStatus.AVAILABLE, LocationType.STATION, 94.0, 88.0, "standard", "VoltEdge", 135, 135),
        ("battery_003", "PF-HYD-24003", "jubilee_hills_hub", BatteryStatus.CHARGING, LocationType.STATION, 91.0, 54.0, "standard", "VoltEdge", 168, 168),
        ("battery_004", "PF-HYD-24004", "jubilee_hills_hub", BatteryStatus.MAINTENANCE, LocationType.STATION, 52.0, 37.0, "standard", "VoltEdge", 620, 620),
        ("battery_005", "PF-HYD-24005", "hitech_city_nexus", BatteryStatus.RENTED, LocationType.STATION, 88.0, 73.0, "long_range", "VoltEdge", 210, 210),
        ("battery_006", "PF-HYD-24006", "hitech_city_nexus", BatteryStatus.AVAILABLE, LocationType.STATION, 93.0, 87.0, "long_range", "VoltEdge", 184, 184),
        ("battery_007", "PF-HYD-24007", "hitech_city_nexus", BatteryStatus.AVAILABLE, LocationType.STATION, 89.0, 82.0, "standard", "VoltEdge", 256, 256),
        ("battery_008", "PF-HYD-24008", "hitech_city_nexus", BatteryStatus.MAINTENANCE, LocationType.STATION, 47.0, 29.0, "standard", "VoltEdge", 712, 712),
        ("battery_009", "PF-HYD-24009", "kukatpally_exchange", BatteryStatus.RENTED, LocationType.STATION, 86.0, 64.0, "long_range", "VoltEdge", 240, 240),
        ("battery_010", "PF-HYD-24010", "kukatpally_exchange", BatteryStatus.AVAILABLE, LocationType.STATION, 90.0, 85.0, "standard", "VoltEdge", 205, 205),
        ("battery_011", "PF-HYD-24011", "kukatpally_exchange", BatteryStatus.CHARGING, LocationType.STATION, 84.0, 42.0, "standard", "VoltEdge", 334, 334),
        ("battery_012", "PF-HYD-24012", "kukatpally_exchange", BatteryStatus.MAINTENANCE, LocationType.STATION, 44.0, 25.0, "standard", "VoltEdge", 805, 805),
        ("battery_013", "PF-HYD-24013", "secunderabad_central", BatteryStatus.RENTED, LocationType.STATION, 83.0, 61.0, "long_range", "VoltEdge", 278, 278),
        ("battery_014", "PF-HYD-24014", "secunderabad_central", BatteryStatus.AVAILABLE, LocationType.STATION, 87.0, 90.0, "standard", "VoltEdge", 298, 298),
        ("battery_015", "PF-HYD-24015", "secunderabad_central", BatteryStatus.AVAILABLE, LocationType.STATION, 85.0, 78.0, "standard", "VoltEdge", 322, 322),
        ("battery_016", "PF-HYD-24016", None, BatteryStatus.RETIRED, LocationType.RECYCLING, 18.0, 0.0, "standard", "VoltEdge", 1340, 1340),
        ("battery_017", "PF-HYD-24017", "uppal_transit_point", BatteryStatus.RENTED, LocationType.STATION, 79.0, 58.0, "long_range", "VoltEdge", 355, 355),
        ("battery_018", "PF-HYD-24018", "uppal_transit_point", BatteryStatus.AVAILABLE, LocationType.STATION, 82.0, 76.0, "standard", "VoltEdge", 366, 366),
        ("battery_019", "PF-HYD-24019", "uppal_transit_point", BatteryStatus.RENTED, LocationType.STATION, 31.0, 19.0, "standard", "VoltEdge", 980, 980),
        ("battery_020", "PF-HYD-24020", "uppal_transit_point", BatteryStatus.AVAILABLE, LocationType.STATION, 78.0, 74.0, "standard", "VoltEdge", 404, 404),
        ("battery_021", "PF-WGL-24021", "warangal_gateway", BatteryStatus.RENTED, LocationType.STATION, 27.0, 14.0, "standard", "VoltEdge", 1120, 1120),
        ("battery_022", "PF-WGL-24022", "warangal_gateway", BatteryStatus.AVAILABLE, LocationType.STATION, 76.0, 72.0, "standard", "VoltEdge", 448, 448),
        ("battery_023", "PF-WHS-24023", None, BatteryStatus.AVAILABLE, LocationType.WAREHOUSE, 92.0, 96.0, "long_range", "VoltEdge", 88, 88),
        ("battery_024", "PF-SVC-24024", None, BatteryStatus.MAINTENANCE, LocationType.SERVICE_CENTER, 39.0, 22.0, "long_range", "VoltEdge", 875, 875),
    ]
    for key, serial, station_key, status, location_type, health, current_charge, sku_key, manufacturer, cycle_count, total_cycles in battery_specs:
        station = ctx.stations.get(station_key) if station_key else None
        battery = Battery(
            serial_number=serial,
            qr_code_data=f"QR::{serial}",
            sku_id=ctx.battery_skus[sku_key].id,
            spec_id=ctx.battery_skus[sku_key].id,
            station_id=station.id if station else None,
            created_by=ctx.users["admin_fleet"].id,
            status=status,
            health_status=BatteryHealth.CRITICAL if health <= 30 else BatteryHealth.POOR if health <= 50 else BatteryHealth.GOOD if health <= 95 else BatteryHealth.EXCELLENT,
            current_charge=current_charge,
            health_percentage=health,
            cycle_count=cycle_count,
            total_cycles=total_cycles,
            temperature_c=28.0 if status != BatteryStatus.MAINTENANCE else 34.0,
            manufacturer=manufacturer,
            battery_type="60V/32Ah" if sku_key == "long_range" else "48V/30Ah",
            purchase_cost=33999.0 if sku_key == "long_range" else 28999.0,
            notes="Seeded showcase asset",
            location_type=location_type,
            manufacture_date=_ts(days_ago=260),
            purchase_date=_ts(days_ago=220),
            warranty_expiry=_future(days_ahead=420),
            last_charged_at=_ts(hours_ago=4 if status == BatteryStatus.CHARGING else 18),
            last_inspected_at=_ts(days_ago=7),
            last_maintenance_date=_ts(days_ago=22) if status in {BatteryStatus.MAINTENANCE, BatteryStatus.RETIRED} else _ts(days_ago=36),
            last_maintenance_cycles=max(0, cycle_count - 80),
            state_of_health=health,
            temperature_history=[26.2, 27.4, 28.1, 29.0] if status != BatteryStatus.MAINTENANCE else [30.2, 32.1, 34.5, 35.2],
            charge_cycles=cycle_count,
            location_id=station.id if station else (1 if location_type == LocationType.WAREHOUSE else 2 if location_type == LocationType.SERVICE_CENTER else 3),
            last_telemetry_at=_ts(minutes_ago=18),
            created_at=_ts(days_ago=210),
            updated_at=_ts(days_ago=1),
        )
        ctx.batteries[key] = battery
    session.add_all(ctx.batteries.values())
    session.flush()

    slot_layout = {
        "jubilee_hills_hub": ["battery_001", "battery_002", "battery_003", "battery_004", None, None],
        "hitech_city_nexus": ["battery_006", "battery_007", "battery_008", None, None, None],
        "kukatpally_exchange": ["battery_010", "battery_011", "battery_012", None, None, None],
        "secunderabad_central": ["battery_014", "battery_015", None, None, None, None],
        "uppal_transit_point": ["battery_018", "battery_020", None, None, None, None],
        "warangal_gateway": ["battery_022", None, None, None, None, None],
    }
    slots = []
    for station_key, battery_keys in slot_layout.items():
        station = ctx.stations[station_key]
        for slot_number, battery_key in enumerate(battery_keys, start=1):
            battery = ctx.batteries.get(battery_key) if battery_key else None
            slot_status = "empty"
            if battery:
                slot_status = (
                    "charging"
                    if battery.status == BatteryStatus.CHARGING
                    else "maintenance"
                    if battery.status in {BatteryStatus.MAINTENANCE, BatteryStatus.RETIRED}
                    else "ready"
                )
            slots.append(
                StationSlot(
                    station_id=station.id,
                    slot_number=slot_number,
                    status=slot_status,
                    is_locked=slot_status != "empty",
                    battery_id=battery.id if battery else None,
                    current_power_w=900.0 if slot_status == "charging" else 0.0,
                    last_heartbeat=_ts(minutes_ago=slot_number * 2),
                )
            )
    session.add_all(slots)

    device_batteries = [
        "battery_001", "battery_002", "battery_003", "battery_005", "battery_006", "battery_007",
        "battery_009", "battery_010", "battery_011", "battery_013", "battery_014", "battery_015",
        "battery_017", "battery_018", "battery_019", "battery_020", "battery_021", "battery_022",
    ]
    for index, battery_key in enumerate(device_batteries, start=1):
        battery = ctx.batteries[battery_key]
        device = IoTDevice(
            device_id=f"IOT-{battery.serial_number}",
            device_type="tracker_v2",
            firmware_version="2.4.1" if index <= 12 else "2.5.0",
            status="online" if battery.status != BatteryStatus.MAINTENANCE else "error",
            communication_protocol="mqtt",
            battery_id=battery.id,
            auth_token=f"auth-{battery.serial_number.lower()}",
            last_heartbeat=_ts(minutes_ago=index),
            last_ip_address=f"10.10.0.{index}",
            created_at=_ts(days_ago=120),
            updated_at=_ts(days_ago=1),
        )
        ctx.devices[battery_key] = device
        battery.iot_device_id = device.device_id
        session.add(device)
        session.add(battery)
    session.flush()

    session.add_all(
        [
            FirmwareUpdate(
                version="2.4.1",
                file_url="https://assets.powerfill.demo/firmware/tracker_v2_2.4.1.bin",
                checksum="sha256:seed-fw-241",
                device_type="tracker_v2",
                is_critical=False,
                created_at=_ts(days_ago=21),
            ),
            FirmwareUpdate(
                version="2.5.0",
                file_url="https://assets.powerfill.demo/firmware/tracker_v2_2.5.0.bin",
                checksum="sha256:seed-fw-250",
                device_type="tracker_v2",
                is_critical=True,
                created_at=_ts(days_ago=5),
            ),
        ]
    )

    command_specs = [
        ("battery_003", "BALANCE_CELL", "executed"),
        ("battery_005", "DIAGNOSTIC", "executed"),
        ("battery_006", "REBOOT", "acknowledged"),
        ("battery_007", "SYNC_CLOCK", "executed"),
        ("battery_009", "LOCK", "executed"),
        ("battery_010", "UNLOCK", "executed"),
        ("battery_011", "CALIBRATE_SOC", "queued"),
        ("battery_013", "DIAGNOSTIC", "executed"),
        ("battery_017", "REBOOT", "failed"),
        ("battery_018", "SYNC_CLOCK", "executed"),
        ("battery_021", "DIAGNOSTIC", "failed"),
        ("battery_022", "BALANCE_CELL", "queued"),
    ]
    session.add_all(
        [
            DeviceCommand(
                device_id=ctx.devices[battery_key].id,
                command_type=command_type,
                payload='{"source":"admin_portal"}',
                status=status,
                created_at=_ts(days_ago=index // 3, hours_ago=index),
                sent_at=_ts(days_ago=index // 3, hours_ago=index - 1) if status != "queued" else None,
                executed_at=_ts(days_ago=index // 3, hours_ago=index - 1) if status == "executed" else None,
                response_data='{"result":"ok"}' if status == "executed" else None,
            )
            for index, (battery_key, command_type, status) in enumerate(command_specs, start=1)
        ]
    )

    telemetry_rows = []
    for index, battery_key in enumerate(
        ["battery_003", "battery_005", "battery_009", "battery_011", "battery_013", "battery_017", "battery_019", "battery_021", "battery_022", "battery_023"],
        start=1,
    ):
        battery = ctx.batteries[battery_key]
        station = next((s for s in ctx.stations.values() if s.id == battery.station_id), None)
        latitude = station.latitude if station else 17.44
        longitude = station.longitude if station else 78.39
        telemetry_rows.append(
            Telemetry(
                device_id=ctx.devices[battery_key].device_id if battery_key in ctx.devices else f"IOT-{battery.serial_number}",
                battery_id=battery.id,
                rental_id=None,
                latitude=latitude + (index * 0.0004),
                longitude=longitude + (index * 0.0003),
                speed_kmph=22.0 if battery.status == BatteryStatus.RENTED else 0.0,
                voltage=52.4 if battery.status != BatteryStatus.MAINTENANCE else 47.8,
                current=12.2 if battery.status == BatteryStatus.CHARGING else 3.6,
                temperature=31.0 if battery.status == BatteryStatus.MAINTENANCE else 27.6,
                soc=battery.current_charge,
                soh=battery.health_percentage,
                range_remaining_km=max(12.0, battery.current_charge * 0.55),
                timestamp=_ts(minutes_ago=index * 6),
                metadata_json='{"cell_delta_mv": 11, "network": "4G"}',
            )
        )
    session.add_all(telemetry_rows)

    snapshot_rows = []
    history_rows = []
    critical_keys = {"battery_004", "battery_008", "battery_019", "battery_021"}
    for index, (battery_key, battery) in enumerate(ctx.batteries.items(), start=1):
        deltas = [(60, 6.0), (12, 0.0)]
        if battery_key in critical_keys:
            deltas = [(90, 12.0), (45, 7.5), (20, 3.5), (5, 0.0)]
        for days_ago, uplift in deltas:
            snapshot_rows.append(
                BatteryHealthSnapshot(
                    battery_id=battery.id,
                    health_percentage=min(100.0, battery.health_percentage + uplift),
                    voltage=54.1 if battery.status != BatteryStatus.MAINTENANCE else 49.2,
                    temperature=28.0 if battery.status != BatteryStatus.MAINTENANCE else 34.5,
                    internal_resistance=11.0 + (100 - battery.health_percentage) / 12.0,
                    charge_cycles=max(0, battery.total_cycles - days_ago // 2),
                    snapshot_type=SnapshotType.IOT_SYNC if days_ago <= 20 else SnapshotType.MANUAL,
                    recorded_by=ctx.users["admin_fleet"].id,
                    recorded_at=_ts(days_ago=days_ago, hours_ago=index % 6),
                )
            )
        history_rows.extend(
            [
                BatteryHealthHistory(
                    battery_id=battery.id,
                    health_percentage=min(100.0, battery.health_percentage + 4.0),
                    recorded_at=_ts(days_ago=75),
                ),
                BatteryHealthHistory(
                    battery_id=battery.id,
                    health_percentage=min(100.0, battery.health_percentage + 1.5),
                    recorded_at=_ts(days_ago=28),
                ),
            ]
        )
    session.add_all(snapshot_rows)
    session.add_all(history_rows)

    maintenance_schedule_rows = [
        BatteryMaintenanceSchedule(
            battery_id=ctx.batteries["battery_004"].id,
            scheduled_date=_future(days_ahead=1),
            maintenance_type=MaintenanceType.DEEP_SERVICE,
            priority=MaintenancePriority.HIGH,
            assigned_to=ctx.users["field_officer"].id,
            status=MaintenanceStatus.SCHEDULED,
            notes="Thermal sensor and weld inspection before redeployment.",
            health_before=52.0,
            created_by=ctx.users["admin_fleet"].id,
            created_at=_ts(days_ago=1),
        ),
        BatteryMaintenanceSchedule(
            battery_id=ctx.batteries["battery_008"].id,
            scheduled_date=_ts(days_ago=3),
            maintenance_type=MaintenanceType.REPLACEMENT,
            priority=MaintenancePriority.CRITICAL,
            assigned_to=ctx.users["field_officer"].id,
            status=MaintenanceStatus.OVERDUE,
            notes="Cell-bank variance remained above safe threshold.",
            health_before=47.0,
            created_by=ctx.users["admin_fleet"].id,
            created_at=_ts(days_ago=7),
        ),
        BatteryMaintenanceSchedule(
            battery_id=ctx.batteries["battery_012"].id,
            scheduled_date=_ts(days_ago=8),
            maintenance_type=MaintenanceType.CALIBRATION,
            priority=MaintenancePriority.MEDIUM,
            assigned_to=ctx.users["field_officer"].id,
            status=MaintenanceStatus.COMPLETED,
            notes="SOC calibration completed after inconsistent telemetry.",
            health_before=46.0,
            health_after=50.0,
            completed_at=_ts(days_ago=7),
            created_by=ctx.users["admin_fleet"].id,
            created_at=_ts(days_ago=10),
        ),
        BatteryMaintenanceSchedule(
            battery_id=ctx.batteries["battery_019"].id,
            scheduled_date=_future(days_ahead=2),
            maintenance_type=MaintenanceType.INSPECTION,
            priority=MaintenancePriority.CRITICAL,
            assigned_to=ctx.users["field_officer"].id,
            status=MaintenanceStatus.SCHEDULED,
            notes="Overdue rental return expected with abnormal discharge profile.",
            health_before=31.0,
            created_by=ctx.users["admin_fleet"].id,
            created_at=_ts(hours_ago=18),
        ),
        BatteryMaintenanceSchedule(
            battery_id=ctx.batteries["battery_021"].id,
            scheduled_date=_future(days_ahead=1),
            maintenance_type=MaintenanceType.REPLACEMENT,
            priority=MaintenancePriority.CRITICAL,
            assigned_to=ctx.users["field_officer"].id,
            status=MaintenanceStatus.SCHEDULED,
            notes="Prepare replacement after franchise recovery sweep.",
            health_before=27.0,
            created_by=ctx.users["admin_fleet"].id,
            created_at=_ts(hours_ago=12),
        ),
        BatteryMaintenanceSchedule(
            battery_id=ctx.batteries["battery_024"].id,
            scheduled_date=_ts(days_ago=14),
            maintenance_type=MaintenanceType.DEEP_SERVICE,
            priority=MaintenancePriority.HIGH,
            assigned_to=ctx.users["field_officer"].id,
            status=MaintenanceStatus.COMPLETED,
            notes="Service-center restoration and balancing cycle completed.",
            health_before=35.0,
            health_after=39.0,
            completed_at=_ts(days_ago=12),
            created_by=ctx.users["admin_fleet"].id,
            created_at=_ts(days_ago=16),
        ),
    ]
    session.add_all(maintenance_schedule_rows)

    session.add_all(
        [
            BatteryHealthAlert(
                battery_id=ctx.batteries["battery_019"].id,
                alert_type=AlertType.RAPID_DEGRADATION,
                severity=AlertSeverity.WARNING,
                message="Battery health dropped sharply while on a long-running rental.",
                created_at=_ts(hours_ago=9),
            ),
            BatteryHealthAlert(
                battery_id=ctx.batteries["battery_021"].id,
                alert_type=AlertType.CRITICAL_HEALTH,
                severity=AlertSeverity.CRITICAL,
                message="Battery health is below safe operating threshold.",
                created_at=_ts(hours_ago=4),
            ),
            BatteryHealthAlert(
                battery_id=ctx.batteries["battery_008"].id,
                alert_type=AlertType.HIGH_TEMP,
                severity=AlertSeverity.WARNING,
                message="Repeated high-temperature readings during charge cycle.",
                created_at=_ts(days_ago=1),
            ),
            BatteryHealthAlert(
                battery_id=ctx.batteries["battery_004"].id,
                alert_type=AlertType.OVERDUE_SERVICE,
                severity=AlertSeverity.INFO,
                message="Service window exceeded by 48 hours.",
                is_resolved=True,
                resolved_by=ctx.users["admin_fleet"].id,
                resolved_at=_ts(hours_ago=2),
                resolution_reason="Maintenance ticket converted into scheduled deep service.",
                created_at=_ts(days_ago=2),
            ),
            BatteryHealthAlert(
                battery_id=ctx.batteries["battery_016"].id,
                alert_type=AlertType.WARRANTY_EXPIRY,
                severity=AlertSeverity.INFO,
                message="Retired asset warranty expired after storage review.",
                is_resolved=True,
                resolved_by=ctx.users["admin_risk"].id,
                resolved_at=_ts(days_ago=20),
                resolution_reason="Asset retired and moved to recycling workflow.",
                created_at=_ts(days_ago=24),
            ),
            BatteryHealthAlert(
                battery_id=ctx.batteries["battery_024"].id,
                alert_type=AlertType.CRITICAL_HEALTH,
                severity=AlertSeverity.CRITICAL,
                message="Service-center asset waiting for post-repair validation.",
                created_at=_ts(days_ago=3),
            ),
        ]
    )

    session.add_all(
        [
            BatteryAuditLog(
                battery_id=battery.id,
                changed_by=ctx.users["admin_fleet"].id,
                field_changed="health_percentage",
                old_value=str(min(100.0, battery.health_percentage + 2.5)),
                new_value=str(battery.health_percentage),
                reason="Periodic inspection sync",
                timestamp=_ts(days_ago=(index % 7) + 1),
            )
            for index, battery in enumerate(ctx.batteries.values(), start=1)
        ]
    )

    session.add_all(
        [
            BatteryLifecycleEvent(
                battery_id=battery.id,
                event_type="commissioned" if battery.status != BatteryStatus.RETIRED else "retired",
                description="Battery introduced into operational fleet." if battery.status != BatteryStatus.RETIRED else "Battery retired after lifecycle threshold breach.",
                actor_id=ctx.users["admin_fleet"].id,
                timestamp=_ts(days_ago=120 - index),
            )
            for index, battery in enumerate(ctx.batteries.values(), start=1)
        ]
    )

    inventory_logs = [
        ("battery_005", "transfer", "station", ctx.stations["hitech_city_nexus"].id, "user", ctx.users["customer_1"].id, "Issued to active rental."),
        ("battery_009", "transfer", "station", ctx.stations["kukatpally_exchange"].id, "user", ctx.users["customer_2"].id, "Issued to active rental."),
        ("battery_013", "transfer", "station", ctx.stations["secunderabad_central"].id, "user", ctx.users["customer_3"].id, "Issued to active rental."),
        ("battery_017", "transfer", "station", ctx.stations["uppal_transit_point"].id, "user", ctx.users["customer_4"].id, "Issued to active rental."),
        ("battery_019", "status_change", "station", ctx.stations["uppal_transit_point"].id, "station", ctx.stations["uppal_transit_point"].id, "Marked high-risk while rental remained overdue."),
        ("battery_021", "status_change", "station", ctx.stations["warangal_gateway"].id, "station", ctx.stations["warangal_gateway"].id, "Escalated to critical health watch."),
        ("battery_023", "manual_entry", "warehouse", 1, "warehouse", 1, "Warehouse cycle count corrected after receiving note."),
        ("battery_024", "transfer", "station", ctx.stations["warangal_gateway"].id, "service_center", 2, "Moved to service center for repair."),
        ("battery_016", "disposal", "station", ctx.stations["secunderabad_central"].id, "recycling", 3, "Retired after repeated service-center failures."),
        ("battery_004", "manual_entry", "station", ctx.stations["jubilee_hills_hub"].id, "station", ctx.stations["jubilee_hills_hub"].id, "Inspection note added for thermal variance."),
        ("battery_008", "transfer", "station", ctx.stations["hitech_city_nexus"].id, "service_center", 2, "Sent for advanced diagnostics."),
        ("battery_012", "status_change", "station", ctx.stations["kukatpally_exchange"].id, "station", ctx.stations["kukatpally_exchange"].id, "Returned to maintenance queue pending calibration."),
    ]
    session.add_all(
        [
            InventoryAuditLog(
                battery_id=ctx.batteries[battery_key].id,
                action_type=action_type,
                from_location_type=from_type,
                from_location_id=from_id,
                to_location_type=to_type,
                to_location_id=to_id,
                actor_id=ctx.users["admin_fleet"].id,
                notes=notes,
                timestamp=_ts(days_ago=index // 2, hours_ago=index),
            )
            for index, (battery_key, action_type, from_type, from_id, to_type, to_id, notes) in enumerate(inventory_logs, start=1)
        ]
    )

    session.add_all(
        [
            MaintenanceRecord(
                entity_type="battery",
                entity_id=ctx.batteries["battery_008"].id,
                technician_id=ctx.users["field_officer"].id,
                maintenance_type="diagnostic",
                description="Thermal runaway prevention inspection after repeated alerts.",
                cost=1650.0,
                status="completed",
                performed_at=_ts(days_ago=3),
            ),
            MaintenanceRecord(
                entity_type="battery",
                entity_id=ctx.batteries["battery_012"].id,
                technician_id=ctx.users["field_officer"].id,
                maintenance_type="calibration",
                description="Charge estimator recalibration and BMS reset.",
                cost=1250.0,
                status="completed",
                performed_at=_ts(days_ago=7),
            ),
            MaintenanceRecord(
                entity_type="battery",
                entity_id=ctx.batteries["battery_024"].id,
                technician_id=ctx.users["field_officer"].id,
                maintenance_type="deep_service",
                description="Service-center repair batch for low-voltage pack.",
                cost=5400.0,
                status="completed",
                performed_at=_ts(days_ago=12),
            ),
        ]
    )

    session.add_all(
        [
            BatteryReservation(
                user_id=ctx.users["customer_7"].id,
                station_id=ctx.stations["jubilee_hills_hub"].id,
                battery_id=ctx.batteries["battery_001"].id,
                start_time=_future(hours_ahead=2),
                end_time=_future(hours_ahead=3),
                status="PENDING",
                created_at=_ts(hours_ago=2),
                updated_at=_ts(hours_ago=2),
            ),
            BatteryReservation(
                user_id=ctx.users["customer_8"].id,
                station_id=ctx.stations["warangal_gateway"].id,
                battery_id=ctx.batteries["battery_022"].id,
                start_time=_future(days_ahead=1, hours_ahead=1),
                end_time=_future(days_ahead=1, hours_ahead=2),
                status="PENDING",
                created_at=_ts(hours_ago=1),
                updated_at=_ts(hours_ago=1),
            ),
        ]
    )

    session.flush()


def seed_rentals_and_finance(session: Session, ctx: SeedContext) -> None:
    from app.models.battery import BatteryStatus
    from app.models.chargeback import Chargeback
    from app.models.commission import CommissionLog
    from app.models.financial import Transaction, TransactionStatus, TransactionType, WalletWithdrawalRequest
    from app.models.invoice import Invoice
    from app.models.late_fee import LateFee, LateFeeWaiver
    from app.models.payment import PaymentTransaction
    from app.models.refund import Refund
    from app.models.rental import Purchase, Rental, RentalStatus
    from app.models.rental_event import RentalEvent
    from app.models.rental_modification import RentalExtension, RentalPause
    from app.models.settlement import Settlement
    from app.models.settlement_dispute import SettlementDispute
    from app.models.swap import SwapSession
    from app.models.swap_suggestion import SwapPreference, SwapSuggestion

    rental_specs = [
        ("rental_active_1", "customer_1", "battery_005", "hitech_city_nexus", None, RentalStatus.ACTIVE, _ts(days_ago=1, hours_ago=8), _future(hours_ahead=6), None, 179.0, 1499.0, 0.0),
        ("rental_active_2", "customer_2", "battery_009", "kukatpally_exchange", None, RentalStatus.ACTIVE, _ts(days_ago=2, hours_ago=4), _future(hours_ahead=4), None, 209.0, 1499.0, 0.0),
        ("rental_active_3", "customer_3", "battery_013", "secunderabad_central", None, RentalStatus.ACTIVE, _ts(days_ago=3, hours_ago=1), _future(hours_ahead=10), None, 219.0, 1499.0, 0.0),
        ("rental_active_4", "customer_4", "battery_017", "uppal_transit_point", None, RentalStatus.ACTIVE, _ts(hours_ago=10), _future(hours_ahead=12), None, 229.0, 1499.0, 0.0),
        ("rental_overdue_1", "customer_5", "battery_019", "uppal_transit_point", None, RentalStatus.OVERDUE, _ts(days_ago=4), _ts(days_ago=1, hours_ago=4), None, 780.0, 1499.0, 120.0),
        ("rental_overdue_2", "customer_6", "battery_021", "warangal_gateway", None, RentalStatus.OVERDUE, _ts(days_ago=5), _ts(days_ago=2, hours_ago=2), None, 950.0, 1499.0, 180.0),
        ("rental_completed_1", "customer_1", "battery_001", "jubilee_hills_hub", "jubilee_hills_hub", RentalStatus.COMPLETED, _ts(days_ago=18), _ts(days_ago=17, hours_ago=12), _ts(days_ago=17, hours_ago=10), 189.0, 1499.0, 0.0),
        ("rental_completed_2", "customer_7", "battery_006", "hitech_city_nexus", "hitech_city_nexus", RentalStatus.COMPLETED, _ts(days_ago=26), _ts(days_ago=25, hours_ago=10), _ts(days_ago=25, hours_ago=8), 209.0, 1499.0, 0.0),
        ("rental_completed_3", "customer_8", "battery_010", "kukatpally_exchange", "jubilee_hills_hub", RentalStatus.COMPLETED, _ts(days_ago=34), _ts(days_ago=33, hours_ago=11), _ts(days_ago=33, hours_ago=9), 219.0, 1499.0, 0.0),
        ("rental_completed_4", "customer_10", "battery_014", "secunderabad_central", "uppal_transit_point", RentalStatus.COMPLETED, _ts(days_ago=44), _ts(days_ago=43, hours_ago=12), _ts(days_ago=43, hours_ago=9), 229.0, 1499.0, 35.0),
        ("rental_cancelled_1", "customer_9", "battery_018", "uppal_transit_point", "uppal_transit_point", RentalStatus.CANCELLED, _ts(days_ago=12), _ts(days_ago=12, hours_ago=1), _ts(days_ago=12, hours_ago=1), 0.0, 0.0, 0.0),
        ("rental_cancelled_2", "customer_3", "battery_022", "warangal_gateway", "warangal_gateway", RentalStatus.CANCELLED, _ts(days_ago=52), _ts(days_ago=52, hours_ago=2), _ts(days_ago=52, hours_ago=2), 0.0, 0.0, 0.0),
    ]
    for key, user_key, battery_key, start_station_key, end_station_key, status, start_time, expected_end_time, end_time, total_amount, deposit, late_fee in rental_specs:
        rental = Rental(
            user_id=ctx.users[user_key].id,
            battery_id=ctx.batteries[battery_key].id,
            start_station_id=ctx.stations[start_station_key].id,
            end_station_id=ctx.stations[end_station_key].id if end_station_key else None,
            start_time=start_time,
            expected_end_time=expected_end_time,
            end_time=end_time,
            total_amount=total_amount,
            security_deposit=deposit,
            late_fee=late_fee,
            is_deposit_refunded=status in {RentalStatus.COMPLETED, RentalStatus.CANCELLED},
            status=status,
            start_battery_level=ctx.batteries[battery_key].current_charge,
            end_battery_level=max(8.0, ctx.batteries[battery_key].current_charge - 34) if end_time else 0.0,
            distance_traveled_km=18.4 if status in {RentalStatus.ACTIVE, RentalStatus.OVERDUE} else 26.7,
            created_at=start_time,
            updated_at=end_time or _ts(hours_ago=2),
        )
        ctx.rentals[key] = rental
    session.add_all(ctx.rentals.values())
    session.flush()

    for rental_key, rental in ctx.rentals.items():
        battery = next(b for b in ctx.batteries.values() if b.id == rental.battery_id)
        if rental.status in {RentalStatus.ACTIVE, RentalStatus.OVERDUE}:
            battery.current_user_id = rental.user_id
            battery.status = BatteryStatus.RENTED
        else:
            battery.current_user_id = None
        session.add(battery)

    rental_events = []
    for rental_key, rental in ctx.rentals.items():
        rental_events.append(
            RentalEvent(
                rental_id=rental.id,
                event_type="started",
                description="Battery issued to rider.",
                station_id=rental.start_station_id,
                battery_id=rental.battery_id,
                created_at=rental.created_at,
            )
        )
        if rental.status == RentalStatus.OVERDUE:
            rental_events.append(
                RentalEvent(
                    rental_id=rental.id,
                    event_type="overdue",
                    description="Rental crossed expected return window.",
                    station_id=rental.start_station_id,
                    battery_id=rental.battery_id,
                    created_at=_ts(hours_ago=8),
                )
            )
        elif rental.status == RentalStatus.COMPLETED:
            rental_events.append(
                RentalEvent(
                    rental_id=rental.id,
                    event_type="completed",
                    description="Battery returned and rental closed.",
                    station_id=rental.end_station_id,
                    battery_id=rental.battery_id,
                    created_at=rental.end_time,
                )
            )
        elif rental.status == RentalStatus.CANCELLED:
            rental_events.append(
                RentalEvent(
                    rental_id=rental.id,
                    event_type="cancelled",
                    description="Rental cancelled before meaningful usage began.",
                    station_id=rental.end_station_id,
                    battery_id=rental.battery_id,
                    created_at=rental.end_time,
                )
            )
    session.add_all(rental_events)

    session.add(
        RentalExtension(
            rental_id=ctx.rentals["rental_active_2"].id,
            user_id=ctx.users["customer_2"].id,
            current_end_date=ctx.rentals["rental_active_2"].expected_end_time,
            requested_end_date=ctx.rentals["rental_active_2"].expected_end_time + timedelta(days=1),
            extension_days=1,
            status="PENDING",
            additional_cost=129.0,
            payment_status="PENDING",
            reason="Outstation ride extended overnight",
            created_at=_ts(hours_ago=5),
            updated_at=_ts(hours_ago=5),
        )
    )
    session.add(
        RentalPause(
            rental_id=ctx.rentals["rental_active_3"].id,
            user_id=ctx.users["customer_3"].id,
            pause_start_date=_future(days_ahead=1),
            pause_end_date=_future(days_ahead=3),
            pause_days=2,
            status="APPROVED",
            reason="Vehicle under workshop repair",
            daily_pause_charge=49.0,
            total_pause_cost=98.0,
            admin_notes="Approved after workshop invoice upload",
            approved_by=ctx.users["admin_support"].id,
            approved_at=_ts(hours_ago=7),
            created_at=_ts(days_ago=1),
            updated_at=_ts(hours_ago=7),
        )
    )

    session.add_all(
        [
            Purchase(
                user_id=ctx.users["customer_2"].id,
                battery_id=ctx.batteries["battery_023"].id,
                amount=16250.0,
                timestamp=_ts(days_ago=15),
            ),
            Purchase(
                user_id=ctx.users["dealer_owner_1"].id,
                battery_id=ctx.batteries["battery_016"].id,
                amount=4800.0,
                timestamp=_ts(days_ago=32),
            ),
        ]
    )

    session.add_all(
        [
            SwapPreference(
                user_id=ctx.users["customer_1"].id,
                prefer_nearby=9,
                prefer_fast_charging=7,
                prefer_high_rated=8,
                prefer_low_wait=9,
                favorite_station_ids='[1,2]',
                max_acceptable_distance_km=5.0,
                notify_when_battery_below=25,
                updated_at=_ts(days_ago=2),
            ),
            SwapPreference(
                user_id=ctx.users["customer_2"].id,
                prefer_nearby=8,
                prefer_fast_charging=8,
                prefer_high_rated=7,
                prefer_low_wait=8,
                favorite_station_ids='[2,3]',
                max_acceptable_distance_km=7.5,
                notify_when_battery_below=22,
                updated_at=_ts(days_ago=4),
            ),
            SwapPreference(
                user_id=ctx.users["customer_5"].id,
                prefer_nearby=10,
                prefer_fast_charging=4,
                prefer_high_rated=6,
                prefer_low_wait=10,
                favorite_station_ids='[5]',
                max_acceptable_distance_km=4.0,
                notify_when_battery_below=18,
                updated_at=_ts(days_ago=1),
            ),
        ]
    )

    swap_specs = [
        ("swap_1", "rental_active_1", "customer_1", "jubilee_hills_hub", "battery_005", "battery_002", 24.0, 94.0, 49.0, "completed", _ts(days_ago=1, hours_ago=2), _ts(days_ago=1, hours_ago=2)),
        ("swap_2", "rental_overdue_1", "customer_5", "uppal_transit_point", "battery_019", "battery_018", 21.0, 82.0, 59.0, "completed", _ts(days_ago=2, hours_ago=6), _ts(days_ago=2, hours_ago=5)),
        ("swap_3", "rental_completed_2", "customer_7", "hitech_city_nexus", "battery_006", "battery_007", 31.0, 91.0, 39.0, "completed", _ts(days_ago=25, hours_ago=2), _ts(days_ago=25, hours_ago=2)),
        ("swap_4", "rental_active_4", "customer_4", "uppal_transit_point", "battery_017", "battery_020", 27.0, 79.0, 0.0, "initiated", _ts(hours_ago=4), None),
    ]
    swap_rows = []
    for key, rental_key, user_key, station_key, old_battery_key, new_battery_key, old_soc, new_soc, amount, status, created_at, completed_at in swap_specs:
        swap = SwapSession(
            rental_id=ctx.rentals[rental_key].id,
            user_id=ctx.users[user_key].id,
            station_id=ctx.stations[station_key].id,
            old_battery_id=ctx.batteries[old_battery_key].id,
            new_battery_id=ctx.batteries[new_battery_key].id,
            old_battery_soc=old_soc,
            new_battery_soc=new_soc,
            swap_amount=amount,
            status=status,
            payment_status="paid" if amount > 0 and status == "completed" else "pending",
            created_at=created_at,
            completed_at=completed_at,
        )
        ctx.swaps[key] = swap
        swap_rows.append(swap)
    session.add_all(swap_rows)
    session.flush()

    session.add_all(
        [
            SwapSuggestion(
                user_id=ctx.users["customer_1"].id,
                rental_id=ctx.rentals["rental_active_1"].id,
                current_battery_soc=24.0,
                current_location_lat=17.4320,
                current_location_lng=78.4080,
                suggested_station_id=ctx.stations["jubilee_hills_hub"].id,
                priority_rank=1,
                distance_km=1.4,
                estimated_travel_time_minutes=6,
                station_availability_score=9.1,
                station_rating=4.6,
                predicted_wait_time_minutes=2,
                predicted_battery_availability=6,
                preference_match_score=9.0,
                total_score=92.0,
                was_accepted=True,
                accepted_at=_ts(days_ago=1, hours_ago=2),
                created_at=_ts(days_ago=1, hours_ago=3),
            ),
            SwapSuggestion(
                user_id=ctx.users["customer_2"].id,
                rental_id=ctx.rentals["rental_active_2"].id,
                current_battery_soc=29.0,
                current_location_lat=17.4938,
                current_location_lng=78.3989,
                suggested_station_id=ctx.stations["kukatpally_exchange"].id,
                priority_rank=1,
                distance_km=1.2,
                estimated_travel_time_minutes=5,
                station_availability_score=8.6,
                station_rating=4.3,
                predicted_wait_time_minutes=3,
                predicted_battery_availability=4,
                preference_match_score=8.4,
                total_score=87.0,
                was_accepted=None,
                created_at=_ts(days_ago=1),
            ),
            SwapSuggestion(
                user_id=ctx.users["customer_5"].id,
                rental_id=ctx.rentals["rental_overdue_1"].id,
                current_battery_soc=17.0,
                current_location_lat=17.4061,
                current_location_lng=78.5585,
                suggested_station_id=ctx.stations["uppal_transit_point"].id,
                priority_rank=1,
                distance_km=0.9,
                estimated_travel_time_minutes=4,
                station_availability_score=7.8,
                station_rating=4.2,
                predicted_wait_time_minutes=4,
                predicted_battery_availability=2,
                preference_match_score=9.5,
                total_score=89.0,
                was_accepted=False,
                created_at=_ts(hours_ago=7),
            ),
            SwapSuggestion(
                user_id=ctx.users["customer_6"].id,
                rental_id=ctx.rentals["rental_overdue_2"].id,
                current_battery_soc=12.0,
                current_location_lat=17.9929,
                current_location_lng=79.5668,
                suggested_station_id=ctx.stations["warangal_gateway"].id,
                priority_rank=1,
                distance_km=2.3,
                estimated_travel_time_minutes=7,
                station_availability_score=6.9,
                station_rating=4.1,
                predicted_wait_time_minutes=5,
                predicted_battery_availability=1,
                preference_match_score=8.9,
                total_score=81.0,
                was_accepted=None,
                created_at=_ts(hours_ago=5),
            ),
        ]
    )

    payment_specs = [
        ("pay_topup_1", "customer_5", 500.0, "success", "upi", _ts(days_ago=7)),
        ("pay_topup_2", "customer_6", 750.0, "success", "upi", _ts(days_ago=9)),
        ("pay_purchase_1", "customer_2", 16250.0, "success", "card", _ts(days_ago=15)),
        ("pay_deposit_4", "customer_4", 1499.0, "success", "upi", _ts(days_ago=1)),
        ("pay_failed_swap", "customer_6", 59.0, "failed", "upi", _ts(hours_ago=11)),
    ]
    for key, user_key, amount, status, method, created_at in payment_specs:
        payment = PaymentTransaction(
            user_id=ctx.users[user_key].id,
            amount=amount,
            status=status,
            payment_method=method,
            razorpay_order_id=f"order_{key}",
            razorpay_payment_id=f"pay_{key}",
            razorpay_signature=f"sig_{key}",
            created_at=created_at,
            updated_at=created_at,
        )
        ctx.payment_transactions[key] = payment
    session.add_all(ctx.payment_transactions.values())
    session.flush()

    transaction_specs = [
        ("txn_completed_1", "customer_1", "rental_completed_1", 189.0, 160.17, 28.83, TransactionType.RENTAL_PAYMENT, TransactionStatus.SUCCESS, "wallet", _ts(days_ago=17)),
        ("txn_completed_2", "customer_7", "rental_completed_2", 209.0, 177.12, 31.88, TransactionType.RENTAL_PAYMENT, TransactionStatus.SUCCESS, "upi", _ts(days_ago=25)),
        ("txn_completed_3", "customer_8", "rental_completed_3", 219.0, 185.59, 33.41, TransactionType.RENTAL_PAYMENT, TransactionStatus.SUCCESS, "upi", _ts(days_ago=33)),
        ("txn_completed_4", "customer_10", "rental_completed_4", 229.0, 194.07, 34.93, TransactionType.RENTAL_PAYMENT, TransactionStatus.SUCCESS, "card", _ts(days_ago=43)),
        ("txn_deposit_1", "customer_1", "rental_active_1", 1499.0, 1499.0, 0.0, TransactionType.SECURITY_DEPOSIT, TransactionStatus.SUCCESS, "upi", _ts(days_ago=2)),
        ("txn_rental_1", "customer_1", "rental_active_1", 179.0, 151.69, 27.31, TransactionType.RENTAL_PAYMENT, TransactionStatus.SUCCESS, "wallet", _ts(days_ago=1)),
        ("txn_deposit_2", "customer_2", "rental_active_2", 1499.0, 1499.0, 0.0, TransactionType.SECURITY_DEPOSIT, TransactionStatus.SUCCESS, "upi", _ts(days_ago=3)),
        ("txn_rental_2", "customer_2", "rental_active_2", 209.0, 177.12, 31.88, TransactionType.RENTAL_PAYMENT, TransactionStatus.SUCCESS, "upi", _ts(days_ago=2)),
        ("txn_deposit_3", "customer_3", "rental_active_3", 1499.0, 1499.0, 0.0, TransactionType.SECURITY_DEPOSIT, TransactionStatus.SUCCESS, "card", _ts(days_ago=4)),
        ("txn_rental_3", "customer_3", "rental_active_3", 219.0, 185.59, 33.41, TransactionType.RENTAL_PAYMENT, TransactionStatus.SUCCESS, "wallet", _ts(days_ago=3)),
        ("txn_deposit_4", "customer_4", "rental_active_4", 1499.0, 1499.0, 0.0, TransactionType.SECURITY_DEPOSIT, TransactionStatus.SUCCESS, "upi", _ts(days_ago=1)),
        ("txn_rental_4", "customer_4", "rental_active_4", 229.0, 194.07, 34.93, TransactionType.RENTAL_PAYMENT, TransactionStatus.PENDING, "upi", _ts(hours_ago=12)),
        ("txn_deposit_5", "customer_5", "rental_overdue_1", 1499.0, 1499.0, 0.0, TransactionType.SECURITY_DEPOSIT, TransactionStatus.SUCCESS, "wallet", _ts(days_ago=5)),
        ("txn_late_fee_1", "customer_5", "rental_overdue_1", 120.0, 101.69, 18.31, TransactionType.LATE_FEE, TransactionStatus.PENDING, "wallet", _ts(hours_ago=6)),
        ("txn_deposit_6", "customer_6", "rental_overdue_2", 1499.0, 1499.0, 0.0, TransactionType.SECURITY_DEPOSIT, TransactionStatus.SUCCESS, "upi", _ts(days_ago=6)),
        ("txn_late_fee_2", "customer_6", "rental_overdue_2", 180.0, 152.54, 27.46, TransactionType.LATE_FEE, TransactionStatus.PENDING, "upi", _ts(hours_ago=5)),
        ("txn_topup_1", "customer_5", None, 500.0, 500.0, 0.0, TransactionType.WALLET_TOPUP, TransactionStatus.SUCCESS, "upi", _ts(days_ago=7)),
        ("txn_topup_2", "customer_6", None, 750.0, 750.0, 0.0, TransactionType.WALLET_TOPUP, TransactionStatus.SUCCESS, "upi", _ts(days_ago=9)),
        ("txn_swap_1", "customer_1", "rental_active_1", 49.0, 41.53, 7.47, TransactionType.SWAP_FEE, TransactionStatus.SUCCESS, "wallet", _ts(days_ago=1)),
        ("txn_swap_2", "customer_5", "rental_overdue_1", 59.0, 50.00, 9.00, TransactionType.SWAP_FEE, TransactionStatus.SUCCESS, "upi", _ts(days_ago=2)),
        ("txn_purchase_1", "customer_2", None, 16250.0, 13771.19, 2478.81, TransactionType.PURCHASE, TransactionStatus.SUCCESS, "card", _ts(days_ago=15)),
        ("txn_refund_1", "customer_9", None, 189.0, 160.17, 28.83, TransactionType.REFUND, TransactionStatus.REFUNDED, "upi", _ts(days_ago=11)),
    ]
    for key, user_key, rental_key, amount, subtotal, tax_amount, transaction_type, status, method, created_at in transaction_specs:
        transaction = Transaction(
            user_id=ctx.users[user_key].id,
            rental_id=ctx.rentals[rental_key].id if rental_key else None,
            wallet_id=ctx.wallets[user_key].id if user_key in ctx.wallets else None,
            amount=amount,
            tax_amount=tax_amount,
            subtotal=subtotal,
            currency="INR",
            transaction_type=transaction_type,
            status=status,
            payment_method=method,
            payment_gateway_ref=f"gw_{key}",
            description=f"Seeded {transaction_type.value.lower()} transaction",
            created_at=created_at,
            updated_at=created_at,
        )
        ctx.transactions[key] = transaction
    session.add_all([value for value in ctx.transactions.values() if isinstance(value, Transaction)])
    session.flush()

    invoice_specs = [
        ("INV-2026-0401", "customer_1", "txn_completed_1", False),
        ("INV-2026-0402", "customer_7", "txn_completed_2", False),
        ("INV-2026-0403", "customer_8", "txn_completed_3", False),
        ("INV-2026-0404", "customer_10", "txn_completed_4", False),
        ("INV-2026-0405", "customer_1", "txn_rental_1", False),
        ("INV-2026-0406", "customer_2", "txn_rental_2", False),
        ("INV-2026-0407", "customer_3", "txn_rental_3", False),
        ("INV-2026-0408", "customer_5", "txn_late_fee_1", True),
        ("INV-2026-0409", "customer_6", "txn_late_fee_2", True),
        ("INV-2026-0410", "customer_2", "txn_purchase_1", False),
        ("INV-2026-0411", "customer_5", "txn_swap_2", False),
        ("INV-2026-0412", "customer_1", "txn_swap_1", False),
    ]
    for invoice_number, user_key, txn_key, is_late_fee in invoice_specs:
        transaction = ctx.transactions[txn_key]
        invoice = Invoice(
            user_id=ctx.users[user_key].id,
            transaction_id=transaction.id,
            invoice_number=invoice_number,
            amount=transaction.amount,
            subtotal=transaction.subtotal,
            tax_amount=transaction.tax_amount,
            total=transaction.amount,
            gstin="36AAACP1234A1Z5",
            hsn_code="85076000",
            is_late_fee=is_late_fee,
            pdf_url=f"https://assets.powerfill.demo/invoices/{invoice_number}.pdf",
            created_at=transaction.created_at,
        )
        ctx.invoices[invoice_number] = invoice
    session.add_all(ctx.invoices.values())
    session.flush()

    late_fee_rows = [
        LateFee(
            rental_id=ctx.rentals["rental_overdue_1"].id,
            user_id=ctx.users["customer_5"].id,
            original_end_date=ctx.rentals["rental_overdue_1"].expected_end_time,
            actual_return_date=None,
            days_overdue=1,
            daily_late_fee_rate=120.0,
            base_late_fee=120.0,
            progressive_penalty=0.0,
            total_late_fee=120.0,
            amount_paid=0.0,
            amount_waived=0.0,
            amount_outstanding=120.0,
            payment_status="PENDING",
            invoice_id=ctx.invoices["INV-2026-0408"].id,
            invoice_generated_at=_ts(hours_ago=6),
            created_at=_ts(hours_ago=6),
            updated_at=_ts(hours_ago=6),
        ),
        LateFee(
            rental_id=ctx.rentals["rental_overdue_2"].id,
            user_id=ctx.users["customer_6"].id,
            original_end_date=ctx.rentals["rental_overdue_2"].expected_end_time,
            actual_return_date=None,
            days_overdue=2,
            daily_late_fee_rate=90.0,
            base_late_fee=180.0,
            progressive_penalty=20.0,
            total_late_fee=200.0,
            amount_paid=0.0,
            amount_waived=0.0,
            amount_outstanding=200.0,
            payment_status="PENDING",
            invoice_id=ctx.invoices["INV-2026-0409"].id,
            invoice_generated_at=_ts(hours_ago=5),
            created_at=_ts(hours_ago=5),
            updated_at=_ts(hours_ago=5),
        ),
        LateFee(
            rental_id=ctx.rentals["rental_completed_4"].id,
            user_id=ctx.users["customer_10"].id,
            original_end_date=ctx.rentals["rental_completed_4"].expected_end_time,
            actual_return_date=ctx.rentals["rental_completed_4"].end_time,
            days_overdue=1,
            daily_late_fee_rate=35.0,
            base_late_fee=35.0,
            progressive_penalty=0.0,
            total_late_fee=35.0,
            amount_paid=0.0,
            amount_waived=15.0,
            amount_outstanding=20.0,
            payment_status="PARTIAL",
            created_at=_ts(days_ago=43, hours_ago=9),
            updated_at=_ts(days_ago=42),
        ),
    ]
    for row in late_fee_rows:
        ctx.late_fees[f"late_fee_{len(ctx.late_fees) + 1}"] = row
    session.add_all(late_fee_rows)
    session.flush()

    session.add_all(
        [
            LateFeeWaiver(
                late_fee_id=late_fee_rows[0].id,
                user_id=ctx.users["customer_5"].id,
                requested_waiver_amount=40.0,
                reason="Metro construction lane closure delayed return path",
                status="PENDING",
                created_at=_ts(hours_ago=3),
            ),
            LateFeeWaiver(
                late_fee_id=late_fee_rows[2].id,
                user_id=ctx.users["customer_10"].id,
                requested_waiver_amount=15.0,
                requested_waiver_percentage=42.8,
                reason="Payment gateway failed during return flow",
                status="APPROVED",
                approved_waiver_amount=15.0,
                reviewed_by=ctx.users["admin_finance"].id,
                reviewed_at=_ts(days_ago=42),
                admin_notes="Good customer history, waived one-time penalty",
                created_at=_ts(days_ago=43),
            ),
        ]
    )

    settlements = [
        (
            "settlement_metro_mar",
            Settlement(
                dealer_id=ctx.dealers["metro_energy"].id,
                settlement_month="2026-03",
                start_date=_ts(days_ago=32),
                end_date=_ts(days_ago=1),
                due_date=_future(days_ahead=5),
                total_revenue=6240.0,
                total_commission=530.0,
                chargeback_amount=0.0,
                platform_fee=42.0,
                tax_amount=19.0,
                net_payable=469.0,
                status="paid",
                transaction_reference="SET-METRO-2026-03",
                payment_proof_url="https://assets.powerfill.demo/settlements/metro-mar.pdf",
                created_at=_ts(days_ago=1),
                paid_at=_ts(hours_ago=10),
            ),
        ),
        (
            "settlement_city_mar",
            Settlement(
                dealer_id=ctx.dealers["city_charge"].id,
                settlement_month="2026-03",
                start_date=_ts(days_ago=32),
                end_date=_ts(days_ago=1),
                due_date=_future(days_ahead=6),
                total_revenue=5820.0,
                total_commission=451.0,
                chargeback_amount=0.0,
                platform_fee=36.0,
                tax_amount=17.0,
                net_payable=398.0,
                status="approved",
                transaction_reference="SET-CITY-2026-03",
                created_at=_ts(days_ago=1),
            ),
        ),
        (
            "settlement_hanamkonda_mar",
            Settlement(
                dealer_id=ctx.dealers["hanamkonda_mobility"].id,
                settlement_month="2026-03",
                start_date=_ts(days_ago=32),
                end_date=_ts(days_ago=1),
                due_date=_future(days_ahead=8),
                total_revenue=3160.0,
                total_commission=252.0,
                chargeback_amount=45.0,
                platform_fee=22.0,
                tax_amount=11.0,
                net_payable=174.0,
                status="pending",
                created_at=_ts(days_ago=1),
            ),
        ),
        (
            "settlement_vendor_mar",
            Settlement(
                vendor_id=ctx.vendors["rapidhaul"].id,
                settlement_month="2026-03",
                start_date=_ts(days_ago=32),
                end_date=_ts(days_ago=1),
                due_date=_future(days_ahead=4),
                total_revenue=0.0,
                total_commission=0.0,
                chargeback_amount=0.0,
                platform_fee=0.0,
                tax_amount=0.0,
                net_payable=600.0,
                status="paid",
                transaction_reference="SET-RAPIDHAUL-2026-03",
                created_at=_ts(days_ago=1),
                paid_at=_ts(hours_ago=12),
            ),
        ),
    ]
    for key, settlement in settlements:
        ctx.settlements[key] = settlement
        session.add(settlement)
    session.flush()

    session.add(
        SettlementDispute(
            settlement_id=ctx.settlements["settlement_hanamkonda_mar"].id,
            dealer_id=ctx.users["dealer_owner_3"].id,
            reason="Requested clarification on chargeback offset and first-week launch credits.",
            status="open",
            adjustment_amount=45.0,
            created_at=_ts(hours_ago=20),
        )
    )

    session.add_all(
        [
            CommissionLog(
                transaction_id=ctx.transactions["txn_completed_1"].id,
                dealer_id=ctx.users["dealer_owner_1"].id,
                amount=16.1,
                status="settled",
                settlement_id=ctx.settlements["settlement_metro_mar"].id,
                created_at=_ts(days_ago=17),
            ),
            CommissionLog(
                transaction_id=ctx.transactions["txn_rental_1"].id,
                dealer_id=ctx.users["dealer_owner_1"].id,
                amount=15.2,
                status="settled",
                settlement_id=ctx.settlements["settlement_metro_mar"].id,
                created_at=_ts(days_ago=1),
            ),
            CommissionLog(
                transaction_id=ctx.transactions["txn_rental_2"].id,
                dealer_id=ctx.users["dealer_owner_1"].id,
                amount=17.8,
                status="settled",
                settlement_id=ctx.settlements["settlement_metro_mar"].id,
                created_at=_ts(days_ago=2),
            ),
            CommissionLog(
                transaction_id=ctx.transactions["txn_completed_2"].id,
                dealer_id=ctx.users["dealer_owner_2"].id,
                amount=16.2,
                status="approved",
                settlement_id=ctx.settlements["settlement_city_mar"].id,
                created_at=_ts(days_ago=25),
            ),
            CommissionLog(
                transaction_id=ctx.transactions["txn_rental_3"].id,
                dealer_id=ctx.users["dealer_owner_2"].id,
                amount=18.0,
                status="approved",
                settlement_id=ctx.settlements["settlement_city_mar"].id,
                created_at=_ts(days_ago=3),
            ),
            CommissionLog(
                transaction_id=ctx.transactions["txn_swap_2"].id,
                dealer_id=ctx.users["dealer_owner_3"].id,
                amount=3.0,
                status="pending",
                settlement_id=ctx.settlements["settlement_hanamkonda_mar"].id,
                created_at=_ts(days_ago=2),
            ),
            CommissionLog(
                transaction_id=ctx.transactions["txn_purchase_1"].id,
                dealer_id=ctx.users["dealer_owner_1"].id,
                amount=487.5,
                status="settled",
                settlement_id=ctx.settlements["settlement_metro_mar"].id,
                created_at=_ts(days_ago=15),
            ),
            CommissionLog(
                transaction_id=ctx.transactions["txn_swap_1"].id,
                dealer_id=ctx.users["dealer_owner_2"].id,
                amount=2.9,
                status="approved",
                settlement_id=ctx.settlements["settlement_city_mar"].id,
                created_at=_ts(days_ago=1),
            ),
        ]
    )

    session.add(
        Chargeback(
            dealer_id=ctx.users["dealer_owner_3"].id,
            swap_session_id=swap_rows[1].id,
            amount=45.0,
            reason="Duplicate settlement reference on manual franchise payout",
            status="pending",
            settlement_id=ctx.settlements["settlement_hanamkonda_mar"].id,
            created_at=_ts(days_ago=1),
        )
    )

    session.add(
        Refund(
            transaction_id=ctx.transactions["txn_refund_1"].id,
            amount=189.0,
            reason="Cancelled ride refunded after payment capture",
            status="processed",
            gateway_refund_id="rfnd_seed_001",
            processed_at=_ts(days_ago=10),
            created_at=_ts(days_ago=11),
        )
    )

    session.add_all(
        [
            WalletWithdrawalRequest(
                wallet_id=ctx.wallets["dealer_owner_1"].id,
                amount=5000.0,
                status="processed",
                bank_details='{"bank":"HDFC Bank","last4":"4421"}',
                created_at=_ts(days_ago=5),
                processed_at=_ts(days_ago=3),
            ),
            WalletWithdrawalRequest(
                wallet_id=ctx.wallets["dealer_owner_2"].id,
                amount=3200.0,
                status="requested",
                bank_details='{"bank":"ICICI Bank","last4":"8821"}',
                created_at=_ts(hours_ago=18),
            ),
        ]
    )

    session.flush()


def seed_logistics_and_commerce(session: Session, ctx: SeedContext) -> None:
    from app.models.delivery_assignment import DeliveryAssignment
    from app.models.delivery_route import DeliveryRoute, RouteStop
    from app.models.driver_profile import DriverProfile
    from app.models.ecommerce import EcommerceOrder, EcommerceOrderItem, EcommerceProduct
    from app.models.logistics import BatteryTransfer, DeliveryOrder, DeliveryStatus, DeliveryType, Manifest
    from app.models.payment import PaymentTransaction
    from app.models.return_request import ReturnRequest, ReturnStatus

    product_specs = [
        ("home_charger", "PowerFill Home Charger", "ACC-CHG-001", 4899.0, 14, "accessories"),
        ("battery_cover", "Weatherproof Battery Cover", "ACC-COV-002", 899.0, 28, "accessories"),
        ("fleet_pack", "Fleet Starter Battery Pack", "BAT-PACK-003", 16250.0, 3, "battery"),
        ("service_kit", "Station Service Kit", "OPS-SVC-004", 2499.0, 7, "operations"),
    ]
    for key, name, sku, price, stock_quantity, category in product_specs:
        product = EcommerceProduct(
            name=name,
            sku=sku,
            description=f"{name} seeded for admin showcase inventory.",
            price=price,
            stock_quantity=stock_quantity,
            category=category,
            image_url=f"https://assets.powerfill.demo/products/{sku.lower()}.jpg",
            is_active=True,
            created_at=_ts(days_ago=45),
        )
        ctx.products[key] = product
    session.add_all(ctx.products.values())
    session.flush()

    extra_payment_specs = [
        ("pay_order_2", "customer_1", 5798.0, "success", "card", _ts(days_ago=4)),
        ("pay_order_3", "customer_10", 2499.0, "success", "upi", _ts(days_ago=2)),
    ]
    for key, user_key, amount, status, method, created_at in extra_payment_specs:
        payment = PaymentTransaction(
            user_id=ctx.users[user_key].id,
            amount=amount,
            status=status,
            payment_method=method,
            razorpay_order_id=f"order_{key}",
            razorpay_payment_id=f"pay_{key}",
            razorpay_signature=f"sig_{key}",
            created_at=created_at,
            updated_at=created_at,
        )
        ctx.payment_transactions[key] = payment
    session.add_all([ctx.payment_transactions[key] for key, *_ in extra_payment_specs])
    session.flush()

    ecommerce_orders = [
        (
            "order_1",
            EcommerceOrder(
                user_id=ctx.users["customer_2"].id,
                total_amount=16250.0,
                status="delivered",
                shipping_address_id=ctx.addresses["customer_2"].id,
                payment_transaction_id=ctx.payment_transactions["pay_purchase_1"].id,
                created_at=_ts(days_ago=15),
                updated_at=_ts(days_ago=10),
            ),
        ),
        (
            "order_2",
            EcommerceOrder(
                user_id=ctx.users["customer_1"].id,
                total_amount=5798.0,
                status="delivered",
                shipping_address_id=ctx.addresses["customer_1"].id,
                payment_transaction_id=ctx.payment_transactions["pay_order_2"].id,
                created_at=_ts(days_ago=4),
                updated_at=_ts(days_ago=2),
            ),
        ),
        (
            "order_3",
            EcommerceOrder(
                user_id=ctx.users["customer_10"].id,
                total_amount=2499.0,
                status="return_requested",
                shipping_address_id=ctx.addresses["customer_10"].id,
                payment_transaction_id=ctx.payment_transactions["pay_order_3"].id,
                created_at=_ts(days_ago=2),
                updated_at=_ts(hours_ago=18),
            ),
        ),
    ]
    for key, order in ecommerce_orders:
        ctx.ecommerce_orders[key] = order
        session.add(order)
    session.flush()

    session.add_all(
        [
            EcommerceOrderItem(
                order_id=ctx.ecommerce_orders["order_1"].id,
                product_id=ctx.products["fleet_pack"].id,
                quantity=1,
                unit_price=16250.0,
                total_price=16250.0,
            ),
            EcommerceOrderItem(
                order_id=ctx.ecommerce_orders["order_2"].id,
                product_id=ctx.products["home_charger"].id,
                quantity=1,
                unit_price=4899.0,
                total_price=4899.0,
            ),
            EcommerceOrderItem(
                order_id=ctx.ecommerce_orders["order_2"].id,
                product_id=ctx.products["battery_cover"].id,
                quantity=1,
                unit_price=899.0,
                total_price=899.0,
            ),
            EcommerceOrderItem(
                order_id=ctx.ecommerce_orders["order_3"].id,
                product_id=ctx.products["service_kit"].id,
                quantity=1,
                unit_price=2499.0,
                total_price=2499.0,
            ),
            EcommerceOrderItem(
                order_id=ctx.ecommerce_orders["order_3"].id,
                product_id=ctx.products["battery_cover"].id,
                quantity=1,
                unit_price=0.0,
                total_price=0.0,
            ),
        ]
    )

    for key, user_key, license_number, vehicle_type, vehicle_plate, rating, total_deliveries, on_time in [
        ("driver_1", "driver_1", "DL-TS-001221", "e-bike", "TS09EB1044", 4.8, 184, 171),
        ("driver_2", "driver_2", "DL-TS-001222", "cargo_scooter", "TS08EV2210", 4.6, 142, 131),
        ("driver_3", "driver_3", "DL-TS-001223", "mini_van", "TS10EV5502", 4.9, 97, 94),
        ("driver_4", "driver_4", "DL-TS-001224", "cargo_scooter", "TS07EV7781", 4.5, 76, 70),
    ]:
        profile = DriverProfile(
            user_id=ctx.users[user_key].id,
            license_number=license_number,
            vehicle_type=vehicle_type,
            vehicle_plate=vehicle_plate,
            is_online=key in {"driver_1", "driver_2"},
            current_latitude=17.44 if key != "driver_3" else 17.99,
            current_longitude=78.39 if key != "driver_3" else 79.56,
            last_location_update=_ts(minutes_ago=12),
            rating=rating,
            total_deliveries=total_deliveries,
            on_time_deliveries=on_time,
            total_delivery_time_seconds=total_deliveries * 1800,
            satisfaction_sum=total_deliveries * rating,
            created_at=_ts(days_ago=120),
        )
        ctx.driver_profiles[key] = profile
        session.add(profile)
    session.flush()

    return_pending = ReturnRequest(
        order_id=ctx.ecommerce_orders["order_3"].id,
        user_id=ctx.users["customer_10"].id,
        reason="Ordered wrong station service kit specification",
        status=ReturnStatus.PENDING,
        refund_amount=2499.0,
        inspection_notes=None,
        created_at=_ts(hours_ago=18),
        updated_at=_ts(hours_ago=18),
    )
    return_completed = ReturnRequest(
        order_id=ctx.ecommerce_orders["order_2"].id,
        user_id=ctx.users["customer_1"].id,
        reason="Battery cover seam was damaged on arrival",
        status=ReturnStatus.COMPLETED,
        refund_amount=899.0,
        inspection_notes="Approved after image review; replacement not requested.",
        created_at=_ts(days_ago=2),
        updated_at=_ts(days_ago=1),
    )
    ctx.return_requests["pending_return"] = return_pending
    ctx.return_requests["completed_return"] = return_completed
    session.add_all(ctx.return_requests.values())
    session.flush()

    delivery_order_specs = [
        (
            "dealer_restock_1",
            DeliveryOrder(
                order_type=DeliveryType.DEALER_RESTOCK,
                status=DeliveryStatus.DELIVERED,
                origin_address="Central Warehouse, Madhapur, Hyderabad",
                origin_lat=17.4505,
                origin_lng=78.3918,
                destination_address=ctx.stations["warangal_gateway"].address,
                destination_lat=ctx.stations["warangal_gateway"].latitude,
                destination_lng=ctx.stations["warangal_gateway"].longitude,
                assigned_driver_id=ctx.users["driver_3"].id,
                battery_ids_json="[23,24]",
                scheduled_at=_ts(days_ago=2),
                started_at=_ts(days_ago=2, hours_ago=1),
                completed_at=_ts(days_ago=1, hours_ago=20),
                tracking_url="https://tracking.powerfill.demo/DO-001",
                proof_of_delivery_url="https://assets.powerfill.demo/logistics/deliveries/do-001.jpg",
                otp_verified=True,
                completion_otp="441122",
                created_at=_ts(days_ago=2),
                updated_at=_ts(days_ago=1, hours_ago=20),
            ),
        ),
        (
            "dealer_restock_2",
            DeliveryOrder(
                order_type=DeliveryType.DEALER_RESTOCK,
                status=DeliveryStatus.IN_TRANSIT,
                origin_address="Central Warehouse, Madhapur, Hyderabad",
                origin_lat=17.4505,
                origin_lng=78.3918,
                destination_address=ctx.stations["uppal_transit_point"].address,
                destination_lat=ctx.stations["uppal_transit_point"].latitude,
                destination_lng=ctx.stations["uppal_transit_point"].longitude,
                assigned_driver_id=ctx.users["driver_1"].id,
                battery_ids_json="[4,8]",
                scheduled_at=_ts(hours_ago=10),
                started_at=_ts(hours_ago=7),
                tracking_url="https://tracking.powerfill.demo/DO-002",
                otp_verified=False,
                completion_otp="774433",
                created_at=_ts(hours_ago=10),
                updated_at=_ts(hours_ago=1),
            ),
        ),
        (
            "customer_delivery_1",
            DeliveryOrder(
                order_type=DeliveryType.CUSTOMER_DELIVERY,
                status=DeliveryStatus.DELIVERED,
                origin_address="Fulfillment Center, Jubilee Hills, Hyderabad",
                destination_address=ctx.addresses["customer_2"].address_line1,
                destination_lat=ctx.addresses["customer_2"].latitude,
                destination_lng=ctx.addresses["customer_2"].longitude,
                assigned_driver_id=ctx.users["driver_2"].id,
                scheduled_at=_ts(days_ago=14),
                started_at=_ts(days_ago=14, hours_ago=1),
                completed_at=_ts(days_ago=14, hours_ago=2),
                tracking_url="https://tracking.powerfill.demo/DO-003",
                proof_of_delivery_url="https://assets.powerfill.demo/logistics/deliveries/do-003.jpg",
                otp_verified=True,
                completion_otp="112233",
                created_at=_ts(days_ago=15),
                updated_at=_ts(days_ago=14, hours_ago=2),
            ),
        ),
        (
            "customer_delivery_2",
            DeliveryOrder(
                order_type=DeliveryType.CUSTOMER_DELIVERY,
                status=DeliveryStatus.ASSIGNED,
                origin_address="Fulfillment Center, Jubilee Hills, Hyderabad",
                destination_address=ctx.addresses["customer_10"].address_line1,
                destination_lat=ctx.addresses["customer_10"].latitude,
                destination_lng=ctx.addresses["customer_10"].longitude,
                assigned_driver_id=ctx.users["driver_1"].id,
                scheduled_at=_future(hours_ahead=4),
                tracking_url="https://tracking.powerfill.demo/DO-004",
                otp_verified=False,
                completion_otp="998877",
                created_at=_ts(hours_ago=5),
                updated_at=_ts(hours_ago=2),
            ),
        ),
        (
            "reverse_logistics_1",
            DeliveryOrder(
                order_type=DeliveryType.REVERSE_LOGISTICS,
                status=DeliveryStatus.ASSIGNED,
                origin_address=ctx.addresses["customer_10"].address_line1,
                destination_address="Returns Processing Hub, Madhapur, Hyderabad",
                assigned_driver_id=ctx.users["driver_2"].id,
                scheduled_at=_future(hours_ahead=3),
                tracking_url="https://tracking.powerfill.demo/DO-005",
                otp_verified=False,
                completion_otp="221144",
                return_request_id=return_pending.id,
                created_at=_ts(hours_ago=3),
                updated_at=_ts(hours_ago=1),
            ),
        ),
        (
            "reverse_logistics_2",
            DeliveryOrder(
                order_type=DeliveryType.REVERSE_LOGISTICS,
                status=DeliveryStatus.DELIVERED,
                origin_address=ctx.addresses["customer_1"].address_line1,
                destination_address="Returns Processing Hub, Madhapur, Hyderabad",
                assigned_driver_id=ctx.users["driver_1"].id,
                scheduled_at=_ts(days_ago=2),
                started_at=_ts(days_ago=2, hours_ago=1),
                completed_at=_ts(days_ago=1, hours_ago=22),
                tracking_url="https://tracking.powerfill.demo/DO-006",
                proof_of_delivery_url="https://assets.powerfill.demo/logistics/deliveries/do-006.jpg",
                otp_verified=True,
                completion_otp="556677",
                return_request_id=return_completed.id,
                created_at=_ts(days_ago=2),
                updated_at=_ts(days_ago=1, hours_ago=22),
            ),
        ),
    ]
    for key, order in delivery_order_specs:
        ctx.delivery_orders[key] = order
        session.add(order)
    session.flush()

    return_pending.delivery_order_id = ctx.delivery_orders["reverse_logistics_1"].id
    return_completed.delivery_order_id = ctx.delivery_orders["reverse_logistics_2"].id
    session.add(return_pending)
    session.add(return_completed)

    assignment_specs = [
        ("assignment_1", None, None, "driver_3", "Central Warehouse, Madhapur, Hyderabad", ctx.stations["warangal_gateway"].address, "delivered"),
        ("assignment_2", None, None, "driver_1", "Central Warehouse, Madhapur, Hyderabad", ctx.stations["uppal_transit_point"].address, "picked_up"),
        ("assignment_3", None, None, "driver_1", "Fulfillment Center, Jubilee Hills, Hyderabad", ctx.addresses["customer_10"].address_line1, "assigned"),
        ("assignment_4", None, "pending_return", "driver_2", ctx.addresses["customer_10"].address_line1, "Returns Processing Hub, Madhapur, Hyderabad", "assigned"),
    ]
    for key, order_key, return_key, driver_key, pickup, delivery, status in assignment_specs:
        assignment = DeliveryAssignment(
            order_id=ctx.delivery_orders[order_key].id if order_key else None,
            return_request_id=ctx.return_requests[return_key].id if return_key else None,
            driver_id=ctx.driver_profiles[driver_key].id,
            status=status,
            pickup_address=pickup,
            delivery_address=delivery,
            assigned_at=_ts(hours_ago=6),
            picked_up_at=_ts(hours_ago=4) if status in {"picked_up", "delivered"} else None,
            delivered_at=_ts(days_ago=1, hours_ago=20) if status == "delivered" else None,
            proof_of_delivery_img="https://assets.powerfill.demo/logistics/assignment-proof.jpg" if status == "delivered" else None,
            customer_signature="signed-customer" if status == "delivered" else None,
            otp_verified=status == "delivered",
            created_at=_ts(hours_ago=6),
        )
        ctx.delivery_assignments[key] = assignment
        session.add(assignment)
    session.flush()

    route_specs = [
        ("route_hyd_central", "driver_1", "Hyderabad Restock Loop", "IN_PROGRESS", 2, 1, 28.5, 105),
        ("route_returns", "driver_2", "Returns Recovery Run", "PLANNED", 2, 0, 14.0, 62),
        ("route_warangal", "driver_3", "Warangal Launch Route", "COMPLETED", 2, 2, 154.0, 260),
    ]
    for key, driver_key, route_name, status, total_stops, completed_stops, distance, duration in route_specs:
        route = DeliveryRoute(
            driver_id=ctx.driver_profiles[driver_key].id,
            route_name=route_name,
            status=status,
            total_stops=total_stops,
            completed_stops=completed_stops,
            estimated_distance_km=distance,
            estimated_duration_minutes=duration,
            actual_distance_km=distance - 1.6 if status == "COMPLETED" else None,
            actual_duration_minutes=duration - 8 if status == "COMPLETED" else None,
            optimized_path='["A","B","C"]',
            started_at=_ts(days_ago=1) if status in {"IN_PROGRESS", "COMPLETED"} else None,
            completed_at=_ts(days_ago=1, hours_ago=20) if status == "COMPLETED" else None,
            created_at=_ts(days_ago=2),
        )
        ctx.delivery_routes[key] = route
        session.add(route)
    session.flush()

    session.add_all(
        [
            RouteStop(
                route_id=ctx.delivery_routes["route_hyd_central"].id,
                delivery_assignment_id=ctx.delivery_assignments["assignment_2"].id,
                stop_sequence=1,
                stop_type="PICKUP",
                address="Central Warehouse, Madhapur, Hyderabad",
                latitude=17.4505,
                longitude=78.3918,
                estimated_arrival=_future(hours_ahead=1),
                status="COMPLETED",
                actual_arrival=_ts(hours_ago=5),
                completed_at=_ts(hours_ago=5),
            ),
            RouteStop(
                route_id=ctx.delivery_routes["route_hyd_central"].id,
                delivery_assignment_id=ctx.delivery_assignments["assignment_3"].id,
                stop_sequence=2,
                stop_type="DELIVERY",
                address=ctx.addresses["customer_10"].address_line1,
                latitude=ctx.addresses["customer_10"].latitude or 17.44,
                longitude=ctx.addresses["customer_10"].longitude or 78.39,
                estimated_arrival=_future(hours_ahead=3),
                status="PENDING",
            ),
            RouteStop(
                route_id=ctx.delivery_routes["route_returns"].id,
                delivery_assignment_id=ctx.delivery_assignments["assignment_4"].id,
                stop_sequence=1,
                stop_type="PICKUP",
                address=ctx.addresses["customer_10"].address_line1,
                latitude=ctx.addresses["customer_10"].latitude or 17.44,
                longitude=ctx.addresses["customer_10"].longitude or 78.39,
                estimated_arrival=_future(hours_ahead=2),
                status="PENDING",
            ),
            RouteStop(
                route_id=ctx.delivery_routes["route_returns"].id,
                delivery_assignment_id=ctx.delivery_assignments["assignment_4"].id,
                stop_sequence=2,
                stop_type="DELIVERY",
                address="Returns Processing Hub, Madhapur, Hyderabad",
                latitude=17.4505,
                longitude=78.3918,
                estimated_arrival=_future(hours_ahead=4),
                status="PENDING",
            ),
            RouteStop(
                route_id=ctx.delivery_routes["route_warangal"].id,
                delivery_assignment_id=ctx.delivery_assignments["assignment_1"].id,
                stop_sequence=1,
                stop_type="PICKUP",
                address="Central Warehouse, Madhapur, Hyderabad",
                latitude=17.4505,
                longitude=78.3918,
                estimated_arrival=_ts(days_ago=2, hours_ago=2),
                actual_arrival=_ts(days_ago=2, hours_ago=2),
                completed_at=_ts(days_ago=2, hours_ago=2),
                status="COMPLETED",
            ),
            RouteStop(
                route_id=ctx.delivery_routes["route_warangal"].id,
                delivery_assignment_id=ctx.delivery_assignments["assignment_1"].id,
                stop_sequence=2,
                stop_type="DELIVERY",
                address=ctx.stations["warangal_gateway"].address,
                latitude=ctx.stations["warangal_gateway"].latitude,
                longitude=ctx.stations["warangal_gateway"].longitude,
                estimated_arrival=_ts(days_ago=1, hours_ago=22),
                actual_arrival=_ts(days_ago=1, hours_ago=22),
                completed_at=_ts(days_ago=1, hours_ago=22),
                status="COMPLETED",
            ),
        ]
    )

    manifest = Manifest(
        driver_id=ctx.users["driver_3"].id,
        vehicle_id="TS10EV5502",
        status="closed",
        created_at=_ts(days_ago=2),
        updated_at=_ts(days_ago=1, hours_ago=20),
    )
    ctx.manifests["launch_manifest"] = manifest
    session.add(manifest)
    session.flush()

    session.add_all(
        [
            BatteryTransfer(
                battery_id=ctx.batteries["battery_023"].id,
                from_location_type="warehouse",
                from_location_id=1,
                to_location_type="station",
                to_location_id=ctx.stations["warangal_gateway"].id,
                status="received",
                manifest_id=manifest.id,
                created_at=_ts(days_ago=2),
                updated_at=_ts(days_ago=1, hours_ago=20),
            ),
            BatteryTransfer(
                battery_id=ctx.batteries["battery_024"].id,
                from_location_type="service_center",
                from_location_id=2,
                to_location_type="station",
                to_location_id=ctx.stations["warangal_gateway"].id,
                status="received",
                manifest_id=manifest.id,
                created_at=_ts(days_ago=2),
                updated_at=_ts(days_ago=1, hours_ago=20),
            ),
            BatteryTransfer(
                battery_id=ctx.batteries["battery_008"].id,
                from_location_type="station",
                from_location_id=ctx.stations["hitech_city_nexus"].id,
                to_location_type="service_center",
                to_location_id=2,
                status="in_transit",
                manifest_id=manifest.id,
                created_at=_ts(hours_ago=9),
                updated_at=_ts(hours_ago=2),
            ),
        ]
    )

    session.flush()


def seed_support_and_content(session: Session, ctx: SeedContext) -> None:
    from app.models.banner import Banner
    from app.models.blog import Blog
    from app.models.faq import FAQ
    from app.models.legal import LegalDocument
    from app.models.media import MediaAsset
    from app.models.support import ChatMessage, ChatSession, ChatStatus, SupportTicket, TicketMessage, TicketPriority, TicketStatus

    ticket_specs = [
        ("ticket_1", "customer_5", "admin_support", "Late fee dispute for overdue rental", "Rider is disputing late fee due to metro construction detour.", TicketStatus.OPEN, TicketPriority.HIGH, "billing", _ts(hours_ago=7)),
        ("ticket_2", "customer_6", "support_agent_1", "Battery health dropped during active ride", "Customer reports severe discharge and wants urgent assistance.", TicketStatus.IN_PROGRESS, TicketPriority.CRITICAL, "hardware", _ts(hours_ago=9)),
        ("ticket_3", "dealer_owner_3", "admin_support", "Warangal launch kit still missing spare harness", "Dealer launch checklist is blocked by missing service harness.", TicketStatus.OPEN, TicketPriority.HIGH, "dealer_ops", _ts(days_ago=1)),
        ("ticket_4", "customer_1", "support_agent_2", "Refund not reflected in wallet", "User sees refund approved but wallet balance is unchanged.", TicketStatus.RESOLVED, TicketPriority.MEDIUM, "billing", _ts(days_ago=2)),
        ("ticket_5", "customer_8", "support_agent_1", "KYC verification stuck in review", "Customer submitted fresh documents and wants ETA.", TicketStatus.IN_PROGRESS, TicketPriority.MEDIUM, "kyc", _ts(days_ago=3)),
        ("ticket_6", "customer_3", "support_agent_2", "App kept recommending the wrong swap station", "Suggestion engine pointed to a low-stock station twice.", TicketStatus.CLOSED, TicketPriority.LOW, "app", _ts(days_ago=4)),
        ("ticket_7", "dealer_owner_2", "admin_support", "Settlement statement missing March swap credits", "Dealer requests a revised statement before approval.", TicketStatus.OPEN, TicketPriority.HIGH, "settlements", _ts(days_ago=1, hours_ago=2)),
        ("ticket_8", "customer_10", "support_agent_2", "Return pickup slot needs to be moved", "Customer is available only after 7 PM for the reverse pickup.", TicketStatus.RESOLVED, TicketPriority.MEDIUM, "returns", _ts(hours_ago=18)),
    ]
    for key, user_key, assignee_key, subject, description, status, priority, category, created_at in ticket_specs:
        ticket = SupportTicket(
            user_id=ctx.users[user_key].id,
            assigned_to=ctx.users[assignee_key].id,
            subject=subject,
            description=description,
            status=status,
            priority=priority,
            category=category,
            created_at=created_at,
            updated_at=created_at + timedelta(hours=2),
            resolved_at=created_at + timedelta(hours=6) if status in {TicketStatus.RESOLVED, TicketStatus.CLOSED} else None,
        )
        ctx.support_tickets[key] = ticket
    session.add_all(ctx.support_tickets.values())
    session.flush()

    ticket_messages = []
    for index, (ticket_key, ticket) in enumerate(ctx.support_tickets.items(), start=1):
        ticket_messages.append(
            TicketMessage(
                ticket_id=ticket.id,
                sender_id=ticket.user_id,
                message=f"Initial context for {ticket.subject.lower()}.",
                is_internal_note=False,
                created_at=ticket.created_at,
            )
        )
        ticket_messages.append(
            TicketMessage(
                ticket_id=ticket.id,
                sender_id=ticket.assigned_to or ctx.users["admin_support"].id,
                message="Support team reviewed the case and updated the workflow.",
                is_internal_note=index % 3 == 0,
                created_at=ticket.created_at + timedelta(hours=1),
            )
        )
    session.add_all(ticket_messages)

    session.add_all(
        [
            ChatSession(
                user_id=ctx.users["customer_1"].id,
                assigned_agent_id=ctx.users["support_agent_1"].id,
                status=ChatStatus.ACTIVE,
                created_at=_ts(hours_ago=3),
                updated_at=_ts(hours_ago=1),
            ),
            ChatSession(
                user_id=ctx.users["dealer_owner_3"].id,
                assigned_agent_id=ctx.users["admin_support"].id,
                status=ChatStatus.WAITING,
                created_at=_ts(hours_ago=6),
                updated_at=_ts(hours_ago=2),
            ),
        ]
    )
    session.flush()
    chat_sessions = session.exec(select(ChatSession).order_by(ChatSession.id)).all()
    session.add_all(
        [
            ChatMessage(session_id=chat_sessions[0].id, sender_id=ctx.users["customer_1"].id, message="Need help understanding the latest invoice.", created_at=_ts(hours_ago=3)),
            ChatMessage(session_id=chat_sessions[0].id, sender_id=ctx.users["support_agent_1"].id, message="Checking the wallet ledger now.", created_at=_ts(hours_ago=2)),
            ChatMessage(session_id=chat_sessions[1].id, sender_id=ctx.users["dealer_owner_3"].id, message="Can someone confirm tomorrow's field visit slot?", created_at=_ts(hours_ago=6)),
            ChatMessage(session_id=chat_sessions[1].id, sender_id=0, message="Your request has been queued for the dealer-success desk.", created_at=_ts(hours_ago=5)),
        ]
    )

    session.add_all(
        [
            FAQ(
                question="How are late fees calculated?",
                answer="Late fees are calculated from the expected return time using the configured daily rate and any progressive penalty slabs.",
                category="billing",
                helpful_count=38,
                not_helpful_count=4,
                created_at=_ts(days_ago=20),
                updated_at=_ts(days_ago=4),
            ),
            FAQ(
                question="What triggers a low stock alert?",
                answer="A low stock alert is raised when available station inventory falls below the configured reorder point and no active dismissal exists.",
                category="fleet_ops",
                helpful_count=22,
                not_helpful_count=2,
                created_at=_ts(days_ago=18),
                updated_at=_ts(days_ago=3),
            ),
            FAQ(
                question="How long does KYC verification take?",
                answer="Most KYC reviews close within 24 hours, but manual escalations can take up to 48 hours.",
                category="kyc",
                helpful_count=44,
                not_helpful_count=6,
                created_at=_ts(days_ago=22),
                updated_at=_ts(days_ago=5),
            ),
            FAQ(
                question="How do dealer settlements get approved?",
                answer="Finance reviews commission logs, disputes, and chargebacks before approving and paying the settlement batch.",
                category="dealers",
                helpful_count=18,
                not_helpful_count=1,
                created_at=_ts(days_ago=24),
                updated_at=_ts(days_ago=4),
            ),
            FAQ(
                question="What happens when a battery health alert is resolved?",
                answer="The alert stays in history with its resolution reason, resolver, and timestamp for auditability.",
                category="health",
                helpful_count=27,
                not_helpful_count=0,
                created_at=_ts(days_ago=16),
                updated_at=_ts(days_ago=3),
            ),
            FAQ(
                question="Can notification providers be tested from admin?",
                answer="Yes. Each notification configuration can be test-fired from the admin portal to validate credentials and delivery.",
                category="notifications",
                helpful_count=15,
                not_helpful_count=1,
                created_at=_ts(days_ago=12),
                updated_at=_ts(days_ago=2),
            ),
        ]
    )

    session.add_all(
        [
            Blog(
                title="How PowerFill Prepared the Warangal Launch Corridor",
                slug="warangal-launch-corridor",
                content="Long-form launch recap with station readiness, franchise onboarding, and fleet balancing notes.",
                summary="Launch operations story for the Warangal expansion.",
                featured_image_url="https://assets.powerfill.demo/blogs/warangal-launch.jpg",
                category="operations",
                author_id=ctx.users["admin_super"].id,
                status="published",
                views_count=1240,
                published_at=_ts(days_ago=6),
                created_at=_ts(days_ago=8),
                updated_at=_ts(days_ago=6),
            ),
            Blog(
                title="Understanding Battery Health Alerts in the Admin Portal",
                slug="battery-health-alerts-admin-guide",
                content="Guide to interpreting critical health, overdue service, and rapid degradation signals.",
                summary="Operator playbook for acting on health alerts.",
                featured_image_url="https://assets.powerfill.demo/blogs/health-alerts.jpg",
                category="product",
                author_id=ctx.users["admin_fleet"].id,
                status="published",
                views_count=860,
                published_at=_ts(days_ago=12),
                created_at=_ts(days_ago=14),
                updated_at=_ts(days_ago=12),
            ),
            Blog(
                title="Five Changes We Made to Dealer Settlement Review",
                slug="dealer-settlement-review-improvements",
                content="Finance and dealer-success teams reviewed dispute patterns and updated the approval checklist.",
                summary="What changed in settlement QA.",
                featured_image_url="https://assets.powerfill.demo/blogs/settlements.jpg",
                category="finance",
                author_id=ctx.users["admin_finance"].id,
                status="draft",
                views_count=112,
                created_at=_ts(days_ago=5),
                updated_at=_ts(days_ago=1),
            ),
            Blog(
                title="Designing Notification Journeys for Swap Demand Peaks",
                slug="notification-journeys-swap-demand",
                content="How campaign targeting and automated triggers were tuned around commuter demand peaks.",
                summary="Notification strategy for high-demand periods.",
                featured_image_url="https://assets.powerfill.demo/blogs/notification-journeys.jpg",
                category="growth",
                author_id=ctx.users["admin_support"].id,
                status="scheduled",
                views_count=0,
                published_at=_future(days_ahead=2),
                created_at=_ts(days_ago=1),
                updated_at=_ts(hours_ago=6),
            ),
        ]
    )

    session.add_all(
        [
            Banner(
                title="Warangal Launch Week",
                image_url="https://assets.powerfill.demo/banners/warangal-launch.png",
                deep_link="/campaigns/warangal-launch",
                priority=10,
                is_active=True,
                start_date=_ts(days_ago=2),
                end_date=_future(days_ahead=5),
                click_count=284,
                created_at=_ts(days_ago=3),
                updated_at=_ts(days_ago=1),
            ),
            Banner(
                title="Zero Waiting Swap Hour",
                image_url="https://assets.powerfill.demo/banners/zero-waiting-hour.png",
                deep_link="/fleet/stock",
                priority=8,
                is_active=True,
                start_date=_ts(days_ago=10),
                end_date=_future(days_ahead=12),
                click_count=198,
                created_at=_ts(days_ago=10),
                updated_at=_ts(days_ago=2),
            ),
            Banner(
                title="Dealer Training Bootcamp",
                image_url="https://assets.powerfill.demo/banners/dealer-bootcamp.png",
                external_url="https://academy.powerfill.demo/dealer-bootcamp",
                priority=6,
                is_active=False,
                start_date=_ts(days_ago=20),
                end_date=_ts(days_ago=12),
                click_count=91,
                created_at=_ts(days_ago=22),
                updated_at=_ts(days_ago=12),
            ),
        ]
    )

    session.add_all(
        [
            LegalDocument(
                title="Terms of Service",
                slug="terms-of-service",
                content="Terms for use of the PowerFill platform and rental network.",
                version="3.2.0",
                is_active=True,
                force_update=False,
                published_at=_ts(days_ago=45),
                created_at=_ts(days_ago=45),
                updated_at=_ts(days_ago=3),
            ),
            LegalDocument(
                title="Privacy Policy",
                slug="privacy-policy",
                content="Privacy commitments covering user identity, telemetry, and payment data.",
                version="2.7.0",
                is_active=True,
                force_update=False,
                published_at=_ts(days_ago=45),
                created_at=_ts(days_ago=45),
                updated_at=_ts(days_ago=3),
            ),
            LegalDocument(
                title="Dealer Commercial Terms",
                slug="dealer-commercial-terms",
                content="Commercial structure, payout windows, and dispute handling for dealer partners.",
                version="1.4.1",
                is_active=True,
                force_update=True,
                published_at=_ts(days_ago=20),
                created_at=_ts(days_ago=20),
                updated_at=_ts(days_ago=2),
            ),
        ]
    )

    media_specs = [
        ("warangal-launch.png", "image/png", 218_442, "https://assets.powerfill.demo/media/warangal-launch.png", "Warangal launch hero", "banner"),
        ("settlement-guide.pdf", "application/pdf", 412_889, "https://assets.powerfill.demo/media/settlement-guide.pdf", "Settlement guide", "general"),
        ("fleet-health-dashboard.png", "image/png", 152_090, "https://assets.powerfill.demo/media/fleet-health-dashboard.png", "Fleet health dashboard", "blog"),
        ("dealer-kyc-checklist.pdf", "application/pdf", 380_114, "https://assets.powerfill.demo/media/dealer-kyc-checklist.pdf", "Dealer KYC checklist", "kyc"),
        ("home-charger-packshot.jpg", "image/jpeg", 98_454, "https://assets.powerfill.demo/media/home-charger-packshot.jpg", "Home charger", "general"),
        ("returns-ops-board.png", "image/png", 204_377, "https://assets.powerfill.demo/media/returns-ops-board.png", "Returns board", "blog"),
        ("banner-zero-waiting.png", "image/png", 174_110, "https://assets.powerfill.demo/media/banner-zero-waiting.png", "Zero waiting banner", "banner"),
        ("dealer-bootcamp.jpg", "image/jpeg", 132_228, "https://assets.powerfill.demo/media/dealer-bootcamp.jpg", "Dealer bootcamp", "general"),
    ]
    session.add_all(
        [
            MediaAsset(
                file_name=file_name,
                file_type=file_type,
                file_size_bytes=file_size,
                url=url,
                alt_text=alt_text,
                category=category,
                uploaded_by_id=ctx.users["admin_support"].id,
                created_at=_ts(days_ago=10),
                updated_at=_ts(days_ago=2),
            )
            for file_name, file_type, file_size, url, alt_text, category in media_specs
        ]
    )

    session.flush()


def seed_notifications(session: Session, ctx: SeedContext) -> None:
    from app.models.notification_admin import AutomatedTrigger, NotificationConfig, NotificationLog, PushCampaign

    campaign_specs = [
        (
            "warangal_launch_push",
            PushCampaign(
                title="Warangal launch week is live",
                message="New swap corridor is active with zero activation fee for the first seven days.",
                target_segment="warangal_launch",
                target_count=1240,
                channel="push",
                status="sent",
                scheduled_at=_ts(days_ago=2, hours_ago=2),
                sent_at=_ts(days_ago=2),
                sent_count=1240,
                delivered_count=1170,
                open_count=432,
                click_count=158,
                failed_count=70,
                created_by=ctx.users["admin_support"].id,
                created_at=_ts(days_ago=3),
                updated_at=_ts(days_ago=2),
            ),
        ),
        (
            "late_fee_reminder",
            PushCampaign(
                title="Rental return reminder",
                message="Return your battery before the grace window closes to avoid late fees.",
                target_segment="overdue_watchlist",
                target_count=186,
                channel="push",
                status="scheduled",
                scheduled_at=_future(hours_ahead=4),
                sent_count=0,
                delivered_count=0,
                open_count=0,
                click_count=0,
                failed_count=0,
                created_by=ctx.users["admin_support"].id,
                created_at=_ts(hours_ago=8),
                updated_at=_ts(hours_ago=2),
            ),
        ),
        (
            "dealer_bootcamp_mailer",
            PushCampaign(
                title="Dealer bootcamp registration",
                message="Seats are open for next week's dealer commercial excellence bootcamp.",
                target_segment="dealer_network",
                target_count=42,
                channel="email",
                status="draft",
                sent_count=0,
                delivered_count=0,
                open_count=0,
                click_count=0,
                failed_count=0,
                created_by=ctx.users["admin_finance"].id,
                created_at=_ts(days_ago=1),
                updated_at=_ts(hours_ago=5),
            ),
        ),
    ]
    for key, campaign in campaign_specs:
        ctx.campaigns[key] = campaign
        session.add(campaign)
    session.flush()

    trigger_specs = [
        (
            "battery_low_soc",
            AutomatedTrigger(
                name="Battery SOC below threshold",
                description="Notify riders when their active battery is nearing mandatory swap range.",
                event_type="battery_low_soc",
                channel="push",
                template_message="Your battery is running low. A nearby swap station has been suggested.",
                delay_minutes=0,
                is_active=True,
                trigger_count=184,
                last_triggered_at=_ts(hours_ago=3),
                created_at=_ts(days_ago=30),
                updated_at=_ts(days_ago=1),
            ),
        ),
        (
            "kyc_pending_reminder",
            AutomatedTrigger(
                name="KYC pending reminder",
                description="Follow up with customers whose KYC review is still incomplete.",
                event_type="kyc_pending_24h",
                channel="email",
                template_message="Your KYC is pending. Please review the checklist and resubmit if required.",
                delay_minutes=1440,
                is_active=True,
                trigger_count=67,
                last_triggered_at=_ts(days_ago=1),
                created_at=_ts(days_ago=28),
                updated_at=_ts(days_ago=1),
            ),
        ),
        (
            "settlement_ready",
            AutomatedTrigger(
                name="Settlement ready for approval",
                description="Notify finance leads when a monthly settlement pack is complete.",
                event_type="settlement_pack_ready",
                channel="email",
                template_message="A settlement batch is ready for review in the finance console.",
                delay_minutes=15,
                is_active=True,
                trigger_count=12,
                last_triggered_at=_ts(days_ago=1, hours_ago=1),
                created_at=_ts(days_ago=24),
                updated_at=_ts(days_ago=1),
            ),
        ),
        (
            "return_pickup_eta",
            AutomatedTrigger(
                name="Reverse pickup ETA",
                description="Notify customers when their reverse pickup has been assigned.",
                event_type="return_pickup_assigned",
                channel="sms",
                template_message="Your return pickup has been assigned and will arrive in the selected window.",
                delay_minutes=0,
                is_active=False,
                trigger_count=9,
                last_triggered_at=_ts(days_ago=5),
                created_at=_ts(days_ago=20),
                updated_at=_ts(days_ago=2),
            ),
        ),
    ]
    for key, trigger in trigger_specs:
        ctx.triggers[key] = trigger
        session.add(trigger)
    session.flush()

    session.add_all(
        [
            NotificationConfig(
                provider="firebase",
                channel="push",
                display_name="Firebase Cloud Messaging",
                api_key="fcm_seed_live_key_00112233",
                api_secret="fcm_seed_secret_8899",
                sender_id="powerfill-app",
                is_active=True,
                last_tested_at=_ts(days_ago=1),
                test_status="success",
                created_at=_ts(days_ago=60),
                updated_at=_ts(days_ago=1),
            ),
            NotificationConfig(
                provider="twilio",
                channel="sms",
                display_name="Twilio SMS",
                api_key="twilio_seed_live_key_22334455",
                api_secret="twilio_seed_secret_1010",
                sender_id="PWRFIL",
                is_active=True,
                last_tested_at=_ts(days_ago=2),
                test_status="success",
                created_at=_ts(days_ago=60),
                updated_at=_ts(days_ago=2),
            ),
            NotificationConfig(
                provider="sendgrid",
                channel="email",
                display_name="SendGrid Transactional",
                api_key="sendgrid_seed_key_33445566",
                api_secret="sendgrid_seed_secret_1112",
                sender_id="ops@powerfill.in",
                is_active=True,
                last_tested_at=_ts(days_ago=3),
                test_status="success",
                created_at=_ts(days_ago=60),
                updated_at=_ts(days_ago=3),
            ),
            NotificationConfig(
                provider="gupshup",
                channel="whatsapp",
                display_name="Gupshup WhatsApp",
                api_key="gupshup_seed_key_44556677",
                api_secret="gupshup_seed_secret_9911",
                sender_id="PowerFill",
                is_active=False,
                last_tested_at=_ts(days_ago=5),
                test_status="failed",
                created_at=_ts(days_ago=60),
                updated_at=_ts(days_ago=5),
            ),
        ]
    )

    log_rows = [
        ("warangal_launch_push", None, "customer_1", "push", "Warangal launch week is live", "New corridor is active.", "opened", _ts(days_ago=2), _ts(days_ago=2), _ts(days_ago=2)),
        ("warangal_launch_push", None, "customer_2", "push", "Warangal launch week is live", "New corridor is active.", "delivered", _ts(days_ago=2), _ts(days_ago=2), None),
        ("warangal_launch_push", None, "customer_3", "push", "Warangal launch week is live", "New corridor is active.", "failed", _ts(days_ago=2), None, None),
        ("warangal_launch_push", None, "customer_4", "push", "Warangal launch week is live", "New corridor is active.", "sent", _ts(days_ago=2), None, None),
        (None, "battery_low_soc", "customer_5", "push", "Battery low", "Swap now to avoid outage.", "opened", _ts(hours_ago=7), _ts(hours_ago=7), _ts(hours_ago=6)),
        (None, "battery_low_soc", "customer_6", "push", "Battery low", "Swap now to avoid outage.", "delivered", _ts(hours_ago=5), _ts(hours_ago=5), None),
        (None, "kyc_pending_reminder", "customer_7", "email", "KYC pending", "Please review your submitted documents.", "sent", _ts(days_ago=1), None, None),
        (None, "kyc_pending_reminder", "customer_8", "email", "KYC pending", "Please review your submitted documents.", "opened", _ts(days_ago=1), _ts(days_ago=1), _ts(hours_ago=18)),
        (None, "settlement_ready", "dealer_owner_2", "email", "Settlement ready", "March settlement batch is ready.", "delivered", _ts(hours_ago=20), _ts(hours_ago=20), None),
        (None, "settlement_ready", "dealer_owner_3", "email", "Settlement ready", "March settlement batch is ready.", "failed", _ts(hours_ago=20), None, None),
        ("late_fee_reminder", None, "customer_5", "push", "Rental return reminder", "Return before grace closes.", "sent", _ts(hours_ago=2), None, None),
        ("late_fee_reminder", None, "customer_6", "push", "Rental return reminder", "Return before grace closes.", "sent", _ts(hours_ago=2), None, None),
    ]
    session.add_all(
        [
            NotificationLog(
                campaign_id=ctx.campaigns[campaign_key].id if campaign_key else None,
                trigger_id=ctx.triggers[trigger_key].id if trigger_key else None,
                user_id=ctx.users[user_key].id,
                channel=channel,
                title=title,
                message=message,
                status=status,
                sent_at=sent_at,
                delivered_at=delivered_at,
                opened_at=opened_at,
            )
            for campaign_key, trigger_key, user_key, channel, title, message, status, sent_at, delivered_at, opened_at in log_rows
        ]
    )

    session.flush()


def seed_settings_security_and_ops(session: Session, ctx: SeedContext) -> None:
    from app.models.api_key import ApiKeyConfig
    from app.models.audit_log import AuditLog, AuditActionType, SecurityEvent
    from app.models.batch_job import BatchJob, JobExecution
    from app.models.device_fingerprint import DeviceFingerprint, DuplicateAccount
    from app.models.fraud import Blacklist, FraudCheckLog, RiskScore
    from app.models.system import FeatureFlag, SystemConfig

    session.add_all(
        [
            SystemConfig(key="company_name", value="PowerFill Demo Ops", description="Tenant display name"),
            SystemConfig(key="support_hours", value="06:00-23:00", description="Public support hours"),
            SystemConfig(key="default_city", value="Hyderabad", description="Primary ops city"),
            SystemConfig(key="2fa_enabled", value="true", description="Security: two-factor auth"),
            SystemConfig(key="session_timeout_minutes", value="60", description="Security: session timeout"),
            SystemConfig(key="max_login_attempts", value="5", description="Security: brute-force protection"),
            SystemConfig(key="password_min_length", value="10", description="Security: password minimum length"),
            SystemConfig(key="password_expiry_days", value="90", description="Security: password expiry window"),
            SystemConfig(key="ip_whitelist_enabled", value="false", description="Security: IP whitelist toggle"),
        ]
    )

    session.add_all(
        [
            FeatureFlag(name="warangal_launch_incentive", is_enabled=True, rollout_percentage=100, enabled_for_tenants='["powerfill-demo"]', updated_at=_ts(days_ago=1)),
            FeatureFlag(name="dynamic_swap_eta", is_enabled=True, rollout_percentage=80, enabled_for_users='[1,2,3,4]', updated_at=_ts(days_ago=2)),
            FeatureFlag(name="dealer_settlement_v2", is_enabled=True, rollout_percentage=100, enabled_for_tenants='["powerfill-demo"]', updated_at=_ts(days_ago=2)),
            FeatureFlag(name="battery_reservation_hold", is_enabled=False, rollout_percentage=0, updated_at=_ts(days_ago=3)),
            FeatureFlag(name="bess_peak_shaving", is_enabled=True, rollout_percentage=100, updated_at=_ts(days_ago=1)),
            FeatureFlag(name="support_chatbot_handoff", is_enabled=True, rollout_percentage=65, enabled_for_users='[1,2,7,8]', updated_at=_ts(days_ago=4)),
        ]
    )

    session.add_all(
        [
            ApiKeyConfig(service_name="firebase", key_name="primary_fcm", key_value="fcm_prod_seed_88990011", environment="production", is_active=True, last_used_at=_ts(hours_ago=1), created_at=_ts(days_ago=60), updated_at=_ts(days_ago=1)),
            ApiKeyConfig(service_name="twilio", key_name="sms_primary", key_value="twilio_prod_seed_223311", environment="production", is_active=True, last_used_at=_ts(hours_ago=2), created_at=_ts(days_ago=60), updated_at=_ts(days_ago=2)),
            ApiKeyConfig(service_name="sendgrid", key_name="email_primary", key_value="sendgrid_prod_seed_776655", environment="production", is_active=True, last_used_at=_ts(hours_ago=4), created_at=_ts(days_ago=60), updated_at=_ts(days_ago=2)),
            ApiKeyConfig(service_name="maps", key_name="routing_api", key_value="maps_prod_seed_443322", environment="production", is_active=True, last_used_at=_ts(hours_ago=6), created_at=_ts(days_ago=60), updated_at=_ts(days_ago=3)),
            ApiKeyConfig(service_name="fraud", key_name="risk_engine", key_value="risk_prod_seed_118899", environment="production", is_active=False, last_used_at=_ts(days_ago=7), created_at=_ts(days_ago=60), updated_at=_ts(days_ago=5)),
        ]
    )

    audit_rows = [
        (ctx.users["admin_super"].id, AuditActionType.USER_CREATION.value, "USER", str(ctx.users["dealer_owner_4"].id), "Created pending dealer principal account"),
        (ctx.users["admin_support"].id, AuditActionType.PERMISSION_CHANGE.value, "ROLE", str(ctx.roles["support_agent"].id), "Expanded support agent privileges for live chat handoff"),
        (ctx.users["admin_fleet"].id, AuditActionType.DATA_MODIFICATION.value, "BATTERY", str(ctx.batteries["battery_021"].id), "Escalated battery to critical health watch"),
        (ctx.users["admin_finance"].id, AuditActionType.FINANCIAL_TRANSACTION.value, "SETTLEMENT", str(ctx.settlements["settlement_city_mar"].id), "Reviewed March city settlement pack"),
        (ctx.users["admin_risk"].id, AuditActionType.ACCOUNT_STATUS_CHANGE.value, "USER", str(ctx.users["customer_9"].id), "Suspended rider account after duplicate-device risk confirmation"),
        (ctx.users["admin_support"].id, AuditActionType.AUTH_LOGIN.value, "AUTH", str(ctx.users["admin_support"].id), "Admin login from support war room"),
        (ctx.users["admin_super"].id, AuditActionType.USER_INVITE.value, "DEALER", str(ctx.dealers["hanamkonda_mobility"].id), "Invited dealer team into onboarding workspace"),
        (ctx.users["admin_fleet"].id, AuditActionType.DATA_MODIFICATION.value, "STATION", str(ctx.stations["warangal_gateway"].id), "Adjusted reorder point for launch week"),
        (ctx.users["admin_finance"].id, AuditActionType.BALANCE_ADJUSTMENT.value, "WALLET", str(ctx.wallets["dealer_owner_1"].id), "Processed dealer withdrawal request"),
        (ctx.users["admin_support"].id, AuditActionType.SESSION_TERMINATED.value, "AUTH", str(ctx.users["customer_8"].id), "Forced logout after KYC resubmission"),
        (ctx.users["admin_risk"].id, AuditActionType.PERMISSION_CHANGE.value, "SECURITY_EVENT", "3", "Marked event resolved after verification"),
        (ctx.users["admin_super"].id, AuditActionType.AUTH_LOGOUT.value, "AUTH", str(ctx.users["admin_super"].id), "Scheduled logout after key rotation"),
        (ctx.users["admin_finance"].id, AuditActionType.FINANCIAL_TRANSACTION.value, "INVOICE", str(next(iter(ctx.invoices.values())).id), "Generated invoice batch for daily ledger"),
        (ctx.users["admin_fleet"].id, AuditActionType.DATA_MODIFICATION.value, "DELIVERY_ORDER", str(ctx.delivery_orders["dealer_restock_2"].id), "Re-routed restock order around traffic block"),
        (ctx.users["admin_support"].id, AuditActionType.ACCOUNT_ACTIVATION.value, "USER", str(ctx.users["customer_1"].id), "Re-enabled notification opt-in"),
        (ctx.users["admin_risk"].id, AuditActionType.PASSWORD_RESET.value, "USER", str(ctx.users["customer_9"].id), "Triggered password reset after suspicious activity"),
    ]
    session.add_all(
        [
            AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                meta_data={"seeded": True},
                old_value={"state": "previous"} if index % 2 == 0 else None,
                new_value={"state": "current"} if index % 2 == 0 else None,
                ip_address=f"10.0.0.{index}",
                user_agent="seed-showcase-admin",
                timestamp=_ts(days_ago=index // 3, hours_ago=index),
            )
            for index, (user_id, action, resource_type, resource_id, details) in enumerate(audit_rows, start=1)
        ]
    )

    session.add_all(
        [
            SecurityEvent(event_type="failed_login", severity="medium", details="Multiple failed attempts on support dashboard", source_ip="49.205.1.21", user_id=ctx.users["customer_9"].id, timestamp=_ts(days_ago=2), is_resolved=True),
            SecurityEvent(event_type="suspicious_ip", severity="high", details="Login attempt from new ASN while account under review", source_ip="185.220.101.4", user_id=ctx.users["customer_9"].id, timestamp=_ts(days_ago=2), is_resolved=False),
            SecurityEvent(event_type="api_abuse", severity="medium", details="Rate limiter tripped on notification export endpoint", source_ip="103.92.10.3", user_id=ctx.users["admin_support"].id, timestamp=_ts(days_ago=1), is_resolved=True),
            SecurityEvent(event_type="duplicate_device", severity="high", details="Same device hash observed across two customer accounts", source_ip="106.51.9.88", user_id=ctx.users["customer_7"].id, timestamp=_ts(days_ago=4), is_resolved=False),
            SecurityEvent(event_type="chargeback_watch", severity="critical", details="Franchise settlement batch contains a flagged chargeback", source_ip="10.0.2.44", user_id=ctx.users["dealer_owner_3"].id, timestamp=_ts(days_ago=1), is_resolved=False),
            SecurityEvent(event_type="privilege_change", severity="low", details="Support agent role updated via RBAC admin", source_ip="10.0.1.16", user_id=ctx.users["admin_super"].id, timestamp=_ts(days_ago=14), is_resolved=True),
            SecurityEvent(event_type="session_revoke", severity="low", details="User sessions revoked after KYC document mismatch", source_ip="10.0.1.22", user_id=ctx.users["customer_8"].id, timestamp=_ts(days_ago=3), is_resolved=True),
            SecurityEvent(event_type="key_rotation", severity="medium", details="API key rotation completed for Twilio and Maps", source_ip="10.0.1.30", user_id=ctx.users["admin_super"].id, timestamp=_ts(days_ago=5), is_resolved=True),
        ]
    )

    fingerprint_specs = [
        ("customer_1", "devhash-001", "MOBILE", "Android", "49.205.1.10", False, 8.0),
        ("customer_2", "devhash-002", "MOBILE", "Android", "49.205.1.11", False, 9.0),
        ("customer_3", "devhash-003", "MOBILE", "iOS", "49.205.1.12", False, 12.0),
        ("customer_4", "devhash-004", "MOBILE", "iOS", "49.205.1.13", False, 11.0),
        ("customer_5", "devhash-005", "MOBILE", "Android", "49.205.1.14", True, 58.0),
        ("customer_6", "devhash-006", "MOBILE", "Android", "49.205.1.15", False, 21.0),
        ("customer_7", "dup-devhash-777", "MOBILE", "Android", "106.51.9.88", True, 73.0),
        ("customer_9", "dup-devhash-777", "MOBILE", "Android", "106.51.9.88", True, 81.0),
    ]
    device_map: dict[str, DeviceFingerprint] = {}
    for index, (user_key, hash_value, device_type, os_name, ip_address, suspicious, risk_score) in enumerate(fingerprint_specs, start=1):
        fingerprint = DeviceFingerprint(
            user_id=ctx.users[user_key].id,
            device_id=f"device-{user_key}",
            fingerprint_hash=hash_value,
            device_type=device_type,
            os_name=os_name,
            os_version="14" if os_name == "Android" else "17.4",
            browser_name="WebView",
            browser_version="124",
            device_model="Pixel 8" if os_name == "Android" else "iPhone 15",
            device_manufacturer="Google" if os_name == "Android" else "Apple",
            screen_resolution="1080x2400",
            timezone="Asia/Kolkata",
            language="en-IN",
            ip_address=ip_address,
            user_agent="seed-showcase-mobile",
            device_metadata={"nfc": True, "biometric": True},
            is_suspicious=suspicious,
            risk_score=risk_score,
            first_seen=_ts(days_ago=30 + index),
            last_seen=_ts(hours_ago=index),
        )
        device_map[user_key] = fingerprint
        session.add(fingerprint)
    session.flush()

    session.add_all(
        [
            DuplicateAccount(
                primary_user_id=ctx.users["customer_7"].id,
                suspected_duplicate_user_id=ctx.users["customer_9"].id,
                matching_device_id=device_map["customer_7"].id,
                matching_phone=False,
                matching_email=False,
                matching_ip=True,
                matching_address=False,
                matching_payment_method=True,
                device_similarity_score=92.0,
                behavior_similarity_score=81.0,
                overall_confidence=87.0,
                status="INVESTIGATING",
                investigated_by=ctx.users["admin_risk"].id,
                investigated_at=_ts(days_ago=1),
                action_taken="FLAGGED",
                notes="Shared device hash and overlapping wallet behavior.",
                detected_at=_ts(days_ago=4),
            )
        ]
    )

    session.add_all(
        [
            RiskScore(user_id=ctx.users["customer_5"].id, total_score=64.0, breakdown={"overdue_rentals": 22, "late_fee": 18, "device_risk": 24}, last_updated=_ts(hours_ago=6)),
            RiskScore(user_id=ctx.users["customer_6"].id, total_score=58.0, breakdown={"overdue_rentals": 25, "high_swap_frequency": 14, "battery_alert": 19}, last_updated=_ts(hours_ago=5)),
            RiskScore(user_id=ctx.users["customer_7"].id, total_score=72.0, breakdown={"duplicate_device": 35, "kyc_pending": 12, "behavioral": 25}, last_updated=_ts(days_ago=1)),
            RiskScore(user_id=ctx.users["customer_8"].id, total_score=41.0, breakdown={"kyc_pending": 18, "payment_failures": 8, "engagement_drop": 15}, last_updated=_ts(days_ago=1)),
            RiskScore(user_id=ctx.users["customer_9"].id, total_score=88.0, breakdown={"chargeback": 40, "duplicate_device": 28, "failed_login": 20}, last_updated=_ts(days_ago=1)),
            RiskScore(user_id=ctx.users["dealer_owner_3"].id, total_score=33.0, breakdown={"settlement_dispute": 14, "onboarding_gap": 19}, last_updated=_ts(days_ago=1)),
        ]
    )

    session.add_all(
        [
            FraudCheckLog(user_id=ctx.users["customer_5"].id, check_type="PAYMENT_PATTERN", status="WARN", details="Late fee pattern started increasing", created_at=_ts(days_ago=1)),
            FraudCheckLog(user_id=ctx.users["customer_6"].id, check_type="BATTERY_RETURN_BEHAVIOR", status="WARN", details="Two overdue returns in 30 days", created_at=_ts(days_ago=1)),
            FraudCheckLog(user_id=ctx.users["customer_7"].id, check_type="DEVICE_FINGERPRINT", status="FAIL", details="Shared device hash with suspended user", created_at=_ts(days_ago=4)),
            FraudCheckLog(user_id=ctx.users["customer_8"].id, check_type="KYC_LIVENESS", status="PASS", details="Manual override after resubmission", created_at=_ts(days_ago=2)),
            FraudCheckLog(user_id=ctx.users["customer_9"].id, check_type="CHARGEBACK_CHECK", status="FAIL", details="Chargeback under investigation", created_at=_ts(days_ago=1)),
            FraudCheckLog(user_id=ctx.users["dealer_owner_3"].id, check_type="SETTLEMENT_REVIEW", status="WARN", details="Launch-week credits require manual audit", created_at=_ts(days_ago=1)),
            FraudCheckLog(user_id=ctx.users["dealer_owner_2"].id, check_type="ACCOUNT_TENURE", status="PASS", details="Established dealer profile", created_at=_ts(days_ago=10)),
            FraudCheckLog(user_id=ctx.users["customer_1"].id, check_type="IP_REPUTATION", status="PASS", details="Stable commuter profile", created_at=_ts(days_ago=3)),
        ]
    )

    session.add_all(
        [
            Blacklist(type="IP", value="185.220.101.4", reason="Repeated suspicious login attempts"),
            Blacklist(type="DEVICE_ID", value="device-customer_9", reason="Linked to confirmed chargeback investigation"),
        ]
    )

    jobs = [
        ("settlement_batch", "SCHEDULED", "0 2 * * *", True, True, "Nightly settlement compilation"),
        ("battery_health_rollup", "SCHEDULED", "0 */4 * * *", True, True, "Battery health trend aggregation"),
        ("notification_retry", "SCHEDULED", "*/15 * * * *", True, False, "Retry failed notification deliveries"),
        ("bess_report_daily", "SCHEDULED", "15 1 * * *", True, False, "Generate daily BESS reports"),
    ]
    for job_name, job_type, cron, is_active, is_critical, description in jobs:
        session.add(
            BatchJob(
                job_name=job_name,
                job_type=job_type,
                schedule_cron=cron,
                is_active=is_active,
                is_critical=is_critical,
                max_retries=3,
                retry_delay_seconds=300,
                timeout_seconds=3600,
                alert_on_failure=True,
                alert_emails='["ops@powerfill.in"]',
                description=description,
                created_at=_ts(days_ago=20),
                updated_at=_ts(days_ago=1),
            )
        )
    session.flush()

    jobs_in_db = session.exec(select(BatchJob).order_by(BatchJob.id)).all()
    job_execution_specs = [
        (jobs_in_db[0], "exec-settlement-001", "COMPLETED", "SCHEDULED", ctx.users["admin_finance"].id, _ts(days_ago=1, hours_ago=2), _ts(days_ago=1, hours_ago=1), 14, 14, 0),
        (jobs_in_db[0], "exec-settlement-002", "FAILED", "SCHEDULED", ctx.users["admin_finance"].id, _ts(days_ago=3, hours_ago=2), _ts(days_ago=3, hours_ago=1), 12, 9, 3),
        (jobs_in_db[1], "exec-health-001", "COMPLETED", "SCHEDULED", ctx.users["admin_fleet"].id, _ts(hours_ago=8), _ts(hours_ago=7), 24, 24, 0),
        (jobs_in_db[1], "exec-health-002", "COMPLETED", "MANUAL", ctx.users["admin_fleet"].id, _ts(days_ago=2), _ts(days_ago=2, hours_ago=23), 24, 24, 0),
        (jobs_in_db[2], "exec-notify-001", "COMPLETED", "SCHEDULED", ctx.users["admin_support"].id, _ts(hours_ago=4), _ts(hours_ago=4), 18, 18, 0),
        (jobs_in_db[3], "exec-bess-001", "COMPLETED", "SCHEDULED", ctx.users["admin_fleet"].id, _ts(days_ago=1, hours_ago=3), _ts(days_ago=1, hours_ago=2), 2, 2, 0),
    ]
    session.add_all(
        [
            JobExecution(
                job_id=job.id,
                execution_id=execution_id,
                status=status,
                trigger_type=trigger_type,
                triggered_by=triggered_by,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=300 if completed_at else None,
                total_items=total_items,
                processed_items=processed_items,
                failed_items=failed_items,
                result_summary="Seeded execution record",
                error_message="Timeout while compiling one dealer ledger" if status == "FAILED" else None,
                execution_log="Execution log captured by seed",
                retry_count=1 if status == "FAILED" else 0,
                memory_usage_mb=256.0,
                cpu_usage_percent=32.0,
                created_at=started_at,
            )
            for job, execution_id, status, trigger_type, triggered_by, started_at, completed_at, total_items, processed_items, failed_items in job_execution_specs
        ]
    )

    session.flush()


def seed_bess(session: Session, ctx: SeedContext) -> None:
    from app.models.bess import BessEnergyLog, BessGridEvent, BessReport, BessUnit

    unit_specs = [
        ("bess_hyd", "Hyderabad Peak Shaving Block", "Madhapur Grid Edge", 250.0, 184.0, 120.0, "online", 73.6, 96.2),
        ("bess_wgl", "Warangal Backup Reserve", "Hanamkonda Franchise Yard", 180.0, 121.0, 90.0, "online", 67.2, 94.4),
    ]
    for key, name, location, capacity_kwh, current_charge_kwh, max_power_kw, status, soc, soh in unit_specs:
        unit = BessUnit(
            name=name,
            location=location,
            capacity_kwh=capacity_kwh,
            current_charge_kwh=current_charge_kwh,
            max_power_kw=max_power_kw,
            status=status,
            soc=soc,
            soh=soh,
            temperature_c=29.4 if key == "bess_hyd" else 28.1,
            cycle_count=112 if key == "bess_hyd" else 74,
            manufacturer="GridStor",
            model_number="GS-250-EDGE" if key == "bess_hyd" else "GS-180-EDGE",
            firmware_version="1.8.2",
            installed_at=_ts(days_ago=300),
            last_maintenance_at=_ts(days_ago=32),
            created_at=_ts(days_ago=300),
            updated_at=_ts(days_ago=1),
        )
        ctx.bess_units[key] = unit
        session.add(unit)
    session.flush()

    energy_logs = []
    for unit_key, unit in ctx.bess_units.items():
        for hour, power_kw, energy_kwh, soc_delta, source in [
            (22, 48.0, 48.0, +9.0, "grid"),
            (18, -36.0, 36.0, -7.0, "station"),
            (14, 28.0, 28.0, +5.0, "solar"),
            (10, -24.0, 24.0, -4.5, "station"),
            (6, 32.0, 32.0, +6.0, "grid"),
            (3, -18.0, 18.0, -3.0, "station"),
            (1, 12.0, 12.0, +2.0, "solar"),
            (0, -8.0, 8.0, -1.5, "grid_support"),
        ]:
            energy_logs.append(
                BessEnergyLog(
                    bess_unit_id=unit.id,
                    timestamp=_ts(hours_ago=hour) if hour else NOW,
                    power_kw=power_kw,
                    energy_kwh=energy_kwh,
                    soc_start=max(20.0, unit.soc - soc_delta),
                    soc_end=min(100.0, unit.soc),
                    source=source,
                    voltage=415.0 if power_kw >= 0 else 408.0,
                    current_a=82.0 if power_kw >= 0 else 71.0,
                    temperature_c=30.0 if unit_key == "bess_hyd" else 28.6,
                )
            )
    session.add_all(energy_logs)

    grid_events = [
        BessGridEvent(
            bess_unit_id=ctx.bess_units["bess_hyd"].id,
            event_type="peak_shaving",
            status="completed",
            start_time=_ts(hours_ago=5),
            end_time=_ts(hours_ago=3),
            target_power_kw=80.0,
            actual_power_kw=76.0,
            energy_kwh=152.0,
            revenue_earned=8240.0,
            grid_operator="TSSPDCL",
            notes="Evening peak offset for commercial feeder.",
            created_at=_ts(days_ago=1, hours_ago=4),
        ),
        BessGridEvent(
            bess_unit_id=ctx.bess_units["bess_hyd"].id,
            event_type="load_shifting",
            status="completed",
            start_time=_ts(days_ago=2, hours_ago=6),
            end_time=_ts(days_ago=2, hours_ago=3),
            target_power_kw=60.0,
            actual_power_kw=57.0,
            energy_kwh=128.0,
            revenue_earned=6120.0,
            grid_operator="TSSPDCL",
            notes="Shifted charger load into lower tariff window.",
            created_at=_ts(days_ago=2, hours_ago=6),
        ),
        BessGridEvent(
            bess_unit_id=ctx.bess_units["bess_wgl"].id,
            event_type="backup",
            status="completed",
            start_time=_ts(days_ago=3, hours_ago=5),
            end_time=_ts(days_ago=3, hours_ago=4),
            target_power_kw=45.0,
            actual_power_kw=43.0,
            energy_kwh=43.0,
            revenue_earned=0.0,
            grid_operator="TSNPDCL",
            notes="Franchise outage cover during utility interruption.",
            created_at=_ts(days_ago=3, hours_ago=5),
        ),
        BessGridEvent(
            bess_unit_id=ctx.bess_units["bess_wgl"].id,
            event_type="frequency_regulation",
            status="scheduled",
            start_time=_future(days_ahead=1, hours_ahead=2),
            target_power_kw=35.0,
            actual_power_kw=None,
            energy_kwh=None,
            revenue_earned=None,
            grid_operator="TSNPDCL",
            notes="Planned pilot participation for franchise region.",
            created_at=_ts(hours_ago=8),
        ),
    ]
    session.add_all(grid_events)

    session.add_all(
        [
            BessReport(
                bess_unit_id=ctx.bess_units["bess_hyd"].id,
                report_type="daily",
                period_start=_ts(days_ago=1, hours_ago=23),
                period_end=_ts(days_ago=1),
                total_charged_kwh=188.0,
                total_discharged_kwh=164.0,
                avg_efficiency=91.4,
                peak_power_kw=80.0,
                avg_soc=69.2,
                min_soc=48.0,
                max_soc=83.0,
                revenue=8240.0,
                cost=3180.0,
                grid_events_count=1,
                created_at=_ts(days_ago=1),
            ),
            BessReport(
                bess_unit_id=ctx.bess_units["bess_hyd"].id,
                report_type="weekly",
                period_start=_ts(days_ago=7),
                period_end=_ts(days_ago=1),
                total_charged_kwh=1240.0,
                total_discharged_kwh=1115.0,
                avg_efficiency=89.8,
                peak_power_kw=82.0,
                avg_soc=66.4,
                min_soc=44.0,
                max_soc=85.0,
                revenue=42840.0,
                cost=19410.0,
                grid_events_count=5,
                created_at=_ts(days_ago=1),
            ),
            BessReport(
                bess_unit_id=ctx.bess_units["bess_wgl"].id,
                report_type="daily",
                period_start=_ts(days_ago=1, hours_ago=23),
                period_end=_ts(days_ago=1),
                total_charged_kwh=132.0,
                total_discharged_kwh=118.0,
                avg_efficiency=90.6,
                peak_power_kw=46.0,
                avg_soc=62.1,
                min_soc=41.0,
                max_soc=74.0,
                revenue=0.0,
                cost=2140.0,
                grid_events_count=0,
                created_at=_ts(days_ago=1),
            ),
            BessReport(
                bess_unit_id=ctx.bess_units["bess_wgl"].id,
                report_type="monthly",
                period_start=_ts(days_ago=30),
                period_end=_ts(days_ago=1),
                total_charged_kwh=3960.0,
                total_discharged_kwh=3524.0,
                avg_efficiency=88.9,
                peak_power_kw=50.0,
                avg_soc=64.8,
                min_soc=38.0,
                max_soc=79.0,
                revenue=9150.0,
                cost=16420.0,
                grid_events_count=9,
                created_at=_ts(days_ago=1),
            ),
        ]
    )

    session.flush()


def seed_analytics_tables(session: Session, ctx: SeedContext) -> None:
    from app.models.analytics import ChurnPrediction, DemandForecast, PricingRecommendation
    from app.models.revenue_report import RevenueReport

    forecast_rows = []
    demand_stations = [
        ("jubilee_hills_hub", "Jubilee Hills Hub"),
        ("hitech_city_nexus", "HITEC City Nexus"),
        ("warangal_gateway", "Warangal Gateway"),
    ]
    for offset in range(7):
        forecast_date = (NOW + timedelta(days=offset)).date()
        for station_key, station_name in demand_stations:
            base = 24 if station_key != "warangal_gateway" else 12
            forecast_rows.append(
                DemandForecast(
                    forecast_type="STATION",
                    entity_id=ctx.stations[station_key].id,
                    entity_name=station_name,
                    forecast_date=forecast_date,
                    forecast_hour=None,
                    predicted_rentals=base + offset,
                    predicted_swaps=max(4, base // 5),
                    predicted_purchases=1 if station_key != "warangal_gateway" else 0,
                    confidence_level=0.91,
                    lower_bound=max(0, base - 3),
                    upper_bound=base + 5,
                    actual_rentals=base - 1 if offset == 0 else None,
                    actual_swaps=base // 6 if offset == 0 else None,
                    actual_purchases=1 if offset == 0 and station_key == "hitech_city_nexus" else None,
                    forecast_accuracy=94.2 if offset == 0 else None,
                    model_version="admin-showcase-v1",
                    model_features={"weather": "clear", "commuter_peak": True},
                    created_at=_ts(hours_ago=4),
                )
            )
    session.add_all(forecast_rows)

    session.add_all(
        [
            ChurnPrediction(
                user_id=ctx.users["customer_5"].id,
                churn_probability=0.68,
                churn_risk_level="HIGH",
                days_since_last_activity=2,
                days_since_last_rental=2,
                total_rentals=14,
                total_spend=5240.0,
                app_opens_last_30_days=9,
                searches_last_30_days=5,
                support_tickets_last_30_days=1,
                has_unresolved_issues=True,
                has_negative_reviews=False,
                payment_failures_count=0,
                top_churn_factors={"late_fees": 0.34, "support_issue": 0.28},
                recommended_actions={"waive_fee": True, "send_offer": True},
                prediction_date=NOW.date(),
                created_at=_ts(hours_ago=6),
            ),
            ChurnPrediction(
                user_id=ctx.users["customer_6"].id,
                churn_probability=0.72,
                churn_risk_level="HIGH",
                days_since_last_activity=1,
                days_since_last_rental=1,
                total_rentals=18,
                total_spend=6410.0,
                app_opens_last_30_days=11,
                searches_last_30_days=7,
                support_tickets_last_30_days=1,
                has_unresolved_issues=True,
                has_negative_reviews=False,
                payment_failures_count=1,
                top_churn_factors={"battery_health": 0.31, "delivery_delay": 0.23},
                recommended_actions={"priority_support": True},
                prediction_date=NOW.date(),
                created_at=_ts(hours_ago=6),
            ),
            ChurnPrediction(
                user_id=ctx.users["customer_7"].id,
                churn_probability=0.55,
                churn_risk_level="MEDIUM",
                days_since_last_activity=5,
                days_since_last_rental=26,
                total_rentals=6,
                total_spend=2120.0,
                app_opens_last_30_days=6,
                searches_last_30_days=3,
                support_tickets_last_30_days=1,
                has_unresolved_issues=True,
                has_negative_reviews=False,
                payment_failures_count=0,
                top_churn_factors={"kyc_delay": 0.42},
                recommended_actions={"manual_callback": True},
                prediction_date=NOW.date(),
                created_at=_ts(hours_ago=6),
            ),
            ChurnPrediction(
                user_id=ctx.users["customer_8"].id,
                churn_probability=0.49,
                churn_risk_level="MEDIUM",
                days_since_last_activity=7,
                days_since_last_rental=34,
                total_rentals=4,
                total_spend=1680.0,
                app_opens_last_30_days=4,
                searches_last_30_days=2,
                support_tickets_last_30_days=1,
                has_unresolved_issues=False,
                has_negative_reviews=False,
                payment_failures_count=0,
                top_churn_factors={"kyc_pending": 0.37},
                recommended_actions={"send_kyc_help": True},
                prediction_date=NOW.date(),
                created_at=_ts(hours_ago=6),
            ),
            ChurnPrediction(
                user_id=ctx.users["customer_9"].id,
                churn_probability=0.91,
                churn_risk_level="CRITICAL",
                days_since_last_activity=12,
                days_since_last_rental=12,
                total_rentals=9,
                total_spend=3980.0,
                app_opens_last_30_days=1,
                searches_last_30_days=0,
                support_tickets_last_30_days=1,
                has_unresolved_issues=True,
                has_negative_reviews=True,
                payment_failures_count=2,
                top_churn_factors={"chargeback": 0.52, "duplicate_device": 0.33},
                recommended_actions={"block_account": True},
                did_churn=False,
                prediction_date=NOW.date(),
                created_at=_ts(hours_ago=6),
            ),
            ChurnPrediction(
                user_id=ctx.users["customer_10"].id,
                churn_probability=0.28,
                churn_risk_level="LOW",
                days_since_last_activity=1,
                days_since_last_rental=44,
                total_rentals=12,
                total_spend=4510.0,
                app_opens_last_30_days=16,
                searches_last_30_days=8,
                support_tickets_last_30_days=1,
                has_unresolved_issues=False,
                has_negative_reviews=False,
                payment_failures_count=0,
                top_churn_factors={"recent_return_request": 0.19},
                recommended_actions={"send_loyalty_offer": False},
                prediction_date=NOW.date(),
                created_at=_ts(hours_ago=6),
            ),
        ]
    )

    session.add_all(
        [
            PricingRecommendation(
                recommendation_type="RENTAL",
                entity_type="STATION",
                entity_id=ctx.stations["hitech_city_nexus"].id,
                current_price=179.0,
                recommended_price=189.0,
                price_change_percentage=5.6,
                demand_factor=1.14,
                competition_factor=0.98,
                seasonality_factor=1.03,
                inventory_factor=0.94,
                expected_revenue_change_percentage=8.2,
                expected_volume_change_percentage=-1.5,
                confidence_score=86.0,
                risk_level="LOW",
                valid_from=_future(hours_ahead=6),
                valid_until=_future(days_ahead=7),
                status="PENDING",
                created_at=_ts(hours_ago=4),
            ),
            PricingRecommendation(
                recommendation_type="SWAP",
                entity_type="STATION",
                entity_id=ctx.stations["uppal_transit_point"].id,
                current_price=49.0,
                recommended_price=59.0,
                price_change_percentage=20.4,
                demand_factor=1.21,
                competition_factor=1.02,
                seasonality_factor=1.04,
                inventory_factor=0.89,
                expected_revenue_change_percentage=12.1,
                expected_volume_change_percentage=-3.4,
                confidence_score=78.0,
                risk_level="MEDIUM",
                valid_from=_future(hours_ahead=12),
                valid_until=_future(days_ahead=5),
                status="APPROVED",
                implemented_at=_ts(hours_ago=1),
                implemented_by=ctx.users["admin_finance"].id,
                created_at=_ts(hours_ago=5),
            ),
            PricingRecommendation(
                recommendation_type="PURCHASE",
                entity_type="BATTERY_MODEL",
                entity_id=ctx.battery_skus["long_range"].id,
                current_price=16250.0,
                recommended_price=15899.0,
                price_change_percentage=-2.16,
                demand_factor=0.94,
                competition_factor=0.97,
                seasonality_factor=1.0,
                inventory_factor=1.12,
                expected_revenue_change_percentage=5.4,
                expected_volume_change_percentage=8.2,
                confidence_score=81.0,
                risk_level="LOW",
                valid_from=_future(days_ahead=1),
                valid_until=_future(days_ahead=14),
                status="PENDING",
                created_at=_ts(hours_ago=4),
            ),
            PricingRecommendation(
                recommendation_type="LATE_FEE",
                entity_type="OVERALL",
                entity_id=None,
                current_price=120.0,
                recommended_price=110.0,
                price_change_percentage=-8.33,
                demand_factor=0.88,
                competition_factor=1.0,
                seasonality_factor=1.0,
                inventory_factor=1.0,
                expected_revenue_change_percentage=-2.8,
                expected_volume_change_percentage=4.3,
                confidence_score=66.0,
                risk_level="MEDIUM",
                valid_from=_future(days_ahead=3),
                valid_until=_future(days_ahead=20),
                status="REVIEW",
                created_at=_ts(hours_ago=4),
            ),
        ]
    )

    session.add_all(
        [
            RevenueReport(
                report_type="daily",
                period_start=(_ts(days_ago=1, hours_ago=23)).date(),
                period_end=(_ts(days_ago=1)).date(),
                total_revenue=4285.0,
                total_transactions=12,
                avg_transaction_value=357.1,
                total_refunds=0.0,
                net_revenue=4285.0,
                growth_percentage=8.4,
                breakdown_by_dealer={"metro_energy": 1820.0, "city_charge": 1435.0, "hanamkonda_mobility": 1030.0},
                breakdown_by_station={"Jubilee Hills Hub": 910.0, "HITEC City Nexus": 1320.0, "Uppal Transit Point": 845.0},
                breakdown_by_category={"rental": 3010.0, "deposit": 1199.0, "swap": 76.0},
                breakdown_by_source={"wallet": 920.0, "upi": 2526.0, "card": 839.0},
                created_at=_ts(hours_ago=2),
            ),
            RevenueReport(
                report_type="weekly",
                period_start=(_ts(days_ago=7)).date(),
                period_end=(_ts(days_ago=1)).date(),
                total_revenue=22784.0,
                total_transactions=44,
                avg_transaction_value=517.8,
                total_refunds=189.0,
                net_revenue=22595.0,
                growth_percentage=11.2,
                breakdown_by_dealer={"metro_energy": 9240.0, "city_charge": 7112.0, "hanamkonda_mobility": 2310.0},
                breakdown_by_station={"Jubilee Hills Hub": 5120.0, "HITEC City Nexus": 6340.0, "Uppal Transit Point": 4850.0, "Warangal Gateway": 2310.0},
                breakdown_by_category={"rental": 6820.0, "deposit": 8994.0, "swap": 108.0, "purchase": 16250.0},
                breakdown_by_source={"wallet": 1420.0, "upi": 9874.0, "card": 11490.0},
                created_at=_ts(hours_ago=2),
            ),
            RevenueReport(
                report_type="monthly",
                period_start=(_ts(days_ago=30)).date(),
                period_end=NOW.date(),
                total_revenue=46824.0,
                total_transactions=92,
                avg_transaction_value=508.9,
                total_refunds=378.0,
                net_revenue=46446.0,
                growth_percentage=14.7,
                breakdown_by_dealer={"metro_energy": 18410.0, "city_charge": 14320.0, "hanamkonda_mobility": 5120.0},
                breakdown_by_station={"Jubilee Hills Hub": 11040.0, "HITEC City Nexus": 12890.0, "Kukatpally Exchange": 7240.0, "Uppal Transit Point": 6864.0},
                breakdown_by_category={"rental": 11823.0, "deposit": 8994.0, "swap": 108.0, "purchase": 25899.0},
                breakdown_by_source={"wallet": 4120.0, "upi": 18684.0, "card": 24020.0},
                created_at=_ts(hours_ago=2),
            ),
        ]
    )

    session.flush()


def finalize_station_metrics(session: Session, ctx: SeedContext) -> None:
    from app.models.battery import Battery, BatteryStatus
    from app.models.station import StationSlot

    slot_rows = session.exec(select(StationSlot)).all()
    slot_counts: dict[int, int] = {}
    for slot in slot_rows:
        if slot.status == "empty":
            slot_counts[slot.station_id] = slot_counts.get(slot.station_id, 0) + 1

    batteries = session.exec(select(Battery)).all()
    availability_counts: dict[int, int] = {}
    for battery in batteries:
        if battery.station_id and battery.status == BatteryStatus.AVAILABLE:
            availability_counts[battery.station_id] = availability_counts.get(battery.station_id, 0) + 1

    for station in ctx.stations.values():
        station.available_batteries = availability_counts.get(station.id, 0)
        station.available_slots = slot_counts.get(station.id, 0)
        station.updated_at = _ts(hours_ago=1)
        session.add(station)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a presentation-grade admin portal dataset.")
    parser.add_argument("--database-url", help="Target database URL. Defaults to DATABASE_URL.")
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Skip `alembic upgrade head` and seed the current schema as-is.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip seeding and only run contract verification against the target database.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    database_url = resolve_database_url(args.database_url)
    ensure_seed_runtime_env(database_url)

    if not args.verify_only and not args.skip_migrate:
        run_migrations(database_url)

    if not args.verify_only:
        engine = create_engine(database_url, future=True)
        with Session(engine) as session:
            assert_database_empty(session)
            ctx = seed_showcase_data(session)
            verify_business_metrics(session, ctx)
            session.commit()

    verify_contract(database_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
