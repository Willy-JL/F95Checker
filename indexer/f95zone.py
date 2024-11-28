import asyncio
import contextlib
import dataclasses
import datetime as dt
import logging
import os
import sys

import aiohttp
import aiolimiter

RATELIMIT = aiolimiter.AsyncLimiter(max_rate=1, time_period=0.5)
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
THREAD_URL = f"{HOST}/threads/{{thread}}"
LATEST_URL = f"{HOST}/sam/latest_alpha/latest_data.php?cmd={{cmd}}&cat={{cat}}&page={{page}}&sort={{sort}}&rows={{rows}}&_={{ts}}"
VERCHK_URL = f"{HOST}/sam/checker.php?threads={{threads}}"


@dataclasses.dataclass
class IndexerError:
    error_flag: str
    retry_delay: int


ERROR_SESSION_LOGGED_OUT = IndexerError(
    "SESSION_LOGGED_OUT", dt.timedelta(hours=2).total_seconds()
)
ERROR_FORUM_RATELIMIT = IndexerError(
    "FORUM_RATELIMIT", dt.timedelta(minutes=15).total_seconds()
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
ERROR_UNKNOWN_RESPONSE = IndexerError(
    "UNKNOWN_RESPONSE", dt.timedelta(hours=6).total_seconds()
)
ERROR_INTERNAL_ERROR = IndexerError(
    "INTERNAL_ERROR", dt.timedelta(hours=6).total_seconds()
)


@contextlib.asynccontextmanager
async def lifespan(version: str):
    global session, cookies
    session = aiohttp.ClientSession(
        cookie_jar=aiohttp.DummyCookieJar(),
        timeout=TIMEOUT,
        headers={
            "User-Agent": (
                f"F95Indexer/{version} "
                f"Python/{sys.version.split(' ')[0]} "
                f"aiohttp/{aiohttp.__version__}"
            ),
        },
    )
    cookies = {
        "xf_user": os.environ.get("COOKIE_XF_USER"),
    }

    try:
        yield
    finally:

        await session.close()
        session = None


def check_error(res: bytes | Exception) -> IndexerError | None:
    if isinstance(res, bytes):
        if any((msg in res) for msg in LOGIN_ERROR_MESSAGES):
            logger.error("Logged out of F95zone")
            # TODO: maybe auto login, but xf_user cookie should be enough for a long time
            return ERROR_SESSION_LOGGED_OUT

        if any((msg in res) for msg in RATELIMIT_ERROR_MESSAGES):
            logger.error("Hit F95zone ratelimit")
            return ERROR_FORUM_RATELIMIT

        if any((msg in res) for msg in TEMP_ERROR_MESSAGES):
            logger.warning("F95zone temporarily unreachable")
            return ERROR_F95ZONE_UNAVAILABLE

        return None

    elif isinstance(res, Exception):
        if isinstance(res, asyncio.TimeoutError):
            logger.warning("F95zone temporarily unreachable")
            return ERROR_F95ZONE_UNAVAILABLE

        return None
