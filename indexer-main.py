#!/usr/bin/env python3
import contextlib
import logging
import os
import pathlib
import re

import fastapi
import uvicorn

from indexer import (
    cache,
    f95zone,
    threads,
    watcher,
)

logger = logging.getLogger()


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    async with (
        cache.lifespan(),
        f95zone.lifespan(),
        watcher.lifespan(),
    ):
        yield


app = fastapi.FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
app.include_router(threads.router)


def main() -> None:
    logger.setLevel(logging.INFO)
    log_handler = logging.StreamHandler()
    log_handler.setFormatter(_ColourFormatter())
    logger.addHandler(log_handler)

    uvicorn.run(
        "indexer-main:app",
        host=os.environ.get("BIND_HOST", "127.0.0.1"),
        port=int(os.environ.get("BIND_HOST", 8069)),
        workers=1,
        log_config=None,
        log_level=logging.INFO,
        access_log=False,
        env_file="indexer.env",
    )


# https://github.com/Rapptz/discord.py/blob/master/discord/utils.py
class _ColourFormatter(logging.Formatter):
    LEVEL_COLOURS = [
        (logging.DEBUG, "\x1b[30;1m"),
        (logging.INFO, "\x1b[34;1m"),
        (logging.WARNING, "\x1b[33;1m"),
        (logging.ERROR, "\x1b[31m"),
        (logging.CRITICAL, "\x1b[41m"),
    ]
    FORMATS = {
        level: logging.Formatter(
            f"\x1b[30;1m%(asctime)s\x1b[0m {colour}%(levelname)-8s\x1b[0m \x1b[35m%(name)s\x1b[0m %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        for level, colour in LEVEL_COLOURS
    }

    def format(self, record):
        formatter = self.FORMATS.get(record.levelno)
        if formatter is None:
            formatter = self.FORMATS[logging.DEBUG]
        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = f"\x1b[31m{text}\x1b[0m"
        output = formatter.format(record)
        record.exc_text = None
        return output


if __name__ == "__main__":
    main()
