import time
import asyncio # Импорт для неблокирующей задержки
from functools import wraps
from typing import Callable, Any, Awaitable

from redis_om import get_redis_connection, NotFoundError
from redis.asyncio import Redis as AsyncRedis # Используем асинхронный клиент
from redis.exceptions import ConnectionError
from redis import Redis
from loguru import logger
from .config import Settings

settings = Settings()

# Глобальная переменная для хранения асинхронного клиента
_redis_connection: AsyncRedis | None = None

async def _get_redis_connection_instance() -> AsyncRedis:
    """
    Создает и возвращает одиночный экземпляр соединения Redis (AsyncRedis) с логикой повторных попыток.
    """
    global _redis_connection
    if _redis_connection is not None:
        try:
            # Асинхронная проверка соединения
            await _redis_connection.ping()
            return _redis_connection
        except ConnectionError:
            logger.warning("Cached Redis connection failed ping. Attempting to re-establish.")
            _redis_connection = None
        except Exception as e:
            logger.warning(f"Error during cached Redis ping: {e}. Attempting to re-establish.")
            _redis_connection = None

    redis_url: str = settings.get_redis_url
    if not redis_url:
        logger.error("REDIS_URL environment variable is not set.")
        raise ValueError("REDIS_URL environment variable is not set.")

    retries = 5
    delay = 2
    logger.info(f"Attempting to connect to Redis at {settings.redis_host}:{settings.redis_port}...")

    for i in range(retries):
        try:
            # Используем AsyncRedis.from_url для создания асинхронного клиента
            conn = AsyncRedis.from_url(
                url=redis_url,
                decode_responses=True
            )
            await conn.ping() # Асинхронный ping check
            logger.info("Successfully connected to Redis!")
            _redis_connection = conn
            return conn
        except ConnectionError:
            logger.warning(
                f"Attempt {i + 1} of {retries}: Could not connect to Redis. Retrying in {delay} seconds..."
            )
            await asyncio.sleep(delay) # Используем неблокирующую задержку
            delay *= 2
        except Exception as e:
            logger.warning(
                f"Attempt {i + 1} of {retries}: Error initializing or connecting to Redis: {e}. Retrying in {delay} seconds..."
            )
            await asyncio.sleep(delay)
            delay *= 2

    logger.critical("Failed to connect to Redis after multiple attempts.")
    raise ConnectionError("Failed to connect to Redis after multiple attempts.")


def inject_redis_connection(func: Callable[[AsyncRedis, Any], Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """
    Асинхронный декоратор для внедрения экземпляра Redis (AsyncRedis)
    в качестве первого аргумента декорируемой асинхронной функции.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Получаем (или инициализируем) асинхронное соединение Redis
        redis_client = await _get_redis_connection_instance()

        # Вызываем оригинальную асинхронную функцию и ожидаем ее
        return await func(redis_client, *args, **kwargs)

    return wrapper