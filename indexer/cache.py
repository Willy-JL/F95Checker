import asyncio
import contextlib
import datetime as dt
import logging
import time

import redis.asyncio as aredis

from external import error
from indexer import (
    f95zone,
    scraper,
)

CACHE_TTL = dt.timedelta(days=7).total_seconds()
SHORT_TTL = dt.timedelta(days=2).total_seconds()
LAST_CHANGE_ELIGIBLE_FIELDS = (
    "name",
    "thread_version",
    "developer",
    "type",
    "status",
    "last_updated",
    "score",
    "votes",
    "description",
    "changelog",
    "tags",
    "unknown_tags",
    "image_url",
    "downloads",
    "INDEX_ERROR",
)

logger = logging.getLogger(__name__)
redis: aredis.Redis = None
locks_lock = asyncio.Lock()
locks: dict[asyncio.Lock] = {}
version: str = None

CACHE_KEYWORDS = (
    LAST_CACHED := "LAST_CACHED",
    CACHED_WITH := "CACHED_WITH",
    LAST_CHANGE := "LAST_CHANGE",
    EXPIRE_TIME := "EXPIRE_TIME",
    HASHED_META := "HASHED_META",
    INDEX_ERROR := "INDEX_ERROR",
)
NAME_FORMAT = "thread:{id}"


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
    name = NAME_FORMAT.format(id=id)
    logger.debug(f"Last change {name}")

    async with lock(id):
        await _maybe_update_thread_cache(id, name)

    last_change = await redis.hget(name, LAST_CHANGE) or 0
    return int(last_change)


async def get_thread(id: int) -> dict[str, str]:
    assert isinstance(id, int)
    name = NAME_FORMAT.format(id=id)
    logger.debug(f"Get {name}")

    async with lock(id):
        await _maybe_update_thread_cache(id, name)

    thread = await redis.hgetall(name)

    # Don't return thread data (there might be some) if an error flag is active
    if thread.get(INDEX_ERROR):
        return {INDEX_ERROR: thread[INDEX_ERROR]}

    # Remove internal fields from response
    for key in CACHE_KEYWORDS:
        if key in thread:
            del thread[key]
    return thread


async def _maybe_update_thread_cache(id: int, name: str) -> None:
    last_cached, cached_with, expire_time = await redis.hmget(
        name, (LAST_CACHED, CACHED_WITH, EXPIRE_TIME)
    )
    if last_cached and not expire_time:
        expire_time = int(last_cached) + CACHE_TTL
    if (
        not last_cached  # Never cached
        or time.time() >= int(expire_time)  # Cache expired
        # or cached_with != version  # Cached on different version
    ):
        await _update_thread_cache(id, name)


async def _update_thread_cache(id: int, name: str) -> None:
    logger.info(f"Update cached {name}")

    try:
        result = await scraper.thread(id)
    except Exception:
        logger.error(f"Exception caching {name}: {error.text()}\n{error.traceback()}")
        result = f95zone.ERROR_INTERNAL_ERROR
    old_fields = await redis.hgetall(name)
    now = time.time()

    if isinstance(result, f95zone.IndexerError):
        # Something went wrong, keep cache and retry sooner/later
        new_fields = {
            INDEX_ERROR: result.error_flag,
            EXPIRE_TIME: int(now + result.retry_delay),
        }
        if result is f95zone.ERROR_THREAD_MISSING:
            # F95zone responded but thread is missing, remove any previous cache
            await redis.delete(name)
            if last_change := old_fields.get(LAST_CHANGE):
                new_fields[LAST_CHANGE] = last_change
        # Consider new error as a change
        if old_fields.get(INDEX_ERROR) != new_fields.get(INDEX_ERROR):
            new_fields[LAST_CHANGE] = int(now)
    else:
        # F95zone responded, cache new thread data
        new_fields = {
            **result,
            INDEX_ERROR: "",
            EXPIRE_TIME: int(now + CACHE_TTL),
        }
        # Recache more often if using thread_version
        if "thread_version" in new_fields:
            del new_fields["thread_version"]
            new_fields[EXPIRE_TIME] = int(now + SHORT_TTL)
        # Track last time that some meaningful data changed to tell clients to full check it
        if any(
            new_fields.get(key) != old_fields.get(key)
            for key in LAST_CHANGE_ELIGIBLE_FIELDS
        ):
            new_fields[LAST_CHANGE] = int(now)
            logger.info(f"Data for {name} changed")

    new_fields[LAST_CACHED] = int(now)
    new_fields[CACHED_WITH] = version
    if LAST_CHANGE not in old_fields and LAST_CHANGE not in new_fields:
        new_fields[LAST_CHANGE] = int(now)
    await redis.hmset(name, new_fields)
