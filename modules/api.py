import subprocess
import aiohttp
import asyncio
import random
import shlex
import json

from modules.structs import Game, Status
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
        *shlex.split(globals.start_cmd), "asklogin", globals.login_page,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.PIPE
    )
    globals.subprocesses.append(proc)
    try:
        data = await proc.communicate()
    except asyncio.CancelledError:
        proc.kill()
        globals.subprocesses.remove(proc)
        raise
    new_cookies = json.loads(data[0])
    await db.update_cookies(new_cookies)


async def check(game: Game):
    try:
        await asyncio.sleep(random.random())
        print(game.id)
    except asyncio.CancelledError:
        print(f"cancelled {game.id}")
        raise


async def check_notifs():
    try:
        await asyncio.sleep(random.random())
        print("notifs")
    except asyncio.CancelledError:
        print("cancelled notifs")
        raise


async def refresh():
    globals.refresh_progress = 0
    globals.refresh_total = 1

    if not await is_logged_in():
        await login()
        if not await is_logged_in():
            return

    refresh_tasks = asyncio.Queue()
    async def worker():
        while not refresh_tasks.empty():
            await refresh_tasks.get_nowait()
            globals.refresh_progress += 1

    for game in globals.games.values():
        if game.status is Status.Completed and not globals.settings.refresh_completed_games:
            continue
        refresh_tasks.put_nowait(check(game))
    refresh_tasks.put_nowait(check_notifs())

    globals.refresh_progress += 1
    globals.refresh_total += refresh_tasks.qsize()

    try:
        await asyncio.gather(*[worker() for _ in range(globals.settings.refresh_workers)])
    except asyncio.CancelledError:
        return
