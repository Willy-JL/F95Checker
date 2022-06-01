import multiprocessing
import aiohttp
import asyncio
import random
import time

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
    while queue.empty():
        await asyncio.sleep(0.1)
    new_cookies = queue.get()
    await db.update_cookies(new_cookies)


async def assert_login():
    if not await is_logged_in():
        await login()
        if not await is_logged_in():
            return False
    return True


async def check(game: Game, full=False):
    full = full or game.last_full_refresh < time.time() - 172800  # 2 days  # TODO: check how viable this might be
    if not full:
        async with request("HEAD", game.url) as req:
            if (redirect := str(req.real_url)) != game.url and str(game.id) in redirect and redirect.startswith(globals.threads_page):  # FIXME
                full = True
    if full:
        print(f"{game.id} full refresh")  # TODO: get all game data


async def check_notifs():
    await asyncio.sleep(random.random())
    print("notifs")


async def refresh():
    globals.refresh_progress = 0
    globals.refresh_total = 1

    if not await assert_login():
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

    await asyncio.gather(*[worker() for _ in range(globals.settings.refresh_workers)])
