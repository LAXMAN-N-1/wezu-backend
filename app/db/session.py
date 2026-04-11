"""
Canonical database session factory for the WEZU backend.

Usage in FastAPI endpoints:
    from app.core.database import get_db
    db: Session = Depends(get_db)

Usage in scripts / background tasks:
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        ...
"""
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel
from app.core.database import engine

def get_session():
    """Generator dependency — identical to core.database.get_db."""
    with Session(engine) as session:
        yield session

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)

def init_db():
    """
    Bootstrap all tables via SQLModel metadata.
    WARNING: This bypasses Alembic migration tracking.
    Only use as a last-resort fallback or for local SQLite dev.
    Prefer `alembic upgrade head` for production.
    """
    import warnings
    warnings.warn(
        "init_db() uses create_all which bypasses Alembic. "
        "Use 'alembic upgrade head' for production deployments.",
        stacklevel=2,
    )
    import app.models.all  # noqa: F401 — ensure all models registered
    SQLModel.metadata.create_all(engine)

