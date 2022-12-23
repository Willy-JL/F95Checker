import json

from modules.structs import (
    TorrentResult,
)
from modules.api import (
    fetch,
)

domain = "dl.rpdl.net"
host = "https://" + domain
search_endpoint   = host + "/api/torrents"
torrent_page      = host + "/torrent/{id}"


async def torrent_search(query: str):
    res = await fetch("GET", search_endpoint, params={"search": query, "sort": "uploaded_DESC"})
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
