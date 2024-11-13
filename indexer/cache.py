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


@contextlib.asynccontextmanager
async def lifespan():
    global redis
    redis = aredis.Redis(decode_responses=True)
    await redis.ping()

    try:
        yield
    finally:

        await redis.aclose()
        redis = None


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


async def last_change(id: int):
    assert isinstance(id, int)
    thread_name = f"thread:{id}"
    logger.debug(f"Last change {thread_name}")

    async with lock(id):
        # TODO: implement
        pass

    return 0


async def get_thread(id: int) -> dict[str, str]:
    assert isinstance(id, int)
    thread_name = f"thread:{id}"
    logger.debug(f"Get {thread_name}")

    async with lock(id):
        # TODO: Also check last version cached on to fetch new fields
        last_cached = await redis.hget(thread_name, "last_cached")
        if not last_cached or (time.time() - int(last_cached)) > cache_ttl:
            await _update_thread_cache(id)

    thread = await redis.hgetall(thread_name)
    del thread["last_cached"]
    return thread


async def refresh_thread(id: int) -> None:
    assert isinstance(id, int)

    async with lock(id):
        await _update_thread_cache(id)


async def _update_thread_cache(id: int) -> None:
    thread_name = f"thread:{id}"
    logger.info(f"Update cached {thread_name}")

    thread = await scraper.thread(id)
    last_cached = time.time()

    if thread is None:
        # Can't reach F95zone, keep cache, mark older last_cached to retry sooner
        last_cached = last_cached - cache_ttl + retry_delay
        # TODO: If an unknown issue (aka not a temporary connection issue) maybe add a flag
        # to cached data saying the thread could not be parsed, and show it in F95Checker UI
    elif thread == {}:
        # F95zone responded but thread is missing, remove any previous cache
        await redis.delete(thread_name)
    else:
        # F95zone responded, cache new thread data
        await redis.hmset(thread_name, thread)
    # TODO: Also track last time that the data actually changed

    await redis.hset(thread_name, "last_cached", int(time.time()))
