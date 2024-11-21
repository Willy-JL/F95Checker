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

WATCH_UPDATES_INTERVAL = dt.timedelta(minutes=5).total_seconds()
WATCH_UPDATES_CATEGORIES = (
    "games",
    "comics",
    "animations",
)
WATCH_VERSIONS_INTERVAL = dt.timedelta(hours=12).total_seconds()
WATCH_VERSIONS_CHUNK_SIZE = 1000

logger = logging.getLogger(__name__)

LAST_WATCH = "LAST_WATCH"


@contextlib.asynccontextmanager
async def lifespan():
    updates_task = asyncio.create_task(watch_updates())
    versions_task = asyncio.create_task(watch_versions())

    try:
        yield
    finally:

        updates_task.cancel()
        versions_task.cancel()


# https://stackoverflow.com/a/312464
def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def watch_updates():
    while True:
        try:
            logger.debug("Poll updates start")

            for category in WATCH_UPDATES_CATEGORIES:
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

                try:
                    updates = json.loads(res)
                except Exception:
                    raise Exception(f"Latest updates returned invalid JSON: {res}")
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
                    # Delete version too to avoid watch_versions() picking it up as mismatch
                    last_cached = await cache.redis.hget(name, cache.LAST_CACHED)
                    await cache.redis.hdel(name, cache.LAST_CACHED, "version")
                    logger.info(
                        f"Updates: Invalidated cache for {name}"
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
            logger.error(f"Error polling updates: {error.text()}\n{error.traceback()}")

        await asyncio.sleep(WATCH_UPDATES_INTERVAL)


async def watch_versions():
    while True:
        await asyncio.sleep(WATCH_VERSIONS_INTERVAL)

        try:
            logger.debug("Poll versions start")

            names = [n async for n in cache.redis.scan_iter("thread:*", 10000, "hash")]
            invalidate_cache = cache.redis.pipeline()

            for names_chunk in chunks(names, WATCH_VERSIONS_CHUNK_SIZE):

                cached_versions = cache.redis.pipeline()
                csv = ""
                ids = []
                for name in names_chunk:
                    cached_versions.hget(name, "version")
                    id = name.split(":")[1]
                    csv += f"{id},"
                    ids.append(id)
                csv = csv.strip(",")

                async with f95zone.session.get(
                    f95zone.VERCHK_URL.format(threads=csv),
                ) as req:
                    # Await together for efficiency
                    res, cached_versions = await asyncio.gather(
                        req.read(), cached_versions.execute()
                    )

                if index_error := f95zone.check_error(res):
                    raise Exception(index_error.error_flag)

                try:
                    versions = json.loads(res)
                except Exception:
                    raise Exception(f"Versions API returned invalid JSON: {res}")
                if (
                    versions["status"] == "error"
                    and versions["msg"] == "Thread not found"
                ):
                    continue
                elif versions["status"] != "ok":
                    raise Exception(f"Versions API returned an error: {versions}")
                versions = versions["msg"]

                assert len(names_chunk) == len(ids) == len(cached_versions)
                for name, id, cached_version in zip(names_chunk, ids, cached_versions):
                    if cached_version is None:
                        continue
                    version = versions.get(id)
                    if not version or version == "Unknown":
                        continue

                    if version != cached_version:
                        # Delete version too to avoid ending up here again
                        invalidate_cache.hdel(name, cache.LAST_CACHED, "version")
                        logger.warning(
                            f"Versions: Invalidating cache for {name}"
                            f" ({cached_version!r} -> {version!r})"
                        )

            if len(invalidate_cache):
                result = await invalidate_cache.execute()
                invalidated = sum(ret != "0" for ret in result)
                logger.warning(f"Version invalidated cache for {invalidated} threads")

            logger.debug("Poll versions done")

        except Exception:
            logger.error(f"Error polling versions: {error.text()}\n{error.traceback()}")
