import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Alembic config
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Override the sqlalchemy.url from app settings so the single DATABASE_URL
# env-var is the authoritative source (no duplication in alembic.ini).
# ---------------------------------------------------------------------------
from app.config import get_settings  # noqa: E402

_settings = get_settings()
config.set_main_option("sqlalchemy.url", _settings.DATABASE_URL)

# ---------------------------------------------------------------------------
# Import Base.metadata so alembic autogenerate can detect schema changes.
# Additional model modules are imported here as they land (per chunk).
# ---------------------------------------------------------------------------
from app.auth import models as _auth_models  # noqa: E402, F401
from app.database import Base  # noqa: E402, F401
from app.schools import models as _school_models  # noqa: E402, F401

# from app.vehicles import models as _vehicle_models  # noqa: F401
# from app.routes import models as _route_models  # noqa: F401
# from app.tracking import models as _tracking_models  # noqa: F401
# from app.notifications import models as _notif_models  # noqa: F401

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration modes
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Offline mode: emit SQL to stdout without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # GeoAlchemy2 requires include_schemas=False (default); no extra config needed.
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
