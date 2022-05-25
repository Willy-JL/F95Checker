import aiohttp

from modules import globals, async_thread

session: aiohttp.ClientSession = None


def setup():
    global session
    session = aiohttp.ClientSession(loop=async_thread.loop)


async def shutdown():
    await session.close()


def request(method: str, url: str, **kwargs):
    return session.request(
        method,
        url,
        cookies=globals.cookies,
        # headers=...,
        allow_redirects=True,
        raise_for_status=True,
        timeout=globals.settings.request_timeout,
        ssl=False,
        **kwargs
    )
