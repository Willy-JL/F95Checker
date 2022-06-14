# https://gist.github.com/Willy-JL/3eaa171144b3bb0a4602c7b537f90036
from contextlib import contextmanager
import sys
import re
import io
import os

# Fix missing streams
for stream in ("stdout", "stderr", "stdin"):
    if getattr(sys, stream) is None:
        setattr(sys, stream, open(os.devnull, "w+"))

# Backup original functionality
_stdout = sys.stdout
_stderr = sys.stderr
_stdin  = sys.stdin

# Used to temporarily stop output to log file
_pause_file_output = False
_path = "log.txt"


def _file_write(message, no_color=True):
    if _pause_file_output:
        return
    if no_color:
        message = re.sub("\\x1b\[38;2;\d\d?\d?;\d\d?\d?;\d\d?\d?m", "", message)
        message = re.sub("\\x1b\[\d\d?\d?m",                        "", message)
    with open(_path, "a", encoding="utf-8") as log:
        log.write(message)

class __stdout_override():
    def write(self, message):
        _stdout.write(message)
        _file_write(message)

    def __getattr__(self, name):
        return getattr(_stdout, name)

class __stderr_override():
    def write(self, message):
        _stderr.write(message)
        _file_write(message)

    def __getattr__(self, name):
        return getattr(_stderr, name)

class __stdin_override():
    def readline(self):
        message = _stdin.readline()
        _file_write(message, no_color=False)
        return message

    def __getattr__(self, name):
        # The input() function tries to use sys.stdin.fileno()
        # and then do the printing and input reading on the C
        # side, causing this .readline() override to not work.
        # Denying access to .fileno() fixes this and forces
        # input() to use sys.stdin.readline()
        if name == "fileno": raise AttributeError
        return getattr(_stdin, name)

@contextmanager
def pause_file_output():
    global _pause_file_output
    _pause_file_output = True
    yield
    _pause_file_output = False
pause = pause_file_output


def install(path=_path, lowlevel=False):
    global _path
    _path = str(path)
    if lowlevel:
        print(f"Redirecting stdout and stderr to {_path}")
        log = open(str(_path), "wb")
        # Redirect
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())
        # Buffer wrap
        sys.stdout = io.TextIOWrapper(os.fdopen(sys.stdout.fileno(), "wb"))
        sys.stderr = io.TextIOWrapper(os.fdopen(sys.stderr.fileno(), "wb"))
    else:
        # Create / clear log file
        try:
            open(_path, "w").close()
        except Exception:
            pass
        # Apply overrides
        sys.stdout = __stdout_override()
        sys.stderr = __stderr_override()
        sys.stdin  = __stdin_override ()


# Example usage
if __name__ == "__main__":
    import logger  # This script is designed as a module you import
    logger.install()

    from colorama import Fore
    def rgb(r, g, b):
        return f"\x1b[38;2;{r};{g};{b}m"

    print("I have been saved to the log file!")
    with logger.pause_file_output():
        print("But I didn't! Shhh, this is just between you and me...")
    print(f"{rgb(0, 100, 255)}This is blue! {rgb(255, 100, 100)}This is red! {Fore.RESET}And this is back to normal!")
    print("But in the log file there are no color escape codes!")
    input("Also your input gets saved in the file! Try it: ")
