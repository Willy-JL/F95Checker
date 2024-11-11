import redis.asyncio as aredis
import contextlib
import asyncio

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
    redis = aredis.Redis()
    await redis.ping()

    yield

    await redis.aclose()
    redis = None
