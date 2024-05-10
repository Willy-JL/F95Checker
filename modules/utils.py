from PyQt6.QtWidgets import QSystemTrayIcon
import OpenGL.GL as gl
from PIL import Image, ImageFile
import concurrent
import functools
import asyncio
import typing
import random
import socket
import imgui
import time
import math
import glfw
import sys
import re
import io

from modules.structs import (
    Popup,
)
from modules import (
    globals,
    async_thread,
    callbacks,
    msgbox,
    icons,
    api,
)


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


def image_ext(data: bytes):
    try:
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        ext = str(Image.open(io.BytesIO(data)).format or "img").lower()
    except Exception:
        ext = "img"
    return ext


def custom_id():
    return min(min(game.id for game in globals.games.values()), 0) - 1


def is_uri(text: str):
    # See https://www.rfc-editor.org/rfc/rfc3986#section-3.1
    return bool(re.search(r"^[A-Za-z][A-Za-z0-9\+\-\.]*://", text))


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
    async def coro_wrapper():
        await coro
        await asyncio.sleep(0.5)
    globals.refresh_task = async_thread.run(coro_wrapper())
    globals.gui.tray.update_status()
    def done_callback(future: asyncio.Future):
        globals.refresh_task = None
        globals.gui.tray.update_status()
        globals.gui.require_sort = True
        if (globals.gui.hidden or not globals.gui.focused) and (count := len(globals.updated_games)) > 0:
            globals.gui.tray.push_msg(
                title="Updates",
                msg=f"{count} item{'' if count == 1 else 's'} in your library {'has' if count == 1 else 'have'} received updates, "
                    f"click here to view {'it' if count == 1 else 'them'}.",
                icon=QSystemTrayIcon.MessageIcon.Information
            )
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
            if size.x > 50 and size.y > 50:
                # Valid geometry
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
        if imgui.selectable(f"{icons.tooltip_image_outline} Icons", False)[0]:
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
            push_popup(
                popup, "Select icon",
                popup_content,
                buttons=True,
                closable=True,
                outside=True
            )


@functools.cache
def clean_thread_url(url: str):
    thread = re.search(r"threads/([^/]*)", url).group(1)
    return f"{api.threads_page}{thread}/"


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

def popup(label: str, popup_content: typing.Callable, buttons: dict[str, typing.Callable] = None, closable=True, outside=True, footer="", popup_uuid: str = ""):
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
        imgui.begin_group()
        closed = (popup_content() is True) or closed  # Close if content returns True
        imgui.end_group()
        imgui.spacing()
        if buttons or footer:
            right_width = 0
            if footer:
                right_width += imgui.calc_text_size(footer).x
            if buttons:
                right_width += (
                    sum(imgui.calc_text_size(name).x for name in buttons) +
                    (2 * len(buttons) * imgui.style.frame_padding.x) +
                    (imgui.style.item_spacing.x * (len(buttons) - (not footer)))
                )
            cur_pos_x = imgui.get_cursor_pos_x()
            new_pos_x = cur_pos_x + imgui.get_content_region_available_width() - right_width
            if new_pos_x > cur_pos_x:
                imgui.set_cursor_pos_x(new_pos_x)
            if footer:
                imgui.align_text_to_frame_padding()
                imgui.text(footer)
                imgui.same_line()
            if buttons:
                for text, callback in buttons.items():
                    if imgui.button(text):
                        if callback:
                            callback()
                        imgui.close_current_popup()
                        closed = True
                    imgui.same_line()
        if outside:
             closed = closed or close_weak_popup()
    else:
        opened = 0
        closed = True
    return opened, closed


def push_popup(*args, bottom=False, **kwargs):
    popup = Popup(*args, **kwargs)
    if globals.gui:
        if (globals.gui.hidden or not globals.gui.focused) and (len(args) > 3) and (args[0] is msgbox.msgbox) and (args[3] in (MsgBox.warn, MsgBox.error)):
            if globals.gui.hidden and args[1] == "Daily backups":
                return
            globals.gui.tray.push_msg(
                title="Oops",
                msg="Something went wrong, click here to view the error.",
                icon=QSystemTrayIcon.MessageIcon.Critical
            )
    if bottom:
        globals.popup_stack.insert(0, popup)
    else:
        globals.popup_stack.append(popup)
    return popup

def simple_invisible_button(label: str):
    imgui.push_style_color(imgui.COLOR_BORDER, 0, 0, 0, 0)
    imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0, 0, 0, 0)
    imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0, 0, 0, 0)
    button = imgui.small_button(label)
    imgui.pop_style_color(3)
    return button

def migrate_old_single_images():
    import os, pathlib
    for item in pathlib.Path(globals.images_path).iterdir():
        if item.is_file():
            dir = item.with_name(item.stem)
            if not dir.exists():
                os.mkdir(dir)
            try:
                os.rename(item.absolute(), dir / f"banner{item.suffix}")
            except FileExistsError:
                pass


def draw_segmented_button(labels: list[str], value: int, width: float = None, height: float = None) -> tuple[bool, int]:
    if not labels:
        return False, 0

    cursor_pos = imgui.get_cursor_pos()
    draw_list = imgui.get_window_draw_list()
    screen_pos = imgui.get_cursor_screen_pos()

    full_b_width = width if width else imgui.get_content_region_available_width()
    b_height = height if height else imgui.get_frame_height()
    b_width = full_b_width / len(labels)

    thickness = imgui.style.frame_border_size
    pillpad = math.ceil(thickness + 0) - 1  # Filled region slightly bigger and covered by lines to make up for float errors
    rounding = globals.settings.style_corner_radius
    text = imgui.get_color_u32_rgba(*globals.settings.style_text)
    border = imgui.get_color_u32_rgba(*globals.settings.style_border)
    accent = imgui.get_color_u32_rgba(*globals.settings.style_accent)

    ret = (False, 0)

    n = len(labels)
    for i, label in enumerate(labels):
        x1 = screen_pos[0] + b_width * i
        if i == value:
            if i == 0:
                flags=imgui.DRAW_ROUND_CORNERS_LEFT
            elif i == n - 1:
                flags=imgui.DRAW_ROUND_CORNERS_RIGHT
            else:
                flags=imgui.DRAW_ROUND_CORNERS_NONE
            draw_list.add_rect_filled(x1 + pillpad, screen_pos[1] + pillpad, x1 + b_width - (pillpad if i == n - 1 else 0), screen_pos[1] + b_height - pillpad, accent, rounding=rounding / 2, flags=flags)
        if i != n - 1:
            draw_list.add_line(x1 + b_width, screen_pos[1], x1 + b_width, screen_pos[1] + b_height - pillpad, border, thickness=thickness)
        while (label_size := imgui.calc_text_size(label)).x > b_width - imgui.STYLE_FRAME_PADDING:
            label = label[:-1]
        draw_list.add_text(x1 + (b_width - label_size.x) / 2, screen_pos[1] + (b_height - label_size.y) / 2, text, label)
        imgui.same_line(cursor_pos[0] + b_width * i)
        if imgui.invisible_button(f"###segmented_button_label_{label}", b_width, b_height):
            ret = (True, i)

    draw_list.add_rect(screen_pos[0], screen_pos[1], screen_pos[0] + full_b_width, screen_pos[1] + b_height, border, rounding=rounding, thickness=thickness, flags=imgui.DRAW_ROUND_CORNERS_ALL)

    return ret


def is_connected():
    try:
        # See if we can resolve the host name - tells us if there is a DNS listening
        host = socket.gethostbyname("one.one.one.one")
        # Connect to the host - tells us if the host is actually reachable
        with socket.create_connection((host, 80), 2):
            return True
    except Exception:
        pass
    return False
