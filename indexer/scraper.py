import asyncio
import dataclasses
import json
import logging

from common import parser
from indexer import f95zone

logger = logging.getLogger(__name__)


async def thread(id: int) -> dict[str, str] | None:
    thread_url = f95zone.THREAD_URL.format(thread=id)
    retries = 10
    while retries:
        async with f95zone.XENFORO_RATELIMIT:
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

    if index_error := f95zone.check_error(res):
        return index_error

    if req.status in (403, 404):
        return f95zone.ERROR_THREAD_MISSING

    loop = asyncio.get_event_loop()
    ret = await loop.run_in_executor(None, parser.thread, res)
    if isinstance(ret, parser.ParserError):
        logger.error(f"Thread {id} parsing failed: {ret.message}\n{ret.dump}")
        return f95zone.ERROR_PARSING_FAILED

    # TODO: maybe add an error flag for threads outside of
    # games/media/mods forums so it wont get cached for no reason

    version = ""
    async with f95zone.session.get(
        f95zone.VERCHK_URL.format(threads=id),
    ) as req:
        res = await req.read()
    if index_error := f95zone.check_error(res):
        return index_error
    try:
        versions = json.loads(res)
    except Exception:
        logger.error(f"Thread {id} version returned invalid JSON: {res}")
        return f95zone.ERROR_UNKNOWN_RESPONSE
    if versions["status"] == "ok":
        version = versions["msg"][str(id)]
        if version == "Unknown":
            version = ""
    elif versions["status"] == "error" and versions["msg"] == "Thread not found":
        pass
    else:
        logger.error(f"Thread {id} version returned an error: {versions}")
        return f95zone.ERROR_UNKNOWN_RESPONSE

    # Redact unmasked links to prevent abuse, since this api is public
    # Replaces with thread link, so user can click it and go find it anyway
    for label, links in ret.downloads:
        for link_i, (link_name, link_url) in enumerate(links):
            if not link_url.startswith(f95zone.MASKED_URL):
                links[link_i] = (link_name, thread_url)

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
    parsed["downloads"] = json.dumps(parsed["downloads"])
    return parsed
