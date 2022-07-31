from PyQt6.QtWidgets import QSystemTrayIcon
import datetime as dt
from PIL import Image
import configparser
import subprocess
import contextlib
import tempfile
import aiohttp
import pathlib
import asyncio
import zipfile
import shutil
import socket
import shlex
import imgui
import time
import json
import bs4
import os
import io
import re

from modules.structs import ContextLimiter, CounterContext, Game, MsgBox, OldGame, Os, SearchResult, Status, Tag, Type
from modules import globals, async_thread, callbacks, db, msgbox, utils

session: aiohttp.ClientSession = None
full_interval = int(dt.timedelta(days=7).total_seconds())
images = ContextLimiter()
fulls = CounterContext()


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
    timeout = kwargs.pop("timeout", None)
    if not timeout:
        timeout = globals.settings.request_timeout
    return session.request(
        method,
        url,
        cookies=globals.cookies,
        timeout=timeout,
        allow_redirects=True,
        max_redirects=None,
        ssl=False,
        **kwargs
    )


async def fetch(method: str, url: str, **kwargs):
    raw = None
    exc = None
    failed = False
    for _ in range(3):
        try:
            async with request(method, url, **kwargs) as req:
                raw = await req.read()
            failed = False
            break
        except aiohttp.ClientError as e:
            failed = True
            exc = e
            continue
    if failed:
        raise exc
    return raw, req


def raise_f95zone_error(raw: bytes):
    if b"<title>Log in | F95zone</title>" in raw:
        raise msgbox.Exc("Login expired", "Your F95Zone login session has expired, press refresh to login again.", MsgBox.warn)
    if b"<p>Automated backups are currently executing. During this time, the site will be unavailable</p>" in raw:
        raise msgbox.Exc("Daily backups", "F95Zone daily backups are currently running,\nplease retry in a few minutes.", MsgBox.warn)
    # if b"<title>DDOS-GUARD</title>" in data:
    #     raise Exception("Captcha needed!")


async def is_logged_in():
    async with request("GET", globals.check_login_page) as req:
        raw = b""
        raw += await req.content.readuntil(b"_xfToken")
        raw += await req.content.readuntil(b">")
        start = raw.rfind(b'value="') + len(b'value="')
        end = raw.find(b'"', start)
        globals.token = str(raw[start:end], encoding="utf-8")
        if not 200 <= req.status < 300:
            raw += await req.content.read()
            try:
                raise_f95zone_error(raw)
            except msgbox.Exc as exc:
                if exc.title == "Login expired" and not globals.gui.minimized:
                    globals.popup_stack.remove(exc.popup)
                    return False
                raise
            with open(globals.self_path / "login_broken.bin", "wb") as f:
                f.write(raw)
            raise msgbox.Exc("Login assertion failure", f"Something went wrong checking the validity of your login session.\n\nF95Zone replied with a status code of {req.status} at this URL:\n{str(req.real_url)}\n\nThe response body has been saved to:\n{globals.self_path}{os.sep}login_broken.bin\nPlease submit a bug report on F95Zone or GitHub including this file.", MsgBox.error)
        return True


async def login():
    try:
        proc = await asyncio.create_subprocess_exec(
            *shlex.split(globals.start_cmd), "asklogin", globals.login_page,
            stdout=subprocess.PIPE
        )
        with utils.daemon(proc):
            data = await proc.communicate()
        with contextlib.suppress(asyncio.CancelledError):
            new_cookies = json.loads(data[0])
            await db.update_cookies(new_cookies)
    except Exception:
        raise msgbox.Exc("Login window failure", f"Something went wrong with the login window subprocess:\n\n{utils.get_traceback()}\n\nThe \"log.txt\" file might contain more information.\nPlease submit a bug report on F95Zone or GitHub including this file.", MsgBox.error)


async def assert_login():
    if not await is_logged_in():
        await login()
        if not await is_logged_in():
            return False
    return True


async def download_webpage(url: str):
    if not await assert_login():
        return
    raw, req = await fetch("GET", url)
    html = bs4.BeautifulSoup(raw, "lxml")
    for elem in html.find_all():
        for key, value in elem.attrs.items():
            if isinstance(value, str) and value.startswith("/"):
                elem.attrs[key] = globals.domain + value
    with tempfile.NamedTemporaryFile("wb", prefix="F95Checker-Temp-", suffix=".html", delete=False) as f:
        f.write(html.prettify(encoding="utf-8"))
    return f.name


async def quick_search(query: str):
    if not await assert_login():
        return
    raw, req = await fetch("POST", globals.qsearch_endpoint, data={"title": query, "_xfToken": globals.token})
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


async def import_url_shortcut(file: str | pathlib.Path):
    parser = configparser.RawConfigParser()
    threads = []
    try:
        parser.read(file)
        threads += utils.extract_thread_matches(parser.get("InternetShortcut", "URL"))
    except Exception:
        pass
    if threads:
        await callbacks.add_games(*threads)
    else:
        utils.push_popup(msgbox.msgbox, "Invalid shortcut", "This shortcut file does not point to a valid thread to import!", MsgBox.warn)


async def import_browser_bookmarks(file: str | pathlib.Path):
    with open(file, "rb") as f:
        raw = f.read()
    html = bs4.BeautifulSoup(raw, "lxml")
    threads = []
    for bookmark in html.find_all(lambda elem: hasattr(elem, "attrs") and "href" in elem.attrs):
        threads += utils.extract_thread_matches(bookmark.get("href"))
    if threads:
        await callbacks.add_games(*threads)
    else:
        utils.push_popup(msgbox.msgbox, "No threads", "This bookmark file contains no valid threads to import!", MsgBox.warn)


async def import_f95_bookmarks():
    globals.refresh_total = 2
    if not await assert_login():
        return
    globals.refresh_progress = 1
    diff = 0
    threads = []
    while True:
        globals.refresh_total += 1
        globals.refresh_progress += 1
        raw, req = await fetch("GET", globals.bookmarks_page, params={"difference": diff})
        raise_f95zone_error(raw)
        html = bs4.BeautifulSoup(raw, "lxml")
        bookmarks = html.find(is_class("p-body-pageContent")).find(is_class("listPlain"))
        if not bookmarks:
            break
        for title in bookmarks.find_all(is_class("contentRow-title")):
            diff += 1
            threads += utils.extract_thread_matches(title.find("a").get("href"))
    if threads:
        await callbacks.add_games(*threads)
    else:
        utils.push_popup(msgbox.msgbox, "No threads", "Your F95Zone bookmarks contains no valid threads to import!", MsgBox.warn)


async def import_f95_watched_threads():
    globals.refresh_total = 2
    if not await assert_login():
        return
    globals.refresh_progress = 1
    page = 1
    threads = []
    while True:
        globals.refresh_total += 1
        globals.refresh_progress += 1
        raw, req = await fetch("GET", globals.watched_page, params={"unread": 0, "page": page})
        raise_f95zone_error(raw)
        html = bs4.BeautifulSoup(raw, "lxml")
        watched = html.find(is_class("p-body-pageContent")).find(is_class("structItemContainer"))
        if not watched:
            break
        page += 1
        for title in watched.find_all(is_class("structItem-title")):
            threads += utils.extract_thread_matches(title.get("uix-data-href"))
    if threads:
        await callbacks.add_games(*threads)
    else:
        utils.push_popup(msgbox.msgbox, "No threads", "Your F95Zone watched threads contains no valid threads to import!", MsgBox.warn)


async def check(game: Game, full=False, login=False):
    if login:
        globals.refresh_total = 2
        if not await assert_login():
            return
        globals.refresh_progress = 1

    last_breaking_changes_version = "9.0"
    checked = game.last_refresh_version.split(".")
    breaking = last_breaking_changes_version.split(".")
    if len(breaking) > len(checked):
        breaking_changes = True  # More version fields, is breaking
    elif len(breaking) < len(checked):
        breaking_changes = False  # Less version fields, not breaking
    else:
        breaking_changes = False
        for ch, br in zip(checked, breaking):
            if ch == br:
                continue  # Ignore this field if same on both versions
            breaking_changes = int(br) > int(ch)
            break  # If field is bigger then its breaking
    full = full or (game.last_full_refresh < time.time() - full_interval) or (game.image.missing and game.image_url != "-") or breaking_changes
    if not full:
        async with request("HEAD", game.url) as req:
            if (redirect := str(req.real_url)) != game.url:
                if str(game.id) in redirect and redirect.startswith(globals.threads_page):
                    full = True
                else:
                    raise msgbox.Exc("Bad HEAD response", f"Something went wrong checking {game.id}, F95Zone responded with an unexpected redirect.\n\nThe quick check HEAD request redirected to:\n{redirect}", MsgBox.error)
    if not full:
        return

    with fulls:

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
            text = elem.text.lstrip(":")
            if "\n" in text:
                text = text[:text.find("\n")]
            return text.strip()
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
            value = value.strip()
            while "\n\n\n" in value:
                value = value.replace("\n\n\n", "\n\n")
            return value

        raw, req = await fetch("GET", game.url, timeout=globals.settings.request_timeout * 2)
        raise_f95zone_error(raw)
        if req.status == 404 or req.status == 403:
            buttons = {
                "󰄬 Yes": lambda: callbacks.remove_game(game, bypass_confirm=True),
                "󰜺 No": None
            }
            if req.status == 404:
                title = "Thread not found"
                msg = f"The F95Zone thread for {game.name} could not be found.\nIt is possible it was privated, moved or deleted."
            elif req.status == 403:
                title = "No permission"
                msg = f"You do not have permission to view {game.name}'s F95Zone thread.\nIt is possible it was privated, moved or deleted."
            raise msgbox.Exc(title, msg + f"\n\nDo you want to remove {game.name} from your list?", MsgBox.error, buttons=buttons)
        html = bs4.BeautifulSoup(raw, "lxml")

        head = html.find(is_class("p-body-header"))
        post = html.find(is_class("message-threadStarterPost"))
        if head is None or post is None:
            with open(globals.self_path / f"{game.id}_broken.html", "wb") as f:
                f.write(raw)
            raise msgbox.Exc("Thread parsing error", f"Failed to parse necessary sections in thread response,\nthe html file has been saved to:\n{globals.self_path}{os.sep}{game.id}_broken.html\n\nPlease submit a bug report on F95Zone or GitHub including this file.", MsgBox.error)
        for spoiler in post.find_all(is_class("bbCodeSpoiler-button")):
            try:
                next(spoiler.span.span.children).replace_with(html.new_string(""))
            except Exception:
                pass

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
            type = Type.Media
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
        elif game_has_prefixes("Others"):
            type = Type.Others
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
            type = Type.Unreal_Eng
        elif game_has_prefixes("WebGL"):
            type = Type.WebGL
        elif game_has_prefixes("Wolf RPG"):
            type = Type.Wolf_RPG
        else:
            type = Type.Misc

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
        last_updated = int(dt.datetime.fromordinal(dt.datetime.fromtimestamp(last_updated).date().toordinal()).timestamp())

        last_full_refresh = int(time.time())

        # Do not reset played and installed checkboxes if refreshing with braking changes
        played = game.played
        installed = game.installed
        if breaking_changes:
            if old_version == installed:
                installed = version  # Is breaking and was previously installed, mark again as installed
        else:
            if version != old_version:
                played = False  # Not breaking and version changed, remove played checkbox

        description = get_long_game_attr("overview", "story")

        changelog = get_long_game_attr("changelog", "change-log")

        old_tags = game.tags
        tags = []
        if (taglist := head.find(is_class("js-tagList"))) is not None:
            for child in taglist.children:
                if hasattr(child, "get") and "/tags/" in (tag := child.get("href", "")):
                    tag = tag.replace("/tags/", "").strip("/")
                    tags.append(Tag._members_[tag])

        elem = post.find(is_class("bbWrapper")).find(lambda elem: elem.name == "img" and "data-src" in elem.attrs)
        if elem:
            image_url = elem.get("data-src")
        else:
            image_url = "-"
        fetch_image = game.image.missing
        if not globals.settings.update_keep_image and not breaking_changes:
            fetch_image = fetch_image or (image_url != game.image_url)

        if fetch_image and image_url and image_url != "-":
            async with images:
                try:
                    raw, req = await fetch("GET", image_url, timeout=globals.settings.request_timeout * 4)
                except aiohttp.ClientConnectorError as exc:
                    if not isinstance(exc.os_error, socket.gaierror):
                        raise  # Not a dead link
                    if re.search(f"^https?://[^/]*\.?{globals.host}/", image_url):
                        raise  # Not a foreign host, raise normal connection error message
                    f95zone_ok = True
                    foreign_ok = True
                    try:
                        await async_thread.loop.run_in_executor(None, socket.gethostbyname, globals.host)
                    except Exception:
                        f95zone_ok = False
                    try:
                        await async_thread.loop.run_in_executor(None, socket.gethostbyname, re.search("^https?://([^/]+)", image_url).group(1))
                    except Exception:
                        foreign_ok = False
                    if f95zone_ok and not foreign_ok:
                        image_url = "-"
                    else:
                        raise  # Foreign host might not actually be dead
                try:
                    ext = "." + str(Image.open(io.BytesIO(raw)).format or "img").lower()
                except Exception:
                    ext = ".img"
                with contextlib.suppress(asyncio.CancelledError):
                    for img in globals.images_path.glob(f"{game.id}.*"):
                        try:
                            img.unlink()
                        except Exception:
                            pass
                    if image_url != "-":
                        with open(globals.images_path / f"{game.id}{ext}", "wb") as f:
                            f.write(raw)
                    game.image.loaded = False
                    game.image.resolve()

        last_refresh_version = globals.version

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
            game.installed = installed
            game.description = description
            game.changelog = changelog
            game.tags = tags
            game.image_url = image_url
            await db.update_game(game, "name", "version", "developer", "type", "status", "url", "last_updated", "last_full_refresh", "last_refresh_version", "played", "description", "changelog", "tags", "image_url")

            if old_status is not Status.Not_Yet_Checked and not breaking_changes and (
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
                globals.updated_games[game.id] = old_game


async def check_notifs(login=False):
    if login:
        globals.refresh_total = 2
        if not await assert_login():
            return
        globals.refresh_progress = 1

    try:
        raw, req = await fetch("GET", globals.notif_endpoint, params={"_xfToken": globals.token, "_xfResponseType": "json"})
        res = json.loads(raw)
        alerts = int(res["visitor"]["alerts_unread"])
        inbox  = int(res["visitor"]["conversations_unread"])
    except Exception:
        with open(globals.self_path / "notifs_broken.bin", "wb") as f:
            f.write(raw)
        raise msgbox.Exc("Notifs check error", f"Something went wrong checking your unread notifications:\n\n{utils.get_traceback()}\n\nThe response body has been saved to:\n{globals.self_path}{os.sep}notifs_broken.bin\nPlease submit a bug report on F95Zone or GitHub including this file.", MsgBox.error)
    if alerts != 0 and inbox != 0:
        msg = f"You have {alerts + inbox} unread notifications ({alerts} alert{'s' if alerts > 1 else ''} and {inbox} conversation{'s' if inbox > 1 else ''})."
    elif alerts != 0 and inbox == 0:
        msg = f"You have {alerts} unread alert{'s' if alerts > 1 else ''}."
    elif alerts == 0 and inbox != 0:
        msg = f"You have {inbox} unread conversation{'s' if inbox > 1 else ''}."
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
    for popup in globals.popup_stack:
        if hasattr(popup, "func") and popup.func is msgbox.msgbox and popup.args[0].startswith("Notifications##"):
            globals.popup_stack.remove(popup)
    utils.push_popup(msgbox.msgbox, "Notifications", msg + f"\n\nDo you want to view {'them' if (alerts + inbox) > 1 else 'it'}?", MsgBox.info, buttons)
    if globals.gui.minimized or not globals.gui.focused:
        globals.gui.tray.push_msg(title="Notifications", msg=msg + ".\nClick here to view them.", icon=QSystemTrayIcon.MessageIcon.Information)


async def check_updates():
    try:
        raw, req = await fetch("GET", globals.update_endpoint)
        res = json.loads(raw)
        latest = res["tag_name"].split(".")
        current = globals.version.split(".")
        if res["prerelease"]:
            update_available = False  # Release is not ready yet
        elif (globals.self_path / ".git").is_dir():
            update_available = False  # Running from git repo, skip update
        elif len(latest) > len(current):
            update_available = True  # More version fields, is an update
        elif len(latest) < len(current):
            update_available = False  # Less version fields, not an update
        else:
            update_available = not globals.is_release  # Allow updating from beta to full release
            for cur, lat in zip(current, latest):
                if cur == lat:
                    continue  # Ignore this field if same on both versions
                update_available = int(lat) > int(cur)
                break  # If field is bigger then its an update
        asset_url = None
        asset_name = None
        asset_size = None
        for asset in res["assets"]:
            if (globals.frozen and globals.os.name.lower() in asset["name"].lower()) or \
            (not globals.frozen and "source" in asset["name"].lower()):
                asset_url = asset["browser_download_url"]
                asset_name = asset["name"]
                asset_size = asset["size"]
                break
        changelog = res["body"].strip("\n")
        if (match := "## 🚀 Changelog") in changelog:
            changelog = changelog[changelog.find(match) + len(match):].strip()
        globals.last_update_check = time.time()
        if not update_available or not asset_url or not asset_name or not asset_size:
            return
    except Exception:
        with open(globals.self_path / "update_broken.bin", "wb") as f:
            f.write(raw)
        raise msgbox.Exc("Update check error", f"Something went wrong checking for F95Checker updates:\n\n{utils.get_traceback()}\n\nThe response body has been saved to:\n{globals.self_path}{os.sep}update_broken.bin\nPlease submit a bug report on F95Zone or GitHub including this file.", MsgBox.error)
    async def update_callback():
        progress = 0.0
        total = float(asset_size)
        cancel = [False]
        status = f"Downloading {asset_name}..."
        fmt = "{ratio:.0%}"
        def popup_content():
            imgui.text(status)
            ratio = progress / total
            width = imgui.get_content_region_available_width()
            height = imgui.get_frame_height()
            imgui.progress_bar(ratio, (width, height))
            draw_list = imgui.get_window_draw_list()
            col = imgui.get_color_u32_rgba(1, 1, 1, 1)
            text = fmt.format(ratio=ratio, progress=progress)
            text_size = imgui.calc_text_size(text)
            screen_pos = imgui.get_cursor_screen_pos()
            text_x = screen_pos.x + (width - text_size.x) / 2
            text_y = screen_pos.y - (height + text_size.y) / 2 - imgui.style.item_spacing.y
            draw_list.add_text(text_x, text_y, col, text)
        def cancel_callback():
            cancel[0] = True
        buttons = {
            "󰜺 Cancel": cancel_callback
        }
        utils.push_popup(utils.popup, "Updating F95checker", popup_content, buttons=buttons, closable=False, outside=False)
        asset_data = io.BytesIO()
        async with request("GET", asset_url, timeout=3600) as req:
            async for chunk in req.content.iter_any():
                if cancel[0]:
                    return
                if chunk:
                    progress += asset_data.write(chunk)
                else:
                    break
        progress = 0.0
        total = 1.0
        status = f"Extracting {asset_name}..."
        asset_path = pathlib.Path(tempfile.TemporaryDirectory(prefix=asset_name[:asset_name.rfind(".")] + "-").name)
        with zipfile.ZipFile(asset_data) as z:
            total = float(len(z.filelist))
            for file in z.filelist:
                if cancel[0]:
                    shutil.rmtree(asset_path, ignore_errors=True)
                    return
                z.extract(file.filename, asset_path)
                progress += 1
        progress = 5.0
        total = 5.0
        status = "Installing update in..."
        fmt = "{progress:.0f}s"
        for _ in range(500):
            if cancel[0]:
                shutil.rmtree(asset_path, ignore_errors=True)
                return
            await asyncio.sleep(0.01)
            progress -= 0.01
        if globals.os is Os.Windows:
            script = "\n".join([
                shlex.join(["Wait-Process", "-Id", str(os.getpid())]),
                shlex.join(["Remove-Item", "-Recurse", str(globals.self_path)]),
                shlex.join(["Move-Item", str(asset_path), str(globals.self_path)]),
                globals.start_cmd
            ])
            shell = [shutil.which("powershell")]
        else:
            if globals.frozen and globals.os is Os.MacOS:
                src = next(asset_path.glob("*.app"))  # F95Checker-123/F95Checker.app
                dst = globals.self_path.parent.parent  # F95Checker.app/Contents/MacOS
            else:
                src = asset_path
                dst = globals.self_path
            shutil.rmtree(dst)
            shutil.move(src, dst)
            if globals.frozen and globals.os is Os.MacOS:
                shutil.rmtree(asset_path, ignore_errors=True)
            script = "\n".join([
                shlex.join(["lsof", "-p", str(os.getpid()), "+r", "1"] if globals.os is Os.MacOS else ["tail", "--pid", str(os.getpid()), "-f", os.devnull]),
                globals.start_cmd
            ])
            shell = [shutil.which("bash") or shutil.which("zsh") or shutil.which("sh"), "-c"]
        await asyncio.create_subprocess_exec(*shell, script)
        globals.gui.close()
    buttons = {
        "󰄬 Yes": lambda: async_thread.run(update_callback()),
        "󰜺 No": None
    }
    for popup in globals.popup_stack:
        if hasattr(popup, "func") and popup.func is msgbox.msgbox and popup.args[0].startswith("F95checker update##"):
            globals.popup_stack.remove(popup)
    if globals.frozen and globals.os is Os.MacOS:
        path = globals.self_path.parent.parent
    else:
        path = globals.self_path
    utils.push_popup(msgbox.msgbox, "F95checker update", f"F95Checker has been updated to version {'.'.join(latest)} (you are on v{globals.version}{'' if globals.is_release else ' beta'}).\nTHIS WILL DELETE EVERYTHING INSIDE {path}, MAKE SURE THAT IS OK!\n\nDo you want to update?", MsgBox.info, buttons=buttons, more=changelog, bottom=True)
    if globals.gui.minimized or not globals.gui.focused:
        globals.gui.tray.push_msg(title="F95checker update", msg="F95Checker has received an update.\nClick here to view it.", icon=QSystemTrayIcon.MessageIcon.Information)


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
    images.avail = int(max(1, globals.settings.refresh_workers / 10))

    game_refresh_task = asyncio.gather(*[worker() for _ in range(globals.settings.refresh_workers)])
    def reset_counts(_):
        images.count = 0
        fulls.count = 0
    game_refresh_task.add_done_callback(reset_counts)
    await game_refresh_task

    await check_notifs()
