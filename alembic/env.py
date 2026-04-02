from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from sqlmodel import SQLModel
from app.core.config import settings

# ✅ Import all models so Alembic detects them
from app.models.all import *

# Alembic Config object
config = context.config

# ✅ FORCE Alembic to always use Neon DB URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = SQLModel.metadata


# ✅ FIX: Render SQLModel AutoString as normal String
def render_item(type_, obj, autogen_context):
    """
    Fix AutoString migration bug:
    Converts sqlmodel.sql.sqltypes.AutoString → sa.String
    """
    if type_ == "type" and obj.__class__.__name__ == "AutoString":
        return "sa.String()"
    return False


def include_object(object, name, type_, reflected, compare_to):
    """
    Control which objects are included in the autogeneration process.
    All models use the default (public) schema.
    """
    if type_ == "table":
        # All our models use the default schema (public / None)
        return object.schema in ["public", None]
    return True


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    url = settings.DATABASE_URL

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,   # ✅ Important
        include_schemas=True,       # ✅ Support multiple schemas
        include_object=include_object, # ✅ Filter schemas
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    # ✅ FIX: Override sqlalchemy.url properly
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=render_item,   # ✅ Important
            include_schemas=True,       # ✅ Support multiple schemas
            include_object=include_object, # ✅ Filter schemas
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
