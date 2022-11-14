#!/usr/bin/env python
import pathlib
import sys

version = "9.4.1"
is_release = False
build_number = 0
version_name = f"{version}{'' if is_release else ' beta'}{'' if is_release or not build_number else ' ' + str(build_number)}"
rpc_port = 57095

frozen = getattr(sys, "frozen", False)
self_path = pathlib.Path(sys.executable if frozen else __file__).parent

def main():
    # Must import globals first to fix load paths when frozen
    from modules import globals

    from modules.structs import Os
    try:  # Non essential, ignore errors
        if globals.os is Os.Windows:
            # Hide conhost if frozen or release
            if (globals.frozen or globals.is_release) and "nohide" not in sys.argv:
                import ctypes
                ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        else:
            # Install uvloop on MacOS and Linux
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
            if frozen or is_release:
                if "main" in sys.argv:
                    main()
                elif lock_singleton():
                    import subprocess
                    import os
                    with open(self_path / "log.txt", "wb") as log:
                        sys.exit(subprocess.call([sys.executable, *sys.argv, "main"], cwd=os.getcwd(), stdout=log, stderr=subprocess.STDOUT))
            elif lock_singleton():
                main()
        except KeyboardInterrupt:
            pass
