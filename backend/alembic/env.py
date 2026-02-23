from logging.config import fileConfig
import os
import sys
from asyncio import run

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import Base
from app.models import user, photo, album, drive  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        version_table="alembic_version",
        version_table_schema="public",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"statement_cache_size": 0},
    )

    async def do_migrations() -> None:
        def run_migrations_in_sync(sync_connection) -> None:
            context.configure(
                connection=sync_connection,
                target_metadata=target_metadata,
                version_table="alembic_version",
                version_table_schema="public",
            )
            with context.begin_transaction():
                context.run_migrations()

        async with connectable.connect() as connection:
            await connection.run_sync(run_migrations_in_sync)

        await connectable.dispose()

    run(do_migrations())


run_migrations_online() if not context.is_offline_mode() else run_migrations_offline()
