import threading
import asyncio
import typing
import time

loop: asyncio.BaseEventLoop = None
thread: threading.Thread = None


def setup():
    global loop, thread

    loop = asyncio.new_event_loop()

    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()


def run(coroutine: typing.Coroutine, wait: bool = False):
    if wait:
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        while not future.done():
            time.sleep(0.1)
        return future.result
    else:
        return asyncio.run_coroutine_threadsafe(coroutine, loop)
