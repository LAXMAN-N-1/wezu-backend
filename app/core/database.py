from sqlalchemy import pool
from sqlmodel import Session, create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.config import settings

# Determine the best pooling strategy for PostgreSQL
# If using a Neon/PgBouncer pooler, NullPool is safer to prevent conflict with server-side pooling
engine_kwargs = {
    "echo": settings.SQLALCHEMY_ECHO,
    "pool_pre_ping": settings.DB_POOL_PRE_PING,
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
        "pool_use_lifo": settings.DB_POOL_USE_LIFO,
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

if settings.DATABASE_URL.startswith("sqlite"):
    async_db_url = settings.DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
elif settings.DATABASE_URL.startswith("postgresql"):
    async_db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    async_db_url = settings.DATABASE_URL

async_engine = create_async_engine(async_db_url, **engine_kwargs)

from sqlalchemy import event

@event.listens_for(engine, "connect")
@event.listens_for(async_engine.sync_engine, "connect")
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

async def get_async_db():
    """Async Dependency for FastAPI endpoints built for MNC load balancing"""
    async with AsyncSession(async_engine) as session:
        yield session
