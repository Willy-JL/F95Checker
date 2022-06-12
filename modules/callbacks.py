import configparser
import subprocess
import tempfile
import plistlib
import pathlib
import shlex
import time
import stat
import bs4
import os

from modules.structs import Browser, Game, MsgBox, Os, ThreadMatch
from modules import globals, api, async_thread, db, filepicker, msgbox, utils


def update_start_with_system(toggle: bool):
    try:
        if toggle:
            if globals.os is Os.Windows:
                import winreg
                current_user = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                winreg.SetValue(current_user, globals.autostart, winreg.REG_SZ, globals.start_cmd)
            elif globals.os is Os.Linux:
                config = configparser.RawConfigParser()
                config.optionxform = lambda option: option
                config.add_section("Desktop Entry")
                config.set("Desktop Entry", "Name", "F95Checker")
                config.set("Desktop Entry", "Comment", "An update checker tool for (NSFW) games on the F95Zone platform")
                config.set("Desktop Entry", "Type", "Application")
                config.set("Desktop Entry", "Exec", globals.start_cmd)
                with globals.autostart.open("w") as fp:
                    config.write(fp, space_around_delimiters=False)
            elif globals.os is Os.MacOS:
                plist = {
                    "Label": "com.github.f95checker",
                    "ProgramArguments": shlex.split(globals.start_cmd),
                    "KeepAlive": True,
                    "OnDemand": False,
                    "RunAtLoad": True
                }
                with globals.autostart.open("wb") as fp:
                    plistlib.dump(plist, fp)
        else:
            if globals.os is Os.Windows:
                import winreg
                current_user = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                winreg.SetValue(current_user, globals.autostart, winreg.REG_SZ, "")
            elif globals.os is Os.Linux or globals.os is Os.MacOS:
                globals.autostart.unlink()
        globals.start_with_system = toggle
    except Exception:
        utils.push_popup(msgbox.msgbox, "Oops!", f"Something went wrong changing the start with system setting:\n\n{utils.get_traceback()}", MsgBox.error)


def _launch(path: str | pathlib.Path):
    exe = pathlib.Path(path).absolute()
    if not exe.is_file():
        raise FileNotFoundError()

    if globals.os is Os.Windows:
        # Open with default app
        os.startfile(str(exe))
    else:
        mode = exe.stat().st_mode
        executable = not (mode & stat.S_IEXEC < stat.S_IEXEC)
        if not executable:
            with exe.open("r") as f:
                if f.read(2) == "#!":
                    # Make executable if shebang is present
                    exe.chmod(mode | stat.S_IEXEC)
                    executable = True
        if (exe.parent / "renpy").is_dir():
            # Make all needed renpy libs executable
            for file in (exe.parent / "lib").glob("**/*"):
                if file.is_file() and not file.suffix:
                    mode = file.stat().st_mode
                    if mode & stat.S_IEXEC < stat.S_IEXEC:
                        file.chmod(mode | stat.S_IEXEC)
        if executable:
            # Run as executable
            subprocess.Popen(
                [
                    str(exe)
                ],
                cwd=str(exe.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Open with default app
            if globals.os is Os.Linux:
                open_util = "xdg-open"
            elif globals.os is Os.MacOS:
                open_util = "open"
            subprocess.Popen(
                [
                    open_util,
                    str(exe)
                ],
                cwd=str(exe.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )


def launch_game_exe(game: Game):
    def _launch_game():
        if not game.executable:
            return
        try:
            _launch(game.executable)
            game.last_played.update(time.time())
            async_thread.run(db.update_game(game, "last_played"))
        except FileNotFoundError:
            def reset_callback():
                game.executable = ""
                async_thread.run(db.update_game(game, "executable"))
            buttons = {
                "󰄬 Yes": reset_callback,
                "󰜺 No": None
            }
            utils.push_popup(msgbox.msgbox, "File not found!", "The selected executable could not be found.\n\nDo you want to unset the path?", MsgBox.warn, buttons)
        except Exception:
            utils.push_popup(msgbox.msgbox, "Oops!", f"Something went wrong launching {game.name}:\n\n{utils.get_traceback()}", MsgBox.error)
    if not game.executable:
        def select_callback(selected):
            if selected:
                game.executable = selected
                async_thread.run(db.update_game(game, "executable"))
                _launch_game()
        utils.push_popup(filepicker.FilePicker(f"Select executable for {game.name}", start_dir=globals.settings.default_exe_dir, callback=select_callback).tick)
    else:
        _launch_game()


def open_game_folder(game: Game):
    dir = pathlib.Path(game.executable).absolute().parent
    if not dir.is_dir():
        def reset_callback():
            game.executable = ""
            async_thread.run(db.update_game(game, "executable"))
        buttons = {
            "󰄬 Yes": reset_callback,
            "󰜺 No": None
        }
        utils.push_popup(msgbox.msgbox, "No such folder!", "The parent folder for the game executable could not be found.\n\nDo you want to unset the path?", MsgBox.warn, buttons)
    if globals.os is Os.Windows:
        os.startfile(str(dir))  # TODO: Needs testing
    else:
        if globals.os is Os.Linux:
            open_util = "xdg-open"
        elif globals.os is Os.MacOS:
            open_util = "open"
        subprocess.Popen(
            [
                open_util,
                str(dir)
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )


def open_webpage(url: str):
    set = globals.settings
    if set.browser is Browser._None:
        utils.push_popup(msgbox.msgbox, "Browser", "Please select a browser in order to open webpages!", MsgBox.warn)
        return
    # TODO: download pages
    name = set.browser.name
    if set.browser is Browser.Custom:
        name = "your browser"
        path = set.browser_custom_executable
        args = shlex.split(set.browser_custom_arguments)
    else:
        path = set.browser.path
        args = []
        if set.browser_private:
            args.append(set.browser.private)
    def _open_webpage(url):
        try:
            subprocess.Popen(
                [
                    path,
                    *args,
                    url
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            utils.push_popup(msgbox.msgbox, "Oops!", f"Something went wrong opening {name}:\n\n{utils.get_traceback()}", MsgBox.error)
    if globals.settings.browser_html:
        async def _fetch_page():
            if not await api.assert_login():
                return
            async with api.request("GET", url) as req:
                raw = await req.read()
            html = bs4.BeautifulSoup(raw, "lxml")
            for elem in html.find_all():
                for key, value in elem.attrs.items():
                    if isinstance(value, str) and value.startswith("/"):
                        elem.attrs[key] = globals.domain + value
            with tempfile.NamedTemporaryFile("wb", prefix="F95Checker-HTML-", delete=False) as f:
                f.write(html.prettify(encoding="utf-8"))
            _open_webpage(f.name)
        async_thread.run(_fetch_page())
    else:
        _open_webpage(url)


def remove_game(game: Game, bypass_confirm=False):
    def remove_callback():
        id = game.id
        del globals.games[id]
        globals.gui.require_sort = True
        async_thread.run(db.remove_game(id))
        for img in globals.images_path.glob(f"{id}.*"):
            try:
                img.unlink()
            except Exception:
                pass
    if not bypass_confirm and globals.settings.confirm_on_remove:
        buttons = {
            "󰄬 Yes": remove_callback,
            "󰜺 No": None
        }
        utils.push_popup(msgbox.msgbox, "Remove game", f"Are you sure you want to remove {game.name} from your list?", MsgBox.warn, buttons)
    else:
        remove_callback()

async def add_games(*threads: list[ThreadMatch]):
    dupes = []
    for thread in threads:
        if thread.id in globals.games:
            dupes.append(globals.games[thread.id].name)
            continue
        await db.add_game(thread)
        await db.load_games(thread.id)
        game = globals.games[thread.id]
        if globals.settings.select_executable_after_add:
            def select_callback(selected):
                if selected:
                    game.executable = selected
                    async_thread.run(db.update_game(game, "executable"))
            utils.push_popup(filepicker.FilePicker(f"Select executable for {game.name}", start_dir=globals.settings.default_exe_dir, callback=select_callback).tick)
    if dupes:
        utils.push_popup(msgbox.msgbox, "Duplicate games", "These games are already present in your library and therefore have not been re-added:\n - " + "\n - ".join(dupes), MsgBox.warn)
    globals.gui.require_sort = True

