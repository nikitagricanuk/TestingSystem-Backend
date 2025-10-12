import pytest
from unittest.mock import AsyncMock, MagicMock
from fakeredis import FakeRedis, FakeAsyncRedis  # Импортируем FakeAsyncRedis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import Settings
from app.core.databases import AsyncRedis, _get_redis_connection_instance


# 1. Загрузка тестовых настроек
@pytest.fixture(scope="session", autouse=True)
def load_test_settings():
    """
    Фикстура, которая переопределяет настройки, заставляя pydantic-settings
    использовать .env.test.
    """
    original_env_file = Settings.model_config.get('env_file')
    Settings.model_config['env_file'] = '.env.test'
    yield
    # Возвращаем оригинальное значение после завершения сессии тестов
    Settings.model_config['env_file'] = original_env_file


# 2. Фикстура для подмены Redis на FakeRedis
@pytest.fixture(scope="function", autouse=True)
async def fakeredis_client(monkeypatch):
    """
    Подменяет AsyncRedis.from_url на функцию, возвращающую FakeAsyncRedis
    для всех юнит-тестов. Очищает базу данных после каждого теста.
    """

    # ⚠️ Важно: поскольку AsyncRedis.from_url - это классметод,
    # мы должны мокировать его и вернуть AsyncMock,
    # который при вызове вернет FakeAsyncRedis.

    fake_redis_instance = FakeAsyncRedis(decode_responses=True)

    # Функция, которая будет мокировать AsyncRedis.from_url
    # Она возвращает готовый экземпляр FakeAsyncRedis.
    def mock_from_url(*args, **kwargs):
        return fake_redis_instance

    # Подменяем AsyncRedis.from_url
    monkeypatch.setattr(AsyncRedis, "from_url", mock_from_url)

    # Также очищаем глобальный кэш соединения, чтобы он использовал FakeRedis
    monkeypatch.setattr("app.core.databases._redis_connection", None)

    # Выполняем тест
    yield fake_redis_instance

    # Очистка: сбрасываем состояние FakeRedis после каждого теста
    await fake_redis_instance.flushdb()


# 3. Фикстура для тестов, требующих реального подключения (Integration)
# (Вам нужно настроить реальный Redis-stack, например, через docker)

@pytest.fixture(scope="session")
def real_redis_client():
    """
    Фикстура для получения реального клиента Redis для integration-тестов.
    """
    # Этот код вернет реальный клиент, используя настройки из .env.test
    import asyncio
    return asyncio.run(_get_redis_connection_instance())