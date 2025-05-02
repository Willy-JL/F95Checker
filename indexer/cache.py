import asyncio
import contextlib
import datetime as dt
import logging
import time

import redis.asyncio as aredis

from common import meta
from external import error
from indexer import (
    f95zone,
    scraper,
)

CACHE_TTL = dt.timedelta(days=7).total_seconds()
SHORT_TTL = dt.timedelta(days=2).total_seconds()
LAST_CHANGE_ELIGIBLE_FIELDS = (
    "name",
    "version",
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
    "previews_urls",
    "downloads",
    "reviews_total",
    "reviews",
    "INDEX_ERROR",
)

logger = logging.getLogger(__name__)
redis: aredis.Redis = None
locks_lock = asyncio.Lock()
locks: dict[asyncio.Lock] = {}

LAST_CACHED = "LAST_CACHED"
EXPIRE_TIME = "EXPIRE_TIME"
INDEX_ERROR = "INDEX_ERROR"
INTERNAL_KEYWORDS = (
    CACHED_WITH := "CACHED_WITH",
    LAST_CHANGE := "LAST_CHANGE",
    HASHED_META := "HASHED_META",
)
NAME_FORMAT = "thread:{id}"


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
    async with locks_lock:
        if (lock := locks.get(id)) and not lock.locked() and not lock._waiters:
            del locks[id]


async def last_change(id: int) -> int:
    assert isinstance(id, int)
    name = NAME_FORMAT.format(id=id)
    logger.debug(f"Last change {name}")

    await _maybe_update_thread_cache(id, name)

    last_change = await redis.hget(name, LAST_CHANGE) or 0
    return int(last_change)


async def get_thread(id: int) -> dict[str, str]:
    assert isinstance(id, int)
    name = NAME_FORMAT.format(id=id)
    logger.debug(f"Get {name}")

    await _maybe_update_thread_cache(id, name)

    thread = await redis.hgetall(name)

    # Remove internal fields from response
    for key in INTERNAL_KEYWORDS:
        if key in thread:
            del thread[key]
    return thread


async def _is_thread_cache_outdated(id: int, name: str) -> bool:
    last_cached, expire_time = await redis.hmget(name, (LAST_CACHED, EXPIRE_TIME))
    if last_cached and not expire_time:
        expire_time = int(last_cached) + CACHE_TTL
    # Never cached or cache expired
    return not last_cached or time.time() >= int(expire_time)


async def _maybe_update_thread_cache(id: int, name: str) -> None:
    # Check without lock first to avoid bottlenecks
    if not await _is_thread_cache_outdated(id, name):
        return

    # If it might be outdated, check with lock to avoid multiple updates
    async with lock(id):
        if await _is_thread_cache_outdated(id, name):
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
    new_fields[CACHED_WITH] = meta.version
    if LAST_CHANGE not in old_fields and LAST_CHANGE not in new_fields:
        new_fields[LAST_CHANGE] = int(now)
    await redis.hmset(name, new_fields)
