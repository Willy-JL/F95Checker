import multiprocessing
import aiohttp
import asyncio
import random

from modules.structs import Game, Status
from modules import globals, asklogin, async_thread, db

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
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    proc = ctx.Process(target=asklogin.asklogin, args=(globals.login_page, queue,), daemon=True)
    proc.start()
    try:
        while queue.empty():
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        proc.kill()
        raise
    new_cookies = queue.get()
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
