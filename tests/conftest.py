import os
import sys
from pathlib import Path
from types import ModuleType

os.environ.setdefault("TESTING", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base


def _install_redis_stub():
    if "redis" in sys.modules:
        return
    redis_stub = ModuleType("redis")

    class Redis:  # pragma: no cover - simple import stub
        pass

    class ConnectionError(Exception):
        pass

    redis_stub.Redis = Redis
    redis_stub.ConnectionPool = object

    exceptions_mod = ModuleType("redis.exceptions")
    exceptions_mod.ConnectionError = ConnectionError

    redis_stub.exceptions = exceptions_mod
    sys.modules["redis"] = redis_stub
    sys.modules["redis.exceptions"] = exceptions_mod


_install_redis_stub()


def _install_redis_om_stub():
    if "redis_om" in sys.modules:
        return
    redis_om_stub = ModuleType("redis_om")

    class NotFoundError(Exception):
        pass

    class HashModel:  # pragma: no cover - import stub
        @classmethod
        async def get(cls, *args, **kwargs):
            raise NotImplementedError

    def Field(*args, **kwargs):  # pragma: no cover - import stub
        return None

    def get_redis_connection(*args, **kwargs):  # pragma: no cover - import stub
        return None

    redis_om_stub.NotFoundError = NotFoundError
    redis_om_stub.HashModel = HashModel
    redis_om_stub.Field = Field
    redis_om_stub.get_redis_connection = get_redis_connection
    sys.modules["redis_om"] = redis_om_stub


_install_redis_om_stub()


def _install_databases_stub():
    if "app.core.databases" in sys.modules:
        return
    databases_stub = ModuleType("app.core.databases")

    async def _noop_session_maker():  # pragma: no cover - import stub
        return None

    def connection(method):
        async def wrapper(*args, **kwargs):
            return await method(*args, **kwargs)

        return wrapper

    def init_redis_connection():  # pragma: no cover - import stub
        return None

    databases_stub.async_session_maker = _noop_session_maker
    databases_stub.connection = connection
    databases_stub.init_redis_connection = init_redis_connection
    sys.modules["app.core.databases"] = databases_stub


_install_databases_stub()


def _install_asyncpg_stub():
    if "asyncpg" in sys.modules:
        return
    asyncpg_stub = ModuleType("asyncpg")

    class ForeignKeyViolationError(Exception):
        pass

    class UniqueViolationError(Exception):
        pass

    asyncpg_stub.ForeignKeyViolationError = ForeignKeyViolationError
    asyncpg_stub.UniqueViolationError = UniqueViolationError
    sys.modules["asyncpg"] = asyncpg_stub


_install_asyncpg_stub()


def _install_passlib_stub():
    if "passlib" in sys.modules:
        return
    passlib_stub = ModuleType("passlib")
    context_stub = ModuleType("passlib.context")

    class CryptContext:  # pragma: no cover - import stub
        def __init__(self, *args, **kwargs):
            pass

        def verify(self, *args, **kwargs):
            return True

        def hash(self, *args, **kwargs):
            return "hashed"

    context_stub.CryptContext = CryptContext
    passlib_stub.context = context_stub
    sys.modules["passlib"] = passlib_stub
    sys.modules["passlib.context"] = context_stub


_install_passlib_stub()


def _install_jwcrypto_stub():
    if "jwcrypto" in sys.modules:
        return
    jwcrypto_stub = ModuleType("jwcrypto")
    jwt_stub = ModuleType("jwcrypto.jwt")
    jwk_stub = ModuleType("jwcrypto.jwk")

    class JWK:  # pragma: no cover - import stub
        @classmethod
        def from_password(cls, *args, **kwargs):
            return cls()

    class JWT:  # pragma: no cover - import stub
        def __init__(self, *args, **kwargs):
            self.claims = "{}"

    def json_decode(value):
        return {}

    jwk_stub.JWK = JWK
    jwt_stub.JWT = JWT
    jwt_stub.json_decode = json_decode

    jwcrypto_stub.jwt = jwt_stub
    jwcrypto_stub.jwk = jwk_stub

    sys.modules["jwcrypto"] = jwcrypto_stub
    sys.modules["jwcrypto.jwt"] = jwt_stub
    sys.modules["jwcrypto.jwk"] = jwk_stub


_install_jwcrypto_stub()


def _install_aredis_om_stub():
    if "aredis_om" in sys.modules:
        return
    aredis_stub = ModuleType("aredis_om")

    class NotFoundError(Exception):
        pass

    class HashModel:  # pragma: no cover - import stub
        @classmethod
        async def get(cls, *args, **kwargs):
            raise NotImplementedError

    aredis_stub.NotFoundError = NotFoundError
    aredis_stub.HashModel = HashModel
    sys.modules["aredis_om"] = aredis_stub


_install_aredis_om_stub()


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)

    async_session_maker = sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()