import subprocess
import aiohttp
import asyncio
import shlex
import json

from modules import globals, async_thread, db

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
        timeout=globals.settings.request_timeout,
        ssl=False,
        **kwargs
    )


async def is_logged_in():
    async with request("HEAD", globals.check_login_page) as req:
        return 200 <= req.status < 300


async def login():
    proc = await asyncio.create_subprocess_exec(
        *shlex.split(globals.start_cmd), "getlogin", globals.login_page,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.PIPE
    )
    data = await proc.communicate()
    new_cookies = json.loads(data[0])
    await db.update_cookies(new_cookies)


async def refresh():
    globals.refresh_progress = 0
    globals.refresh_total = 1
    if not await is_logged_in():
        await login()
        if not await is_logged_in():
            return
    globals.refresh_progress += 1
    print("logged in!")
