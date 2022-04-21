import queue as queuem
import threading
import typing
import time

queue: queuem.Queue = None
thread: threading.Thread = None


def setup():
    global queue, thread

    queue = queuem.Queue()

    def run_loop():
        while True:
            if queue.not_empty:
                queue.get()()
            else:
                time.sleep(0.1)

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()


def enqueue(fn: typing.Callable):
    queue.put(fn)
