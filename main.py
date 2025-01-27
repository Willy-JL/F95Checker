#!/usr/bin/env python
import asyncio
import contextlib
import os
import pathlib
import subprocess
import sys

version = "11.1"
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
        # Install uvloop on Linux and Rubicon-ObjC on MacOS, non essential so ignore errors
        if globals.os is Os.Linux:
            # Faster eventloop
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            # Disable coredumps, desktop-notifier with uvloop segfaults at app exit
            subprocess.Popen(["prlimit", "--core=0", "--pid", str(os.getpid())])
        elif globals.os is Os.MacOS:
            # Needed for desktop-notifier
            import rubicon.objc.eventloop as crloop
            asyncio.set_event_loop_policy(crloop.EventLoopPolicy())
    except Exception:
        pass

    from external import async_thread, sync_thread
    async_thread.setup()
    sync_thread.setup()

    from modules import api, db
    with db.setup(), api.setup():

        from modules import gui
        globals.gui = gui.MainGUI()

        from modules import notification_proc, rpc_thread
        with notification_proc.setup(), rpc_thread.setup():

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


def get_subprocess_args(subprocess_type: str):
    import json
    i = sys.argv.index(subprocess_type)
    args = json.loads(sys.argv[i + 1])
    kwargs = json.loads(sys.argv[i + 2])
    return args, kwargs


if __name__ == "__main__":
    if "-c" in sys.argv:
        # Mimic python's -c flag to evaluate code
        exec(sys.argv[sys.argv.index("-c") + 1])

    elif "webview-daemon" in sys.argv:
        # Run webviews as subprocesses since Qt doesn't like threading
        args, kwargs = get_subprocess_args("webview-daemon")
        from modules import webview
        webview_action = getattr(webview, args.pop(0))
        webview_action(*args, **kwargs)

    elif "notification-daemon" in sys.argv:
        # Run notifications as subprocesses since desktop-notifier doesn't like threading
        args, kwargs = get_subprocess_args("notification-daemon")
        from modules import notification_proc
        notification_proc.daemon(*args, **kwargs)

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
