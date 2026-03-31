from sqlalchemy import pool
from sqlmodel import Session, create_engine
from app.core.config import settings

# Determine the best pooling strategy for PostgreSQL
# If using a Neon/PgBouncer pooler, NullPool is safer to prevent conflict with server-side pooling
engine_kwargs = {
    "echo": settings.SQLALCHEMY_ECHO,
    "pool_pre_ping": True,
}

if settings.DATABASE_URL.startswith("sqlite"):
    # Allow background APScheduler threads to open concurrent sqlite connections
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    engine_kwargs["poolclass"] = pool.NullPool
else:
    # Production PostgreSQL settings
    # We use NullPool if we're in a highly dynamic bouncer environment, 
    # but for most Neon setups, QueuePool with these parameters is fine.
    engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

def get_db():
    """Dependency for FastAPI endpoints"""
    with Session(engine) as session:
        yield session

