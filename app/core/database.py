import re
import socket
import time

from sqlalchemy import event, inspect, pool, text
from sqlalchemy.engine import make_url
from sqlmodel import Session, create_engine

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
