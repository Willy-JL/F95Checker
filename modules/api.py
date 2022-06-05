import multiprocessing
import datetime as dt
import contextlib
import aiohttp
import asyncio
import time
import bs4
import re

from modules.structs import Game, MsgBox, Status, Tag
from modules import globals, asklogin, async_thread, callbacks, db, msgbox, utils

session: aiohttp.ClientSession = None
full_check_interval = int(dt.timedelta(days=7).total_seconds())


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
    try:
        proc.start()
        while queue.empty():
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        proc.kill()
        raise
    with contextlib.suppress(asyncio.CancelledError):
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

    full = full or game.last_full_refresh < time.time() - full_check_interval
    if not full:
        async with request("HEAD", game.url) as req:
            if (redirect := str(req.real_url)) != game.url:  # FIXME
                if str(game.id) in redirect and redirect.startswith(globals.threads_page):
                    full = True
                else:
                    print(redirect)
    if full:
        async with request("GET", game.url) as req:
            def text_val(text: str):
                def _text_val(elem: bs4.element.Tag):
                    if not hasattr(elem, "text"):
                        return False
                    val = elem.text.lower()
                    return val == text or val == text + ":"
                return _text_val
            def has_class(name: str):
                def _has_class(elem: bs4.element.Tag):
                    return name in elem.get_attribute_list("class")
                return _has_class
            raw = await req.read()
            html = bs4.BeautifulSoup(raw, "lxml")
            try:
                head = html.find(has_class("p-body-header"))
                post = html.find(has_class("message-threadStarterPost"))
            finally:
                if head is None or post is None:
                    with open(f"{game.id}_broken.html", "wb") as f:
                        f.write(raw)
                    raise Exception(f"Failed to parse key sections in thread response, html has been saved to {game.id}_broken.html")

            old_name = game.name
            name = re.search(r"(?:\[[^\]]+\] - )*([^\[]+)", html.title.text).group(1).strip()

            old_version = game.version
            elem = post.find(text_val("version"))
            if elem:
                version = elem.next_sibling.get_text().lstrip(":").strip()
            else:
                version = re.search(r"(?:\[[^\]]+\] - )*[^\[]+\[([^\]]+)\]", html.title.text).group(1).strip()

            old_developer = game.developer
            elem = post.find(text_val("developer"))
            if elem:
                developer = elem.next_sibling.get_text().lstrip(":").strip()
            else:
                developer = ""

            old_type = game.type
            pass  # TODO: Type

            old_status = game.status
            # FIXME
            if head.find("span", text="[Completed]"):
                status = Status.Completed
            elif head.find("span", text="[Onhold]"):
                status = Status.OnHold
            elif head.find("span", text="[Abandoned]"):
                status = Status.Abandoned
            else:
                status = Status.Normal

            url = utils.clean_thread_url(str(req.real_url))

            elem = post.find(text_val("thread updated")) or post.find(text_val("updated"))
            last_updated = None
            if elem:
                text = elem.next_sibling.text.lstrip(":").strip().replace("/", "-")
                try:
                    last_updated = dt.datetime.fromisoformat(text).timestamp()
                except ValueError:
                    pass
            if not last_updated:
                elem = post.find(has_class("message-lastEdit"))
                if elem:
                    last_updated = int(list(elem.children)[1].get("data-time"))
                else:
                    last_updated = int(post.find(has_class("message-attribution-main")).find("time").get("data-time"))

            last_full_refresh = int(time.time())

            if game.version != old_version:
                played = False
            else:
                played = game.played

            pass  # TODO: Description

            pass  # TODO: Changelog

            old_tags = game.tags
            tags = []
            tagl = head.find(has_class("js-tagList"))
            if tagl is not None:
                for child in tagl.children:
                    if hasattr(child, "get") and "/tags/" in (tag := child.get("href", "")):
                        tag = tag.replace("/tags/", "").strip("/")
                        tags.append(Tag._members_[tag])

            pass  # TODO: Image

            with contextlib.suppress(asyncio.CancelledError):
                game.name = name
                game.version = version
                game.developer = developer
                # game.type = type
                game.status = status
                game.url = url
                game.last_updated.update(last_updated)
                game.last_full_refresh = last_full_refresh
                game.played = played
                # game.description = description
                # game.changelog = changelog
                game.tags = tags
                # game.image = image
                await db.update_game(game, "name", "version", "developer", "type", "status", "url", "last_updated", "last_full_refresh", "played", "description", "changelog", "tags")
            # TODO: show updated games


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


async def refresh(full=False):
    if not await assert_login():
        return

    game_queue = asyncio.Queue()
    async def worker():
        while not game_queue.empty() and utils.is_refreshing():
            try:
                await check(game_queue.get_nowait(), full=full)
            except Exception:
                game_refresh_task.cancel()
                raise
            globals.refresh_progress += 1

    for game in globals.games.values():
        if game.status is Status.Completed and not globals.settings.refresh_completed_games:
            continue
        game_queue.put_nowait(game)

    globals.refresh_progress += 1
    globals.refresh_total += game_queue.qsize() + 1

    game_refresh_task = asyncio.gather(*[worker() for _ in range(globals.settings.refresh_workers)])
    await game_refresh_task

    await check_notifs()
