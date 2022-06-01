# https://gist.github.com/Willy-JL/183cb7134e940db1cfab72480e95a357
import threading
import asyncio
import typing
import time

loop: asyncio.BaseEventLoop = None
thread: threading.Thread = None
done_callback: typing.Callable = lambda _: None


def setup():
    global loop, thread

    loop = asyncio.new_event_loop()

    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()


def run(coroutine: typing.Coroutine):
    future = asyncio.run_coroutine_threadsafe(coroutine, loop)
    future.add_done_callback(done_callback)
    return future


def wait(coroutine: typing.Coroutine):
    future = run(coroutine)
    while future.running():
        time.sleep(0.1)
    if exception := future.exception():
        raise exception
    return future.result


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
        async_thread.wait(wait_and_say_hello(i))
