import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.db import DATABASE_URL, Base

# Obiekt konfiguracji Alembica — dostęp do wartości z alembic.ini.
config = context.config

# alembic.ini celowo nie zawiera sqlalchemy.url (poświadczenia nie trafiają do repo),
# więc adres bazy podajemy tutaj z DATABASE_URL. Znaki "%" muszą zostać podwojone:
# configparser traktuje pojedynczy "%" jako początek interpolacji, więc hasło
# zawierające ten znak wywróciłoby wczytywanie konfiguracji.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadane schematu dla `alembic revision --autogenerate`. Base nie ma jeszcze
# żadnych modeli — pierwszy dojdzie razem ze zgłoszeniem uczestnika (issue #17).
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Tryb offline — generuje sam SQL, bez łączenia się z bazą."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Backend łączy się z bazą asynchronicznie (asyncpg), więc Alembic też musi."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Tryb online — stosuje migracje na żywym połączeniu."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
