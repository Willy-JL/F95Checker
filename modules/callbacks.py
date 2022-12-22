import multiprocessing
import configparser
import subprocess
import plistlib
import pathlib
import asyncio
import shlex
import imgui
import glfw
import time
import stat
import re
import os

from modules.structs import DaemonProcess, Game, MsgBox, Os, ProcessPipe, SearchResult, ThreadMatch
from modules import globals, api, async_thread, db, error, filepicker, icons, msgbox, utils, webview


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
                with globals.autostart.open("w") as f:
                    config.write(f, space_around_delimiters=False)
            elif globals.os is Os.MacOS:
                plist = {
                    "Label": "io.github.willy-jl.f95checker",
                    "ProgramArguments": shlex.split(globals.start_cmd),
                    "KeepAlive": False,
                    "RunAtLoad": True
                }
                globals.autostart.write_bytes(plistlib.dumps(plist))
        else:
            if globals.os is Os.Windows:
                import winreg
                current_user = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                winreg.SetValue(current_user, globals.autostart, winreg.REG_SZ, "")
            elif globals.os is Os.Linux or globals.os is Os.MacOS:
                globals.autostart.unlink()
        globals.start_with_system = toggle
    except Exception:
        utils.push_popup(msgbox.msgbox, "Start with system error", f"Something went wrong changing the start with system setting:\n{error.text()}", MsgBox.error, more=error.traceback())


async def _launch_exe(path: str):
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
            mark_exe = False
            if exe.suffix in (".exe", ".msi"):  # Probably windows executable
                mark_exe = True
            with exe.open("rb") as f:
                if f.read(2) == b"#!":  # Shebang is present, probably a script
                    mark_exe = True
            if mark_exe:
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
            await asyncio.create_subprocess_exec(
                str(exe),
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
            await asyncio.create_subprocess_exec(
                open_util, str(exe),
                cwd=str(exe.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )


async def _launch_game_exe(game: Game, executable: str):
    try:
        await _launch_exe(executable)
        game.last_played.update(time.time())
        await db.update_game(game, "last_played")
    except FileNotFoundError:
        def select_callback(selected):
            if selected:
                game.remove_executable(executable)
                game.add_executable(selected)
                async_thread.run(db.update_game(game, "executables"))
                async_thread.run(_launch_game_exe(game, selected))
        buttons = {
            f"{icons.check} Yes": lambda: utils.push_popup(filepicker.FilePicker(f"Select or drop executable for {game.name}", start_dir=globals.settings.default_exe_dir, callback=select_callback).tick),
            f"{icons.cancel} No": None
        }
        utils.push_popup(msgbox.msgbox, "File not found", "The selected executable could not be found.\n\nDo you want to select another one?", MsgBox.warn, buttons)
    except Exception:
        utils.push_popup(msgbox.msgbox, "Game launch error", f"Something went wrong launching {executable}:\n{error.text()}", MsgBox.error, more=error.traceback())


def launch_game(game: Game, executable: str = None):
    game.validate_executables()
    if not executable and len(game.executables) == 1:
        executable = game.executables[0]
    if executable:
        async_thread.run(_launch_game_exe(game, executable))
        return

    if not game.executables:
        def select_callback(selected):
            if selected:
                game.add_executable(selected)
                async_thread.run(db.update_game(game, "executables"))
                async_thread.run(_launch_game_exe(game, selected))
        utils.push_popup(filepicker.FilePicker(f"Select or drop executable for {game.name}", start_dir=globals.settings.default_exe_dir, callback=select_callback).tick)
        return

    def popup_content():
        imgui.text("Click one of the executables to launch it, or Cancel to not do anything.\n\n")
        for i, executable in enumerate(game.executables):
            if imgui.selectable(f"{executable}###{game.id}_launch_exe_{i}", False)[0]:
                async_thread.run(_launch_game_exe(game, executable))
                return True
    buttons = {
        f"{icons.cancel} Cancel": None
    }
    utils.push_popup(utils.popup, f"Choose Exe for {game.name}", popup_content, buttons=buttons, closable=True, outside=True)


async def _open_folder(path: str):
    folder = pathlib.Path(path).absolute().parent
    if not folder.is_dir():
        raise FileNotFoundError()

    if globals.os is Os.Windows:
        os.startfile(str(folder))
    else:
        if globals.os is Os.Linux:
            open_util = "xdg-open"
        elif globals.os is Os.MacOS:
            open_util = "open"
        await asyncio.create_subprocess_exec(
            open_util, str(folder),
            cwd=str(folder),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )


async def _open_game_folder_exe(game: Game, executable: str):
    try:
        await _open_folder(executable)
    except FileNotFoundError:
        def select_callback(selected):
            if selected:
                game.remove_executable(executable)
                game.add_executable(selected)
                async_thread.run(db.update_game(game, "executables"))
                async_thread.run(_open_game_folder_exe(game, selected))
        buttons = {
            f"{icons.check} Yes": lambda: utils.push_popup(filepicker.FilePicker(f"Select or drop executable for {game.name}", start_dir=globals.settings.default_exe_dir, callback=select_callback).tick),
            f"{icons.cancel} No": None
        }
        utils.push_popup(msgbox.msgbox, "Folder not found", "The parent folder for the game executable could not be found.\n\nDo you want to select another executable?", MsgBox.warn, buttons)
    except Exception:
        utils.push_popup(msgbox.msgbox, "Open folder error", f"Something went wrong opening the folder for {executable}:\n{error.text()}", MsgBox.error, more=error.traceback())


def open_game_folder(game: Game, executable: str = None):
    game.validate_executables()
    if not executable and len(game.executables) == 1:
        executable = game.executables[0]
    if executable:
        async_thread.run(_open_game_folder_exe(game, executable))
        return

    if not game.executables:
        def select_callback(selected):
            if selected:
                game.add_executable(selected)
                async_thread.run(db.update_game(game, "executables"))
                async_thread.run(_open_game_folder_exe(game, selected))
        buttons = {
            f"{icons.check} Yes": lambda: utils.push_popup(filepicker.FilePicker(f"Select or drop executable for {game.name}", start_dir=globals.settings.default_exe_dir, callback=select_callback).tick),
            f"{icons.cancel} No": None
        }
        utils.push_popup(msgbox.msgbox, "Exe not selected", "You did not select an executable for this game, so\nopening its folder is not possible.\n\nDo you want to select it now?", MsgBox.warn, buttons)
        return

    def popup_content():
        imgui.text("Click one of the executables to open its folder, or Cancel to not do anything.\n\n")
        for i, executable in enumerate(game.executables):
            if imgui.selectable(f"{executable}###{game.id}_open_folder_{i}", False)[0]:
                async_thread.run(_open_game_folder_exe(game, executable))
                return True
    buttons = {
        f"{icons.cancel} Cancel": None
    }
    utils.push_popup(utils.popup, f"Choose Folder for {game.name}", popup_content, buttons=buttons, closable=True, outside=True)


def open_webpage(url: str):
    set = globals.settings
    if set.browser.integrated:
        name = "the integrated browser"
    elif set.browser.custom:
        name = "your custom browser"
        args = [set.browser_custom_executable, *shlex.split(set.browser_custom_arguments)]
    else:
        name = set.browser.name
        args = [*set.browser.args]
        if set.browser_private:
            args.extend(set.browser.private_arg)
    async def _open_webpage(url: str):
        try:
            if set.browser.integrated:
                proc = multiprocessing.Process(target=webview.open, args=(url,), kwargs=webview.kwargs() | dict(cookies=globals.cookies, size=(1269, 969)))
                proc.start()
                DaemonProcess(proc)
            else:
                await asyncio.create_subprocess_exec(
                    *args, url,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        except Exception:
            utils.push_popup(msgbox.msgbox, "Open webpage error", f"Something went wrong opening {name}:\n{error.text()}", MsgBox.error, more=error.traceback())
    if globals.settings.browser_html:
        async def _fetch_open_page():
            html = await api.download_webpage(url)
            if html:
                await _open_webpage(html)
        async_thread.run(_fetch_open_page())
    else:
        async_thread.run(_open_webpage(url))


def clipboard_copy(text: str):
    glfw.set_clipboard_string(globals.gui.window, text)


def clipboard_paste():
    return str(glfw.get_clipboard_string(globals.gui.window) or b"", encoding="utf-8")


def copy_masked_link(masked_url: str):
    host = (re.search(r"/masked/(.*?)/", masked_url) or ("", ""))[1]
    pipe = ProcessPipe()
    proc = multiprocessing.Process(target=webview.redirect, args=(masked_url, pipe, "a.host_link"), kwargs=webview.kwargs() | dict(
        cookies=globals.cookies,
        title=f"Unmask link{f' for {host}' if host else ''}",
        size=(size := (520, 480)),
        pos=(
            int(globals.gui.screen_pos[0] + (imgui.io.display_size.x / 2) - size[0] / 2),
            int(globals.gui.screen_pos[1] + (imgui.io.display_size.y / 2) - size[1] / 2)
        )
    ))
    async def _unmask_and_copy():
        with pipe(proc):
            clipboard_copy(await pipe.get_async())
    async_thread.run(_unmask_and_copy())


def remove_game(game: Game, bypass_confirm=False):
    def remove_callback():
        id = game.id
        del globals.games[id]
        if id in globals.updated_games:
            del globals.updated_games[id]
        globals.gui.require_sort = True
        async_thread.run(db.remove_game(id))
        for img in globals.images_path.glob(f"{id}.*"):
            try:
                img.unlink()
            except Exception:
                pass
    if not bypass_confirm and globals.settings.confirm_on_remove:
        buttons = {
            f"{icons.check} Yes": remove_callback,
            f"{icons.cancel} No": None
        }
        utils.push_popup(msgbox.msgbox, "Remove game", f"Are you sure you want to remove {game.name} from your list?", MsgBox.warn, buttons)
    else:
        remove_callback()

async def add_games(*threads: list[ThreadMatch | SearchResult]):
    if not threads:
        return
    async def _add_games():
        dupes = []
        added = []
        for thread in threads:
            if thread.id in globals.games:
                dupes.append(globals.games[thread.id].name)
                continue
            await db.add_game(thread)
            await db.load_games(thread.id)
            game = globals.games[thread.id]
            added.append(game.name)
            if globals.settings.select_executable_after_add:
                def select_callback(selected):
                    if selected:
                        game.add_executable(selected)
                        async_thread.run(db.update_game(game, "executables"))
                utils.push_popup(filepicker.FilePicker(f"Select or drop executable for {game.name}", start_dir=globals.settings.default_exe_dir, callback=select_callback).tick)
        dupe_count = len(dupes)
        added_count = len(added)
        if dupe_count > 0 or added_count > 1:
            utils.push_popup(msgbox.msgbox, ("Duplicate" if dupe_count > 0 else "Added") + " games", ((f"{added_count} new game{' has' if added_count == 1 else 's have'} been added to your library.\nMake sure to refresh to grab all the game details.") if added_count > 0 else "") + ("\n\n" if dupe_count > 0 and added_count > 0 else "") + ((f"{dupe_count} duplicate game{' has' if dupe_count == 1 else 's have'} not been re-added.") if dupe_count > 0 else ""), MsgBox.warn if dupe_count > 0 else MsgBox.info, more=(("Added:\n - " + "\n - ".join(added)) if added_count > 0 else "") + ("\n\n" if dupe_count > 0 and added_count > 0 else "") + (("Duplicates:\n - " + "\n - ".join(dupes)) if dupe_count > 0 else ""))
        globals.gui.require_sort = True
    count = len(threads)
    if globals.settings.select_executable_after_add and count > 1:
        buttons = {
            f"{icons.check} Yes": lambda: async_thread.run(_add_games()),
            f"{icons.cancel} No": None
        }
        utils.push_popup(msgbox.msgbox, "Are you sure?", f"You are about to add {count} games and you have enabled the \"Ask path on add\" setting enabled.\nThis means that you will be asked to select the executable for all {count} games.\n\nDo you wish to continue?", MsgBox.warn, buttons)
    else:
        await _add_games()
