import multiprocessing
import aiohttp
import asyncio
import time

from modules.structs import Game, MsgBox, Status
from modules import globals, asklogin, async_thread, callbacks, db, msgbox, utils

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
    async with request("GET", globals.check_login_page) as req:
        data = await req.content.readuntil(b"_xfToken")
        data += await req.content.readuntil(b">")
        start = data.rfind(b'value="') + len(b'value="')
        end = data.find(b'"', start)
        globals.token = str(data[start:end], encoding="utf-8")
        if not 200 <= req.status < 300:  # FIXME
            print(req.status)
            print(data + await req.content.read())
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


async def check(game: Game, full=False, single=False):
    if single:
        globals.refresh_total = 2
        if not await assert_login():
            return
        globals.refresh_progress = 1

    if not full:
        async with request("HEAD", game.url) as req:
            if (redirect := str(req.real_url)) != game.url:  # FIXME
                if str(game.id) in redirect and redirect.startswith(globals.threads_page):
                    full = True
                else:
                    print(redirect)
    if full:
        print(f"{game.id} full refresh")  # TODO: get all game data


async def check_notifs():
    async with request("GET", globals.notif_endpoint, params={"_xfToken": globals.token, "_xfResponseType": "json"}) as req:
        res = await req.json()  # FIXME
        alerts = int(res["visitor"]["alerts_unread"])
        inbox  = int(res["visitor"]["conversations_unread"])
    if alerts != 0 and inbox != 0:
        title = "Notifications"
        msg = f"You have {alerts + inbox} unread notifications ({alerts} alert{'s' if alerts > 1 else ''} and {inbox} conversation{'s' if inbox > 1 else ''}).\n\nDo you want to view them?"
    elif alerts != 0 and inbox == 0:
        title = "Alerts"
        msg = f"You have {alerts} unread alert{'s' if alerts > 1 else ''}.\n\nDo you want to view {'them' if alerts > 1 else 'it'}?"
    elif alerts == 0 and inbox != 0:
        title = "Inbox"
        msg = f"You have {inbox} unread conversation{'s' if inbox > 1 else ''}.\n\nDo you want to view {'them' if inbox > 1 else 'it'}?"
    else:
        return
    def open_callback():
        if alerts > 0:
            callbacks.open_webpage(globals.alerts_page)
        if inbox > 0:
            callbacks.open_webpage(globals.inbox_page)
    buttons = {
        "󰄬 Yes": open_callback,
        "󰜺 No": None
    }
    utils.push_popup(msgbox.msgbox, title, msg, MsgBox.info, buttons)


async def refresh():
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
