import datetime as dt
import json
import logging

from indexer import f95zone
from modules import parser

logger = logging.getLogger(__name__)

ERROR_THREAD_MISSING = f95zone.IndexerError(
    "THREAD_MISSING", dt.timedelta(days=14).total_seconds()
)
ERROR_PARSING_FAILED = f95zone.IndexerError(
    "PARSING_FAILED", dt.timedelta(hours=6).total_seconds()
)


async def thread(id: int) -> dict[str, str] | None:
    thread_url = f95zone.THREAD_URL.format(thread=id)
    async with f95zone.XENFORO_RATELIMIT:
        async with f95zone.session.get(
            thread_url,
            timeout=f95zone.TIMEOUT,
            allow_redirects=True,
            max_redirects=10,
            cookies=f95zone.cookies,
        ) as req:
            res = await req.read()

    if index_error := f95zone.check_error(res):
        return index_error

    if req.status in (403, 404):
        return ERROR_THREAD_MISSING

    # TODO: Intensive operation, move to threads+queue
    ret = parser.thread(id, res, False)
    if isinstance(ret, parser.ParserException):
        logger.error(f"Thread {id} parsing failed:" + ret.args[1])
        return ERROR_PARSING_FAILED

    # TODO: maybe add an error flag for threads outside of
    # games/media/mods forums so it wont get cached for no reason

    # Redact unmasked links to prevent abuse, since this api is public
    # Replaces with thread link, so user can click it and go find it anyway
    parsed = ret._asdict()
    for label, links in parsed["downloads"]:
        for link_i, (link_name, link_url) in enumerate(links):
            if not link_url.startswith(f95zone.MASKED_URL):
                links[link_i] = (link_name, thread_url)

    # Prepare for redis, only strings allowed
    parsed["type"] = str(int(parsed["type"]))
    parsed["status"] = str(int(parsed["status"]))
    parsed["last_updated"] = str(parsed["last_updated"])
    parsed["score"] = str(parsed["score"])
    parsed["votes"] = str(parsed["votes"])
    parsed["tags"] = json.dumps(parsed["tags"])
    parsed["unknown_tags"] = json.dumps(parsed["unknown_tags"])
    parsed["downloads"] = json.dumps(parsed["downloads"])
    return parsed
