import asyncio
import json
import logging

from indexer import f95zone
from modules import parser

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
                    await asyncio.sleep(0.5)
                    retries -= 1;
                    continue
                res = await req.read()
                break

    if index_error := f95zone.check_error(res):
        return index_error

    if req.status in (403, 404):
        return f95zone.ERROR_THREAD_MISSING

    # TODO: Intensive operation, move to threads+queue
    ret = parser.thread(id, res, False)
    if isinstance(ret, parser.ParserException):
        logger.error(f"Thread {id} parsing failed: {ret.args[1]}\n{res}")
        return f95zone.ERROR_PARSING_FAILED

    # TODO: maybe add an error flag for threads outside of
    # games/media/mods forums so it wont get cached for no reason

    version = ""
    async with f95zone.session.get(
        f95zone.VERCHK_URL.format(threads=id),
        cookies=f95zone.cookies,
    ) as req:
        res = await req.read()
    versions = json.loads(res)
    if versions["status"] == "ok":
        version = versions["msg"][str(id)]
    elif versions["status"] == "error" and versions["msg"] == "Thread not found":
        pass
    else:
        logger.error(f"Thread {id} version failed: {versions}")
        return f95zone.ERROR_VERSION_FAILED

    # Redact unmasked links to prevent abuse, since this api is public
    # Replaces with thread link, so user can click it and go find it anyway
    parsed = ret._asdict()
    for label, links in parsed["downloads"]:
        for link_i, (link_name, link_url) in enumerate(links):
            if not link_url.startswith(f95zone.MASKED_URL):
                links[link_i] = (link_name, thread_url)

    # Prepare for redis, only strings allowed
    parsed["version"] = version if version else parsed["thread_version"]
    del parsed["thread_version"]  # TODO: Recache more often if using thread_version
    parsed["type"] = str(int(parsed["type"]))
    parsed["status"] = str(int(parsed["status"]))
    parsed["last_updated"] = str(parsed["last_updated"])
    parsed["score"] = str(parsed["score"])
    parsed["votes"] = str(parsed["votes"])
    parsed["tags"] = json.dumps(parsed["tags"])
    parsed["unknown_tags"] = json.dumps(parsed["unknown_tags"])
    parsed["downloads"] = json.dumps(parsed["downloads"])
    return parsed
