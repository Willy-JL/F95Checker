#!/usr/bin/env python
import contextlib
import pathlib
import sys

version = "9.6.4"
release = False
build_number = 0
version_name = f"{version}{'' if release else ' beta'}{'' if release or not build_number else ' ' + str(build_number)}"
rpc_port = 57095

frozen = getattr(sys, "frozen", False)
self_path = pathlib.Path(sys.executable if frozen else __file__).parent
debug = not (frozen or release)


def main():
    # Must import globals first to fix load paths when frozen
    from modules import globals

    from modules.structs import Os
    try:
        # Install uvloop on MacOS and Linux, non essential so ignore errors
        if globals.os is not Os.Windows:
            import uvloop
            uvloop.install()
    except Exception:
        pass

    from modules import async_thread, sync_thread
    async_thread.setup()
    sync_thread.setup()

    from modules import db, api
    with db.setup(), api.setup():

        from modules import gui
        globals.gui = gui.MainGUI()

        from modules import rpc_thread
        with rpc_thread.setup():

            globals.gui.main_loop()


@contextlib.contextmanager
def lock_singleton():
    from modules import singleton
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
                request.urlopen(request.Request(f"http://localhost:{rpc_port}/window/show", method="POST"))
            except Exception:
                pass


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    if "-c" in sys.argv:
        # Mimic python's -c flag to evaluate code
        exec(sys.argv[sys.argv.index("-c") + 1])

    else:
        try:
            if "main" in sys.argv:
                main()
                sys.exit(0)

            with lock_singleton() as locked:
                if not locked:
                    sys.exit(0)
                with (self_path / "log.txt").open("wb", buffering=0) as log:
                    stream = None if debug else log  # Don't redirect in debug mode
                    import subprocess
                    import os
                    ret = subprocess.call(
                        [
                            sys.executable,
                            *sys.argv,
                            "main"
                        ],
                        env={
                            **os.environ,
                            "PYTHONUNBUFFERED": "1"
                        },
                        cwd=os.getcwd(),
                        stdout=stream,
                        stderr=stream,
                        bufsize=0
                    )
                    if debug and release:
                        try:
                            input(f"Exited with code {ret}, press [Enter] to quit... ")
                        except Exception:
                            pass
                    sys.exit(ret)
        except KeyboardInterrupt:
            pass
