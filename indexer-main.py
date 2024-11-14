#!/usr/bin/env python3
import contextlib
import logging
import os
import pathlib
import subprocess

import fastapi
import uvicorn

from indexer import (
    cache,
    scraper,
    threads,
)


def force_log_info(msg: str) -> None:
    logger = logging.getLogger()
    prev_level = logger.level
    logger.setLevel(logging.INFO)
    logging.info(msg)
    logger.setLevel(prev_level)


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    try:
        version = subprocess.check_output(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=pathlib.Path(__file__).parent,
            encoding="utf-8",
        ).strip()
    except subprocess.CalledProcessError:
        version = "unknown"

    async with (
        cache.lifespan(version),
        scraper.lifespan(version),
    ):
        force_log_info("Startup complete")
        yield
        force_log_info("Shutting down")


app = fastapi.FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
app.include_router(threads.router)


def main() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    uvicorn.run(
        "indexer-main:app",
        host=os.environ.get("BIND_HOST", "127.0.0.1"),
        port=int(os.environ.get("BIND_HOST", 8069)),
        workers=1,
        log_config=None,
        log_level=logging.WARN,
    )


if __name__ == "__main__":
    main()
