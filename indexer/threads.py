import asyncio
import time

import fastapi

from indexer import (
    cache,
    f95zone,
)

FAST_MAX_IDS = 10
VALID_THREAD_IDS = range(1, 1_000_000)  # Top ID was ~232k at time of writing

router = fastapi.APIRouter()


@router.get("/fast")
async def fast_request(ids: str):
    ids = ids.split(",")
    if len(ids) > FAST_MAX_IDS:
        return fastapi.responses.JSONResponse(
            f"Max {FAST_MAX_IDS} IDs",
            status_code=400,
        )

    try:
        ids = set(int(id) for id in ids if id)
    except ValueError:
        return fastapi.responses.JSONResponse(
            "IDs must be numeric",
            status_code=400,
        )

    if any(id not in VALID_THREAD_IDS for id in ids):
        return fastapi.responses.JSONResponse(
            "Invalid thread IDs",
            status_code=400,
        )

    tasks = [cache.last_change(id) for id in ids]
    last_changes = await asyncio.gather(*tasks)
    results = dict(zip(ids, last_changes))
    return fastapi.responses.JSONResponse(
        results,
        status_code=200,
    )


@router.get("/full/{id}")
async def full_request(id: int, ts: int):
    if id not in VALID_THREAD_IDS:
        return fastapi.responses.JSONResponse(
            "Invalid thread ID",
            status_code=400,
        )

    # Use timestamps for dynamic cache, but
    # prevent abuse from caching future timestamps
    if ts > time.time():
        return fastapi.responses.JSONResponse(
            "Invalid timestamp",
            status_code=406,
        )

    full = await cache.get_thread(id)

    status = 200
    if index_error := full.get(cache.INDEX_ERROR):
        if index_error == f95zone.ERROR_THREAD_MISSING.error_flag:
            status = 404
        else:
            status = 500

    return fastapi.responses.JSONResponse(
        full,
        status_code=status,
    )
