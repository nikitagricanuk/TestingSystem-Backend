import time

from redis_om import get_redis_connection, NotFoundError
from redis.exceptions import ConnectionError
from redis import Redis
from .config import Settings

settings = Settings()

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