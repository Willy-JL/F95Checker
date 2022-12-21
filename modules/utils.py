from PyQt6.QtWidgets import QSystemTrayIcon
import OpenGL.GL as gl
import concurrent
import functools
import asyncio
import weakref
import typing
import random
import imgui
import time
import math
import glfw
import sys
import re

from modules import globals, async_thread, callbacks, icons, msgbox


def rand_num_str(len=8):
    return "".join((random.choice('0123456789') for _ in range(len)))


@functools.cache
def map_range(in_value: float, in_start: float, in_end: float, out_start: float, out_end: float):
    in_value -= in_start
    in_end -= in_start
    in_start = 0.0
    out_range = out_end - out_start
    out_value = ((in_value / in_end) * out_range) + out_start
    return out_value


def is_refreshing():
    if globals.refresh_task and not globals.refresh_task.done():
        return True
    return False


def start_refresh_task(coro: typing.Coroutine, reset_bg_timers=True):
    if is_refreshing():
        return
    if reset_bg_timers:
        globals.gui.bg_mode_timer = None
        globals.gui.bg_mode_notifs_timer = None
    globals.refresh_progress = 0
    globals.refresh_total = 1
    globals.gui.refresh_ratio_smooth = 0.0
    globals.refresh_task = async_thread.run(coro)
    globals.gui.tray.update_status()
    def done_callback(future: asyncio.Future):
        globals.refresh_task = None
        globals.gui.tray.update_status()
        globals.gui.require_sort = True
        if (globals.gui.hidden or not globals.gui.focused) and (count := len(globals.updated_games)) > 0:
            globals.gui.tray.push_msg(title="Updates", msg=f"{count} item{'' if count == 1 else 's'} in your library {'has' if count == 1 else 'have'} received updates, click here to view {'it' if count == 1 else 'them'}.", icon=QSystemTrayIcon.MessageIcon.Information)
        # Continues after this only if the task was not cancelled
        try:
            future.exception()
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


class daemon:
    def __init__(self, proc):
        self.finalize = weakref.finalize(proc, self.kill, proc)

    @staticmethod
    def kill(proc):
        # Multiprocessing
        if getattr(proc, "exitcode", False) is None:
            proc.kill()
        # Asyncio subprocess
        elif getattr(proc, "returncode", False) is None:
            proc.kill()
        # Standard subprocess
        elif getattr(proc, "poll", lambda: False)() is None:
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


def validate_geometry(x, y, width, height):
    window_pos = (x, y)
    window_size = (width, height)
    valid = True
    for monitor in glfw.get_monitors():
        valid = False
        monitor_area = glfw.get_monitor_workarea(monitor)
        monitor_pos = (monitor_area[0], monitor_area[1])
        monitor_size = (monitor_area[2], monitor_area[3])
        # Horizontal check, at least 1 pixel on x axis must be in monitor
        if (window_pos[0]) >= (monitor_pos[0] + monitor_size[0]):
            continue  # Too right
        if (window_pos[0] + window_size[0]) <= (monitor_pos[0]):
            continue  # Too left
        # Vertical check, at least the pixel above window must be in monitor (titlebar)
        if (window_pos[1] - 1) >= (monitor_pos[1] + monitor_size[1]):
            continue  # Too low
        if (window_pos[1]) <= (monitor_pos[1]):
            continue  # Too high
        valid = True
        break
    return valid


def center_next_window():
    size = imgui.io.display_size
    imgui.set_next_window_position(size.x / 2, size.y / 2, pivot_x=0.5, pivot_y=0.5)


def constrain_next_window():
    size = imgui.io.display_size
    imgui.set_next_window_size_constraints((0, 0), (size.x * 0.9, size.y * 0.9))


def close_weak_popup():
    if imgui.is_topmost():
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


def wrap_text(text: str, width: float, offset=0, func: typing.Callable = imgui.text_unformatted):
    for line in text.split("\n"):
        while line := line.strip():
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
            func(line[:cut])
            line = line[cut:]
            if offset is not None:
                offset = None
                avail = width


def text_context(obj: object, attr: str, setter_extra: typing.Callable = lambda _: None, editable=True, no_icons=False):
    getter = lambda: getattr(obj, attr)
    setter = lambda val: [setattr(obj, attr, val), setter_extra(val)]
    if imgui.selectable(f"{icons.content_copy} Copy", False)[0]:
        callbacks.clipboard_copy(getter())
    if editable:
        if imgui.selectable(f"{icons.content_paste} Paste", False)[0]:
            setter(getter() + callbacks.clipboard_paste())
        if imgui.selectable(f"{icons.trash_can_outline} Clear", False)[0]:
            setter("")
        if no_icons:
            return
        if imgui.selectable(f"{icons.tooltip_image} Icons", False)[0]:
            search = type("_", (), dict(_=""))()
            def popup_content():
                nonlocal search
                imgui.set_next_item_width(-imgui.FLOAT_MIN)
                _, search._ = imgui.input_text_with_hint(f"###text_context_icons_search", "Search icons...", search._)
                if imgui.begin_popup_context_item(f"###text_context_icons_search_context"):
                    text_context(search, "_", no_icons=True)
                    imgui.end_popup()
                imgui.begin_child(f"###text_context_icons_frame", width=globals.gui.scaled(350), height=imgui.io.display_size.y * 0.5)
                for name, icon in icons.names.items():
                    if not search._ or search._ in name:
                        if imgui.selectable(f"{icon}  {name}", False, flags=imgui.SELECTABLE_DONT_CLOSE_POPUPS)[0]:
                            setter(getter() + icon)
                imgui.end_child()
            push_popup(popup, "Select icon", popup_content, buttons=True, closable=True, outside=True)


@functools.cache
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


popup_flags: int = (
    imgui.WINDOW_NO_MOVE |
    imgui.WINDOW_NO_RESIZE |
    imgui.WINDOW_NO_COLLAPSE |
    imgui.WINDOW_NO_SAVED_SETTINGS |
    imgui.WINDOW_ALWAYS_AUTO_RESIZE
)

def popup(label: str, popup_content: typing.Callable, buttons: dict[str, typing.Callable] = None, closable=True, outside=True, popup_uuid: str = ""):
    if buttons is True:
        buttons = {
            f"{icons.check} Ok": None
        }
    label = label + "###popup_" + popup_uuid
    if not imgui.is_popup_open(label):
        imgui.open_popup(label)
    closed = False
    opened = 1
    constrain_next_window()
    center_next_window()
    if imgui.begin_popup_modal(label, closable or None, flags=popup_flags)[0]:
        if outside:
             closed = closed or close_weak_popup()
        imgui.begin_group()
        closed = (popup_content() is True) or closed  # Close if content returns True
        imgui.end_group()
        imgui.spacing()
        if buttons:
            btns_width = sum(imgui.calc_text_size(name).x for name in buttons) + (2 * len(buttons) * imgui.style.frame_padding.x) + (imgui.style.item_spacing.x * (len(buttons) - 1))
            cur_pos_x = imgui.get_cursor_pos_x()
            new_pos_x = cur_pos_x + imgui.get_content_region_available_width() - btns_width
            if new_pos_x > cur_pos_x:
                imgui.set_cursor_pos_x(new_pos_x)
            for text, callback in buttons.items():
                if imgui.button(text):
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
    popup_func = functools.partial(*args, **kwargs, popup_uuid=f"{time.time()}{rand_num_str()}")
    if globals.gui:
        if (globals.gui.hidden or not globals.gui.focused) and (len(args) > 3) and (args[0] is msgbox.msgbox) and (args[3] in (MsgBox.warn, MsgBox.error)):
            if globals.gui.hidden and args[1] == "Daily backups":
                return
            globals.gui.tray.push_msg(title="Oops", msg="Something went wrong, click here to view the error.", icon=QSystemTrayIcon.MessageIcon.Critical)
    if bottom:
        globals.popup_stack.insert(0, popup_func)
    else:
        globals.popup_stack.append(popup_func)
    return popup_func
