from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from redis_om import get_redis_connection
from redis.exceptions import ConnectionError
from sqlalchemy import text

from app.core.config import settings
from app.core.databases import engine


router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


async def _check_database() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_redis() -> bool:
    try:
        redis_url = settings.get_redis_url
        redis = get_redis_connection(url=redis_url, decode_responses=True)
        redis.ping()
        return True
    except ConnectionError:
        return False
    except Exception:
        return False


@router.get("/ready")
async def readiness_check():
    db_ok = await _check_database()
    redis_ok = _check_redis()
    if db_ok and redis_ok:
        return {"status": "ready"}
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "not_ready",
            "dependencies": {"database": db_ok, "redis": redis_ok},
        },
    )
