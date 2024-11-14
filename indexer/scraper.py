import contextlib
import json
import logging
import sys

import aiohttp
import aiolimiter

from modules import parser

XENFORO_RATELIMIT = aiolimiter.AsyncLimiter(max_rate=6, time_period=2)
TIMEOUT = 30
LOGIN_ERROR_MESSAGES = (
    b'<a href="/login/" data-xf-click="overlay">Log in or register now.</a>',
    b"<title>Log in | F95zone</title>",
    b"<title>DDOS-GUARD</title>",
)
RATELIMIT_ERROR_MESSAGES = (
    b"<title>Error 429</title>",
    b"<title>DDOS-GUARD</title>",
)
TEMP_ERROR_MESSAGES = (
    b"<title>502 Bad Gateway</title>",
    b"<!-- Too many connections -->",
    b"<p>Automated backups are currently executing. During this time, the site will be unavailable</p>",
)

logger = logging.getLogger(__name__)
session: aiohttp.ClientSession = None

THREAD_URL = "https://f95zone.to/threads/{thread}"


@contextlib.asynccontextmanager
async def lifespan(version: str):
    global session
    session = aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar())
    session.headers["User-Agent"] = (
        f"F95Indexer/{version} "
        f"Python/{sys.version.split(' ')[0]} "
        f"aiohttp/{aiohttp.__version__}"
    )

    try:
        yield
    finally:

        await session.close()
        session = None


async def thread(id: int) -> dict[str, str] | None:
    async with XENFORO_RATELIMIT:
        async with session.get(
            THREAD_URL.format(thread=id),
            timeout=TIMEOUT,
            allow_redirects=True,
            max_redirects=10,
            cookies={
                "xf_user": os.environ.get("COOKIE_XF_USER"),
            },
        ) as req:
            if req.status in (403, 404):
                # Thread doesn't exist
                return {}
            res = await req.read()

    if any((msg in res) for msg in LOGIN_ERROR_MESSAGES):
        logger.error("Logged out of F95zone")
        # TODO: maybe auto login, but xf_user cookie should be enough for a long time
        return None
    if any((msg in res) for msg in RATELIMIT_ERROR_MESSAGES):
        logger.error("Hit F95zone ratelimit")
        # FIXME: wait for a bit and retry
        return None
    if any((msg in res) for msg in TEMP_ERROR_MESSAGES):
        logger.warning("F95zone temporarily unreachable")
        return None

    # TODO: Intensive operation, move to threads+queue
    ret = parser.thread(id, res, False)
    if isinstance(ret, parser.ParserException):
        logger.error(f"Thread {id} parsing failed:" + ret.args[1])

    # Prepare for redis, only strings allowed
    parsed = ret._asdict()
    parsed["type"] = str(int(parsed["type"]))
    parsed["status"] = str(int(parsed["status"]))
    parsed["last_updated"] = str(parsed["last_updated"])
    parsed["score"] = str(parsed["score"])
    parsed["votes"] = str(parsed["votes"])
    parsed["tags"] = json.dumps(parsed["tags"])
    parsed["unknown_tags"] = json.dumps(parsed["unknown_tags"])
    parsed["downloads"] = json.dumps(parsed["downloads"])
    return parsed
