#!/usr/bin/env python3
import contextlib
import logging
import fastapi
import uvicorn
import os

from indexer import (
    threads,
    cache,
)


def force_log_info(msg: str):
    logger = logging.getLogger()
    prev_level = logger.level
    logger.setLevel(logging.INFO)
    logging.info(msg)
    logger.setLevel(prev_level)


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    async with cache.lifespan():
        force_log_info("Startup complete")
        yield
        force_log_info("Shutting down")


app = fastapi.FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
app.include_router(threads.router)


def main() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.WARN)

    uvicorn.run(
        "indexer-main:app",
        host=os.environ.get("BIND_HOST", "127.0.0.1"),
        port=int(os.environ.get("BIND_HOST", 8069)),
        workers=1,
        log_config=None,
    )


if __name__ == "__main__":
    main()
