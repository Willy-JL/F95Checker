import OpenGL.GL as gl
import subprocess
import traceback
import functools
import pathlib
import shlex
import imgui
import glfw
import stat
import sys
import re
import os

from modules.structs import Browser, Game, MsgBox, Os
from modules.remote import async_thread, filepicker
from modules import globals, db


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
        globals.popup_stack.append(functools.partial(globals.gui.draw_msgbox, "No such folder!", "The parent folder for the game executable could not be found.\n\nDo you want to unset the path?", MsgBox.warn, buttons))
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


def launch_game_exe(path: str | pathlib.Path):
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


def launch(game: Game):
    def launch_game():
        if not game.executable:
            return
        try:
            launch_game_exe(game.executable)
        except FileNotFoundError:
            def reset_callback():
                game.executable = ""
                async_thread.run(db.update_game(game, "executable"))
            buttons = {
                "󰄬 Yes": reset_callback,
                "󰜺 No": None
            }
            globals.popup_stack.append(functools.partial(globals.gui.draw_msgbox, "File not found!", "The selected executable could not be found.\n\nDo you want to unset the path?", MsgBox.warn, buttons))
        except Exception:
            globals.popup_stack.append(functools.partial(globals.gui.draw_msgbox, "Oops!", f"Something went wrong launching {game.name}:\n\n{get_traceback()}", MsgBox.error))
    if not game.executable:
        def select_callback(selected):
            if selected:
                game.executable = selected
                async_thread.run(db.update_game(game, "executable"))
                launch_game()
        globals.popup_stack.append(filepicker.FilePicker(f"Select executable for {game.name}", callback=select_callback).tick)
    else:
        launch_game()


def open_webpage(url: str):
    set = globals.settings
    if set.browser is Browser._None:
        globals.popup_stack.append(functools.partial(globals.gui.draw_msgbox, "Browser", "Please select a browser in order to open webpages!", MsgBox.warn))
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
        globals.popup_stack.append(functools.partial(globals.gui.draw_msgbox, "Oops!", f"Something went wrong opening {name}:\n\n{get_traceback()}", MsgBox.error))


def extract_thread_ids(text: str):
    ids = []
    for match in re.finditer("threads/(?:[^\./]*\.)?(\d+)", text):
        ids.append(int(match.group(1)))
    return ids


# https://gist.github.com/Willy-JL/f733c960c6b0d2284bcbee0316f88878
def get_traceback():
    exc_info = sys.exc_info()
    tb_lines = traceback.format_exception(*exc_info)
    tb = "".join(tb_lines)
    return tb


# https://github.com/pyimgui/pyimgui/blob/24219a8d4338b6e197fa22af97f5f06d3b1fe9f7/doc/examples/integrations_glfw3.py
def impl_glfw_init(width: int, height: int, window_name: str):
    # FIXME: takes quite a while to initialize on my arch linux machine
    if not glfw.init():
        print("Could not initialize OpenGL context")
        sys.exit(1)

    # OS X supports only forward-compatible core profiles from 3.2
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)

    # Create a windowed mode window and its OpenGL context
    window = glfw.create_window(width, height, window_name, None, None)
    glfw.make_context_current(window)

    if not window:
        glfw.terminate()
        print("Could not initialize Window")
        sys.exit(1)

    return window


def push_disabled(block_interaction: bool = True):
    if block_interaction:
        imgui.internal.push_item_flag(imgui.internal.ITEM_DISABLED, True)
    imgui.push_style_var(imgui.STYLE_ALPHA, imgui.style.alpha *  0.5)


def pop_disabled(block_interaction: bool = True):
    if block_interaction:
        imgui.internal.pop_item_flag()
    imgui.pop_style_var()


def center_next_window():
    size = imgui.io.display_size
    imgui.set_next_window_position(size.x / 2, size.y / 2, pivot_x=0.5, pivot_y=0.5)


def close_popup_clicking_outside():
    if not imgui.is_popup_open("", imgui.POPUP_ANY_POPUP_ID):
        # This is the topmost popup
        if imgui.is_mouse_clicked():
            # Mouse was just clicked
            pos = imgui.get_window_position()
            size = imgui.get_window_size()
            if not imgui.is_mouse_hovering_rect(pos.x, pos.y, pos.x + size.x, pos.y + size.y, clip=False):
                # Popup is not hovered
                imgui.close_current_popup()
                return True
    return False
