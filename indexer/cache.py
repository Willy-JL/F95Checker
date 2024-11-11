import redis.asyncio as aredis
import datetime as dt
import contextlib
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

ttl = dt.timedelta(hours=6).total_seconds()

redis: aredis.Redis = None

locks_lock = asyncio.Lock()
locks: dict[asyncio.Lock] = {}


# https://stackoverflow.com/a/67057328
@contextlib.asynccontextmanager
async def lock(id: int):
    async with locks_lock:
        if not locks.get(id):
            locks[id] = asyncio.Lock()
    async with locks[id]:
        yield
    async with locks_lock:
        if locks[id].locked() == 0:
            del locks[id]


@contextlib.asynccontextmanager
async def lifespan():
    global redis
    redis = aredis.Redis(decode_responses=True)
    await redis.ping()

    yield

    await redis.aclose()
    redis = None


async def get_thread(id: int) -> dict:
    assert isinstance(id, int)
    thread_name = f"thread:{id}"
    logger.debug(f"Get {thread_name}")

    async with lock(id):
        last_cached = int((await redis.hget(thread_name, "last_cached")) or 0)
        now = time.time()
        if (now - last_cached) > ttl:
            await _update_thread_cache(id)

        thread = await redis.hgetall(thread_name)
        del thread["last_cached"]
        return thread


async def refresh_thread(id: int) -> None:
    assert isinstance(id, int)

    async with lock(id):
        await _update_thread_cache(id)


async def _update_thread_cache(id: int):
    thread_name = f"thread:{id}"
    logger.info(f"Update cached {thread_name}")

    # FIXME: Implement
    await redis.hset(thread_name, "last_cached", int(time.time()))
