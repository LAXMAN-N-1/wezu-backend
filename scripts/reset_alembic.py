from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(str(settings.DATABASE_URL))
with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    # for SQLAlchemy 2.0+
    try:
        conn.commit()
    except Exception:
        pass
