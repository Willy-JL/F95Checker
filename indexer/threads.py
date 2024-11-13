import asyncio

import fastapi

from indexer import cache

fast_max_ids = 10
valid_thread_ids = range(1, 1_000_000)  # Top ID was ~232k at time of writing

router = fastapi.APIRouter()


@router.get("/fast")
async def fast_request(ids: str):
    ids = ids.split(",")
    if len(ids) > fast_max_ids:
        return fastapi.responses.JSONResponse(
            f"Max {fast_max_ids} IDs",
            status_code=400,
        )

    try:
        ids = set(int(id) for id in ids if id)
    except ValueError:
        return fastapi.responses.JSONResponse(
            "IDs must be numeric",
            status_code=400,
        )

    if any(id not in valid_thread_ids for id in ids):
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
async def full_request(id: int):
    if id not in valid_thread_ids:
        return fastapi.responses.JSONResponse(
            "Invalid thread ID",
            status_code=400,
        )

    full = await cache.get_thread(id)

    return fastapi.responses.JSONResponse(
        full,
        status_code=200,
    )
