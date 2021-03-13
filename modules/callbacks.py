import os
import glob
import aiohttp
import asyncio
from qasync import asyncSlot
from subprocess import Popen
from bs4 import BeautifulSoup
from functools import partial
from PyQt5 import QtWidgets, QtCore, QtGui
from modules import globals, config_utils, gui, browsers, api


# Cleanup, save window size and exit
async def exit_handler():
    file_list = glob.glob('temp/f95checker*.html')
    for item in file_list:
        try:
            os.remove(item)
        except:
            pass
    try:
        os.rmdir('temp')
    except:
        pass

    globals.config["options"]["width"] = globals.gui.size().width()
    globals.config["options"]["height"] = globals.gui.size().height()
    config_utils.save_config()

    try:
        await globals.http.close()
    except:
        pass


@asyncSlot()
async def remove_game(name, *kw):
    count = 0
    while name in globals.config["game_list"]:
        globals.config["game_list"].remove(name)
        count += 1
    if not globals.config["game_data"][name]["version"]:
        del globals.config["game_data"][name]
    config_utils.save_config()
    globals.gui.games_layout.removeWidget(globals.gui.game_list[name])
    globals.gui.game_list[name].setVisible(False)
    del globals.gui.game_list[name]
    for i, item in enumerate(globals.config["game_list"]):
        globals.gui.game_list[item].update_details(alt=True if (i % 2) == 0 else False)
    if count > 1:
        await sort_games()


# Convert thread ids to names
async def id_to_name(code):
    try:
        async with globals.http.get(f'https://f95zone.to/threads/{code}/') as req:
            html = BeautifulSoup(await req.read(), 'html.parser')
    except aiohttp.ClientConnectorError:
        await gui.WarningPopup.open(globals.gui, "Can't connect!", "There was an error connecting to F95Zone, please check your internet connection!")
        return None
    if await api.check_f95zone_error(html, warn=True):
        return None
    try:
        title = html.select('h1[class="p-title-value"]')[0].get_text()
    except IndexError:
        await gui.WarningPopup.open(globals.gui, "Error!", "Couldn't find that game, make sure you pasted the right link!")
        return None
    while not title.find('[') == -1:
        title = title[0:title.find('[')] + title[title.find(']')+1:]
    while title[0] == ' ' or title[0] == ' ':
        title = title[1:]
    while title[-1] == ' ' or title[-1] == ' ':
        title = title[:-1]
    return title


@asyncSlot()
async def add_game(*kw):
    # Grab input text
    name = globals.gui.add_input.text()
    if name:
        globals.gui.add_input.setEnabled(False)
        globals.gui.add_button.setEnabled(False)
        # Convert ids and links to names
        if name.isdigit():
            name = await id_to_name(name)
        if name[0:27] == 'https://f95zone.to/threads/':
            name = name[name.rfind('.')+1:name.rfind('/')]
            name = await id_to_name(name)
        if name is None:
            globals.gui.add_input.setEnabled(True)
            globals.gui.add_button.setEnabled(True)
            return
        globals.gui.add_input.clear()
        # Config
        if name in globals.config["game_list"]:
            globals.gui.add_input.setEnabled(True)
            globals.gui.add_button.setEnabled(True)
            await gui.WarningPopup.open(globals.gui, 'Error!', f'{name} is already in your games list!')
            globals.gui.add_input.setFocus()
        else:
            globals.config["game_list"].append(name)

            config_utils.ensure_game_data(name)

            # Create and configure gui container
            globals.gui.game_list[name] = gui.GameContainer(alt=True if (len(globals.config["game_list"]) % 2) == 1 else False)
            globals.gui.games_layout.addWidget(globals.gui.game_list[name])
            globals.gui.game_list[name].update_details(name=name,
                                                       status=globals.config["game_data"][name]["status"],
                                                       version=globals.config["game_data"][name]["version"],
                                                       highlight=not globals.config["game_data"][name]["played"],
                                                       link=globals.config["game_data"][name]["link"])
            globals.gui.game_list[name].open_button.clicked.connect(partial(open_game, name))
            globals.gui.game_list[name].name.mousePressEvent = partial(invoke_changelog, name)
            globals.gui.game_list[name].installed_button.setChecked(globals.config["game_data"][name]["installed"])
            globals.gui.game_list[name].installed_button.stateChanged.connect(partial(set_installed, name))
            globals.gui.game_list[name].played_button.setChecked(globals.config["game_data"][name]["played"])
            globals.gui.game_list[name].played_button.stateChanged.connect(partial(set_played, name))
            globals.gui.game_list[name].remove_button.clicked.connect(partial(remove_game, name))
            if not globals.config["game_data"][name]["installed"]:
                globals.config["game_data"][name]["played"] = False
                globals.config["game_data"][name]["exe_path"] = ''
                globals.gui.game_list[name].played_button.setChecked(False)
                globals.gui.game_list[name].played_button.setEnabled(False)
                globals.gui.game_list[name].open_button.setEnabled(False)
                globals.gui.game_list[name].update_details(highlight=True)
            else:
                globals.gui.game_list[name].played_button.setEnabled(True)
                globals.gui.game_list[name].open_button.setEnabled(True)
            config_utils.save_config()

            visible = globals.gui.edit_button.text() == "Done"
            globals.gui.game_list[name].remove_button.setVisible(visible)

            # Set focus to input box and scroll to bottom
            globals.gui.add_input.setEnabled(True)
            globals.gui.add_button.setEnabled(True)
            globals.gui.add_input.setFocus()
            QtCore.QTimer.singleShot(100, lambda: globals.gui.games_section.verticalScrollBar().setSliderPosition(globals.gui.games_section.verticalScrollBar().maximum()))


@asyncSlot()
async def set_browser(new_browser, *kw):
    for browser_name in browsers.BROWSER_LIST:
        if globals.gui.browser_buttons.get(browser_name):
            globals.gui.browser_buttons[browser_name].setObjectName(u"browser_button_selected" if browser_name == new_browser else u"browser_button")
            globals.gui.browser_buttons[browser_name].setStyleSheet("/* /")
    globals.config["options"]["browser"] = new_browser
    config_utils.save_config()


@asyncSlot()
async def set_private_browser(*kw):
    globals.config["options"]["private_browser"] = globals.gui.private_button.isChecked()
    config_utils.save_config()


@asyncSlot()
async def set_html(*kw):
    globals.config["options"]["open_html"] = globals.gui.saved_html_button.isChecked()
    config_utils.save_config()


@asyncSlot()
async def set_refresh(*kw):
    globals.config["options"]["start_refresh"] = globals.gui.start_refresh_button.isChecked()
    config_utils.save_config()


@asyncSlot()
async def set_sorting(*kw):
    i = globals.gui.sort_input.currentIndex()
    if i == 0:
        globals.config["options"]["auto_sort"] = 'none'
    elif i == 1:
        globals.config["options"]["auto_sort"] = 'last_updated'
    elif i == 2:
        globals.config["options"]["auto_sort"] = 'first_added'
    elif i == 3:
        globals.config["options"]["auto_sort"] = 'alphabetical'
    config_utils.save_config()
    await sort_games()


# Sort game view and config
async def sort_games():
    if globals.config["options"]["auto_sort"] == 'last_updated':
        sorting = []
        for item in globals.config["game_list"]:
            sorting.append(item)
        sorting.sort(key=lambda x: globals.config["game_data"][x]["updated_time"], reverse=True)
        globals.config["game_list"] = []
        for item in sorting:
            globals.config["game_list"].append(item)
    elif globals.config["options"]["auto_sort"] == 'first_added':
        sorting = []
        for item in globals.config["game_list"]:
            sorting.append(item)
        sorting.sort(key=lambda x: globals.config["game_data"][x]["updated_time"])
        globals.config["game_list"] = []
        for item in sorting:
            globals.config["game_list"].append(item)
    elif globals.config["options"]["auto_sort"] == 'alphabetical':
        sorting = []
        for item in globals.config["game_list"]:
            sorting.append(item)
        sorting.sort()
        globals.config["game_list"] = []
        for item in sorting:
            globals.config["game_list"].append(item)
    else:
        return
    config_utils.save_config()
    for item in globals.gui.game_list:
        globals.gui.games_layout.removeWidget(globals.gui.game_list[item])
    for i, item in enumerate(globals.config["game_list"]):
        globals.gui.games_layout.insertWidget(i, globals.gui.game_list[item])
        globals.gui.game_list[item].update_details(alt=True if (i % 2) == 0 else False)


@asyncSlot()
async def set_max_retries(*kw):
    globals.config["options"]["max_retries"] = globals.gui.retries_input.value()
    config_utils.save_config()


@asyncSlot()
async def set_refresh_threads(*kw):
    globals.config["options"]["refresh_threads"] = globals.gui.threads_input.value()
    config_utils.save_config()


@asyncSlot()
async def restore_default_style(*kw):
    globals.config["style"] = {
        'back': '#181818',
        'alt': '#141414',
        'accent': '#da1e2e',
        'border': '#454545',
        'hover': '#747474',
        'disabled': '#232323',
        'radius': 6
    }
    update_style()


# Refresh gui with new style
def update_style(style_id=None):
    # Config
    if style_id == 'radius':
        globals.config["style"][style_id] = globals.gui.style_gui.radius.value()
    elif style_id:
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(globals.config["style"][style_id]))
        if color.isValid():
            globals.config["style"][style_id] = f'#{hex(color.rgb())[4:]}'
    config_utils.save_config()
    # Update gui style
    globals.app.setStyleSheet(globals.gui.get_stylesheet(globals.config["style"]))
    if not style_id:
        globals.gui.style_gui.radius.setValue(globals.config["style"]["radius"])


@asyncSlot()
async def invoke_styler(*kw):
    globals.gui.style_gui = gui.StyleGUI()
    globals.gui.style_gui.radius.setValue(globals.config["style"]["radius"])
    # Assign click actions
    globals.gui.style_gui.background.clicked.connect(partial(update_style, 'back'))
    globals.gui.style_gui.alternate.clicked.connect(partial(update_style, 'alt'))
    globals.gui.style_gui.accent.clicked.connect(partial(update_style, 'accent'))
    globals.gui.style_gui.border.clicked.connect(partial(update_style, 'border'))
    globals.gui.style_gui.hover.clicked.connect(partial(update_style, 'hover'))
    globals.gui.style_gui.disabled.clicked.connect(partial(update_style, 'disabled'))
    globals.gui.style_gui.radius.valueChanged.connect(partial(update_style, 'radius'))
    globals.gui.style_gui.restore.clicked.connect(restore_default_style)
    # Show window
    globals.gui.style_gui.show()


@asyncSlot()
async def set_delay(*kw):
    globals.config["options"]["bg_mode_delay_mins"] = globals.gui.bg_refresh_input.value()
    config_utils.save_config()


def invoke_changelog(name, *kw):
    globals.gui.changelog_gui = gui.ChangelogGUI()
    globals.gui.changelog_gui.setWindowTitle(QtCore.QCoreApplication.translate("Form", u"Changelog for {}".format(name), None))
    globals.gui.changelog_gui.text.setPlainText(globals.config["game_data"][name]["changelog"])
    globals.gui.changelog_gui.show()


@asyncSlot()
async def set_installed(name, *kw):
    globals.config["game_data"][name]["installed"] = globals.gui.game_list[name].installed_button.isChecked()
    if not globals.config["game_data"][name]["installed"]:
        globals.config["game_data"][name]["played"] = False
        globals.config["game_data"][name]["exe_path"] = ''
        globals.gui.game_list[name].played_button.setChecked(False)
        globals.gui.game_list[name].played_button.setEnabled(False)
        globals.gui.game_list[name].open_button.setEnabled(False)
        globals.gui.game_list[name].update_details(highlight=True)
    else:
        globals.gui.game_list[name].played_button.setEnabled(True)
        globals.gui.game_list[name].open_button.setEnabled(True)
    config_utils.save_config()
    globals.gui.game_list[name].update_details(highlight=not globals.config["game_data"][name]["played"])


@asyncSlot()
async def set_played(name, *kw):
    globals.config["game_data"][name]["played"] = globals.gui.game_list[name].played_button.isChecked()
    config_utils.save_config()
    globals.gui.game_list[name].update_details(highlight=not globals.config["game_data"][name]["played"])


@asyncSlot()
async def toggle_edit_mode(*kw):
    visible = not globals.gui.edit_button.text() == "Done"
    for item in globals.gui.game_list:
        globals.gui.game_list[item].remove_button.setVisible(visible)
    if visible:
        globals.gui.edit_button.setText(QtCore.QCoreApplication.translate("F95Checker", u"Done", None))
    else:
        globals.gui.edit_button.setText(QtCore.QCoreApplication.translate("F95Checker", u"Edit", None))


def hide_all_context_menus():
    globals.tray.idle_menu.hide()
    globals.tray.paused_menu.hide()
    globals.tray.refresh_menu.hide()
    globals.tray.paused_refresh_menu.hide()


@asyncSlot()
async def toggle_background(*kw):
    if globals.mode == 'gui':
        globals.gui.hide()
        globals.tray.show()
        globals.mode = 'tray'
        globals.bg_paused = False
        globals.tray.bg_loop_task = asyncio.create_task(bg_loop())
    else:
        if globals.tray.bg_loop_task:
            globals.tray.bg_loop_task.cancel()
            globals.tray.bg_loop_task = None
        globals.gui.show()
        globals.tray.hide()
        globals.mode = 'gui'


async def bg_loop():
    while True:
        hide_all_context_menus()
        globals.tray.setContextMenu(globals.tray.refresh_menu)
        globals.tray.setIcon(globals.tray.refresh_icon)
        await refresh()
        hide_all_context_menus()
        globals.tray.setContextMenu(globals.tray.idle_menu)
        globals.tray.setIcon(globals.tray.idle_icon)
        await asyncio.sleep(globals.config["options"]["bg_mode_delay_mins"] * 60)


@asyncSlot()
async def bg_toggle_pause(*kw):
    if globals.bg_paused:
        globals.bg_paused = False
        globals.tray.bg_loop_task = asyncio.create_task(bg_loop())
        hide_all_context_menus()
        globals.tray.setContextMenu(globals.tray.idle_menu)
        globals.tray.setIcon(globals.tray.idle_icon)
    else:
        globals.bg_paused = True
        globals.tray.bg_loop_task.cancel()
        globals.tray.bg_loop_task = None
        hide_all_context_menus()
        globals.tray.setContextMenu(globals.tray.paused_menu)
        globals.tray.setIcon(globals.tray.paused_icon)


def open_game(name, event):
    if not globals.config["game_data"][name]["exe_path"]:
        globals.config["game_data"][name]["exe_path"] = QtWidgets.QFileDialog.getOpenFileName(globals.gui, f'Select game executable file for {name}', filter="Game exe (*.exe *.py *.sh *.bat)")[0]
        config_utils.save_config()
    if globals.config["game_data"][name]["exe_path"]:
        if event.button() == QtCore.Qt.LeftButton:
            Popen([globals.config["game_data"][name]["exe_path"]])
        elif event.button() == QtCore.Qt.RightButton and globals.user_os == "windows":
            path = globals.config["game_data"][name]["exe_path"]
            path = path[:path.rfind("/")].replace("/", "\\")
            Popen(["explorer.exe", path])


@asyncSlot()
async def refresh(*kw):
    if globals.refreshing and globals.mode == 'tray':
        while globals.refreshing:
            await asyncio.sleep(0.25)
        return
    if globals.refreshing:
        return
    globals.refreshing = True
    globals.warned_connection = False
    globals.updated_games = []
    globals.gui.refresh_bar.setVisible(True)
    globals.gui.refresh_label.setVisible(True)
    if globals.gui.edit_button.text() == "Done":
        await toggle_edit_mode()
    globals.gui.edit_button.setEnabled(False)
    globals.gui.add_input.setEnabled(False)
    globals.gui.add_button.setEnabled(False)

    refresh_tasks = asyncio.Queue()
    for game in globals.config["game_list"]:
        refresh_tasks.put_nowait(api.check(game))
    refresh_tasks.put_nowait(api.check_notifs())
    if not globals.checked_updates:
        refresh_tasks.put_nowait(api.check_for_updates())
    globals.gui.refresh_bar.setMaximum(len(globals.config["game_list"])+1)
    globals.gui.refresh_bar.setValue(1)

    async def worker():
        while not refresh_tasks.empty():
            await refresh_tasks.get_nowait()

    if not globals.logged_in:
        await api.login()
    globals.gui.refresh_bar.setValue(2)

    if globals.logged_in:
        try:
            await asyncio.gather(*[worker() for _ in range(globals.config["options"]["refresh_threads"])])
        except:
            pass

    globals.gui.refresh_bar.setVisible(False)
    globals.gui.refresh_label.setVisible(False)
    globals.gui.edit_button.setEnabled(True)
    globals.gui.add_input.setEnabled(True)
    globals.gui.add_button.setEnabled(True)
    await sort_games()
    if globals.updated_games:
        details = ''
        ignored = 0
        for entry in globals.updated_games:
            if entry["old_version"]:
                details += f'{entry["name"]}:\n{entry["old_version"]}   ->  {entry["new_version"]}\n\n'
            else:
                ignored += 1
        if details:
            details = details[:-2]
            await gui.InfoPopup.open(globals.gui, 'Updates', f'{len(globals.updated_games)-ignored} game{"" if (len(globals.updated_games)-ignored) == 1 else "s"} {"has" if (len(globals.updated_games)-ignored) == 1 else "have"} been updated:\n\n{details}')
    globals.refreshing = False


async def refresh_helper():
    await refresh()
