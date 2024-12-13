# https://gist.github.com/Willy-JL/bb410bcc761f8bf5649180f22b7f3b44
import threading
import typing

stack: list = None
thread: threading.Thread = None
_condition: threading.Condition = None


def setup():
    global stack, thread, _condition

    stack = []
    _condition = threading.Condition()

    def run_loop():
        while True:
            while stack:
                stack.pop()()
            with _condition:
                _condition.wait()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()


def queue(fn: typing.Callable):
    stack.append(fn)
    with _condition:
        _condition.notify()


# Example usage
if __name__ == "__main__":
    import sync_thread  # This script is designed as a module you import
    sync_thread.setup()

    def say_hello():
        print("Hello world!")

    for _ in range(10):
        sync_thread.queue(say_hello)
