# https://gist.github.com/Willy-JL/bb410bcc761f8bf5649180f22b7f3b44
import queue as _queue
import threading
import time
import typing

fn_queue: _queue.Queue = None
thread: threading.Thread = None


def setup():
    global fn_queue, thread

    fn_queue = _queue.Queue()

    def run_loop():
        while True:
            if fn_queue.not_empty:
                fn_queue.get()()
            else:
                time.sleep(0.1)

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()


def queue(fn: typing.Callable):
    fn_queue.put(fn)


# Example usage
if __name__ == "__main__":
    import sync_thread  # This script is designed as a module you import
    sync_thread.setup()

    def say_hello():
        print("Hello world!")

    for _ in range(10):
        sync_thread.queue(say_hello)
