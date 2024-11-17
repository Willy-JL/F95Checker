# https://gist.github.com/Willy-JL/f733c960c6b0d2284bcbee0316f88878
import sys
import traceback as _traceback


def traceback(exc: Exception = None):
    # Full error traceback with line numbers and previews
    if exc:
        exc_info = type(exc), exc, exc.__traceback__
    else:
        exc_info = sys.exc_info()
    tb_lines = _traceback.format_exception(*exc_info)
    tb = "".join(tb_lines)
    return tb


def text(exc: Exception = None):
    # Short error text like "ExcName: exception text"
    exc = exc or sys.exc_info()[1]
    return f"{type(exc).__name__}: {str(exc) or 'No further details'}"


# Example usage
if __name__ == "__main__":
    import error  # This script is designed as a module you import

    try:
        0/0
    except Exception as exc:
        # can be used with no arguments inside except blocks
        print(error.text())
        print(error.traceback())
        # or if you have the exception object you can pass that
        print(error.text(exc))
        print(error.traceback(exc))
