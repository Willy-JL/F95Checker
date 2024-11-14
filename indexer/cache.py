import asyncio
import contextlib
import datetime as dt
import logging
import time

import redis.asyncio as aredis

from indexer import scraper

cache_ttl = dt.timedelta(days=7).total_seconds()
retry_delay = dt.timedelta(hours=1).total_seconds()

logger = logging.getLogger(__name__)
redis: aredis.Redis = None
locks_lock = asyncio.Lock()
locks: dict[asyncio.Lock] = {}
version: str = None

LAST_CACHED = "last_cached"
CACHED_WITH = "cached_with"


@contextlib.asynccontextmanager
async def lifespan(_version: str):
    global redis, version
    redis = aredis.Redis(decode_responses=True)
    await redis.ping()
    version = _version

    try:
        yield
    finally:

        await redis.aclose()
        redis = None
        version = None


# https://stackoverflow.com/a/67057328
@contextlib.asynccontextmanager
async def lock(id: int):
    async with locks_lock:
        if not locks.get(id):
            locks[id] = asyncio.Lock()
    async with locks[id]:
        yield
    # TODO: concurrency issues, check if it uses too much RAM like this
    # async with locks_lock:
    #     if locks[id].locked() == 0:
    #         del locks[id]


async def last_change(id: int) -> int:
    assert isinstance(id, int)
    name = f"thread:{id}"
    logger.debug(f"Last change {name}")

    async with lock(id):
        await _maybe_update_thread_cache(id, name)

    # TODO: implement
    return 0


async def get_thread(id: int) -> dict[str, str]:
    assert isinstance(id, int)
    name = f"thread:{id}"
    logger.debug(f"Get {name}")

    async with lock(id):
        await _maybe_update_thread_cache(id, name)

    thread = await redis.hgetall(name)
    del thread[LAST_CACHED]
    del thread[CACHED_WITH]
    return thread


async def refresh_thread(id: int) -> None:
    assert isinstance(id, int)
    name = f"thread:{id}"
    logger.info(f"Refresh {name}")

    async with lock(id):
        await _update_thread_cache(id, name)


async def _maybe_update_thread_cache(id: int, name: str) -> None:
    last_cached, cached_with = await redis.hmget(name, (LAST_CACHED, CACHED_WITH))
    if (
        not last_cached  # Never cached
        or (time.time() - int(last_cached)) > cache_ttl  # Cache expired
        or cached_with != version  # Cached on different version
    ):
        await _update_thread_cache(id, name)


async def _update_thread_cache(id: int, name: str) -> None:
    logger.info(f"Update cached {name}")

    thread = await scraper.thread(id)
    new_fields = {}
    last_cached = time.time()

    if thread is None:
        # Can't reach F95zone, keep cache, mark older last_cached to retry sooner
        last_cached = last_cached - cache_ttl + retry_delay
        # TODO: If an unknown issue (aka not a temporary connection issue) maybe add a flag
        # to cached data saying the thread could not be parsed, and show it in F95Checker UI
    else:
        if thread == {}:
            # F95zone responded but thread is missing, remove any previous cache
            await redis.delete(name)
        else:
            # F95zone responded, cache new thread data
            new_fields = thread
        # TODO: Also track last time that the data actually changed

    new_fields[LAST_CACHED] = int(last_cached)
    new_fields[CACHED_WITH] = version
    await redis.hmset(name, new_fields)
