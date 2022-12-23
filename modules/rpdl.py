import bencode3
import pathlib
import json

from modules.structs import (
    TorrentResult,
)
from modules.api import (
    fetch,
)
from modules import (
    globals,
    callbacks,
)

domain = "dl.rpdl.net"
host = "https://" + domain
search_endpoint   = host + "/api/torrents?search={query}&sort={sort}"
download_endpoint = host + "/api/torrent/download/{id}"
details_endpoint  = host + "/api/torrent/{id}"
torrent_page      = host + "/torrent/{id}"


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


async def login():
    pass  # FIXME


async def assert_login():
    if not globals.settings.rpdl_token:
        await login()
        if not globals.settings.rpdl_token:
            return False
    return True


def has_authenticated_tracker(res: bytes | dict):
    if isinstance(res, bytes):
        tracker = bencode3.bdecode(res).get("announce", "")
    elif isinstance(res, dict):
        tracker = (res.get("data", {}).get("trackers") or [""])[0]
    else:
        return False
    return bool(tracker.split("/announce")[-1])


async def open_torrent_file(torrent_id: int):
    for _ in range(2):
        if not await assert_login():
            return
        res = await fetch("GET", download_endpoint.format(id=torrent_id))
        if not has_authenticated_tracker(res):
            globals.settings.rpdl_token = ""
            continue
        break
    else:  # Didn't break
        return
    name = bencode3.bdecode(res).get("info", {}).get("name", str(torrent_id))
    torrent = (pathlib.Path.home() / "Downloads") / f"{name}.torrent"
    torrent.parent.mkdir(parents=True, exist_ok=True)
    torrent.write_bytes(res)
    await callbacks.default_open(str(torrent))


async def open_magnet_link(torrent_id: int):
    for _ in range(2):
        if not await assert_login():
            return
        res = await fetch("GET", details_endpoint.format(id=torrent_id))
        res = json.loads(res)
        if not has_authenticated_tracker(res):
            globals.settings.rpdl_token = ""
            continue
        break
    else:  # Didn't break
        return
    magnet = res["data"]["magnet_link"]
    await callbacks.default_open(magnet)
