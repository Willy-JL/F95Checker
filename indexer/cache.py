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
last_change_eligible_fields = (
    "name",
    "thread_version",
    "developer",
    "type",
    "status",
    "last_updated",
    # "score",
    # "votes",
    "description",
    "changelog",
    "tags",
    "unknown_tags",
    "image_url",
    "downloads",
)

LAST_CACHED = "last_cached"
CACHED_WITH = "cached_with"
LAST_CHANGE = "last_change"


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

    last_change = await redis.hget(name, LAST_CHANGE)
    return last_change


async def get_thread(id: int) -> dict[str, str]:
    assert isinstance(id, int)
    name = f"thread:{id}"
    logger.debug(f"Get {name}")

    async with lock(id):
        await _maybe_update_thread_cache(id, name)

    thread = await redis.hgetall(name)
    del thread[LAST_CACHED]
    del thread[CACHED_WITH]
    del thread[LAST_CHANGE]
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
        # Track last time that some meaningful data changed to tell clients to full check it
        old_fields = await redis.hgetall(name)
        if any(
            new_fields.get(key) != old_fields.get(key)
            for key in last_change_eligible_fields
        ):
            new_fields[LAST_CHANGE] = int(last_cached)

    new_fields[LAST_CACHED] = int(last_cached)
    new_fields[CACHED_WITH] = version
    await redis.hmset(name, new_fields)
