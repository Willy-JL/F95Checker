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
if sys.platform.startswith("darwin"):
    debug_file = open(pathlib.Path.home() / "Desktop/f95checker-test.txt", "a")
else:
    import io
    debug_file = io.StringIO()
debug_file.write("\n\n\ninit\n")


def main():
    debug_file.write("main\n")
    # Must import globals first to fix load paths when frozen
    from modules import globals
    debug_file.write("globals\n")

    from modules.structs import Os
    if globals.os is not Os.Windows:
        import uvloop
        uvloop.install()
    debug_file.write("uvloop\n")

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
    debug_file.write("singleton\n")

    if globals.frozen:
        from modules import logger
        logger.install(path=globals.self_path / "log.txt", lowlevel=True)
    debug_file.write("logger\n")

    from modules import async_thread, sync_thread
    async_thread.setup()
    sync_thread.setup()
    debug_file.write("threads\n")

    from modules import db
    async_thread.wait(db.connect())
    async_thread.wait(db.load())
    async_thread.run(db.save_loop())
    debug_file.write("database\n")

    from modules import api
    api.setup()
    debug_file.write("api\n")

    from modules import gui
    globals.gui = gui.MainGUI()
    debug_file.write("gui\n")

    from modules import rpc_thread
    rpc_thread.start()
    debug_file.write("rpc\n")

    globals.gui.main_loop()
    debug_file.write("after mainloop\n")

    async_thread.wait(db.close())
    async_thread.wait(api.shutdown())
    debug_file.write("shutdown\n")

    for file in pathlib.Path(tempfile.gettempdir()).glob("F95Checker-Temp-*"):
        try:
            file.unlink()
        except Exception:
            pass
    debug_file.write("cleanup\n")


if __name__ == "__main__":
    if "-c" in sys.argv:
        # Mimic python's -c flag to evaluate code
        exec(sys.argv[sys.argv.index("-c") + 1])
    elif "asklogin" in sys.argv:
        from modules import asklogin
        asklogin.asklogin(sys.argv[sys.argv.index("asklogin") + 1])
    else:
        main()
