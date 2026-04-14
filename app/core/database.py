import re
import time

from sqlalchemy import event, pool
from sqlalchemy.engine import make_url
from sqlmodel import Session, create_engine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


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
            # Detect actual schema where app tables live; fall back to public.
            cursor.execute(
                "SELECT table_schema FROM information_schema.tables "
                "WHERE table_name = 'users' "
                "  AND table_schema NOT IN ('information_schema', 'pg_catalog') "
                "LIMIT 1"
            )
            row = cursor.fetchone()
            app_schema = row[0] if row else "public"
            cursor.execute(f"SET search_path TO {app_schema}, public")
        finally:
            cursor.close()


# ── SQL observability (slow queries + suspicious no-op mutations) ───────────

_UPDATE_TABLE_RE = re.compile(r"^\s*UPDATE\s+([a-zA-Z0-9_\.\"`]+)", re.IGNORECASE)
_DELETE_TABLE_RE = re.compile(r"^\s*DELETE\s+FROM\s+([a-zA-Z0-9_\.\"`]+)", re.IGNORECASE)
_INSERT_TABLE_RE = re.compile(r"^\s*INSERT\s+INTO\s+([a-zA-Z0-9_\.\"`]+)", re.IGNORECASE)


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
    log_noop_mutations = bool(getattr(settings, "DB_LOG_NOOP_MUTATIONS", True))
    ignore_tables = {name.strip().lower() for name in (settings.DB_NOOP_MUTATION_IGNORE_TABLES or []) if name.strip()}
    if slow_threshold_ms <= 0 and not log_noop_mutations:
        return

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
