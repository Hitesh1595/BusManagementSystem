import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()
_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


async def redis_ok() -> bool:
    try:
        return await get_redis().ping()
    except Exception:
        return False
