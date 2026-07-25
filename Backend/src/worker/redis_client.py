"""
Shared ARQ Redis pool used by the FastAPI app to enqueue tasks.
Initialised once at app startup via lifespan.
"""
from __future__ import annotations

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

_pool: ArqRedis | None = None


def _settings() -> RedisSettings:
    from src.config.settings import settings
    from src.worker.main import _redis_settings
    return _redis_settings()


async def get_redis_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(_settings())
    return _pool


async def close_redis_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
