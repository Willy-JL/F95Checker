#!/usr/bin/env python
import sys
if sys.platform.startswith("win"):
    # Hide conhost if frozen
    import os
    import ctypes
    from win32 import win32process
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if win32process.GetWindowThreadProcessId(hwnd)[1] == os.getpid():
        ctypes.windll.user32.ShowWindow(hwnd, 0)
import tempfile
import pathlib


def main():
    # Must import globals first to fix load paths when frozen
    from modules import globals

    from modules.structs import Os
    if globals.os is not Os.Windows:
        try:
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

    if globals.frozen:
        from modules import logger
        logger.install(path=globals.self_path / "log.txt", lowlevel=True)

    from modules import async_thread, sync_thread
    async_thread.setup()
    sync_thread.setup()

    from modules import db
    async_thread.wait(db.connect())
    async_thread.wait(db.load())
    async_thread.run(db.save_loop())

    from modules import api
    api.setup()

    from modules import gui
    globals.gui = gui.MainGUI()

    from modules import rpc_thread
    rpc_thread.start()

    globals.gui.main_loop()

    async_thread.wait(db.close())
    async_thread.wait(api.shutdown())

    for file in pathlib.Path(tempfile.gettempdir()).glob("F95Checker-Temp-*"):
        try:
            file.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    if "-c" in sys.argv:
        # Mimic python's -c flag to evaluate code
        exec(sys.argv[sys.argv.index("-c") + 1])
    elif "asklogin" in sys.argv:
        from modules import asklogin
        asklogin.asklogin(sys.argv[sys.argv.index("asklogin") + 1])
    else:
        main()
