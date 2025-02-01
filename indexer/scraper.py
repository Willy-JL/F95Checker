import asyncio
import dataclasses
import json
import logging
import re
import time

from common import parser
from indexer import f95zone

logger = logging.getLogger(__name__)


async def thread(id: int) -> dict[str, str] | f95zone.IndexerError | None:
    thread_url = f95zone.THREAD_URL.format(thread=id)
    retries = 10
    while retries:
        async with f95zone.RATELIMIT:
            try:
                async with f95zone.session.get(
                    thread_url,
                    cookies=f95zone.cookies,
                ) as req:
                    if req.status == 429 and retries > 1:
                        logger.warning("Hit a ratelimit, sleeping 2 seconds")
                        await asyncio.sleep(2)
                        retries -= 1
                        continue
                    res = await req.read()
                    break
            except Exception as exc:
                if index_error := f95zone.check_error(exc, logger):
                    return index_error
                raise

    if index_error := f95zone.check_error(res, logger):
        return index_error

    loop = asyncio.get_event_loop()
    ret = await loop.run_in_executor(None, parser.thread, res)
    if isinstance(ret, parser.ParserError):

        if ret.message == "Thread structure missing" and req.status in (403, 404):
            return f95zone.ERROR_THREAD_MISSING

        logger.error(f"Thread {id} parsing failed: {ret.message}\n{ret.dump}")
        return f95zone.ERROR_PARSING_FAILED

    # TODO: maybe add an error flag for threads outside of
    # games/media/mods forums so it wont get cached for no reason

    # Check if thread is tracked by latest updates using version API, then keep this version value
    version = ""
    try:
        async with f95zone.session.get(
            f95zone.VERCHK_URL.format(threads=id),
        ) as req:
            res = await req.read()
    except Exception as exc:
        if index_error := f95zone.check_error(exc, logger):
            return index_error
        raise
    if index_error := f95zone.check_error(res, logger):
        return index_error
    try:
        versions = json.loads(res)
    except Exception:
        logger.error(f"Thread {id} version returned invalid JSON: {res}")
        return f95zone.ERROR_UNKNOWN_RESPONSE
    if versions.get("msg") in ("Missing threads data", "Thread not found"):
        versions["status"] = "ok"
        versions["msg"] = {}
    if index_error := f95zone.check_error(versions, logger):
        return index_error
    if str(id) in versions["msg"]:
        version = versions["msg"][str(id)]
        if version == "Unknown":
            version = ""

    # If tracked by latest updates, try to search the thread there to get more precise details
    if version:
        query = ret.name.encode("ascii", errors="replace").decode()
        query = re.sub(r"\.+ | \.+", " ", query)
        for char in "?&/':;-":
            query = query.replace(char, " ")
        query = re.sub(r"\s+", " ", query).strip()[:28]
        if len(words := query.split(" ")) > 2 and len(words[-1]) < 3:
            query = " ".join(words[:-1])
        for category in f95zone.LATEST_CATEGORIES:

            try:
                async with f95zone.session.get(
                    f95zone.SEARCH_URL.format(
                        cmd="list",
                        cat=category,
                        page=1,
                        search="search",
                        query=query,
                        sort="likes",
                        rows=90,
                        ts=int(time.time()),
                    ),
                    cookies=f95zone.cookies,
                ) as req:
                    res = await req.read()
            except Exception as exc:
                if index_error := f95zone.check_error(exc, logger):
                    return index_error
                raise
            if index_error := f95zone.check_error(res, logger):
                return index_error
            try:
                updates = json.loads(res)
            except Exception:
                logger.error(f"Thread {id} search returned invalid JSON: {res}")
                return f95zone.ERROR_UNKNOWN_RESPONSE
            if index_error := f95zone.check_error(updates, logger):
                return index_error

            for update in updates["msg"]["data"]:
                if update["thread_id"] == id:
                    ret.name = update["title"] or ret.name
                    ret.developer = update["creator"] or ret.developer
                    ret.score = round(update["rating"], 1)
                    ret.image_url = parser.attachment(update["cover"]) or ret.image_url
                    ret.previews_urls = [
                        parser.attachment(preview_url)
                        for preview_url in update["screens"]
                    ] or ret.previews_urls
                    ret.last_updated = parser.datestamp(update["ts"])
                    break
            else:  # Didn't break
                continue
            break

        else:  # Didn't break
            logger.warning(f"Thread {id} not found in latest updates search")

    retries = 10
    while retries:
        async with f95zone.RATELIMIT:
            try:
                async with f95zone.session.get(
                    thread_url + "/br-reviews",
                    cookies=f95zone.cookies,
                ) as req:
                    if req.status == 429 and retries > 1:
                        logger.warning("Hit a ratelimit, sleeping 2 seconds")
                        await asyncio.sleep(2)
                        retries -= 1
                        continue
                    res = await req.read()
                    break
            except Exception as exc:
                if index_error := f95zone.check_error(exc, logger):
                    return index_error
                raise

    if index_error := f95zone.check_error(res, logger):
        return index_error

    reviews = await loop.run_in_executor(None, parser.reviews, res)
    if isinstance(reviews, parser.ParserError):

        if reviews.message == "Thread structure missing" and req.status in (403, 404):
            return f95zone.ERROR_THREAD_MISSING

        logger.error(f"Thread {id} reviews parsing failed: {reviews.message}\n{reviews.dump}")
        return f95zone.ERROR_PARSING_FAILED

    reviews.items = [dataclasses.asdict(review) for review in reviews.items]

    # Prepare for redis, only strings allowed
    parsed = dataclasses.asdict(ret)
    if version:
        parsed["version"] = version
        del parsed["thread_version"]
    else:
        parsed["version"] = parsed["thread_version"]
        # Leave thread_version set so cache knows to use a lower TTL,
        # but only if the thread had a valid version detected
        if not parsed["thread_version"]:
            del parsed["thread_version"]
    parsed["type"] = str(int(parsed["type"]))
    parsed["status"] = str(int(parsed["status"]))
    parsed["last_updated"] = str(parsed["last_updated"])
    parsed["score"] = str(parsed["score"])
    parsed["votes"] = str(parsed["votes"])
    parsed["tags"] = json.dumps(parsed["tags"])
    parsed["unknown_tags"] = json.dumps(parsed["unknown_tags"])
    parsed["previews_urls"] = json.dumps(parsed["previews_urls"])
    parsed["downloads"] = json.dumps(parsed["downloads"])
    parsed["reviews_total"] = str(reviews.total)
    parsed["reviews"] = json.dumps(reviews.items)
    return parsed
