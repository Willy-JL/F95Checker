from functools import partial
import tkinter.messagebox
import tkinter as tk
import pathlib
import asyncio
import json
import sys
import os


# Handle dependencies import
try:
    import aiohttp
    from bs4 import BeautifulSoup
    from PyQt5 import QtWidgets, QtGui, QtCore
    from qasync import QEventLoop, asyncSlot, asyncClose

    from modules import api, callbacks, gui
except ModuleNotFoundError as e:
    # Dependencies not found, prompt to install and exit
    root = tk.Tk()
    root.withdraw()
    tk.messagebox.showerror('Error!', f'Some required dependencies were not found. Please install them manually using the command "pip install --upgrade -r requirements.txt"\n\nError:\n{e}')
    root.destroy()
    del root
    sys.exit()
except ImportError as e:
    # Dependencies failed, prompt to install and exit
    root = tk.Tk()
    root.withdraw()
    tk.messagebox.showerror('Error!', f'Somemething went wrong importing dependencies. Please install them manually using the command "pip install --upgrade -r requirements.txt"\n\nError:\n{e}')
    root.destroy()
    del root
    sys.exit()


# Setup Globals
from modules import globals
globals.version = '8.2dev1'

globals.domain            = "https://f95zone.to"
globals.check_login_page  = globals.domain +  "/account/"
globals.login_page        = globals.domain +  "/login/"
globals.login_endpoint    = globals.domain +  "/login/login"
globals.two_step_endpoint = globals.domain +  "/login/two-step"
globals.notif_endpoint    = globals.domain +  "/conversations/popup"
globals.qsearch_endpoint  = globals.domain +  "/quicksearch"
globals.alerts_page       = globals.domain +  "/account/alerts/"
globals.inbox_page        = globals.domain +  "/conversations/"
globals.tool_page         = globals.domain +  "/threads/44173/"

globals.logged_in       = False
globals.logging_in      = False
globals.checked_updates = False
globals.refreshing      = False


# OS Handling
from modules import browsers
try:
    globals.exec_type, globals.user_os, globals.user_browsers = browsers.detect_user_os_and_browsers()
    if globals.user_os == "windows":
        globals.config_path = os.path.expanduser("~/AppData/Roaming/f95checker")
    elif globals.user_os == "linux":
        globals.config_path = os.path.expanduser("~/.f95checker")
except OSError:
    root = tk.Tk()
    root.withdraw()
    tk.messagebox.showerror('Compatibility',
                            "F95Checker currently is not compatible with your OS. Please let me know in the tool " +
                            "thread if you want it to be supported! Or if you think you\'re up to the task feel " +
                            "free to try to make it compatible editing the python file and let me know your results.")
    root.destroy()
    del root
    sys.exit()


from modules import singleton
try:
    globals.singleton = singleton.Singleton("F95Checker")
except RuntimeError as exc:
    print(exc)
    root = tk.Tk()
    root.withdraw()
    tk.messagebox.showerror('Already running!', str(exc))
    root.destroy()
    del root
    sys.exit()


# Handle config
from modules import config_utils
pathlib.Path(globals.config_path).mkdir(parents=True, exist_ok=True)
try:
    with open(f'{globals.config_path}/f95checker.json', 'r') as f:
        try:
            globals.config = json.load(f)
            config_utils.init_config()
        except json.JSONDecodeError:
            root = tk.Tk()
            root.withdraw()
            tk.messagebox.showerror('Invalid config!', "Something went wrong with your config file, it might have gotten corrupted...\nClick ok to generate a new empty cconfig")
            root.destroy()
            del root
            globals.config = {}
            config_utils.init_config()
except FileNotFoundError:
    globals.config = {}
    config_utils.init_config()
    if os.path.isfile(f'{globals.config_path}/config.ini'):
        config_utils.migrate_legacy("pre7.0")


def setup_interface():
    """Populate interface with game entries"""
    for i, game_id in enumerate(globals.config["games"]):
        globals.gui.game_list[game_id] = gui.GameContainer(game_id, alt=True if (i % 2) == 0 else False)
        globals.gui.games_layout.addWidget(globals.gui.game_list[game_id])


if __name__ == '__main__':

    # Create App
    globals.app = QtWidgets.QApplication(sys.argv)
    globals.app.setQuitOnLastWindowClosed(False)

    # Configure asyncio loop to work with PyQt
    loop = QEventLoop(globals.app)
    asyncio.set_event_loop(loop)
    globals.loop = asyncio.get_event_loop()

    async def make_aiohttp_session():
        """Make aiohttp global session"""
        globals.http = aiohttp.ClientSession(headers={"user-agent": globals.config["advanced"]["user_agent"]},
                                             loop=globals.loop,
                                             timeout=aiohttp.ClientTimeout(sock_read=5.0),
                                             connector=aiohttp.TCPConnector(limit=0),
                                             cookies=globals.config["advanced"]["cookies"])
    globals.loop.run_until_complete(make_aiohttp_session())
    globals.image_semaphore = asyncio.Semaphore(4)


    # Setup GUIs
    globals.settings = QtCore.QSettings("WillyJL", "F95Checker")
    globals.gui = gui.F95CheckerGUI()
    globals.app.setStyleSheet(globals.gui.get_stylesheet(globals.config["style"]))
    globals.tray = gui.F95CheckerTray(globals.gui)
    globals.mode = "gui"

    # Setup font awesome for icons
    QtGui.QFontDatabase.addApplicationFont("resources/fonts/Font Awesome 5 Free-Solid-900.otf")
    globals.font_awesome = QtGui.QFont('Font Awesome 5 Free Solid', 11)

    # Populate and configure interface items and callbacks
    setup_interface()

    # Queue start refresh task
    if globals.config["options"]["start_refresh"]:
        globals.loop.create_task(callbacks.refresh_helper())

    # Finally show GUI
    globals.gui.show()

    # Set off loop
    with globals.loop:
        sys.exit(globals.loop.run_forever())
