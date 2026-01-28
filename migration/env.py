import sys
import os
from dotenv import load_dotenv

# путь до .env относительно корня проекта
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.engine import Connection
from sqlalchemy import engine_from_config

from alembic import context

# добавляем корень проекта, чтобы Python видел app/
sys.path.insert(0, "/app")

# импортируем Base и модели
from app.models.database import Base  # содержит User
from app.repositories.question_bank import models  # Question/Category

# sqlalchemy url из core
from app.core.databases import DATABASE_URL

# Alembic config
config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# логирование
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# метаданные для autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Миграции в offline режиме (SQL выводится, но не выполняется)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Выполнение миграций через соединение."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Выполнение миграций через AsyncEngine."""
    connectable = AsyncEngine(
        engine_from_config(
            config.get_section(config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            future=True,
        )
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Выполнение онлайн-миграций."""
    asyncio.run(run_async_migrations())


# запуск
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
