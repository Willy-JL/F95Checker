import multiprocessing
import datetime as dt
import contextlib
import aiohttp
import asyncio
import time
import bs4
import re

from modules.structs import Game, MsgBox, Status, Tag, Type
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
            def is_text(text: str):
                def _is_text(elem: bs4.element.Tag):
                    if not hasattr(elem, "text"):
                        return False
                    val = elem.text.lower().strip()
                    return val == text or val == text + ":"
                return _is_text
            def is_class(name: str):
                def _is_class(elem: bs4.element.Tag):
                    return name in elem.get_attribute_list("class")
                return _is_class
            def game_has_prefixes(*names: list[str]):
                for name in names:
                    if head.find("span", text=f"[{name}]"):
                        return True
                return False
            def get_game_attr(*names: list[str]):
                for name in names:
                    if elem := post.find(is_text(name)):
                        break
                if not elem:
                    return ""
                elem = elem.next_sibling or elem.parent.next_sibling
                if not elem:
                    return ""
                stripped = elem.text.strip()
                if stripped == ":" or stripped == "":
                    elem = elem.next_sibling or elem.parent.next_sibling
                if not elem:
                    return ""
                return elem.text.lstrip(":").strip()
            def get_long_game_attr(*names: list[str]):
                for name in names:
                    if elem := post.find(is_text(name)):
                        break
                if not elem:
                    return ""
                value = ""
                for sibling in elem.next_siblings:
                    if sibling.name == "b":
                        break
                    stripped = sibling.text.strip()
                    if stripped == ":" or stripped == "":
                        continue
                    value += sibling.text
                value = value.replace("Spoiler", "").strip()
                while "\n\n\n" in value:
                    value = value.replace("\n\n\n", "\n\n")
                return value

            raw = await req.read()
            html = bs4.BeautifulSoup(raw, "lxml")

            if html.find(is_text("the requested thread could not be found.")):
                raise Exception(f"The F95Zone thread for {game.name} could not be found!\nIt is possible it was deleted.")

            try:
                head = html.find(is_class("p-body-header"))
                post = html.find(is_class("message-threadStarterPost"))
            finally:
                if head is None or post is None:
                    with open(f"{game.id}_broken.html", "wb") as f:
                        f.write(raw)
                    raise Exception(f"Failed to parse key sections in thread response, html has been saved to {game.id}_broken.html")

            old_name = game.name
            name = re.search(r"(?:\[[^\]]+\] - )*([^\[\|]+)", html.title.text).group(1).strip()

            old_version = game.version
            version = get_game_attr("version")
            if not version:
                if match := re.search(r"(?:\[[^\]]+\] - )*[^\[]+\[([^\]]+)\]", html.title.text):
                    version = match.group(1).strip()
            if not version:
                version = "N/A"

            old_developer = game.developer
            developer = get_game_attr("developer", "artist", "publisher", "developer/publisher", "developer / publisher").rstrip("(|-").strip()

            old_type = game.type
            # Content Types
            if game_has_prefixes("Cheat Mod"):
                type = Type.Cheat_Mod
            elif game_has_prefixes("Collection", "Manga", "SiteRip", "Comics", "CG", "Pinup", "Video", "GIF"):
                type = Type.Collection
            elif game_has_prefixes("Mod"):
                type = Type.Mod
            elif game_has_prefixes("Tool"):
                type = Type.Tool
            # Post Types
            elif game_has_prefixes("READ ME"):
                type = Type.READ_ME
            elif game_has_prefixes("Request"):
                type = Type.Request
            elif game_has_prefixes("Tutorial"):
                type = Type.Tutorial
            # Game Engines
            elif game_has_prefixes("ADRIFT"):
                type = Type.ADRIFT
            elif game_has_prefixes("Flash"):
                type = Type.Flash
            elif game_has_prefixes("HTML"):
                type = Type.HTML
            elif game_has_prefixes("Java"):
                type = Type.Java
            elif game_has_prefixes("QSP"):
                type = Type.QSP
            elif game_has_prefixes("RAGS"):
                type = Type.RAGS
            elif game_has_prefixes("RPGM"):
                type = Type.RPGM
            elif game_has_prefixes("Ren'Py"):
                type = Type.RenPy
            elif game_has_prefixes("Tads"):
                type = Type.Tads
            elif game_has_prefixes("Unity"):
                type = Type.Unity
            elif game_has_prefixes("Unreal Engine"):
                type = Type.Unreal_Engine
            elif game_has_prefixes("WebGL"):
                type = Type.WebGL
            elif game_has_prefixes("Wolf RPG"):
                type = Type.Wolf_RPG
            else:
                type = Type.Others

            old_status = game.status
            if game_has_prefixes("Completed"):
                status = Status.Completed
            elif game_has_prefixes("Onhold"):
                status = Status.OnHold
            elif game_has_prefixes("Abandoned"):
                status = Status.Abandoned
            else:
                status = Status.Normal

            url = utils.clean_thread_url(str(req.real_url))

            last_updated = 0
            text = get_game_attr("thread updated", "updated").replace("/", "-")
            try:
                last_updated = dt.datetime.fromisoformat(text).timestamp()
            except ValueError:
                pass
            if not last_updated:
                if elem := post.find(is_class("message-lastEdit")):
                    last_updated = int(elem.find("time").get("data-time"))
                else:
                    last_updated = int(post.find(is_class("message-attribution-main")).find("time").get("data-time"))

            last_full_refresh = int(time.time())

            if game.version != old_version:
                played = False
            else:
                played = game.played

            description = get_long_game_attr("overview")

            changelog = get_long_game_attr("changelog", "change-log")

            old_tags = game.tags
            tags = []
            if (taglist := head.find(is_class("js-tagList"))) is not None:
                for child in taglist.children:
                    if hasattr(child, "get") and "/tags/" in (tag := child.get("href", "")):
                        tag = tag.replace("/tags/", "").strip("/")
                        tags.append(Tag._members_[tag])

            pass  # TODO: Image

            with contextlib.suppress(asyncio.CancelledError):
                game.name = name
                game.version = version
                game.developer = developer
                game.type = type
                game.status = status
                game.url = url
                game.last_updated.update(last_updated)
                game.last_full_refresh = last_full_refresh
                game.played = played
                game.description = description
                game.changelog = changelog
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
