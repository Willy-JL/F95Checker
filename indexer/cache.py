import asyncio
import contextlib
import datetime as dt
import logging
import time

import redis.asyncio as aredis

from indexer import scraper

CACHE_TTL = dt.timedelta(days=7).total_seconds()
LAST_CHANGE_ELIGIBLE_FIELDS = (
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

logger = logging.getLogger(__name__)
redis: aredis.Redis = None
locks_lock = asyncio.Lock()
locks: dict[asyncio.Lock] = {}
version: str = None

LAST_CACHED = "LAST_CACHED"
CACHED_WITH = "CACHED_WITH"
LAST_CHANGE = "LAST_CHANGE"
INDEX_ERROR = "INDEX_ERROR"


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
    async with locks_lock:
        if (lock := locks.get(id)) and not lock.locked() and not lock._waiters:
            del locks[id]


async def last_change(id: int) -> int:
    assert isinstance(id, int)
    name = f"thread:{id}"
    logger.debug(f"Last change {name}")

    async with lock(id):
        await _maybe_update_thread_cache(id, name)

    last_change = await redis.hget(name, LAST_CHANGE) or 0
    return int(last_change)


async def get_thread(id: int) -> dict[str, str]:
    assert isinstance(id, int)
    name = f"thread:{id}"
    logger.debug(f"Get {name}")

    async with lock(id):
        await _maybe_update_thread_cache(id, name)

    thread = await redis.hgetall(name)

    # Don't return thread data (there might be some) if an error flag is active
    if thread.get(INDEX_ERROR):
        return {INDEX_ERROR: thread[INDEX_ERROR]}

    # Remove internal fields from response
    for key in (LAST_CACHED, CACHED_WITH, LAST_CHANGE, INDEX_ERROR):
        if key in thread:
            del thread[key]
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
        or (time.time() - int(last_cached)) > CACHE_TTL  # Cache expired
        or cached_with != version  # Cached on different version
    ):
        await _update_thread_cache(id, name)


async def _update_thread_cache(id: int, name: str) -> None:
    logger.info(f"Update cached {name}")

    result = await scraper.thread(id)
    old_fields = await redis.hgetall(name)
    new_fields = {}
    last_cached = time.time()

    if isinstance(result, scraper.ScraperError):
        if result is scraper.ERROR_THREAD_MISSING:
            # F95zone responded but thread is missing, remove any previous cache
            await redis.delete(name)
        # Something went wrong, keep cache and retry sooner/later
        last_cached = last_cached - CACHE_TTL + result.retry_delay
        # Consider new error as a change
        if old_fields.get(INDEX_ERROR) != result.error_flag:
            new_fields[LAST_CHANGE] = int(last_cached)
    else:
        # F95zone responded, cache new thread data
        new_fields = result
        # Track last time that some meaningful data changed to tell clients to full check it
        if any(
            new_fields.get(key) != old_fields.get(key)
            for key in LAST_CHANGE_ELIGIBLE_FIELDS
        ):
            new_fields[LAST_CHANGE] = int(last_cached)

    new_fields[LAST_CACHED] = int(last_cached)
    new_fields[CACHED_WITH] = version
    await redis.hmset(name, new_fields)
