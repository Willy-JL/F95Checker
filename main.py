#!/usr/bin/env python
import pathlib
import sys

version = "9.4.1"
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

        if globals.settings.rpc_enabled:
            from modules import rpc_thread
            rpc_thread.start()

        globals.gui.main_loop()


def lock_singleton():
    from modules import singleton
    try:
        singleton.lock("F95Checker")
        return True
    except RuntimeError:
        import xmlrpc.client
        try:
            with xmlrpc.client.ServerProxy(f"http://localhost:{rpc_port}/", allow_none=True) as proxy:
                proxy.show_window()
        except Exception:
            pass
        return False


if __name__ == "__main__":
    if "-c" in sys.argv:
        # Mimic python's -c flag to evaluate code
        exec(sys.argv[sys.argv.index("-c") + 1])
    else:
        try:
            if "main" in sys.argv:
                main()
            elif lock_singleton():
                with open(self_path / "log.txt", "wb", buffering=0) as log:
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
                    if debug:
                        try:
                            input(f"Exited with code {ret}, press [Enter] to quit... ")
                        except Exception:
                            pass
                    sys.exit(ret)
        except KeyboardInterrupt:
            pass
