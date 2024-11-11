import fastapi

router = fastapi.APIRouter()


@router.get("/threads")
async def threads_request(ids: str):
    try:
        ids = (int(id) for id in ids.split(","))
    except ValueError:
        return fastapi.responses.JSONResponse("Invalid thread IDs", status_code=400)

    # FIXME: Implement
    return fastapi.responses.JSONResponse(ids, status_code=200)
