import os
import sys
import json
import asyncio
import pathlib
import tkinter as tk
import tkinter.messagebox
from functools import partial


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
globals.version = '7.0'
globals.login_url = "https://f95zone.to/login/login"
globals.search_url = "https://f95zone.to/quicksearch"
globals.notif_url = "https://f95zone.to/conversations/popup"
globals.logged_in = False
globals.logging_in = False
globals.checked_updates = False
globals.refreshing = False


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
        config_utils.migrate_legacy()


# Populate interface
def setup_interface():
    # Game List section
    globals.gui.add_button.clicked.connect(callbacks.add_game)
    globals.gui.add_input.returnPressed.connect(callbacks.add_game)
    for i, game in enumerate(globals.config["game_list"]):
        config_utils.ensure_game_data(game)

        globals.gui.game_list[game] = gui.GameContainer(alt=True if (i % 2) == 0 else False)
        globals.gui.games_layout.addWidget(globals.gui.game_list[game])
        globals.gui.game_list[game].update_details(name=game,
                                                   status=globals.config["game_data"][game]["status"],
                                                   version=globals.config["game_data"][game]["version"],
                                                   highlight=not globals.config["game_data"][game]["played"],
                                                   link=globals.config["game_data"][game]["link"])
        globals.gui.game_list[game].open_button.mousePressEvent = partial(callbacks.open_game, game)
        globals.gui.game_list[game].name.mousePressEvent = partial(callbacks.invoke_changelog, game)
        globals.gui.game_list[game].installed_button.setChecked(globals.config["game_data"][game]["installed"])
        globals.gui.game_list[game].installed_button.stateChanged.connect(partial(callbacks.set_installed, game))
        globals.gui.game_list[game].played_button.setChecked(globals.config["game_data"][game]["played"])
        globals.gui.game_list[game].played_button.stateChanged.connect(partial(callbacks.set_played, game))
        globals.gui.game_list[game].remove_button.clicked.connect(partial(callbacks.remove_game, game))
        if not globals.config["game_data"][game]["installed"]:
            globals.config["game_data"][game]["played"] = False
            globals.config["game_data"][game]["exe_path"] = ''
            globals.gui.game_list[game].played_button.setChecked(False)
            globals.gui.game_list[game].played_button.setEnabled(False)
            globals.gui.game_list[game].open_button.setEnabled(False)
            globals.gui.game_list[game].update_details(highlight=True)
        else:
            globals.gui.game_list[game].played_button.setEnabled(True)
            globals.gui.game_list[game].open_button.setEnabled(True)
        config_utils.save_config()

    # Refresh Button
    globals.gui.refresh_button.clicked.connect(callbacks.refresh)

    # Browsers Buttons
    for btn in globals.gui.browser_buttons:
        globals.gui.browser_buttons[btn].setEnabled(False)
        if globals.user_browsers.get(btn):
            globals.gui.browser_buttons[btn].setEnabled(True)
            globals.gui.browser_buttons[btn].clicked.connect(partial(callbacks.set_browser, btn))
    if globals.config["options"]["browser"]:
        globals.gui.browser_buttons[globals.config["options"]["browser"]].setObjectName(u"browser_button_selected")
        globals.gui.browser_buttons[globals.config["options"]["browser"]].setStyleSheet("/* /")

    # Check Boxes
    if globals.config["options"]["private_browser"]:
        globals.gui.private_button.setChecked(True)
    globals.gui.private_button.stateChanged.connect(callbacks.set_private_browser)

    if globals.config["options"]["start_refresh"]:
        globals.gui.start_refresh_button.setChecked(True)
    globals.gui.start_refresh_button.stateChanged.connect(callbacks.set_refresh)

    if globals.config["options"]["open_html"]:
        globals.gui.saved_html_button.setChecked(True)
    globals.gui.saved_html_button.stateChanged.connect(callbacks.set_html)

    # Sorting
    globals.gui.sort_input.setCurrentIndex(1 if globals.config["options"]["auto_sort"] == 'last_updated' else 2 if globals.config["options"]["auto_sort"] == 'first_added' else 3 if globals.config["options"]["auto_sort"] == 'alphabetical' else 0)
    globals.gui.sort_input.currentIndexChanged.connect(callbacks.set_sorting)

    # Spin Boxes
    globals.gui.retries_input.setValue(globals.config["options"]["max_retries"])
    globals.gui.retries_input.valueChanged.connect(callbacks.set_max_retries)

    globals.gui.bg_refresh_input.setValue(globals.config["options"]["bg_mode_delay_mins"])
    globals.gui.bg_refresh_input.valueChanged.connect(callbacks.set_delay)

    # Buttons
    globals.gui.color_button.clicked.connect(callbacks.invoke_styler)

    globals.gui.edit_button.clicked.connect(callbacks.toggle_edit_mode)

    # globals.gui.background_button.clicked.connect()
    globals.gui.background_button.setEnabled(False)
    globals.gui.background_button.setToolTip("Coming soon...")

    # Watermark
    if "tester" in globals.version:
        globals.gui.watermark.setText(QtCore.QCoreApplication.translate("F95Checker", u"F95Checker Tester Build", None))
    else:
        globals.gui.watermark.setText(QtCore.QCoreApplication.translate("F95Checker", u"F95Checker v{} by WillyJL".format(globals.version), None))
    globals.gui.watermark.mousePressEvent = partial(browsers.open_webpage_sync_helper, 'https://f95zone.to/threads/44173/')


if __name__ == '__main__':

    # Create App
    globals.app = QtWidgets.QApplication(sys.argv)

    # Configure asyncio loop to work with PyQt
    loop = QEventLoop(globals.app)
    asyncio.set_event_loop(loop)
    globals.loop = asyncio.get_event_loop()

    # Make aiohttp global session
    async def make_aiohttp_session():
        globals.http = aiohttp.ClientSession(headers={"user-agent": globals.config["advanced"]["user_agent"]},
                                             loop=globals.loop,
                                             timeout=aiohttp.ClientTimeout(sock_read=5.0))
    globals.loop.run_until_complete(make_aiohttp_session())


    # Setup main GUI
    globals.gui = gui.F95Checker_GUI()
    globals.app.setStyleSheet(globals.gui.get_stylesheet(globals.config["style"]))
    globals.gui.setWindowIcon(QtGui.QIcon('resources/icons/icon.ico' if globals.user_os == "windows" else 'resources/icons/icon.png'))
    globals.gui.resize(globals.config["options"]["width"], globals.config["options"]["height"])

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
