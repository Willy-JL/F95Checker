#!/usr/bin/env python
import sys


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

    from modules import singleton
    try:
        singleton.lock("F95Checker")
    except RuntimeError:
        import xmlrpc.client
        try:
            with xmlrpc.client.ServerProxy(f"http://localhost:{globals.rpc_port}/", allow_none=True) as proxy:
                proxy.show_window()
        except Exception:
            pass
        sys.exit(0)

    if globals.frozen or globals.is_release:
        from modules import logger
        logger.install(path=globals.self_path / "log.txt", lowlevel=True)

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


if __name__ == "__main__":
    if "-c" in sys.argv:
        # Mimic python's -c flag to evaluate code
        exec(sys.argv[sys.argv.index("-c") + 1])
    else:
        try:
            main()
        except KeyboardInterrupt:
            pass
