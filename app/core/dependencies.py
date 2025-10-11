from typing import Optional, Annotated
from fastapi import Header, HTTPException, Depends
from redis.asyncio import Redis as AsyncRedis # 👈 Используем AsyncRedis
from app.core.databases import _get_redis_connection_instance

async def get_token_header(x_token: Optional[str] = Header(default=None)):
    # Placeholder dependency to demonstrate structure.
    # Replace with real auth/logic as needed.
    if x_token == "invalid":
        raise HTTPException(status_code=400, detail="Invalid X-Token header")

# Функция зависимости должна стать асинхронной и использовать await
async def get_redis_client() -> AsyncRedis:
    """
    Асинхронная зависимость FastAPI для получения (или инициализации)
    асинхронного соединения Redis.
    """
    # Теперь _get_redis_connection_instance является асинхронной и требует await
    return await _get_redis_connection_instance()

# Создаем псевдоним типа для удобства
RedisClient = Annotated[AsyncRedis, Depends(get_redis_client)]