from __future__ import annotations
import re
import socket
import time

from sqlalchemy import event, inspect, pool, text
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel, Session, create_engine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _resolve_ipv4_hostaddr(database_url: str) -> str | None:
    parsed_url = make_url(database_url)
    host = parsed_url.host
    if not host:
        return None
    port = parsed_url.port or 5432
    try:
        candidates = socket.getaddrinfo(
            host,
            port,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
    except Exception as exc:
        logger.warning("db.hostaddr.resolve_failed", host=host, error=str(exc))
        return None

    for _, _, _, _, sockaddr in candidates:
        if sockaddr and sockaddr[0]:
            return str(sockaddr[0])
    return None


def _build_engine():
    """
    Build the SQLAlchemy engine with the best pooling strategy:
    - SQLite: NullPool + WAL mode (for dev / APScheduler)
    - PostgreSQL: QueuePool with LIFO, connect timeout, optional SSL
    """
    database_url = settings.DATABASE_URL
    engine_kwargs = {
        "echo": settings.SQLALCHEMY_ECHO,
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
    }

    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        engine_kwargs["poolclass"] = pool.NullPool
    else:
        connect_args = {
            "connect_timeout": settings.DATABASE_CONNECT_TIMEOUT_SECONDS,
        }
        if settings.DATABASE_SSL_MODE:
            connect_args["sslmode"] = settings.DATABASE_SSL_MODE
        parsed_url = make_url(database_url)
        if parsed_url.drivername.startswith("postgresql"):
            connect_args.update({
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5
            })
            configured_hostaddr = (settings.DATABASE_HOSTADDR or "").strip()
            if configured_hostaddr:
                connect_args["hostaddr"] = configured_hostaddr
            elif settings.DATABASE_PREFER_IPV4:
                resolved_hostaddr = _resolve_ipv4_hostaddr(database_url)
                if resolved_hostaddr:
                    connect_args["hostaddr"] = resolved_hostaddr

        engine_kwargs.update({
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_recycle": settings.DB_POOL_RECYCLE,
            "pool_use_lifo": settings.DB_POOL_USE_LIFO,
            "connect_args": connect_args,
        })

    return create_engine(database_url, **engine_kwargs)


engine = _build_engine()


# ── Compatibility schema patching ──────────────────────────────────────────

def ensure_roles_schema_compatibility() -> None:
    """
    Backfill RBAC role columns if migrations were skipped.
    This keeps auth endpoints alive on partially-migrated databases.
    """
    parsed_url = make_url(settings.DATABASE_URL)
    driver = parsed_url.drivername
    if not (driver.startswith("postgresql") or driver.startswith("sqlite")):
        return

    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("roles"):
            return

        cols = {col["name"] for col in inspector.get_columns("roles")}
        statements: list[str] = []
        patched_columns: list[str] = []

        if driver.startswith("postgresql"):
            if "is_custom_role" not in cols:
                statements.append(
                    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS is_custom_role BOOLEAN NOT NULL DEFAULT FALSE"
                )
                patched_columns.append("is_custom_role")
            if "scope_owner" not in cols:
                statements.append(
                    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS scope_owner VARCHAR NOT NULL DEFAULT 'global'"
                )
                patched_columns.append("scope_owner")
        else:  # sqlite
            if "is_custom_role" not in cols:
                statements.append(
                    "ALTER TABLE roles ADD COLUMN is_custom_role BOOLEAN NOT NULL DEFAULT 0"
                )
                patched_columns.append("is_custom_role")
            if "scope_owner" not in cols:
                statements.append(
                    "ALTER TABLE roles ADD COLUMN scope_owner VARCHAR NOT NULL DEFAULT 'global'"
                )
                patched_columns.append("scope_owner")

        for statement in statements:
            conn.execute(text(statement))

        if statements:
            logger.info(
                "schema.roles_compatibility_patch_applied",
                patched_columns=patched_columns,
            )


def ensure_warehouses_schema_compatibility() -> None:
    """
    Backfill warehouse columns if migrations were skipped.
    Currently patches `warehouses.capacity` used by logistics endpoints.
    """
    parsed_url = make_url(settings.DATABASE_URL)
    driver = parsed_url.drivername
    if not (driver.startswith("postgresql") or driver.startswith("sqlite")):
        return

    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("warehouses"):
            return

        cols = {col["name"] for col in inspector.get_columns("warehouses")}
        if "capacity" in cols:
            return

        if driver.startswith("postgresql"):
            conn.execute(
                text(
                    "ALTER TABLE warehouses "
                    "ADD COLUMN IF NOT EXISTS capacity INTEGER NOT NULL DEFAULT 100"
                )
            )
        else:  # sqlite
            conn.execute(
                text(
                    "ALTER TABLE warehouses "
                    "ADD COLUMN capacity INTEGER NOT NULL DEFAULT 100"
                )
            )

        logger.info(
            "schema.warehouses_compatibility_patch_applied",
            patched_columns=["capacity"],
        )


def ensure_transactions_schema_compatibility() -> None:
    """
    Backfill newer `transactions` columns when deployments run on
    partially-migrated databases.
    """
    parsed_url = make_url(settings.DATABASE_URL)
    driver = parsed_url.drivername
    if not (driver.startswith("postgresql") or driver.startswith("sqlite")):
        return

    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("transactions"):
            return

        existing_columns = {
            column["name"] for column in inspector.get_columns("transactions")
        }

        column_types_postgres = {
            "type": "VARCHAR",
            "category": "VARCHAR",
            "balance_after": "DOUBLE PRECISION",
            "reference_type": "VARCHAR",
            "reference_id": "VARCHAR",
            "razorpay_payment_id": "VARCHAR",
        }
        column_types_sqlite = {
            "type": "VARCHAR",
            "category": "VARCHAR",
            "balance_after": "REAL",
            "reference_type": "VARCHAR",
            "reference_id": "VARCHAR",
            "razorpay_payment_id": "VARCHAR",
        }

        patched_columns: list[str] = []
        for column_name, column_type in (
            column_types_postgres.items()
            if driver.startswith("postgresql")
            else column_types_sqlite.items()
        ):
            if column_name in existing_columns:
                continue
            if driver.startswith("postgresql"):
                statement = (
                    "ALTER TABLE transactions "
                    f'ADD COLUMN IF NOT EXISTS "{column_name}" {column_type}'
                )
            else:
                statement = (
                    "ALTER TABLE transactions "
                    f'ADD COLUMN "{column_name}" {column_type}'
                )
            conn.execute(text(statement))
            patched_columns.append(column_name)

        if patched_columns:
            logger.info(
                "schema.transactions_compatibility_patch_applied",
                patched_columns=patched_columns,
            )


def ensure_users_schema_compatibility() -> None:
    """
    Backfill user columns expected by current auth/session code when running
    against partially-migrated databases.
    """
    parsed_url = make_url(settings.DATABASE_URL)
    driver = parsed_url.drivername
    if not (driver.startswith("postgresql") or driver.startswith("sqlite")):
        return

    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("users"):
            return

        existing_columns = {
            column["name"] for column in inspector.get_columns("users")
        }

        column_types_postgres = {
            "biometric_login_enabled": "BOOLEAN NOT NULL DEFAULT FALSE",
            "security_question": "VARCHAR",
            "security_answer": "VARCHAR",
            "reset_token": "VARCHAR",
            "reset_token_expires": "TIMESTAMP WITH TIME ZONE",
            "last_login": "TIMESTAMP WITH TIME ZONE",
        }
        column_types_sqlite = {
            "biometric_login_enabled": "BOOLEAN NOT NULL DEFAULT 0",
            "security_question": "VARCHAR",
            "security_answer": "VARCHAR",
            "reset_token": "VARCHAR",
            "reset_token_expires": "TIMESTAMP",
            "last_login": "TIMESTAMP",
        }

        patched_columns: list[str] = []
        for column_name, column_type in (
            column_types_postgres.items()
            if driver.startswith("postgresql")
            else column_types_sqlite.items()
        ):
            if column_name in existing_columns:
                continue
            if driver.startswith("postgresql"):
                statement = (
                    "ALTER TABLE users "
                    f'ADD COLUMN IF NOT EXISTS "{column_name}" {column_type}'
                )
            else:
                statement = (
                    "ALTER TABLE users "
                    f'ADD COLUMN "{column_name}" {column_type}'
                )
            conn.execute(text(statement))
            patched_columns.append(column_name)

        # Preserve historical login timestamps when older schemas used last_login_at.
        if "last_login" in patched_columns and "last_login_at" in existing_columns:
            conn.execute(
                text(
                    "UPDATE users SET last_login = last_login_at "
                    "WHERE last_login IS NULL AND last_login_at IS NOT NULL"
                )
            )

        if patched_columns:
            if driver.startswith("postgresql"):
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_users_reset_token ON users (reset_token)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_users_last_login ON users (last_login)"
                    )
                )
            logger.info(
                "schema.users_compatibility_patch_applied",
                patched_columns=patched_columns,
            )


def ensure_runtime_tables_compatibility() -> None:
    """
    Ensure a minimal set of runtime-critical tables exists on partially
    migrated databases so customer flows do not fail with 500.
    """
    parsed_url = make_url(settings.DATABASE_URL)
    driver = parsed_url.drivername
    if not (driver.startswith("postgresql") or driver.startswith("sqlite")):
        return

    from app.models.catalog import CatalogProduct, CatalogProductImage, CatalogProductVariant
    from app.models.oauth import BlacklistedToken

    required_tables = {
        "blacklisted_tokens": BlacklistedToken.__table__,
        "products": CatalogProduct.__table__,
        "product_images": CatalogProductImage.__table__,
        "product_variants": CatalogProductVariant.__table__,
    }

    with engine.begin() as conn:
        inspector = inspect(conn)
        missing = [
            table_name
            for table_name in required_tables
            if not inspector.has_table(table_name)
        ]
        if not missing:
            return

        SQLModel.metadata.create_all(
            bind=conn,
            tables=[required_tables[table_name] for table_name in missing],
            checkfirst=True,
        )
        logger.warning(
            "schema.runtime_table_compatibility_patch_applied",
            created_tables=missing,
        )


def _create_table_if_missing(
    *,
    conn,
    inspector,
    driver: str,
    table_name: str,
    postgres_sql: str,
    sqlite_sql: str,
) -> bool:
    if inspector.has_table(table_name):
        return False

    statement = postgres_sql if driver.startswith("postgresql") else sqlite_sql
    conn.execute(text(statement))
    return True


def _add_columns_if_missing(
    *,
    conn,
    inspector,
    driver: str,
    table_name: str,
    columns: list[tuple[str, str, str]],
) -> list[str]:
    if not inspector.has_table(table_name):
        return []

    existing = {column["name"] for column in inspector.get_columns(table_name)}
    patched: list[str] = []

    for column_name, postgres_def, sqlite_def in columns:
        if column_name in existing:
            continue
        if driver.startswith("postgresql"):
            statement = (
                f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS {postgres_def}'
            )
        else:
            statement = f'ALTER TABLE "{table_name}" ADD COLUMN {sqlite_def}'
        conn.execute(text(statement))
        existing.add(column_name)
        patched.append(f"{table_name}.{column_name}")

    return patched


def ensure_admin_schema_compatibility() -> None:
    """
    Backfill admin-facing schema drift observed in long-lived dev databases.
    Prevents 500s in stations/stock/health/dealers/admin-groups pages when
    partial migrations left missing tables/columns behind.
    """
    parsed_url = make_url(settings.DATABASE_URL)
    driver = parsed_url.drivername
    if not (driver.startswith("postgresql") or driver.startswith("sqlite")):
        return

    with engine.begin() as conn:
        inspector = inspect(conn)
        created_tables: list[str] = []

        if _create_table_if_missing(
            conn=conn,
            inspector=inspector,
            driver=driver,
            table_name="maintenance_records",
            postgres_sql=(
                """
                CREATE TABLE maintenance_records (
                    id SERIAL PRIMARY KEY,
                    entity_type VARCHAR NOT NULL,
                    entity_id INTEGER NOT NULL,
                    technician_id INTEGER NOT NULL,
                    maintenance_type VARCHAR NOT NULL,
                    description TEXT NOT NULL,
                    cost DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    parts_replaced TEXT,
                    status VARCHAR NOT NULL DEFAULT 'completed',
                    performed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            ),
            sqlite_sql=(
                """
                CREATE TABLE maintenance_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type VARCHAR NOT NULL,
                    entity_id INTEGER NOT NULL,
                    technician_id INTEGER NOT NULL,
                    maintenance_type VARCHAR NOT NULL,
                    description TEXT NOT NULL,
                    cost REAL NOT NULL DEFAULT 0.0,
                    parts_replaced TEXT,
                    status VARCHAR NOT NULL DEFAULT 'completed',
                    performed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            ),
        ):
            created_tables.append("maintenance_records")

        if _create_table_if_missing(
            conn=conn,
            inspector=inspector,
            driver=driver,
            table_name="commission_logs",
            postgres_sql=(
                """
                CREATE TABLE commission_logs (
                    id SERIAL PRIMARY KEY,
                    transaction_id INTEGER,
                    dealer_id INTEGER,
                    vendor_id INTEGER,
                    amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    status VARCHAR NOT NULL DEFAULT 'pending',
                    settlement_id INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            ),
            sqlite_sql=(
                """
                CREATE TABLE commission_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id INTEGER,
                    dealer_id INTEGER,
                    vendor_id INTEGER,
                    amount REAL NOT NULL DEFAULT 0.0,
                    status VARCHAR NOT NULL DEFAULT 'pending',
                    settlement_id INTEGER,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            ),
        ):
            created_tables.append("commission_logs")

        if _create_table_if_missing(
            conn=conn,
            inspector=inspector,
            driver=driver,
            table_name="commission_configs",
            postgres_sql=(
                """
                CREATE TABLE commission_configs (
                    id SERIAL PRIMARY KEY,
                    dealer_id INTEGER,
                    vendor_id INTEGER,
                    transaction_type VARCHAR NOT NULL,
                    percentage DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    flat_fee DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    effective_from TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    effective_until TIMESTAMP WITH TIME ZONE,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            ),
            sqlite_sql=(
                """
                CREATE TABLE commission_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dealer_id INTEGER,
                    vendor_id INTEGER,
                    transaction_type VARCHAR NOT NULL,
                    percentage REAL NOT NULL DEFAULT 0.0,
                    flat_fee REAL NOT NULL DEFAULT 0.0,
                    effective_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    effective_until TIMESTAMP,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            ),
        ):
            created_tables.append("commission_configs")

        if _create_table_if_missing(
            conn=conn,
            inspector=inspector,
            driver=driver,
            table_name="swap_sessions",
            postgres_sql=(
                """
                CREATE TABLE swap_sessions (
                    id SERIAL PRIMARY KEY,
                    rental_id INTEGER,
                    user_id INTEGER,
                    station_id INTEGER,
                    old_battery_id INTEGER,
                    new_battery_id INTEGER,
                    old_battery_soc DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    new_battery_soc DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    swap_amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    currency VARCHAR NOT NULL DEFAULT 'INR',
                    status VARCHAR NOT NULL DEFAULT 'initiated',
                    payment_status VARCHAR NOT NULL DEFAULT 'pending',
                    error_message VARCHAR,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMP WITH TIME ZONE
                )
                """
            ),
            sqlite_sql=(
                """
                CREATE TABLE swap_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rental_id INTEGER,
                    user_id INTEGER,
                    station_id INTEGER,
                    old_battery_id INTEGER,
                    new_battery_id INTEGER,
                    old_battery_soc REAL NOT NULL DEFAULT 0.0,
                    new_battery_soc REAL NOT NULL DEFAULT 0.0,
                    swap_amount REAL NOT NULL DEFAULT 0.0,
                    currency VARCHAR NOT NULL DEFAULT 'INR',
                    status VARCHAR NOT NULL DEFAULT 'initiated',
                    payment_status VARCHAR NOT NULL DEFAULT 'pending',
                    error_message VARCHAR,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
                """
            ),
        ):
            created_tables.append("swap_sessions")

        if _create_table_if_missing(
            conn=conn,
            inspector=inspector,
            driver=driver,
            table_name="station_stock_configs",
            postgres_sql=(
                """
                CREATE TABLE station_stock_configs (
                    id SERIAL PRIMARY KEY,
                    station_id INTEGER NOT NULL UNIQUE,
                    max_capacity INTEGER NOT NULL DEFAULT 50,
                    reorder_point INTEGER NOT NULL DEFAULT 10,
                    reorder_quantity INTEGER NOT NULL DEFAULT 20,
                    manager_email VARCHAR,
                    manager_phone VARCHAR,
                    updated_by INTEGER,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            ),
            sqlite_sql=(
                """
                CREATE TABLE station_stock_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_id INTEGER NOT NULL UNIQUE,
                    max_capacity INTEGER NOT NULL DEFAULT 50,
                    reorder_point INTEGER NOT NULL DEFAULT 10,
                    reorder_quantity INTEGER NOT NULL DEFAULT 20,
                    manager_email VARCHAR,
                    manager_phone VARCHAR,
                    updated_by INTEGER,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            ),
        ):
            created_tables.append("station_stock_configs")

        if _create_table_if_missing(
            conn=conn,
            inspector=inspector,
            driver=driver,
            table_name="stock_alert_dismissals",
            postgres_sql=(
                """
                CREATE TABLE stock_alert_dismissals (
                    id SERIAL PRIMARY KEY,
                    station_id INTEGER NOT NULL,
                    reason VARCHAR NOT NULL,
                    dismissed_by INTEGER NOT NULL,
                    dismissed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE
                )
                """
            ),
            sqlite_sql=(
                """
                CREATE TABLE stock_alert_dismissals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_id INTEGER NOT NULL,
                    reason VARCHAR NOT NULL,
                    dismissed_by INTEGER NOT NULL,
                    dismissed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN NOT NULL DEFAULT 1
                )
                """
            ),
        ):
            created_tables.append("stock_alert_dismissals")

        if _create_table_if_missing(
            conn=conn,
            inspector=inspector,
            driver=driver,
            table_name="menus",
            postgres_sql=(
                """
                CREATE TABLE menus (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    display_name VARCHAR NOT NULL,
                    route VARCHAR,
                    icon VARCHAR,
                    parent_id INTEGER,
                    menu_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    created_by VARCHAR,
                    modified_by VARCHAR
                )
                """
            ),
            sqlite_sql=(
                """
                CREATE TABLE menus (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR NOT NULL,
                    display_name VARCHAR NOT NULL,
                    route VARCHAR,
                    icon VARCHAR,
                    parent_id INTEGER,
                    menu_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR,
                    modified_by VARCHAR
                )
                """
            ),
        ):
            created_tables.append("menus")

        if _create_table_if_missing(
            conn=conn,
            inspector=inspector,
            driver=driver,
            table_name="role_rights",
            postgres_sql=(
                """
                CREATE TABLE role_rights (
                    id SERIAL PRIMARY KEY,
                    role_id INTEGER NOT NULL,
                    menu_id INTEGER NOT NULL,
                    can_view BOOLEAN NOT NULL DEFAULT FALSE,
                    can_create BOOLEAN NOT NULL DEFAULT FALSE,
                    can_edit BOOLEAN NOT NULL DEFAULT FALSE,
                    can_delete BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    created_by VARCHAR,
                    modified_by VARCHAR
                )
                """
            ),
            sqlite_sql=(
                """
                CREATE TABLE role_rights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_id INTEGER NOT NULL,
                    menu_id INTEGER NOT NULL,
                    can_view BOOLEAN NOT NULL DEFAULT 0,
                    can_create BOOLEAN NOT NULL DEFAULT 0,
                    can_edit BOOLEAN NOT NULL DEFAULT 0,
                    can_delete BOOLEAN NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR,
                    modified_by VARCHAR
                )
                """
            ),
        ):
            created_tables.append("role_rights")

        if _create_table_if_missing(
            conn=conn,
            inspector=inspector,
            driver=driver,
            table_name="staff_profiles",
            postgres_sql=(
                """
                CREATE TABLE staff_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL UNIQUE,
                    dealer_id INTEGER,
                    station_id INTEGER,
                    staff_type VARCHAR NOT NULL,
                    employment_id VARCHAR NOT NULL UNIQUE,
                    reporting_manager_id INTEGER,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            ),
            sqlite_sql=(
                """
                CREATE TABLE staff_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    dealer_id INTEGER,
                    station_id INTEGER,
                    staff_type VARCHAR NOT NULL,
                    employment_id VARCHAR NOT NULL UNIQUE,
                    reporting_manager_id INTEGER,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            ),
        ):
            created_tables.append("staff_profiles")

        if _create_table_if_missing(
            conn=conn,
            inspector=inspector,
            driver=driver,
            table_name="wallets",
            postgres_sql=(
                """
                CREATE TABLE wallets (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL UNIQUE,
                    balance DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    cashback_balance DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    currency VARCHAR NOT NULL DEFAULT 'INR',
                    is_frozen BOOLEAN NOT NULL DEFAULT FALSE,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            ),
            sqlite_sql=(
                """
                CREATE TABLE wallets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    balance REAL NOT NULL DEFAULT 0.0,
                    cashback_balance REAL NOT NULL DEFAULT 0.0,
                    currency VARCHAR NOT NULL DEFAULT 'INR',
                    is_frozen BOOLEAN NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            ),
        ):
            created_tables.append("wallets")

        if _create_table_if_missing(
            conn=conn,
            inspector=inspector,
            driver=driver,
            table_name="admin_groups",
            postgres_sql=(
                """
                CREATE TABLE admin_groups (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR NOT NULL UNIQUE,
                    description TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            ),
            sqlite_sql=(
                """
                CREATE TABLE admin_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR NOT NULL UNIQUE,
                    description TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            ),
        ):
            created_tables.append("admin_groups")

        # Refresh inspector after potential CREATE TABLE operations.
        inspector = inspect(conn)
        patched_columns: list[str] = []

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="stations",
                columns=[
                    ("max_capacity", '"max_capacity" INTEGER', '"max_capacity" INTEGER'),
                    ("charger_type", '"charger_type" VARCHAR', '"charger_type" VARCHAR'),
                    (
                        "temperature_control",
                        '"temperature_control" BOOLEAN NOT NULL DEFAULT FALSE',
                        '"temperature_control" BOOLEAN NOT NULL DEFAULT 0',
                    ),
                    ("safety_features", '"safety_features" VARCHAR', '"safety_features" VARCHAR'),
                    (
                        "available_batteries",
                        '"available_batteries" INTEGER NOT NULL DEFAULT 0',
                        '"available_batteries" INTEGER NOT NULL DEFAULT 0',
                    ),
                    (
                        "available_slots",
                        '"available_slots" INTEGER NOT NULL DEFAULT 0',
                        '"available_slots" INTEGER NOT NULL DEFAULT 0',
                    ),
                    (
                        "approval_status",
                        '"approval_status" VARCHAR NOT NULL DEFAULT \'approved\'',
                        '"approval_status" VARCHAR NOT NULL DEFAULT \'approved\'',
                    ),
                    ("contact_phone", '"contact_phone" VARCHAR', '"contact_phone" VARCHAR'),
                    ("operating_hours", '"operating_hours" VARCHAR', '"operating_hours" VARCHAR'),
                    ("is_24x7", '"is_24x7" BOOLEAN NOT NULL DEFAULT FALSE', '"is_24x7" BOOLEAN NOT NULL DEFAULT 0'),
                    ("amenities", '"amenities" VARCHAR', '"amenities" VARCHAR'),
                    ("image_url", '"image_url" VARCHAR', '"image_url" VARCHAR'),
                    ("rating", '"rating" DOUBLE PRECISION NOT NULL DEFAULT 0.0', '"rating" REAL NOT NULL DEFAULT 0.0'),
                    (
                        "total_reviews",
                        '"total_reviews" INTEGER NOT NULL DEFAULT 0',
                        '"total_reviews" INTEGER NOT NULL DEFAULT 0',
                    ),
                    (
                        "last_maintenance_date",
                        '"last_maintenance_date" TIMESTAMP WITH TIME ZONE',
                        '"last_maintenance_date" TIMESTAMP',
                    ),
                    (
                        "low_stock_threshold_pct",
                        '"low_stock_threshold_pct" DOUBLE PRECISION NOT NULL DEFAULT 20.0',
                        '"low_stock_threshold_pct" REAL NOT NULL DEFAULT 20.0',
                    ),
                    ("is_deleted", '"is_deleted" BOOLEAN NOT NULL DEFAULT FALSE', '"is_deleted" BOOLEAN NOT NULL DEFAULT 0'),
                    ("deleted_at", '"deleted_at" TIMESTAMP WITH TIME ZONE', '"deleted_at" TIMESTAMP'),
                    ("last_heartbeat", '"last_heartbeat" TIMESTAMP WITH TIME ZONE', '"last_heartbeat" TIMESTAMP'),
                ],
            )
        )

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="wallets",
                columns=[
                    ("user_id", '"user_id" INTEGER NOT NULL DEFAULT 0', '"user_id" INTEGER NOT NULL DEFAULT 0'),
                    (
                        "balance",
                        '"balance" DOUBLE PRECISION NOT NULL DEFAULT 0.0',
                        '"balance" REAL NOT NULL DEFAULT 0.0',
                    ),
                    (
                        "cashback_balance",
                        '"cashback_balance" DOUBLE PRECISION NOT NULL DEFAULT 0.0',
                        '"cashback_balance" REAL NOT NULL DEFAULT 0.0',
                    ),
                    (
                        "currency",
                        '"currency" VARCHAR NOT NULL DEFAULT \'INR\'',
                        '"currency" VARCHAR NOT NULL DEFAULT \'INR\'',
                    ),
                    (
                        "is_frozen",
                        '"is_frozen" BOOLEAN NOT NULL DEFAULT FALSE',
                        '"is_frozen" BOOLEAN NOT NULL DEFAULT 0',
                    ),
                    (
                        "updated_at",
                        '"updated_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()',
                        '"updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
                    ),
                ],
            )
        )

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="menus",
                columns=[
                    ("name", '"name" VARCHAR NOT NULL DEFAULT \'menu\'', '"name" VARCHAR NOT NULL DEFAULT \'menu\''),
                    (
                        "display_name",
                        '"display_name" VARCHAR NOT NULL DEFAULT \'Menu\'',
                        '"display_name" VARCHAR NOT NULL DEFAULT \'Menu\'',
                    ),
                    ("route", '"route" VARCHAR', '"route" VARCHAR'),
                    ("icon", '"icon" VARCHAR', '"icon" VARCHAR'),
                    ("parent_id", '"parent_id" INTEGER', '"parent_id" INTEGER'),
                    ("menu_order", '"menu_order" INTEGER NOT NULL DEFAULT 0', '"menu_order" INTEGER NOT NULL DEFAULT 0'),
                    ("is_active", '"is_active" BOOLEAN NOT NULL DEFAULT TRUE', '"is_active" BOOLEAN NOT NULL DEFAULT 1'),
                    (
                        "created_at",
                        '"created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()',
                        '"created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
                    ),
                    (
                        "updated_at",
                        '"updated_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()',
                        '"updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
                    ),
                    ("created_by", '"created_by" VARCHAR', '"created_by" VARCHAR'),
                    ("modified_by", '"modified_by" VARCHAR', '"modified_by" VARCHAR'),
                ],
            )
        )

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="role_rights",
                columns=[
                    ("role_id", '"role_id" INTEGER NOT NULL DEFAULT 0', '"role_id" INTEGER NOT NULL DEFAULT 0'),
                    ("menu_id", '"menu_id" INTEGER NOT NULL DEFAULT 0', '"menu_id" INTEGER NOT NULL DEFAULT 0'),
                    ("can_view", '"can_view" BOOLEAN NOT NULL DEFAULT FALSE', '"can_view" BOOLEAN NOT NULL DEFAULT 0'),
                    ("can_create", '"can_create" BOOLEAN NOT NULL DEFAULT FALSE', '"can_create" BOOLEAN NOT NULL DEFAULT 0'),
                    ("can_edit", '"can_edit" BOOLEAN NOT NULL DEFAULT FALSE', '"can_edit" BOOLEAN NOT NULL DEFAULT 0'),
                    ("can_delete", '"can_delete" BOOLEAN NOT NULL DEFAULT FALSE', '"can_delete" BOOLEAN NOT NULL DEFAULT 0'),
                    (
                        "created_at",
                        '"created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()',
                        '"created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
                    ),
                    (
                        "updated_at",
                        '"updated_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()',
                        '"updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
                    ),
                    ("created_by", '"created_by" VARCHAR', '"created_by" VARCHAR'),
                    ("modified_by", '"modified_by" VARCHAR', '"modified_by" VARCHAR'),
                ],
            )
        )

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="staff_profiles",
                columns=[
                    ("user_id", '"user_id" INTEGER NOT NULL DEFAULT 0', '"user_id" INTEGER NOT NULL DEFAULT 0'),
                    ("dealer_id", '"dealer_id" INTEGER', '"dealer_id" INTEGER'),
                    ("station_id", '"station_id" INTEGER', '"station_id" INTEGER'),
                    (
                        "staff_type",
                        '"staff_type" VARCHAR NOT NULL DEFAULT \'staff\'',
                        '"staff_type" VARCHAR NOT NULL DEFAULT \'staff\'',
                    ),
                    (
                        "employment_id",
                        '"employment_id" VARCHAR NOT NULL DEFAULT \'N/A\'',
                        '"employment_id" VARCHAR NOT NULL DEFAULT \'N/A\'',
                    ),
                    ("reporting_manager_id", '"reporting_manager_id" INTEGER', '"reporting_manager_id" INTEGER'),
                    ("is_active", '"is_active" BOOLEAN NOT NULL DEFAULT TRUE', '"is_active" BOOLEAN NOT NULL DEFAULT 1'),
                    (
                        "created_at",
                        '"created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()',
                        '"created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
                    ),
                ],
            )
        )

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="dealer_documents",
                columns=[
                    (
                        "category",
                        '"category" VARCHAR NOT NULL DEFAULT \'verification\'',
                        '"category" VARCHAR NOT NULL DEFAULT \'verification\'',
                    ),
                    (
                        "status",
                        '"status" VARCHAR NOT NULL DEFAULT \'PENDING\'',
                        '"status" VARCHAR NOT NULL DEFAULT \'PENDING\'',
                    ),
                    ("version", '"version" INTEGER NOT NULL DEFAULT 1', '"version" INTEGER NOT NULL DEFAULT 1'),
                    (
                        "valid_until",
                        '"valid_until" TIMESTAMP WITH TIME ZONE',
                        '"valid_until" TIMESTAMP',
                    ),
                    (
                        "uploaded_at",
                        '"uploaded_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()',
                        '"uploaded_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
                    ),
                    (
                        "is_verified",
                        '"is_verified" BOOLEAN NOT NULL DEFAULT FALSE',
                        '"is_verified" BOOLEAN NOT NULL DEFAULT 0',
                    ),
                ],
            )
        )

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="commission_configs",
                columns=[
                    ("dealer_id", '"dealer_id" INTEGER', '"dealer_id" INTEGER'),
                    ("vendor_id", '"vendor_id" INTEGER', '"vendor_id" INTEGER'),
                    ("transaction_type", '"transaction_type" VARCHAR', '"transaction_type" VARCHAR'),
                    (
                        "percentage",
                        '"percentage" DOUBLE PRECISION NOT NULL DEFAULT 0.0',
                        '"percentage" REAL NOT NULL DEFAULT 0.0',
                    ),
                    (
                        "flat_fee",
                        '"flat_fee" DOUBLE PRECISION NOT NULL DEFAULT 0.0',
                        '"flat_fee" REAL NOT NULL DEFAULT 0.0',
                    ),
                    (
                        "effective_from",
                        '"effective_from" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()',
                        '"effective_from" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
                    ),
                    (
                        "effective_until",
                        '"effective_until" TIMESTAMP WITH TIME ZONE',
                        '"effective_until" TIMESTAMP',
                    ),
                    (
                        "is_active",
                        '"is_active" BOOLEAN NOT NULL DEFAULT TRUE',
                        '"is_active" BOOLEAN NOT NULL DEFAULT 1',
                    ),
                    (
                        "created_at",
                        '"created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()',
                        '"created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
                    ),
                ],
            )
        )

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="swap_sessions",
                columns=[
                    ("rental_id", '"rental_id" INTEGER', '"rental_id" INTEGER'),
                    ("user_id", '"user_id" INTEGER', '"user_id" INTEGER'),
                    ("station_id", '"station_id" INTEGER', '"station_id" INTEGER'),
                    ("old_battery_id", '"old_battery_id" INTEGER', '"old_battery_id" INTEGER'),
                    ("new_battery_id", '"new_battery_id" INTEGER', '"new_battery_id" INTEGER'),
                    (
                        "old_battery_soc",
                        '"old_battery_soc" DOUBLE PRECISION NOT NULL DEFAULT 0.0',
                        '"old_battery_soc" REAL NOT NULL DEFAULT 0.0',
                    ),
                    (
                        "new_battery_soc",
                        '"new_battery_soc" DOUBLE PRECISION NOT NULL DEFAULT 0.0',
                        '"new_battery_soc" REAL NOT NULL DEFAULT 0.0',
                    ),
                    (
                        "swap_amount",
                        '"swap_amount" DOUBLE PRECISION NOT NULL DEFAULT 0.0',
                        '"swap_amount" REAL NOT NULL DEFAULT 0.0',
                    ),
                    (
                        "currency",
                        '"currency" VARCHAR NOT NULL DEFAULT \'INR\'',
                        '"currency" VARCHAR NOT NULL DEFAULT \'INR\'',
                    ),
                    (
                        "status",
                        '"status" VARCHAR NOT NULL DEFAULT \'initiated\'',
                        '"status" VARCHAR NOT NULL DEFAULT \'initiated\'',
                    ),
                    (
                        "payment_status",
                        '"payment_status" VARCHAR NOT NULL DEFAULT \'pending\'',
                        '"payment_status" VARCHAR NOT NULL DEFAULT \'pending\'',
                    ),
                    ("error_message", '"error_message" VARCHAR', '"error_message" VARCHAR'),
                    (
                        "created_at",
                        '"created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()',
                        '"created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
                    ),
                    (
                        "completed_at",
                        '"completed_at" TIMESTAMP WITH TIME ZONE',
                        '"completed_at" TIMESTAMP',
                    ),
                ],
            )
        )

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="station_stock_configs",
                columns=[
                    ("station_id", '"station_id" INTEGER', '"station_id" INTEGER'),
                    (
                        "max_capacity",
                        '"max_capacity" INTEGER NOT NULL DEFAULT 50',
                        '"max_capacity" INTEGER NOT NULL DEFAULT 50',
                    ),
                    (
                        "reorder_point",
                        '"reorder_point" INTEGER NOT NULL DEFAULT 10',
                        '"reorder_point" INTEGER NOT NULL DEFAULT 10',
                    ),
                    (
                        "reorder_quantity",
                        '"reorder_quantity" INTEGER NOT NULL DEFAULT 20',
                        '"reorder_quantity" INTEGER NOT NULL DEFAULT 20',
                    ),
                    ("manager_email", '"manager_email" VARCHAR', '"manager_email" VARCHAR'),
                    ("manager_phone", '"manager_phone" VARCHAR', '"manager_phone" VARCHAR'),
                    ("updated_by", '"updated_by" INTEGER', '"updated_by" INTEGER'),
                    (
                        "updated_at",
                        '"updated_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()',
                        '"updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
                    ),
                ],
            )
        )

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="stock_alert_dismissals",
                columns=[
                    ("station_id", '"station_id" INTEGER', '"station_id" INTEGER'),
                    ("reason", '"reason" VARCHAR NOT NULL DEFAULT \'manual\'', '"reason" VARCHAR NOT NULL DEFAULT \'manual\''),
                    ("dismissed_by", '"dismissed_by" INTEGER NOT NULL DEFAULT 0', '"dismissed_by" INTEGER NOT NULL DEFAULT 0'),
                    (
                        "dismissed_at",
                        '"dismissed_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()',
                        '"dismissed_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
                    ),
                    (
                        "is_active",
                        '"is_active" BOOLEAN NOT NULL DEFAULT TRUE',
                        '"is_active" BOOLEAN NOT NULL DEFAULT 1',
                    ),
                ],
            )
        )

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="batteries",
                columns=[
                    ("spec_id", '"spec_id" INTEGER', '"spec_id" INTEGER'),
                    ("current_user_id", '"current_user_id" INTEGER', '"current_user_id" INTEGER'),
                    ("health_status", '"health_status" VARCHAR', '"health_status" VARCHAR'),
                    ("current_charge", '"current_charge" DOUBLE PRECISION NOT NULL DEFAULT 100.0', '"current_charge" REAL NOT NULL DEFAULT 100.0'),
                    ("health_percentage", '"health_percentage" DOUBLE PRECISION NOT NULL DEFAULT 100.0', '"health_percentage" REAL NOT NULL DEFAULT 100.0'),
                    ("cycle_count", '"cycle_count" INTEGER NOT NULL DEFAULT 0', '"cycle_count" INTEGER NOT NULL DEFAULT 0'),
                    ("total_cycles", '"total_cycles" INTEGER NOT NULL DEFAULT 0', '"total_cycles" INTEGER NOT NULL DEFAULT 0'),
                    ("temperature_c", '"temperature_c" DOUBLE PRECISION NOT NULL DEFAULT 25.0', '"temperature_c" REAL NOT NULL DEFAULT 25.0'),
                    ("manufacturer", '"manufacturer" VARCHAR', '"manufacturer" VARCHAR'),
                    ("battery_type", '"battery_type" VARCHAR', '"battery_type" VARCHAR'),
                    ("purchase_cost", '"purchase_cost" DOUBLE PRECISION NOT NULL DEFAULT 0.0', '"purchase_cost" REAL NOT NULL DEFAULT 0.0'),
                    ("notes", '"notes" VARCHAR', '"notes" VARCHAR'),
                    (
                        "location_type",
                        '"location_type" VARCHAR NOT NULL DEFAULT \'warehouse\'',
                        '"location_type" VARCHAR NOT NULL DEFAULT \'warehouse\'',
                    ),
                    ("manufacture_date", '"manufacture_date" TIMESTAMP WITH TIME ZONE', '"manufacture_date" TIMESTAMP'),
                    ("purchase_date", '"purchase_date" TIMESTAMP WITH TIME ZONE', '"purchase_date" TIMESTAMP'),
                    ("warranty_expiry", '"warranty_expiry" TIMESTAMP WITH TIME ZONE', '"warranty_expiry" TIMESTAMP'),
                    ("last_charged_at", '"last_charged_at" TIMESTAMP WITH TIME ZONE', '"last_charged_at" TIMESTAMP'),
                    ("last_inspected_at", '"last_inspected_at" TIMESTAMP WITH TIME ZONE', '"last_inspected_at" TIMESTAMP'),
                    ("last_maintenance_date", '"last_maintenance_date" TIMESTAMP WITH TIME ZONE', '"last_maintenance_date" TIMESTAMP'),
                    ("last_maintenance_cycles", '"last_maintenance_cycles" INTEGER NOT NULL DEFAULT 0', '"last_maintenance_cycles" INTEGER NOT NULL DEFAULT 0'),
                    ("state_of_health", '"state_of_health" DOUBLE PRECISION NOT NULL DEFAULT 100.0', '"state_of_health" REAL NOT NULL DEFAULT 100.0'),
                    ("temperature_history", '"temperature_history" JSONB', '"temperature_history" JSON'),
                    ("charge_cycles", '"charge_cycles" INTEGER NOT NULL DEFAULT 0', '"charge_cycles" INTEGER NOT NULL DEFAULT 0'),
                    ("location_id", '"location_id" INTEGER', '"location_id" INTEGER'),
                    ("retirement_date", '"retirement_date" TIMESTAMP WITH TIME ZONE', '"retirement_date" TIMESTAMP'),
                    ("decommissioned_at", '"decommissioned_at" TIMESTAMP WITH TIME ZONE', '"decommissioned_at" TIMESTAMP'),
                    ("decommissioned_by", '"decommissioned_by" INTEGER', '"decommissioned_by" INTEGER'),
                    ("decommission_reason", '"decommission_reason" VARCHAR', '"decommission_reason" VARCHAR'),
                    ("last_telemetry_at", '"last_telemetry_at" TIMESTAMP WITH TIME ZONE', '"last_telemetry_at" TIMESTAMP'),
                ],
            )
        )

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="dealer_profiles",
                columns=[
                    ("year_established", '"year_established" VARCHAR', '"year_established" VARCHAR'),
                    ("website_url", '"website_url" VARCHAR', '"website_url" VARCHAR'),
                    ("business_description", '"business_description" VARCHAR', '"business_description" VARCHAR'),
                    ("alternate_phone", '"alternate_phone" VARCHAR', '"alternate_phone" VARCHAR'),
                    ("whatsapp_number", '"whatsapp_number" VARCHAR', '"whatsapp_number" VARCHAR'),
                    ("support_email", '"support_email" VARCHAR', '"support_email" VARCHAR'),
                    ("support_phone", '"support_phone" VARCHAR', '"support_phone" VARCHAR'),
                    ("bank_name", '"bank_name" VARCHAR', '"bank_name" VARCHAR'),
                    ("bank_account_number", '"bank_account_number" VARCHAR', '"bank_account_number" VARCHAR'),
                    ("bank_ifsc_code", '"bank_ifsc_code" VARCHAR', '"bank_ifsc_code" VARCHAR'),
                    ("bank_details", '"bank_details" JSONB', '"bank_details" JSON'),
                    ("global_station_defaults", '"global_station_defaults" JSONB', '"global_station_defaults" JSON'),
                    ("global_inventory_rules", '"global_inventory_rules" JSONB', '"global_inventory_rules" JSON'),
                    ("global_rental_settings", '"global_rental_settings" JSONB', '"global_rental_settings" JSON'),
                    ("holiday_calendar", '"holiday_calendar" JSONB', '"holiday_calendar" JSON'),
                    ("settings", '"settings" JSONB', '"settings" JSON'),
                ],
            )
        )

        patched_columns.extend(
            _add_columns_if_missing(
                conn=conn,
                inspector=inspector,
                driver=driver,
                table_name="admin_users",
                columns=[("admin_group_id", '"admin_group_id" INTEGER', '"admin_group_id" INTEGER')],
            )
        )

        if created_tables:
            logger.warning(
                "schema.admin_table_compatibility_patch_applied",
                created_tables=created_tables,
            )
        if patched_columns:
            logger.info(
                "schema.admin_column_compatibility_patch_applied",
                patched_columns=patched_columns,
            )


# ── Connection-level hooks ─────────────────────────────────────────────────

@event.listens_for(engine, "connect")
def _on_connect(dbapi_connection, connection_record):
    """
    Per-connection setup:
    - SQLite  → enable WAL journal + NORMAL sync
    - PostgreSQL → lock search_path to public (safe for PgBouncer/Neon)
    """
    parsed_url = make_url(settings.DATABASE_URL)

    if parsed_url.drivername.startswith("sqlite"):

        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()
    elif parsed_url.drivername.startswith("postgresql"):
        cursor = dbapi_connection.cursor()
        try:
            # Prefer public (Supabase-safe), then detect app schema from known app tables.
            app_schema = "public"
            try:
                cursor.execute(
                    "SELECT table_schema FROM information_schema.tables "
                    "WHERE table_name IN ('roles', 'users', 'stations', 'batteries') "
                    "  AND table_schema NOT IN "
                    "      ('information_schema', 'pg_catalog', 'auth', 'storage', 'graphql', 'realtime') "
                    "ORDER BY CASE WHEN table_schema = 'public' THEN 0 ELSE 1 END, table_schema "
                    "LIMIT 1"
                )
                row = cursor.fetchone()
                if row and row[0]:
                    app_schema = _safe_schema_name(row[0], default="public")
            except Exception as exc:
                logger.warning("db.search_path.detect_failed", error=str(exc))

            try:
                cursor.execute(f"SET search_path TO {app_schema}, public")
            except Exception as exc:
                logger.warning(
                    "db.search_path.set_failed",
                    schema=app_schema,
                    error=str(exc),
                )
                cursor.execute("SET search_path TO public")
        finally:
            cursor.close()


# ── SQL observability (slow queries + suspicious no-op mutations) ───────────

_UPDATE_TABLE_RE = re.compile(r"^\s*UPDATE\s+([a-zA-Z0-9_\.\"`]+)", re.IGNORECASE)
_DELETE_TABLE_RE = re.compile(r"^\s*DELETE\s+FROM\s+([a-zA-Z0-9_\.\"`]+)", re.IGNORECASE)
_INSERT_TABLE_RE = re.compile(r"^\s*INSERT\s+INTO\s+([a-zA-Z0-9_\.\"`]+)", re.IGNORECASE)
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_schema_name(value: object, default: str = "public") -> str:
    schema = str(value or "").strip()
    if _SQL_IDENTIFIER_RE.match(schema):
        return schema
    return default


def _compact_sql(statement: object, *, max_len: int = 400) -> str:
    compact = " ".join(str(statement).split())
    if len(compact) <= max_len:
        return compact
    return f"{compact[:max_len]}..."


def _mutation_info(statement: object) -> tuple[str | None, str | None]:
    sql = str(statement)
    stripped = sql.lstrip().upper()
    if stripped.startswith("UPDATE"):
        match = _UPDATE_TABLE_RE.match(sql)
        return "UPDATE", (match.group(1) if match else None)
    if stripped.startswith("DELETE"):
        match = _DELETE_TABLE_RE.match(sql)
        return "DELETE", (match.group(1) if match else None)
    if stripped.startswith("INSERT"):
        match = _INSERT_TABLE_RE.match(sql)
        return "INSERT", (match.group(1) if match else None)
    return None, None


def _register_sql_observability() -> None:
    slow_threshold_ms = int(getattr(settings, "SQL_SLOW_QUERY_LOG_MS", 0) or 0)
    slow_warn_cooldown_seconds = max(
        0, int(getattr(settings, "SQL_SLOW_QUERY_WARN_COOLDOWN_SECONDS", 0) or 0)
    )
    slow_ignore_patterns = tuple(
        pattern.strip().lower()
        for pattern in (getattr(settings, "SQL_SLOW_QUERY_IGNORE_PATTERNS", []) or [])
        if pattern and pattern.strip()
    )
    log_noop_mutations = bool(getattr(settings, "DB_LOG_NOOP_MUTATIONS", True))
    ignore_tables = {
        name.strip().lower()
        for name in (settings.DB_NOOP_MUTATION_IGNORE_TABLES or [])
        if name.strip()
    }
    if slow_threshold_ms <= 0 and not log_noop_mutations:
        return

    slow_query_last_warned_at: dict[str, float] = {}
    slow_query_suppressed_count: dict[str, int] = {}

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("_query_start_times", []).append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        start_times = conn.info.get("_query_start_times")
        if not start_times:
            return
        started_at = start_times.pop()
        duration_ms = (time.perf_counter() - started_at) * 1000
        rowcount = getattr(cursor, "rowcount", None)
        sql_text = _compact_sql(statement)

        if slow_threshold_ms > 0 and duration_ms >= slow_threshold_ms:
            sql_key = sql_text.lower()
            if not any(pattern in sql_key for pattern in slow_ignore_patterns):
                if slow_warn_cooldown_seconds > 0:
                    now_monotonic = time.monotonic()
                    last_warned_at = slow_query_last_warned_at.get(sql_key)
                    if (
                        last_warned_at is not None
                        and (now_monotonic - last_warned_at) < slow_warn_cooldown_seconds
                    ):
                        slow_query_suppressed_count[sql_key] = (
                            slow_query_suppressed_count.get(sql_key, 0) + 1
                        )
                    else:
                        # Prevent unbounded growth in long-lived workers.
                        if len(slow_query_last_warned_at) > 2048:
                            slow_query_last_warned_at.clear()
                            slow_query_suppressed_count.clear()
                        suppressed = slow_query_suppressed_count.pop(sql_key, 0)
                        slow_query_last_warned_at[sql_key] = now_monotonic
                        log_payload = {
                            "duration_ms": round(duration_ms, 2),
                            "threshold_ms": slow_threshold_ms,
                            "rowcount": rowcount,
                            "executemany": executemany,
                            "sql": sql_text,
                        }
                        if suppressed:
                            log_payload["suppressed_since_last"] = suppressed
                        logger.warning("anomaly.db.slow_query", **log_payload)
                else:
                    logger.warning(
                        "anomaly.db.slow_query",
                        duration_ms=round(duration_ms, 2),
                        threshold_ms=slow_threshold_ms,
                        rowcount=rowcount,
                        executemany=executemany,
                        sql=sql_text,
                    )

        if not log_noop_mutations:
            return
        operation, raw_table = _mutation_info(statement)
        if not operation:
            return
        table_name = (raw_table or "").strip().strip('"`').lower()
        if table_name and table_name in ignore_tables:
            return
        if rowcount == 0:
            logger.warning(
                "anomaly.db.noop_mutation",
                operation=operation,
                table=table_name or None,
                rowcount=rowcount,
                executemany=executemany,
                sql=sql_text,
            )


_register_sql_observability()


# ── Session dependency ─────────────────────────────────────────────────────

def get_db():
    """Dependency for FastAPI endpoints."""
    with Session(engine) as session:
        yield session
