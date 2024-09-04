import bencode2
import pathlib
import asyncio
import imgui
import json

from modules.structs import (
    TorrentResult,
)
from modules.api import (
    request,
    fetch,
)
from modules import (
    globals,
    async_thread,
    callbacks,
    icons,
    utils,
    db,
)

domain = "dl.rpdl.net"
host = "https://" + domain
login_endpoint    = host + "/api/user/login"
register_endpoint = host + "/api/user/register"
search_endpoint   = host + "/api/torrents?search={query}&sort={sort}"
download_endpoint = host + "/api/torrent/download/{id}"
details_endpoint  = host + "/api/torrent/{id}"
torrent_page      = host + "/torrent/{id}"

auth = lambda: {"Authorization": f"Bearer {globals.settings.rpdl_token}"}


async def torrent_search(query: str):
    res = await fetch("GET", search_endpoint.format(query=query, sort="uploaded_DESC"))
    res = json.loads(res)
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
    async with request("POST", login_endpoint, json={
        "login": globals.settings.rpdl_username,
        "password": globals.settings.rpdl_password
    }) as (res, req):
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
    async with request("POST", register_endpoint, json={
        "username": globals.settings.rpdl_username,
        "password": globals.settings.rpdl_password,
        "confirm_password": confirm_password
    }) as (res, req):
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
        res = await fetch("GET", download_endpoint.format(id=torrent_id), headers={**auth()})
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
