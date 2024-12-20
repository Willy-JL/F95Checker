#!/usr/bin/env python
import contextlib
import os
import pathlib
import sys

version = "11.0.2"
release = False
build_number = 0
version_name = f"{version}{'' if release else ' beta'}{'' if release or not build_number else ' ' + str(build_number)}"
rpc_port = 57095
rpc_url = f"http://127.0.0.1:{rpc_port}"

frozen = getattr(sys, "frozen", False)
self_path = pathlib.Path(sys.executable if frozen else __file__).parent
debug = not (frozen or release)

if not sys.stdout: sys.stdout = open(os.devnull, "w")
if not sys.stderr: sys.stderr = open(os.devnull, "w")
if os.devnull in (sys.stdout.name, sys.stderr.name):
    debug = False


def main():
    # Must import globals first to fix load paths when frozen
    from modules import globals

    from common.structs import Os
    try:
        # Install uvloop on MacOS and Linux, non essential so ignore errors
        if globals.os is not Os.Windows:
            import uvloop
            uvloop.install()
    except Exception:
        pass

    from external import async_thread, sync_thread
    async_thread.setup()
    sync_thread.setup()

    from modules import api, db
    with db.setup(), api.setup():

        from modules import gui
        globals.gui = gui.MainGUI()

        from modules import rpc_thread
        with rpc_thread.setup():

            globals.gui.main_loop()


@contextlib.contextmanager
def lock_singleton():
    from external import singleton
    try:
        singleton.lock("F95Checker")
        locked = True
    except RuntimeError:
        locked = False
    try:
        yield locked
    finally:
        if locked:
            singleton.release("F95Checker")
        else:
            try:
                from urllib import request
                request.urlopen(request.Request(rpc_url + "/window/show", method="POST"))
            except Exception:
                pass


if __name__ == "__main__":
    if "-c" in sys.argv:
        # Mimic python's -c flag to evaluate code
        exec(sys.argv[sys.argv.index("-c") + 1])

    elif "webview" in sys.argv:
        # Run webviews as subprocesses since Qt doesn't like threading
        import json
        from modules import webview
        i = sys.argv.index("webview")
        cb = getattr(webview, sys.argv[i + 1])
        args = json.loads(sys.argv[i + 2])
        kwargs = json.loads(sys.argv[i + 3])
        cb(*args, **kwargs)

    else:
        try:
            with lock_singleton() as locked:
                if not locked:
                    sys.exit(0)
                try:
                    main()
                except Exception:
                    if debug and release:
                        try:
                            from external import error
                            print(error.traceback())
                            input(f"Unhandled exception, press [Enter] to quit... ")
                        except Exception:
                            pass
                    else:
                        raise
        except KeyboardInterrupt:
            pass
