# https://gist.github.com/Willy-JL/3eaa171144b3bb0a4602c7b537f90036
from contextlib import contextmanager
import typing
import sys

# Backup original functionality
_stdout: typing.TextIO = sys.stdout
_stderr: typing.TextIO = sys.stderr
_stdin:  typing.TextIO = sys.stdin

# Used to temporarily stop output to log file
_pause_file_output_count: int = 0


def _file_write(message: str):
    if _pause_file_output_count > 0:
        return
    try:
        with open("log.txt", "a", encoding='utf-8') as log:
            log.write(message)
    except Exception:
        pass

class __stdout_override():
    def write(self, message: str):
        _stdout.write(message)
        _file_write(message)

    def __getattr__(self, name: str):
        return getattr(_stdout, name)

class __stderr_override():
    def write(self, message: str):
        _stderr.write(message)
        _file_write(message)

    def __getattr__(self, name: str):
        return getattr(_stderr, name)

class __stdin_override():
    def readline(self):
        message = _stdin.readline()
        _file_write(message)
        return message

    def __getattr__(self, name: str):
        # The input() function tries to use sys.stdin.fileno()
        # and then do the printing and input reading on the C
        # side, causing this .readline() override to not work.
        # Denying access to .fileno() fixes this and forces
        # input() to use sys.stdin.readline()
        if name == "fileno": raise AttributeError
        return getattr(_stdin, name)

@contextmanager
def pause_file_output():
    global _pause_file_output_count
    _pause_file_output_count += 1
    yield
    _pause_file_output_count -= 1
pause = pause_file_output


def install():

    # Create / clear log file
    try:
        open("log.txt", "w").close()
    except Exception:
        pass

    # Apply overrides
    sys.stdout = __stdout_override()
    sys.stderr = __stderr_override()
    sys.stdin  = __stdin_override ()
