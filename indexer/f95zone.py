import collections
import contextlib
import datetime as dt
import logging
import os
import sys

import aiohttp
import aiolimiter

XENFORO_RATELIMIT = aiolimiter.AsyncLimiter(max_rate=6, time_period=2)
TIMEOUT = aiohttp.ClientTimeout(total=30)
LOGIN_ERROR_MESSAGES = (
    b'<a href="/login/" data-xf-click="overlay">Log in or register now.</a>',
    b"<title>Log in | F95zone</title>",
    b'<form action="/login/login" method="post" class="block"',
)
RATELIMIT_ERROR_MESSAGES = (
    b"<title>429 Too Many Requests</title>",
    b"<h1>429 Too Many Requests</h1>",
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
cookies: dict = None

HOST = "https://f95zone.to"
THREAD_URL = HOST + "/threads/{thread}"
MASKED_URL = HOST + "/masked/"
LATEST_URL = HOST + "/sam/latest_alpha/latest_data.php?cmd={t}&cat={c}&page={p}&rows=90"
VERCHK_URL = HOST + "/sam/checker.php?threads={threads}"

IndexerError = collections.namedtuple(
    "IndexerError",
    (
        "error_flag",
        "retry_delay",
    ),
)

ERROR_SESSION_LOGGED_OUT = IndexerError(
    "SESSION_LOGGED_OUT", dt.timedelta(hours=2).total_seconds()
)
ERROR_XENFORO_RATELIMIT = IndexerError(
    "XENFORO_RATELIMIT", dt.timedelta(minutes=15).total_seconds()
)
ERROR_F95ZONE_UNAVAILABLE = IndexerError(
    "F95ZONE_UNAVAILABLE", dt.timedelta(minutes=15).total_seconds()
)
ERROR_THREAD_MISSING = IndexerError(
    "THREAD_MISSING", dt.timedelta(days=14).total_seconds()
)
ERROR_PARSING_FAILED = IndexerError(
    "PARSING_FAILED", dt.timedelta(hours=6).total_seconds()
)
ERROR_VERSION_FAILED = IndexerError(
    "VERSION_FAILED", dt.timedelta(hours=6).total_seconds()
)


@contextlib.asynccontextmanager
async def lifespan(version: str):
    global session, cookies
    session = aiohttp.ClientSession(
        cookie_jar=aiohttp.DummyCookieJar(),
        timeout=TIMEOUT,
    )
    session.headers["User-Agent"] = (
        f"F95Indexer/{version} "
        f"Python/{sys.version.split(' ')[0]} "
        f"aiohttp/{aiohttp.__version__}"
    )
    cookies = {
        "xf_user": os.environ.get("COOKIE_XF_USER"),
    }

    try:
        yield
    finally:

        await session.close()
        session = None


def check_error(res: bytes) -> IndexerError | None:
    if any((msg in res) for msg in LOGIN_ERROR_MESSAGES):
        logger.error("Logged out of F95zone")
        # TODO: maybe auto login, but xf_user cookie should be enough for a long time
        return ERROR_SESSION_LOGGED_OUT

    if any((msg in res) for msg in RATELIMIT_ERROR_MESSAGES):
        logger.error("Hit F95zone ratelimit")
        return ERROR_XENFORO_RATELIMIT

    if any((msg in res) for msg in TEMP_ERROR_MESSAGES):
        logger.warning("F95zone temporarily unreachable")
        return ERROR_F95ZONE_UNAVAILABLE

    return None
