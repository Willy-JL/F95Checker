#!/usr/bin/env python
from common import meta
from modules import patches

import asyncio
import contextlib
import sys


def main():
    from modules import globals

    from common.structs import Os
    if globals.os is not Os.Windows:
        # Faster eventloop, non essential so ignore errors
        try:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
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
                request.urlopen(request.Request(meta.rpc_url + "/window/show", method="POST"))
            except Exception:
                pass


def get_subprocess_args(subprocess_type: str):
    import json
    i = sys.argv.index(subprocess_type)
    args = json.loads(sys.argv[i + 1])
    kwargs = json.loads(sys.argv[i + 2])
    return args, kwargs


def _start():
    patches.apply()

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
                    if meta.debug and meta.release:
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


if __name__ == "__main__":
    _start()
