import asyncio

import fastapi

from indexer import cache

router = fastapi.APIRouter()


@router.get("/threads")
async def threads_request(ids: str):
    try:
        ids = [int(id) for id in ids.split(",") if id]
    except ValueError:
        return fastapi.responses.JSONResponse("Invalid thread IDs", status_code=400)

    tasks = [cache.get_thread(id) for id in ids]
    threads = await asyncio.gather(*tasks)
    results = dict(zip(ids, threads))
    return fastapi.responses.JSONResponse(results, status_code=200)
