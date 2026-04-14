import logging
import time

from sqlalchemy import event, pool
from sqlalchemy.engine import make_url
from sqlmodel import Session, create_engine

from app.core.config import settings

logger = logging.getLogger(__name__)


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


# ── Slow query logger (from Hardened) ──────────────────────────────────────

def _register_slow_query_logger() -> None:
    threshold_ms = int(getattr(settings, "SQL_SLOW_QUERY_LOG_MS", 0) or 0)
    if threshold_ms <= 0:
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
        if duration_ms < threshold_ms:
            return
        compact_sql = " ".join(str(statement).split())
        if len(compact_sql) > 400:
            compact_sql = f"{compact_sql[:400]}..."
        logger.warning(
            "Slow SQL query detected duration_ms=%.2f threshold_ms=%s rows=%s executemany=%s sql=%s",
            duration_ms,
            threshold_ms,
            getattr(cursor, "rowcount", None),
            executemany,
            compact_sql,
        )


_register_slow_query_logger()


# ── Session dependency ─────────────────────────────────────────────────────

def get_db():
    """Dependency for FastAPI endpoints."""
    with Session(engine) as session:
        yield session
