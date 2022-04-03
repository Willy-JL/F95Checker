import threading
import asyncio

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


def run(coroutine):
    return asyncio.run_coroutine_threadsafe(coroutine, loop)
