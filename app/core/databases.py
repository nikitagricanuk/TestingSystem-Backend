import time

from redis_om import get_redis_connection, NotFoundError
from redis.exceptions import ConnectionError
from redis import Redis

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import settings


DATABASE_URL = settings.get_postgres_url

engine = create_async_engine(url=DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

def init_redis_connection() -> Redis:
    redis_url: str = settings.get_redis_url
    if not redis_url:
        raise ValueError("REDIS_URL environment variable is not set.")

    retries = 5
    delay = 2
    for i in range(retries):
        try:
            conn = get_redis_connection(
                url=redis_url,
                decode_responses=True
            )
            conn.ping()
            print("Successfully connected to Redis!")
            return conn
        except ConnectionError as e:
            print(f"Attempt {i + 1} of {retries}: Could not connect to Redis. Retrying in {delay} seconds...")
            time.sleep(delay)
            delay *= 2

    raise ConnectionError("Failed to connect to Redis after multiple attempts.")

def connection(method):
    async def wrapper(*args, **kwargs):
        if "session" in kwargs and kwargs["session"] is not None:
            # Use the provided session (e\.g\. from test)
            return await method(*args, **kwargs)
        async with async_session_maker() as session:
            try:
                return await method(*args, session=session, **kwargs)
            except Exception as e:
                await session.rollback()
                raise e
            finally:
                await session.close()
    return wrapper