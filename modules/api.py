import asyncio
import configparser
import contextlib
import http.cookies
import io
import json
import os
import pathlib
import re
import shlex
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import zipfile

from PyQt6.QtWidgets import QSystemTrayIcon
import aiofiles
import aiohttp
import aiohttp_socks
import aiolimiter
import imgui
import python_socks

from common.structs import (
    AsyncProcessPipe,
    CounterContext,
    Game,
    MsgBox,
    OldGame,
    Os,
    ProxyType,
    SearchResult,
    Status,
    Tag,
    TimelineEventType,
    Type,
)
from common import parser
from external import (
    async_thread,
    error,
)
from modules import (
    callbacks,
    db,
    globals,
    icons,
    msgbox,
    utils,
    webview,
)

f95_domain = "f95zone.to"
f95_host = "https://" + f95_domain
f95_sam_backend_root    = f95_host + "/sam/"
f95_check_login_page    = f95_host + "/account/"
f95_login_page          = f95_host + "/login/"
f95_notif_endpoint      = f95_host + "/conversations/popup?_xfToken={xf_token}&_xfResponseType=json"
f95_alerts_page         = f95_host + "/account/alerts/"
f95_inbox_page          = f95_host + "/conversations/"
f95_threads_page        = f95_host + "/threads/"
f95_bookmarks_page      = f95_host + "/account/bookmarks?difference=0&page={page}"
f95_watched_page        = f95_host + "/watched/threads?unread=0&page={page}"
f95_qsearch_endpoint    = f95_host + "/quicksearch"

api_domain = "api.f95checker.dev"
api_host = "https://" + api_domain
api_fast_check_url = api_host + "/fast?ids={ids}"
api_full_check_url = api_host + "/full/{id}?ts={ts}"
api_fast_check_max_ids = 10

app_update_endpoint     = "https://api.github.com/repos/Willy-JL/F95Checker/releases/latest"

updating = False
session: aiohttp.ClientSession = None
ssl_context: ssl.SSLContext = None
webpage_prefix = "F95Checker-Temp-"
xenforo_ratelimit = aiolimiter.AsyncLimiter(max_rate=1, time_period=2)
fast_checks_sem: asyncio.Semaphore = None
full_checks_sem: asyncio.Semaphore = None
fast_checks_counter = 0
full_checks_counter = CounterContext()
images_counter = CounterContext()
xf_token = ""


def make_session():
    global session
    old_session = session

    # Setup new HTTP session and proxy
    if globals.settings.proxy_type is ProxyType.Disabled:
        connector = None
    else:
        proxy_type = python_socks.ProxyType.HTTP
        match globals.settings.proxy_type:
            case ProxyType.SOCKS4: proxy_type = python_socks.ProxyType.SOCKS4
            case ProxyType.SOCKS5: proxy_type = python_socks.ProxyType.SOCKS5
            case ProxyType.HTTP: proxy_type = python_socks.ProxyType.HTTP
        connector = aiohttp_socks.ProxyConnector(
            proxy_type=proxy_type,
            host=globals.settings.proxy_host,
            port=globals.settings.proxy_port,
            username=globals.settings.proxy_username,
            password=globals.settings.proxy_password,
            loop=async_thread.loop,
        )
    session = aiohttp.ClientSession(
        loop=async_thread.loop,
        connector=connector,
        cookie_jar=aiohttp.DummyCookieJar(loop=async_thread.loop),
        headers={
            "User-Agent": (
                f"F95Checker/{globals.version} "
                f"Python/{sys.version.split(' ')[0]} "
                f"aiohttp/{aiohttp.__version__}"
            ),
        },
    )

    if old_session:
        async_thread.wait(old_session.close())


@contextlib.contextmanager
def setup():
    global ssl_context

    # Setup SSL context
    if globals.os is Os.Windows:
        # Python SSL module seems to import Windows CA certs fine by itself
        ca_paths = None
    elif globals.os is Os.Linux:
        ca_paths = (
            "/etc/ssl/certs/ca-certificates.crt",  # Ubuntu / Common
            "/etc/pki/tls/certs/ca-bundle.crt",  # Fedora
            "/etc/ssl/cert.pem",  # Alias
        )
    elif globals.os is Os.MacOS:
        ca_paths = (
            "/opt/homebrew/etc/ca-certificates/cert.pem",  # Homebrew
            "/usr/local/etc/openssl/cert.pem",  # Homebrew?
            "/opt/local/etc/openssl/cert.pem",  # MacPorts
            "/opt/local/share/curl/curl-ca-bundle.crt",  # MacPorts
            "/etc/ssl/cert.pem",  # Standard, maybe outdated?
        )
    if ca_paths:
        # Prefer system-provided CA certs
        for ca_path in ca_paths:
            if pathlib.Path(ca_path).is_file():
                break
        else:  # Did not break, so no system CA exists, fallback to certifi
            import certifi
            ca_path = certifi.where()
        ssl_context = ssl.create_default_context(cafile=ca_path)
    else:
        ssl_context = ssl.create_default_context()

    make_session()

    try:
        yield
    finally:

        async_thread.wait(session.close())
        cleanup_webpages()


def is_f95zone_url(url: str):
    return bool(re.search(r"^https?://[^/]*\.?" + re.escape(f95_domain) + r"/", url))


def cookiedict(cookies: http.cookies.SimpleCookie):
    return {cookie.key: cookie.value for cookie in cookies.values()}


@contextlib.asynccontextmanager
async def request(method: str, url: str, read=True, no_cookies=False, **kwargs):
    timeout = kwargs.pop("timeout", None)
    if not timeout:
        timeout = globals.settings.request_timeout
    retries = globals.settings.max_retries + 1
    req_opts = dict(
        timeout=timeout,
        allow_redirects=True,
        max_redirects=None,
        ssl=ssl_context
    )
    if no_cookies:
        cookies = {}
    else:
        cookies = globals.cookies
    ddos_guard_cookies = {}
    ddos_guard_first_challenge = False
    is_xenforo_request = url.startswith(f95_host) and not url.startswith(f95_sam_backend_root)
    xenforo_ratelimit_retries = 10
    while retries and xenforo_ratelimit_retries:
        try:
            # Only ratelimit when connecting to F95zone
            maybe_ratelimit = xenforo_ratelimit if is_xenforo_request else contextlib.nullcontext()
            async with maybe_ratelimit, session.request(
                method,
                url,
                cookies=cookies | ddos_guard_cookies,
                **req_opts,
                **kwargs
            ) as req:
                if is_xenforo_request and req.status == 429 and xenforo_ratelimit_retries > 1:
                    xenforo_ratelimit_retries -= 1
                    continue
                if not read:
                    yield b"", req
                    break
                res = await req.read()
                if req.headers.get("server") in ("ddos-guard", "", None) and re.search(rb"<title>DDOS-GUARD</title>", res, flags=re.IGNORECASE):
                    # Attempt DDoS-Guard bypass (credits to https://git.gay/a/ddos-guard-bypass)
                    ddos_guard_cookies.update(cookiedict(req.cookies))
                    if not ddos_guard_first_challenge:
                        # First challenge: repeat original request with new cookies
                        ddos_guard_first_challenge = True
                        continue
                    # First challenge failed, attempt manual bypass and retry original request
                    referer = f"{req.url.scheme}://{req.url.host}"
                    headers = {
                        "Accept": "*/*",
                        "Accept-Language": "en-US,en;q=0.5",
                        "Accept-Encoding": "gzip, deflate",
                        "Referer": referer,
                        "Sec-Fetch-Mode": "no-cors"
                    }
                    for script in re.finditer(rb'loadScript\(\s*"(.+?)"', await req.read()):
                        script = str(script.group(1), encoding="utf-8")
                        async with session.request(
                            "GET",
                            f"{referer if script.startswith('/') else ''}{script}",
                            cookies=cookies | ddos_guard_cookies,
                            headers=headers | {
                                "Sec-Fetch-Dest": "script",
                                "Sec-Fetch-Site": "same-site" if "ddos-guard.net/" in script else "cross-site"
                            },
                            **req_opts
                        ) as script_req:
                            ddos_guard_cookies.update(cookiedict(script_req.cookies))
                            for image in re.finditer(rb"\.src\s*=\s*'(.+?)'", await script_req.read()):
                                image = str(image.group(1), encoding="utf-8")
                                async with session.request(
                                    "GET",
                                    f"{referer if image.startswith('/') else ''}{image}",
                                    cookies=cookies | ddos_guard_cookies,
                                    headers=headers | {
                                        "Sec-Fetch-Dest": "image",
                                        "Sec-Fetch-Site": "same-origin"
                                    },
                                    **req_opts
                                ) as image_req:
                                    ddos_guard_cookies.update(cookiedict(image_req.cookies))
                    async with session.request(
                        "POST",
                        f"{referer}/.well-known/ddos-guard/mark/",
                        json=ddos_guard_bypass_fake_mark,
                        cookies=cookies | ddos_guard_cookies,
                        headers=headers | {
                            "Content-Type": "text/plain;charset=UTF-8",
                            "DNT": "1",
                            "Sec-Fetch-Dest": "empty",
                            "Sec-Fetch-Mode": "cors",
                            "Sec-Fetch-Site": "same-origin"
                        },
                        **req_opts
                    ) as mark_req:
                        ddos_guard_cookies.update(cookiedict(mark_req.cookies))
                    continue
                yield res, req
            break
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            if globals.settings.ignore_semaphore_timeouts and isinstance(exc, OSError) and exc.errno == 121:
                continue
            retries -= 1
            if not retries:
                raise


async def fetch(method: str, url: str, **kwargs):
    async with request(method, url, **kwargs) as (res, _):
        return res


def raise_f95zone_error(res: bytes | dict, return_login=False):
    if isinstance(res, bytes):
        if b"<title>Log in | F95zone</title>" in res:
            if return_login:
                return False
            raise msgbox.Exc(
                "Login expired",
                "Your F95Zone login session has expired,\n"
                "press refresh to login again.",
                MsgBox.warn
            )
        if any(msg in res for msg in (
            b"<title>429 Too Many Requests</title>",
            b"<h1>429 Too Many Requests</h1>",
            b"<title>Error 429</title>",
        )):
            raise msgbox.Exc(
                "Rate limit",
                "F95Zone servers are ratelimiting you,\n"
                "please retry in a few minutes.",
                MsgBox.warn
            )
        if b"<title>502 Bad Gateway</title>" in res:
            raise msgbox.Exc(
                "Server downtime",
                "F95Zone servers are currently unreachable,\n"
                "please retry in a few minutes.",
                MsgBox.warn
            )
        if b"<!-- Too many connections -->" in res:
            raise msgbox.Exc(
                "Database overload",
                "F95Zone databases are currently overloaded,\n"
                "please retry in a few minutes.",
                MsgBox.warn
            )
        if b"<p>Automated backups are currently executing. During this time, the site will be unavailable</p>" in res:
            raise msgbox.Exc(
                "Daily backups",
                "F95Zone daily backups are currently running,\n"
                "please retry in a few minutes.",
                MsgBox.warn
            )
        if b"<title>DDOS-GUARD</title>" in res:
            raise msgbox.Exc(
                "DDoS-Guard bypass failure",
                "F95Zone requested a DDoS-Guard browser challenge and F95Checker\n"
                "was unable to bypass it. Try waiting a few minutes, opening F95Zone\n"
                "in browser, rebooting your router, or connecting through a VPN.",
                MsgBox.error
            )
        return True
    elif isinstance(res, dict):
        if res.get("status") == "error":
            more = json.dumps(res, indent=4)
            if msg := res.get("msg"):
                raise msgbox.Exc(
                    "API error",
                    "The F95Zone API returned an 'error' status with the following message:\n"
                    f"{msg}",
                    MsgBox.error,
                    more=more
                )
            if errors := res.get("errors", []):
                if "Cookies are required to use this site. You must accept them to continue using the site." in errors:
                    if return_login:
                        return False
                    raise msgbox.Exc(
                        "Login expired",
                        "Your F95Zone login session has expired,\n"
                        "press refresh to login again.",
                        MsgBox.warn
                    )
                raise msgbox.Exc(
                    "API error",
                    "The F95Zone API returned an 'error' status with the following messages:\n"
                    " - " + "\n - ".join(errors),
                    MsgBox.error,
                    more=more
                )
            raise msgbox.Exc(
                "API error",
                "The F95Zone API returned an 'error' status.",
                MsgBox.error,
                more=more
            )
        return True


def raise_api_error(res: bytes | dict):
    if isinstance(res, bytes):
        if any(msg in res for msg in (
            b"<title>api.f95checker.dev | 502: Bad gateway</title>",
            b"<title>api.f95checker.dev | 521: Web server is down</title>",
        )):
            raise msgbox.Exc(
                "Server downtime",
                "F95Checker Cache API is currently unreachable,\n"
                "please retry in a few minutes.",
                MsgBox.warn
            )
        return True
    elif isinstance(res, dict):
        if index_error := res.get("INDEX_ERROR"):
            # TODO: make graceful, collect to a list and show at refresh end
            more = json.dumps(res, indent=4)
            raise msgbox.Exc(
                "API error",
                f"The F95Checker Cache API returned error '{index_error}'.",
                MsgBox.error,
                more=more
            )
        return True


async def is_logged_in():
    global xf_token
    async with request("GET", f95_check_login_page) as (res, req):
        if not 200 <= req.status < 300:
            res += await req.content.read()
            if not raise_f95zone_error(res, return_login=True):
                return False
            # Check login page was not in 200 range, but error is not a login issue
            async with aiofiles.open(globals.self_path / "login_broken.bin", "wb") as f:
                await f.write(res)
            raise msgbox.Exc(
                "Login assertion failure",
                "Something went wrong checking the validity of your login session.\n"
                "\n"
                f"F95Zone replied with a status code of {req.status} at this URL:\n"
                f"{str(req.real_url)}\n"
                "\n"
                "The response body has been saved to:\n"
                f"{globals.self_path / 'login_broken.bin'}\n"
                "Please submit a bug report on F95Zone or GitHub including this file.",
                MsgBox.error
            )
        xf_token = str(re.search(rb'<\s*input.*?name\s*=\s*"_xfToken"\s*value\s*=\s*"(.+)"', res).group(1), encoding="utf-8")
        return True


async def login():
    try:
        new_cookies = {}
        with (pipe := AsyncProcessPipe())(await asyncio.create_subprocess_exec(
            *shlex.split(globals.start_cmd), "webview", "cookies", json.dumps((f95_login_page,)), json.dumps(webview.kwargs() | dict(
                title="F95Checker: Login to F95Zone",
                size=(size := (500, 720)),
                pos=(
                    int(globals.gui.screen_pos[0] + (imgui.io.display_size.x / 2) - size[0] / 2),
                    int(globals.gui.screen_pos[1] + (imgui.io.display_size.y / 2) - size[1] / 2)
                )
            )),
            stdout=subprocess.PIPE
        )):
            while True:
                (key, value) = await pipe.get_async()
                new_cookies[key] = value
                if "xf_user" in new_cookies:
                    break
        await asyncio.shield(db.update_cookies(new_cookies))
    except Exception:
        raise msgbox.Exc(
            "Login window failure",
            "Something went wrong with the login window subprocess:\n"
            f"{error.text()}\n"
            "\n"
            "The console output contain more information.\n"
            "Please submit a bug report on F95Zone or GitHub including this file.",
            MsgBox.error,
            more=error.traceback()
        )


async def assert_login():
    if not await is_logged_in():
        await login()
        if not await is_logged_in():
            return False
    return True


async def download_webpage(url: str):
    if not await assert_login():
        return
    res = await fetch("GET", url)
    html = parser.html(res)
    for elem in html.find_all():
        for key, value in elem.attrs.items():
            if isinstance(value, str) and value.startswith("/"):
                elem.attrs[key] = f95_host + value
    with tempfile.NamedTemporaryFile("wb", prefix=webpage_prefix, suffix=".html", delete=False) as f:
        f.write(html.prettify(encoding="utf-8"))
    return pathlib.Path(f.name).as_uri()


def cleanup_webpages():
    for item in pathlib.Path(tempfile.gettempdir()).glob(f"{webpage_prefix}*"):
        try:
            item.unlink()
        except Exception:
            pass


async def quick_search(query: str):
    if not await assert_login():
        return
    res = await fetch("POST", f95_qsearch_endpoint, data={"title": query, "_xfToken": xf_token})
    html = parser.html(res)
    results = []
    for row in html.find(parser.is_class("quicksearch-wrapper-wide")).find_all(parser.is_class("dataList-row")):
        title = list(row.find_all(parser.is_class("dataList-cell")))[1]
        url = title.find("a")
        if not url:
            continue
        url = url.get("href")
        id = utils.extract_thread_matches(url)
        if not id:
            continue
        id = id[0].id
        title = re.sub(r"\s+", r" ", title.text).strip()
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
        utils.push_popup(
            msgbox.msgbox, "Invalid shortcut",
            "This shortcut file does not point to a valid thread to import!",
            MsgBox.warn
        )


async def import_browser_bookmarks(file: str | pathlib.Path):
    async with aiofiles.open(file, "rb") as f:
        raw = await f.read()
    html = parser.html(raw)
    threads = []
    for bookmark in html.find_all(lambda elem: "href" in getattr(elem, "attrs", "")):
        threads += utils.extract_thread_matches(bookmark.get("href"))
    if threads:
        await callbacks.add_games(*threads)
    else:
        utils.push_popup(
            msgbox.msgbox, "No threads",
            "This bookmark file contains no valid threads to import!",
            MsgBox.warn
        )


async def import_f95_bookmarks():
    globals.refresh_total = 1
    if not await assert_login():
        return
    globals.refresh_progress = 1
    page = 0
    threads = []
    while True:
        globals.refresh_total += 1
        res = await fetch("GET", f95_bookmarks_page.format(page=page))
        raise_f95zone_error(res)
        html = parser.html(res)
        bookmarks = html.find(parser.is_class("p-body-pageContent")).find(parser.is_class("listPlain"))
        globals.refresh_progress += 1
        if not bookmarks:
            break
        page += 1
        for title in bookmarks.find_all(parser.is_class("contentRow-title")):
            threads += utils.extract_thread_matches(title.find("a").get("href"))
    if threads:
        await callbacks.add_games(*threads)
    else:
        utils.push_popup(
            msgbox.msgbox, "No threads",
            "Your F95Zone bookmarks contains no valid threads to import!",
            MsgBox.warn
        )


async def import_f95_watched_threads():
    globals.refresh_total = 1
    if not await assert_login():
        return
    globals.refresh_progress = 1
    page = 1
    threads = []
    while True:
        globals.refresh_total += 1
        res = await fetch("GET", f95_watched_page.format(page=page))
        raise_f95zone_error(res)
        html = parser.html(res)
        watched = html.find(parser.is_class("p-body-pageContent")).find(parser.is_class("structItemContainer"))
        globals.refresh_progress += 1
        if not watched:
            break
        page += 1
        for title in watched.find_all(parser.is_class("structItem-title")):
            threads += utils.extract_thread_matches(title.get("uix-data-href"))
    if threads:
        await callbacks.add_games(*threads)
    else:
        utils.push_popup(
            msgbox.msgbox, "No threads",
            "Your F95Zone watched threads contains no valid threads to import!",
            MsgBox.warn
        )


def last_check_before(before_version: str, checked_version: str):
    checked = (checked_version or "0").split(".")
    before = before_version.split(".")
    if len(before) > len(checked):
        checked += ["0" for _ in range(len(before) - len(checked))]
    elif len(checked) > len(before):
        before += ["0" for _ in range(len(checked) - len(before))]
    is_before = False
    for ch, bf in zip(checked, before):
        if ch == bf:
            continue  # Ignore this field if same on both versions
        is_before = int(ch) < int(bf)
        break  # If field is smaller then its before
    return is_before


async def fast_check(games: list[Game], full=False):
    games = list(filter(lambda game: not game.custom, games))

    global fast_checks_counter
    fast_checks_counter += len(games)
    try:
        async with fast_checks_sem:
            res = None
            try:
                res = await fetch("GET", api_fast_check_url.format(ids=",".join(str(game.id) for game in games)), timeout=120, no_cookies=True)
                raise_api_error(res)
                last_changes = json.loads(res)
                raise_api_error(last_changes)
            except Exception as exc:
                if isinstance(exc, msgbox.Exc):
                    raise exc
                if res:
                    async with aiofiles.open(globals.self_path / "check_broken.bin", "wb") as f:
                        await f.write(json.dumps(res).encode() if isinstance(res, (dict, list)) else res)
                raise msgbox.Exc(
                    "Fast check error",
                    "Something went wrong checking some of your games:\n"
                    f"{error.text()}\n" + (
                        "\n"
                        "The response body has been saved to:\n"
                        f"{globals.self_path / 'check_broken.bin'}\n"
                        "Please submit a bug report on F95Zone or GitHub including this file."
                        if res else ""
                    ),
                    MsgBox.error,
                    more=error.traceback()
                )
    finally:
        fast_checks_counter -= len(games)

    full_queue: list[tuple[Game, int]] = []
    for game in games:
        last_changed = last_changes.get(str(game.id), 0)
        assert last_changed > 0, "Invalid last_changed from fast check API"

        this_full = full or (
            game.status is Status.Unchecked or
            last_changed > game.last_full_check or
            (game.image.missing and game.image_url.startswith("http")) or
            last_check_before("10.1.1", game.last_check_version)  # Switch away from HEAD requests, new version parsing
        )
        if not this_full:
            globals.refresh_progress += 1
            continue

        full_queue.append((game, last_changed))

    tasks: list[asyncio.Task] = []
    try:
        tasks = [asyncio.create_task(full_check(game, ts)) for game, ts in full_queue]
        await asyncio.gather(*tasks)
    except Exception:
        for task in tasks:
            task.cancel()
        raise


async def full_check(game: Game, last_changed: int):
    async with full_checks_counter, full_checks_sem:

        async with request("GET", api_full_check_url.format(id=game.id, ts=last_changed), timeout=globals.settings.request_timeout * 2) as (res, req):
            raise_api_error(res)
            if req.status in (403, 404):
                if not game.archived:
                    buttons = {
                        f"{icons.cancel} Do nothing": None,
                        f"{icons.trash_can_outline} Remove": lambda: callbacks.remove_game(game, bypass_confirm=True),
                        f"{icons.puzzle_outline} Convert": lambda: callbacks.convert_f95zone_to_custom(game)
                    }
                    utils.push_popup(
                        msgbox.msgbox, "Thread not found",
                        "The F95Zone thread for this game could not be found:\n"
                        f"{game.name}\n"
                        "It might have been privated, moved or deleted, maybe for breaking forum rules.\n"
                        "\n"
                        "You can remove this game from your library, or convert it to a custom game.\n"
                        "Custom games are untied from F95Zone and are not checked for updates, so\n"
                        "you won't get this error anymore. You can later convert it back to an F95Zone\n"
                        "game from its info popup. You can also find more details there.",
                        MsgBox.error,
                        buttons=buttons
                    )
                globals.refresh_progress += 1
                return
            thread = json.loads(res)
            raise_api_error(thread)
            url = f95_threads_page + str(game.id)

        # Redis only allows string values, so API only gives str for simplicity
        thread["type"] = Type(int(thread["type"]))
        thread["status"] = Status(int(thread["status"]))
        thread["last_updated"] = int(thread["last_updated"])
        thread["score"] = float(thread["score"])
        thread["votes"] = int(thread["votes"])
        thread["tags"] = tuple(Tag(tag) for tag in json.loads(thread["tags"]))
        thread["unknown_tags"] = json.loads(thread["unknown_tags"])
        thread["downloads"] = json.loads(thread["downloads"])
        for label, links in thread["downloads"]:
            for link_i, link_pair in enumerate(links):
                links[link_i] = tuple(link_pair)
        thread["downloads"] = tuple(thread["downloads"])

        old_name = game.name
        old_version = game.version
        old_status = game.status

        version = thread["version"]
        if not version:
            version = "N/A"

        if old_status is not Status.Unchecked:
            if game.developer != thread["developer"]:
                game.add_timeline_event(TimelineEventType.ChangedDeveloper, game.developer, thread["developer"])

            if game.type != thread["type"]:
                game.add_timeline_event(TimelineEventType.ChangedType, game.type.name, thread["type"].name)

            if game.tags != thread["tags"]:
                if difference := [tag.text for tag in thread["tags"] if tag not in game.tags]:
                    game.add_timeline_event(TimelineEventType.TagsAdded, ", ".join(difference))
                if difference := [tag.text for tag in game.tags if tag not in thread["tags"]]:
                    game.add_timeline_event(TimelineEventType.TagsRemoved, ", ".join(difference))

            if game.score != thread["score"]:
                if game.score < thread["score"]:
                    game.add_timeline_event(TimelineEventType.ScoreIncreased, game.score, game.votes, thread["score"], thread["votes"])
                else:
                    game.add_timeline_event(TimelineEventType.ScoreDecreased, game.score, game.votes, thread["score"], thread["votes"])

        breaking_name_parsing    = last_check_before("9.6.4",  game.last_check_version)  # Skip name change in update popup
        breaking_version_parsing = last_check_before("10.1.1", game.last_check_version)  # Skip update popup and keep installed/finished checkboxes
        breaking_keep_old_image  = last_check_before("9.0",    game.last_check_version)  # Keep existing image files

        last_full_check = last_changed
        last_check_version = globals.version

        # Skip update popup and don't reset finished/installed checkboxes if refreshing with braking changes
        finished = game.finished
        installed = game.installed
        updated = game.updated
        if breaking_version_parsing or old_status is Status.Unchecked:
            if old_version == finished:
                finished = version  # Is breaking and was previously finished, mark again as finished
            if old_version == installed:
                installed = version  # Is breaking and was previously installed, mark again as installed
            old_version = version  # Don't include version change in popup for simple parsing adjustments
        else:
            if version != old_version:
                if not game.archived:
                    updated = True

        # Don't include name change in popup for simple parsing adjustments
        if breaking_name_parsing:
            old_name = thread["name"]

        fetch_image = game.image.missing
        if not game.image_url == "custom" and not breaking_keep_old_image:
            fetch_image = fetch_image or (thread["image_url"] != game.image_url)

        unknown_tags_flag = game.unknown_tags_flag
        if len(thread["unknown_tags"]) > 0 and game.unknown_tags != thread["unknown_tags"]:
            unknown_tags_flag = True

        async def update_game():
            game.name = thread["name"]
            game.version = version
            game.developer = thread["developer"]
            game.type = thread["type"]
            game.status = thread["status"]
            game.url = url
            game.last_updated = thread["last_updated"]
            game.last_full_check = last_full_check
            game.last_check_version = last_check_version
            game.score = thread["score"]
            game.votes = thread["votes"]
            game.finished = finished
            game.installed = installed
            game.updated = updated
            game.description = thread["description"]
            game.changelog = thread["changelog"]
            game.tags = thread["tags"]
            game.unknown_tags = thread["unknown_tags"]
            game.unknown_tags_flag = unknown_tags_flag
            game.image_url = thread["image_url"]
            game.downloads = thread["downloads"]

            changed_name = thread["name"] != old_name
            changed_status = thread["status"] != old_status
            changed_version = version != old_version

            if old_status is not Status.Unchecked:
                if changed_name:
                    game.add_timeline_event(TimelineEventType.ChangedName, old_name, game.name)
                if changed_status:
                    game.add_timeline_event(TimelineEventType.ChangedStatus, old_status.name, game.status.name)
                if changed_version:
                    game.add_timeline_event(TimelineEventType.ChangedVersion, old_version, game.version)

            if not game.archived and old_status is not Status.Unchecked and (
                changed_name or changed_status or changed_version
            ):
                old_game = OldGame(
                    id=game.id,
                    name=old_name,
                    version=old_version,
                    status=old_status,
                )
                globals.updated_games[game.id] = old_game

        if fetch_image and thread["image_url"] and thread["image_url"].startswith("http"):
            with images_counter:
                try:
                    res = await fetch("GET", thread["image_url"], timeout=globals.settings.request_timeout * 4, raise_for_status=True)
                except aiohttp.ClientResponseError as exc:
                    if exc.status < 400:
                        raise  # Not error status
                    if thread["image_url"].startswith("https://i.imgur.com"):
                        thread["image_url"] = "blocked"
                    else:
                        thread["image_url"] = "dead"
                    res = b""
                except aiohttp.ClientConnectorError as exc:
                    if not isinstance(exc.os_error, socket.gaierror):
                        raise  # Not a dead link
                    if is_f95zone_url(thread["image_url"]):
                        raise  # Not a foreign host, raise normal connection error message
                    f95zone_ok = True
                    foreign_ok = True
                    try:
                        await async_thread.loop.run_in_executor(None, socket.gethostbyname, f95_domain)
                    except Exception:
                        f95zone_ok = False
                    try:
                        await async_thread.loop.run_in_executor(None, socket.gethostbyname, re.search(r"^https?://([^/]+)", thread["image_url"]).group(1))
                    except Exception:
                        foreign_ok = False
                    if f95zone_ok and not foreign_ok:
                        thread["image_url"] = "dead"
                        res = b""
                    else:
                        raise  # Foreign host might not actually be dead
                async def set_image_and_update_game():
                    await game.set_image_async(res)
                    await update_game()
                await asyncio.shield(set_image_and_update_game())
        else:
            await asyncio.shield(update_game())
        globals.refresh_progress += 1


async def check_notifs(standalone=True):
    if standalone:
        globals.refresh_total = 2
    if not await assert_login():
        return
    if standalone:
        globals.refresh_progress = 1

    res = None
    try:
        res = await fetch("GET", f95_notif_endpoint.format(xf_token=xf_token))
        raise_f95zone_error(res)
        res = json.loads(res)
        raise_f95zone_error(res)
        alerts = int(res["visitor"]["alerts_unread"].replace(",", "").replace(".", ""))
        inbox  = int(res["visitor"]["conversations_unread"].replace(",", "").replace(".", ""))
    except Exception as exc:
        if isinstance(exc, msgbox.Exc):
            raise exc
        if res:
            async with aiofiles.open(globals.self_path / "notifs_broken.bin", "wb") as f:
                await f.write(json.dumps(res).encode() if isinstance(res, (dict, list)) else res)
        raise msgbox.Exc(
            "Notifs check error",
            "Something went wrong checking your unread notifications:\n"
            f"{error.text()}\n" + (
                "\n"
                "The response body has been saved to:\n"
                f"{globals.self_path / 'notifs_broken.bin'}\n"
                "Please submit a bug report on F95Zone or GitHub including this file."
                if res else ""
            ),
            MsgBox.error,
            more=error.traceback()
        )
    globals.refresh_progress += 1
    if alerts != 0 and inbox != 0:
        msg = (
            f"You have {alerts + inbox} unread notifications.\n"
            f"({alerts} alert{'s' if alerts > 1 else ''} and {inbox} conversation{'s' if inbox > 1 else ''})\n"
        )
    elif alerts != 0 and inbox == 0:
        msg = f"You have {alerts} unread alert{'s' if alerts > 1 else ''}.\n"
    elif alerts == 0 and inbox != 0:
        msg = f"You have {inbox} unread conversation{'s' if inbox > 1 else ''}.\n"
    else:
        return
    def open_callback():
        if alerts > 0:
            callbacks.open_webpage(f95_alerts_page)
        if inbox > 0:
            callbacks.open_webpage(f95_inbox_page)
    buttons = {
        f"{icons.check} Yes": open_callback,
        f"{icons.cancel} No": None
    }
    for popup in globals.popup_stack:
        if popup.func is msgbox.msgbox and popup.args[0] == "Notifications":
            globals.popup_stack.remove(popup)
    utils.push_popup(
        msgbox.msgbox, "Notifications",
        msg +
        "\n"
        f"Do you want to view {'them' if (alerts + inbox) > 1 else 'it'}?",
        MsgBox.info, buttons
    )
    if globals.gui.hidden or not globals.gui.focused:
        globals.gui.tray.push_msg(
            title="Notifications",
            msg=msg +
                "Click here to view them.",
            icon=QSystemTrayIcon.MessageIcon.Information)


async def check_updates():
    if (globals.self_path / ".git").is_dir():
        return  # Running from git repo, skip update
    res = None
    try:
        res = await fetch("GET", app_update_endpoint, headers={"Accept": "application/vnd.github+json"})
        res = json.loads(res)
        globals.last_update_check = time.time()
        if "tag_name" not in res:
            utils.push_popup(
                msgbox.msgbox, "Update check error",
                "Failed to fetch latest F95Checker release information.\n"
                "This might be a temporary issue.",
                MsgBox.warn
            )
            return
        if res["prerelease"]:
            return  # Release is not ready yet
        latest_name = res["tag_name"]
        latest = latest_name.split(".")
        current = globals.version.split(".")
        if len(current) > len(latest):
            latest += ["0" for _ in range(len(current) - len(latest))]
        elif len(latest) > len(current):
            current += ["0" for _ in range(len(latest) - len(current))]
        update_available = not globals.release  # Allow updating from beta to full release
        for cur, lat in zip(current, latest):
            if cur == lat:
                continue  # Ignore this field if same on both versions
            update_available = int(lat) > int(cur)
            break  # If field is bigger then its an update
        asset_url = None
        asset_name = None
        asset_size = None
        asset_type = globals.os.name.lower() if globals.frozen else "source"
        for asset in res["assets"]:
            if asset_type in asset["name"].lower():
                asset_url = asset["browser_download_url"]
                asset_name = asset["name"]
                asset_size = asset["size"]
                break
        changelog = res["body"].strip("\n")
        if (match := "## 🚀 Changelog") in changelog:
            changelog = changelog[changelog.find(match) + len(match):].strip()
        if not update_available or not asset_url or not asset_name or not asset_size:
            return
    except Exception:
        if res:
            async with aiofiles.open(globals.self_path / "update_broken.bin", "wb") as f:
                await f.write(json.dumps(res).encode() if isinstance(res, (dict, list)) else res)
        raise msgbox.Exc(
            "Update check error",
            "Something went wrong checking for F95Checker updates:\n"
            f"{error.text()}\n" + (
                "\n"
                "The response body has been saved to:\n"
                f"{globals.self_path / 'update_broken.bin'}\n"
                "Please submit a bug report on F95Zone or GitHub including this file."
                if res else ""
            ),
            MsgBox.error,
            more=error.traceback()
        )
    async def update_callback():
        progress = 0.0
        total = float(asset_size)
        cancel = False
        status = f"(1/3) Downloading {asset_name}..."
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
            imgui.text("(DON'T reopen manually after the update!)")
            imgui.text("(Allow it up to 3 minutes to finish up after)")
        def cancel_callback():
            nonlocal cancel
            cancel = True
        buttons = {
            f"{icons.cancel} Cancel": cancel_callback
        }
        utils.push_popup(
            utils.popup, "Updating F95Checker",
            popup_content,
            buttons=buttons,
            closable=False,
            outside=False
        )
        asset_data = io.BytesIO()
        async with request("GET", asset_url, timeout=3600, read=False) as (_, req):
            async for chunk in req.content.iter_any():
                if cancel:
                    return
                if chunk:
                    progress += asset_data.write(chunk)
                else:
                    break
        progress = 0.0
        total = 1.0
        status = f"(2/3) Extracting {asset_name}..."
        asset_path = pathlib.Path(tempfile.TemporaryDirectory(prefix=asset_name[:asset_name.rfind(".")] + "-").name)
        with zipfile.ZipFile(asset_data) as z:
            total = float(len(z.filelist))
            for file in z.filelist:
                if cancel:
                    shutil.rmtree(asset_path, ignore_errors=True)
                    return
                extracted = z.extract(file, asset_path)
                if (attr := file.external_attr >> 16) != 0:
                    os.chmod(extracted, attr)
                progress += 1
        progress = 5.0
        total = 5.0
        status = "(3/3) Installing update in..."
        fmt = "{progress:.0f}s"
        for _ in range(500):
            if cancel:
                shutil.rmtree(asset_path, ignore_errors=True)
                return
            await asyncio.sleep(0.01)
            progress -= 0.01
        src = asset_path.absolute()
        dst = globals.self_path.absolute()
        if macos_app := (globals.frozen and globals.os is Os.MacOS):
            src = next(asset_path.glob("*.app")).absolute()  # F95Checker-123/F95Checker.app
            dst = globals.self_path.parent.parent.absolute()  # F95Checker.app/Contents/MacOS
        ppid = os.getppid()  # main.py launches a subprocess for the main script, so we need the parent pid
        if globals.os is Os.Windows:
            script = "\n".join((
                "try {"
                'Write-Host "Waiting for F95Checker to quit..."',
                f"Wait-Process -Id {ppid}",
                'Write-Host "Sleeping 3 seconds..."',
                "Start-Sleep -Seconds 3",
                'Write-Host "Deleting old version files..."',
                " | ".join((
                    f"Get-ChildItem -Force -Recurse -Path {shlex.quote(str(dst))}",
                    "Select-Object -ExpandProperty FullName",
                    "Sort-Object -Property Length -Descending",
                    "Remove-Item -Force -Recurse",
                )),
                'Write-Host "Moving new version files..."',
                f"Get-ChildItem -Force -Path {shlex.quote(str(src))} | Select-Object -ExpandProperty FullName | Move-Item -Force -Destination {shlex.quote(str(dst))}",
                'Write-Host "Sleeping 3 seconds..."',
                "Start-Sleep -Seconds 3",
                'Write-Host "Starting F95Checker..."',
                f"& {globals.start_cmd}",
                "} catch {",
                'Write-Host "An error occurred:`n" $_.InvocationInfo.PositionMessage "`n" $_',
                "}",
            ))
            shell = [shutil.which("powershell")]
        else:
            for item in dst.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink()
                except Exception:
                    pass
            for item in src.iterdir():
                try:
                    shutil.move(item, dst)
                except Exception:
                    pass
            script = "\n".join([
                shlex.join(["echo", "Waiting for F95Checker to quit..."]),
                shlex.join(["tail", "--pid", str(ppid), "-f", os.devnull] if globals.os is Os.Linux else ["lsof", "-p", str(ppid), "+r", "1"]),
                shlex.join(["echo", "Sleeping 3 seconds..."]),
                shlex.join(["sleep", "3"]),
                shlex.join(["echo", "Starting F95Checker..."]),
                globals.start_cmd,
            ])
            shell = [shutil.which("bash") or shutil.which("zsh") or shutil.which("sh"), "-c"]
        if macos_app:
            shutil.rmtree(asset_path, ignore_errors=True)
        await asyncio.create_subprocess_exec(
            *shell, script,
            cwd=globals.self_path
        )
        globals.gui.close()
    def update_callback_wrapper():
        global updating
        updating = True
        def update_callback_done(_):
            global updating
            updating = False
        task = async_thread.run(update_callback())
        task.add_done_callback(update_callback_done)
    buttons = {
        f"{icons.check} Yes": update_callback_wrapper,
        f"{icons.cancel} No": None
    }
    for popup in globals.popup_stack:
        if popup.func is msgbox.msgbox and popup.args[0] == "F95Checker update":
            globals.popup_stack.remove(popup)
    if globals.frozen and globals.os is Os.MacOS:
        path = globals.self_path.parent.parent
    else:
        path = globals.self_path
    utils.push_popup(
        msgbox.msgbox, "F95Checker update",
        f"F95Checker has been updated to version {latest_name} (you are on {globals.version_name}).\n"
        "UPDATING WILL DELETE EVERYTHING IN THIS FOLDER:\n"
        f"{path}\n"
        "Your user data (games, settings, login, ...) will not be affected.\n"
        "\n"
        "Do you want to update?\n"
        "(The app will restart automatically, DON'T reopen manually!)",
        MsgBox.info,
        buttons=buttons,
        more=changelog,
        bottom=True
    )
    if globals.gui.hidden or not globals.gui.focused:
        globals.gui.tray.push_msg(
            title="F95Checker update",
            msg="F95Checker has received an update.\n"
                "Click here to view it.",
            icon=QSystemTrayIcon.MessageIcon.Information
        )


async def refresh(*games: list[Game], full=False, notifs=True):
    fast_queue: list[list[Game]] = [[]]
    for game in (games or globals.games.values()):
        if game.custom:
            continue
        if not games and game.status is Status.Completed and not globals.settings.refresh_completed_games:
            continue
        if len(fast_queue[-1]) == api_fast_check_max_ids:
            fast_queue.append([])
        fast_queue[-1].append(game)

    notifs = notifs and globals.settings.check_notifs
    globals.refresh_progress += 1
    globals.refresh_total += sum(len(chunk) for chunk in fast_queue) + bool(notifs)

    global fast_checks_sem, full_checks_sem, fast_checks_counter
    fast_checks_sem = asyncio.Semaphore(1)
    full_checks_sem = asyncio.Semaphore(globals.settings.refresh_workers)
    fast_checks_counter = 0
    tasks: list[asyncio.Task] = []
    try:
        tasks = [asyncio.create_task(fast_check(chunk, full=full)) for chunk in fast_queue]
        await asyncio.gather(*tasks)
    except Exception:
        for task in tasks:
            task.cancel()
        fast_checks_sem = None
        full_checks_sem = None
        fast_checks_counter = 0
        raise
    fast_checks_sem = None
    full_checks_sem = None
    fast_checks_counter = 0

    if notifs:
        await check_notifs(standalone=False)

    if not games:
        globals.settings.last_successful_refresh.update(time.time())
        await db.update_settings("last_successful_refresh")


ddos_guard_bypass_fake_mark = {
    "_geo": True,
    "_sensor": {
        "gyroscope": False,
        "accelerometer": False,
        "magnetometer": False,
        "absorient": False,
        "relorient": False
    },
    "userAgent": "Linux_x86_64_Gecko_Mozilla_undefined",
    "webdriver": False,
    "language": "en-US",
    "colorDepth": 32,
    "deviceMemory": "not available",
    "pixelRatio": 1,
    "hardwareConcurrency": 12,
    "screenResolution": [
        1920,
        1080
    ],
    "availableScreenResolution": [
        1920,
        1080
    ],
    "timezoneOffset": 240,
    "timezone": "America/New_York",
    "sessionStorage": True,
    "localStorage": True,
    "indexedDb": True,
    "addBehavior": False,
    "openDatabase": False,
    "cpuClass": "not available",
    "platform": "Linux x86_64",
    "doNotTrack": "1",
    "plugins": [
        [
            "PDF Viewer",
            "Portable Document Format",
            [
                [
                    "application/pdf",
                    "pdf"
                ],
                [
                    "text/pdf",
                    "pdf"
                ]
            ]
        ],
        [
            "Chrome PDF Viewer",
            "Portable Document Format",
            [
                [
                    "application/pdf",
                    "pdf"
                ],
                [
                    "text/pdf",
                    "pdf"
                ]
            ]
        ],
        [
            "Chromium PDF Viewer",
            "Portable Document Format",
            [
                [
                    "application/pdf",
                    "pdf"
                ],
                [
                    "text/pdf",
                    "pdf"
                ]
            ]
        ],
        [
            "Microsoft Edge PDF Viewer",
            "Portable Document Format",
            [
                [
                    "application/pdf",
                    "pdf"
                ],
                [
                    "text/pdf",
                    "pdf"
                ]
            ]
        ],
        [
            "WebKit built-in PDF",
            "Portable Document Format",
            [
                [
                    "application/pdf",
                    "pdf"
                ],
                [
                    "text/pdf",
                    "pdf"
                ]
            ]
        ]
    ],
    "canvas": [],
    "webgl": False,
    "adBlock": False,
    "hasLiedLanguages": False,
    "hasLiedResolution": False,
    "hasLiedOs": False,
    "hasLiedBrowser": False,
    "touchSupport": [
        0,
        False,
        False
    ],
    "fonts": [
        "Andale Mono",
        "Arial",
        "Arial Black",
        "Bitstream Vera Sans Mono",
        "Calibri",
        "Cambria",
        "Cambria Math",
        "Comic Sans MS",
        "Consolas",
        "Courier",
        "Courier New",
        "Georgia",
        "Helvetica",
        "Impact",
        "Lucida Console",
        "LUCIDA GRANDE",
        "Lucida Sans Unicode",
        "Palatino",
        "Times",
        "Times New Roman",
        "Trebuchet MS",
        "Verdana"
    ],
    "audio": "100.00000",
    "enumerateDevices": [
        "audioinput;"
    ],
    "context": "free_splash"
}
