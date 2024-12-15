import asyncio
import configparser
import difflib
import os
import pathlib
import plistlib
import re
import shlex
import stat
import string
import subprocess
import time
import typing

import glfw
import imgui

from common.structs import (
    Game,
    MsgBox,
    Os,
    SearchResult,
    Status,
    ThreadMatch,
    TimelineEventType,
)
from external import (
    async_thread,
    error,
    filepicker,
)
from modules import (
    api,
    db,
    globals,
    icons,
    msgbox,
    utils,
    webview,
)


def update_start_with_system(toggle: bool):
    try:
        if toggle:
            if globals.os is Os.Windows:
                import winreg
                current_user = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                key = winreg.OpenKeyEx(current_user, str(globals.autostart.parent), 0, winreg.KEY_WRITE)
                winreg.SetValueEx(key, globals.autostart.name, 0, winreg.REG_SZ, globals.start_cmd)
            elif globals.os is Os.Linux:
                config = configparser.RawConfigParser()
                config.optionxform = lambda option: option
                config.add_section("Desktop Entry")
                config.set("Desktop Entry", "Name", "F95Checker")
                config.set("Desktop Entry", "Comment", "An update checker tool for (NSFW) games on the F95zone platform")
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
                key = winreg.OpenKeyEx(current_user, str(globals.autostart.parent), 0, winreg.KEY_WRITE)
                winreg.DeleteValue(key, globals.autostart.name)
            elif globals.os is Os.Linux or globals.os is Os.MacOS:
                globals.autostart.unlink()
        globals.start_with_system = toggle
    except Exception:
        utils.push_popup(
            msgbox.msgbox, "Start with system error",
            "Something went wrong changing the start with system setting:\n"
            f"{error.text()}",
            MsgBox.error,
            more=error.traceback()
        )


def _fuzzy_match_subdir(where: pathlib.Path, match: str):
    clean_charset = string.ascii_letters + string.digits + " "
    clean_dir = "".join(char for char in match.replace("&", "and") if char in clean_charset)
    clean_dir = re.sub(r" +", r" ", clean_dir).strip()
    if (where / clean_dir).is_dir():
        where /= clean_dir
    else:
        try:
            dirs = [node.name for node in where.iterdir() if node.is_dir()]
            clean_dir_lower = clean_dir.lower()
            match_dirs = [d for d in dirs if clean_dir_lower in d.lower()]
            if len(match_dirs) == 1:
                where /= match_dirs[0]
            else:
                ratio = lambda a, b: difflib.SequenceMatcher(None, a.lower(), b.lower()).quick_ratio()
                similarity = {d: ratio(d, match) for d in dirs}
                best_match = max(similarity.keys())
                if similarity[best_match] > 0.85:
                    where /= best_match
        except Exception:
            pass
    return where


def add_game_exe(game: Game, callback: typing.Callable = None):
    use_uri = f"{icons.link_variant} Use URI"
    def select_callback(selected):
        if selected == use_uri:
            uri = ""
            def popup_content():
                nonlocal uri
                _, uri = imgui.input_text("###exe_uri", uri)
            buttons = {
                f"{icons.check} Ok": lambda: select_callback(uri),
                f"{icons.cancel} Cancel": lambda: select_callback(None)
            }
            utils.push_popup(
                utils.popup, f"Input URI for {game.name}",
                popup_content,
                buttons=buttons,
                closable=True,
                outside=False
            )
            return
        if selected:
            game.add_executable(selected)
        if callback:
            callback(selected)
    start_dir = globals.settings.default_exe_dir.get(globals.os)
    if start_dir:
        start_dir = pathlib.Path(start_dir)
        for subdir in (game.type.name, game.developer, game.name.removesuffix(" Collection")):
            start_dir = _fuzzy_match_subdir(start_dir, subdir)
    utils.push_popup(filepicker.FilePicker(
        title=f"Select or drop executable for {game.name}",
        start_dir=start_dir,
        callback=select_callback,
        buttons=[use_uri]
    ).tick)


async def default_open(what: str, cwd=None):
    if globals.os is Os.Windows:
        os.startfile(what)
    else:
        if globals.os is Os.Linux:
            open_util = "xdg-open"
        elif globals.os is Os.MacOS:
            open_util = "open"
        await asyncio.create_subprocess_exec(
            open_util, what,
            cwd=cwd or os.getcwd(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )


async def _launch_exe(executable: str):
    # Check URI scheme and launch with browser or default scheme handler
    if utils.is_uri(executable):
        if executable.startswith(("http://", "https://")):
            open_webpage(executable)
        else:
            await default_open(executable)
        return

    exe = pathlib.Path(executable)
    if globals.settings.default_exe_dir.get(globals.os) and not exe.is_absolute():
        exe = pathlib.Path(globals.settings.default_exe_dir.get(globals.os)) / exe
    if not exe.is_file():
        raise FileNotFoundError()

    if exe.suffix == ".html":
        open_webpage(exe.as_uri())
        return

    if globals.os is Os.Windows:
        # Open with default app
        await default_open(str(exe))
    else:
        mode = exe.stat().st_mode
        exe_flag = not (mode & stat.S_IEXEC < stat.S_IEXEC)
        with exe.open("rb") as f:
            # Check for shebang, exe and msi magic numbers
            exe_magic = f.read(8).startswith((b"#!", b"MZ", b"ZM", b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"))
        if exe_magic and not exe_flag:
            # Should be executable but isn't, fix it
            exe.chmod(mode | stat.S_IEXEC)
            exe_flag = True
        if (exe.parent / "renpy").is_dir():
            # Make all needed renpy libs executable
            for file in (exe.parent / "lib").glob("**/*"):
                if file.is_file() and not file.suffix:
                    mode = file.stat().st_mode
                    if mode & stat.S_IEXEC < stat.S_IEXEC:
                        file.chmod(mode | stat.S_IEXEC)
        if exe_magic and exe_flag:
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
            await default_open(str(exe), cwd=str(exe.parent))


async def _launch_game_exe(game: Game, executable: str):
    try:
        await _launch_exe(executable)
        game.last_launched = time.time()
        exe = pathlib.Path(executable)
        if utils.is_uri(executable):
            launched_name = executable.removeprefix("https://").removeprefix("http://")
        elif globals.settings.default_exe_dir.get(globals.os) and not exe.is_absolute():
            launched_name = executable
        else:
            launched_name = exe.name
        game.add_timeline_event(TimelineEventType.GameLaunched, f'"{launched_name}"')
    except FileNotFoundError:
        def select_callback(selected):
            if selected:
                game.remove_executable(executable)
                async_thread.run(_launch_game_exe(game, selected))
        buttons = {
            f"{icons.check} Yes": lambda: add_game_exe(game, select_callback),
            f"{icons.cancel} No": None
        }
        utils.push_popup(
            msgbox.msgbox, "File not found",
            "The selected executable could not be found.\n"
            "\n"
            "Do you want to select another one?",
            MsgBox.warn,
            buttons
        )
    except Exception:
        utils.push_popup(
            msgbox.msgbox, "Game launch error",
            f"Something went wrong launching {executable}:\n"
            f"{error.text()}",
            MsgBox.error,
            more=error.traceback()
        )


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
                async_thread.run(_launch_game_exe(game, selected))
        add_game_exe(game, select_callback)
        return

    def popup_content():
        imgui.text("Click one of the executables to launch it, or Cancel to not do anything.\n\n")
        for executable in game.executables:
            if imgui.selectable(executable, False)[0]:
                async_thread.run(_launch_game_exe(game, executable))
                return True
    buttons = {
        f"{icons.cancel} Cancel": None
    }
    utils.push_popup(
        utils.popup, f"Choose Exe for {game.name}",
        popup_content,
        buttons=buttons,
        closable=True,
        outside=True
    )


async def _open_folder(executable: str):
    if utils.is_uri(executable):
        return

    exe = pathlib.Path(executable)
    if globals.settings.default_exe_dir.get(globals.os) and not exe.is_absolute():
        exe = pathlib.Path(globals.settings.default_exe_dir.get(globals.os)) / exe
    folder = exe.parent
    if not folder.is_dir():
        raise FileNotFoundError()

    await default_open(str(folder), cwd=str(folder))


async def _open_game_folder_exe(game: Game, executable: str):
    try:
        await _open_folder(executable)
    except FileNotFoundError:
        def select_callback(selected):
            if selected:
                game.remove_executable(executable)
                async_thread.run(_open_game_folder_exe(game, selected))
        buttons = {
            f"{icons.check} Yes": lambda: add_game_exe(game, select_callback),
            f"{icons.cancel} No": None
        }
        utils.push_popup(
            msgbox.msgbox, "Folder not found",
            "The parent folder for the game executable could not be found.\n"
            "\n"
            "Do you want to select another executable?",
            MsgBox.warn,
            buttons
        )
    except Exception:
        utils.push_popup(
            msgbox.msgbox, "Open folder error",
            f"Something went wrong opening the folder for {executable}:\n"
            f"{error.text()}",
            MsgBox.error,
            more=error.traceback()
        )


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
                async_thread.run(_open_game_folder_exe(game, selected))
        buttons = {
            f"{icons.check} Yes": lambda: add_game_exe(game, select_callback),
            f"{icons.cancel} No": None
        }
        utils.push_popup(
            msgbox.msgbox, "Exe not selected",
            "You did not select an executable for this game, so\n"
            "opening its folder is not possible.\n"
            "\n"
            "Do you want to select it now?",
            MsgBox.warn,
            buttons
        )
        return

    def popup_content():
        imgui.text("Click one of the executables to open its folder, or Cancel to not do anything.\n\n")
        for executable in game.executables:
            if imgui.selectable(executable, False)[0]:
                async_thread.run(_open_game_folder_exe(game, executable))
                return True
    buttons = {
        f"{icons.cancel} Cancel": None
    }
    utils.push_popup(
        utils.popup, f"Choose Folder for {game.name}",
        popup_content,
        buttons=buttons,
        closable=True,
        outside=True
    )


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
                await webview.start("open", url, size=(1269, 969))
            else:
                await asyncio.create_subprocess_exec(
                    *args, url,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        except Exception:
            utils.push_popup(
                msgbox.msgbox, "Open webpage error",
                f"Something went wrong opening {name}:\n"
                f"{error.text()}",
                MsgBox.error,
                more=error.traceback()
            )
    if globals.settings.browser_html and api.is_f95zone_url(url):
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


def redirect_masked_link(masked_url: str, copy=False):
    host = (re.search(r"/masked/(.*?)/", masked_url) or ("", ""))[1]
    if not copy and globals.settings.browser.integrated:
        size = (1269, 969)
    else:
        size = (520, 480)
    async def _unmask_and_copy():
        if not await api.assert_login():
            return
        with await webview.start(
            "css_redirect", masked_url, "a.host_link",
            title=f"Unmask link{f' for {host}' if host else ''}",
            size=size,
            pipe=True,
            minimal=copy,
        ) as pipe:
            link = await pipe.get_async()
            if copy:
                clipboard_copy(link)
            else:
                if globals.settings.browser.integrated:
                    pipe.daemon.finalize.detach()
                else:
                    open_webpage(link)
    async_thread.run(_unmask_and_copy())


def redirect_xpath_link(thread_url: str, xpath_expr: str, copy=False):
    host = (re.search(r"://(.*?)/", xpath_expr) or ("", ""))[1]
    xpath_post = "//*[contains(@class,'message-threadStarterPost')][1]"
    xpath_expr = xpath_post + xpath_expr  # Parser only looks inside main post element
    if not copy and globals.settings.browser.integrated:
        size = (1269, 969)
    else:
        size = (520, 480)
    async def _retrieve_and_copy():
        if not await api.assert_login():
            return
        with await webview.start(
            "xpath_redirect", thread_url, xpath_expr,
            title=f"Retrieve link{f' for {host}' if host else ''}",
            size=size,
            pipe=True,
            minimal=copy,
        ) as pipe:
            link = await pipe.get_async()
            if copy:
                clipboard_copy(link)
            else:
                if globals.settings.browser.integrated:
                    pipe.daemon.finalize.detach()
                else:
                    open_webpage(link)
    async_thread.run(_retrieve_and_copy())


def convert_f95zone_to_custom(game: Game):
    async_thread.wait(db.update_game_id(game, utils.custom_id()))
    game.custom = True
    game.downloads = ()


def convert_custom_to_f95zone(game: Game):
    new_id = utils.extract_thread_matches(game.url)
    if not new_id:
        utils.push_popup(
            msgbox.msgbox, "Invalid URL",
            "The URL you provided for this game is not a valid F95zone thread link!",
            MsgBox.warn
        )
        return
    new_id = new_id[0].id
    if new_id in globals.games and globals.games[new_id] is not game:
        utils.push_popup(
            msgbox.msgbox, "Invalid URL",
            "The URL you provided for this game points to another game that is already in your list!",
            MsgBox.warn
        )
        return
    async_thread.wait(db.update_game_id(game, new_id))
    game.custom = False
    game.status = Status.Unchecked


def remove_game(*games: list[Game], bypass_confirm=False):
    def remove_callback():
        for game in games:
            id = game.id
            game.delete_images()
            del globals.games[id]
            globals.gui.recalculate_ids = True
            async_thread.run(db.delete_game(id))
            async_thread.run(db.delete_timeline_events(id))
    if not bypass_confirm and (len(games) > 1 or globals.settings.confirm_on_remove):
        buttons = {
            f"{icons.check} Yes": remove_callback,
            f"{icons.cancel} No": None
        }
        utils.push_popup(
            msgbox.msgbox, f"Remove game{'' if len(games) == 1 else 's'}",
            f"You are removing {'this game' if len(games) == 1 else 'these games'} from your list:\n" +
            "\n".join(game.name for game in games) + "\n"
            "Are you sure you want to do this?",
            MsgBox.warn,
            buttons
        )
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
            await db.create_game(thread)
            await db.load_games(thread.id)
            game = globals.games[thread.id]
            added.append(game.name)
            if globals.settings.mark_installed_after_add:
                game.installed = game.version
            if globals.settings.select_executable_after_add:
                add_game_exe(game)
        dupe_count = len(dupes)
        added_count = len(added)
        if dupe_count > 0 or added_count > 1:
            utils.push_popup(
                msgbox.msgbox, f"{'Duplicate' if dupe_count > 0 else 'Added'} games",
                (
                    (f"{added_count} new game{' has' if added_count == 1 else 's have'} been added to your library.\n"
                    "Make sure to refresh to grab all the game details.")
                    if added_count > 0 else ""
                ) +
                ("\n\n" if dupe_count > 0 and added_count > 0 else "") +
                (
                    f"{dupe_count} duplicate game{' has' if dupe_count == 1 else 's have'} not been re-added."
                    if dupe_count > 0 else ""
                ),
                MsgBox.warn if dupe_count > 0 else MsgBox.info,
                more=(("Added:\n - " + "\n - ".join(added)) if added_count > 0 else "") +
                     ("\n\n" if dupe_count > 0 and added_count > 0 else "") +
                     (("Duplicates:\n - " + "\n - ".join(dupes)) if dupe_count > 0 else "")
            )
        globals.gui.recalculate_ids = True
    count = len(threads)
    if globals.settings.select_executable_after_add and count > 1:
        buttons = {
            f"{icons.check} Yes": lambda: async_thread.run(_add_games()),
            f"{icons.cancel} No": None
        }
        utils.push_popup(
            msgbox.msgbox, "Are you sure?",
            f"You are about to add {count} games and you have enabled the 'Ask exe on add' setting enabled.\n"
            f"This means that you will be asked to select the executable for all {count} games.\n"
            "\n"
            "Do you wish to continue?",
            MsgBox.warn,
            buttons
        )
    else:
        await _add_games()
