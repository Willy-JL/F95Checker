# https://gist.github.com/Willy-JL/183cb7134e940db1cfab72480e95a357
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
    future = asyncio.run_coroutine_threadsafe(coroutine, loop)
    if wait:
        while not future.done():
            time.sleep(0.1)
        return future.result
    else:
        return future


# Example usage
if __name__ == "__main__":
    import async_thread  # This script is designed as a module you import
    async_thread.setup()

    import random
    async def wait_and_say_hello(num):
        await asyncio.sleep(random.random())
        print(f"Hello {num}!")

    for i in range(10):
        async_thread.run(wait_and_say_hello(i))

    # You can also wait for the task to complete:
    for i in range(10):
        async_thread.run(wait_and_say_hello(i), wait=True)
