import contextlib
import json
import logging
import pathlib
import subprocess
import sys

import aiohttp
import aiolimiter

from modules import parser

xenforo_ratelimit = aiolimiter.AsyncLimiter(max_rate=6, time_period=2)

logger = logging.getLogger(__name__)
session: aiohttp.ClientSession = None
thread_url = "https://f95zone.to/threads/{thread}"
timeout = 30
login_error_messages = (
    b'<a href="/login/" data-xf-click="overlay">Log in or register now.</a>',
    b"<title>Log in | F95zone</title>",
    b"<title>DDOS-GUARD</title>",
)
ratelimit_error_messages = (
    b"<title>Error 429</title>",
    b"<title>DDOS-GUARD</title>",
)
temp_error_messages = (
    b"<title>502 Bad Gateway</title>",
    b"<!-- Too many connections -->",
    b"<p>Automated backups are currently executing. During this time, the site will be unavailable</p>",
)


@contextlib.asynccontextmanager
async def lifespan():
    global session
    session = aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar())
    try:
        version = subprocess.check_output(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=pathlib.Path(__file__).parent,
            encoding="utf-8",
        ).strip()
    except subprocess.CalledProcessError:
        version = "unknown"
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


async def thread(id: int) -> dict[str, str | int] | None:
    async with xenforo_ratelimit:
        async with session.get(
            thread_url.format(thread=id),
            timeout=timeout,
            allow_redirects=True,
            max_redirects=10,
            cookies={},  # FIXME: auth
        ) as req:
            if req.status in (403, 404):
                # Thread doesn't exist
                return {}
            res = await req.read()

    if any((msg in res) for msg in login_error_messages):
        logger.error("Logged out of F95zone")
        # FIXME: login
        return None
    if any((msg in res) for msg in ratelimit_error_messages):
        logger.error("Hit F95zone ratelimit")
        # FIXME: wait for a bit and retry
        return None
    if any((msg in res) for msg in temp_error_messages):
        logger.warning("F95zone temporarily unreachable")
        return None

    # TODO: Intensive operation, move to threads+queue
    ret = parser.thread(id, res, False)
    if isinstance(ret, parser.ParserException):
        logger.error(f"Thread {id} parsing failed:" + ret.args[1])

    parsed = ret._asdict()
    parsed["downloads"] = json.dumps(parsed["downloads"])
    parsed["status"] = int(parsed["status"])
    parsed["tags"] = json.dumps(parsed["tags"])
    parsed["type"] = int(parsed["type"])
    parsed["unknown_tags"] = json.dumps(parsed["unknown_tags"])
    return parsed
