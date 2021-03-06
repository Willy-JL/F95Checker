from PyQt6.QtWidgets import QSystemTrayIcon
import OpenGL.GL as gl
import concurrent
import functools
import traceback
import asyncio
import hashlib
import weakref
import typing
import random
import imgui
import time
import math
import glfw
import sys
import re

from modules import globals, async_thread, msgbox


def hash(text: str):
    return int(hashlib.md5(text.encode()).hexdigest()[-12:], 16)


def hex_to_rgba_0_1(hex):
    r = int(hex[1:3], base=16) / 255
    g = int(hex[3:5], base=16) / 255
    b = int(hex[5:7], base=16) / 255
    if len(hex) > 7:
        a = int(hex[7:9], base=16) / 255
    else:
        a = 1.0
    return (r, g, b, a)


def rgba_0_1_to_hex(rgba):
    r = "%.2x" % int(rgba[0] * 255)
    g = "%.2x" % int(rgba[1] * 255)
    b = "%.2x" % int(rgba[2] * 255)
    if len(rgba) > 3:
        a = "%.2x" % int(rgba[3] * 255)
    else:
        a = "FF"
    return f"#{r}{g}{b}{a}"


def rand_num_str(len=8):
    return "".join((random.choice('0123456789') for _ in range(len)))


def is_refreshing():
    if globals.refresh_task and not globals.refresh_task.done():
        return True
    return False


def start_refresh_task(coro: typing.Coroutine):
    if is_refreshing():
        return
    globals.gui.bg_mode_timer = None
    globals.refresh_progress = 0
    globals.refresh_total = 1
    globals.refresh_task = async_thread.run(coro)
    globals.gui.tray.update_status()
    def done_callback(future: asyncio.Future):
        globals.refresh_task = None
        globals.gui.tray.update_status()
        globals.gui.require_sort = True
        if (globals.gui.minimized or not globals.gui.focused) and (count := len(globals.updated_games)) > 0:
            globals.gui.tray.push_msg(title="Updates", msg=f"{count} item{'' if count == 1 else 's'} in your library {'has' if count == 1 else 'have'} received updates, click here to view {'it' if count == 1 else 'them'}.", icon=QSystemTrayIcon.MessageIcon.Information)
        # Continues after this only if the task completed successfully
        try:
            if future.exception():
                return
        except concurrent.futures.CancelledError:
            return
        if globals.last_update_check is not None and globals.last_update_check < time.time() - 21600:  # Check updates after refreshing at 6 hour intervals
            from modules import api
            globals.last_update_check = None
            update_check = async_thread.run(api.check_updates())
            def reset_timer(_):
                if globals.last_update_check is None:
                    globals.last_update_check = 0.0
            update_check.add_done_callback(reset_timer)
    globals.refresh_task.add_done_callback(done_callback)


# https://gist.github.com/Willy-JL/f733c960c6b0d2284bcbee0316f88878
def get_traceback(*exc_info: list):
    exc_info = exc_info or sys.exc_info()
    tb_lines = traceback.format_exception(*exc_info)
    tb = "".join(tb_lines)
    return tb


class daemon:
    def __init__(self, proc):
        self.finalize = weakref.finalize(proc, self.kill, proc)

    @staticmethod
    def kill(proc):
        if hasattr(proc, "returncode") and proc.returncode is None:
            proc.kill()
        elif hasattr(proc, "poll") and proc.poll() is None:
            proc.kill()

    def __enter__(self):
        pass

    def __exit__(self, *_):
        self.finalize()


# https://github.com/pyimgui/pyimgui/blob/24219a8d4338b6e197fa22af97f5f06d3b1fe9f7/doc/examples/integrations_glfw3.py
def impl_glfw_init(width: int, height: int, window_name: str):
    # FIXME: takes quite a while to initialize on my arch linux machine
    if not glfw.init():
        print("Could not initialize OpenGL context")
        sys.exit(1)

    if sys.platform.startswith("darwin"):
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


def push_disabled(block_interaction=True):
    if block_interaction:
        imgui.internal.push_item_flag(imgui.internal.ITEM_DISABLED, True)
    imgui.push_style_var(imgui.STYLE_ALPHA, imgui.style.alpha *  0.5)


def pop_disabled(block_interaction=True):
    if block_interaction:
        imgui.internal.pop_item_flag()
    imgui.pop_style_var()


def center_next_window():
    size = imgui.io.display_size
    imgui.set_next_window_position(size.x / 2, size.y / 2, pivot_x=0.5, pivot_y=0.5)


def constrain_next_window():
    size = imgui.io.display_size
    imgui.set_next_window_size_constraints((0, 0), (size.x * 0.9, size.y * 0.9))


def close_weak_popup():
    if not imgui.is_popup_open("", imgui.POPUP_ANY_POPUP_ID):
        # This is the topmost popup
        if imgui.io.keys_down[glfw.KEY_ESCAPE]:
            # Escape is pressed
            imgui.close_current_popup()
            return True
        elif imgui.is_mouse_clicked():
            # Mouse was just clicked
            pos = imgui.get_window_position()
            size = imgui.get_window_size()
            if not imgui.is_mouse_hovering_rect(pos.x, pos.y, pos.x + size.x, pos.y + size.y, clip=False):
                # Popup is not hovered
                imgui.close_current_popup()
                return True
    return False


def wrap_text(text: str, *args, width: float, offset=0, func: typing.Callable = imgui.text_unformatted, **kwargs):
    for line in text.split("\n"):
        while line:= line.strip():
            if offset is not None:
                avail = width - offset
            if avail < 0:
                imgui.dummy(0, 0)
                if offset is not None:
                    offset = None
                    avail = width
                continue
            if avail > 0:
                cut = 1
                line_len = len(line)
                step = math.ceil(line_len / 50)
                while cut <= line_len and imgui.calc_text_size(line[:cut]).x < avail:
                    cut += step
                while cut > 1 and (cut > line_len or imgui.calc_text_size(line[:cut]).x >= avail):
                    cut -= 1
            else:
                cut = len(line)
            func(line[:cut], *args, **kwargs)
            line = line[cut:]
            if offset is not None:
                offset = None
                avail = width


def clean_thread_url(url: str):
    thread = re.search("threads/([^/]*)", url).group(1)
    return f"{globals.threads_page}{thread}/"


from modules.structs import MsgBox, ThreadMatch

def extract_thread_matches(text: str) -> list[ThreadMatch]:
    matches = []
    if not isinstance(text, str):
        return matches
    for match in re.finditer(r"threads/(?:([^\./]*)\.)?(\d+)", text):
        matches.append(ThreadMatch(title=match.group(1) or "", id=int(match.group(2))))
    return matches


def popup(label: str, popup_content: typing.Callable, buttons: dict[str, typing.Callable] = None, closable=True, outside=True):
    if buttons is True:
        buttons = {
            "???? Ok": None
        }
    if not imgui.is_popup_open(label):
        imgui.open_popup(label)
    closed = False
    opened = 1
    constrain_next_window()
    center_next_window()
    if imgui.begin_popup_modal(label, closable or None, flags=globals.gui.popup_flags)[0]:
        if outside:
             closed = close_weak_popup()
        imgui.begin_group()
        popup_content()
        imgui.end_group()
        imgui.spacing()
        if buttons:
            btns_width = sum(imgui.calc_text_size(name).x for name in buttons) + (2 * len(buttons) * imgui.style.frame_padding.x) + (imgui.style.item_spacing.x * (len(buttons) - 1))
            cur_pos_x = imgui.get_cursor_pos_x()
            new_pos_x = cur_pos_x + imgui.get_content_region_available_width() - btns_width
            if new_pos_x > cur_pos_x:
                imgui.set_cursor_pos_x(new_pos_x)
            for label, callback in buttons.items():
                if imgui.button(label):
                    if callback:
                        callback()
                    imgui.close_current_popup()
                    closed = True
                imgui.same_line()
    else:
        opened = 0
        closed = True
    return opened, closed


def push_popup(*args, bottom=False, **kwargs):
    if len(args) + len(kwargs) > 1:
        if args[0] is popup or args[0] is msgbox.msgbox:
            args = list(args)
            args[1] = args[1] + "##" + rand_num_str()
        popup_func = functools.partial(*args, **kwargs)
    else:
        popup_func = args[0]
    if (globals.gui.minimized or not globals.gui.focused) and (len(args) > 3) and (args[0] is msgbox.msgbox) and (args[3] is MsgBox.warn or args[3] is MsgBox.error):
        if globals.gui.minimized and args[1].startswith("Daily backups##"):
            return
        globals.gui.tray.push_msg(title="Oops", msg="Something went wrong, click here to view the error.", icon=QSystemTrayIcon.MessageIcon.Critical)
    if bottom:
        globals.popup_stack.insert(0, popup_func)
    else:
        globals.popup_stack.append(popup_func)
    return popup_func
