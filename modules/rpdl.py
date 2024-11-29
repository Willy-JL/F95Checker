import asyncio
import json
import pathlib
import string

import bencode2
import imgui

from common.structs import (
    Game,
    MsgBox,
    TorrentResult,
)
from external import async_thread
from modules.api import (
    request,
    fetch,
)
from modules import (
    callbacks,
    db,
    globals,
    icons,
    msgbox,
    utils,
)

rpdl_domain = "dl.rpdl.net"
rpdl_host = "https://" + rpdl_domain
rpdl_login_endpoint    = rpdl_host + "/api/user/login"
rpdl_register_endpoint = rpdl_host + "/api/user/register"
rpdl_search_endpoint   = rpdl_host + "/api/torrents?search={query}&sort={sort}"
rpdl_download_endpoint = rpdl_host + "/api/torrent/download/{id}"
rpdl_details_endpoint  = rpdl_host + "/api/torrent/{id}"
rpdl_torrent_page      = rpdl_host + "/torrent/{id}"

rpdl_auth_headers = lambda: {"Authorization": f"Bearer {globals.settings.rpdl_token}"}


def raise_rpdl_error(res: bytes | dict):
    if isinstance(res, bytes):
        if any(msg in res for msg in (
            b"<title>Site Maintenance</title>",
            b"<h1>We&rsquo;ll be back soon!</h1>",
        )):
            raise msgbox.Exc(
                "Server downtime",
                "RPDL is currently unreachable,\n"
                "please retry in a few minutes.",
                MsgBox.warn
            )
        return True
    elif isinstance(res, dict):
        return True


async def torrent_search(query: str):
    res = await fetch("GET", rpdl_search_endpoint.format(query=query, sort="uploaded_DESC"))
    raise_rpdl_error(res)
    res = json.loads(res)
    raise_rpdl_error(res)
    results = []
    for result in res["data"]["results"]:
        results.append(TorrentResult(
            id=result["torrent_id"],
            title=result["title"],
            size=result["file_size"],
            seeders=result["seeders"],
            leechers=result["leechers"],
            date=result["upload_date"],
        ))
    return results


async def do_login(reset=False):
    if not globals.settings.rpdl_username or not globals.settings.rpdl_password:
        return "Missing credentials"
    async with request("POST", rpdl_login_endpoint, json={
        "login": globals.settings.rpdl_username,
        "password": globals.settings.rpdl_password
    }) as (res, req):
        raise_rpdl_error(res)
        res = json.loads(res)
        if req.ok:
            globals.settings.rpdl_username = res["data"]["username"]
            globals.settings.rpdl_token = res["data"]["token"]
            await db.update_settings("rpdl_username", "rpdl_token")
            return True
        else:
            if reset:
                globals.settings.rpdl_username = ""
                globals.settings.rpdl_password = ""
                globals.settings.rpdl_token = ""
                await db.update_settings("rpdl_username", "rpdl_password", "rpdl_token")
            return res["error"]


async def do_register(confirm_password: str):
    if not globals.settings.rpdl_username or not globals.settings.rpdl_password or not confirm_password:
        return "Missing credentials"
    async with request("POST", rpdl_register_endpoint, json={
        "username": globals.settings.rpdl_username,
        "password": globals.settings.rpdl_password,
        "confirm_password": confirm_password
    }) as (res, req):
        raise_rpdl_error(res)
        if req.ok:
            return True
        else:
            res = json.loads(res)
            return res["error"]


async def login():
    if await do_login(reset=True) is True:
        return
    login = None
    register = None
    confirm_password = ""
    def popup_content():
        nonlocal login, register, confirm_password
        if login is True or globals.settings.rpdl_token:
            return True
        ret = None
        if imgui.begin_tab_bar("RPDL account"):

            if imgui.begin_tab_item(f"{icons.login} Login", flags=imgui.TAB_ITEM_SET_SELECTED if register is True else 0)[0]:
                if register is True:
                    register = None
                imgui.spacing()
                _320 = globals.gui.scaled(320)

                imgui.text("Username:")
                imgui.same_line()
                pos = imgui.get_cursor_pos_x()
                imgui.set_next_item_width(_320)
                changed, globals.settings.rpdl_username = imgui.input_text("###login_user", globals.settings.rpdl_username)
                if changed:
                    async_thread.run(db.update_settings("rpdl_username"))

                imgui.text("Password:")
                imgui.same_line()
                imgui.set_cursor_pos_x(pos)
                imgui.set_next_item_width(_320)
                changed, globals.settings.rpdl_password = imgui.input_text("###login_pass", globals.settings.rpdl_password, flags=imgui.INPUT_TEXT_PASSWORD)
                if changed:
                    async_thread.run(db.update_settings("rpdl_password"))

                avail = imgui.get_content_region_available_width()
                width = (avail - imgui.style.item_spacing.x) / 2
                if isinstance(login, str):
                    imgui.push_text_wrap_pos(avail)
                    imgui.text(login)
                    imgui.pop_text_wrap_pos()

                if imgui.button(f"{icons.cancel} Cancel", width=width):
                    ret = True
                imgui.same_line()
                if imgui.button(f"{icons.login} Login", width=width):
                    login = False
                imgui.end_tab_item()

            if imgui.begin_tab_item(f"{icons.account_plus} Register")[0]:
                imgui.spacing()
                _320 = globals.gui.scaled(320)

                imgui.text("Username:")
                imgui.same_line()
                pos = imgui.get_cursor_pos_x()
                imgui.set_next_item_width(_320)
                changed, globals.settings.rpdl_username = imgui.input_text("###register_user", globals.settings.rpdl_username)
                if changed:
                    async_thread.run(db.update_settings("rpdl_username"))

                imgui.text("Password:")
                imgui.same_line()
                imgui.set_cursor_pos_x(pos)
                imgui.set_next_item_width(_320)
                changed, globals.settings.rpdl_password = imgui.input_text("###register_pass", globals.settings.rpdl_password, flags=imgui.INPUT_TEXT_PASSWORD)
                if changed:
                    async_thread.run(db.update_settings("rpdl_password"))

                imgui.text("Confirm:")
                imgui.same_line()
                imgui.set_cursor_pos_x(pos)
                imgui.set_next_item_width(_320)
                _, confirm_password = imgui.input_text("###confirm_password", confirm_password, flags=imgui.INPUT_TEXT_PASSWORD)

                avail = imgui.get_content_region_available_width()
                width = (avail - imgui.style.item_spacing.x) / 2
                if isinstance(register, str):
                    imgui.push_text_wrap_pos(avail)
                    imgui.text(register)
                    imgui.pop_text_wrap_pos()

                if imgui.button(f"{icons.cancel} Cancel", width=width):
                    ret = True
                imgui.same_line()
                if imgui.button(f"{icons.account_plus} Register", width=width):
                    register = False
                imgui.end_tab_item()
            imgui.end_tab_bar()
        return ret
    popup = utils.push_popup(
        utils.popup, "RPDL account",
        popup_content,
        closable=True,
        outside=False
    )
    while popup.open:
        if login is False:
            login = None
            login = await do_login()
        if register is False:
            register = None
            register = await do_register(confirm_password)
        await asyncio.sleep(0.1)


async def assert_login():
    if not globals.settings.rpdl_token:
        await login()
        if not globals.settings.rpdl_token:
            return False
    return True


def has_authenticated_tracker(res: bytes | dict):
    if isinstance(res, bytes):
        tracker = bencode2.bdecode(res).get(b"announce", b"").decode()
    elif isinstance(res, dict):
        tracker = (res.get("data", {}).get("trackers") or [""])[0]
    else:
        return False
    return bool(tracker.split("/announce")[-1])


async def open_torrent_file(torrent_id: int):
    for _ in range(2):
        if not await assert_login():
            return
        res = await fetch("GET", rpdl_download_endpoint.format(id=torrent_id), headers={**rpdl_auth_headers()})
        raise_rpdl_error(res)
        if not has_authenticated_tracker(res):
            globals.settings.rpdl_token = ""
            continue
        break
    else:  # Didn't break
        return
    name = bencode2.bdecode(res).get(b"info", {}).get(b"name", str(torrent_id).encode()).decode()
    torrent = (pathlib.Path.home() / "Downloads") / f"{name}.torrent"
    torrent.parent.mkdir(parents=True, exist_ok=True)
    torrent.write_bytes(res)
    await callbacks.default_open(str(torrent))


def open_search_popup(game: Game):
    results = None
    query = "".join(char for char in game.name.replace("&", "And") if char in (string.ascii_letters + string.digits))
    ran_query = query
    def _rpdl_search_popup():
        nonlocal query

        globals.gui.draw_game_downloads_header(game)

        imgui.set_next_item_width(-(imgui.calc_text_size(f"{icons.magnify} Search").x + 2 * imgui.style.frame_padding.x) - imgui.style.item_spacing.x)
        activated, query = imgui.input_text_with_hint(
            "###search",
            "Search torrents...",
            query,
            flags=imgui.INPUT_TEXT_ENTER_RETURNS_TRUE
        )
        imgui.same_line()
        if imgui.button(f"{icons.magnify} Search") or activated:
            async_thread.run(_rpdl_run_search())

        if not results:
            imgui.text(f"Running RPDL search for query '{ran_query}'...")
            imgui.text("Status:")
            imgui.same_line()
            if results is None:
                imgui.text("Searching...")
            else:
                imgui.text("No results!")
            return

        if imgui.begin_table(
            "###rpdl_results",
            column=7,
            flags=imgui.TABLE_NO_SAVED_SETTINGS
        ):
            imgui.table_setup_scroll_freeze(0, 1)
            imgui.table_setup_column("", imgui.TABLE_COLUMN_WIDTH_FIXED)
            imgui.table_setup_column("", imgui.TABLE_COLUMN_WIDTH_STRETCH)
            imgui.table_next_row(imgui.TABLE_ROW_HEADERS)
            imgui.table_next_column()
            imgui.table_header("Actions")
            globals.gui.draw_hover_text(
                f"The {icons.open_in_new} view button will open the torrent webpage with your selected browser.\n"
                f"The {icons.download_multiple} download button will save the torrent file to your user's downloads\n"
                "folder and open it with the default torrenting application.\n",
                text=None
            )
            imgui.table_next_column()
            imgui.table_header("Title")
            imgui.table_next_column()
            imgui.table_header("Seed")
            imgui.table_next_column()
            imgui.table_header("Leech")
            imgui.table_next_column()
            imgui.table_header("Size")
            imgui.table_next_column()
            imgui.table_header("Date")
            for result in results:
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.dummy(0, 0)
                imgui.same_line(spacing=imgui.style.item_spacing.x / 2)
                if imgui.button(icons.open_in_new):
                    callbacks.open_webpage(rpdl_torrent_page.format(id=result.id))
                imgui.same_line()
                if imgui.button(icons.download_multiple):
                    async_thread.run(open_torrent_file(result.id))
                imgui.table_next_column()
                imgui.text(result.title)
                imgui.table_next_column()
                imgui.text(result.seeders)
                imgui.table_next_column()
                imgui.text(result.leechers)
                imgui.table_next_column()
                imgui.text(result.size)
                imgui.table_next_column()
                imgui.push_font(imgui.fonts.mono)
                imgui.text(result.date)
                imgui.pop_font()
                imgui.same_line()
                imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() - imgui.style.frame_padding.y)
                imgui.selectable(
                    "", False,
                    flags=imgui.SELECTABLE_SPAN_ALL_COLUMNS | imgui.SELECTABLE_DONT_CLOSE_POPUPS,
                    height=imgui.get_frame_height()
                )
            imgui.end_table()
    async def _rpdl_run_search():
        nonlocal results, ran_query
        results = None
        ran_query = query
        results = await torrent_search(ran_query)
    utils.push_popup(
        utils.popup, "RPDL torrent search",
        _rpdl_search_popup,
        buttons=True,
        closable=True,
        outside=False,
        footer="Donate at rpdl.net if you like the torrents!"
    )
    async_thread.run(_rpdl_run_search())
