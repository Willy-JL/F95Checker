import asyncio
import builtins
import concurrent.futures
import configparser
import dataclasses
import datetime as dt
import functools
import itertools
import pathlib
import pickle
import platform
import shutil
import sys
import threading
import time
import tomllib

from imgui.integrations.glfw import GlfwRenderer
from PIL import Image
from PyQt6 import (
    QtCore,
    QtGui,
    QtWidgets,
)
import aiohttp
import glfw
import imgui
import OpenGL
import OpenGL.GL as gl

from common.structs import (
    Browser,
    Datestamp,
    DefaultStyle,
    DisplayMode,
    ExeState,
    Filter,
    FilterMode,
    Game,
    Label,
    MsgBox,
    Os,
    ProxyType,
    SortSpec,
    Status,
    Tab,
    Tag,
    TagHighlight,
    TimelineEventType,
    Timestamp,
    TrayMsg,
    Type,
)
from common import parser
from external import (
    async_thread,
    error,
    filepicker,
    imagehelper,
    ratingwidget,
)
from modules import (
    api,
    callbacks,
    colors,
    db,
    globals,
    icons,
    msgbox,
    rpc_thread,
    rpdl,
    utils,
)

tool_page         = api.f95_threads_page + "44173/"
github_page       = "https://github.com/Willy-JL/F95Checker"
developer_page    = "https://linktr.ee/WillyJL"

imgui.io = None
imgui.style = None


class Columns:

    @dataclasses.dataclass(slots=True)
    class Column:
        cols: object
        name: str
        flags: int = 0
        ghost: bool = False
        default: bool = False
        hideable: bool = True
        sortable: bool = False
        resizable: bool = True
        enabled: bool = None
        no_header: str = False
        short_header: str = False
        header: str = None
        index: int = None

        def __post_init__(self):
            # Header
            if self.ghost or self.no_header:
                self.header = "##" + self.name[2:]
            elif self.short_header:
                self.header = self.name[:1]
            else:
                self.header = self.name[2:]
            # Flags
            if self.ghost:
                self.flags |= (
                    imgui.TABLE_COLUMN_NO_SORT |
                    imgui.TABLE_COLUMN_NO_RESIZE |
                    imgui.TABLE_COLUMN_NO_REORDER |
                    imgui.TABLE_COLUMN_NO_HEADER_WIDTH
                )
            if not self.default:
                self.flags |= imgui.TABLE_COLUMN_DEFAULT_HIDE
            if not self.hideable:
                self.flags |= imgui.TABLE_COLUMN_NO_HIDE
            if not self.sortable:
                self.flags |= imgui.TABLE_COLUMN_NO_SORT
            if not self.resizable:
                self.flags |= imgui.TABLE_COLUMN_NO_RESIZE
            # Add to outer class
            self.cols.items.append(self)
            self.cols.count = len(self.cols.items)
            self.index = self.cols.count - 1

    def __init__(self):
        self.items = []
        self.count = 0
        # Ghosts (more info in MainGUI.draw_games_list())
        self.manual_sort = self.Column(
            self, f"{icons.cursor_move} Manual Sort",
            ghost=True,
        )
        self.version = self.Column(
            self, f"{icons.star_shooting} Version",
            ghost=True,
            default=True,
        )
        self.finished_version = self.Column(
            self, f"{icons.flag_checkered} Finished Version",
            ghost=True,
        )
        self.installed_version = self.Column(
            self, f"{icons.download} Installed Version",
            ghost=True,
        )
        self.status = self.Column(
            self, f"{icons.checkbox_marked_circle} Status (after name)",
            ghost=True,
            default=True,
        )
        self.separator = self.Column(
            self, "-----------------------------------",
            ghost=True,
            default=True,
            hideable=False,
        )
        # Regulars
        self.play_button = self.Column(
            self, f"{icons.play} Play Button",
            default=True,
            resizable=False,
            no_header=True,
        )
        self.type = self.Column(
            self, f"{icons.book_information_variant} Type",
            default=True,
            sortable=True,
            resizable=False,
        )
        self.name = self.Column(
            self, f"{icons.gamepad_variant} Name",
            imgui.TABLE_COLUMN_WIDTH_STRETCH | imgui.TABLE_COLUMN_DEFAULT_SORT,
            default=True,
            sortable=True,
            hideable=False,
        )
        self.developer = self.Column(
            self, f"{icons.account} Developer",
            sortable=True,
        )
        self.last_updated = self.Column(
            self, f"{icons.update} Last Updated",
            default=True,
            sortable=True,
            resizable=False,
        )
        self.last_launched = self.Column(
            self, f"{icons.play} Last Launched",
            sortable=True,
            resizable=False,
        )
        self.added_on = self.Column(
            self, f"{icons.plus} Added On",
            sortable=True,
            resizable=False,
        )
        self.finished = self.Column(
            self, f"{icons.flag_checkered} Finished",
            default=True,
            sortable=True,
            resizable=False,
            short_header=True,
        )
        self.installed = self.Column(
            self, f"{icons.download} Installed",
            default=True,
            sortable=True,
            resizable=False,
            short_header=True,
        )
        self.rating = self.Column(
            self, f"{icons.star} Rating",
            sortable=True,
            resizable=False,
        )
        self.notes = self.Column(
            self, f"{icons.draw_pen} Notes",
            sortable=True,
        )
        self.open_thread = self.Column(
            self, f"{icons.open_in_new} Open Thread",
            default=True,
            resizable=False,
            no_header=True,
        )
        self.copy_link = self.Column(
            self, f"{icons.content_copy} Copy Link",
            resizable=False,
            no_header=True,
        )
        self.open_folder = self.Column(
            self, f"{icons.folder_open_outline} Open Folder",
            resizable=False,
            no_header=True,
        )
        self.status_standalone = self.Column(
            self, f"{icons.checkbox_marked_circle} Status (own column)",
            sortable=True,
            resizable=False,
            no_header=True,
        )
        self.score = self.Column(
            self, f"{icons.message_star} Forum Score",
            sortable=True,
            resizable=False,
            short_header=True,
        )

cols = Columns()


@functools.cache
def _scaled(mult: float, size: int | float):
    return size * mult


class MainGUI():
    def __init__(self):
        # Constants
        self.sidebar_size = 234
        self.window_flags: int = (
            imgui.WINDOW_NO_MOVE |
            imgui.WINDOW_NO_RESIZE |
            imgui.WINDOW_NO_COLLAPSE |
            imgui.WINDOW_NO_TITLE_BAR |
            imgui.WINDOW_NO_SCROLLBAR |
            imgui.WINDOW_NO_SCROLL_WITH_MOUSE
        )
        self.tabbar_flags: int = (
            imgui.TAB_BAR_FITTING_POLICY_SCROLL
        )
        self.game_list_table_flags: int = (
            imgui.TABLE_SCROLL_Y |
            imgui.TABLE_HIDEABLE |
            imgui.TABLE_SORTABLE |
            imgui.TABLE_RESIZABLE |
            imgui.TABLE_SORT_MULTI |
            imgui.TABLE_REORDERABLE |
            imgui.TABLE_ROW_BACKGROUND |
            imgui.TABLE_SIZING_FIXED_FIT |
            imgui.TABLE_NO_HOST_EXTEND_Y |
            imgui.TABLE_NO_BORDERS_IN_BODY_UTIL_RESIZE
        )
        self.game_grid_table_flags: int = (
            imgui.TABLE_SCROLL_Y |
            imgui.TABLE_PAD_OUTER_X |
            imgui.TABLE_NO_HOST_EXTEND_Y |
            imgui.TABLE_SIZING_FIXED_SAME |
            imgui.TABLE_NO_SAVED_SETTINGS
        )
        self.game_kanban_table_flags: int = (
            imgui.TABLE_SCROLL_X |
            imgui.TABLE_SCROLL_Y |
            imgui.TABLE_PAD_OUTER_X |
            imgui.TABLE_REORDERABLE |
            imgui.TABLE_NO_HOST_EXTEND_Y |
            imgui.TABLE_SIZING_FIXED_SAME |
            imgui.TABLE_BORDERS_INNER_VERTICAL
        )
        self.game_hitbox_drag_drop_flags: int = (
            imgui.DRAG_DROP_ACCEPT_PEEK_ONLY |
            imgui.DRAG_DROP_SOURCE_ALLOW_NULL_ID |
            imgui.DRAG_DROP_SOURCE_NO_PREVIEW_TOOLTIP
        )
        self.watermark_text = f"F95Checker {globals.version_name}{'' if not globals.release else ' by WillyJL'}"

        # Variables
        self.hidden = False
        self.focused = True
        self.minimized = False
        self.filtering = False
        self.add_box_text = ""
        self.new_styles = False
        self.prev_size = (0, 0)
        self.screen_pos = (0, 0)
        self.repeat_chars = False
        self.scroll_percent = 0.0
        self.prev_manual_sort = 0
        self.add_box_valid = False
        self.bg_mode_paused = False
        self.recalculate_ids = True
        self.current_tab: Tab = None
        self.selected_games_count = 0
        self.game_hitbox_click = False
        self.hovered_game: Game = None
        self.sorts: list[SortSpec] = []
        self.filters: list[Filter] = []
        self.poll_chars: list[int] = []
        self.refresh_ratio_smooth = 0.0
        self.bg_mode_timer: float = None
        self.input_chars: list[int] = []
        self.switched_display_mode = False
        self.type_label_width: float = None
        self.last_selected_game: Game = None
        self.prev_filters: list[Filter] = []
        self.ghost_columns_enabled_count = 0
        self.bg_mode_notifs_timer: float = None
        self.show_games_ids: dict[Tab, list[int]] = {}

        # Setup Qt objects
        self.qt_app = QtWidgets.QApplication(sys.argv)
        self.tray = TrayIcon(self)

        # Setup ImGui
        imgui.create_context()
        imgui.io = imgui.get_io()
        imgui.io.ini_file_name = str(globals.data_path / "imgui.ini")
        imgui.io.config_drag_click_to_input_text = True
        imgui.io.config_cursor_blink = False
        size = tuple()
        pos = tuple()
        try:
            # Get window size
            with open(imgui.io.ini_file_name, "r") as f:
                ini = f.read()
            imgui.load_ini_settings_from_memory(ini)
            start = ini.find("[Window][F95Checker]")
            assert start != -1
            end = ini.find("\n\n", start)
            assert end != -1
            config = configparser.RawConfigParser()
            config.read_string(ini[start:end])
            try:
                size = tuple(int(x) for x in config.get("Window][F95Checker", "Size").split(","))
            except Exception:
                pass
            try:
                pos = tuple(int(x) for x in config.get("Window][F95Checker", "ScreenPos").split(","))
            except Exception:
                pass
        except Exception:
            pass
        if not all(type(x) is int for x in size) or not len(size) == 2:
            size = (1280, 720)

        # Setup GLFW
        if not glfw.init():
            print("Could not initialize OpenGL context")
            sys.exit(1)
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)  # OS X supports only forward-compatible core profiles from 3.2

        # Create a windowed mode window and its OpenGL context
        self.window: glfw._GLFWwindow = glfw.create_window(*size, "F95Checker", None, None)
        if not self.window:
            print("Could not initialize Window")
            glfw.terminate()
            sys.exit(1)
        glfw.make_context_current(self.window)
        self.impl = GlfwRenderer(self.window)

        # Window position and icon
        if all(type(x) is int for x in pos) and len(pos) == 2 and utils.validate_geometry(*pos, *size):
            glfw.set_window_pos(self.window, *pos)
        self.screen_pos = glfw.get_window_pos(self.window)
        if globals.settings.start_in_background:
            self.hide()
        self.icon_path = globals.self_path / "resources/icons/icon.png"
        self.icon_texture = imagehelper.ImageHelper(self.icon_path)
        glfw.set_window_icon(self.window, 1, Image.open(self.icon_path))

        # Window callbacks
        glfw.set_char_callback(self.window, self.char_callback)
        glfw.set_window_close_callback(self.window, self.close_callback)
        glfw.set_window_iconify_callback(self.window, self.minimize_callback)
        glfw.set_window_focus_callback(self.window, self.focus_callback)
        glfw.set_window_pos_callback(self.window, self.pos_callback)
        glfw.set_drop_callback(self.window, self.drop_callback)
        glfw.swap_interval(globals.settings.vsync_ratio)

        self.refresh_fonts()
        self.load_filters()
        self.load_styles_from_toml()

        # Show errors in threads
        def syncexcepthook(args: threading.ExceptHookArgs):
            if args.exc_type is not msgbox.Exc:
                err = error.text(args.exc_value)
                tb = error.traceback(args.exc_value)
                utils.push_popup(
                    msgbox.msgbox, "Oops!",
                    "Something went wrong in a parallel task of a separate thread:\n"
                    f"{err}",
                    MsgBox.error,
                    more=tb
                )
        threading.excepthook = syncexcepthook
        def asyncexcepthook(future: asyncio.Future):
            try:
                exc = future.exception()
            except concurrent.futures.CancelledError:
                return
            if not exc or type(exc) is msgbox.Exc:
                return
            err = error.text(exc)
            tb = error.traceback(exc)
            if isinstance(exc, (aiohttp.ClientError, asyncio.TimeoutError)):
                utils.push_popup(
                    msgbox.msgbox, "Connection error",
                    "A connection request has failed:\n"
                    f"{err}\n"
                    "\n"
                    "Possible causes include:\n"
                    " - You're not connected to the internet, or your connection is unstable\n"
                    " - Your timeout value is too low, try increasing it in settings\n"
                    " - The server is experiencing difficulties, try waiting a bit and retrying\n"
                    " - The web address is blocked in your country, network, antivirus, DNS or firewall, try a VPN\n"
                    " - You are refreshing with too many connections, try lowering them in settings\n"
                    " - Your retries value is too low, try increasing it in settings (last resort!)",
                    MsgBox.warn,
                    more=tb
                )
                return
            utils.push_popup(
                msgbox.msgbox, "Oops!",
                "Something went wrong in an asynchronous task of a separate thread:\n"
                f"{err}",
                MsgBox.error,
                more=tb
            )
        async_thread.done_callback = asyncexcepthook

        # Load style configuration
        imgui.style = imgui.get_style()
        imgui.style.item_spacing = (imgui.style.item_spacing.y, imgui.style.item_spacing.y)
        imgui.style.colors[imgui.COLOR_MODAL_WINDOW_DIM_BACKGROUND] = (0, 0, 0, 0.5)
        imgui.style.scrollbar_size = 10
        imgui.style.frame_border_size = 1.6
        imgui.style.colors[imgui.COLOR_TABLE_BORDER_STRONG] = (0, 0, 0, 0)
        self.refresh_styles()
        # No redundant vprintf
        imgui.text = imgui.text_unformatted
        # Custom checkbox style
        imgui._checkbox = imgui.checkbox
        def checkbox(label: str, state: bool):
            if state:
                imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND_HOVERED, *imgui.style.colors[imgui.COLOR_BUTTON_HOVERED])
                imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND, *imgui.style.colors[imgui.COLOR_BUTTON_HOVERED])
                imgui.push_style_color(imgui.COLOR_CHECK_MARK, *imgui.style.colors[imgui.COLOR_WINDOW_BACKGROUND])
            ret = imgui._checkbox(label, state)
            if state:
                imgui.pop_style_color(3)
            return ret
        imgui.checkbox = checkbox
        # Custom combo style
        imgui._combo = imgui.combo
        def combo(*args, **kwargs):
            imgui.push_style_color(imgui.COLOR_BUTTON, *imgui.style.colors[imgui.COLOR_BUTTON_HOVERED])
            imgui.push_style_color(imgui.COLOR_HEADER, *imgui.style.colors[imgui.COLOR_BUTTON_HOVERED][:3], 0.5)
            ret = imgui._combo(*args, **kwargs)
            imgui.pop_style_color(2)
            return ret
        imgui.combo = combo
        imgui._begin_combo = imgui.begin_combo
        def begin_combo(*args, **kwargs):
            imgui.push_style_color(imgui.COLOR_BUTTON, *imgui.style.colors[imgui.COLOR_BUTTON_HOVERED])
            ret = imgui._begin_combo(*args, **kwargs)
            imgui.pop_style_color()
            if ret:
                imgui.push_style_color(imgui.COLOR_HEADER, *imgui.style.colors[imgui.COLOR_BUTTON_HOVERED][:3], 0.5)
            return ret
        imgui.begin_combo = begin_combo
        imgui._end_combo = imgui.end_combo
        def end_combo(*args, **kwargs):
            imgui.pop_style_color()
            return imgui._end_combo(*args, **kwargs)
        imgui.end_combo = end_combo
        # Fix clicking into multiline textboxes
        imgui._input_text_multiline = imgui.input_text_multiline
        def input_text_multiline(*args, **kwargs):
            pos = imgui.io.mouse_pos
            imgui.io.mouse_pos = (pos.x - 8, pos.y)
            ret = imgui._input_text_multiline(*args, **kwargs)
            imgui.io.mouse_pos = (pos.x, pos.y)
            return ret
        imgui.input_text_multiline = input_text_multiline
        # Fix some ID hell
        imgui._button = imgui.button
        def button(*args, **kwargs):
            imgui._button(*args, **kwargs)
            return imgui.is_item_clicked()
        imgui.button = button
        imgui._small_button = imgui.small_button
        def small_button(*args, **kwargs):
            imgui._small_button(*args, **kwargs)
            return imgui.is_item_clicked()
        imgui.small_button = small_button
        imgui._invisible_button = imgui.invisible_button
        def invisible_button(*args, **kwargs):
            imgui._invisible_button(*args, **kwargs)
            return imgui.is_item_clicked()
        imgui.invisible_button = invisible_button
        imgui._selectable = imgui.selectable
        def selectable(*args, **kwargs):
            _, selected = imgui._selectable(*args, **kwargs)
            return imgui.is_item_clicked(), selected
        imgui.selectable = selectable
        # Utils
        def push_y(offset: float):
            imgui.begin_group()
            imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() + offset)
        imgui.push_y = push_y
        def pop_y():
            imgui.end_group()
        imgui.pop_y = pop_y
        def push_no_interaction():
            imgui.internal.push_item_flag(imgui.internal.ITEM_DISABLED, True)
        imgui.push_no_interaction = push_no_interaction
        def pop_no_interaction():
            imgui.internal.pop_item_flag()
        imgui.pop_no_interaction = pop_no_interaction
        def push_alpha(amount: float):
            imgui.push_style_var(imgui.STYLE_ALPHA, imgui.style.alpha * amount)
        imgui.push_alpha = push_alpha
        def pop_alpha():
            imgui.pop_style_var()
        imgui.pop_alpha = pop_alpha
        def push_disabled():
            imgui.push_no_interaction()
            imgui.push_alpha(0.5)
        imgui.push_disabled = push_disabled
        def pop_disabled():
            imgui.pop_alpha()
            imgui.pop_no_interaction()
        imgui.pop_disabled = pop_disabled
        def is_topmost():
            return not imgui.is_popup_open("", imgui.POPUP_ANY_POPUP_ID)
        imgui.is_topmost = is_topmost

    def refresh_styles(self):
        _ = \
            imgui.style.colors[imgui.COLOR_CHECK_MARK] = \
            imgui.style.colors[imgui.COLOR_TAB_ACTIVE] = \
            imgui.style.colors[imgui.COLOR_SLIDER_GRAB] = \
            imgui.style.colors[imgui.COLOR_TAB_HOVERED] = \
            imgui.style.colors[imgui.COLOR_BUTTON_ACTIVE] = \
            imgui.style.colors[imgui.COLOR_HEADER_ACTIVE] = \
            imgui.style.colors[imgui.COLOR_NAV_HIGHLIGHT] = \
            imgui.style.colors[imgui.COLOR_PLOT_HISTOGRAM] = \
            imgui.style.colors[imgui.COLOR_HEADER_HOVERED] = \
            imgui.style.colors[imgui.COLOR_BUTTON_HOVERED] = \
            imgui.style.colors[imgui.COLOR_SEPARATOR_ACTIVE] = \
            imgui.style.colors[imgui.COLOR_SEPARATOR_HOVERED] = \
            imgui.style.colors[imgui.COLOR_RESIZE_GRIP_ACTIVE] = \
            imgui.style.colors[imgui.COLOR_RESIZE_GRIP_HOVERED] = \
            imgui.style.colors[imgui.COLOR_TAB_UNFOCUSED_ACTIVE] = \
            imgui.style.colors[imgui.COLOR_SCROLLBAR_GRAB_ACTIVE] = \
            imgui.style.colors[imgui.COLOR_FRAME_BACKGROUND_ACTIVE] = \
            imgui.style.colors[imgui.COLOR_TITLE_BACKGROUND_ACTIVE] = \
            imgui.style.colors[imgui.COLOR_TEXT_SELECTED_BACKGROUND] = \
        globals.settings.style_accent
        _ = \
            imgui.style.colors[imgui.COLOR_TAB] = \
            imgui.style.colors[imgui.COLOR_RESIZE_GRIP] = \
            imgui.style.colors[imgui.COLOR_TAB_UNFOCUSED] = \
            imgui.style.colors[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = \
        (*globals.settings.style_accent[:3], 0.25)
        _ = \
            imgui.style.colors[imgui.COLOR_TABLE_HEADER_BACKGROUND] = \
            imgui.style.colors[imgui.COLOR_TABLE_ROW_BACKGROUND_ALT] = \
        globals.settings.style_alt_bg
        _ = \
            imgui.style.colors[imgui.COLOR_BUTTON] = \
            imgui.style.colors[imgui.COLOR_HEADER] = \
            imgui.style.colors[imgui.COLOR_FRAME_BACKGROUND] = \
            imgui.style.colors[imgui.COLOR_CHILD_BACKGROUND] = \
            imgui.style.colors[imgui.COLOR_POPUP_BACKGROUND] = \
            imgui.style.colors[imgui.COLOR_TITLE_BACKGROUND] = \
            imgui.style.colors[imgui.COLOR_WINDOW_BACKGROUND] = \
            imgui.style.colors[imgui.COLOR_SLIDER_GRAB_ACTIVE] = \
            imgui.style.colors[imgui.COLOR_SCROLLBAR_BACKGROUND] = \
        globals.settings.style_bg
        _ = \
            imgui.style.colors[imgui.COLOR_BORDER] = \
            imgui.style.colors[imgui.COLOR_SEPARATOR] = \
        globals.settings.style_border
        _ = \
            imgui.style.tab_rounding  = \
            imgui.style.grab_rounding = \
            imgui.style.frame_rounding = \
            imgui.style.child_rounding = \
            imgui.style.popup_rounding = \
            imgui.style.window_rounding = \
            imgui.style.scrollbar_rounding = \
        self.scaled(globals.settings.style_corner_radius)
        _ = \
            imgui.style.colors[imgui.COLOR_TEXT] = \
        globals.settings.style_text
        _ = \
            imgui.style.colors[imgui.COLOR_TEXT_DISABLED] = \
        globals.settings.style_text_dim
        self.qt_app.setStyleSheet(f"""
            QMenu {{
                padding: 5px;
                background-color: {colors.rgba_0_1_to_hex(globals.settings.style_bg)[:-2]};
            }}
            QMenu::item {{
                margin: 1px;
                padding: 2px 7px 2px 7px;
                border-radius: {globals.settings.style_corner_radius};
                color: {colors.rgba_0_1_to_hex(globals.settings.style_text)[:-2]};
            }}
            QMenu::item:disabled {{
                color: {colors.rgba_0_1_to_hex(globals.settings.style_text_dim)[:-2]};
            }}
            QMenu::item:selected:enabled {{
                background-color: {colors.rgba_0_1_to_hex(globals.settings.style_accent)[:-2]};
            }}
        """)

    def refresh_fonts(self):
        imgui.io.fonts.clear()
        max_tex_size = gl.glGetIntegerv(gl.GL_MAX_TEXTURE_SIZE)
        imgui.io.fonts.texture_desired_width = max_tex_size
        win_w, win_h = glfw.get_window_size(self.window)
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        font_scaling_factor = max(fb_w / win_w, fb_h / win_h)
        imgui.io.font_global_scale = 1 / font_scaling_factor
        karlar_path = str(next(globals.self_path.glob("resources/fonts/Karla-Regular.*.ttf")))
        karlab_path = str(next(globals.self_path.glob("resources/fonts/Karla-Bold.*.ttf")))
        meslo_path  = str(next(globals.self_path.glob("resources/fonts/MesloLGS-Regular.*.ttf")))
        noto_path   = str(next(globals.self_path.glob("resources/fonts/NotoSans-Regular.*.ttf")))
        mdi_path    = str(icons.font_path)
        merge = dict(merge_mode=True)
        oversample = dict(oversample_h=2, oversample_v=2)
        karla_config = imgui.core.FontConfig(         glyph_offset_y=-0.5, **oversample)
        meslo_config = imgui.core.FontConfig(                              **oversample)
        noto_config  = imgui.core.FontConfig(**merge, glyph_offset_y=-0.5, **oversample)
        mdi_config   = imgui.core.FontConfig(**merge, glyph_offset_y=+1.0)
        karla_range = imgui.core.GlyphRanges([0x1,            0x25ca,         0])
        meslo_range = imgui.core.GlyphRanges([0x1,            0x2e2e,         0])
        noto_range  = imgui.core.GlyphRanges([0x1,            0xfffd,         0])
        mdi_range   = imgui.core.GlyphRanges([icons.min_char, icons.max_char, 0])
        msgbox_range_values = []
        for icon in [icons.information, icons.alert_rhombus, icons.alert_octagon]:
            msgbox_range_values += [ord(icon), ord(icon)]
        msgbox_range_values.append(0)
        msgbox_range = imgui.core.GlyphRanges(msgbox_range_values)
        size_14 = round(self.scaled(14 * font_scaling_factor))
        size_15 = round(self.scaled(15 * font_scaling_factor))
        size_17 = round(self.scaled(17 * font_scaling_factor))
        size_18 = round(self.scaled(18 * font_scaling_factor))
        size_22 = round(self.scaled(22 * font_scaling_factor))
        size_28 = round(self.scaled(28 * font_scaling_factor))
        size_32 = round(self.scaled(32 * font_scaling_factor))
        size_69 = round(self.scaled(69 * font_scaling_factor))
        fonts = type("FontStore", (), {})()
        imgui.fonts = fonts
        add_font = imgui.io.fonts.add_font_from_file_ttf
        # Default font + more glyphs + icons
        fonts.default = add_font(karlar_path, size_18, font_config=karla_config, glyph_ranges=karla_range)
        add_font(                noto_path,   size_18, font_config=noto_config,  glyph_ranges=noto_range)
        add_font(                mdi_path,    size_18, font_config=mdi_config,   glyph_ranges=mdi_range)
        # Bold font + more glyphs + icons
        fonts.bold    = add_font(karlab_path, size_22, font_config=karla_config, glyph_ranges=karla_range)
        add_font(                noto_path,   size_22, font_config=noto_config,  glyph_ranges=noto_range)
        add_font(                mdi_path,    size_18, font_config=mdi_config,   glyph_ranges=mdi_range)
        # Big font + more glyphs + icons
        fonts.big     = add_font(karlab_path, size_32, font_config=karla_config, glyph_ranges=karla_range)
        add_font(                noto_path,   size_32, font_config=noto_config,  glyph_ranges=noto_range)
        add_font(                mdi_path,    size_28, font_config=mdi_config,   glyph_ranges=mdi_range)
        # Small font + more glyphs + icons
        fonts.small   = add_font(karlar_path, size_14, font_config=karla_config, glyph_ranges=karla_range)
        add_font(                noto_path,   size_14, font_config=noto_config,  glyph_ranges=noto_range)
        add_font(                mdi_path,    size_14, font_config=mdi_config,   glyph_ranges=mdi_range)
        # Monospace font for some dates
        fonts.mono    = add_font(meslo_path,  size_17, font_config=meslo_config, glyph_ranges=meslo_range)
        # Small monospace font for more info dropdowns
        fonts.mono_sm = add_font(meslo_path,  size_15, font_config=meslo_config, glyph_ranges=meslo_range)
        # MsgBox type icons/thumbnails
        fonts.msgbox  = add_font(mdi_path,    size_69,                           glyph_ranges=msgbox_range)
        try:
            self.impl.refresh_font_texture()
        except Exception:
            if globals.settings.interface_scaling == 1.0:
                raise
            globals.settings.interface_scaling = 1.0
            async_thread.run(db.update_settings("interface_scaling"))
            return self.refresh_fonts()
        self.type_label_width = None

    def save_filters(self):
        with open(globals.data_path / "filters.pkl", "wb") as file:
            pickle.dump(self.filters, file)

    def load_filters(self):
        try:
            with open(globals.data_path / "filters.pkl", "rb") as file:
                self.filters = pickle.load(file)
        except Exception:
            self.filters = []

    def load_styles_from_toml(self):
        if not (path := pathlib.Path(globals.data_path / 'styles.toml')).exists():
            return
        try:
            with open(path, 'rb') as file:
                styles = tomllib.load(file)
                globals.settings.style_corner_radius = styles.get("corner_radius", DefaultStyle.corner_radius)
                globals.settings.style_accent        = colors.hex_to_rgba_0_1(styles.get("accent", DefaultStyle.accent))
                globals.settings.style_bg            = colors.hex_to_rgba_0_1(styles.get("bg", DefaultStyle.bg))
                globals.settings.style_alt_bg        = colors.hex_to_rgba_0_1(styles.get("alt_bg", DefaultStyle.alt_bg))
                globals.settings.style_border        = colors.hex_to_rgba_0_1(styles.get("border", DefaultStyle.border))
                globals.settings.style_text          = colors.hex_to_rgba_0_1(styles.get("text", DefaultStyle.text))
                globals.settings.style_text_dim      = colors.hex_to_rgba_0_1(styles.get("text_dim", DefaultStyle.text_dim))
                self.new_styles = True
                self.refresh_styles()
        except Exception:
            pass

    def close(self, *_, **__):
        glfw.set_window_should_close(self.window, True)

    def char_callback(self, window: glfw._GLFWwindow, char: int):
        self.impl.char_callback(window, char)
        self.poll_chars.append(char)

    def close_callback(self, window: glfw._GLFWwindow):
        if globals.settings.background_on_close:
            self.hide()
            glfw.set_window_should_close(self.window, False)

    def minimize_callback(self, window: glfw._GLFWwindow, minimized: int):
        self.minimized = minimized

    def focus_callback(self, window: glfw._GLFWwindow, focused: int):
        self.focused = focused

    def pos_callback(self, window: glfw._GLFWwindow, x: int, y: int):
        if not glfw.get_window_attrib(self.window, glfw.ICONIFIED):
            self.screen_pos = (x, y)

    def drop_callback(self, window: glfw._GLFWwindow, items: list[str]):
        paths = [pathlib.Path(item) for item in items]
        if globals.popup_stack and isinstance(picker := getattr(globals.popup_stack[-1].func, "__self__", None), filepicker.FilePicker):
            path = paths[0]
            if (picker.dir_picker and path.is_dir()) or (not picker.dir_picker and path.is_file()):
                picker.selected = str(path)
                if picker.callback:
                    picker.callback(picker.selected)
                picker.active = False
        else:
            for path in paths:
                if path.suffix and path.suffix.lower() == ".html":
                    async_thread.run(api.import_browser_bookmarks(path))
                elif path.suffix and path.suffix.lower() == ".url":
                    async_thread.run(api.import_url_shortcut(path))

    def hide(self, *_, **__):
        self.screen_pos = glfw.get_window_pos(self.window)
        glfw.hide_window(self.window)
        self.hidden = True
        self.tray.update_status()

    def show(self, *_, **__):
        self.bg_mode_timer = None
        self.bg_mode_notifs_timer = None
        if not self.hidden:
            glfw.hide_window(self.window)
        glfw.show_window(self.window)
        if utils.validate_geometry(*self.screen_pos, *self.prev_size):
            glfw.set_window_pos(self.window, *self.screen_pos)
        glfw.focus_window(self.window)
        self.hidden = False
        self.tray.update_status()

    def scaled(self, size: int | float):
        return _scaled(globals.settings.interface_scaling, size)

    def main_loop(self):
        if globals.settings.start_refresh and not self.hidden:
            utils.start_refresh_task(api.refresh())
        # Loop variables
        prev_scaling = globals.settings.interface_scaling
        prev_any_hovered = None
        prev_win_hovered = None
        prev_mouse_pos = None
        prev_minimized = None
        scroll_energy = 0.0
        prev_focused = None
        any_hovered = False
        win_hovered = None
        prev_cursor = None
        prev_hidden = None
        draw_next = 5.0
        size = (0, 0)
        cursor = -1
        try:
            # While window is open
            while not glfw.window_should_close(self.window):
                # Tick events and inputs
                prev_mouse_pos = imgui.io.mouse_pos
                prev_minimized = self.minimized
                prev_win_hovered = win_hovered
                prev_any_hovered = any_hovered
                prev_focused = self.focused
                prev_hidden = self.hidden
                self.prev_size = size
                prev_cursor = cursor
                self.tray.tick_msgs()
                self.qt_app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents)
                glfw.make_context_current(self.window)
                if self.repeat_chars:
                    for char in self.input_chars:
                        imgui.io.add_input_character(char)
                    self.repeat_chars = False
                self.input_chars.clear()
                glfw.poll_events()
                self.input_chars, self.poll_chars = self.poll_chars, self.input_chars
                self.impl.process_inputs()
                imagehelper.apply_textures()
                # Window state handling
                size = imgui.io.display_size
                mouse_pos = imgui.io.mouse_pos
                cursor = imgui.get_mouse_cursor()
                any_hovered = imgui.is_any_item_hovered()
                win_hovered = glfw.get_window_attrib(self.window, glfw.HOVERED)
                if not self.focused and win_hovered:
                    # GlfwRenderer (self.impl) resets cursor pos if not focused, making it unresponsive
                    imgui.io.mouse_pos = glfw.get_cursor_pos(self.window)
                if not self.hidden and not self.minimized and (self.focused or globals.settings.render_when_unfocused):

                    # Scroll modifiers (must be before new_frame())
                    imgui.io.mouse_wheel *= globals.settings.scroll_amount
                    if globals.settings.scroll_smooth:

                        if scroll_energy * imgui.io.mouse_wheel < 0: # fast check if signs are opposite
                            # we want to immediately reverse rather than slowly decelerating.
                            scroll_energy = 0.0

                        scroll_energy += imgui.io.mouse_wheel
                        if abs(scroll_energy) > 0.1:
                            scroll_now = scroll_energy * imgui.io.delta_time * globals.settings.scroll_smooth_speed
                            scroll_energy -= scroll_now
                        else:
                            scroll_now = 0.0
                            scroll_energy = 0.0
                        imgui.io.mouse_wheel = scroll_now

                    # Redraw only when needed
                    draw = (
                        (api.downloads and any(dl.state in (dl.State.Verifying, dl.State.Extracting) for dl in api.downloads.values()))
                        or imgui.io.mouse_wheel or self.input_chars or any(imgui.io.mouse_down) or any(imgui.io.keys_down)
                        or (prev_mouse_pos != mouse_pos and (prev_win_hovered or win_hovered))
                        or prev_scaling != globals.settings.interface_scaling
                        or prev_minimized != self.minimized
                        or api.session.connector._acquired
                        or prev_focused != self.focused
                        or prev_hidden != self.hidden
                        or size != self.prev_size
                        or self.recalculate_ids
                        or imagehelper.redraw
                        or self.new_styles
                        or api.updating
                    )
                    if draw:
                        draw_next = max(draw_next, imgui.io.delta_time + 1.0)  # Draw for at least next half second
                    if draw_next > 0.0:
                        draw_next -= imgui.io.delta_time

                        # Reactive mouse cursors
                        if cursor != prev_cursor or any_hovered != prev_any_hovered:
                            shape = glfw.ARROW_CURSOR
                            if cursor == imgui.MOUSE_CURSOR_TEXT_INPUT:
                                shape = glfw.IBEAM_CURSOR
                            elif any_hovered:
                                shape = glfw.HAND_CURSOR
                            glfw.set_cursor(self.window, glfw.create_standard_cursor(shape))

                        # Updated games popup
                        if not utils.is_refreshing() and globals.updated_games:
                            updated_games = globals.updated_games.copy()
                            globals.updated_games.clear()
                            sorted_ids = sorted(updated_games, key=lambda id: globals.games[id].type.category.value)
                            utils.push_popup(self.draw_updates_popup, updated_games, sorted_ids)

                        # Start drawing
                        prev_scaling = globals.settings.interface_scaling
                        imgui.new_frame()
                        self.new_styles = False
                        imagehelper.redraw = False

                        # Imgui window is top left of display window, and has same size
                        imgui.set_next_window_position(0, 0, imgui.ONCE)
                        if size != self.prev_size and not self.minimized:
                            imgui.set_next_window_size(*size, imgui.ALWAYS)

                        # Create main window
                        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0)
                        imgui.begin("F95Checker", closable=False, flags=self.window_flags)
                        imgui.pop_style_var()
                        sidebar_size = self.scaled(self.sidebar_size)

                        # Main pane
                        imgui.begin_child("###main_frame", width=-sidebar_size)
                        self.hovered_game = None
                        # Tabbar
                        self.draw_tabbar()
                        # Games container
                        match globals.settings.display_mode.value:
                            case DisplayMode.list.value:
                                self.draw_games_list()
                            case DisplayMode.grid.value:
                                self.draw_games_grid()
                            case DisplayMode.kanban.value:
                                self.draw_games_kanban()
                        # Bottombar
                        self.draw_bottombar()
                        imgui.end_child()

                        # Prepare bottom status / watermark text (done before sidebar to get text offset from bottom of window)
                        if (count := api.images_counter.count) > 0:
                            text = f"Downloading {count} image{'s' if count > 1 else ''}..."
                        elif (count := api.full_checks_counter.count) > 0:
                            text = f"Fetching {count} full thread{'s' if count > 1 else ''}..."
                        elif (count := api.fast_checks_counter) > 0:
                            text = f"Validating {count} cached item{'s' if count > 1 else ''}..."
                        elif api.f95_ratelimit._waiters or api.f95_ratelimit_sleeping.count:
                            text = f"Waiting for F95zone ratelimit..."
                        elif globals.last_update_check is None:
                            text = "Checking for updates..."
                        else:
                            text = self.watermark_text
                        _3 = self.scaled(3)
                        _6 = self.scaled(6)
                        text_size = imgui.calc_text_size(text)
                        text_x = size.x - text_size.x - _6
                        text_y = size.y - text_size.y - _6

                        # Sidebar
                        imgui.same_line(spacing=imgui.style.item_spacing.x)
                        imgui.begin_child("###sidebar_frame", width=sidebar_size - imgui.style.item_spacing.x + 1, height=-text_size.y)
                        self.draw_sidebar()
                        imgui.end_child()

                        # Status / watermark text
                        imgui.set_cursor_screen_pos((text_x - _3, text_y))
                        if imgui.invisible_button("", width=text_size.x + _6, height=text_size.y + _3):
                            utils.push_popup(self.draw_about_popup)
                        elif imgui.is_item_clicked(imgui.MOUSE_BUTTON_MIDDLE):
                            callbacks.open_webpage(api.f95_host)
                        imgui.set_cursor_screen_pos((text_x, text_y))
                        imgui.text(text)

                        # Popups
                        open_popup_count = 0
                        for popup in globals.popup_stack:
                            opened, closed =  popup()
                            if closed:
                                globals.popup_stack.remove(popup)
                            open_popup_count += opened
                        # Popups are closed all at the end to allow stacking
                        for _ in range(open_popup_count):
                            imgui.end_popup()

                        # Close main window (technically popups are inside the window, and inside one another - this gives proper stacking order)
                        imgui.end()

                        # Render interface
                        imgui.render()
                        self.impl.render(imgui.get_draw_data())
                        # Rescale fonts
                        if prev_scaling != globals.settings.interface_scaling:
                            self.refresh_fonts()
                            self.refresh_styles()
                            async_thread.run(db.update_settings("interface_scaling"))
                    # Wait idle time
                        glfw.swap_buffers(self.window)
                    else:
                        time.sleep(1 / 15)
                else:
                    # Tray bg mode and not paused
                    if self.hidden and not self.bg_mode_paused and not utils.is_refreshing():
                        if not self.bg_mode_timer:
                            # Schedule next refresh
                            self.bg_mode_timer = time.time() + globals.settings.bg_refresh_interval * 60
                            self.tray.update_status()
                        elif self.bg_mode_timer and time.time() > self.bg_mode_timer:
                            # Run scheduled refresh
                            self.bg_mode_timer = None
                            utils.start_refresh_task(api.refresh(notifs=False), reset_bg_timers=False)
                        elif globals.settings.check_notifs:
                            if not self.bg_mode_notifs_timer:
                                # Schedule next notif check
                                self.bg_mode_notifs_timer = time.time() + globals.settings.bg_notifs_interval * 60
                                self.tray.update_status()
                            elif self.bg_mode_notifs_timer and time.time() > self.bg_mode_notifs_timer:
                                # Run scheduled notif check
                                self.bg_mode_notifs_timer = None
                                utils.start_refresh_task(api.check_notifs(standalone=True), reset_bg_timers=False)
                    # Wait idle time
                    if self.tray.menu_open:
                        time.sleep(1 / 60)
                    else:
                        time.sleep(1 / 8)  # 8 FPS tray refresh icon
                if utils.is_refreshing():
                    globals.gui.tray.animate_refresh_icon()
        finally:
            # Main loop over, cleanup and close
            self.save_filters()
            imgui.save_ini_settings_to_disk(imgui.io.ini_file_name)
            ini = imgui.save_ini_settings_to_memory()
            try:
                start = ini.find("[Window][F95Checker]")
                assert start != -1
                end = ini.find("\n\n", start)
                assert end != -1
                if "ScreenPos=" not in ini[start:end]:
                    insert = ini.find("\n", start)
                    new_ini = ini[:insert] + f"\nScreenPos={self.screen_pos[0]},{self.screen_pos[1]}" + ini[insert:]
                else:
                    new_ini = ini
            except Exception:
                new_ini = ini
            with open(imgui.io.ini_file_name, "w") as f:
                f.write(new_ini)
            self.impl.shutdown()
            glfw.terminate()

    def draw_hover_text(self, hover_text: str, text="(?)", force=False):
        if text:
            imgui.text_disabled(text)
        if force or imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.push_text_wrap_pos(min(imgui.get_font_size() * 35, imgui.io.display_size.x))
            imgui.text(hover_text)
            imgui.pop_text_wrap_pos()
            imgui.end_tooltip()

    def begin_framed_text(self, color: tuple[float], interaction=True):
        if interaction:
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *color)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *color)
        else:
            imgui.push_no_interaction()
        imgui.push_style_color(imgui.COLOR_BUTTON, *color)
        imgui.push_style_var(imgui.STYLE_FRAME_BORDERSIZE, 0)

    def end_framed_text(self, interaction=True):
        imgui.pop_style_var()
        if interaction:
            imgui.pop_style_color(3)
        else:
            imgui.pop_no_interaction()
            imgui.pop_style_color()

    def get_type_label_width(self):
        if self.type_label_width is None:
            self.type_label_width = 0
            for name in Type._member_names_:
                self.type_label_width = max(self.type_label_width, imgui.calc_text_size(name).x)
            self.type_label_width += 8
        return self.type_label_width

    def draw_type_widget(self, type: Type, wide=True, align=False):
        quick_filter = globals.settings.quick_filters
        self.begin_framed_text(type.color, interaction=quick_filter)
        imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 1.0, 1.0, 1.0)
        if wide:
            x_padding = 4
            backup_y_padding = imgui.style.frame_padding.y
            imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (x_padding, 0))
            if align:
                imgui.push_y(backup_y_padding)
            clicked = imgui.button(type.name, width=self.get_type_label_width())
            if align:
                imgui.pop_y()
            imgui.pop_style_var()
        else:
            clicked = imgui.small_button(type.name)
        if clicked and quick_filter:
            flt = Filter(FilterMode.Type)
            flt.match = type
            self.filters.append(flt)
        imgui.pop_style_color()
        self.end_framed_text(interaction=quick_filter)

    def draw_tag_widget(self, tag: Tag, quick_filter=True, change_highlight=True):
        quick_filter = quick_filter and globals.settings.quick_filters
        interaction = quick_filter or change_highlight
        color = (0.3, 0.3, 0.3, 1.0)
        if globals.settings.highlight_tags:
            if highlight := globals.settings.tags_highlights.get(tag):
                color = highlight.color
        self.begin_framed_text(color, interaction=interaction)
        if imgui.small_button(tag.text) and quick_filter:
            flt = Filter(FilterMode.Tag)
            flt.match = tag
            self.filters.append(flt)
        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_RIGHT) and change_highlight:
            if tag not in globals.settings.tags_highlights:
                globals.settings.tags_highlights[tag] = TagHighlight[TagHighlight._member_names_[0]]
            else:
                highlight = globals.settings.tags_highlights[tag]
                if highlight is TagHighlight[TagHighlight._member_names_[-1]]:
                    del globals.settings.tags_highlights[tag]
                else:
                    globals.settings.tags_highlights[tag] = TagHighlight(highlight + 1)
            async_thread.run(db.update_settings("tags_highlights"))
        self.end_framed_text(interaction=interaction)

    def draw_label_widget(self, label: Label, short=False):
        quick_filter = globals.settings.quick_filters
        self.begin_framed_text(label.color, interaction=quick_filter)
        imgui.push_style_color(imgui.COLOR_TEXT, *colors.foreground_color(label.color))
        if imgui.small_button(label.short_name if short else label.name) and quick_filter:
            flt = Filter(FilterMode.Label)
            flt.match = label
            self.filters.append(flt)
        if short and imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.push_font(imgui.fonts.default)
            self.draw_label_widget(label, short=False)
            imgui.pop_font()
            imgui.end_tooltip()
        imgui.pop_style_color()
        self.end_framed_text(interaction=quick_filter)

    def draw_tab_widget(self, tab: Tab):
        color = (tab and tab.color) or globals.settings.style_accent
        self.begin_framed_text(color, interaction=False)
        imgui.push_style_color(imgui.COLOR_TEXT, *colors.foreground_color(color))
        if (tab and tab.icon) and (tab and (tab.name or 'New Tab')):
            imgui.small_button(f"{tab.icon} {tab.name or 'New Tab'}")
        else:
            imgui.small_button(f"{Tab.first_tab_label()}")
        imgui.pop_style_color()
        self.end_framed_text(interaction=False)

    def draw_status_widget(self, status: Status):
        quick_filter = globals.settings.quick_filters
        if quick_filter:
            imgui.begin_group()
            pos = imgui.get_cursor_pos()
        imgui.text_colored(getattr(icons, status.icon), *status.color)
        if quick_filter:
            imgui.set_cursor_pos(pos)
            if imgui.invisible_button("", *imgui.get_item_rect_size()):
                flt = Filter(FilterMode.Status)
                flt.match = status
                self.filters.append(flt)
            imgui.end_group()

    def draw_game_update_icon(self, game: Game):
        quick_filter = globals.settings.quick_filters
        with imgui.begin_group():
            pos = imgui.get_cursor_pos()
            imgui.text_colored(icons.star_circle, 0.85, 0.85, 0.00)
            imgui.set_cursor_pos(pos)
            imgui.invisible_button("", *imgui.get_item_rect_size())
        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.push_text_wrap_pos(min(imgui.get_font_size() * 35, imgui.io.display_size.x))
            imgui.text("This game has been updated!")
            imgui.text_disabled("Installed:")
            imgui.same_line()
            imgui.text(game.installed or 'N/A')
            imgui.text_disabled("Latest:")
            imgui.same_line()
            imgui.text(game.version)
            imgui.text(
                "To remove this update marker:\n"
                f"{icons.menu_right} Middle click\n"
                f"{icons.menu_right} Alt + Left click\n"
                f"{icons.menu_right} Mark game as installed"
            )
            imgui.pop_text_wrap_pos()
            imgui.end_tooltip()
        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_MIDDLE):
            # Middle click - remove update marker
            game.updated = False
        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_LEFT):
            if imgui.is_key_down(glfw.KEY_LEFT_ALT):
                # Alt + left click - remove update marker
                game.updated = False
            elif quick_filter:
                # Left click - trigger quick filter
                flt = Filter(FilterMode.Updated)
                self.filters.append(flt)

    def draw_game_unknown_tags_icon(self, game: Game):
        with imgui.begin_group():
            pos = imgui.get_cursor_pos()
            imgui.text_colored(icons.progress_tag, 1.00, 0.65, 0.00)
            imgui.set_cursor_pos(pos)
            imgui.invisible_button("", *imgui.get_item_rect_size())
        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.push_text_wrap_pos(min(imgui.get_font_size() * 35, imgui.io.display_size.x))
            imgui.text("This game has new tags that F95Checker failed to recognize:")
            for tag in game.unknown_tags:
                imgui.text(f" - {tag}")
            imgui.text("To copy them:")
            imgui.text(f"{icons.menu_right} Shift + Left click")
            imgui.text(f"{icons.menu_right} Use Copy button in Tags section")
            imgui.text("To remove this marker:")
            imgui.text(f"{icons.menu_right} Middle click")
            imgui.text(f"{icons.menu_right} Alt + Left click")
            imgui.pop_text_wrap_pos()
            imgui.end_tooltip()
        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_MIDDLE):
            # Middle click - remove unknown tags marker
            game.unknown_tags_flag = False
        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_LEFT):
            if imgui.is_key_down(glfw.KEY_LEFT_ALT):
                # Alt + left click - remove unknown tags marker
                game.unknown_tags_flag = False
            elif imgui.is_key_down(glfw.KEY_LEFT_SHIFT):
                # Shift + left click - copy tags to clipboard
                callbacks.clipboard_copy(", ".join(game.unknown_tags))

    def draw_game_archive_icon(self, game: Game):
        quick_filter = globals.settings.quick_filters
        if quick_filter:
            imgui.begin_group()
            pos = imgui.get_cursor_pos()
        imgui.text_disabled(icons.archive)
        if quick_filter:
            imgui.set_cursor_pos(pos)
            if imgui.invisible_button("", *imgui.get_item_rect_size()):
                flt = Filter(FilterMode.Archived)
                self.filters.append(flt)
            imgui.end_group()
        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.push_text_wrap_pos(min(imgui.get_font_size() * 35, imgui.io.display_size.x))
            imgui.text(
                "This game is archived!\n"
                "In this state you won't receive update notifications for\n"
                "this game and it will stay at the bottom of the list.\n"
                "Middle click to remove it from the archive, alternatively\n"
                "use the right click menu to do the same."
            )
            imgui.pop_text_wrap_pos()
            imgui.end_tooltip()
        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_MIDDLE):
            game.archived = False

    def draw_game_more_info_button(self, game: Game, label="", selectable=False, carousel_ids: list = None):
        if selectable:
            clicked = imgui.selectable(label, False)[0]
        else:
            clicked = imgui.button(label)
        if clicked:
            if not game:
                carousel_ids = [game.id for game in globals.games.values() if game.selected]
                game = globals.games[carousel_ids[0]]
            utils.push_popup(self.draw_game_info_popup, game, carousel_ids.copy() if carousel_ids else None)

    def draw_game_play_button(self, game: Game, label="", selectable=False, executable: str = None):
        if game and not game.executables:
            imgui.push_style_color(imgui.COLOR_TEXT, *imgui.style.colors[imgui.COLOR_TEXT_DISABLED][:3], 0.75)
        elif game:
            if executable:
                try:
                    valid = game.executables_valids[game.executables.index(executable)]
                except Exception:
                    valid = False
            else:
                valid = game.executables_valid
            if not valid:
                imgui.push_style_color(imgui.COLOR_TEXT, 0.87, 0.20, 0.20)
        if selectable:
            clicked = imgui.selectable(label, False)[0]
        else:
            clicked = imgui.button(label)
        if game and (not game.executables or not valid):
            imgui.pop_style_color()
        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_MIDDLE):
            if game:
                callbacks.open_game_folder(game, executable=executable)
            else:
                for game in globals.games.values():
                    if game.selected:
                        callbacks.open_game_folder(game)
        elif clicked:
            if game:
                callbacks.launch_game(game, executable=executable)
            else:
                for game in globals.games.values():
                    if game.selected:
                        callbacks.launch_game(game)

    def draw_game_name_text(self, game: Game):
        if game.archived:
            imgui.text_disabled(game.name)
        elif game.finished == game.version:
            imgui.text(game.name)
        else:
            imgui.text_colored(game.name, *globals.settings.style_accent)
        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_MIDDLE):
            callbacks.clipboard_copy(game.name)

    def draw_game_finished_checkbox(self, game: Game, label=""):
        if game:
            installed_finished = game.finished == (game.installed or game.version)
            if installed_finished:
                checkbox = imgui.checkbox
            else:
                checkbox = imgui._checkbox
            changed, _ = checkbox(f"{label}###{game.id}_finished", bool(game.finished))
            if changed:
                if installed_finished:
                    game.finished = ""  # Finished -> Not finished
                else:
                    game.finished = (game.installed or game.version)  # Not finished -> Finished, Outdated finished -> Finished
                    game.add_timeline_event(TimelineEventType.GameFinished, game.version)
            if game.finished and not installed_finished and imgui.is_item_hovered():
                imgui.begin_tooltip()
                imgui.push_text_wrap_pos(min(imgui.get_font_size() * 35, imgui.io.display_size.x))
                imgui.text_disabled("Finished:")
                imgui.same_line()
                imgui.text(game.finished)
                imgui.text_disabled("Installed:")
                imgui.same_line()
                imgui.text(game.installed or 'N/A')
                imgui.text("Click to mark installed as finished.")
                imgui.pop_text_wrap_pos()
                imgui.end_tooltip()
        else:
            if imgui.small_button(icons.check):
                for game in globals.games.values():
                    if game.selected:
                        game.finished = (game.installed or game.version)
                        game.add_timeline_event(TimelineEventType.GameFinished, game.version)
            imgui.same_line()
            if imgui.small_button(icons.close):
                for game in globals.games.values():
                    if game.selected:
                        game.finished = ""
            imgui.same_line()
            imgui.text(label + " ")

    def draw_game_installed_checkbox(self, game: Game, label=""):
        if game:
            latest_installed = game.installed == game.version
            if latest_installed:
                checkbox = imgui.checkbox
            else:
                checkbox = imgui._checkbox
            changed, _ = checkbox(f"{label}###{game.id}_installed", bool(game.installed))
            if changed:
                if latest_installed:
                    game.installed = ""  # Latest installed -> Not installed
                else:
                    game.add_timeline_event(TimelineEventType.GameInstalled, game.version)
                    game.installed = game.version  # Not installed -> Latest installed, Outdated installed -> Latest installed
                    game.updated = False
            if game.installed and not latest_installed and imgui.is_item_hovered():
                imgui.begin_tooltip()
                imgui.push_text_wrap_pos(min(imgui.get_font_size() * 35, imgui.io.display_size.x))
                imgui.text_disabled("Installed:")
                imgui.same_line()
                imgui.text(game.installed or 'N/A')
                imgui.text_disabled("Latest:")
                imgui.same_line()
                imgui.text(game.version)
                imgui.text("Click to mark latest as installed.")
                imgui.pop_text_wrap_pos()
                imgui.end_tooltip()
        else:
            if imgui.small_button(icons.check):
                for game in globals.games.values():
                    if game.selected:
                        game.add_timeline_event(TimelineEventType.GameInstalled, game.version)
                        game.installed = game.version
                        game.updated = False
            imgui.same_line()
            if imgui.small_button(icons.close):
                for game in globals.games.values():
                    if game.selected:
                        game.installed = ""
            imgui.same_line()
            imgui.text(label + " ")

    def draw_game_rating_widget(self, game: Game):
        if not game:
            imgui.text("Set:")
            imgui.same_line()
            if imgui.small_button(icons.close):
                for game in globals.games.values():
                    if game.selected:
                        game.rating = 0
            imgui.same_line()
        changed, value = ratingwidget.ratingwidget("", game.rating if game else 0)
        if changed:
            if game:
                game.rating = value
            else:
                for game in globals.games.values():
                    if game.selected:
                        game.rating = value

    def draw_game_open_thread_button(self, game: Game, label="", selectable=False):
        if selectable:
            clicked = imgui.selectable(label, False)[0]
        else:
            clicked = imgui.button(label)
        if game and imgui.is_item_clicked(imgui.MOUSE_BUTTON_MIDDLE):
            if globals.settings.copy_urls_as_bbcode:
                _url = lambda game: f"[URL='{game.url}']{game.name}[/URL]"
            else:
                _url = lambda game: game.url
            if game:
                text = _url(game)
            else:
                text = "\n".join(_url(game) for game in globals.games.values() if game.selected if game.url)
            callbacks.clipboard_copy(text)
        elif clicked:
            if game:
                callbacks.open_webpage(game.url)
            else:
                for game in globals.games.values():
                    if game.selected:
                        callbacks.open_webpage(game.url)

    def draw_game_copy_link_button(self, game: Game, label="", selectable=False):
        if selectable:
            clicked = imgui.selectable(label, False)[0]
        else:
            clicked = imgui.button(label)
        if clicked:
            if globals.settings.copy_urls_as_bbcode:
                _url = lambda game: f"[URL='{game.url}']{game.name}[/URL]"
            else:
                _url = lambda game: game.url
            if game:
                text = _url(game)
            else:
                text = "\n".join(_url(game) for game in globals.games.values() if game.selected if game.url)
            callbacks.clipboard_copy(text)

    def draw_game_archive_button(self, game: Game, label_off="", label_on="", selectable=False):
        if game:
            if selectable:
                clicked = imgui.selectable(label_on if game.archived else label_off, False)[0]
            else:
                clicked = imgui.button(label_on if game.archived else label_off)
            if clicked:
                game.archived = not game.archived
                if game.archived:
                    game.updated = False
        else:
            if imgui.small_button(icons.check):
                for game in globals.games.values():
                    if game.selected:
                        game.archived = True
                        game.updated = False
            imgui.same_line()
            if imgui.small_button(icons.close):
                for game in globals.games.values():
                    if game.selected:
                        game.archived = False
            imgui.same_line()
            imgui.text(label_off + " ")

    def draw_game_remove_button(self, game: Game, label="", selectable=False):
        if selectable:
            clicked = imgui.selectable(label, False)[0]
        else:
            clicked = imgui.button(label)
        if clicked:
            if game:
                callbacks.remove_game(game)
            else:
                callbacks.remove_game(*filter(lambda game: game.selected, globals.games.values()))

    def draw_game_add_exe_button(self, game: Game, label="", selectable=False):
        if selectable:
            clicked = imgui.selectable(label, False)[0]
        else:
            clicked = imgui.button(label)
        if clicked:
            if game:
                callbacks.add_game_exe(game)
            else:
                for game in globals.games.values():
                    if game.selected:
                        callbacks.add_game_exe(game)

    def draw_game_clear_exes_button(self, game: Game, label="", selectable=False):
        if game and not game.executables:
            imgui.push_disabled()
        if selectable:
            clicked = imgui.selectable(label, False)[0]
        else:
            clicked = imgui.button(label)
        if game and not game.executables:
            imgui.pop_disabled()
        if clicked:
            imgui.close_current_popup()
            if game:
                game.clear_executables()
            else:
                for game in globals.games.values():
                    if game.selected:
                        game.clear_executables()

    def draw_game_open_folder_button(self, game: Game, label="", selectable=False, executable: str = None):
        if game and not game.executables:
            imgui.push_alpha(0.5)
        if selectable:
            clicked = imgui.selectable(label, False)[0]
        else:
            clicked = imgui.button(label)
        if game and not game.executables:
            imgui.pop_alpha()
        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_MIDDLE):
            def _exe(exe):
                if utils.is_uri(exe):
                    return exe
                exe = pathlib.Path(exe)
                if globals.settings.default_exe_dir.get(globals.os) and not exe.is_absolute():
                    exe = pathlib.Path(globals.settings.default_exe_dir.get(globals.os)) / exe
                return str(exe)
            if game:
                if executable:
                    text = _exe(executable)
                else:
                    text = "\n".join(_exe(exe) for exe in game.executables)
            else:
                text = "\n".join("\n".join(_exe(exe) for exe in game.executables) for game in globals.games.values() if game.selected)
            callbacks.clipboard_copy(text)
        elif clicked:
            if game:
                callbacks.open_game_folder(game, executable=executable)
            else:
                for game in globals.games.values():
                    if game.selected:
                        callbacks.open_game_folder(game)

    def draw_game_id_button(self, game: Game, label="", selectable=False):
        if game.custom:
            imgui.push_disabled()
        if selectable:
            clicked = imgui.selectable(label, False)[0]
        else:
            clicked = imgui.button(label)
        if clicked:
            callbacks.clipboard_copy(str(game.id))
        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.text(
                f"Thread ID: {game.id}\n"
                "Click to copy!"
            )
            imgui.end_tooltip()
        if game.custom:
            imgui.pop_disabled()

    def draw_game_recheck_button(self, game: Game, label="", selectable=False):
        if game and game.custom:
            imgui.push_disabled()
        if selectable:
            clicked = imgui.selectable(label, False)[0]
        else:
            clicked = imgui.button(label)
        if clicked:
            games = [game] if game else list(filter(lambda g: g.selected, globals.games.values()))
            for g in games:
                g.add_timeline_event(TimelineEventType.RecheckUserReq)
            utils.start_refresh_task(api.refresh(*games, full=True, notifs=False))
        if game and game.custom:
            imgui.pop_disabled()

    def draw_game_tab_widget(self, game: Game):
        self.draw_tab_widget(game.tab)
        if imgui.begin_popup_context_item(f"###{game.id}_context_tab"):
            imgui.text("Move To:")
            imgui.separator()
            self.draw_game_tab_select_widget(game)
            imgui.end_popup()

    def draw_game_labels_select_widget(self, game: Game):
        if Label.instances:
            if game:
                for label in Label.instances:
                    changed, value = imgui.checkbox(f"###{game.id}_label_{label.id}", label in game.labels)
                    if changed:
                        if value:
                            game.add_label(label)
                        else:
                            game.remove_label(label)
                    imgui.same_line()
                    self.draw_label_widget(label)
            else:
                for label in Label.instances:
                    if imgui.small_button(icons.check):
                        for game in globals.games.values():
                            if game.selected:
                                game.add_label(label)
                    imgui.same_line()
                    if imgui.small_button(icons.close):
                        for game in globals.games.values():
                            if game.selected:
                                game.remove_label(label)
                    imgui.same_line()
                    self.draw_label_widget(label)
        else:
            imgui.text_disabled("Make some labels first!")

    def draw_game_tab_select_widget(self, game: Game):
        current_tab = game.tab if game else self.current_tab
        new_tab = current_tab
        if current_tab is None:
            imgui.push_disabled()
        if imgui.selectable(f"{Tab.first_tab_label()}###move_tab_-1", False)[0]:
            new_tab = None
        if current_tab is None:
            imgui.pop_disabled()
        for tab in Tab.instances:
            if current_tab is tab:
                imgui.push_disabled()
            color = (tab and tab.color) or globals.settings.style_accent
            imgui.push_style_color(imgui.COLOR_HEADER_HOVERED, *color)
            pos = imgui.get_cursor_pos()
            if imgui.selectable(f"###move_tab_{tab.id}", False)[0]:
                new_tab = tab
            imgui.set_cursor_pos(pos)
            if imgui.is_item_hovered():
                imgui.pop_style_color()
                imgui.push_style_color(imgui.COLOR_TEXT, *colors.foreground_color(color))
            imgui.text(f"{tab.icon} {tab.name or 'New Tab'}")
            imgui.pop_style_color()
            if current_tab is tab:
                imgui.pop_disabled()
        if imgui.selectable(f"{icons.tab_plus} New Tab###move_tab_-2", False)[0]:
            new_tab = async_thread.wait(db.create_tab())
            globals.settings.display_tab = new_tab
            async_thread.run(db.update_settings("display_tab"))
            self.recalculate_ids = True
            imgui.close_current_popup()
        if new_tab is not current_tab:
            imgui.close_current_popup()
            if game:
                game.tab = new_tab
            else:
                for game in globals.games.values():
                    if game.selected:
                        game.tab = new_tab

    def draw_game_tags_select_widget(self, game: Game):
        for tag in Tag:
            changed, value = imgui.checkbox(f"###{game.id}_tag_{tag.value}", tag in game.tags)
            if changed:
                if value:
                    game.tags = tuple(sorted(list(game.tags) + [tag]))
                else:
                    game.tags = tuple(sorted(filter(lambda x: x is not tag, game.tags)))
            imgui.same_line()
            self.draw_tag_widget(tag, quick_filter=False, change_highlight=False)

    def draw_game_context_menu(self, game: Game = None):
        if not game:
            imgui.text(f"Selected games: {self.selected_games_count}")
        self.draw_game_more_info_button(game, f"{icons.information_outline} More Info", selectable=True, carousel_ids=self.show_games_ids[self.current_tab])
        self.draw_game_recheck_button(game, f"{icons.reload_alert} Full Recheck", selectable=True)
        imgui.separator()
        self.draw_game_play_button(game, f"{icons.play} Play", selectable=True)
        self.draw_game_open_thread_button(game, f"{icons.open_in_new} Open Thread", selectable=True)
        self.draw_game_copy_link_button(game, f"{icons.content_copy} Copy Link", selectable=True)
        imgui.separator()
        self.draw_game_add_exe_button(game, f"{icons.folder_edit_outline} Add Exe", selectable=True)
        self.draw_game_clear_exes_button(game, f"{icons.folder_remove_outline} Clear Exes", selectable=True)
        self.draw_game_open_folder_button(game, f"{icons.folder_open_outline} Open Folder", selectable=True)
        imgui.separator()
        self.draw_game_finished_checkbox(game, f"{icons.flag_checkered} Finished")
        self.draw_game_installed_checkbox(game, f"{icons.download} Installed")
        imgui.separator()
        self.draw_game_rating_widget(game)
        if imgui.begin_menu(f"{icons.label_multiple_outline} Labels"):
            self.draw_game_labels_select_widget(game)
            imgui.end_menu()
        if imgui.begin_menu(f"{icons.tab} Move to Tab"):
            self.draw_game_tab_select_widget(game)
            imgui.end_menu()
        imgui.separator()
        self.draw_game_archive_button(game, label_off=f"{icons.archive_outline} Archive", label_on=f"{icons.archive_off_outline} Unarchive", selectable=True)
        self.draw_game_remove_button(game, f"{icons.trash_can_outline} Remove", selectable=True)

    def draw_game_notes_widget(self, game: Game, multiline=True, width: int | float = None):
        if multiline:
            changed, value = imgui.input_text_multiline(
                f"###{game.id}_notes",
                value=game.notes,
                width=width or imgui.get_content_region_available_width(),
                height=self.scaled(450)
            )
            if changed:
                game.notes = value
            if imgui.begin_popup_context_item(f"###{game.id}_notes_context"):
                utils.text_context(game, "notes")
                imgui.end_popup()
        else:
            imgui.set_next_item_width(width or imgui.get_content_region_available_width())
            # Only show first line
            if (offset := game.notes.find("\n")) != -1:
                first_line = game.notes[:offset]
            else:
                first_line = game.notes
            changed, first_line = imgui.input_text(
                f"###{game.id}_notes_inline",
                value=first_line
            )
            def setter_extra(value: str):
                # Merge with remaining lines
                if (offset := game.notes.find("\n")) != -1:
                    value += game.notes[offset:]
                game.notes = value
            if changed:
                setter_extra(first_line)
            if imgui.begin_popup_context_item(f"###{game.id}_notes_inline_context"):
                utils.text_context(type("_", (), dict(_=first_line))(), "_", setter_extra)
                imgui.end_popup()

    def draw_game_tags_widget(self, game: Game):
        pad = 2 * imgui.style.frame_padding.x + imgui.style.item_spacing.x
        for tag in game.tags:
            if imgui.get_content_region_available_width() < imgui.calc_text_size(tag.name).x + pad:
                imgui.dummy(0, 0)
            self.draw_tag_widget(tag)
            imgui.same_line()
        imgui.dummy(0, 0)

    def draw_game_labels_widget(self, game: Game, wrap=True, small=False, short=False, align=False):
        pad = 2 * imgui.style.frame_padding.x + imgui.style.item_spacing.x
        if small:
            short = True
            imgui.push_font(imgui.fonts.small)
            if align:
                imgui.push_y(self.scaled(2.5))
                popped_y = False
        for label in game.labels:
            if wrap and imgui.get_content_region_available_width() < imgui.calc_text_size(label.short_name if short else label.name).x + pad:
                if small and align and not popped_y:
                    imgui.pop_y()
                    popped_y = True
                imgui.dummy(0, 0)
            self.draw_label_widget(label, short=short)
            imgui.same_line()
        if small and align and not popped_y:
            imgui.pop_y()
        elif wrap:
            imgui.dummy(0, 0)
        if small:
            imgui.pop_font()

    def draw_timeline_filter_widget(self, game: Game):
        label = f"###{game.id}_timeline_filter_popup"
        if imgui.button(f"{icons.eye_off_outline} Hide events"):
            imgui.open_popup(label)
        if imgui.begin_popup(label):
            for event_type in TimelineEventType:
                changed, value = imgui.checkbox(f"###{game.id}_event_{event_type.value}", event_type in globals.settings.hidden_timeline_events)
                if changed:
                    if value:
                        globals.settings.hidden_timeline_events.append(event_type)
                    else:
                        globals.settings.hidden_timeline_events.remove(event_type)
                    async_thread.run(db.update_settings("hidden_timeline_events"))
                imgui.same_line()
                imgui.text(f"{getattr(icons, event_type.icon)} {event_type.display}")
            imgui.end_popup()

    def draw_game_timeline_widget(self, game: Game):
        icon_coordinates: list[tuple[x1, y1, x2, y2]] = []
        text_coordinates: list[tuple[x1, y1, x2, y2]] = []

        self.draw_timeline_filter_widget(game)
        imgui.dummy(0, 0 if globals.settings.compact_timeline else self.scaled(6))

        def draw_event(timestamp, type, args, spacing=True):
            icon = getattr(icons, type.icon)
            date = dt.datetime.fromtimestamp(timestamp)
            message = type.template.format(*args, *["?" for _ in range(type.args_min - len(args))])
            # Short timeline variant
            if globals.settings.compact_timeline:
                imgui.push_style_color(imgui.COLOR_TEXT, *globals.settings.style_text_dim)
                imgui.push_font(imgui.fonts.mono)
                imgui.text(date.strftime(globals.settings.timestamp_format))
                imgui.pop_font()
                imgui.pop_style_color()
                imgui.same_line()
                imgui.push_style_color(imgui.COLOR_TEXT, *globals.settings.style_accent)
                imgui.text(icon)
                imgui.pop_style_color()
                imgui.same_line()
                imgui.text(message)
                return
            # Draw icon
            imgui.dummy(0, 0)
            imgui.same_line()
            cur = imgui.get_cursor_screen_pos()
            imgui.push_style_color(imgui.COLOR_TEXT, *globals.settings.style_accent)
            imgui.text(icon)
            imgui.pop_style_color()
            icon_size = imgui.get_item_rect_size()
            icon_coordinates.append((cur.x, cur.y, cur.x + icon_size.x, cur.y + icon_size.y))
            # Draw timestamp
            imgui.same_line(spacing=self.scaled(15))
            timestamp_pos = imgui.get_cursor_screen_pos()
            imgui.push_style_color(imgui.COLOR_TEXT, *globals.settings.style_text_dim)
            imgui.text(date.strftime(globals.settings.datestamp_format))
            imgui.pop_style_color()
            timestamp_size = imgui.get_item_rect_size()
            if imgui.is_item_hovered():
                with imgui.begin_tooltip():
                    imgui.text(date.strftime(globals.settings.timestamp_format))
            # Draw message
            message_pos = (timestamp_pos.x, timestamp_pos.y + timestamp_size.y - self.scaled(2))
            imgui.set_cursor_screen_pos(message_pos)
            imgui.text(message)
            message_size = imgui.get_item_rect_size()
            final_x = timestamp_pos.x + timestamp_size.x if timestamp_size.x > message_size.x else message_pos[0] + message_size.x
            text_coordinates.append((timestamp_pos.x, timestamp_pos.y, final_x, message_pos[1] + message_size.y))
            if spacing:
                imgui.dummy(0, self.scaled(10))

        for event in game.timeline_events:
            if event.type not in globals.settings.hidden_timeline_events:
                draw_event(event.timestamp.value, event.type, event.arguments)

        if TimelineEventType.GameAdded not in globals.settings.hidden_timeline_events:
            draw_event(game.added_on.value, TimelineEventType.GameAdded, [], spacing=False)

        thickness = 2
        prev_rect = None
        padding = self.scaled(3)
        dl = imgui.get_window_draw_list()
        color = imgui.get_color_u32_rgba(*globals.settings.style_border)

        # Draw timeline primitives
        rounding = self.scaled(globals.settings.style_corner_radius)
        for x1, y1, x2, y2 in icon_coordinates:
            dl.add_rect(x1 - padding, y1 - padding, x2 + padding, y2 + padding, color, rounding=rounding, thickness=thickness)
            if prev_rect:
                dl.add_line((prev_rect[0] + prev_rect[2]) / 2, prev_rect[3] + padding, (x1 + x2) / 2, y1 - padding, color, thickness=thickness)
            prev_rect = (x1, y1, x2, y2)
        for x1, y1, x2, y2 in text_coordinates:
            dl.add_rect(x1 - padding - self.scaled(2), y1 - padding, x2 + padding + self.scaled(2), y2 + padding, color, rounding=rounding, thickness=thickness)

    def draw_game_downloads_header(self, game: Game):
        pad = 3 * imgui.style.item_spacing.x
        def _cluster_text(name, text):
            imgui.text_disabled(name[0])
            if imgui.is_item_hovered():
                imgui.set_tooltip(name[2:])
            imgui.same_line()
            imgui.text(text)
            imgui.same_line(spacing=pad)
        _cluster_text(cols.name.name, game.name)
        _cluster_text(cols.version.name, game.version)
        _cluster_text(cols.last_updated.name, game.last_updated.display or "Unknown")
        _cluster_text(cols.developer.name, game.developer)
        imgui.spacing()
        imgui.spacing()

    def draw_updates_popup(self, updated_games, sorted_ids, popup_uuid: str = ""):
        def popup_content():
            indent = self.scaled(222)
            width = indent - 3 * imgui.style.item_spacing.x
            full_width = 3 * indent
            wrap_width = 2 * indent - imgui.style.item_spacing.x
            name_offset = imgui.calc_text_size("Name: ").x + 2 * imgui.style.item_spacing.x
            version_offset = imgui.calc_text_size("Version: ").x + 2 * imgui.style.item_spacing.x
            arrow_width = imgui.calc_text_size(" -> ").x + imgui.style.item_spacing.x
            img_pos_x = imgui.get_cursor_pos_x()
            category = None
            category_open = False
            imgui.push_text_wrap_pos(full_width)
            imgui.indent(indent)
            for game_i, id in enumerate(sorted_ids):
                if id not in globals.games:
                    sorted_ids.remove(id)
                    continue
                old_game = updated_games[id]
                game = globals.games[id]
                if category is not game.type.category:
                    category = game.type.category
                    imgui.push_font(imgui.fonts.big)
                    imgui.set_cursor_pos_x(img_pos_x - self.scaled(8))
                    category_open = imgui.tree_node(
                        category.name,
                        flags=(
                            imgui.TREE_NODE_NO_TREE_PUSH_ON_OPEN |
                            imgui.TREE_NODE_SPAN_FULL_WIDTH |
                            imgui.TREE_NODE_DEFAULT_OPEN
                        )
                    )
                    imgui.pop_font()
                if not category_open:
                    continue
                img_pos_y = imgui.get_cursor_pos_y()
                imgui.begin_group()

                imgui.push_font(imgui.fonts.big)
                imgui.text(old_game.name)
                imgui.pop_font()

                imgui.spacing()
                imgui.text_disabled("Update date: ")
                imgui.same_line()
                imgui.text(game.last_updated.display)

                if Tab.instances:
                    imgui.spacing()
                    imgui.text_disabled("Tab: ")
                    imgui.same_line()
                    self.draw_game_tab_widget(game)

                for attr, offset in (("name", name_offset), ("version", version_offset)):
                    old_val =  getattr(old_game, attr) or "Unknown"
                    new_val =  getattr(game, attr) or "Unknown"
                    if new_val != old_val:
                        imgui.spacing()
                        imgui.text_disabled(f"{attr.title()}: ")
                        imgui.same_line()
                        utils.wrap_text(old_val, width=wrap_width, offset=offset)
                        imgui.same_line()
                        if full_width - imgui.get_cursor_pos_x() < arrow_width:
                            imgui.dummy(0, 0)
                        imgui.text_disabled(" -> ")
                        imgui.same_line()
                        utils.wrap_text(new_val, width=wrap_width, offset=imgui.get_cursor_pos_x() - indent)

                if game.status is not old_game.status:
                    imgui.spacing()
                    imgui.text_disabled("Status: ")
                    imgui.same_line()
                    imgui.text(old_game.status.name)
                    imgui.same_line()
                    self.draw_status_widget(old_game.status)
                    imgui.same_line()
                    if full_width - imgui.get_cursor_pos_x() < arrow_width:
                        imgui.dummy(0, 0)
                    imgui.text_disabled(" -> ")
                    imgui.same_line()
                    imgui.text(game.status.name)
                    imgui.same_line()
                    self.draw_status_widget(game.status)

                imgui.spacing()
                self.draw_game_open_thread_button(game, f"{icons.open_in_new} Thread")
                imgui.same_line()
                self.draw_game_copy_link_button(game, f"{icons.content_copy} Link")
                imgui.same_line()
                self.draw_game_more_info_button(game, f"{icons.information_outline} Info", carousel_ids=sorted_ids)

                imgui.end_group()
                height = imgui.get_item_rect_size().y + imgui.style.item_spacing.y
                crop = game.image.crop_to_ratio(width / height, fit=globals.settings.fit_images)
                imgui.set_cursor_pos((img_pos_x, img_pos_y))
                game.image.render(width, height, *crop, rounding=self.scaled(globals.settings.style_corner_radius))

                if game_i != len(sorted_ids) - 1:
                    imgui.text("\n")
            imgui.unindent(indent)
            imgui.pop_text_wrap_pos()
        return utils.popup(
            f"{len(sorted_ids)} update{'' if len(sorted_ids) == 1 else 's'}",
            popup_content,
            buttons=True,
            closable=True,
            outside=False,
            popup_uuid=popup_uuid
        )

    def draw_game_image_missing_text(self, game: Game, text: str):
        self.draw_hover_text(
            text=text,
            hover_text=(
                "This image link blocks us! You can blame Imgur." if game.image_url == "blocked" else
                "This thread does not seem to have an image!" if game.image_url == "missing" else
                "This image link cannot be reached anymore!" if game.image_url == "dead" else
                "Run a full refresh to try downloading it again!"
            )
        )

    def draw_game_info_popup(self, game: Game, carousel_ids: list = None, popup_uuid: str = ""):
        popup_pos = None
        popup_size = None
        zoom_popup = False
        def popup_content():
            nonlocal popup_pos, popup_size, zoom_popup
            # Image
            image = game.image
            avail = imgui.get_content_region_available()
            close_image = False
            if image.missing:
                text = "Image missing!"
                width = imgui.calc_text_size(text).x
                imgui.set_cursor_pos_x((avail.x - width + imgui.style.scrollbar_size) / 2)
                self.draw_game_image_missing_text(game, text)
            elif image.invalid:
                text = "Invalid image!"
                width = imgui.calc_text_size(text).x
                imgui.set_cursor_pos_x((avail.x - width + imgui.style.scrollbar_size) / 2)
                self.draw_hover_text(
                    text=text,
                    hover_text="This thread's image has an unrecognised format and couldn't be loaded!"
                )
            else:
                aspect_ratio = image.height / image.width
                out_height = (min(avail.y, self.scaled(690)) * self.scaled(0.4)) or 1
                out_width = avail.x or 1
                if aspect_ratio > (out_height / out_width):
                    height = out_height
                    width = height * (1 / aspect_ratio)
                    margin_x = (out_width - width) / 2
                    margin_y = 0
                else:
                    width = out_width
                    height = width * aspect_ratio
                    margin_x = 0
                    margin_y = (out_height - height) / 2
                prev_pos = imgui.get_cursor_pos()
                imgui.set_cursor_pos((prev_pos.x + margin_x, prev_pos.y + margin_y))
                image_pos = imgui.get_cursor_screen_pos()

                imgui.begin_child("###image_zoomer", width=width, height=height + 1.0, flags=imgui.WINDOW_NO_SCROLLBAR)
                imgui.dummy(width + 2.0, height)
                imgui.set_scroll_x(1.0)
                imgui.set_cursor_screen_pos(image_pos)
                rounding = self.scaled(globals.settings.style_corner_radius)
                image.render(width, height, rounding=rounding)
                if imgui.is_item_hovered():
                    # Image popup
                    if imgui.is_mouse_down():
                        size = imgui.io.display_size
                        if aspect_ratio > size.y / size.x:
                            height = size.y - self.scaled(10)
                            width = height / aspect_ratio
                        else:
                            width = size.x - self.scaled(10)
                            height = width * aspect_ratio
                        x = (size.x - width) / 2
                        y = (size.y - height) / 2
                        flags = imgui.DRAW_ROUND_CORNERS_ALL
                        pos2 = (x + width, y + height)
                        fg_draw_list = imgui.get_foreground_draw_list()
                        fg_draw_list.add_image_rounded(image.texture_id, (x, y), pos2, rounding=rounding, flags=flags)
                    # Zoom
                    elif globals.settings.zoom_enabled:
                        if diff := int(imgui.get_scroll_x() - 1.0):
                            if imgui.is_key_down(glfw.KEY_LEFT_ALT):
                                globals.settings.zoom_area = min(max(globals.settings.zoom_area + diff, 1), 500)
                            else:
                                globals.settings.zoom_times = min(max(globals.settings.zoom_times * (-diff / 50.0 + 1.0), 1), 20)
                        zoom_popup = True
                        out_size = min(*imgui.io.display_size) * globals.settings.zoom_area / 100
                        in_size = out_size / globals.settings.zoom_times
                        mouse_pos = imgui.io.mouse_pos
                        off_x = utils.map_range(in_size, 0.0, width, 0.0, 1.0) / 2.0
                        off_y = utils.map_range(in_size, 0.0, height, 0.0, 1.0) / 2.0
                        x = utils.map_range(mouse_pos.x, image_pos.x, image_pos.x + width, 0.0, 1.0)
                        y = utils.map_range(mouse_pos.y, image_pos.y, image_pos.y + height, 0.0, 1.0)
                        imgui.set_next_window_position(*mouse_pos, pivot_x=0.5, pivot_y=0.5)
                        imgui.begin_tooltip()
                        image.render(out_size, out_size, (x - off_x, y - off_y), (x + off_x, y + off_y), rounding=rounding)
                        imgui.end_tooltip()
                close_image = True
            if imgui.begin_popup_context_item("###image_context"):
                if imgui.selectable(f"{icons.folder_open_outline} Set custom image", False)[0]:
                    def select_callback(selected):
                        if selected:
                            game.image_url = "custom"
                            game.set_image_sync(pathlib.Path(selected).read_bytes())
                    utils.push_popup(filepicker.FilePicker(
                        title=f"Select or drop image for {game.name}",
                        callback=select_callback
                    ).tick)
                if imgui.selectable(f"{icons.trash_can_outline} Reset image", False)[0]:
                    game.delete_images()
                    game.refresh_image()
                imgui.end_popup()
            if close_image:
                imgui.end_child()
                imgui.set_cursor_pos(prev_pos)
                imgui.dummy(out_width, out_height)
            imgui.push_text_wrap_pos()

            imgui.push_font(imgui.fonts.big)
            self.draw_game_name_text(game)
            imgui.pop_font()

            self.draw_game_play_button(game, f"{icons.play} Play")
            imgui.same_line()
            self.draw_game_open_thread_button(game, f"{icons.open_in_new} Thread")
            imgui.same_line()
            self.draw_game_copy_link_button(game, f"{icons.content_copy} Link")
            imgui.same_line()
            self.draw_game_id_button(game, f"{icons.pound} ID")
            imgui.same_line()
            self.draw_game_finished_checkbox(game, f"{icons.flag_checkered} Finished")
            _10 = self.scaled(10)
            imgui.same_line(spacing=_10)
            self.draw_game_installed_checkbox(game, f"{icons.download} Installed")
            imgui.same_line(spacing=_10)
            self.draw_game_recheck_button(game, f"{icons.reload_alert} Recheck")
            imgui.same_line()
            self.draw_game_archive_button(game, label_off=f"{icons.archive_outline} Archive", label_on=f"{icons.archive_off_outline} Unarchive")
            imgui.same_line()
            self.draw_game_remove_button(game, f"{icons.trash_can_outline} Remove")

            imgui.spacing()

            if imgui.begin_table(f"###details", column=2):
                imgui.table_setup_column("", imgui.TABLE_COLUMN_WIDTH_STRETCH)
                imgui.table_setup_column("", imgui.TABLE_COLUMN_WIDTH_STRETCH)

                imgui.table_next_row()

                imgui.table_next_column()
                imgui.text_disabled("Version:")
                imgui.same_line()
                if game.updated:
                    self.draw_game_update_icon(game)
                    imgui.same_line()
                if game.unknown_tags_flag:
                    self.draw_game_unknown_tags_icon(game)
                    imgui.same_line()
                offset = imgui.calc_text_size("Version:").x + imgui.style.item_spacing.x
                utils.wrap_text(game.version, width=offset + imgui.get_content_region_available_width(), offset=offset)

                imgui.table_next_column()
                imgui.text_disabled("Added On:")
                imgui.same_line()
                imgui.text(game.added_on.display)

                imgui.table_next_row()

                imgui.table_next_column()
                imgui.text_disabled("Developer:")
                imgui.same_line()
                offset = imgui.calc_text_size("Developer:").x + imgui.style.item_spacing.x
                utils.wrap_text(game.developer or "Unknown", width=offset + imgui.get_content_region_available_width(), offset=offset)

                imgui.table_next_column()
                imgui.text_disabled("Last Updated:")
                imgui.same_line()
                imgui.text(game.last_updated.display or "Unknown")

                imgui.table_next_row()

                imgui.table_next_column()
                imgui.text_disabled("Status:")
                imgui.same_line()
                imgui.text(game.status.name)
                imgui.same_line()
                self.draw_status_widget(game.status)

                imgui.table_next_column()
                imgui.text_disabled("Last Launched:")
                imgui.same_line()
                imgui.text(game.last_launched.display or "Never")
                if imgui.is_item_clicked():
                    game.last_launched = time.time()
                    game.add_timeline_event(TimelineEventType.GameLaunched, "date set manually")
                if imgui.is_item_hovered():
                    imgui.begin_tooltip()
                    imgui.text("Click to set as launched right now!")
                    imgui.end_tooltip()

                imgui.table_next_row()

                imgui.table_next_column()
                imgui.text_disabled("Forum Score:")
                imgui.same_line()
                imgui.text(f"{game.score:.1f}/5")
                imgui.same_line()
                imgui.text_disabled(f"({game.votes})")

                imgui.table_next_column()
                imgui.text_disabled("Personal Rating:")
                imgui.same_line()
                self.draw_game_rating_widget(game)

                imgui.table_next_row()

                imgui.table_next_column()
                imgui.text_disabled("Type:")
                imgui.same_line()
                self.draw_type_widget(game.type)

                imgui.table_next_column()
                imgui.text_disabled("Tab:")
                imgui.same_line()
                self.draw_game_tab_widget(game)

                imgui.table_next_row()

                imgui.table_next_column()
                imgui.align_text_to_frame_padding()
                if len(game.executables) <= 1:
                    imgui.text_disabled("Executable:")
                    imgui.same_line()
                    if game.executables:
                        offset = imgui.calc_text_size("Executable:").x + imgui.style.item_spacing.x
                        utils.wrap_text(game.executables[0], width=offset + imgui.get_content_region_available_width(), offset=offset)
                    else:
                        imgui.text("Not set")
                else:
                    imgui.text_disabled("Executables:")

                imgui.table_next_column()
                self.draw_game_add_exe_button(game, f"{icons.folder_edit_outline} Add Exe")
                imgui.same_line()
                self.draw_game_open_folder_button(game, f"{icons.folder_open_outline} Open Folder")
                imgui.same_line()
                self.draw_game_clear_exes_button(game, f"{icons.folder_remove_outline} Clear Exes")

                imgui.end_table()

            if len(game.executables) > 1:
                for executable in game.executables:
                    self.draw_game_play_button(game, icons.play, executable=executable)
                    imgui.same_line()
                    self.draw_game_open_folder_button(game, icons.folder_open_outline, executable=executable)
                    imgui.same_line()
                    if imgui.button(icons.folder_remove_outline):
                        game.remove_executable(executable)
                    imgui.same_line()
                    imgui.text(executable)

            imgui.spacing()

            if imgui.begin_tab_bar("Details"):

                if imgui.begin_tab_item((
                    icons.clipboard_text_outline if game.changelog else
                    icons.clipboard_text_off_outline
                ) + " Changelog###changelog")[0]:
                    imgui.spacing()
                    if game.changelog:
                        imgui.text(game.changelog)
                    else:
                        imgui.text_disabled("Either this game doesn't have a changelog, or the thread is not formatted properly!")
                    imgui.end_tab_item()

                if imgui.begin_tab_item((
                    icons.information_outline if game.description else
                    icons.information_off_outline
                ) + " Description###description")[0]:
                    imgui.spacing()
                    if game.description:
                        imgui.text(game.description)
                    else:
                        imgui.text_disabled("Either this game doesn't have a description, or the thread is not formatted properly!")
                    imgui.end_tab_item()

                if not game.custom and imgui.begin_tab_item(icons.tray_arrow_down + " Downloads###downloads")[0]:
                    imgui.spacing()
                    imgui.text("RPDL Torrents:")
                    imgui.same_line()
                    if imgui.small_button(f"{icons.magnify}Search"):
                        rpdl.open_search_popup(game)
                    imgui.spacing()
                    imgui.text("F95zone Donor DDL:")
                    imgui.same_line()
                    if imgui.small_button(f"{icons.cloud_check_variant_outline}Check"):
                        api.open_ddl_popup(game)
                    imgui.spacing()
                    imgui.spacing()
                    imgui.spacing()
                    imgui.text("Regular Downloads:")
                    imgui.same_line()
                    self.draw_hover_text(
                        "Left clicking opens the webpage in your chosen browser.\n"
                        "Middle clicking copies the link to your clipboard.\n\n"
                        "There's 3 types of links that work slightly different:\n"
                        f"{icons.link}Direct: Plain download link, retrieved with automated integrated browser\n"
                        f"{icons.domino_mask}Masked: CAPTCHA protected link, unmasked with automated integrated browser\n"
                        f"{icons.open_in_app}Forum: Link internal to F95zone, no special processing\n"
                    )
                    imgui.spacing()
                    if game.downloads:
                        can_add_spacing = False
                        _20 = self.scaled(20)
                        for name, mirrors in game.downloads:
                            if mirrors:
                                can_add_spacing = True
                                imgui.text(name + ":")
                                for mirror, link in mirrors:
                                    imgui.same_line()
                                    if imgui.get_content_region_available_width() < imgui.calc_text_size(icons.link + mirror).x + _20:
                                        imgui.dummy(0, 0)
                                    if not link:
                                        # Use thread url when link is missing
                                        link = game.url
                                    if link.startswith("//"):
                                        # XPath expression
                                        if imgui.small_button(icons.link + mirror):
                                            callbacks.redirect_xpath_link(game.url, link)
                                        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_MIDDLE):
                                            callbacks.redirect_xpath_link(game.url, link, copy=True)
                                    elif link.startswith(f"{api.f95_host}/masked/"):
                                        # Masked link
                                        if imgui.small_button(icons.domino_mask + mirror):
                                            callbacks.redirect_masked_link(link)
                                        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_MIDDLE):
                                            callbacks.redirect_masked_link(link, copy=True)
                                    elif link.startswith(api.f95_host):
                                        # F95zone link
                                        if imgui.small_button(icons.open_in_app + mirror):
                                            callbacks.open_webpage(link)
                                        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_MIDDLE):
                                            callbacks.clipboard_copy(link)
                                    else:
                                        # Should never happen, but here for backwards compatibility
                                        if imgui.small_button(icons.link + mirror):
                                            callbacks.open_webpage(link)
                                        if imgui.is_item_clicked(imgui.MOUSE_BUTTON_MIDDLE):
                                            callbacks.clipboard_copy(link)
                            else:
                                if can_add_spacing:
                                    imgui.text("")
                                imgui.text(name)
                                imgui.spacing()
                                imgui.spacing()
                                can_add_spacing = False
                    else:
                        imgui.text_disabled("Either this game doesn't have regular downloads, or the thread is not formatted properly!")
                    imgui.end_tab_item()

                if imgui.begin_tab_item((
                    icons.label_multiple_outline if len(game.labels) > 1 else
                    icons.label_outline if len(game.labels) == 1 else
                    icons.label_off_outline
                ) + " Labels###labels")[0]:
                    imgui.spacing()
                    imgui.button("Right click to edit")
                    if imgui.begin_popup_context_item(f"###{game.id}_context_labels"):
                        self.draw_game_labels_select_widget(game)
                        imgui.end_popup()
                    imgui.same_line(spacing=2 * imgui.style.item_spacing.x)
                    if game.labels:
                        self.draw_game_labels_widget(game)
                    else:
                        imgui.text_disabled("This game has no labels!")
                    imgui.end_tab_item()

                if imgui.begin_tab_item((
                    icons.draw_pen if game.notes else
                    icons.pencil_plus_outline
                ) + " Notes###notes")[0]:
                    imgui.spacing()
                    self.draw_game_notes_widget(game)
                    imgui.end_tab_item()

                if imgui.begin_tab_item((
                    icons.tag_multiple_outline if len(game.tags) > 1 else
                    icons.tag_outline if len(game.tags) == 1 else
                    icons.tag_off_outline
                ) + " Tags###tags")[0]:
                    imgui.spacing()
                    if game.tags:
                        self.draw_game_tags_widget(game)
                    else:
                        imgui.text_disabled("This game has no tags!")
                    if utags := game.unknown_tags:
                        imgui.spacing()
                        if imgui.tree_node(f"Unknown tags ({len(utags)})"):
                            if imgui.button(f"{icons.tag_multiple_outline} Copy"):
                                callbacks.clipboard_copy(", ".join(utags))
                            for tag in utags:
                                imgui.text(f"- {tag}")
                            imgui.tree_pop()
                    imgui.end_tab_item()

                if imgui.begin_tab_item(icons.timeline_clock_outline + " Timeline###timeline")[0]:
                    imgui.spacing()
                    self.draw_game_timeline_widget(game)
                    imgui.end_tab_item()

                if imgui.begin_tab_item((
                    icons.puzzle_check_outline if game.custom else
                    icons.puzzle_remove_outline
                ) + " Custom###custom")[0]:
                    if game.custom:
                        imgui.text(
                            "This is a custom game. You can edit all its details below (except downloads). "
                            "If you wish to convert it back to a F95zone game, then make sure to fill the "
                            "game url with a valid F95zone thread url before pressing the button below."
                        )
                        if imgui.button(f"{icons.puzzle_remove} Convert to F95zone game"):
                            callbacks.convert_custom_to_f95zone(game)
                        imgui.text("")
                        imgui.push_item_width(-imgui.FLOAT_MIN)
                        pos_x = imgui.get_cursor_pos_x() + imgui.calc_text_size("Description:").x

                        imgui.set_cursor_pos_x(pos_x - imgui.calc_text_size("URL:").x)
                        imgui.align_text_to_frame_padding()
                        imgui.text("URL:")
                        imgui.same_line()
                        changed, value = imgui.input_text("###url", game.url)
                        if changed:
                            game.url = value
                        if imgui.begin_popup_context_item("###url_context"):
                            utils.text_context(game, "url", no_icons=True)
                            imgui.end_popup()

                        imgui.set_cursor_pos_x(pos_x - imgui.calc_text_size("Name:").x)
                        imgui.align_text_to_frame_padding()
                        imgui.text("Name:")
                        imgui.same_line()
                        imgui.set_next_item_width(imgui.get_content_region_available_width() - self.scaled(120))
                        changed, value = imgui.input_text("###name", game.name)
                        if changed:
                            game.name = value
                        if imgui.begin_popup_context_item("###name_context"):
                            utils.text_context(game, "name", no_icons=True)
                            imgui.end_popup()
                        imgui.same_line(spacing=imgui.style.item_spacing.x * 2)
                        imgui.text("Score:")
                        imgui.same_line()
                        changed, value = imgui.drag_float("###score", game.score, change_speed=0.01, min_value=0, max_value=5, format="%.1f/5")
                        if changed:
                            game.score = value

                        imgui.set_cursor_pos_x(pos_x - imgui.calc_text_size("Version:").x)
                        imgui.align_text_to_frame_padding()
                        imgui.text("Version:")
                        imgui.same_line()
                        imgui.set_next_item_width(imgui.get_content_region_available_width() / 3.5)
                        changed, value = imgui.input_text("###version", game.version)
                        if changed:
                            game.version = value or "N/A"
                        if imgui.begin_popup_context_item("###version_context"):
                            utils.text_context(game, "version", no_icons=True)
                            imgui.end_popup()
                        imgui.same_line(spacing=imgui.style.item_spacing.x * 2)
                        imgui.text("Developer:")
                        imgui.same_line()
                        imgui.set_next_item_width(imgui.get_content_region_available_width() / 2.1)
                        changed, value = imgui.input_text("###developer", game.developer)
                        if changed:
                            game.developer = value
                        if imgui.begin_popup_context_item("###developer_context"):
                            utils.text_context(game, "developer", no_icons=True)
                            imgui.end_popup()
                        imgui.same_line(spacing=imgui.style.item_spacing.x * 2)
                        imgui.text("Status:")
                        imgui.same_line()
                        if imgui.begin_combo("###status", game.status.name):
                            for status in Status:
                                selected = status is game.status
                                pos = imgui.get_cursor_pos()
                                if imgui.selectable(f"###status_{status.value}", selected)[0]:
                                    game.status = status
                                if selected:
                                    imgui.set_item_default_focus()
                                imgui.set_cursor_pos(pos)
                                self.draw_status_widget(status)
                                imgui.same_line()
                                imgui.text(status.name)
                            imgui.end_combo()

                        imgui.set_cursor_pos_x(pos_x - imgui.calc_text_size("Tags:").x)
                        imgui.align_text_to_frame_padding()
                        imgui.text("Tags:")
                        imgui.same_line()
                        imgui.button("Right click")
                        if imgui.begin_popup_context_item("###tags_context"):
                            self.draw_game_tags_select_widget(game)
                            imgui.end_popup()
                        imgui.same_line(spacing=imgui.style.item_spacing.x * 2)
                        imgui.text("Updated:")
                        imgui.same_line()
                        changed, value = imgui.checkbox("###updated", game.updated)
                        if changed:
                            game.updated = value
                        imgui.same_line(spacing=imgui.style.item_spacing.x * 2)
                        imgui.text("Last Updated:")
                        date = dt.datetime.fromtimestamp(game.last_updated.value)
                        day, month, year = date.day, date.month, date.year
                        frame_height = imgui.get_frame_height()
                        imgui.same_line()
                        imgui.set_next_item_width(1.5 * frame_height)
                        day = min(max(imgui.drag_int("###last_updated_day", day, change_speed=0.05, min_value=1, max_value=31)[1], 1), 31)
                        imgui.same_line()
                        imgui.set_next_item_width(1.5 * frame_height)
                        month = min(max(imgui.drag_int("###last_updated_month", month, change_speed=0.03, min_value=1, max_value=12)[1], 1), 12)
                        imgui.same_line()
                        imgui.set_next_item_width(2 * frame_height)
                        year = min(max(imgui.drag_int("###last_updated_year", year, change_speed=0.05, min_value=1970, max_value=9999)[1], 1970), 9999)
                        if day != date.day or month != date.month or year != date.year:
                            for _ in range(5):
                                try:
                                    date = date.replace(day=day, month=month, year=year)
                                    game.last_updated = parser.datestamp(date.timestamp())
                                except (ValueError, OSError):
                                    day -= 1
                                    continue
                                break
                        imgui.same_line(spacing=imgui.style.item_spacing.x * 2)
                        imgui.text("Type:")
                        imgui.same_line()
                        if imgui.begin_combo("###type", game.type.name):
                            category = None
                            for type in Type:
                                if category is not type.category:
                                    category = type.category
                                    imgui.text(category.name)
                                selected = type is game.type
                                pos = imgui.get_cursor_pos()
                                if imgui.selectable(f"###type_{type.value}", selected)[0]:
                                    game.type = type
                                if selected:
                                    imgui.set_item_default_focus()
                                imgui.set_cursor_pos(pos)
                                self.draw_type_widget(type)
                            imgui.end_combo()

                        imgui.align_text_to_frame_padding()
                        imgui.text("Description:")
                        imgui.same_line()
                        changed, value = imgui.input_text_multiline("###description", value=game.description)
                        if changed:
                            game.description = value
                        if imgui.begin_popup_context_item("###description_context"):
                            utils.text_context(game, "description")
                            imgui.end_popup()

                        imgui.set_cursor_pos_x(pos_x - imgui.calc_text_size("Changelog:").x)
                        imgui.align_text_to_frame_padding()
                        imgui.text("Changelog:")
                        imgui.same_line()
                        changed, value = imgui.input_text_multiline("###changelog", value=game.changelog)
                        if changed:
                            game.changelog = value
                        if imgui.begin_popup_context_item("###changelog_context"):
                            utils.text_context(game, "changelog")
                            imgui.end_popup()

                        imgui.pop_item_width()
                    else:
                        imgui.text(
                            "Here you have the option to convert this game to a custom game. Custom games are not checked for updates and become untied from F95zone. "
                            "This is useful for games that have been removed for breaking forum rules, or for adding games from other platforms to your library. Custom "
                            "games allow you to edit all their details (except downloads) that would normally be fetched from F95zone."
                        )
                        if imgui.button(f"{icons.puzzle_check} Convert to custom game"):
                            callbacks.convert_f95zone_to_custom(game)
                    imgui.end_tab_item()

                imgui.end_tab_bar()
            imgui.pop_text_wrap_pos()
            popup_pos = imgui.get_window_position()
            popup_size = imgui.get_window_size()
        if game.id not in globals.games:
            return 0, True
        return_args = utils.popup(game.name, popup_content, closable=True, outside=True, popup_uuid=popup_uuid)
        # Has and is in carousel ids, is not the only one in them, is topmost popup and no item is active
        if carousel_ids and len(carousel_ids) > 1 and game.id in carousel_ids and imgui.is_topmost() and not imgui.is_any_item_active():
            pos = popup_pos
            size = popup_size
            if size and pos:
                imgui.push_font(imgui.fonts.big)
                text_size = imgui.calc_text_size(icons.arrow_left_drop_circle)
                offset = self.scaled(10)
                mouse_pos = imgui.get_mouse_pos()
                mouse_clicked = imgui.is_mouse_clicked()
                y = pos.y + (size.y + text_size.y) / 2
                x1 = pos.x - offset - text_size.x
                x2 = pos.x + size.x + offset
                if not zoom_popup:
                    draw_list = imgui.get_foreground_draw_list()
                    col = imgui.get_color_u32_rgba(*globals.settings.style_text_dim)
                    draw_list.add_text(x1, y, col, icons.arrow_left_drop_circle)
                    draw_list.add_text(x2, y, col, icons.arrow_right_drop_circle)
                y_ok = y <= mouse_pos.y <= y + text_size.y
                clicked_left = mouse_clicked and x1 <= mouse_pos.x <= x1 + text_size.x and y_ok
                clicked_right = mouse_clicked and x2 <= mouse_pos.x <= x2 + text_size.x and y_ok
                imgui.pop_font()
                change_id = None
                idx = carousel_ids.index(game.id)
                if imgui.is_key_pressed(glfw.KEY_LEFT, repeat=True) or clicked_left:
                    idx -= 1
                    if idx == -1:
                        idx = len(carousel_ids) - 1
                    change_id = carousel_ids[idx]
                if imgui.is_key_pressed(glfw.KEY_RIGHT, repeat=True) or clicked_right:
                    idx += 1
                    if idx == len(carousel_ids):
                        idx = 0
                    change_id = carousel_ids[idx]
                if change_id is not None:
                    utils.push_popup(self.draw_game_info_popup, globals.games[change_id], carousel_ids).uuid = popup_uuid
                    return 1, True
        return return_args

    def draw_about_popup(self, popup_uuid: str = ""):
        def popup_content():
            _60 = self.scaled(60)
            _230 = self.scaled(230)
            imgui.begin_group()
            imgui.dummy(_60, _230)
            imgui.same_line()
            self.icon_texture.render(_230, _230, rounding=self.scaled(globals.settings.style_corner_radius))
            imgui.same_line()
            imgui.begin_group()
            imgui.push_font(imgui.fonts.big)
            imgui.text("F95Checker")
            imgui.pop_font()
            imgui.text(f"Version {globals.version_name}")
            imgui.text("Made with <3 by WillyJL")
            imgui.text("")
            imgui.text(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
            imgui.text(f"OpenGL {'.'.join(str(gl.glGetInteger(num)) for num in (gl.GL_MAJOR_VERSION, gl.GL_MINOR_VERSION))},  Py {OpenGL.__version__}")
            imgui.text(f"GLFW {'.'.join(str(num) for num in glfw.get_version())},  Py {glfw.__version__}")
            imgui.text(f"ImGui {imgui.get_version()},  Py {imgui.__version__}")
            imgui.text(f"Qt {QtCore.QT_VERSION_STR},  Py {QtCore.PYQT_VERSION_STR}")
            if globals.os is Os.Linux:
                imgui.text(f"{platform.system()} {platform.release()}")
            elif globals.os is Os.Windows:
                imgui.text(f"{platform.system()} {platform.release()} {platform.version()}")
            elif globals.os is Os.MacOS:
                imgui.text(f"{platform.system()} {platform.release()}")
            imgui.end_group()
            imgui.same_line()
            imgui.dummy(_60, _230)
            imgui.end_group()
            imgui.spacing()
            width = imgui.get_content_region_available_width()
            btn_width = (width - 2 * imgui.style.item_spacing.x) / 3
            if imgui.button(f"{icons.open_in_new} F95zone Thread", width=btn_width):
                callbacks.open_webpage(tool_page)
            imgui.same_line()
            if imgui.button(f"{icons.github} GitHub Repo", width=btn_width):
                callbacks.open_webpage(github_page)
            imgui.same_line()
            if imgui.button(f"{icons.link_variant} Donate + Links", width=btn_width):
                callbacks.open_webpage(developer_page)
            imgui.spacing()
            imgui.spacing()
            imgui.push_text_wrap_pos(width)
            imgui.text("This software is licensed under the 3rd revision of the GNU General Public License (GPLv3) and is provided to you for free. "
                       "Furthermore, due to its license, it is also free as in freedom: you are free to use, study, modify and share this software "
                       "in whatever way you wish as long as you keep the same license.")
            imgui.spacing()
            imgui.spacing()
            imgui.text("However, F95Checker is actively developed by one person only, WillyJL, and not with the aim of profit but out of personal "
                       "interest and benefit for the whole F95zone community. Donations are although greatly appreciated and aid the development "
                       "of this software. You can find donation links above.")
            imgui.spacing()
            imgui.spacing()
            imgui.text("If you find bugs or have some feedback, don't be afraid to let me know either on GitHub (using issues or pull requests) "
                       "or on F95zone (in the thread comments or in direct messages).")
            imgui.spacing()
            imgui.spacing()
            imgui.text("Please note that this software is not ( yet ;) ) officially affiliated with the F95zone platform.")
            imgui.spacing()
            imgui.spacing()
            imgui.text("")
            imgui.push_font(imgui.fonts.big)
            size = imgui.calc_text_size("Cool people")
            imgui.set_cursor_pos_x((width - size.x + imgui.style.scrollbar_size) / 2)
            imgui.text("Cool people")
            imgui.pop_font()
            imgui.spacing()
            imgui.spacing()
            imgui.text("Supporters:")
            for name in [
                "FaceCrap",
                "WhiteVanDaycare",
                "ascsd",
                "Jarulf",
                "rozzic",
                "Belfaier",
                "warez_gamez",
                "DeadMoan",
                "And 3 anons"
            ]:
                if imgui.get_content_region_available_width() < imgui.calc_text_size(name).x + self.scaled(20):
                    imgui.dummy(0, 0)
                imgui.bullet_text(name)
                imgui.same_line(spacing=16)
            imgui.spacing()
            imgui.spacing()
            imgui.text("Contributors:")
            imgui.bullet()
            imgui.text("r37r05p3C7: Tab idea and customization, timeline, many extension features")
            imgui.bullet()
            imgui.text("littleraisins: Fixes, features and misc ideas from the (defunct) 'X' fork")
            imgui.bullet()
            imgui.text("FaceCrap: Multiple small fixes, improvements and finetuning")
            imgui.bullet()
            imgui.text("blackop: Proxy support, temporary ratelimit fix, linux login fix")
            imgui.bullet()
            imgui.text("Sam: Support from F95zone side to make much this possible")
            imgui.bullet()
            imgui.text("GR3ee3N: Optimized build workflows and other PRs")
            imgui.bullet()
            imgui.text("batblue: MacOS suppport and feedback guy")
            imgui.bullet()
            imgui.text("unroot: Linux support and feedback guy")
            imgui.bullet()
            imgui.text("ploper26: Suggested HEAD checks (no longer used)")
            imgui.bullet()
            imgui.text("ascsd: Helped with brainstorming on some issues and gave some tips")
            imgui.spacing()
            imgui.spacing()
            imgui.text("Community:")
            for name in [
                "abada25",
                "AtotehZ",
                "bitogno",
                "BrockLanders",
                "d_pedestrian",
                "Danv",
                "DarK x Duke",
                "Dukez",
                "GrammerCop",
                "harem.king",
                "MillenniumEarl",
                "simple_human",
                "SmurfyBlue",
                "WhiteVanDaycare",
                "yohudood",
                "And others that I might be forgetting"
            ]:
                if imgui.get_content_region_available_width() < imgui.calc_text_size(name).x + self.scaled(20):
                    imgui.dummy(0, 0)
                imgui.bullet_text(name)
                imgui.same_line(spacing=16)
            imgui.pop_text_wrap_pos()
        return utils.popup("About F95Checker", popup_content, closable=True, outside=True, popup_uuid=popup_uuid)

    def draw_tag_highlights_popup(self, popup_uuid: str = ""):
        def popup_content():
            imgui.text_disabled("Right click tags to cycle highlighting options")
            search = ""
            imgui.set_next_item_width(-imgui.FLOAT_MIN)
            _, search = imgui.input_text_with_hint(f"###tag_highlights_input", "Search tags...", search)
            imgui.begin_child(f"###tag_highlights_frame", width=min(imgui.io.display_size.x * 0.5, self.scaled(600)), height=imgui.io.display_size.y * 0.5)
            pad = 2 * imgui.style.frame_padding.x + imgui.style.item_spacing.x
            for tag in Tag:
                if not search or search in tag.text or search in tag.name:
                    if imgui.get_content_region_available_width() < imgui.calc_text_size(tag.name).x + pad:
                        imgui.dummy(0, 0)
                    self.draw_tag_widget(tag, quick_filter=False)
                imgui.same_line()
            imgui.end_child()
        return utils.popup("Tag highlight preferences", popup_content, closable=True, outside=True, popup_uuid=popup_uuid)

    def draw_tabbar(self):
        display_tab = globals.settings.display_tab
        select_tab = self.current_tab is not display_tab
        new_tab = None
        if Tab.instances and not (globals.settings.filter_all_tabs and self.filtering):
            if imgui.begin_tab_bar("###tabbar", flags=self.tabbar_flags):
                hide = globals.settings.hide_empty_tabs
                count = len(self.show_games_ids.get(None, ()))
                if (count or not hide) and imgui.begin_tab_item(f"{Tab.first_tab_label()} ({count})###tab_-1")[0]:
                    new_tab = None
                    imgui.end_tab_item()
                for tab in Tab.instances:
                    count = len(self.show_games_ids.get(tab, ()))
                    if hide and not count:
                        continue
                    if tab.color:
                        imgui.push_style_color(imgui.COLOR_TAB, *tab.color[:3], 0.5)
                        imgui.push_style_color(imgui.COLOR_TAB_ACTIVE, *tab.color)
                        imgui.push_style_color(imgui.COLOR_TAB_HOVERED, *tab.color)
                        imgui.push_style_color(imgui.COLOR_TEXT, *colors.foreground_color(tab.color))
                    if imgui.begin_tab_item(
                        f"{tab.icon} {tab.name or 'New Tab'} ({count})###tab_{tab.id}",
                        flags=imgui.TAB_ITEM_SET_SELECTED if select_tab and tab is display_tab else 0
                    )[0]:
                        new_tab = tab
                        imgui.end_tab_item()
                    if tab.color:
                        imgui.pop_style_color(4)
                    context_id = f"###tab_{tab.id}_context"
                    set_focus = not imgui.is_popup_open(context_id)
                    if imgui.begin_popup_context_item(context_id):
                        imgui.set_next_item_width(imgui.get_content_region_available_width())
                        if set_focus:
                            imgui.set_keyboard_focus_here()
                        changed, value = imgui.input_text_with_hint(f"###tab_name_{tab.id}", "Tab name", tab.name)
                        setter_extra = functools.partial(lambda t, _=None: async_thread.run(db.update_tab(t, "name")), tab)
                        if changed:
                            tab.name = value
                            setter_extra()
                        if imgui.begin_popup_context_item(f"###tab_name_{tab.id}_context"):
                            utils.text_context(tab, "name", setter_extra)
                            imgui.end_popup()
                        set_focus = False
                        if imgui.button(tab.icon):
                            imgui.open_popup(f"###tab_icon_{tab.id}")
                            set_focus = True
                        if imgui.begin_popup(f"###tab_icon_{tab.id}"):
                            search = ""
                            imgui.set_next_item_width(-imgui.FLOAT_MIN)
                            if set_focus:
                                imgui.set_keyboard_focus_here()
                            _, search = imgui.input_text_with_hint(f"###tab_icons_{tab.id}_search", "Search icons...", search)
                            imgui.begin_child(f"###tab_icons_{tab.id}_frame", width=self.scaled(250), height=imgui.io.display_size.y * 0.35)
                            for name, icon in icons.names.items():
                                if not search or search in name or search in icon:
                                    if imgui.selectable(f"{icon}  {name}")[0]:
                                        tab.icon = icon
                                        async_thread.run(db.update_tab(tab, "icon"))
                                        imgui.close_current_popup()
                            imgui.end_child()
                            imgui.end_popup()
                        imgui.same_line()
                        if imgui.button("Reset icon", width=imgui.get_content_region_available_width()):
                            tab.icon = Tab.base_icon()
                            async_thread.run(db.update_tab(tab, "icon"))
                        color = tab.color[:3] if tab.color else (0.0, 0.0, 0.0)
                        changed, value = imgui.color_edit3(f"###tab_color_{tab.id}", *color, flags=imgui.COLOR_EDIT_NO_INPUTS)
                        if changed:
                            tab.color = (*value, 1.0)
                            async_thread.run(db.update_tab(tab, "color"))
                        imgui.same_line()
                        if imgui.button("Reset color", width=imgui.get_content_region_available_width()):
                            tab.color = None
                            async_thread.run(db.update_tab(tab, "color"))
                        if imgui.button(f"{icons.trash_can_outline} Close (keeps games)"):
                            close_callback = functools.partial(lambda t: async_thread.run(db.delete_tab(t)), tab)
                            if globals.settings.confirm_on_remove:
                                buttons = {
                                    f"{icons.check} Yes": close_callback,
                                    f"{icons.cancel} No": None
                                }
                                utils.push_popup(
                                    msgbox.msgbox, f"Close tab {tab.icon} {tab.name or 'New Tab'}",
                                    "Are you sure you want to close this tab?\n"
                                    f"The games will go back to {Tab.first_tab_label()} tab.",
                                    MsgBox.warn,
                                    buttons
                                )
                            else:
                                close_callback()
                        imgui.end_popup()
                imgui.end_tab_bar()
        if new_tab is not self.current_tab:
            for game in globals.games.values():
                game.selected = False
            self.current_tab = new_tab
            self.recalculate_ids = True
            globals.settings.display_tab = new_tab
            async_thread.run(db.update_settings("display_tab"))

    def calculate_ids(self, sorts: imgui.core._ImGuiTableSortSpecs):
        manual_sort = cols.manual_sort.enabled
        if manual_sort != self.prev_manual_sort:
            self.prev_manual_sort = manual_sort
            self.recalculate_ids = True
        if self.prev_filters != self.filters:
            self.prev_filters = self.filters.copy()
            self.recalculate_ids = True
        if sorts.specs_count > 0:
            self.sorts = []
            for sort_spec in sorts.specs:
                self.sorts.insert(0, SortSpec(index=sort_spec.column_index, reverse=bool(sort_spec.sort_direction - 1)))
        if sorts.specs_dirty or self.recalculate_ids:
            self.recalculate_ids = False
            # Pick base ID list
            if manual_sort:
                changed = False
                for id in globals.settings.manual_sort_list.copy():
                    if id not in globals.games:
                        globals.settings.manual_sort_list.remove(id)
                        changed = True
                for id in globals.games:
                    if id not in globals.settings.manual_sort_list:
                        globals.settings.manual_sort_list.insert(0, id)
                        changed = True
                if changed:
                    async_thread.run(db.update_settings("manual_sort_list"))
                base_ids = globals.settings.manual_sort_list
            else:
                base_ids = globals.games.keys()
            filtering = False
            # Filter globally by filters
            for flt in self.filters:
                match flt.mode.value:
                    case FilterMode.Archived.value:
                        key = lambda game, f: (game.archived is True)
                    case FilterMode.Custom.value:
                        key = lambda game, f: (game.custom is True)
                    case FilterMode.Exe_State.value:
                        key = lambda game, f: (
                            (not game.executables) if f.match is ExeState.Unset else
                            (bool(game.executables) and (game.executables_valid != (f.match is ExeState.Invalid)))
                        )
                    case FilterMode.Finished.value:
                        key = lambda game, f: (
                            (game.finished != "") if f.match else
                            (game.finished == (game.installed or game.version))
                        )
                    case FilterMode.Installed.value:
                        key = lambda game, f: (
                            (game.installed != "") if f.match else
                            (game.installed == game.version)
                        )
                    case FilterMode.Label.value:
                        key = lambda game, f: (f.match in game.labels)
                    case FilterMode.Rating.value:
                        key = lambda game, f: (game.rating == f.match)
                    case FilterMode.Score.value:
                        key = lambda game, f: (game.score >= f.match)
                    case FilterMode.Status.value:
                        key = lambda game, f: (game.status is f.match)
                    case FilterMode.Tag.value:
                        key = lambda game, f: (f.match in game.tags)
                    case FilterMode.Type.value:
                        key = lambda game, f: (game.type is f.match)
                    case FilterMode.Updated.value:
                        key = lambda game, f: (game.updated is True)
                    case _:
                        key = None
                if key is not None:
                    base_ids = filter(functools.partial(lambda f, k, id: f.invert != k(globals.games[id], f), flt, key), base_ids)
                    filtering = True
            # Filter globally by search
            if self.add_box_text:
                if self.add_box_valid:
                    id_matches = [match.id for match in utils.extract_thread_matches(self.add_box_text)]
                    base_ids = filter(lambda id: id in id_matches, base_ids)
                    filtering = True
                else:
                    search = self.add_box_text.lower()
                    def key(id):
                        game = globals.games[id]
                        return search in game.version.lower() or search in game.developer.lower() or search in game.name.lower() or search in game.notes.lower()
                    base_ids = filter(key, base_ids)
                    filtering = True
            self.filtering = filtering
            # Finally consume the iterators (was lazy up until now)
            base_ids = list(base_ids)
            # Sort globally by sortspecs
            if not manual_sort:
                for sort_spec in self.sorts:
                    match sort_spec.index:
                        case cols.type.index:
                            key = lambda id: globals.games[id].type.name
                        case cols.developer.index:
                            key = lambda id: globals.games[id].developer.lower()
                        case cols.last_updated.index:
                            key = lambda id: - globals.games[id].last_updated.value
                        case cols.last_launched.index:
                            key = lambda id: - globals.games[id].last_launched.value
                        case cols.added_on.index:
                            key = lambda id: - globals.games[id].added_on.value
                        case cols.finished.index:
                            key = lambda id: 2 if not globals.games[id].finished else 1 if globals.games[id].finished == (globals.games[id].installed or globals.games[id].version) else 0
                        case cols.installed.index:
                            key = lambda id: 2 if not globals.games[id].installed else 1 if globals.games[id].installed == globals.games[id].version else 0
                        case cols.rating.index:
                            key = lambda id: - globals.games[id].rating
                        case cols.notes.index:
                            key = lambda id: globals.games[id].notes.lower() or "z"
                        case cols.status_standalone.index:
                            key = lambda id: globals.games[id].status.value
                        case cols.score.index:
                            if globals.settings.weighted_score:
                                key = lambda id: - utils.bayesian_average(globals.games[id].score, globals.games[id].votes)
                            else:
                                key = lambda id: - globals.games[id].score
                        case _:  # Name and all others
                            key = lambda id: globals.games[id].name.lower()
                    base_ids.sort(key=key, reverse=sort_spec.reverse)
                base_ids.sort(key=lambda id: globals.games[id].archived)
                base_ids.sort(key=lambda id: globals.games[id].type is not Type.Unchecked)
            # Loop all tabs and filter by them
            self.show_games_ids = {
                tab: (
                    base_ids if filtering and globals.settings.filter_all_tabs else
                    list(filter(lambda id: tab is globals.games[id].tab, base_ids))
                )
                for tab in (None, *Tab.instances)
            }
            tab_games_ids = self.show_games_ids[self.current_tab]
            # Deselect things that arent't visible anymore
            for game in globals.games.values():
                if game.selected and game.id not in tab_games_ids:
                    game.selected = False
            sorts.specs_dirty = False
        else:
            tab_games_ids = self.show_games_ids[self.current_tab]

    def handle_game_hitbox_events(self, game: Game, drag_drop: bool = False):
        manual_sort = cols.manual_sort.enabled
        if imgui.is_item_hovered(imgui.HOVERED_ALLOW_WHEN_BLOCKED_BY_ACTIVE_ITEM):
            # Hover = image on refresh button
            self.hovered_game = game
            if imgui.is_item_clicked():
                self.game_hitbox_click = True
            if self.game_hitbox_click and not imgui.is_mouse_down():
                self.game_hitbox_click = False
                if imgui.is_key_down(glfw.KEY_LEFT_SHIFT):
                    # Shift + Left click = multi select
                    if self.selected_games_count and self.last_selected_game.selected:
                        tab_games_ids = self.show_games_ids[self.current_tab]
                        start = tab_games_ids.index(self.last_selected_game.id)
                        end = tab_games_ids.index(game.id)
                        if start > end:
                            start, end = end, start
                        for select in tab_games_ids[start:end + 1]:
                            globals.games[select].selected = True
                    else:
                        game.selected = True
                elif imgui.is_key_down(glfw.KEY_LEFT_CONTROL):
                    # Ctrl + Left click = single select
                    game.selected = not game.selected
                else:
                    if any(game.selected for game in globals.games.values()):
                        for game in globals.games.values():
                            game.selected = False
                    else:
                        # Left click = open game info popup
                        utils.push_popup(self.draw_game_info_popup, game, self.show_games_ids[self.current_tab].copy())
        # Left click drag = swap if in manual sort mode
        if imgui.begin_drag_drop_source(flags=self.game_hitbox_drag_drop_flags):
            self.game_hitbox_click = False
            payload = (globals.settings.manual_sort_list.index(game.id) if manual_sort else 0) + 1
            payload = payload.to_bytes(payload.bit_length(), sys.byteorder)
            imgui.set_drag_drop_payload("manual_swap", payload)
            imgui.end_drag_drop_source()
        if drag_drop and manual_sort:
            if imgui.begin_drag_drop_target():
                if payload := imgui.accept_drag_drop_payload("manual_swap", flags=self.game_hitbox_drag_drop_flags):
                    payload = int.from_bytes(payload, sys.byteorder)
                    payload = payload - 1
                    lst = globals.settings.manual_sort_list
                    switch = lst.index(game.id)
                    lst[switch], lst[payload] = lst[payload], lst[switch]
                    async_thread.run(db.update_settings("manual_sort_list"))
                    self.recalculate_ids = True
                imgui.end_drag_drop_target()
        context_id = f"###{game.id}_context"
        if (imgui.is_topmost() or imgui.is_popup_open(context_id)) and imgui.begin_popup_context_item(context_id):
            # Right click = context menu
            if game.selected:
                self.draw_game_context_menu()
            else:
                self.draw_game_context_menu(game)
            imgui.end_popup()

    def sync_scroll(self):
        if (scroll_max_y := imgui.get_scroll_max_y()) > 1.0:
            if self.switched_display_mode:
                imgui.set_scroll_y(self.scroll_percent * scroll_max_y)
                self.switched_display_mode = False
            else:
                self.scroll_percent = imgui.get_scroll_y() / scroll_max_y

    @property
    def games_table_id(self):
        tab_id = self.current_tab.id if self.current_tab else -1
        return f"###game_list{tab_id if globals.settings.independent_tab_views else ''}"

    def draw_games_list(self):
        # Hack: custom toggles in table header right click menu by adding tiny empty "ghost" columns and hiding them
        # by starting the table render before the content region.
        ghost_column_size = (imgui.style.frame_padding.x + imgui.style.cell_padding.x * 2)
        offset = ghost_column_size * self.ghost_columns_enabled_count
        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() - offset)
        if imgui.begin_table(
            self.games_table_id,
            column=cols.count,
            flags=self.game_list_table_flags,
            outer_size_height=-imgui.get_frame_height_with_spacing()  # Bottombar
        ):
            # Setup columns
            self.ghost_columns_enabled_count = 0
            can_sort = 0
            for column in cols.items:
                imgui.table_setup_column(column.name, column.flags | (can_sort * column.sortable))
                # Enabled columns
                column.enabled = bool(imgui.table_get_column_flags(column.index) & imgui.TABLE_COLUMN_IS_ENABLED)
                # Ghosts count
                if column.ghost and column.enabled:
                    self.ghost_columns_enabled_count += 1
                # Set sorting condition
                if column is cols.manual_sort:
                    can_sort = imgui.TABLE_COLUMN_NO_SORT * cols.manual_sort.enabled
            imgui.table_setup_scroll_freeze(0, 1)  # Sticky column headers
            self.calculate_ids(imgui.table_get_sort_specs())

            # Column headers
            imgui.table_next_row(imgui.TABLE_ROW_HEADERS)
            for column in cols.items:
                imgui.table_set_column_index(column.index)
                imgui.table_header(column.header)

            # Loop rows
            self.sync_scroll()
            frame_height = imgui.get_frame_height()
            notes_width = None
            for id in self.show_games_ids[self.current_tab]:
                game = globals.games[id]
                imgui.table_next_row()
                imgui.table_set_column_index(cols.separator.index)
                # Skip if outside view
                if not imgui.is_rect_visible(imgui.io.display_size.x, frame_height):
                    imgui.dummy(0, frame_height)
                    continue
                # Base row height with a buttom to align the following text calls to center vertically
                imgui.button("", width=imgui.FLOAT_MIN)
                # Loop columns
                for column in cols.items:
                    if not column.enabled or column.ghost:
                        continue
                    imgui.table_set_column_index(column.index)
                    match column.index:
                        case cols.play_button.index:
                            self.draw_game_play_button(game, cols.play_button.name[0])
                        case cols.type.index:
                            self.draw_type_widget(game.type, align=True)
                        case cols.name.index:
                            if globals.settings.show_remove_btn:
                                self.draw_game_remove_button(game, icons.trash_can_outline)
                                imgui.same_line()
                            if game.archived:
                                self.draw_game_archive_icon(game)
                                imgui.same_line()
                            if game.updated:
                                self.draw_game_update_icon(game)
                                imgui.same_line()
                            if game.unknown_tags_flag:
                                self.draw_game_unknown_tags_icon(game)
                                imgui.same_line()
                            self.draw_game_name_text(game)
                            if game.notes:
                                imgui.same_line()
                                imgui.text_colored(icons.draw_pen, 0.85, 0.20, 0.85)
                            if game.labels:
                                imgui.same_line()
                                self.draw_game_labels_widget(game, wrap=False, small=True, align=True)
                            if cols.status.enabled and game.status is not Status.Normal:
                                imgui.same_line()
                                self.draw_status_widget(game.status)
                            if cols.version.enabled or cols.finished_version.enabled or cols.installed_version.enabled:
                                imgui.same_line()
                                versions = []
                                if cols.version.enabled:
                                    if cols.finished_version.enabled and game.finished and game.finished != (game.installed or game.version):
                                        versions.append(f"{cols.finished_version.name[0]} {game.finished}")
                                    if cols.installed_version.enabled and game.installed and game.installed != game.version:
                                        versions.append(f"{cols.installed_version.name[0]} {game.installed}")
                                    versions.append(f"{cols.version.name[0]} {game.version}")
                                elif game.finished == game.installed != "":
                                    if cols.finished_version.enabled:
                                        versions.append(f"{cols.finished_version.name[0]} {game.finished}")
                                    elif cols.installed_version.enabled:
                                        versions.append(f"{cols.installed_version.name[0]} {game.installed}")
                                else:
                                    if cols.finished_version.enabled and game.finished:
                                        versions.append(f"{cols.finished_version.name[0]} {game.finished}")
                                    if cols.installed_version.enabled and game.installed:
                                        versions.append(f"{cols.installed_version.name[0]} {game.installed}")
                                imgui.text_disabled("  |  ".join(versions))
                        case cols.developer.index:
                            imgui.text(game.developer or "Unknown")
                        case cols.last_updated.index:
                            imgui.push_font(imgui.fonts.mono)
                            imgui.text(game.last_updated.display or "Unknown")
                            imgui.pop_font()
                        case cols.last_launched.index:
                            imgui.push_font(imgui.fonts.mono)
                            imgui.text(game.last_launched.display or "Never")
                            imgui.pop_font()
                        case cols.added_on.index:
                            imgui.push_font(imgui.fonts.mono)
                            imgui.text(game.added_on.display)
                            imgui.pop_font()
                        case cols.finished.index:
                            self.draw_game_finished_checkbox(game)
                        case cols.installed.index:
                            self.draw_game_installed_checkbox(game)
                        case cols.rating.index:
                            self.draw_game_rating_widget(game)
                        case cols.notes.index:
                            if notes_width is None:
                                notes_width = imgui.get_content_region_available_width() - 2 * imgui.style.item_spacing.x
                            self.draw_game_notes_widget(game, multiline=False, width=notes_width)
                        case cols.open_thread.index:
                            self.draw_game_open_thread_button(game, cols.open_thread.name[0])
                        case cols.copy_link.index:
                            self.draw_game_copy_link_button(game, cols.copy_link.name[0])
                        case cols.open_folder.index:
                            self.draw_game_open_folder_button(game, cols.open_folder.name[0])
                        case cols.status_standalone.index:
                            self.draw_status_widget(game.status)
                        case cols.score.index:
                            with imgui.begin_group():
                                imgui.text(f"{game.score:.1f}")
                                imgui.same_line()
                                imgui.text_disabled(f"({game.votes})")
                            if imgui.is_item_hovered():
                                with imgui.begin_tooltip():
                                    imgui.text(f"{utils.bayesian_average(game.score, game.votes):.2f}")
                # Row hitbox
                imgui.same_line()
                imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() - imgui.style.frame_padding.y)
                if game.selected:
                    imgui.push_alpha(0.5)
                    imgui.get_window_draw_list().add_rect_filled(
                        0, pos_y := imgui.get_cursor_screen_pos().y + 1,
                        imgui.io.display_size.x, pos_y + frame_height + 2 * imgui.style.cell_padding.y,
                        imgui.get_color_u32_rgba(*globals.settings.style_accent)
                    )
                    imgui.pop_alpha()
                imgui.push_alpha(0.25)
                imgui.selectable(f"###{game.id}_hitbox", False, flags=imgui.SELECTABLE_SPAN_ALL_COLUMNS, height=frame_height)
                imgui.pop_alpha()
                self.handle_game_hitbox_events(game, drag_drop=True)

            imgui.end_table()

    def tick_list_columns(self):
        # Hack: get sort and column specs for list mode in grid and kanban mode
        pos = imgui.get_cursor_pos_y()
        if imgui.begin_table(
            self.games_table_id,
            column=cols.count,
            flags=self.game_list_table_flags,
            outer_size_height=1
        ):
            can_sort = 0
            for column in cols.items:
                imgui.table_setup_column("", column.flags | (can_sort * column.sortable))
                # Enabled columns
                column.enabled = bool(imgui.table_get_column_flags(column.index) & imgui.TABLE_COLUMN_IS_ENABLED)
                # Set sorting condition
                if column is cols.manual_sort:
                    can_sort = imgui.TABLE_COLUMN_NO_SORT * cols.manual_sort.enabled
            self.calculate_ids(imgui.table_get_sort_specs())
            imgui.end_table()
        imgui.set_cursor_pos_y(pos)

    def get_game_cell_config(self):
        side_indent = imgui.style.item_spacing.x * 2
        checkboxes = cols.finished.enabled + cols.installed.enabled
        buttons = cols.play_button.enabled + cols.open_folder.enabled + cols.open_thread.enabled + cols.copy_link.enabled
        action_items = checkboxes + buttons
        bg_col = imgui.get_color_u32_rgba(*imgui.style.colors[imgui.COLOR_TABLE_ROW_BACKGROUND_ALT])
        frame_height = imgui.get_frame_height()

        actions_width = (
            imgui.style.item_spacing.x * action_items +      # Spacing * 6 action items
            imgui.style.frame_padding.x * 2 * buttons +      # Button padding * 2 sides * 4 buttons
            imgui.style.item_inner_spacing.x * checkboxes +  # Checkbox to label spacing * 2 checkboxes
            frame_height * checkboxes +          # (Checkbox height = width) * 2 checkboxes
            imgui.calc_text_size(                            # Text
                cols.play_button.name[0] * cols.play_button.enabled +
                cols.open_folder.name[0] * cols.open_folder.enabled +
                cols.open_thread.name[0] * cols.open_thread.enabled +
                cols.copy_link.name[0] * cols.copy_link.enabled +
                cols.finished.name[0] * cols.finished.enabled +
                cols.installed.name[0] * cols.installed.enabled
            ).x
        )

        base_width = max(
            (  # Type / Version line
                2 * self.get_type_label_width()
            ),
            (  # Clustered data
                imgui.style.item_spacing.x +  # Between text
                imgui.calc_text_size(f"{cols.last_updated.name[0]}00/00/0000").x  # Text
            )
        )

        min_cell_width = (
            side_indent * 2 +  # Side indent * 2 sides
            max(actions_width, base_width)
        )

        min_expand_width = (
            side_indent * 2 +  # Side indent * 2 sides
            max(
                (  # Expanded actions text
                    actions_width +
                    imgui.calc_text_size(
                        " Play" * cols.play_button.enabled +
                        " Folder" * cols.open_folder.enabled +
                        " Thread" * cols.open_thread.enabled +
                        " Link" * cols.copy_link.enabled
                    ).x
                ),
                base_width
            )
        )

        config = (side_indent, action_items, bg_col, frame_height)
        return min_cell_width, min_expand_width, config

    def draw_game_cell(self, game: Game, drag_drop: bool, draw_list, cell_width: float, expand: bool, img_height: float, config: tuple):
        (side_indent, action_items, bg_col, frame_height) = config
        draw_list.channels_split(2)
        draw_list.channels_set_current(1)
        pos = imgui.get_cursor_pos()
        rounding = self.scaled(globals.settings.style_corner_radius)
        imgui.begin_group()
        # Image
        if game.image.missing:
            text = "Image missing!"
            text_size = imgui.calc_text_size(text)
            showed_img = imgui.is_rect_visible(cell_width, img_height)
            if text_size.x < cell_width:
                imgui.set_cursor_pos((pos.x + (cell_width - text_size.x) / 2, pos.y + img_height / 2))
                self.draw_game_image_missing_text(game, text)
                imgui.set_cursor_pos(pos)
            imgui.dummy(cell_width, img_height)
        elif game.image.invalid:
            text = "Invalid image!"
            text_size = imgui.calc_text_size(text)
            showed_img = imgui.is_rect_visible(cell_width, img_height)
            if text_size.x < cell_width:
                imgui.set_cursor_pos((pos.x + (cell_width - text_size.x) / 2, pos.y + img_height / 2))
                self.draw_hover_text(
                    text=text,
                    hover_text="This thread's image has an unrecognised format and couldn't be loaded!"
                )
                imgui.set_cursor_pos(pos)
            imgui.dummy(cell_width, img_height)
        else:
            crop = game.image.crop_to_ratio(globals.settings.cell_image_ratio, fit=globals.settings.fit_images)
            showed_img = game.image.render(cell_width, img_height, *crop, rounding=rounding, flags=imgui.DRAW_ROUND_CORNERS_TOP)
        # Alignments
        imgui.indent(side_indent)
        imgui.push_text_wrap_pos(pos.x + cell_width - side_indent)
        imgui.spacing()
        imgui.spacing()
        # Image overlays
        if showed_img:
            old_pos = imgui.get_cursor_pos()
            # Remove button
            if globals.settings.show_remove_btn:
                imgui.set_cursor_pos((pos.x + imgui.style.item_spacing.x, pos.y + imgui.style.item_spacing.y))
                self.draw_game_remove_button(game, icons.trash_can_outline)
            # Type
            if cols.type.enabled:
                imgui.set_cursor_pos((pos.x + imgui.style.item_spacing.x, pos.y + img_height + imgui.style.item_spacing.y - frame_height / 2))
                self.draw_type_widget(game.type, wide=False)
            # Version
            if cols.version.enabled:
                cut = len(game.version)
                while (w := imgui.calc_text_size(game.version[:cut]).x) > cell_width / 2:
                    cut -= 1
                imgui.set_cursor_pos((pos.x + cell_width - side_indent - imgui.style.item_spacing.x - w, pos.y + img_height + imgui.style.item_spacing.y - frame_height / 2))
                self.begin_framed_text((0.3, 0.3, 0.3, 1.0), interaction=True)
                imgui.small_button(game.version[:cut])
                if imgui.is_item_hovered() and cut != len(game.version):
                    imgui.set_tooltip(game.version)
                self.end_framed_text(interaction=True)
            imgui.set_cursor_pos(old_pos)
        # Name line
        imgui.push_font(imgui.fonts.bold)
        self.draw_game_name_text(game)
        imgui.pop_font()
        # Buttons line
        if action_items:
            if imgui.is_rect_visible(cell_width, frame_height):
                # Play Button
                did_newline = False
                if cols.play_button.enabled:
                    if did_newline:
                        imgui.same_line()
                    self.draw_game_play_button(game, f"{cols.play_button.name[0]}{' Play' if expand else ''}")
                    did_newline = True
                # Open Folder
                if cols.open_folder.enabled:
                    if did_newline:
                        imgui.same_line()
                    self.draw_game_open_folder_button(game, f"{cols.open_folder.name[0]}{' Folder' if expand else ''}")
                    did_newline = True
                # Open Thread
                if cols.open_thread.enabled:
                    if did_newline:
                        imgui.same_line()
                    self.draw_game_open_thread_button(game, f"{cols.open_thread.name[0]}{' Thread' if expand else ''}")
                    did_newline = True
                # Copy Link
                if cols.copy_link.enabled:
                    if did_newline:
                        imgui.same_line()
                    self.draw_game_copy_link_button(game, f"{cols.copy_link.name[0]}{' Link' if expand else ''}")
                    did_newline = True
                # Finished
                if cols.finished.enabled:
                    if did_newline:
                        imgui.same_line()
                    self.draw_game_finished_checkbox(game, cols.finished.name[0])
                    did_newline = True
                # Installed
                if cols.installed.enabled:
                    if did_newline:
                        imgui.same_line()
                    self.draw_game_installed_checkbox(game, cols.installed.name[0])
                    did_newline = True
            else:
                # Skip if outside view
                imgui.dummy(0, frame_height)
        # Cluster data
        cluster = False
        if game.archived:
            self.draw_game_archive_icon(game)
            imgui.same_line()
            cluster = True
        if game.updated:
            self.draw_game_update_icon(game)
            imgui.same_line()
            cluster = True
        if game.unknown_tags_flag:
            self.draw_game_unknown_tags_icon(game)
            imgui.same_line()
            cluster = True
        if game.notes:
            imgui.text_colored(icons.draw_pen, 0.85, 0.20, 0.85)
            imgui.same_line()
            cluster = True
        if (cols.status.enabled or cols.status_standalone.enabled) and game.status is not Status.Normal:
            self.draw_status_widget(game.status)
            imgui.same_line()
            cluster = True
        if game.labels:
            self.draw_game_labels_widget(game, short=True, align=False)
            imgui.same_line()
            cluster = True
        pad = 3 * imgui.style.item_spacing.x
        def _cluster_text(name, text):
            nonlocal cluster
            if imgui.get_content_region_available_width() < imgui.calc_text_size(name[0] + text[:10]).x + pad:
                imgui.dummy(0, 0)
            imgui.text_disabled(name[0])
            if imgui.is_item_hovered():
                imgui.set_tooltip(name[2:])
            imgui.same_line()
            utils.wrap_text(text, width=cell_width - side_indent, offset=imgui.get_cursor_pos_x() - pos.x)
            imgui.same_line(spacing=pad)
            cluster = True
        if cols.score.enabled:
            _cluster_text(cols.score.name, f"{game.score:.1f} ({game.votes})")
        if cols.last_updated.enabled:
            _cluster_text(cols.last_updated.name, game.last_updated.display or "Unknown")
        if cols.last_launched.enabled:
            _cluster_text(cols.last_launched.name, game.last_launched.display or "Never")
        if cols.added_on.enabled:
            _cluster_text(cols.added_on.name, game.added_on.display)
        if cols.rating.enabled:
            if imgui.get_content_region_available_width() < imgui.calc_text_size(icons.star * 5).x + pad:
                imgui.dummy(0, 0)
            self.draw_game_rating_widget(game)
            imgui.same_line(spacing=pad)
            cluster = True
        if cols.developer.enabled:
            _cluster_text(cols.developer.name, game.developer)
        if cols.finished_version.enabled or cols.installed_version.enabled:
            if cols.version.enabled:
                if cols.finished_version.enabled and game.finished and game.finished != (game.installed or game.version):
                    _cluster_text(cols.finished_version.name, game.finished)
                if cols.installed_version.enabled and game.installed and game.installed != game.version:
                    _cluster_text(cols.installed_version.name, game.installed)
            elif game.finished == game.installed != "":
                if cols.finished_version.enabled:
                    _cluster_text(cols.finished_version.name, game.finished)
                elif cols.installed_version.enabled:
                    _cluster_text(cols.installed_version.name, game.installed)
            else:
                if cols.finished_version.enabled and game.finished:
                    _cluster_text(cols.finished_version.name, game.finished)
                if cols.installed_version.enabled and game.installed:
                    _cluster_text(cols.installed_version.name, game.installed)
        if cluster:
            imgui.dummy(0, 0)
        # Notes line
        if cols.notes.enabled:
            if imgui.is_rect_visible(cell_width, frame_height):
                self.draw_game_notes_widget(game, multiline=False, width=cell_width - 2 * side_indent)
            else:
                # Skip if outside view
                imgui.dummy(0, frame_height)
        # Cell hitbox
        imgui.pop_text_wrap_pos()
        imgui.spacing()
        imgui.spacing()
        imgui.end_group()
        draw_list.channels_set_current(0)
        imgui.set_cursor_pos(pos)
        cell_height = imgui.get_item_rect_size().y
        if imgui.is_rect_visible(cell_width, cell_height):
            # Skip if outside view
            imgui.invisible_button(f"###{game.id}_hitbox", cell_width, cell_height)
            self.handle_game_hitbox_events(game, drag_drop=drag_drop)
            rect_min = imgui.get_item_rect_min()
            rect_max = imgui.get_item_rect_max()
            if game.selected:
                imgui.push_alpha(0.5)
                draw_list.add_rect_filled(
                    *rect_min, *rect_max, imgui.get_color_u32_rgba(*globals.settings.style_accent),
                    rounding=rounding, flags=imgui.DRAW_ROUND_CORNERS_ALL
                )
                imgui.pop_alpha()
            else:
                draw_list.add_rect_filled(*rect_min, *rect_max, bg_col, rounding=rounding, flags=imgui.DRAW_ROUND_CORNERS_ALL)
        else:
            imgui.dummy(cell_width, cell_height)
        draw_list.channels_merge()

    def draw_games_grid(self):
        # Configure table
        self.tick_list_columns()
        min_cell_width, min_expand_width, cell_config = self.get_game_cell_config()
        padding = self.scaled(8)
        avail = imgui.get_content_region_available_width()
        column_count = globals.settings.grid_columns
        while (cell_width := (avail - padding * 2 * column_count) / column_count) < min_cell_width and column_count > 1:
            column_count -= 1
        expand = cell_width > min_expand_width
        img_height = cell_width / globals.settings.cell_image_ratio
        imgui.push_style_var(imgui.STYLE_CELL_PADDING, (padding, padding))
        if imgui.begin_table(
            "###game_grid",
            column=column_count,
            flags=self.game_grid_table_flags,
            outer_size_height=-imgui.get_frame_height_with_spacing()  # Bottombar
        ):
            # Setup
            for _ in range(column_count):
                imgui.table_setup_column("", imgui.TABLE_COLUMN_WIDTH_STRETCH)

            # Loop cells
            self.sync_scroll()
            draw_list = imgui.get_window_draw_list()
            for id in self.show_games_ids[self.current_tab]:
                game = globals.games[id]
                imgui.table_next_column()
                self.draw_game_cell(game, True, draw_list, cell_width, expand, img_height, cell_config)

            imgui.end_table()
        imgui.pop_style_var()

    def draw_games_kanban(self):
        # Configure table
        self.tick_list_columns()
        cell_width, _, cell_config = self.get_game_cell_config()
        padding = self.scaled(4)
        imgui.push_style_var(imgui.STYLE_CELL_PADDING, (padding, padding))
        img_height = cell_width / globals.settings.cell_image_ratio
        cells_per_column = 1
        column_count = len(Label.instances) + 1
        avail = imgui.get_content_region_available_width()
        table_width = lambda: (padding * 2 + (cell_width + imgui.style.item_spacing.x) * cells_per_column + imgui.style.scrollbar_size) * column_count
        while table_width() < avail:
            cells_per_column += 1
        cells_per_column = max(cells_per_column - 1, 1)
        if imgui.begin_table(
            "###game_kanban",
            column=column_count,
            flags=self.game_kanban_table_flags,
            inner_width=table_width(),
            outer_size_width=-imgui.style.scrollbar_size,
            outer_size_height=-imgui.get_frame_height_with_spacing()  # Bottombar
        ):
            # Setup columns
            not_labelled = len(Label.instances)
            for label in Label.instances:
                imgui.table_setup_column(label.name, imgui.TABLE_COLUMN_WIDTH_STRETCH)
            imgui.table_setup_column("Not Labelled", imgui.TABLE_COLUMN_WIDTH_STRETCH)
            tab_games_ids = self.show_games_ids[self.current_tab]

            # Column headers
            imgui.table_setup_scroll_freeze(0, 1)  # Sticky column headers
            imgui.table_next_row(imgui.TABLE_ROW_HEADERS)
            for label_i, label in enumerate(Label.instances):
                imgui.table_set_column_index(label_i)
                count = 0
                for id in tab_games_ids:
                    if label in globals.games[id].labels:
                        count += 1
                imgui.table_header(f"{label.name} ({count})")
            imgui.table_set_column_index(not_labelled)
            count = 0
            for id in tab_games_ids:
                if not globals.games[id].labels:
                    count += 1
            imgui.table_header(f"Not Labelled ({count})")

            # Loop cells
            for label_i, label in (*enumerate(Label.instances), (not_labelled, None)):
                imgui.table_next_column()
                imgui.begin_child(f"###game_kanban_{label_i}", height=-padding)
                draw_list = imgui.get_window_draw_list()
                wrap = cells_per_column
                imgui.begin_group()
                for id in tab_games_ids:
                    game = globals.games[id]
                    if label_i == not_labelled:
                        if game.labels:
                            continue
                    elif label not in game.labels:
                        continue
                    self.draw_game_cell(game, False, draw_list, cell_width, False, img_height, cell_config)
                    wrap -= 1
                    if wrap:
                        imgui.same_line()
                    else:
                        imgui.end_group()
                        wrap = cells_per_column
                        imgui.begin_group()
                imgui.end_group()
                imgui.end_child()

            imgui.end_table()
        imgui.pop_style_var()

    def draw_bottombar(self):
        new_display_mode = None

        for display_mode in DisplayMode:
            if globals.settings.display_mode is display_mode:
                imgui.push_style_color(imgui.COLOR_BUTTON, *imgui.style.colors[imgui.COLOR_BUTTON_HOVERED])
            if imgui.button(getattr(icons, display_mode.icon)):
                new_display_mode = display_mode
                self.switched_display_mode = True
            if globals.settings.display_mode is display_mode:
                imgui.pop_style_color()
            imgui.same_line()

        if new_display_mode is not None:
            globals.settings.display_mode = new_display_mode
            async_thread.run(db.update_settings("display_mode"))

        if self.add_box_valid:
            imgui.set_next_item_width(-(imgui.calc_text_size("Add!").x + 2 * imgui.style.frame_padding.x) - imgui.style.item_spacing.x)
        else:
            imgui.set_next_item_width(-imgui.FLOAT_MIN)
        any_active_old = imgui.is_any_item_active()
        any_active = False
        def setter_extra(_=None):
            self.add_box_valid = len(utils.extract_thread_matches(self.add_box_text)) > 0
            self.recalculate_ids = True
        if not globals.popup_stack and not any_active_old and (self.input_chars or any(imgui.io.keys_down)):
            if imgui.is_key_pressed(glfw.KEY_BACKSPACE):
                self.add_box_text = self.add_box_text[:-1]
                setter_extra()
            if imgui.is_key_down(glfw.KEY_LEFT_CONTROL) and imgui.is_key_pressed(glfw.KEY_A):
                tab_games_ids = self.show_games_ids[self.current_tab]
                selected = not any(globals.games[id].selected for id in tab_games_ids)
                for id in tab_games_ids:
                    globals.games[id].selected = selected
            if self.input_chars:
                self.repeat_chars = True
                imgui.set_keyboard_focus_here()
            any_active = True
        activated, value = imgui.input_text_with_hint(
            "###bottombar",
            "Type to filter the list, press enter to add a game (link/search)",
            self.add_box_text,
            flags=imgui.INPUT_TEXT_ENTER_RETURNS_TRUE
        )
        changed = value != self.add_box_text
        activated = bool(activated and value)
        any_active = any_active or imgui.is_any_item_active()
        if any_active_old != any_active and imgui.is_key_pressed(glfw.KEY_ESCAPE):
            # Changed active state, and escape is pressed, so clear textbox
            value = ""
            changed = True
            for game in globals.games.values():
                game.selected = False
        if changed:
            self.add_box_text = value
            setter_extra()
        if imgui.begin_popup_context_item("###bottombar_context"):
            # Right click = more options context menu
            utils.text_context(self, "add_box_text", setter_extra, no_icons=True)
            imgui.separator()
            if imgui.selectable(f"{icons.information_outline} More info", False)[0]:
                utils.push_popup(
                    msgbox.msgbox, "About the bottom bar",
                    "This is the filter/add bar. By typing inside it you can search your game list.\n"
                    "Pressing enter will search F95zone for a matching thread and ask if you wish to\n"
                    "add it to your list.\n"
                    "\n"
                    "When you instead paste a link to a F95zone thread, the 'Add!' button will show\n"
                    "up, allowing you to add that thread to your list. When a link is detected you\n"
                    "can also press enter on your keyboard to trigger the 'Add!' button.",
                    MsgBox.info
                )
            imgui.end_popup()
        if self.add_box_valid:
            imgui.same_line()
            if imgui.button("Add!") or activated:
                async_thread.run(callbacks.add_games(*utils.extract_thread_matches(self.add_box_text)))
                self.add_box_text = ""
                self.add_box_valid = False
                self.recalculate_ids = True
        elif activated:
            api.open_search_popup(self.add_box_text)
            self.add_box_text = ""
            self.add_box_valid = False
            self.recalculate_ids = True

    def draw_sidebar(self):
        set = globals.settings
        right_width = self.scaled(90)
        frame_height = imgui.get_frame_height()
        checkbox_offset = right_width - frame_height

        def draw_settings_section(name: str, collapsible=True):
            if collapsible:
                header = imgui.collapsing_header(name)[0]
            else:
                header = True
            opened = header and imgui.begin_table(f"###settings_{name}", column=2, flags=imgui.TABLE_NO_CLIP)
            if opened:
                imgui.table_setup_column("", imgui.TABLE_COLUMN_WIDTH_STRETCH)
                imgui.table_setup_column("", imgui.TABLE_COLUMN_WIDTH_FIXED)
                imgui.table_next_row()
                imgui.table_set_column_index(1)  # Right
                imgui.dummy(right_width, 1)
                imgui.push_item_width(right_width)
            return opened

        def draw_settings_label(label: str, tooltip: str = None):
            imgui.table_next_row()
            imgui.table_next_column()
            imgui.text(label)
            if tooltip:
                imgui.same_line()
                self.draw_hover_text(tooltip)
            imgui.table_next_column()

        def draw_settings_checkbox(setting: str):
            imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
            changed, value = imgui.checkbox(f"###{setting}", getattr(set, setting))
            if changed:
                setattr(set, setting, value)
                async_thread.run(db.update_settings(setting))
            return changed

        def draw_settings_color(setting: str):
            imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
            changed, value = imgui.color_edit3(f"###{setting}", *getattr(set, setting)[:3], flags=imgui.COLOR_EDIT_NO_INPUTS)
            if changed:
                setattr(set, setting, (*value, 1.0))
                self.refresh_styles()
                async_thread.run(db.update_settings(setting))
            return changed

        width = imgui.get_content_region_available_width()
        height = self.scaled(100)
        if utils.is_refreshing():
            # Refresh progress bar
            ratio = globals.refresh_progress / globals.refresh_total
            self.refresh_ratio_smooth += (ratio - self.refresh_ratio_smooth) * imgui.io.delta_time * 8
            imgui.progress_bar(self.refresh_ratio_smooth, (width, height))
            draw_list = imgui.get_window_draw_list()
            screen_pos = imgui.get_cursor_screen_pos()
            col = imgui.get_color_u32_rgba(1, 1, 1, 1)
            if imgui.is_item_clicked():
                # Click = cancel
                globals.refresh_task.cancel()
            if imgui.is_item_hovered():
                text = "Click to cancel!"
                text_size = imgui.calc_text_size(text)
                text_x = screen_pos.x + (width - text_size.x) / 2
                text_y = screen_pos.y - text_size.y - 3 * imgui.style.item_spacing.y
                draw_list.add_text(text_x, text_y, col, text)
            text = f"{ratio:.0%}"
            text_size = imgui.calc_text_size(text)
            text_x = screen_pos.x + (width - text_size.x) / 2
            text_y = screen_pos.y - (height + text_size.y) / 2 - imgui.style.item_spacing.y
            draw_list.add_text(text_x, text_y, col, text)
        elif self.hovered_game:
            # Hover = show image
            game = self.hovered_game
            if game.image.missing:
                imgui.button("Image missing!", width=width, height=height)
            elif game.image.invalid:
                imgui.button("Invalid image!", width=width, height=height)
            else:
                crop = game.image.crop_to_ratio(width / height, fit=globals.settings.fit_images)
                game.image.render(width, height, *crop, rounding=self.scaled(globals.settings.style_corner_radius))
        else:
            # Normal button
            if imgui.button("Refresh!", width=width, height=height):
                utils.start_refresh_task(api.refresh())
            elif imgui.is_item_hovered():
                draw_list = imgui.get_window_draw_list()
                screen_pos = imgui.get_cursor_screen_pos()
                col = imgui.get_color_u32_rgba(1, 1, 1, 1)
                text = str(f"Last refresh: {set.last_successful_refresh.display or 'Never'}")
                text_size = imgui.calc_text_size(text)
                text_x = screen_pos.x + (width - text_size.x) / 2
                text_y = screen_pos.y - text_size.y - 3 * imgui.style.item_spacing.y
                draw_list.add_text(text_x, text_y, col, text)
            if imgui.begin_popup_context_item("###refresh_context"):
                # Right click = more options context menu
                if imgui.selectable(f"{icons.bell_badge_outline} Check notifs", False)[0]:
                    utils.start_refresh_task(api.check_notifs(standalone=True))
                if imgui.selectable(f"{icons.reload_alert} Full Refresh", False)[0]:
                    utils.start_refresh_task(api.refresh(full=True))
                if not globals.settings.refresh_completed_games or not globals.settings.refresh_archived_games:
                    imgui.separator()
                    if not globals.settings.refresh_archived_games:
                        if imgui.selectable(f"{icons.reload_alert} Full Refresh (incl. archived)", False)[0]:
                            utils.start_refresh_task(api.refresh(full=True, force_archived=True))
                    if not globals.settings.refresh_completed_games:
                        if imgui.selectable(f"{icons.reload_alert} Full Refresh (incl. completed)", False)[0]:
                            utils.start_refresh_task(api.refresh(full=True, force_completed=True))
                    if not globals.settings.refresh_completed_games and not globals.settings.refresh_archived_games:
                        if imgui.selectable(f"{icons.reload_alert} Full Refresh (incl. everything)", False)[0]:
                            utils.start_refresh_task(api.refresh(full=True, force_archived=True, force_completed=True))
                imgui.separator()
                if imgui.selectable(f"{icons.information_outline} More info", False)[0]:
                    utils.push_popup(
                        msgbox.msgbox, "About refreshing",
                        "Refreshing is the process by which F95Checker goes through your games and checks\n"
                        "if they have received updates, aswell as syncing other game info.\n"
                        "To keep it fast and smooth while avoiding excessive stress on F95zone servers, this\n"
                        "is done using a dedicated F95Checker Cache API.\n"
                        "\n"
                        "This Cache API gets data from F95zone, parses the relevant details, then saves them for\n"
                        "up to 7 days. To make sure you don't fall behind, it also monitors the F95zone Latest\n"
                        "Updates to invalidate cache when games are updated / some details change. However,\n"
                        "not all details are tracked by Latest Updates, so games are still periodically checked.\n"
                        "There's a bit more complexity to it, but that's the gist of it. Check the OP / README for\n"
                        "a more detailed explanation and all the caveats and behaviors.\n"
                        "\n"
                        "All this data can become quite large if you have lots of games (~2MiB for 100 games) so\n"
                        "fetching everything at each refresh would be quite expensive. Instead F95Checker will\n"
                        "ask the Cache API when each game last changed any of its details (which will also update\n"
                        "the cache if needed) 10 games at a time, then fetch the full game details only for those\n"
                        "that have changed since the last refresh.\n"
                        "You can force full rechecks to fetch all cached game data again, either for single games\n"
                        "or for the whole list, with the right click menu on the game and on the refresh button,\n"
                        "but this usually should not be necessary.",
                        MsgBox.info
                    )
                imgui.end_popup()

        imgui.begin_child("Settings")

        if draw_settings_section("Filter", collapsible=False):
            draw_settings_label(f"Total games count: {len(globals.games)}")
            imgui.text("")
            imgui.spacing()

            if self.selected_games_count:
                draw_settings_label(f"Selected games count: {self.selected_games_count}")
                imgui.text("")
                imgui.spacing()

            if self.filtering:
                if Tab.instances:
                    if globals.settings.filter_all_tabs:
                        draw_settings_label(f"Total filtered count: {len(self.show_games_ids.get(None, ()))}")
                    else:
                        draw_settings_label(f"Total filtered count: {sum(len(ids) for ids in self.show_games_ids.values())}")
                else:
                    draw_settings_label(f"Filtered games count: {len(self.show_games_ids.get(None, ()))}")
                imgui.text("")
                imgui.spacing()

            draw_settings_label("Add filter:")
            changed, value = imgui.combo("###add_filter", 0, FilterMode._member_names_)
            if changed and value > 0:
                flt = Filter(FilterMode[FilterMode._member_names_[value]])
                match flt.mode.value:
                    case FilterMode.Exe_State.value:
                        flt.match = ExeState[ExeState._member_names_[0]]
                    case FilterMode.Finished.value:
                        flt.match = True
                    case FilterMode.Installed.value:
                        flt.match = True
                    case FilterMode.Label.value:
                        if Label.instances:
                            flt.match = Label.instances[0]
                    case FilterMode.Rating.value:
                        flt.match = 0
                    case FilterMode.Score.value:
                        flt.match = 0.0
                    case FilterMode.Status.value:
                        flt.match = Status[Status._member_names_[0]]
                    case FilterMode.Tag.value:
                        flt.match = Tag[Tag._member_names_[0]]
                    case FilterMode.Type.value:
                        flt.match = Type[Type._member_names_[0]]
                self.filters.append(flt)

            text_width = imgui.calc_text_size("Invrt ").x
            buttons_offset = right_width - (2 * frame_height + text_width + imgui.style.item_spacing.x)
            for flt in self.filters:
                imgui.text("")
                draw_settings_label(f"Filter by {flt.mode.name}:")
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + buttons_offset)
                if imgui.button((icons.invert_colors if flt.invert else icons.invert_colors_off) + "Invrt", width=frame_height + text_width):
                    flt.invert = not flt.invert
                    self.recalculate_ids = True
                imgui.same_line()
                if imgui.button(icons.trash_can_outline, width=frame_height):
                    self.filters.remove(flt)

                match flt.mode.value:
                    case FilterMode.Exe_State.value:
                        draw_settings_label("Executable state:")
                        changed, value = imgui.combo(f"###filter_{flt.id}_value", flt.match._index_, ExeState._member_names_)
                        if changed:
                            flt.match = ExeState[ExeState._member_names_[value]]
                            self.recalculate_ids = True
                    case FilterMode.Finished.value:
                        draw_settings_label("Include outdated:")
                        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                        changed, value = imgui.checkbox(f"###filter_{flt.id}_value", flt.match)
                        if changed:
                            flt.match = value
                            self.recalculate_ids = True
                    case FilterMode.Installed.value:
                        draw_settings_label("Include outdated:")
                        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                        changed, value = imgui.checkbox(f"###filter_{flt.id}_value", flt.match)
                        if changed:
                            flt.match = value
                            self.recalculate_ids = True
                    case FilterMode.Label.value:
                        if Label.instances:
                            if flt.match is None:
                                flt.match = Label.instances[0]
                            draw_settings_label("Label value:")
                            if imgui.begin_combo(f"###filter_{flt.id}_value", flt.match.name):
                                for label in Label.instances:
                                    selected = label is flt.match
                                    pos = imgui.get_cursor_pos()
                                    if imgui.selectable(f"###filter_{flt.id}_value_{label.id}", selected)[0]:
                                        flt.match = label
                                        self.recalculate_ids = True
                                    if selected:
                                        imgui.set_item_default_focus()
                                    imgui.set_cursor_pos(pos)
                                    self.draw_label_widget(label)
                                imgui.end_combo()
                        else:
                            draw_settings_label("Make some labels first!")
                            imgui.text("")
                            imgui.spacing()
                    case FilterMode.Rating.value:
                        draw_settings_label("Rating value:")
                        changed, value = ratingwidget.ratingwidget(f"filter_{flt.id}_value", flt.match)
                        if changed:
                            flt.match = value
                            self.recalculate_ids = True
                        imgui.spacing()
                    case FilterMode.Score.value:
                        draw_settings_label("Score value:")
                        changed, value = imgui.drag_float(f"###filter_{flt.id}_value", flt.match, change_speed=0.01, min_value=0, max_value=5, format="%.1f/5")
                        if changed:
                            flt.match = value
                            self.recalculate_ids = True
                    case FilterMode.Status.value:
                        draw_settings_label("Status value:")
                        if imgui.begin_combo(f"###filter_{flt.id}_value", flt.match.name):
                            for status in Status:
                                selected = status is flt.match
                                pos = imgui.get_cursor_pos()
                                if imgui.selectable(f"###filter_{flt.id}_value_{status.value}", selected)[0]:
                                    flt.match = status
                                    self.recalculate_ids = True
                                if selected:
                                    imgui.set_item_default_focus()
                                imgui.set_cursor_pos(pos)
                                self.draw_status_widget(status)
                                imgui.same_line()
                                imgui.text(status.name)
                            imgui.end_combo()
                    case FilterMode.Tag.value:
                        draw_settings_label("Tag value:")
                        if imgui.begin_combo(f"###filter_{flt.id}_value", flt.match.text):
                            for tag in Tag:
                                selected = tag is flt.match
                                pos = imgui.get_cursor_pos()
                                if imgui.selectable(f"###filter_{flt.id}_value_{tag.value}", selected)[0]:
                                    flt.match = tag
                                    self.recalculate_ids = True
                                if selected:
                                    imgui.set_item_default_focus()
                                imgui.set_cursor_pos(pos)
                                self.draw_tag_widget(tag, quick_filter=False, change_highlight=False)
                            imgui.end_combo()
                    case FilterMode.Type.value:
                        draw_settings_label("Type value:")
                        if imgui.begin_combo(f"###filter_{flt.id}_value", flt.match.name):
                            category = None
                            for type in Type:
                                if category is not type.category:
                                    category = type.category
                                    imgui.text(category.name)
                                selected = type is flt.match
                                pos = imgui.get_cursor_pos()
                                if imgui.selectable(f"###filter_{flt.id}_value_{type.value}", selected)[0]:
                                    flt.match = type
                                    self.recalculate_ids = True
                                if selected:
                                    imgui.set_item_default_focus()
                                imgui.set_cursor_pos(pos)
                                self.draw_type_widget(type)
                            imgui.end_combo()

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Browser"):
            draw_settings_label(
                "Browser:",
                "All the options you select here ONLY affect how F95Checker opens links for you, it DOES NOT affect how this tool "
                "operates internally. F95Checker DOES NOT interact with your browsers in any meaningful way, it uses a separate "
                "session just for itself."
            )
            changed, value = imgui.combo("###browser", set.browser.index, Browser.avail_list)
            if changed:
                set.browser = Browser.get(Browser.avail_list[value])
                async_thread.run(db.update_settings("browser"))

            if set.browser.custom:
                draw_settings_label("Custom browser:")
                if imgui.button("Configure", width=right_width):
                    def popup_content():
                        imgui.text("Executable: ")
                        imgui.same_line()
                        pos = imgui.get_cursor_pos_x()
                        changed, value = imgui.input_text("###browser_custom_executable", set.browser_custom_executable)
                        setter_extra = lambda _=None: async_thread.run(db.update_settings("browser_custom_executable"))
                        if changed:
                            set.browser_custom_executable = value
                            setter_extra()
                        if imgui.begin_popup_context_item("###browser_custom_executable_context"):
                            utils.text_context(set, "browser_custom_executable", setter_extra, no_icons=True)
                            imgui.end_popup()
                        imgui.same_line()
                        clicked = imgui.button(icons.folder_open_outline)
                        imgui.same_line(spacing=0)
                        args_width = imgui.get_cursor_pos_x() - pos
                        imgui.dummy(0, 0)
                        if clicked:
                            def callback(selected: str):
                                if selected:
                                    set.browser_custom_executable = selected
                                    async_thread.run(db.update_settings("browser_custom_executable"))
                            utils.push_popup(filepicker.FilePicker(
                                title="Select or drop browser executable",
                                start_dir=set.browser_custom_executable,
                                callback=callback
                            ).tick)
                        imgui.text("Arguments: ")
                        imgui.same_line()
                        imgui.set_cursor_pos_x(pos)
                        imgui.set_next_item_width(args_width)
                        changed, value = imgui.input_text("###browser_custom_arguments", set.browser_custom_arguments)
                        setter_extra = lambda _=None: async_thread.run(db.update_settings("browser_custom_arguments"))
                        if changed:
                            set.browser_custom_arguments = value
                            setter_extra()
                        if imgui.begin_popup_context_item("###browser_custom_arguments_context"):
                            utils.text_context(set, "browser_custom_arguments", setter_extra, no_icons=True)
                            imgui.end_popup()
                    utils.push_popup(
                        utils.popup, "Configure custom browser",
                        popup_content,
                        buttons=True,
                        closable=True,
                        outside=False
                    )
            else:
                draw_settings_label("Use private mode:")
                draw_settings_checkbox("browser_private")

            draw_settings_label(
                "Download pages:",
                "With this enabled links will first be downloaded by F95Checker and then opened as simple HTML files in your "
                "browser. This might be useful if you use private mode because the page will load as if you were logged in, "
                "allowing you to see links and spoiler content without actually logging in."
            )
            draw_settings_checkbox("browser_html")

            draw_settings_label(
                "Software Webview:",
                "Forces software mode for integrated browser webview, disables GPU acceleration. Enable if you have issues with "
                "the integrated browser not rendering correctly."
            )
            draw_settings_checkbox("software_webview")

            draw_settings_label("Copy game links as BBcode:")
            draw_settings_checkbox("copy_urls_as_bbcode")

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Extension"):
            draw_settings_label(
                "RPC enabled:",
                f"The RPC allows other programs on your pc to interact with F95Checker via the API on {globals.rpc_url}. "
                "Essentially this is what makes the web browser extension work. Disable this if you are having issues with the RPC, "
                "but do note that doing so will prevent the extension from working at all."
            )
            if draw_settings_checkbox("rpc_enabled"):
                if set.rpc_enabled:
                    rpc_thread.start()
                else:
                    rpc_thread.stop()

            draw_settings_label("Install extension:")
            cant_install_extension = set.browser.integrated or not set.rpc_enabled
            def cant_install_extension_tooltip():
                if imgui.is_item_hovered():
                    imgui.begin_tooltip()
                    imgui.push_text_wrap_pos(min(imgui.get_font_size() * 35, imgui.io.display_size.x))
                    if set.browser.integrated:
                        imgui.text("You have selected the Integrated browser, this already includes the extension!")
                    elif not set.rpc_enabled:
                        imgui.text("RPC must be enabled for the browser extension to work!")
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
            if cant_install_extension:
                imgui.push_disabled()
            if imgui.button(icons.google_chrome, width=(right_width - imgui.style.item_spacing.x) / 2):
                buttons={
                    f"{icons.check} Ok": lambda: async_thread.run(callbacks.default_open(globals.self_path / "browser")),
                    f"{icons.cancel} Cancel": None
                }
                utils.push_popup(
                    msgbox.msgbox, "Chrome extension",
                    "Unfortunately, the F95Checker extension is banned from the Chrome Webstore.\n"
                    "Therefore, you must install it manually via developer mode:\n"
                    " - Open your Chromium-based browser\n"
                    " - Navigate to 'chrome://extensions/'\n"
                    " - Enable the 'Developer mode' toggle\n"
                    " - Refresh the page\n"
                    " - Click Ok below and drag 'chrome.zip' into your browser window\n",
                    MsgBox.info,
                    buttons
                )
            if cant_install_extension:
                imgui.pop_disabled()
                cant_install_extension_tooltip()
                imgui.push_disabled()
            imgui.same_line()
            if imgui.button(icons.firefox, width=(right_width - imgui.style.item_spacing.x) / 2):
                if globals.release:
                    callbacks.open_webpage("https://addons.mozilla.org/firefox/addon/f95checker-browser-addon/")
                else:
                    callbacks.open_webpage("https://addons.mozilla.org/firefox/addon/f95checker-beta-browser-addon/")
            if cant_install_extension:
                imgui.pop_disabled()
                cant_install_extension_tooltip()

            draw_settings_label(
                "Icon glow:",
                "Icons in some locations will cast colored shadow to improve visibility."
            )
            draw_settings_checkbox("ext_icon_glow")

            draw_settings_label(
                "Highlight tags:",
                "To change tag preferences go to 'Interface' > 'Tags to highlight'"
            )
            draw_settings_checkbox("ext_highlight_tags")

            draw_settings_label(
                "Add in the background:",
                "Don't open F95Checker window after adding a game."
            )
            draw_settings_checkbox("ext_background_add")

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Images"):
            draw_settings_label(
                "Cell ratio:",
                "The aspect ratio to use for images in grid and kanban view. This is width:height, AKA how many times wider the image "
                "is compared to its height. Default is 3:1."
            )
            changed, value = imgui.drag_float("###cell_image_ratio", set.cell_image_ratio, change_speed=0.02, min_value=0.5, max_value=5, format="%.1f:1")
            set.cell_image_ratio = min(max(value, 0.5), 5)
            if changed:
                async_thread.run(db.update_settings("cell_image_ratio"))

            draw_settings_label(
                "Fit images:",
                "Fit images instead of cropping. When cropping the images fill all the space they have available, cutting "
                "off the sides a bit. When fitting the images you see the whole image but it has some empty space at the sides."
            )
            draw_settings_checkbox("fit_images")

            draw_settings_label(
                "Zoom on hover:",
                "Allow zooming header images inside info popups.\n"
                "Tip: hold shift and scroll while hovering the image to change the zoom amount, or hold shift and alt while "
                "scrolling to change the zoom area."
            )
            draw_settings_checkbox("zoom_enabled")

            if not set.zoom_enabled:
                imgui.push_disabled()

            draw_settings_label(
                "Zoom area:",
                "The size of the zoom popup compared to the main window size (uses the shorter of the two window dimensions). "
                "Default 50%."
            )
            changed, value = imgui.drag_int("###zoom_area", set.zoom_area, change_speed=0.2, min_value=1, max_value=500, format="%d%%")
            set.zoom_area = min(max(value, 1), 500)
            if changed:
                async_thread.run(db.update_settings("zoom_area"))

            draw_settings_label(
                "Zoom times:",
                "How many times to magnify the zoomed area of the image. Default 4x."
            )
            changed, value = imgui.drag_float("###zoom_times", set.zoom_times, change_speed=0.02, min_value=1, max_value=20, format="%.1fx")
            set.zoom_times = min(max(value, 1), 20)
            if changed:
                async_thread.run(db.update_settings("zoom_times"))

            if not set.zoom_enabled:
                imgui.pop_disabled()

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Interface"):
            draw_settings_label("Scaling:")
            changed, value = imgui.drag_float("###interface_scaling", set.interface_scaling, change_speed=imgui.FLOAT_MIN, min_value=0.5, max_value=4, format="%.2fx")
            if imgui.is_item_deactivated():  # Only change when editing by text input and accepting the edit
                set.interface_scaling = min(max(value, 0.5), 4)
                async_thread.run(db.update_settings("interface_scaling"))

            draw_settings_label(
                "BG on close:",
                "When closing the window F95Checker will instead switch to background mode. Quit the app via the tray icon."
            )
            draw_settings_checkbox("background_on_close")

            draw_settings_label(
                "Grid columns:",
                "How many games will show in each row in grid view. It is a maximum value because when there is insufficient "
                "space to show all these columns, the number will be internally reduced to render each grid cell properly."
            )
            changed, value = imgui.drag_int("###grid_columns", set.grid_columns, change_speed=0.05, min_value=1, max_value=10)
            set.grid_columns = min(max(value, 1), 10)
            if changed:
                async_thread.run(db.update_settings("grid_columns"))

            draw_settings_label("Smooth scrolling:")
            draw_settings_checkbox("scroll_smooth")

            if not set.scroll_smooth:
                imgui.push_disabled()

            draw_settings_label(
                "Smoothness:",
                "How fast or slow the smooth scrolling animation is. Default is 8."
            )
            changed, value = imgui.drag_float("###scroll_smooth_speed", set.scroll_smooth_speed, change_speed=0.25, min_value=0.1, max_value=50)
            set.scroll_smooth_speed = min(max(value, 0.1), 50)
            if changed:
                async_thread.run(db.update_settings("scroll_smooth_speed"))

            if not set.scroll_smooth:
                imgui.pop_disabled()

            draw_settings_label(
                "Scroll mult:",
                "Multiplier for how much a single scroll event should actually scroll. Default is 1."
            )
            changed, value = imgui.drag_float("###scroll_amount", set.scroll_amount, change_speed=0.05, min_value=0.1, max_value=10, format="%.2fx")
            set.scroll_amount = min(max(value, 0.1), 10)
            if changed:
                async_thread.run(db.update_settings("scroll_amount"))

            draw_settings_label(
                "Quick filters:",
                "When this is enabled you can click on some widgets to quickly add filters for them. This includes: type, tag and "
                "label widgets, and status and update icons."
            )
            draw_settings_checkbox("quick_filters")

            draw_settings_label("Compact timeline:")
            draw_settings_checkbox("compact_timeline")

            draw_settings_label("Highlight tags:")
            draw_settings_checkbox("highlight_tags")

            draw_settings_label("Tags to highlight:")
            if imgui.button("Select", width=right_width):
                utils.push_popup(self.draw_tag_highlights_popup)

            draw_settings_label(
                "Time format:",
                "The format expression to use for full timestamps. Uses the strftime specification. Default is '%d/%m/%Y %H:%M'."
            )
            changed, value = imgui.input_text("###timestamp_format", set.timestamp_format)
            def setter_extra(_=None):
                async_thread.run(db.update_settings("timestamp_format"))
                for timestamp in Timestamp.instances:
                    timestamp.update()
            if changed:
                set.timestamp_format = value
                setter_extra()
            if imgui.begin_popup_context_item("###timestamp_format_context"):
                utils.text_context(set, "timestamp_format", setter_extra)
                imgui.end_popup()

            now = dt.datetime.now()
            try:
                timestamp = now.strftime(set.timestamp_format)
            except Exception:
                timestamp = "Bad format!"
            draw_settings_label(f"Time: {timestamp}")
            imgui.text("")
            imgui.spacing()

            draw_settings_label(
                "Date format:",
                "The format expression to use for short datestamps. Uses the strftime specification. Default is '%b %d, %Y'."
            )
            changed, value = imgui.input_text("###datestamp_format", set.datestamp_format)
            def setter_extra(_=None):
                async_thread.run(db.update_settings("datestamp_format"))
                for datestamp in Datestamp.instances:
                    datestamp.update()
            if changed:
                set.datestamp_format = value
                setter_extra()
            if imgui.begin_popup_context_item("###datestamp_format_context"):
                utils.text_context(set, "datestamp_format", setter_extra)
                imgui.end_popup()

            try:
                datestamp = now.strftime(set.datestamp_format)
            except Exception:
                datestamp = "Bad format!"
            draw_settings_label(f"Date: {datestamp}")
            imgui.text("")
            imgui.spacing()

            draw_settings_label(
                "Vsync ratio:",
                "Vsync means that the framerate should be synced to the one your monitor uses. The ratio modifies this behavior. "
                "A ratio of 1:0 means uncapped framerate, while all other numbers indicate the ratio between screen and app FPS. "
                "For example a ratio of 1:2 means the app refreshes every 2nd monitor frame, resulting in half the framerate."
            )
            changed, value = imgui.drag_int("###vsync_ratio", set.vsync_ratio, change_speed=0.05, min_value=0, max_value=10, format="1:%d")
            set.vsync_ratio = min(max(value, 0), 10)
            if changed:
                glfw.swap_interval(set.vsync_ratio)
                async_thread.run(db.update_settings("vsync_ratio"))

            draw_settings_label(
                "Render if unfocused:",
                "F95Checker renders its interface using ImGui and OpenGL and this means it has to render the whole interface up "
                "to hundreds of times per second (look at the framerate below). This process is as optimized as possible but it "
                "will inevitably consume some CPU and GPU resources. If you absolutely need the performance you can disable this "
                "option to stop rendering when the checker window is not focused, but keep in mind that it might lead to weird "
                "interactions and behavior."
            )
            draw_settings_checkbox("render_when_unfocused")

            draw_settings_label(f"Current framerate: {round(imgui.io.framerate, 3)}")
            imgui.text("")
            imgui.spacing()

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Labels"):
            buttons_offset = right_width - (3 * frame_height + 2 * imgui.style.item_spacing.x)
            for label in Label.instances:
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.set_next_item_width(imgui.get_content_region_available_width() + buttons_offset + imgui.style.cell_padding.x)
                changed, value = imgui.input_text_with_hint(f"###label_name_{label.id}", "Label name", label.name)
                setter_extra = lambda _=None: async_thread.run(db.update_label(label, "name"))
                if changed:
                    label.name = value
                    setter_extra()
                if imgui.begin_popup_context_item(f"###label_name_{label.id}_context"):
                    utils.text_context(label, "name", setter_extra)
                    imgui.end_popup()
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + buttons_offset)
                changed, value = imgui.color_edit3(f"###label_color_{label.id}", *label.color[:3], flags=imgui.COLOR_EDIT_NO_INPUTS)
                if changed:
                    label.color = (*value, 1.0)
                    async_thread.run(db.update_label(label, "color"))
                imgui.same_line()
                if imgui.button(icons.filter_plus_outline, width=frame_height):
                    flt = Filter(FilterMode.Label)
                    flt.match = label
                    self.filters.append(flt)
                imgui.same_line()
                if imgui.button(icons.trash_can_outline, width=frame_height):
                    async_thread.run(db.delete_label(label))

            draw_settings_label("New label:")
            if imgui.button("Add", width=right_width):
                async_thread.run(db.create_label())

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Manage"):
            imgui.table_next_row()
            imgui.table_next_column()
            pos = imgui.get_cursor_pos()
            imgui.table_next_column()
            imgui.set_cursor_pos(pos)
            imgui.begin_group()
            if imgui.tree_node("Import", flags=imgui.TREE_NODE_SPAN_AVAILABLE_WIDTH):
                offset = imgui.get_cursor_pos_x() - pos.x
                if imgui.button("Thread links", width=-offset):
                    thread_links = builtins.type("_", (), dict(_=""))()
                    def popup_content():
                        nonlocal thread_links
                        imgui.text(
                            "Any kind of F95zone thread link, preferably 1 per line. Will be parsed and cleaned,\n"
                            "so don't worry about tidiness and paste like it's anarchy!"
                        )
                        _, thread_links._ = imgui.input_text_multiline(
                            "###import_links",
                            value=thread_links._,
                            width=min(self.scaled(600), imgui.io.display_size.x * 0.6),
                            height=imgui.io.display_size.y * 0.6
                        )
                        if imgui.begin_popup_context_item("###import_links_context"):
                            utils.text_context(thread_links, "_", no_icons=True)
                            imgui.end_popup()
                    buttons={
                        f"{icons.check} Import": lambda: async_thread.run(callbacks.add_games(*utils.extract_thread_matches(thread_links._))),
                        f"{icons.cancel} Cancel": None
                    }
                    utils.push_popup(
                        utils.popup, "Import thread links",
                        popup_content,
                        buttons,
                        closable=True,
                        outside=False
                    )
                if imgui.button("F95 bookmarks", width=-offset):
                    utils.start_refresh_task(api.import_f95_bookmarks(), reset_bg_timers=False)
                if imgui.button("F95 watched threads", width=-offset):
                    utils.start_refresh_task(api.import_f95_watched_threads(), reset_bg_timers=False)
                if imgui.button("Browser bookmarks", width=-offset):
                    def callback(selected):
                        if selected:
                            async_thread.run(api.import_browser_bookmarks(selected))
                    buttons={
                        f"{icons.check} Ok": lambda: utils.push_popup(filepicker.FilePicker(
                                                         title="Select or drop bookmark file",
                                                         callback=callback
                                                     ).tick),
                        f"{icons.cancel} Cancel": None
                    }
                    utils.push_popup(
                        msgbox.msgbox, "Bookmark file",
                        "F95Checker can import your browser bookmarks using an exported bookmark HTML.\n"
                        "Exporting such a file may vary between browsers, but generally speaking you need to:\n"
                        " - Open your browser's bookmark manager\n"
                        " - Find an import / export section, menu or dropdown\n"
                        " - Click export as HTML\n"
                        " - Save the file in some place you can find easily\n"
                        "\n"
                        "Once you have done this click Ok and select this file.",
                        MsgBox.info,
                        buttons
                    )
                file_hover = imgui.is_item_hovered()
                if imgui.button("URL Shortcut file", width=-offset):
                    def callback(selected):
                        if selected:
                            async_thread.run(api.import_url_shortcut(selected))
                    utils.push_popup(filepicker.FilePicker(
                        title="Select or drop shortcut file",
                        callback=callback
                    ).tick),
                file_hover = file_hover or imgui.is_item_hovered()
                if file_hover:
                    self.draw_hover_text("You can also drag and drop .html and .url files into the window for this!", text=None, force=True)
                imgui.tree_pop()
            if imgui.tree_node("Export", flags=imgui.TREE_NODE_SPAN_AVAILABLE_WIDTH):
                offset = imgui.get_cursor_pos_x() - pos.x
                if imgui.button("Thread links", width=-offset):
                    thread_links = builtins.type("_", (), dict(_="\n".join(game.url for game in globals.games.values())))()
                    def popup_content():
                        imgui.input_text_multiline(
                            "###export_links",
                            value=thread_links._,
                            width=min(self.scaled(600), imgui.io.display_size.x * 0.6),
                            height=imgui.io.display_size.y * 0.6,
                            flags=imgui.INPUT_TEXT_READ_ONLY
                        )
                        if imgui.begin_popup_context_item("###export_links_context"):
                            utils.text_context(thread_links, "_", editable=False)
                            imgui.end_popup()
                    utils.push_popup(
                        utils.popup, "Export thread links",
                        popup_content,
                        buttons=True,
                        closable=True,
                        outside=False
                    )
                if imgui.button("Unknown tags", width=-offset):
                    unknown_tags = builtins.type("_", (), dict(_="\n".join(builtins.set(itertools.chain.from_iterable(game.unknown_tags for game in globals.games.values())))))()
                    def popup_content():
                        imgui.input_text_multiline(
                            "###export_unknown_tags",
                            value=unknown_tags._,
                            width=min(self.scaled(600), imgui.io.display_size.x * 0.6),
                            height=imgui.io.display_size.y * 0.6,
                            flags=imgui.INPUT_TEXT_READ_ONLY
                        )
                        if imgui.begin_popup_context_item("###export_unknown_tags_context"):
                            utils.text_context(unknown_tags, "_", editable=False)
                            imgui.end_popup()
                    utils.push_popup(
                        utils.popup, "Export unknown tags",
                        popup_content,
                        buttons=True,
                        closable=True,
                        outside=False
                    )
                imgui.tree_pop()
            if imgui.tree_node("Clear", flags=imgui.TREE_NODE_SPAN_AVAILABLE_WIDTH):
                offset = imgui.get_cursor_pos_x() - pos.x
                if imgui.button("All cookies", width=-offset):
                    buttons = {
                        f"{icons.check} Yes": lambda: async_thread.run(db.update_cookies({})),
                        f"{icons.cancel} No": None
                    }
                    utils.push_popup(
                        msgbox.msgbox, "Clear cookies",
                        "Are you sure you want to clear your session cookies?\n"
                        "This will invalidate your login session, but might help\n"
                        "if you are having issues.",
                        MsgBox.warn,
                        buttons
                    )
                if imgui.button("RPDL session", width=-offset):
                    def clear_callback():
                        globals.settings.rpdl_username = ""
                        globals.settings.rpdl_password = ""
                        globals.settings.rpdl_token = ""
                        async_thread.run(db.update_settings("rpdl_username", "rpdl_password", "rpdl_token"))
                    buttons = {
                        f"{icons.check} Yes": clear_callback,
                        f"{icons.cancel} No": None
                    }
                    utils.push_popup(
                        msgbox.msgbox, "Clear RPDL session",
                        "Are you sure you want to clear your RPDL session?\n"
                        "You will need to sign in to RPDL again to use torrents.",
                        MsgBox.warn,
                        buttons
                    )
                imgui.tree_pop()
            imgui.end_group()
            imgui.spacing()

            draw_settings_label(
                "Ask exe on add:",
                "When this is enabled you will be asked to select a game executable right after adding the game to F95Checker."
            )
            draw_settings_checkbox("select_executable_after_add")

            draw_settings_label(
                "Installed on add:",
                "When this is enabled games will be marked as installed by default when first added to F95Checker."
            )
            draw_settings_checkbox("mark_installed_after_add")

            draw_settings_label(
                "Set exe dir:",
                "This setting indicates what folder you keep all your games in (if you're organized). Executables inside this folder are "
                "remembered relatively, this means you can select the executables with this setting on, then move your entire folder, update this "
                "setting, and all the executables are still valid.\n"
                "This setting is OS dependent, it has different values for different operating systems you use F95Checker on.\n\n"
                f"Current value: {set.default_exe_dir.get(globals.os) or 'Unset'}"
            )
            if imgui.button("Choose", width=right_width):
                def select_callback(selected):
                    set.default_exe_dir[globals.os] = selected or ""
                    async_thread.run(db.update_settings("default_exe_dir"))
                    for game in globals.games.values():
                        game.validate_executables()
                utils.push_popup(filepicker.DirPicker(
                    title="Select or drop default exe dir",
                    start_dir=set.default_exe_dir.get(globals.os),
                    callback=select_callback
                ).tick)

            draw_settings_label(
                "Downloads dir:",
                "Where downloads will be saved to. Currently, only F95zone Donor DDL downloads are supported in F95Checker, but this "
                "setting is also used for saving RPDL torrent files.\n"
                "This setting is OS dependent, it has different values for different operating systems you use F95Checker on.\n\n"
                f"Current value: {set.downloads_dir.get(globals.os) or pathlib.Path.home() / 'Downloads'}\n\n"
                "For other download types, you may want to consider a download manager like JDownloader2, and configure it to monitor the "
                "clipboard: then you will be able to copy links and have them automatically download in your external download manager."
            )
            if imgui.button("Choose", width=right_width):
                def select_callback(selected):
                    set.downloads_dir[globals.os] = selected or ""
                    async_thread.run(db.update_settings("downloads_dir"))
                utils.push_popup(filepicker.DirPicker(
                    title="Select or drop downloads dir",
                    start_dir=set.downloads_dir.get(globals.os),
                    callback=select_callback
                ).tick)

            draw_settings_label("Show remove button:")
            draw_settings_checkbox("show_remove_btn")

            draw_settings_label("Confirm when removing:")
            draw_settings_checkbox("confirm_on_remove")

            draw_settings_label(
                "Weighted score:",
                "Use weighted rating algorithm when sorting table by forum score.\n"
                "You can see the final value used by hovering over the score number."
            )
            if draw_settings_checkbox("weighted_score"):
                self.recalculate_ids = True

            draw_settings_label(
                "Custom game:",
                "Add a custom game that is untied from F95zone. Useful for games removed for breaking forum rules, or for adding games "
                "from other platforms. Custom games are not checked for updates and you have to add the core details (name, url, version...) "
                "yourself. You can later convert a custom game to an F95zone game from the info popup."
            )
            if imgui.button("Add", width=right_width):
                game_id = async_thread.wait(db.create_game(custom=True))
                async_thread.wait(db.load_games(game_id))
                game = globals.games[game_id]
                utils.push_popup(self.draw_game_info_popup, game, None)
                if globals.settings.mark_installed_after_add:
                    game.installed = game.version
                if globals.settings.select_executable_after_add:
                    callbacks.add_game_exe(game)

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Proxy"):
            draw_settings_label(
                "Type:",
                "All listed proxy types work with the main F95Checker functionality.\n\n"
                "The integrated browser (also used for login) instead has some limitations due to Qt:\n"
                "- SOCKS4 is not supported at all\n"
                "- SOCKS5 with authentication won't work\n"
                "- HTTP with authentication is not implemented"
            )
            changed, value = imgui.combo("###proxy_type", set.proxy_type._index_, ProxyType._member_names_)
            if changed:
                set.proxy_type = ProxyType[ProxyType._member_names_[value]]
                async_thread.run(db.update_settings("proxy_type"))
                api.make_session()

            if set.proxy_type is ProxyType.Disabled:
                imgui.push_disabled()

            draw_settings_label(
                "Host:",
                "Domain or IP address of proxy server.\n"
                "For example: 127.0.0.1, myproxy.example.com"
            )
            changed, value = imgui.input_text_with_hint("###proxy_host", "Domain/IP", set.proxy_host)
            if changed:
                set.proxy_host = value
                async_thread.run(db.update_settings("proxy_host"))
                api.make_session()

            draw_settings_label("Port:")
            changed, value = imgui.drag_int("###proxy_port", set.proxy_port, change_speed=0.5, min_value=1, max_value=65535)
            set.proxy_port = min(max(value, 1), 65535)
            if changed:
                set.proxy_port = int(value)
                async_thread.run(db.update_settings("proxy_port"))
                api.make_session()

            draw_settings_label("Username:", "Leave empty if proxy does not require authentication")
            changed, value = imgui.input_text("###proxy_username", set.proxy_username)
            if changed:
                set.proxy_username = value
                async_thread.run(db.update_settings("proxy_username"))
                api.make_session()

            draw_settings_label("Password:", "Leave empty if proxy does not require authentication")
            changed, value = imgui.input_text(
                "###proxy_password",
                set.proxy_password,
                flags=imgui.INPUT_TEXT_PASSWORD,
            )
            if changed:
                set.proxy_password = value
                async_thread.run(db.update_settings("proxy_password"))
                api.make_session()

            if set.proxy_type is ProxyType.Disabled:
                imgui.pop_disabled()

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Refresh"):
            draw_settings_label("Check alerts and inbox:")
            draw_settings_checkbox("check_notifs")

            draw_settings_label("Refresh if archived:")
            draw_settings_checkbox("refresh_archived_games")

            draw_settings_label("Refresh if completed:")
            draw_settings_checkbox("refresh_completed_games")

            draw_settings_label(
                "Connections:",
                "Games are checked 10 at a time for updates, and of those only those with new data are fetched for all game "
                "info from the F95Checker Cache API. This setting determines how many of those can be fetched simultaneously. "
                "In most cases 10 should be fine, but lower it if your internet struggles when doing a full refresh."
            )
            changed, value = imgui.drag_int("###max_connections", set.max_connections, change_speed=0.5, min_value=1, max_value=10)
            set.max_connections = min(max(value, 1), 10)
            if changed:
                async_thread.run(db.update_settings("max_connections"))

            draw_settings_label(
                "Timeout:",
                "To check for updates, notifications and other functionality, F95Checker sends web requests (to its dedicated "
                "Cache API, to F95zone itself, and to other third-parties like RPDL.net if you so choose). However this can sometimes "
                "go  wrong. The timeout is the maximum amount of seconds that a request can try to connect for before it fails.\n"
                "A timeout of 10-30 seconds is most typical."
            )
            changed, value = imgui.drag_int("###request_timeout", set.request_timeout, change_speed=0.6, min_value=1, max_value=120, format="%d sec")
            set.request_timeout = min(max(value, 1), 120)
            if changed:
                async_thread.run(db.update_settings("request_timeout"))

            draw_settings_label(
                "Retries:",
                "While refreshing, a lot of web requests are made quite quickly, so some of them might fail. This setting "
                "determines how many times a failed request will be reattempted before failing completely. However these "
                "connection errors are often caused by misconfigured connections and timeout values, so try to tinker with those "
                "instead of the retries value. This setting should only be used if you know your connection is very unreliable.\n"
                "Usually 2 max retries are fine for stable connections."
            )
            changed, value = imgui.drag_int("###max_retries", set.max_retries, change_speed=0.05, min_value=0, max_value=10)
            set.max_retries = min(max(value, 0), 10)
            if changed:
                async_thread.run(db.update_settings("max_retries"))

            draw_settings_label(
                "No semaphore timeout:",
                "If you are having connection issues specifically with 'WinError 121' and 'The semaphore timeout period has expired' "
                "then try to enable this option, it will suppress these errors and retry all connections as if they never happened. "
                "However this type of error is usually caused by hardware or driver issues, or some bad Windows updates. It is recommended "
                "you first try to repair your system with sfc and DISM (Google them) and update your drivers. Use this option as a last resort."
            )
            draw_settings_checkbox("ignore_semaphore_timeouts")

            draw_settings_label(f"Insecure SSL:")
            draw_settings_checkbox("insecure_ssl")

            draw_settings_label(f"Async tasks count: {sum((0 if task.done() else 1) for task in asyncio.all_tasks(loop=async_thread.loop))}")
            imgui.text("")
            imgui.spacing()

            draw_settings_label(
                "BG interval:",
                "When F95Checker is in background mode it automatically refreshes your games periodically. This "
                "controls how often (in minutes) this happens."
            )
            changed, value = imgui.drag_int("###bg_refresh_interval", set.bg_refresh_interval, change_speed=4.0, min_value=30, max_value=1440, format="%d min")
            set.bg_refresh_interval = min(max(value, 30), 1440)
            if changed:
                async_thread.run(db.update_settings("bg_refresh_interval"))

            if not set.check_notifs:
                imgui.push_disabled()

            draw_settings_label(
                "BG notifs intv:",
                "When F95Checker is in background mode it automatically checks your notifications periodically. This "
                "controls how often (in minutes) this happens."
            )
            changed, value = imgui.drag_int("###bg_notifs_interval", set.bg_notifs_interval, change_speed=4.0, min_value=15, max_value=1440, format="%d min")
            set.bg_notifs_interval = min(max(value, 15), 1440)
            if changed:
                async_thread.run(db.update_settings("bg_notifs_interval"))

            if not set.check_notifs:
                imgui.pop_disabled()

            draw_settings_label(f"Last refresh: {set.last_successful_refresh.display or 'Never'}")
            imgui.text("")
            imgui.spacing()

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Startup"):
            draw_settings_label("Refresh at start:")
            draw_settings_checkbox("start_refresh")

            draw_settings_label(
                "Start in BG:",
                "F95Checker will start in background mode, hidden in the system tray."
            )
            draw_settings_checkbox("start_in_background")

            draw_settings_label("Start with system:")
            imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
            changed, value = imgui.checkbox("###start_with_system", globals.start_with_system)
            if changed:
                callbacks.update_start_with_system(value)

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Style"):
            draw_settings_label("Corner radius:")
            changed, value = imgui.drag_int("###style_corner_radius", set.style_corner_radius, change_speed=0.04, min_value=0, max_value=6, format="%d px")
            set.style_corner_radius = min(max(value, 0), 6)
            if changed:
                imgui.style.window_rounding = imgui.style.frame_rounding = imgui.style.tab_rounding = \
                imgui.style.child_rounding = imgui.style.grab_rounding = imgui.style.popup_rounding = \
                imgui.style.scrollbar_rounding = globals.settings.style_corner_radius
                async_thread.run(db.update_settings("style_corner_radius"))

            draw_settings_label("Accent:")
            draw_settings_color("style_accent")

            draw_settings_label("Background:")
            draw_settings_color("style_bg")

            draw_settings_label("Alt background:")
            draw_settings_color("style_alt_bg")

            draw_settings_label("Border:")
            draw_settings_color("style_border")

            draw_settings_label("Text:")
            draw_settings_color("style_text")

            draw_settings_label("Text dim:")
            draw_settings_color("style_text_dim")

            draw_settings_label("Defaults:")
            if imgui.button("Restore", width=right_width):
                set.style_corner_radius = DefaultStyle.corner_radius
                set.style_accent        = colors.hex_to_rgba_0_1(DefaultStyle.accent)
                set.style_alt_bg        = colors.hex_to_rgba_0_1(DefaultStyle.alt_bg)
                set.style_bg            = colors.hex_to_rgba_0_1(DefaultStyle.bg)
                set.style_border        = colors.hex_to_rgba_0_1(DefaultStyle.border)
                set.style_text          = colors.hex_to_rgba_0_1(DefaultStyle.text)
                set.style_text_dim      = colors.hex_to_rgba_0_1(DefaultStyle.text_dim)
                self.refresh_styles()
                async_thread.run(db.update_settings(
                    "style_corner_radius",
                    "style_accent",
                    "style_alt_bg",
                    "style_bg",
                    "style_border",
                    "style_text",
                    "style_text_dim",
                ))

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Tabs"):
            draw_settings_label("Filter all tabs:")
            if draw_settings_checkbox("filter_all_tabs"):
                self.recalculate_ids = True

            draw_settings_label("Hide empty tabs:")
            draw_settings_checkbox("hide_empty_tabs")

            draw_settings_label(
                f"Default {icons.arrow_left_right} New",
                "Change 'Default' tab to 'New'. Only a visual change.\n"
                "Can be useful if you only store new games in default tab."
            )
            draw_settings_checkbox("default_tab_is_new")

            draw_settings_label(
                "Independent views:",
                "Each tab will have its own sorting/column preferences."
            )
            if draw_settings_checkbox("independent_tab_views"):
                self.recalculate_ids = True

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Background", collapsible=False):
            draw_settings_label(
                "BG mode:",
                "When in background mode, F95Checker hides the main window and only keeps the icon in the system tray. The main feature of "
                "background mode is periodic refreshing: your list will be automatically refreshed at regular intervals and you will receive "
                "a desktop notification if some updates / notifications have been found."
            )
            if imgui.button("Switch", width=right_width):
                self.hide()

            imgui.end_table()

        if api.downloads:
            to_remove = []
            for name, download in api.downloads.items():
                if not download:
                    continue
                imgui.spacing()
                imgui.spacing()
                imgui.spacing()
                imgui.text("DDL: " + name)
                errored = download.error or download.progress != download.total

                if download.state == download.State.Downloading:
                    space_after = (
                        1 * (
                            2 * imgui.style.frame_padding.y +
                            imgui.style.frame_border_size +
                            imgui.style.item_spacing.x
                        ) +
                        imgui.calc_text_size(icons.stop).x +
                        imgui.style.frame_border_size
                    )
                elif download.state == download.State.Stopped:
                    if imgui.button(icons.folder_open_outline):
                        extracted_dir = download.extracted if not errored else None
                        async_thread.run(callbacks.default_open(extracted_dir or download.path.parent))
                    imgui.same_line()
                    if not errored:
                        if imgui.button(icons.open_in_app):
                            async_thread.run(callbacks.default_open(download.path))
                        imgui.same_line()
                    space_after = (
                        2 * (
                            2 * imgui.style.frame_padding.y +
                            imgui.style.frame_border_size +
                            imgui.style.item_spacing.x
                        ) +
                        imgui.calc_text_size(icons.cancel + icons.trash_can_outline).x +
                        imgui.style.frame_border_size
                    )
                else:
                    space_after = 0

                ratio = download.progress / (download.total or 1)
                width = imgui.get_content_region_available_width() - space_after
                height = imgui.get_frame_height()
                imgui.progress_bar(ratio, (width, height))
                if download.state == download.State.Downloading:
                    text = f"{ratio:.0%}"
                elif download.state == download.State.Stopped:
                    if not errored:
                        text = "Done!"
                    else:
                        text = "Error!"
                        self.draw_hover_text(
                            download.error or f"Received less data than expected ({download.progress} != {download.total})",
                            text=None,
                        )
                        if download.traceback and imgui.is_item_clicked():
                            utils.push_popup(
                                msgbox.msgbox, f"Error downloading {name}",
                                download.error,
                                MsgBox.error,
                                more=download.traceback,
                            )
                else:
                    text = f"{download.state.name}..."
                imgui.same_line()
                draw_list = imgui.get_window_draw_list()
                col = imgui.get_color_u32_rgba(1, 1, 1, 1)
                text_size = imgui.calc_text_size(text)
                screen_pos = imgui.get_cursor_screen_pos()
                text_x = screen_pos.x - (width + text_size.x) / 2 - imgui.style.item_spacing.x
                text_y = screen_pos.y + (height - text_size.y) / 2
                draw_list.add_text(text_x, text_y, col, text)

                if download.state == download.State.Downloading:
                    if was_canceling := download.cancel:
                        imgui.push_disabled()
                    if imgui.button(icons.stop):
                        download.cancel = True
                    if was_canceling:
                        imgui.pop_disabled()
                elif download.state == download.State.Stopped:
                    if imgui.button(icons.cancel):
                        to_remove.append(name)
                    imgui.same_line()
                    if imgui.button(icons.trash_can_outline):
                        download.path.unlink(missing_ok=True)
                        if download.extracted:
                            shutil.rmtree(download.extracted, ignore_errors=True)
                        to_remove.append(name)
            for name in to_remove:
                del api.downloads[name]

        imgui.spacing()
        imgui.spacing()
        imgui.spacing()
        imgui.end_child()


class TrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, main_gui: MainGUI):
        self.show_gui_events = [
            QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick,
            QtWidgets.QSystemTrayIcon.ActivationReason.MiddleClick,
            QtWidgets.QSystemTrayIcon.ActivationReason.Trigger
        ]
        self.main_gui = main_gui
        self.idle_icon = QtGui.QIcon(str(globals.self_path / 'resources/icons/icon.png'))
        self.paused_icon = QtGui.QIcon(str(globals.self_path / 'resources/icons/paused.png'))
        self.msg_queue: list[TrayMsg] = []
        super().__init__(self.idle_icon)

        self.watermark = QtGui.QAction(f"F95Checker {globals.version_name}")
        self.watermark.triggered.connect(lambda *_: self.main_gui.show())

        self.next_refresh = QtGui.QAction("Next Refresh: N/A")
        self.next_refresh.setEnabled(False)

        self.refresh_btn = QtGui.QAction("Refresh Now!")
        self.refresh_btn.triggered.connect(lambda *_: globals.refresh_task.cancel() if utils.is_refreshing() else utils.start_refresh_task(api.refresh()))

        def update_pause(*_):
            self.main_gui.bg_mode_paused = not self.main_gui.bg_mode_paused
            if self.main_gui.bg_mode_paused:
                self.main_gui.bg_mode_timer = None
                self.main_gui.bg_mode_notifs_timer = None
            self.update_status()
        self.toggle_pause = QtGui.QAction("Pause Auto Refresh")
        self.toggle_pause.triggered.connect(update_pause)

        self.toggle_gui = QtGui.QAction("Toggle GUI")
        self.toggle_gui.triggered.connect(lambda *_: self.main_gui.show() if self.main_gui.hidden else self.main_gui.hide())

        self.quit = QtGui.QAction("Quit")
        self.quit.triggered.connect(self.main_gui.close)

        self.menu = QtWidgets.QMenu()
        self.menu.addAction(self.watermark)
        self.menu.addAction(self.next_refresh)
        self.menu.addAction(self.refresh_btn)
        self.menu.addAction(self.toggle_pause)
        self.menu.addAction(self.toggle_gui)
        self.menu.addAction(self.quit)
        self.setContextMenu(self.menu)
        self.menu_open = False
        self.menu.aboutToShow.connect(self.showing_menu)
        self.menu.aboutToHide.connect(self.hiding_menu)
        self.menu.aboutToShow.connect(self.update_menu)

        self.activated.connect(self.activated_filter)
        self.messageClicked.connect(self.main_gui.show)

        self.show()

    def update_icon(self, *_):
        if self.main_gui.bg_mode_paused and self.main_gui.hidden:
            self.setIcon(self.paused_icon)
        else:
            self.setIcon(self.idle_icon)

    def animate_refresh_icon(self):
        icn = 1 + (int(time.time() * 8) % 16)
        self.setIcon(QtGui.QIcon(str(globals.self_path / f"resources/icons/refreshing{icn}.png")))

    def showing_menu(self, *_):
        self.menu_open = True

    def hiding_menu(self, *_):
        self.menu_open = False

    def update_menu(self, *_):
        if self.main_gui.hidden:
            if self.main_gui.bg_mode_paused:
                next_refresh = "Paused"
            elif self.main_gui.bg_mode_timer or self.main_gui.bg_mode_notifs_timer:
                next_refresh = dt.datetime.fromtimestamp(
                    min(
                        self.main_gui.bg_mode_timer or globals.settings.bg_refresh_interval,
                        self.main_gui.bg_mode_notifs_timer or globals.settings.bg_notifs_interval
                    )
                ).strftime("%H:%M")
            elif utils.is_refreshing():
                next_refresh = "Now"
            else:
                next_refresh = "N/A"
            self.next_refresh.setText(f"Next Refresh: {next_refresh}")
            self.next_refresh.setVisible(True)
        else:
            self.next_refresh.setVisible(False)

        if utils.is_refreshing():
            self.refresh_btn.setText("Cancel Refresh")
        else:
            self.refresh_btn.setText("Refresh Now!")

        if self.main_gui.hidden:
            if self.main_gui.bg_mode_paused:
                self.toggle_pause.setText("Unpause Auto Refresh")
            else:
                self.toggle_pause.setText("Pause Auto Refresh")
            self.toggle_pause.setVisible(True)
        else:
            self.toggle_pause.setVisible(False)

        if self.main_gui.hidden:
            self.toggle_gui.setText("Switch to GUI")
        else:
            self.toggle_gui.setText("Switch to BG")

    def update_status(self, *_):
        self.update_menu()
        self.update_icon()

    def activated_filter(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason):
        if reason in self.show_gui_events:
            self.main_gui.show()

    def push_msg(self, title: str, msg: str, icon: QtWidgets.QSystemTrayIcon.MessageIcon):
        self.msg_queue.append(TrayMsg(title=title, msg=msg, icon=icon))

    def tick_msgs(self):
        while self.msg_queue:
            msg = self.msg_queue.pop(0)
            self.showMessage(msg.title, msg.msg, msg.icon, 5000)
