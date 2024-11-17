import asyncio
import contextlib
import datetime as dt
import json
import logging

from external import error
from indexer import (
    cache,
    f95zone,
)

WATCH_INTERVAL = dt.timedelta(minutes=5).total_seconds()
WATCH_CATEGORIES = (
    "games",
    "comics",
    "animations",
)

logger = logging.getLogger(__name__)

LAST_WATCH = "LAST_WATCH"


@contextlib.asynccontextmanager
async def lifespan():
    watch_task = asyncio.create_task(watch_latest_updates())

    try:
        yield
    finally:

        watch_task.cancel()


async def watch_latest_updates():
    while True:
        try:
            logger.debug("Poll updates start")

            for category in WATCH_CATEGORIES:
                logger.debug(f"Poll category {category}")
                caught_up_to_thread = ""
                last_watch = await cache.redis.hget(LAST_WATCH, category)

                async with f95zone.session.get(
                    f95zone.LATEST_URL.format(t="list", c=category, p=1),
                    cookies=f95zone.cookies,
                ) as req:
                    res = await req.read()

                if index_error := f95zone.check_error(res):
                    raise Exception(index_error.error_flag)

                updates = json.loads(res)
                if updates["status"] != "ok":
                    raise Exception(f"Latest updates returned an error: {updates}")

                for update in updates["msg"]["data"]:
                    thread_id = str(update["thread_id"])
                    name = cache.NAME_FORMAT.format(id=thread_id)

                    if not caught_up_to_thread:
                        caught_up_to_thread = thread_id

                    if thread_id == last_watch:
                        logger.debug(f"Stopping at {name}")
                        break

                    # Clear cache instead of fetching new data, no point
                    # fetching it if no one cares is tracking it
                    last_cached = await cache.redis.hget(name, cache.LAST_CACHED)
                    await cache.redis.hdel(name, cache.LAST_CACHED)
                    logger.info(
                        f"Invalidated cache for {name}"
                        + (
                            f" (was {dt.datetime.fromtimestamp(int(last_cached))})"
                            if last_cached
                            else ""
                        )
                    )

                if caught_up_to_thread:
                    await cache.redis.hset(LAST_WATCH, category, caught_up_to_thread)

            logger.debug("Poll updates done")

        except Exception:
            logger.error(error.traceback())

        await asyncio.sleep(WATCH_INTERVAL)
