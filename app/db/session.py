from __future__ import annotations
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


SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=Session
)


def init_db(*, create_tables: bool = False, seed_roles: bool = False):
    """
    Bootstrap tables and optionally seed initial roles.
    WARNING: create_all bypasses Alembic migration tracking.
    Use `alembic upgrade head` for production.
    """
    import app.models.all  # noqa: F401 — ensure all models registered

    if create_tables:
        import warnings
        warnings.warn(
            "init_db(create_tables=True) uses create_all which bypasses Alembic. "
            "Use 'alembic upgrade head' for production deployments.",
            stacklevel=2,
        )
        SQLModel.metadata.create_all(engine)

    if not seed_roles:
        return

    with Session(engine) as session:
        from app.db.initial_data import seed_roles as seed_roles_func
        seed_roles_func(session)
