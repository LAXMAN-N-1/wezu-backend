from sqlmodel import Session, create_engine
from app.core.config import settings

engine_kwargs = {
    "echo": settings.SQLALCHEMY_ECHO,
    "pool_pre_ping": settings.DB_POOL_PRE_PING,
}

# QueuePool settings are not applicable to SQLite.
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_recycle": settings.DB_POOL_RECYCLE,
        }
    )

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

def get_db():
    with Session(engine) as session:
        yield session
