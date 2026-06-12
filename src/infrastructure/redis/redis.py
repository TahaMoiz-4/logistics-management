import logging
import redis
from typing import Optional
from src.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
        )
    return _redis_client


def check_redis_connection() -> bool:
    try:
        get_redis().ping()
        logger.info("✅ Redis connection OK")
        return True
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        return False


def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None

def _cache_key(
    lat1: float, lng1: float,
    lat2: float, lng2: float,
    day_type: str,
    hour: int,
) -> str:
    """
    Redis key for a single origin→destination pair at a given time band.
    Rounded to 5 decimal places (~1m precision) to maximise cache hits.
    """
    return (
        f"matrix:pair:"
        f"{lat1:.5f}:{lng1:.5f}:"
        f"{lat2:.5f}:{lng2:.5f}:"
        f"{day_type}:{hour}"
    )


def _get_cached(key: str) -> Optional[int]:
    try:
        r = get_redis()
        val = r.get(key)
        return int(val) if val is not None else None
    except Exception:
        return None


def _set_cached(key: str, value: int) -> None:
    try:
        r = get_redis()
        r.setex(key, settings.CACHE_TTL_SEC, value)
    except Exception:
        pass    # cache failure is non-fatal



if __name__ == "__main__":
    print(check_redis_connection())