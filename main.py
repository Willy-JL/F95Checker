#!/usr/bin/env python
import contextlib
import pathlib
import sys
import os

version = "11.0"
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
    # Must be at the top
    import asyncio
    asyncio.run(resolve_tags_module())

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
                request.urlopen(request.Request(rpc_url + "/window/show", method="POST"))
            except Exception:
                pass


async def resolve_tags_module():
    import sys
    import aiohttp
    import pathlib
    import importlib.util
    if sys.platform.startswith("win"):
        cache_path = "AppData/Local/f95checker"
    elif sys.platform.startswith("linux"):
        cache_path = ".cache/f95checker"
    elif sys.platform.startswith("darwin"):
        cache_path = "Library/Caches/f95checker"
    else:
        return
    cache_path = pathlib.Path().home() / cache_path
    cache_path.mkdir(parents=True, exist_ok=True)
    fresh_module = cache_path / "tags.py"
    url = "https://raw.githubusercontent.com/r37r05p3C7/F95Checker/pull-fresh-tags/modules/tags.py"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    with open(fresh_module, 'wb') as f:
                        while True:
                            chunk = await response.content.read(1024)
                            if not chunk:
                                break
                            f.write(chunk)
                else:
                    return
        spec = importlib.util.spec_from_file_location("modules.tags", fresh_module)
        mod = importlib.util.module_from_spec(spec) # type: ignore
        sys.modules["modules.tags"] = mod
        spec.loader.exec_module(mod) # type: ignore
    except Exception:
        return


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    if "-c" in sys.argv:
        # Mimic python's -c flag to evaluate code
        exec(sys.argv[sys.argv.index("-c") + 1])

    elif "webview" in sys.argv:
        # Run webviews as subprocesses since Qt doesn't like threading
        from modules import webview
        import json
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
                            from modules import error
                            print(error.traceback())
                            input(f"Unhandled exception, press [Enter] to quit... ")
                        except Exception:
                            pass
                    else:
                        raise
        except KeyboardInterrupt:
            pass
