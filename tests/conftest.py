
from app.models import Base  # все ваши модели

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def async_test_session():
    # создаём in-memory sqlite engine
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session_maker = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # создаём таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # создаём сессию
    async with async_session_maker() as session:
        yield session  # <- это уже AsyncSession

    # удаляем таблицы и закрываем engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
