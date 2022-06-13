import multiprocessing
import datetime as dt
import contextlib
import tempfile
import aiohttp
import asyncio
import time
import bs4
import os
import re

from modules.structs import CounterContext, Game, MsgBox, OldGame, SearchResult, Status, Tag, Type
from modules import globals, asklogin, async_thread, callbacks, db, msgbox, utils

session: aiohttp.ClientSession = None
full_check_interval = int(dt.timedelta(days=7).total_seconds())
image_sem = asyncio.Semaphore(2)
image_counter = CounterContext()
full_counter = CounterContext()
updated_games: dict[int, OldGame] = {}


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
            data += await req.content.read()
            if b"<p>Automated backups are currently executing. During this time, the site will be unavailable</p>" in data:
                raise msgbox.Exc("Backups", "F95Zone is currently running some backups,\nplease retry in a few minutes!", MsgBox.warn)
            # if b"<title>DDOS-GUARD</title>" in data:
            #     raise Exception("Captcha needed!")
            print(data)
            print(req.status)
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


async def download_webpage(url: str):
    if not await assert_login():
        return
    async with request("GET", url) as req:
        raw = await req.read()
    html = bs4.BeautifulSoup(raw, "lxml")
    for elem in html.find_all():
        for key, value in elem.attrs.items():
            if isinstance(value, str) and value.startswith("/"):
                elem.attrs[key] = globals.domain + value
    with tempfile.NamedTemporaryFile("wb", prefix="F95Checker-", suffix=".html", delete=False) as f:
        f.write(html.prettify(encoding="utf-8"))
    return f.name


async def quick_search(query: str):
    if not await assert_login():
        return
    async with request("POST", globals.qsearch_endpoint, data={
        "title": query,
        "_xfToken": globals.token
    }) as req:
        raw = await req.read()
    html = bs4.BeautifulSoup(raw, "lxml")
    results = []
    for row in html.find(is_class("quicksearch-wrapper-wide")).find_all(is_class("dataList-row")):
        title = list(row.find_all(is_class("dataList-cell")))[1]
        url = title.find("a")
        if not url:
            continue
        url = url.get("href")
        id = utils.extract_thread_matches(url)
        if not id:
            continue
        id = id[0].id
        title = title.text.replace("\n", " ").strip()
        while "  " in title:
            title = title.replace("  ", " ")
        if not title:
            continue
        results.append(SearchResult(title=title, url=url, id=id))
    return results


async def import_bookmarks():
    globals.refresh_total = 2
    if not await assert_login():
        return
    globals.refresh_progress = 1
    diff = 0
    threads = []
    while True:
        globals.refresh_total += 1
        globals.refresh_progress += 1
        async with request("GET", globals.bookmarks_page, params={"difference": diff}) as req:
            raw = await req.read()
        html = bs4.BeautifulSoup(raw, "lxml")
        bookmarks = html.find(is_class("p-body-pageContent")).find(is_class("listPlain"))
        if not bookmarks:
            break
        for title in bookmarks.find_all(is_class("contentRow-title")):
            diff += 1
            threads += utils.extract_thread_matches(title.find("a").get("href"))
    await callbacks.add_games(*threads)


async def import_watched_threads():
    globals.refresh_total = 2
    if not await assert_login():
        return
    globals.refresh_progress = 1
    page = 1
    threads = []
    while True:
        globals.refresh_total += 1
        globals.refresh_progress += 1
        async with request("GET", globals.watched_page, params={"unread": 0, "page": page}) as req:
            raw = await req.read()
        html = bs4.BeautifulSoup(raw, "lxml")
        watched = html.find(is_class("p-body-pageContent")).find(is_class("structItemContainer"))
        if not watched:
            break
        page += 1
        for title in watched.find_all(is_class("structItem-title")):
            threads += utils.extract_thread_matches(title.get("uix-data-href"))
    await callbacks.add_games(*threads)


async def check(game: Game, full=False, standalone=False):
    if standalone:
        globals.refresh_total = 2
        if not await assert_login():
            return
        globals.refresh_progress = 1

    full = full or game.last_full_refresh < time.time() - full_check_interval or game.image.missing
    if not full:
        async with request("HEAD", game.url) as req:
            if (redirect := str(req.real_url)) != game.url:  # FIXME
                if str(game.id) in redirect and redirect.startswith(globals.threads_page):
                    full = True
                else:
                    print(redirect)
    if not full:
        return

    with full_counter:
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
                if sibling.name == "b" or (hasattr(sibling, "get") and "center" in sibling.get("style", "")):
                    break
                stripped = sibling.text.strip()
                if stripped == ":" or stripped == "":
                    continue
                value += sibling.text
            value = value.replace("Spoiler", "").strip()
            while "\n\n\n" in value:
                value = value.replace("\n\n\n", "\n\n")
            return value

        async with request("GET", game.url) as req:
            raw = await req.read()
        html = bs4.BeautifulSoup(raw, "lxml")

        if html.find(is_text("the requested thread could not be found.")):
            buttons = {
                "󰄬 Yes": lambda: callbacks.remove_game(game, bypass_confirm=True),
                "󰜺 No": None
            }
            raise msgbox.Exc("Not found!", f"The F95Zone thread for {game.name} could not be found!\nIt is possible it was deleted.\n\nDo you want to remove {game.name} from your list?", buttons=buttons)

        try:
            head = html.find(is_class("p-body-header"))
            post = html.find(is_class("message-threadStarterPost"))
        finally:
            if head is None or post is None:
                with open(globals.self_path / f"{game.id}_broken.html", "wb") as f:
                    f.write(raw)
                raise msgbox.Exc("Parse error!", f"Failed to parse necessary sections in thread response,\nthe html file has been saved to:\n{globals.self_path}{os.sep}{game.id}_broken.html\n\nPlease submit a bug report on F95Zone or GitHub!")

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

        # Do not reset played checkbox if first refresh on this version
        played = game.played
        if version != old_version and game.last_refresh_version == globals.version:
            played = False
        last_refresh_version = globals.version

        description = get_long_game_attr("overview")

        changelog = get_long_game_attr("changelog", "change-log")

        old_tags = game.tags
        tags = []
        if (taglist := head.find(is_class("js-tagList"))) is not None:
            for child in taglist.children:
                if hasattr(child, "get") and "/tags/" in (tag := child.get("href", "")):
                    tag = tag.replace("/tags/", "").strip("/")
                    tags.append(Tag._members_[tag])

        if globals.settings.update_keep_image and game.image_url:
            image_url = game.image_url
            fetch_image = game.image.missing
        else:
            elem = post.find(is_class("bbWrapper")).find(lambda elem: elem.name == "img" and "data-src" in elem.attrs)
            if elem:
                image_url = elem.get("data-src")
            else:
                image_url = game.image_url
            fetch_image = (image_url != game.image_url) or game.image.missing

        with contextlib.suppress(asyncio.CancelledError):
            game.name = name
            game.version = version
            game.developer = developer
            game.type = type
            game.status = status
            game.url = url
            game.last_updated.update(last_updated)
            game.last_full_refresh = last_full_refresh
            game.last_refresh_version = last_refresh_version
            game.played = played
            game.description = description
            game.changelog = changelog
            game.tags = tags
            game.image_url = image_url
            await db.update_game(game, "name", "version", "developer", "type", "status", "url", "last_updated", "last_full_refresh", "last_refresh_version", "played", "description", "changelog", "tags", "image_url")

            if old_status is not Status.Not_Yet_Checked and game.last_refresh_version == globals.version and (
                name != old_name or
                version != old_version or
                developer != old_developer or
                type != old_type or
                status != old_status or
                tags != old_tags
            ):
                old_game = OldGame(
                    id=game.id,
                    name=old_name,
                    version=old_version,
                    developer=old_developer,
                    type=old_type,
                    status=old_status,
                    tags=old_tags
                )
                updated_games[game.id] = old_game

        if fetch_image and image_url:
            async with image_counter, image_sem:
                async with request("GET", image_url) as req:
                    raw = await req.read()
                ext = image_url[image_url.rfind("."):]
                with contextlib.suppress(asyncio.CancelledError):
                    for img in globals.images_path.glob(f"{game.id}.*"):
                        try:
                            img.unlink()
                        except Exception:
                            pass
                    with open(globals.images_path / f"{game.id}{ext}", "wb") as f:
                        f.write(raw)
                    await asyncio.sleep(0)
                    game.image.loaded = False
                    game.image.resolve()


async def check_notifs(standalone=False):
    if standalone:
        globals.refresh_total = 2
        if not await assert_login():
            return
        globals.refresh_progress = 1

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
