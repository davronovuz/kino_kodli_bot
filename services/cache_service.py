import json
from typing import Optional, Any
from redis.asyncio import Redis
from loguru import logger

from config import config


class CacheService:
    _redis: Optional[Redis] = None

    @classmethod
    async def connect(cls):
        try:
            cls._redis = Redis.from_url(
                config.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            await cls._redis.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Running without cache.")
            cls._redis = None

    @classmethod
    async def disconnect(cls):
        if cls._redis:
            await cls._redis.close()
            logger.info("Redis disconnected")

    @classmethod
    async def get(cls, key: str) -> Optional[str]:
        if not cls._redis:
            return None
        try:
            return await cls._redis.get(key)
        except Exception as e:
            logger.warning(f"Redis GET error: {e}")
            return None

    @classmethod
    async def set(cls, key: str, value: Any, ttl: int = 300):
        if not cls._redis:
            return
        try:
            if not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False, default=str)
            await cls._redis.set(key, value, ex=ttl)
        except Exception as e:
            logger.warning(f"Redis SET error: {e}")

    @classmethod
    async def delete(cls, key: str):
        if not cls._redis:
            return
        try:
            await cls._redis.delete(key)
        except Exception as e:
            logger.warning(f"Redis DELETE error: {e}")

    @classmethod
    async def delete_pattern(cls, pattern: str):
        if not cls._redis:
            return
        try:
            keys = []
            async for key in cls._redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await cls._redis.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis DELETE pattern error: {e}")

    @classmethod
    async def get_json(cls, key: str) -> Optional[Any]:
        val = await cls.get(key)
        if val:
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    @classmethod
    async def set_json(cls, key: str, value: Any, ttl: int = 300):
        await cls.set(key, json.dumps(value, ensure_ascii=False, default=str), ttl)

    # ---- Rate Limiting ----
    @classmethod
    async def check_rate_limit(cls, user_id: int, limit_seconds: float = 0.5) -> bool:
        """Returns True if rate limited (should block), False if OK."""
        if not cls._redis:
            return False
        key = f"rate:{user_id}"
        try:
            exists = await cls._redis.exists(key)
            if exists:
                return True
            await cls._redis.set(key, "1", px=int(limit_seconds * 1000))
            return False
        except Exception:
            return False

    # ---- Movie cache ----
    @classmethod
    async def cache_movie(cls, code: int, movie_data: dict, ttl: int = 600):
        await cls.set_json(f"movie:{code}", movie_data, ttl)

    @classmethod
    async def get_cached_movie(cls, code: int) -> Optional[dict]:
        return await cls.get_json(f"movie:{code}")

    @classmethod
    async def invalidate_movie(cls, code: int):
        await cls.delete(f"movie:{code}")

    @classmethod
    async def invalidate_all_movies(cls):
        await cls.delete_pattern("movie:*")
