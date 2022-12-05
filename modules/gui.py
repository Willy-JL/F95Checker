from imgui.integrations.glfw import GlfwRenderer
from PyQt6 import QtCore, QtGui, QtWidgets
import concurrent.futures
import OpenGL.GL as gl
import datetime as dt
from PIL import Image
import configparser
import dataclasses
import threading
import platform
import asyncio
import pathlib
import aiohttp
import OpenGL
import imgui
import time
import glfw
import sys

from modules.structs import Browser, Datestamp, DefaultStyle, DisplayMode, ExeState, Filter, FilterMode, Game, Label, MsgBox, Os, SortSpec, Status, Tag, Timestamp, TrayMsg, Type
from modules import globals, api, async_thread, callbacks, colors, db, error, filepicker, icons, imagehelper, msgbox, ratingwidget, rpc_thread, utils

imgui.io = None
imgui.style = None


class Columns:

    @dataclasses.dataclass
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

        def __post_init__(self):
            # Header
            if self.ghost or self.no_header:
                self.header = "###" + self.name[2:]
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
            self, f"{icons.counter} Version",
            ghost=True,
            default=True,
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
            self, f"{icons.information_variant} Name",
            imgui.TABLE_COLUMN_WIDTH_STRETCH | imgui.TABLE_COLUMN_DEFAULT_SORT,
            default=True,
            sortable=True,
            hideable=False,
        )
        self.developer = self.Column(
            self, f"{icons.account_outline} Developer",
        )
        self.last_updated = self.Column(
            self, f"{icons.update} Last Updated",
            default=True,
            sortable=True,
            resizable=False,
        )
        self.last_played = self.Column(
            self, f"{icons.motion_play_outline} Last Played",
            sortable=True,
            resizable=False,
        )
        self.added_on = self.Column(
            self, f"{icons.book_clock} Added On",
            sortable=True,
            resizable=False,
        )
        self.played = self.Column(
            self, f"{icons.flag_checkered} Played",
            default=True,
            sortable=True,
            resizable=False,
            short_header=True,
        )
        self.installed = self.Column(
            self, f"{icons.cloud_download} Installed",
            default=True,
            sortable=True,
            resizable=False,
            short_header=True,
        )
        self.rating = self.Column(
            self, f"{icons.star_outline} Rating",
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


class MainGUI():
    def __init__(self):
        # Constants
        self.sidebar_size = 230
        self.window_flags: int = (
            imgui.WINDOW_NO_MOVE |
            imgui.WINDOW_NO_RESIZE |
            imgui.WINDOW_NO_COLLAPSE |
            imgui.WINDOW_NO_TITLE_BAR |
            imgui.WINDOW_NO_SCROLLBAR |
            imgui.WINDOW_NO_SCROLL_WITH_MOUSE
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
        self.add_box_text = ""
        self.prev_size = (0, 0)
        self.screen_pos = (0, 0)
        self.require_sort = True
        self.repeat_chars = False
        self.scroll_percent = 0.0
        self.prev_manual_sort = 0
        self.add_box_valid = False
        self.bg_mode_paused = False
        self.game_hitbox_click = False
        self.hovered_game: Game = None
        self.filters: list[Filter] = []
        self.refresh_ratio_smooth = 0.0
        self.bg_mode_timer: float = None
        self.input_chars: list[int] = []
        self.switched_display_mode = False
        self.type_label_width: float = None
        self.sort_specs: list[SortSpec] = []
        self.ghost_columns_enabled_count = 0
        self.sorted_games_ids: list[int] = []
        self.bg_mode_notifs_timer: float = None

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
        if not all([isinstance(x, int) for x in size]) or not len(size) == 2:
            size = (1280, 720)

        # Setup GLFW window
        self.window: glfw._GLFWwindow = utils.impl_glfw_init(*size, "F95Checker")
        if all([isinstance(x, int) for x in pos]) and len(pos) == 2 and utils.validate_geometry(*pos, *size):
            glfw.set_window_pos(self.window, *pos)
        self.screen_pos = glfw.get_window_pos(self.window)
        if globals.settings.start_in_background:
            self.hide()
        self.icon_path = globals.self_path / "resources/icons/icon.png"
        self.icon_texture = imagehelper.ImageHelper(self.icon_path)
        glfw.set_window_icon(self.window, 1, Image.open(self.icon_path))
        self.impl = GlfwRenderer(self.window)
        glfw.set_char_callback(self.window, self.char_callback)
        glfw.set_window_close_callback(self.window, self.close_callback)
        glfw.set_window_iconify_callback(self.window, self.minimize_callback)
        glfw.set_window_focus_callback(self.window, self.focus_callback)
        glfw.set_window_pos_callback(self.window, self.pos_callback)
        glfw.set_drop_callback(self.window, self.drop_callback)
        glfw.swap_interval(globals.settings.vsync_ratio)
        self.refresh_fonts()

        # Show errors in threads
        def syncexcepthook(args: threading.ExceptHookArgs):
            if args.exc_type is not msgbox.Exc:
                err = error.text(args.exc_value)
                tb = error.traceback(args.exc_value)
                utils.push_popup(msgbox.msgbox, "Oops!", f"Something went wrong in a parallel task of a separate thread:\n{err}", MsgBox.error, more=tb)
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
            if isinstance(exc, asyncio.TimeoutError) or isinstance(exc, aiohttp.ClientError):
                utils.push_popup(msgbox.msgbox, "Connection error", f"A connection request to F95Zone has failed:\n{err}\n\nPossible causes include:\n - You are refreshing with too many workers, try lowering them in settings\n - Your timeout value is too low, try increasing it in settings\n - F95Zone is experiencing difficulties, try waiting a bit and retrying\n - F95Zone is blocked in your country, network, antivirus or firewall, try a VPN\n - Your retries value is too low, try increasing it in settings (last resort!)", MsgBox.warn, more=tb)
                return
            utils.push_popup(msgbox.msgbox, "Oops!", f"Something went wrong in an asynchronous task of a separate thread:\n{err}", MsgBox.error, more=tb)
        async_thread.done_callback = asyncexcepthook

        # Load style configuration
        imgui.style = imgui.get_style()
        imgui.style.item_spacing = (imgui.style.item_spacing.y, imgui.style.item_spacing.y)
        imgui.style.colors[imgui.COLOR_MODAL_WINDOW_DIM_BACKGROUND] = (0, 0, 0, 0.5)
        imgui.style.scrollbar_size = 10
        imgui.style.frame_border_size = 1.6
        imgui.style.colors[imgui.COLOR_TABLE_BORDER_STRONG] = (0, 0, 0, 0)
        self.refresh_styles()
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
        def push_alpha(amount: float = 0.5):
            imgui.push_style_var(imgui.STYLE_ALPHA, imgui.style.alpha * amount)
        imgui.push_alpha = push_alpha
        def pop_alpha():
            imgui.pop_style_var()
        imgui.pop_alpha = pop_alpha
        def push_disabled():
            imgui.push_no_interaction()
            imgui.push_alpha()
        imgui.push_disabled = push_disabled
        def pop_disabled():
            imgui.pop_alpha()
            imgui.pop_no_interaction()
        imgui.pop_disabled = pop_disabled
        def is_topmost():
            return not imgui.is_popup_open("", imgui.POPUP_ANY_POPUP_ID)
        imgui.is_topmost = is_topmost

    def refresh_styles(self):
        globals.settings.style_accent = \
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
        style_accent_dim = \
            imgui.style.colors[imgui.COLOR_TAB] = \
            imgui.style.colors[imgui.COLOR_RESIZE_GRIP] = \
            imgui.style.colors[imgui.COLOR_TAB_UNFOCUSED] = \
            imgui.style.colors[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = \
        (*globals.settings.style_accent[:3], 0.25)
        globals.settings.style_alt_bg = \
            imgui.style.colors[imgui.COLOR_TABLE_HEADER_BACKGROUND] = \
            imgui.style.colors[imgui.COLOR_TABLE_ROW_BACKGROUND_ALT] = \
        globals.settings.style_alt_bg
        globals.settings.style_bg = \
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
        globals.settings.style_border = \
            imgui.style.colors[imgui.COLOR_BORDER] = \
            imgui.style.colors[imgui.COLOR_SEPARATOR] = \
        globals.settings.style_border
        style_corner_radius = \
            imgui.style.tab_rounding  = \
            imgui.style.grab_rounding = \
            imgui.style.frame_rounding = \
            imgui.style.child_rounding = \
            imgui.style.popup_rounding = \
            imgui.style.window_rounding = \
            imgui.style.scrollbar_rounding = \
        globals.settings.style_corner_radius * globals.settings.interface_scaling
        globals.settings.style_text = \
            imgui.style.colors[imgui.COLOR_TEXT] = \
        globals.settings.style_text
        globals.settings.style_text_dim = \
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
        karla_path = str(next(globals.self_path.glob("resources/fonts/Karla-Regular.*.ttf")))
        meslo_path = str(next(globals.self_path.glob("resources/fonts/MesloLGS-Regular.*.ttf")))
        noto_path  = str(next(globals.self_path.glob("resources/fonts/NotoSans-Regular.*.ttf")))
        mdi_path   = str(icons.font_path)
        merge = dict(merge_mode=True)
        oversample = dict(oversample_h=2, oversample_v=2)
        karla_config = imgui.core.FontConfig(         glyph_offset_y=-0.5, **oversample)
        meslo_config = imgui.core.FontConfig(                              **oversample)
        noto_config  = imgui.core.FontConfig(**merge, glyph_offset_y=-0.5, **oversample)
        mdi_config   = imgui.core.FontConfig(**merge, glyph_offset_y=+1.0)
        karla_range = imgui.core.GlyphRanges([0x1,            0x20ac,         0])
        meslo_range = imgui.core.GlyphRanges([0x1,            0x2e2e,         0])
        noto_range  = imgui.core.GlyphRanges([0x1,            0xfffd,         0])
        mdi_range   = imgui.core.GlyphRanges([icons.min_char, icons.max_char, 0])
        msgbox_range_values = []
        for icon in [icons.information, icons.alert_rhombus, icons.alert_octagon]:
            msgbox_range_values += [ord(icon), ord(icon)]
        msgbox_range_values.append(0)
        msgbox_range = imgui.core.GlyphRanges(msgbox_range_values)
        size_14 = self.scaled(14 * font_scaling_factor)
        size_15 = self.scaled(15 * font_scaling_factor)
        size_18 = self.scaled(18 * font_scaling_factor)
        size_28 = self.scaled(28 * font_scaling_factor)
        size_69 = self.scaled(69 * font_scaling_factor)
        fonts = type("FontStore", (), {})()
        imgui.fonts = fonts
        add_font = imgui.io.fonts.add_font_from_file_ttf
        # Default font + more glyphs + icons
        fonts.default = add_font(karla_path, size_18, font_config=karla_config, glyph_ranges=karla_range)
        add_font(                noto_path,  size_18, font_config=noto_config,  glyph_ranges=noto_range)
        add_font(                mdi_path,   size_18, font_config=mdi_config,   glyph_ranges=mdi_range)
        # Big font + more glyphs + icons
        fonts.big     = add_font(karla_path, size_28, font_config=karla_config, glyph_ranges=karla_range)
        add_font(                noto_path,  size_28, font_config=noto_config,  glyph_ranges=noto_range)
        add_font(                mdi_path,   size_28, font_config=mdi_config,   glyph_ranges=mdi_range)
        # Big font + more glyphs + icons
        fonts.small   = add_font(karla_path, size_14, font_config=karla_config, glyph_ranges=karla_range)
        add_font(                noto_path,  size_14, font_config=noto_config,  glyph_ranges=noto_range)
        add_font(                mdi_path,   size_14, font_config=mdi_config,   glyph_ranges=mdi_range)
        # Monospace font for more info dropdowns
        fonts.mono    = add_font(meslo_path, size_15, font_config=meslo_config, glyph_ranges=meslo_range)
        # MsgBox type icons/thumbnails
        fonts.msgbox  = add_font(mdi_path,   size_69,                           glyph_ranges=msgbox_range)
        try:
            tex_width, tex_height, pixels = imgui.io.fonts.get_tex_data_as_rgba32()
        except SystemError:
            tex_height = 1
            max_tex_size = 0
        if tex_height > max_tex_size:
            globals.settings.interface_scaling = 1.0
            async_thread.run(db.update_settings("interface_scaling"))
            return self.refresh_fonts()
        self.impl.refresh_font_texture()
        self.type_label_width = None

    def close(self, *args, **kwargs):
        glfw.set_window_should_close(self.window, True)

    def char_callback(self, window: glfw._GLFWwindow, char: int):
        self.impl.char_callback(window, char)
        self.input_chars.append(char)

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

    def hide(self, *args, **kwargs):
        self.screen_pos = glfw.get_window_pos(self.window)
        glfw.hide_window(self.window)
        self.hidden = True
        self.tray.update_status()

    def show(self, *args, **kwargs):
        self.bg_mode_timer = None
        self.bg_mode_notifs_timer = None
        glfw.hide_window(self.window)
        glfw.show_window(self.window)
        if utils.validate_geometry(*self.screen_pos, *self.prev_size):
            glfw.set_window_pos(self.window, *self.screen_pos)
        self.hidden = False
        self.tray.update_status()

    def scaled(self, size: int | float):
        return size * globals.settings.interface_scaling

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
                self.qt_app.processEvents()
                if self.repeat_chars:
                    for char in self.input_chars:
                        imgui.io.add_input_character(char)
                    self.repeat_chars = False
                self.input_chars.clear()
                glfw.poll_events()
                self.impl.process_inputs()
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
                        scroll_energy += imgui.io.mouse_wheel
                        if abs(scroll_energy) > 0.1:
                            scroll_now = scroll_energy * imgui.io.delta_time * globals.settings.scroll_smooth_speed
                            scroll_energy -= scroll_now
                        else:
                            scroll_now = 0.0
                            scroll_energy = 0.0
                        imgui.io.mouse_wheel = scroll_now

                    # Redraw only when needed
                    draw = False
                    draw = draw or api.updating
                    draw = draw or self.require_sort
                    draw = draw or imagehelper.redraw
                    draw = draw or utils.is_refreshing()
                    draw = draw or size != self.prev_size
                    draw = draw or prev_hidden != self.hidden
                    draw = draw or prev_focused != self.focused
                    draw = draw or prev_minimized != self.minimized
                    draw = draw or prev_scaling != globals.settings.interface_scaling
                    draw = draw or (prev_mouse_pos != mouse_pos and (prev_win_hovered or win_hovered))
                    draw = draw or bool(imgui.io.mouse_wheel) or bool(self.input_chars) or any(imgui.io.mouse_down) or any(imgui.io.keys_down)
                    if draw:
                        draw_next = max(draw_next, imgui.io.delta_time + 0.5)  # Draw for at least next half second
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
                            updated_games = dict(globals.updated_games)
                            globals.updated_games.clear()
                            sorted_ids = list(updated_games)
                            sorted_ids.sort(key=lambda id: 2 if globals.games[id].type in (Type.Misc, Type.Cheat_Mod, Type.Mod, Type.READ_ME, Type.Request, Type.Tool, Type.Tutorial) else 1 if globals.games[id].type in (Type.Collection, Type.Manga, Type.SiteRip, Type.Comics, Type.CG, Type.Pinup, Type.Video, Type.GIF) else 0)
                            utils.push_popup(self.draw_updates_popup, updated_games, sorted_ids, len(updated_games))

                        # Start drawing
                        prev_scaling = globals.settings.interface_scaling
                        imgui.new_frame()
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
                        if (count := api.images.count) > 0:
                            text = f"Downloading {count}{'+' if count == globals.settings.refresh_workers else ''} image{'s' if count > 1 else ''}..."
                        elif (count := api.fulls.count) > 0:
                            text = f"Running {count}{'+' if count == globals.settings.refresh_workers else ''} full recheck{'s' if count > 1 else ''}..."
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
                        imgui.same_line(spacing=1)
                        imgui.begin_child("###sidebar_frame", width=sidebar_size - 1, height=-text_size.y)
                        self.draw_sidebar()
                        imgui.end_child()

                        # Status / watermark text
                        imgui.set_cursor_screen_pos((text_x - _3, text_y))
                        if imgui.invisible_button("###watermark_btn", width=text_size.x + _6, height=text_size.y + _3):
                            utils.push_popup(self.draw_about_popup)
                        imgui.set_cursor_screen_pos((text_x, text_y))
                        imgui.text(text)

                        # Popups
                        open_popup_count = 0
                        for popup_func in globals.popup_stack:
                            opened, closed =  popup_func()
                            if closed:
                                globals.popup_stack.remove(popup_func)
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
                    if self.hidden and not self.bg_mode_paused:
                        if not self.bg_mode_timer and not utils.is_refreshing():
                            # Schedule next refresh
                            self.bg_mode_timer = time.time() + globals.settings.bg_refresh_interval * 60
                            self.tray.update_status()
                        elif self.bg_mode_timer and time.time() > self.bg_mode_timer:
                            # Run scheduled refresh
                            self.bg_mode_timer = None
                            utils.start_refresh_task(api.refresh(notifs=False), reset_bg_timers=False)
                        elif globals.settings.check_notifs:
                            if not self.bg_mode_notifs_timer and not utils.is_refreshing():
                                # Schedule next notif check
                                self.bg_mode_notifs_timer = time.time() + globals.settings.bg_notifs_interval * 60
                                self.tray.update_status()
                            elif self.bg_mode_notifs_timer and time.time() > self.bg_mode_notifs_timer:
                                # Run scheduled notif check
                                self.bg_mode_notifs_timer = None
                                utils.start_refresh_task(api.check_notifs(login=True), reset_bg_timers=False)
                    # Wait idle time
                    if self.tray.menu_open:
                        time.sleep(1 / 60)
                    else:
                        time.sleep(1 / 3)
        finally:
            # Main loop over, cleanup and close
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

    def draw_hover_text(self, hover_text: str, text="(?)", force=False, *args, **kwargs):
        if text:
            imgui.text_disabled(text, *args, **kwargs)
        if force or imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.push_text_wrap_pos(min(imgui.get_font_size() * 35, imgui.io.display_size.x))
            imgui.text_unformatted(hover_text)
            imgui.pop_text_wrap_pos()
            imgui.end_tooltip()
            return True
        return False

    def draw_type_widget(self, type: Type, wide=True, align=False, *args, **kwargs):
        imgui.push_no_interaction()
        imgui.push_style_color(imgui.COLOR_BUTTON, *type.color)
        imgui.push_style_var(imgui.STYLE_FRAME_BORDERSIZE, 0)
        if wide:
            x_padding = 4
            backup_y_padding = imgui.style.frame_padding.y
            imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (x_padding, 0))
            if self.type_label_width is None:
                self.type_label_width = 0
                for name in Type._member_names_:
                    self.type_label_width = max(self.type_label_width, imgui.calc_text_size(name).x)
                self.type_label_width += 2 * x_padding
            if align:
                imgui.push_y(backup_y_padding)
            imgui.button(f"{type.name}###type_{type.value}", *args, width=self.type_label_width, **kwargs)
            if align:
                imgui.pop_y()
            imgui.pop_style_var(2)
        else:
            imgui.small_button(f"{type.name}###type_{type.value}", *args, **kwargs)
            imgui.pop_style_var()
        imgui.pop_style_color()
        imgui.pop_no_interaction()

    def draw_tag_widget(self, tag: Tag, *args, **kwargs):
        imgui.push_no_interaction()
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.3, 0.3, 0.3, 1.0)
        imgui.push_style_var(imgui.STYLE_FRAME_BORDERSIZE, 0)
        imgui.small_button(f"{tag.name}###tag_{tag.value}", *args, **kwargs)
        imgui.pop_style_var()
        imgui.pop_style_color()
        imgui.pop_no_interaction()

    def draw_label_widget(self, label: Label, short=False, *args, **kwargs):
        if short:
            imgui.push_style_color(imgui.COLOR_BUTTON, *label.color)
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *label.color)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *label.color)
        else:
            imgui.push_style_color(imgui.COLOR_BUTTON, *label.color)
            imgui.push_no_interaction()
        imgui.push_style_var(imgui.STYLE_FRAME_BORDERSIZE, 0)
        imgui.small_button(f"{label.short_name if short else label.name}###label_{label.id}", *args, **kwargs)
        if short and imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.push_font(imgui.fonts.default)
            self.draw_label_widget(label, short=False)
            imgui.pop_font()
            imgui.end_tooltip()
        imgui.pop_style_var()
        if short:
            imgui.pop_style_color(3)
        else:
            imgui.pop_no_interaction()
            imgui.pop_style_color()

    def draw_game_more_info_button(self, game: Game, label="", selectable=False, carousel_ids: list = None, *args, **kwargs):
        id = f"{label}###{game.id}_more_info"
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if clicked:
            utils.push_popup(self.draw_game_info_popup, game, carousel_ids.copy() if carousel_ids else None)
        return clicked

    def draw_game_play_button(self, game: Game, label="", selectable=False, executable: str = None, i=-1, *args, **kwargs):
        id = f"{label}###{game.id}_play_button_{i}"
        if not game.executables:
            imgui.push_style_color(imgui.COLOR_TEXT, *imgui.style.colors[imgui.COLOR_TEXT_DISABLED][:3], 0.75)
        else:
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
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if not game.executables or not valid:
            imgui.pop_style_color()
        if imgui.is_item_clicked(2):
            callbacks.open_game_folder(game)
        elif clicked:
            callbacks.launch_game(game, executable=executable)
        return clicked

    def draw_game_update_icon(self, game: Game, *args, **kwargs):
        imgui.text_colored(icons.star_circle, 0.85, 0.85, 0.00, *args, **kwargs)
        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.push_text_wrap_pos(min(imgui.get_font_size() * 35, imgui.io.display_size.x))
            imgui.text_unformatted(
                "This game has an update available!\n"
                f"Installed version: {game.installed}\n"
                f"Latest version: {game.version}"
            )
            imgui.pop_text_wrap_pos()
            imgui.end_tooltip()

    def draw_game_name_text(self, game: Game, *args, **kwargs):
        if game.played:
            imgui.text(game.name, *args, **kwargs)
        else:
            imgui.text_colored(game.name, *globals.settings.style_accent, *args, **kwargs)

    def get_game_version_text(self, game: Game):
        if game.installed and game.installed != game.version:
            return f"{icons.cloud_download} {game.installed}   |   {icons.star_shooting} {game.version}"
        else:
            return game.version

    def draw_game_status_widget(self, game: Game, *args, **kwargs):
        if game.status is Status.Unchecked:
            imgui.text_colored(icons.alert_circle, 0.50, 0.50, 0.50, *args, **kwargs)
        elif game.status is Status.Normal:
            imgui.text_colored(icons.lightning_bolt_circle, *imgui.style.colors[imgui.COLOR_TEXT][:-1], *args, **kwargs)
        elif game.status is Status.Completed:
            imgui.text_colored(icons.checkbox_marked_circle, 0.00, 0.85, 0.00, *args, **kwargs)
        elif game.status is Status.OnHold:
            imgui.text_colored(icons.pause_circle, 0.00, 0.50, 0.95, *args, **kwargs)
        elif game.status is Status.Abandoned:
            imgui.text_colored(icons.close_circle, 0.87, 0.20, 0.20, *args, **kwargs)
        else:
            imgui.text("", *args, **kwargs)

    def draw_game_played_checkbox(self, game: Game, label="", *args, **kwargs):
        changed, game.played = imgui.checkbox(f"{label}###{game.id}_played", game.played, *args, **kwargs)
        if changed:
            async_thread.run(db.update_game(game, "played"))
            self.require_sort = True

    def draw_game_installed_checkbox(self, game: Game, label="", *args, **kwargs):
        if game.installed and game.installed == game.version:
            checkbox = imgui.checkbox
        else:
            checkbox = imgui._checkbox
        changed, _ = checkbox(f"{label}###{game.id}_installed", bool(game.installed), *args, **kwargs)
        if changed:
            if game.installed == game.version:
                game.installed = ""  # Latest installed -> Not installed
            else:
                game.installed = game.version  # Not installed -> Latest installed, Outdated installed -> Latest installed
            async_thread.run(db.update_game(game, "installed"))
            self.require_sort = True

    def draw_game_rating_widget(self, game: Game, *args, **kwargs):
        changed, value = ratingwidget.ratingwidget(f"{game.id}_rating", game.rating)
        if changed:
            game.rating = value
            async_thread.run(db.update_game(game, "rating"))
            self.require_sort = True

    def draw_game_open_thread_button(self, game: Game, label="", selectable=False, *args, **kwargs):
        id = f"{label}###{game.id}_open_thread"
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if imgui.is_item_clicked(2):
            glfw.set_clipboard_string(self.window, game.url)
        elif clicked:
            callbacks.open_webpage(game.url)
        return clicked

    def draw_game_copy_link_button(self, game: Game, label="", selectable=False, *args, **kwargs):
        id = f"{label}###{game.id}_copy_link"
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if clicked:
            glfw.set_clipboard_string(self.window, game.url)
        return clicked

    def draw_game_remove_button(self, game: Game, label="", selectable=False, *args, **kwargs):
        id = f"{label}###{game.id}_remove"
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if clicked:
            callbacks.remove_game(game)
        return clicked

    def draw_game_add_exe_button(self, game: Game, label="", selectable=False, *args, **kwargs):
        id = f"{label}###{game.id}_add_exe"
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if clicked:
            def select_callback(selected):
                if selected:
                    game.add_executable(selected)
                    async_thread.run(db.update_game(game, "executables"))
            utils.push_popup(filepicker.FilePicker(f"Select or drop executable for {game.name}", start_dir=globals.settings.default_exe_dir, callback=select_callback).tick)
        return clicked

    def draw_game_clear_exes_button(self, game: Game, label="", selectable=False, *args, **kwargs):
        id = f"{label}###{game.id}_clear_exes"
        if not game.executables:
            imgui.push_disabled()
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if not game.executables:
            imgui.pop_disabled()
        if clicked:
            game.clear_executables()
            async_thread.run(db.update_game(game, "executables"))
        return clicked

    def draw_game_open_folder_button(self, game: Game, label="", selectable=False, executable: str = None, i=-1, *args, **kwargs):
        id = f"{label}###{game.id}_open_folder_{i}"
        if not game.executables:
            imgui.push_alpha()
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if not game.executables:
            imgui.pop_alpha()
        if clicked:
            callbacks.open_game_folder(game, executable=executable)
        return clicked

    def draw_game_recheck_button(self, game: Game, label="", selectable=False, *args, **kwargs):
        id = f"{label}###{game.id}_recheck"
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if clicked:
            utils.start_refresh_task(api.check(game, full=True, login=True))
        return clicked

    def draw_game_context_menu(self, game: Game):
        self.draw_game_more_info_button(game, label=f"{icons.information_outline} More Info", selectable=True, carousel_ids=self.sorted_games_ids)
        self.draw_game_recheck_button(game, label=f"{icons.reload_alert} Full Recheck", selectable=True)
        imgui.separator()
        self.draw_game_play_button(game, label=f"{icons.play} Play", selectable=True)
        self.draw_game_open_thread_button(game, label=f"{icons.open_in_new} Open Thread", selectable=True)
        self.draw_game_copy_link_button(game, label=f"{icons.content_copy} Copy Link", selectable=True)
        imgui.separator()
        self.draw_game_add_exe_button(game, label=f"{icons.folder_edit_outline} Add Exe", selectable=True)
        self.draw_game_clear_exes_button(game, label=f"{icons.folder_remove_outline} Clear Exes", selectable=True)
        self.draw_game_open_folder_button(game, label=f"{icons.folder_open_outline} Open Folder", selectable=True)
        imgui.separator()
        self.draw_game_played_checkbox(game, label=f"{icons.flag_checkered} Played")
        self.draw_game_installed_checkbox(game, label=f"{icons.cloud_download} Installed")
        imgui.separator()
        self.draw_game_rating_widget(game)
        if imgui.begin_menu(f"{icons.label_multiple_outline} Labels"):
            self.draw_game_labels_select_widget(game)
            imgui.end_menu()
        imgui.separator()
        self.draw_game_remove_button(game, label=f"{icons.trash_can_outline} Remove", selectable=True)

    def draw_game_notes_widget(self, game: Game, multiline=True, width: int | float = None, *args, **kwargs):
        if multiline:
            changed, game.notes = imgui.input_text_multiline(
                f"###{game.id}_notes",
                value=game.notes,
                width=width or imgui.get_content_region_available_width(),
                height=self.scaled(450),
                *args,
                **kwargs
            )
            setter_extra = lambda _=None: [setattr(self, "require_sort", True), async_thread.run(db.update_game(game, "notes"))]
            if changed:
                setter_extra()
            if imgui.begin_popup_context_item(f"###{game.id}_notes_context"):
                utils.text_context(game, "notes", setter_extra)
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
                value=first_line,
                *args,
                **kwargs
            )
            def setter_extra(value: str):
                # Merge with remaining lines
                if (offset := game.notes.find("\n")) != -1:
                    value += game.notes[offset:]
                game.notes = value
                self.require_sort = True
                async_thread.run(db.update_game(game, "notes"))
            if changed:
                setter_extra(first_line)
            if imgui.begin_popup_context_item(f"###{game.id}_notes_inline_context"):
                utils.text_context(type("_", (), dict(_=first_line))(), "_", setter_extra)
                imgui.end_popup()

    def draw_game_tags_widget(self, game: Game, *args, **kwargs):
        imgui.push_no_interaction()
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.3, 0.3, 0.3, 1.0)
        imgui.push_style_var(imgui.STYLE_FRAME_BORDERSIZE, 0)
        _20 = self.scaled(20)
        for tag in game.tags:
            if imgui.get_content_region_available_width() < imgui.calc_text_size(tag.name).x + _20:
                imgui.dummy(0, 0)
            imgui.small_button(f"{tag.name}###tag_{tag.value}", *args, **kwargs)
            imgui.same_line()
        imgui.dummy(0, 0)
        imgui.pop_style_var()
        imgui.pop_style_color()
        imgui.pop_no_interaction()

    def draw_game_labels_select_widget(self, game: Game, *args, **kwargs):
        if Label.instances:
            for label in Label.instances:
                changed, value = imgui.checkbox(f"###{game.id}_label_{label.id}", label in game.labels)
                if changed:
                    if value:
                        game.labels.append(label)
                    else:
                        game.labels.remove(label)
                    self.require_sort = True
                    async_thread.run(db.update_game(game, "labels"))
                imgui.same_line()
                self.draw_label_widget(label)
        else:
            imgui.text_disabled("Make some labels first!")

    def draw_game_labels_widget(self, game: Game, wrap=True, small=False, align=False, *args, **kwargs):
        _20 = self.scaled(20)
        if small:
            imgui.push_font(imgui.fonts.small)
            if align:
                imgui.push_y(self.scaled(2.5))
                popped_y = False
        for label in game.labels:
            if wrap and imgui.get_content_region_available_width() < imgui.calc_text_size(label.short_name if small else label.name).x + _20:
                if small and align and not popped_y:
                    imgui.pop_y()
                    popped_y = True
                imgui.dummy(0, 0)
            self.draw_label_widget(label, short=small, *args, **kwargs)
            imgui.same_line()
        if small and align and not popped_y:
            imgui.pop_y()
        elif wrap:
            imgui.dummy(0, 0)
        if small:
            imgui.pop_font()

    def draw_updates_popup(self, updated_games, sorted_ids, count, popup_uuid: str = ""):
        def popup_content():
            indent = self.scaled(222)
            width = indent - 3 * imgui.style.item_spacing.x
            full_width = 3 * indent
            wrap_width = 2 * indent - imgui.style.item_spacing.x
            name_offset = imgui.calc_text_size("Name: ").x + 2 * imgui.style.item_spacing.x
            version_offset = imgui.calc_text_size("Version: ").x + 2 * imgui.style.item_spacing.x
            arrow_width = imgui.calc_text_size(" -> ").x + imgui.style.item_spacing.x
            img_pos_x = imgui.get_cursor_pos_x()
            category = -1
            category_open = False
            imgui.push_text_wrap_pos(full_width)
            imgui.indent(indent)
            for i, id in enumerate(sorted_ids):
                if id not in globals.games:
                    sorted_ids.remove(id)
                    continue
                old_game = updated_games[id]
                game = globals.games[id]
                if game.type in (Type.Collection, Type.Manga, Type.SiteRip, Type.Comics, Type.CG, Type.Pinup, Type.Video, Type.GIF):
                    new_category = 1
                elif game.type in (Type.Misc, Type.Cheat_Mod, Type.Mod, Type.READ_ME, Type.Request, Type.Tool, Type.Tutorial):
                    new_category = 2
                else:
                    new_category = 0
                if new_category != category:
                    category = new_category
                    imgui.push_font(imgui.fonts.big)
                    imgui.set_cursor_pos_x(img_pos_x - self.scaled(8))
                    match category:
                        case 1:
                            category_open = imgui.tree_node(f"Media", flags=imgui.TREE_NODE_SPAN_FULL_WIDTH | imgui.TREE_NODE_DEFAULT_OPEN | imgui.TREE_NODE_NO_TREE_PUSH_ON_OPEN)
                        case 2:
                            category_open = imgui.tree_node(f"Misc", flags=imgui.TREE_NODE_SPAN_FULL_WIDTH | imgui.TREE_NODE_DEFAULT_OPEN | imgui.TREE_NODE_NO_TREE_PUSH_ON_OPEN)
                        case _:
                            category_open = imgui.tree_node(f"Games", flags=imgui.TREE_NODE_SPAN_FULL_WIDTH | imgui.TREE_NODE_DEFAULT_OPEN | imgui.TREE_NODE_NO_TREE_PUSH_ON_OPEN)
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
                    self.draw_game_status_widget(old_game)
                    imgui.same_line()
                    if full_width - imgui.get_cursor_pos_x() < arrow_width:
                        imgui.dummy(0, 0)
                    imgui.text_disabled(" -> ")
                    imgui.same_line()
                    imgui.text(game.status.name)
                    imgui.same_line()
                    self.draw_game_status_widget(game)

                imgui.spacing()
                self.draw_game_open_thread_button(game, label=f"{icons.open_in_new} Thread")
                imgui.same_line()
                self.draw_game_copy_link_button(game, label=f"{icons.content_copy} Link")
                imgui.same_line()
                self.draw_game_more_info_button(game, label=f"{icons.information_outline} Info", carousel_ids=sorted_ids)

                imgui.end_group()
                height =  imgui.get_item_rect_size().y + imgui.style.item_spacing.y
                crop = game.image.crop_to_ratio(width / height, fit=globals.settings.fit_images)
                imgui.set_cursor_pos((img_pos_x, img_pos_y))
                game.image.render(width, height, *crop, rounding=globals.settings.style_corner_radius)

                if i != count - 1:
                    imgui.text("\n")
            imgui.unindent(indent)
            imgui.pop_text_wrap_pos()
        return utils.popup(f"{count} update{'s' if count > 1 else ''}", popup_content, buttons=True, closable=True, outside=False, popup_uuid=popup_uuid)

    def draw_game_info_popup(self, game: Game, carousel_ids: list = None, popup_uuid: str = ""):
        popup_pos = [None]
        popup_size = [None]
        zoom_popup = [False]
        def popup_content():
            # Image
            image = game.image
            avail = imgui.get_content_region_available()
            if image.missing:
                text = "Image missing!"
                width = imgui.calc_text_size(text).x
                imgui.set_cursor_pos_x((avail.x - width + imgui.style.scrollbar_size) / 2)
                self.draw_hover_text(
                    text=text,
                    hover_text="This thread does not seem to have an image!" if game.image_url == "-" else "Run a full refresh to try downloading it again!"
                )
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
                width = min(avail.x, image.width)
                height = min(width * aspect_ratio, image.height)
                if height > (new_height := avail.y * self.scaled(0.4)):
                    height = new_height
                    width = height * (1 / aspect_ratio)
                if width < avail.x:
                    imgui.set_cursor_pos_x((avail.x - width + imgui.style.scrollbar_size) / 2)
                image_pos = imgui.get_cursor_screen_pos()

                imgui.begin_child("###image_zoomer", width=width, height=height + 1.0, flags=imgui.WINDOW_NO_SCROLLBAR)
                imgui.dummy(width + 2.0, height)
                imgui.set_scroll_x(1.0)
                imgui.set_cursor_screen_pos(image_pos)
                image.render(width, height, rounding=globals.settings.style_corner_radius)
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
                        rounding = globals.settings.style_corner_radius
                        flags = imgui.DRAW_ROUND_CORNERS_ALL
                        pos2 = (x + width, y + height)
                        fg_draw_list = imgui.get_foreground_draw_list()
                        fg_draw_list.add_image_rounded(image.texture_id, (x, y), pos2, rounding=rounding, flags=flags)
                    # Zoom
                    elif globals.settings.zoom_enabled:
                        if diff := int(imgui.get_scroll_x() - 1.0):
                            if imgui.is_key_down(glfw.KEY_LEFT_ALT):
                                globals.settings.zoom_area = min(max(globals.settings.zoom_area + diff, 1), 200)
                            else:
                                globals.settings.zoom_times = min(max(globals.settings.zoom_times * (-diff / 50.0 + 1.0), 1), 20)
                        zoom_popup[0] = True
                        out_size = min(*imgui.io.display_size) * globals.settings.zoom_area / 100
                        in_size = out_size / globals.settings.zoom_times
                        mouse_pos = imgui.io.mouse_pos
                        off_x = utils.map_range(in_size, 0.0, width, 0.0, 1.0) / 2.0
                        off_y = utils.map_range(in_size, 0.0, height, 0.0, 1.0) / 2.0
                        x = utils.map_range(mouse_pos.x, image_pos.x, image_pos.x + width, 0.0, 1.0)
                        y = utils.map_range(mouse_pos.y, image_pos.y, image_pos.y + height, 0.0, 1.0)
                        imgui.set_next_window_position(*mouse_pos, pivot_x=0.5, pivot_y=0.5)
                        imgui.begin_tooltip()
                        image.render(out_size, out_size, (x - off_x, y - off_y), (x + off_x, y + off_y), rounding=globals.settings.style_corner_radius)
                        imgui.end_tooltip()
                imgui.end_child()
            imgui.push_text_wrap_pos()

            imgui.push_font(imgui.fonts.big)
            self.draw_game_name_text(game)
            imgui.pop_font()

            self.draw_game_play_button(game, label=f"{icons.play} Play")
            imgui.same_line()
            self.draw_game_open_thread_button(game, label=f"{icons.open_in_new} Open Thread")
            imgui.same_line()
            self.draw_game_copy_link_button(game, label=f"{icons.content_copy} Copy Link")
            imgui.same_line()
            if imgui.button(f"{icons.pound} ID"):
                glfw.set_clipboard_string(self.window, str(game.id))
            if imgui.is_item_hovered():
                imgui.begin_tooltip()
                imgui.text_unformatted(
                    f"Thread ID: {game.id}\n"
                    f"Click to copy!"
                )
                imgui.end_tooltip()
            imgui.same_line()
            self.draw_game_played_checkbox(game, label=f"{icons.flag_checkered} Played")
            _10 = self.scaled(10)
            imgui.same_line(spacing=_10)
            self.draw_game_installed_checkbox(game, label=f"{icons.cloud_download} Installed")
            imgui.same_line(spacing=_10)
            self.draw_game_remove_button(game, label=f"{icons.trash_can_outline} Remove")

            imgui.text_disabled("Version:")
            imgui.same_line()
            if game.installed and game.installed != game.version:
                self.draw_game_update_icon(game)
                imgui.same_line()
            offset = imgui.calc_text_size("Version:").x + imgui.style.item_spacing.x
            utils.wrap_text(self.get_game_version_text(game), width=offset + imgui.get_content_region_available_width(), offset=offset)

            imgui.text_disabled("Developer:")
            imgui.same_line()
            offset = imgui.calc_text_size("Developer:").x + imgui.style.item_spacing.x
            utils.wrap_text(game.developer or "Unknown", width=offset + imgui.get_content_region_available_width(), offset=offset)

            imgui.text_disabled("Personal Rating:")
            imgui.same_line()
            self.draw_game_rating_widget(game)

            imgui.text_disabled("Status:")
            imgui.same_line()
            imgui.text(game.status.name)
            imgui.same_line()
            self.draw_game_status_widget(game)

            imgui.text_disabled("Forum Score:")
            imgui.same_line()
            imgui.text(f"{game.score:.1f}/5")

            imgui.text_disabled("Type:")
            imgui.same_line()
            self.draw_type_widget(game.type)

            imgui.text_disabled("Last Updated:")
            imgui.same_line()
            imgui.text(game.last_updated.display or "Unknown")

            imgui.text_disabled("Last Played:")
            imgui.same_line()
            imgui.text(game.last_played.display or "Never")
            if imgui.is_item_hovered():
                imgui.begin_tooltip()
                imgui.text_unformatted("Click to set as played right now!")
                imgui.end_tooltip()
            if imgui.is_item_clicked():
                game.last_played.update(time.time())
                async_thread.run(db.update_game(game, "last_played"))

            imgui.text_disabled("Added On:")
            imgui.same_line()
            imgui.text(game.added_on.display)

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
                for i, executable in enumerate(game.executables):
                    self.draw_game_play_button(game, label=icons.play, executable=executable, i=i)
                    imgui.same_line()
                    self.draw_game_open_folder_button(game, label=icons.folder_open_outline, executable=executable, i=i)
                    imgui.same_line()
                    if imgui.button(f"{icons.folder_remove_outline}###{game.id}_remove_exe_{i}"):
                        game.remove_executable(executable)
                    imgui.same_line()
                    imgui.text_unformatted(executable)

            imgui.text_disabled("Manage Exes:")
            imgui.same_line()
            self.draw_game_add_exe_button(game, label=f"{icons.folder_edit_outline} Add Exe")
            imgui.same_line()
            self.draw_game_clear_exes_button(game, label=f"{icons.folder_remove_outline} Clear Exes")
            imgui.same_line()
            self.draw_game_open_folder_button(game, label=f"{icons.folder_open_outline} Open Folder")

            imgui.spacing()

            if imgui.begin_tab_bar("Details"):

                if imgui.begin_tab_item((icons.clipboard_text_outline if game.changelog else icons.clipboard_text_off_outline) + " Changelog###changelog")[0]:
                    imgui.spacing()
                    if game.changelog:
                        imgui.text_unformatted(game.changelog)
                    else:
                        imgui.text_disabled("Either this game doesn't have a changelog, or the thread is not formatted properly!")
                    imgui.end_tab_item()

                if imgui.begin_tab_item((icons.information_outline if game.description else icons.information_off_outline) + " Description###description")[0]:
                    imgui.spacing()
                    if game.description:
                        imgui.text_unformatted(game.description)
                    else:
                        imgui.text_disabled("Either this game doesn't have a description, or the thread is not formatted properly!")
                    imgui.end_tab_item()

                if imgui.begin_tab_item((icons.draw_pen if game.notes else icons.pen) + " Notes###notes")[0]:
                    imgui.spacing()
                    self.draw_game_notes_widget(game)
                    imgui.end_tab_item()

                if imgui.begin_tab_item((icons.tag_multiple_outline if len(game.tags) > 1 else icons.tag_outline if len(game.tags) == 1 else icons.tag_off_outline) + " Tags###tags")[0]:
                    imgui.spacing()
                    if game.tags:
                        self.draw_game_tags_widget(game)
                    else:
                        imgui.text_disabled("This game has no tags!")
                    imgui.end_tab_item()

                if imgui.begin_tab_item((icons.label_multiple_outline if len(game.labels) > 1 else icons.label_outline if len(game.labels) == 1 else icons.label_off_outline) + " Labels###labels")[0]:
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

                imgui.end_tab_bar()
            imgui.pop_text_wrap_pos()
            popup_pos[0] = imgui.get_window_position()
            popup_size[0] = imgui.get_window_size()
        if game.id not in globals.games:
            return 0, True
        return_args = utils.popup(game.name, popup_content, closable=True, outside=True, popup_uuid=popup_uuid)
        # Has and is in carousel ids, is not the only one in them, is topmost popup and no item is active
        if carousel_ids and len(carousel_ids) > 1 and game.id in carousel_ids and imgui.is_topmost() and not imgui.is_any_item_active():
            pos = popup_pos[0]
            size = popup_size[0]
            if size and pos:
                imgui.push_font(imgui.fonts.big)
                text_size = imgui.calc_text_size(icons.arrow_left_drop_circle)
                offset = self.scaled(10)
                mouse_pos = imgui.get_mouse_pos()
                mouse_clicked = imgui.is_mouse_clicked()
                y = pos.y + (size.y + text_size.y) / 2
                x1 = pos.x - offset - text_size.x
                x2 = pos.x + size.x + offset
                if not zoom_popup[0]:
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
                    utils.push_popup(self.draw_game_info_popup, globals.games[change_id], carousel_ids)
                    return 1, True
        return return_args

    def draw_about_popup(self, popup_uuid: str = ""):
        def popup_content():
            _60 = self.scaled(60)
            _230 = self.scaled(230)
            imgui.begin_group()
            imgui.dummy(_60, _230)
            imgui.same_line()
            self.icon_texture.render(_230, _230, rounding=globals.settings.style_corner_radius)
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
            if imgui.button(f"{icons.open_in_new} F95Zone Thread", width=btn_width):
                callbacks.open_webpage(globals.tool_page)
            imgui.same_line()
            if imgui.button(f"{icons.github} GitHub Repo", width=btn_width):
                callbacks.open_webpage(globals.github_page)
            imgui.same_line()
            if imgui.button(f"{icons.link_variant} Donate + Links", width=btn_width):
                callbacks.open_webpage(globals.developer_page)
            imgui.spacing()
            imgui.spacing()
            imgui.push_text_wrap_pos(width)
            imgui.text("This software is licensed under the 3rd revision of the GNU General Public License (GPLv3) and is provided to you for free. "
                       "Furthermore, due to its license, it is also free as in freedom: you are free to use, study, modify and share this software "
                       "in whatever way you wish as long as you keep the same license.")
            imgui.spacing()
            imgui.spacing()
            imgui.text("However, F95Checker is actively developed by one person only, WillyJL, and not with the aim of profit but out of personal "
                       "interest and benefit for the whole F95Zone community. Donations are although greatly appreciated and aid the development "
                       "of this software. You can find donation links above.")
            imgui.spacing()
            imgui.spacing()
            imgui.text("If you find bugs or have some feedback, don't be afraid to let me know either on GitHub (using issues or pull requests) "
                       "or on F95Zone (in the thread comments or in direct messages).")
            imgui.spacing()
            imgui.spacing()
            imgui.text("Please note that this software is not ( yet ;) ) officially affiliated with the F95Zone platform.")
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
                "ascsd",
                "Jarulf",
                "DarkVermilion",
                "And 1 anon"
            ]:
                if imgui.get_content_region_available_width() < imgui.calc_text_size(name).x + self.scaled(20):
                    imgui.dummy(0, 0)
                imgui.bullet_text(name)
                imgui.same_line(spacing=16)
            imgui.spacing()
            imgui.spacing()
            imgui.text("Contributors:")
            imgui.bullet()
            imgui.text("GR3ee3N: Optimized build workflows and other PRs")
            imgui.bullet()
            imgui.text("batblue: MacOS suppport and feedback guy")
            imgui.bullet()
            imgui.text("unroot: Linux support and feedback guy")
            imgui.bullet()
            imgui.text("ploper26: Suggested HEAD requests for refreshing")
            imgui.bullet()
            imgui.text("ascsd: Helped with brainstorming on some issues and gave some tips")
            imgui.bullet()
            imgui.text("blackop: Helped fix some login window issues on Linux")
            imgui.spacing()
            imgui.spacing()
            imgui.text("Community:")
            for name in [
                "abada25",
                "AtotehZ",
                "bitogno",
                "d_pedestrian",
                "DarK x Duke",
                "GrammerCop",
                "MillenniumEarl",
                "SmurfyBlue",
                "yohudood",
                "And others that I might be forgetting"
            ]:
                if imgui.get_content_region_available_width() < imgui.calc_text_size(name).x + self.scaled(20):
                    imgui.dummy(0, 0)
                imgui.bullet_text(name)
                imgui.same_line(spacing=16)
            imgui.pop_text_wrap_pos()
        return utils.popup("About F95Checker", popup_content, closable=True, outside=True, popup_uuid=popup_uuid)

    def sort_games(self, sort_specs: imgui.core._ImGuiTableSortSpecs):
        manual_sort = cols.manual_sort.enabled
        if manual_sort != self.prev_manual_sort:
            self.prev_manual_sort = manual_sort
            self.require_sort = True
        if sort_specs.specs_count > 0:
            self.sort_specs = []
            for sort_spec in sort_specs.specs:
                self.sort_specs.insert(0, SortSpec(index=sort_spec.column_index, reverse=bool(sort_spec.sort_direction - 1)))
        if sort_specs.specs_dirty or self.require_sort:
            if manual_sort:
                changed = False
                to_remove = []
                for id in globals.settings.manual_sort_list:
                    if id not in globals.games:
                        to_remove.append(id)
                for id in to_remove:
                    while id in globals.settings.manual_sort_list:
                        globals.settings.manual_sort_list.remove(id)
                        changed = True
                for id in globals.games:
                    if id not in globals.settings.manual_sort_list:
                        globals.settings.manual_sort_list.append(id)
                        changed = True
                if changed:
                    async_thread.run(db.update_settings("manual_sort_list"))
                self.sorted_games_ids = globals.settings.manual_sort_list
            else:
                ids = list(globals.games)
                for sort_spec in self.sort_specs:
                    match sort_spec.index:
                        case cols.type.index:
                            key = lambda id: globals.games[id].type.name
                        case cols.developer.index:
                            key = lambda id: globals.games[id].developer.lower()
                        case cols.last_updated.index:
                            key = lambda id: - globals.games[id].last_updated.value
                        case cols.last_played.index:
                            key = lambda id: - globals.games[id].last_played.value
                        case cols.added_on.index:
                            key = lambda id: - globals.games[id].added_on.value
                        case cols.played.index:
                            key = lambda id: not globals.games[id].played
                        case cols.installed.index:
                            key = lambda id: 2 if not globals.games[id].installed else 1 if globals.games[id].installed == globals.games[id].version else 0
                        case cols.rating.index:
                            key = lambda id: - globals.games[id].rating
                        case cols.notes.index:
                            key = lambda id: globals.games[id].notes.lower() or "z"
                        case cols.status_standalone.index:
                            key = lambda id: globals.games[id].status.value
                        case cols.score.index:
                            key = lambda id: - globals.games[id].score
                        case _:  # Name and all others
                            key = lambda id: globals.games[id].name.lower()
                    ids.sort(key=key, reverse=sort_spec.reverse)
                self.sorted_games_ids = ids
            self.sorted_games_ids.sort(key=lambda id: globals.games[id].status is not Status.Unchecked)
            for flt in self.filters:
                match flt.mode.value:
                    case FilterMode.Exe_State.value:
                        key = lambda id: flt.invert != ((not globals.games[id].executables) if flt.match is ExeState.Unset else (bool(globals.games[id].executables) and (globals.games[id].executables_valid != (flt.match is ExeState.Invalid))))
                    case FilterMode.Installed.value:
                        key = lambda id: flt.invert != ((globals.games[id].installed != "") if flt.match else (globals.games[id].installed == globals.games[id].version))
                    case FilterMode.Label.value:
                        key = lambda id: flt.invert != (flt.match in globals.games[id].labels)
                    case FilterMode.Played.value:
                        key = lambda id: flt.invert != (globals.games[id].played is True)
                    case FilterMode.Rating.value:
                        key = lambda id: flt.invert != (globals.games[id].rating == flt.match)
                    case FilterMode.Score.value:
                        key = lambda id: flt.invert != (globals.games[id].score >= flt.match)
                    case FilterMode.Status.value:
                        key = lambda id: flt.invert != (globals.games[id].status is flt.match)
                    case FilterMode.Tag.value:
                        key = lambda id: flt.invert != (flt.match in globals.games[id].tags)
                    case FilterMode.Type.value:
                        key = lambda id: flt.invert != (globals.games[id].type is flt.match)
                    case FilterMode.Updated.value:
                        key = lambda id: flt.invert != (globals.games[id].installed != "" and globals.games[id].installed != globals.games[id].version)
                    case _:
                        key = None
                if key is not None:
                    self.sorted_games_ids = list(filter(key, self.sorted_games_ids))
            if self.add_box_text:
                if self.add_box_valid:
                    matches = [match.id for match in utils.extract_thread_matches(self.add_box_text)]
                    self.sorted_games_ids = list(filter(lambda id: id in matches, self.sorted_games_ids))
                else:
                    search = self.add_box_text.lower()
                    def key(id):
                        game = globals.games[id]
                        return search in game.version.lower() or search in game.developer.lower() or search in game.name.lower() or search in game.notes.lower()
                    self.sorted_games_ids = list(filter(key, self.sorted_games_ids))
            sort_specs.specs_dirty = False
            self.require_sort = False

    def handle_game_hitbox_events(self, game: Game, game_i: int = None):
        manual_sort = cols.manual_sort.enabled
        not_filtering = len(self.filters) == 0 and not self.add_box_text
        if imgui.is_item_hovered(imgui.HOVERED_ALLOW_WHEN_BLOCKED_BY_ACTIVE_ITEM):
            # Hover = image on refresh button
            self.hovered_game = game
            if imgui.is_item_clicked():
                self.game_hitbox_click = True
            if self.game_hitbox_click and not imgui.is_mouse_down():
                # Left click = open game info popup
                self.game_hitbox_click = False
                utils.push_popup(self.draw_game_info_popup, game, self.sorted_games_ids.copy())
        # Left click drag = swap if in manual sort mode
        if imgui.begin_drag_drop_source(flags=self.game_hitbox_drag_drop_flags):
            self.game_hitbox_click = False
            payload = (game_i or 0) + 1
            payload = payload.to_bytes(payload.bit_length(), sys.byteorder)
            imgui.set_drag_drop_payload("game_i", payload)
            imgui.end_drag_drop_source()
        if game_i is not None and manual_sort and not_filtering:
            if imgui.begin_drag_drop_target():
                if payload := imgui.accept_drag_drop_payload("game_i", flags=self.game_hitbox_drag_drop_flags):
                    payload = int.from_bytes(payload, sys.byteorder)
                    payload = payload - 1
                    lst = globals.settings.manual_sort_list
                    lst[game_i], lst[payload] = lst[payload], lst[game_i]
                    async_thread.run(db.update_settings("manual_sort_list"))
                imgui.end_drag_drop_target()
        context_id = f"###{game.id}_context"
        if (imgui.is_topmost() or imgui.is_popup_open(context_id)) and imgui.begin_popup_context_item(context_id):
            # Right click = context menu
            self.draw_game_context_menu(game)
            imgui.end_popup()

    def sync_scroll(self):
        if (scroll_max_y := imgui.get_scroll_max_y()) > 1.0:
            if self.switched_display_mode:
                imgui.set_scroll_y(self.scroll_percent * scroll_max_y)
                self.switched_display_mode = False
            else:
                self.scroll_percent = imgui.get_scroll_y() / scroll_max_y

    def draw_games_list(self):
        # Hack: custom toggles in table header right click menu by adding tiny empty "ghost" columns and hiding them
        # by starting the table render before the content region.
        ghost_column_size = (imgui.style.frame_padding.x + imgui.style.cell_padding.x * 2)
        offset = ghost_column_size * self.ghost_columns_enabled_count
        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() - offset)
        if imgui.begin_table(
            "###game_list",
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
            self.sort_games(imgui.table_get_sort_specs())

            # Column headers
            imgui.table_next_row(imgui.TABLE_ROW_HEADERS)
            for column in cols.items:
                imgui.table_set_column_index(column.index)
                imgui.table_header(column.header)

            # Loop rows
            self.sync_scroll()
            frame_height = imgui.get_frame_height()
            notes_width = None
            for game_i, id in enumerate(self.sorted_games_ids):
                game = globals.games[id]
                imgui.table_next_row()
                imgui.table_set_column_index(cols.separator.index)
                # Skip if outside view
                if not imgui.is_rect_visible(imgui.io.display_size.x, frame_height):
                    imgui.dummy(0, frame_height)
                    continue
                # Base row height with a buttom to align the following text calls to center vertically
                imgui.button(f"###{game.id}_id", width=imgui.FLOAT_MIN)
                # Loop columns
                for column in cols.items:
                    if not column.enabled or column.ghost:
                        continue
                    imgui.table_set_column_index(column.index)
                    match column.index:
                        case cols.play_button.index:
                            self.draw_game_play_button(game, label=icons.play)
                        case cols.type.index:
                            self.draw_type_widget(game.type, align=True)
                        case cols.name.index:
                            if globals.settings.show_remove_btn:
                                self.draw_game_remove_button(game, label=icons.trash_can_outline)
                                imgui.same_line()
                            if game.installed and game.installed != game.version:
                                self.draw_game_update_icon(game)
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
                                self.draw_game_status_widget(game)
                            if cols.version.enabled:
                                imgui.same_line()
                                imgui.text_disabled(self.get_game_version_text(game))
                        case cols.developer.index:
                            imgui.text(game.developer or "Unknown")
                        case cols.last_updated.index:
                            imgui.text(game.last_updated.display or "Unknown")
                        case cols.last_played.index:
                            imgui.text(game.last_played.display or "Never")
                        case cols.added_on.index:
                            imgui.text(game.added_on.display)
                        case cols.played.index:
                            self.draw_game_played_checkbox(game)
                        case cols.installed.index:
                            self.draw_game_installed_checkbox(game)
                        case cols.rating.index:
                            self.draw_game_rating_widget(game)
                        case cols.notes.index:
                            if notes_width is None:
                                notes_width = imgui.get_content_region_available_width() - 2 * imgui.style.item_spacing.x
                            self.draw_game_notes_widget(game, multiline=False, width=notes_width)
                        case cols.open_thread.index:
                            self.draw_game_open_thread_button(game, label=icons.open_in_new)
                        case cols.copy_link.index:
                            self.draw_game_copy_link_button(game, label=icons.content_copy)
                        case cols.open_folder.index:
                            self.draw_game_open_folder_button(game, label=icons.folder_open_outline)
                        case cols.status_standalone.index:
                            self.draw_game_status_widget(game)
                        case cols.score.index:
                            imgui.text(f"{game.score:.1f}")
                # Row hitbox
                imgui.same_line()
                imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() - imgui.style.frame_padding.y)
                imgui.push_alpha(0.25)
                imgui.selectable(f"###{game.id}_hitbox", False, flags=imgui.SELECTABLE_SPAN_ALL_COLUMNS, height=frame_height)
                imgui.pop_alpha()
                self.handle_game_hitbox_events(game, game_i)

            imgui.end_table()

    def tick_list_columns(self):
        # Hack: get sort and column specs for list mode in grid and kanban mode
        pos = imgui.get_cursor_pos_y()
        if imgui.begin_table(
            "###game_list",
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
            self.sort_games(imgui.table_get_sort_specs())
            imgui.end_table()
        imgui.set_cursor_pos_y(pos)

    def get_game_cell_config(self):
        side_indent = imgui.style.item_spacing.x * 2
        checkboxes = cols.played.enabled + cols.installed.enabled
        buttons = cols.play_button.enabled + cols.open_folder.enabled + cols.open_thread.enabled + cols.copy_link.enabled
        action_items = checkboxes + buttons
        data_rows = cols.developer.enabled + cols.score.enabled + cols.last_updated.enabled + cols.last_played.enabled + cols.added_on.enabled + cols.rating.enabled + cols.notes.enabled
        bg_col = imgui.get_color_u32_rgba(*imgui.style.colors[imgui.COLOR_TABLE_ROW_BACKGROUND_ALT])

        min_width = (
            side_indent * 2 +  # Side indent * 2 sides
            max((
                imgui.style.item_spacing.x * action_items +  # Spacing * 6 action items
                imgui.style.frame_padding.x * 2 * buttons +  # Button padding * 2 sides * 4 buttons
                imgui.style.item_inner_spacing.x * checkboxes +  # Checkbox to label spacing * 2 checkboxes
                imgui.get_frame_height() * checkboxes +  # (Checkbox height = width) * 2 checkboxes
                imgui.calc_text_size(f"{icons.play} Play" * cols.play_button.enabled + f"{icons.folder_open_outline} Folder" * cols.open_folder.enabled + f"{icons.open_in_new} Thread" * cols.open_thread.enabled + f"{icons.content_copy} Link" * cols.copy_link.enabled + icons.flag_checkered * cols.played.enabled + icons.cloud_download * cols.installed.enabled).x  # Text
            ),
            (
                imgui.style.item_spacing.x * 2 +  # Between text * 2
                imgui.calc_text_size("Last Updated:00/00/0000").x  # Text
            ))
        )

        frame_height = imgui.get_frame_height()
        data_height = data_rows * imgui.get_text_line_height_with_spacing()
        badge_wrap = side_indent + imgui.get_text_line_height()
        dev_wrap = imgui.calc_text_size("Developer:").x + imgui.style.item_spacing.x * 2

        config = (side_indent, action_items, data_rows, bg_col, frame_height, data_height, badge_wrap, dev_wrap)
        return min_width, config

    def draw_game_cell(self, game: Game, game_i: int | None, draw_list, cell_width: float, img_height: float, config: tuple):
        (side_indent, action_items, data_rows, bg_col, frame_height, data_height, badge_wrap, dev_wrap) = config
        draw_list.channels_split(2)
        draw_list.channels_set_current(1)
        pos = imgui.get_cursor_pos()
        imgui.begin_group()
        # Image
        if game.image.missing:
            text = "Image missing!"
            text_size = imgui.calc_text_size(text)
            showed_img = imgui.is_rect_visible(cell_width, img_height)
            if text_size.x < cell_width:
                imgui.set_cursor_pos((pos.x + (cell_width - text_size.x) / 2, pos.y + img_height / 2))
                self.draw_hover_text(
                    text=text,
                    hover_text="This thread does not seem to have an image!" if game.image_url == "-" else "Run a full refresh to try downloading it again!"
                )
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
            crop = game.image.crop_to_ratio(globals.settings.grid_image_ratio, fit=globals.settings.fit_images)
            showed_img = game.image.render(cell_width, img_height, *crop, rounding=globals.settings.style_corner_radius, flags=imgui.DRAW_ROUND_CORNERS_TOP)
        # Alignments
        imgui.indent(side_indent)
        imgui.push_text_wrap_pos(pos.x + cell_width - side_indent)
        imgui.spacing()
        # Remove button
        if showed_img and globals.settings.show_remove_btn:
            old_pos = imgui.get_cursor_pos()
            imgui.set_cursor_pos((pos.x + imgui.style.item_spacing.x, pos.y + imgui.style.item_spacing.y))
            self.draw_game_remove_button(game, label=icons.trash_can_outline)
            imgui.set_cursor_pos(old_pos)
        # Type
        if showed_img and cols.type.enabled:
            old_pos = imgui.get_cursor_pos()
            imgui.set_cursor_pos((pos.x + imgui.style.item_spacing.x, pos.y + img_height - frame_height))
            self.draw_type_widget(game.type, wide=False)
            imgui.set_cursor_pos(old_pos)
        # Name
        if game.installed and game.installed != game.version:
            self.draw_game_update_icon(game)
            imgui.same_line()
        self.draw_game_name_text(game)
        if game.notes:
            imgui.same_line()
            if imgui.get_content_region_available_width() < badge_wrap:
                imgui.dummy(0, 0)
            imgui.text_colored(icons.draw_pen, 0.85, 0.20, 0.85)
        if game.labels:
            imgui.same_line()
            self.draw_game_labels_widget(game, small=True, align=True)
        if cols.version.enabled:
            imgui.text_disabled(self.get_game_version_text(game))
        if (cols.status.enabled or cols.status_standalone.enabled) and game.status is not Status.Normal:
            imgui.same_line()
            if imgui.get_content_region_available_width() < badge_wrap:
                imgui.dummy(0, 0)
            self.draw_game_status_widget(game)
        if action_items:
            if imgui.is_rect_visible(cell_width, frame_height):
                # Play Button
                did_newline = False
                if cols.play_button.enabled:
                    if did_newline:
                        imgui.same_line()
                    self.draw_game_play_button(game, label=f"{icons.play} Play")
                    did_newline = True
                # Open Folder
                if cols.open_folder.enabled:
                    if did_newline:
                        imgui.same_line()
                    self.draw_game_open_folder_button(game, label=f"{icons.folder_open_outline} Folder")
                    did_newline = True
                # Open Thread
                if cols.open_thread.enabled:
                    if did_newline:
                        imgui.same_line()
                    self.draw_game_open_thread_button(game, label=f"{icons.open_in_new} Thread")
                    did_newline = True
                # Copy Link
                if cols.copy_link.enabled:
                    if did_newline:
                        imgui.same_line()
                    self.draw_game_copy_link_button(game, label=f"{icons.content_copy} Link")
                    did_newline = True
                # Played
                if cols.played.enabled:
                    if did_newline:
                        imgui.same_line()
                    self.draw_game_played_checkbox(game, label=icons.flag_checkered)
                    did_newline = True
                # Installed
                if cols.installed.enabled:
                    if did_newline:
                        imgui.same_line()
                    self.draw_game_installed_checkbox(game, label=icons.cloud_download)
                    did_newline = True
            else:
                # Skip if outside view
                imgui.dummy(0, frame_height)
        if data_rows:
            if imgui.is_rect_visible(cell_width, data_height):
                # Developer
                if cols.developer.enabled:
                    imgui.text_disabled("Developer:")
                    imgui.same_line()
                    utils.wrap_text(game.developer or "Unknown", width=cell_width - 2 * side_indent, offset=dev_wrap)
                # Forum Score
                if cols.score.enabled:
                    imgui.text_disabled("Forum Score:")
                    imgui.same_line()
                    imgui.text(f"{game.score:.1f}/5")
                # Last Updated
                if cols.last_updated.enabled:
                    imgui.text_disabled("Last Updated:")
                    imgui.same_line()
                    imgui.text(game.last_updated.display or "Unknown")
                # Last Played
                if cols.last_played.enabled:
                    imgui.text_disabled("Last Played:")
                    imgui.same_line()
                    imgui.text(game.last_played.display or "Never")
                # Added On
                if cols.added_on.enabled:
                    imgui.text_disabled("Added On:")
                    imgui.same_line()
                    imgui.text(game.added_on.display)
                # Rating
                if cols.rating.enabled:
                    imgui.text_disabled("Rating:")
                    imgui.same_line()
                    self.draw_game_rating_widget(game)
                # Notes
                if cols.notes.enabled:
                    self.draw_game_notes_widget(game, multiline=False, width=cell_width - 2 * side_indent)
            else:
                # Skip if outside view
                imgui.dummy(0, data_height)
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
            imgui.invisible_button(f"###{game.id}_kanban_hitbox", cell_width, cell_height)
            self.handle_game_hitbox_events(game, game_i)
            pos = imgui.get_item_rect_min()
            pos2 = imgui.get_item_rect_max()
            draw_list.add_rect_filled(*pos, *pos2, bg_col, rounding=globals.settings.style_corner_radius, flags=imgui.DRAW_ROUND_CORNERS_ALL)
        else:
            imgui.dummy(cell_width, cell_height)
        draw_list.channels_merge()

    def draw_games_grid(self):
        # Configure table
        self.tick_list_columns()
        min_cell_width, cell_config = self.get_game_cell_config()
        padding = self.scaled(8)
        avail = imgui.get_content_region_available_width()
        column_count = globals.settings.grid_columns
        while column_count > 1 and (cell_width := (avail - padding * 2 * column_count) / column_count) < min_cell_width:
            column_count -= 1
        img_height = cell_width / globals.settings.grid_image_ratio
        imgui.push_style_var(imgui.STYLE_CELL_PADDING, (padding, padding))
        if imgui.begin_table(
            "###game_grid",
            column=column_count,
            flags=self.game_grid_table_flags,
            outer_size_height=-imgui.get_frame_height_with_spacing()  # Bottombar
        ):
            # Setup
            for i in range(column_count):
                imgui.table_setup_column(f"###game_grid_{i}", imgui.TABLE_COLUMN_WIDTH_STRETCH)

            # Loop cells
            self.sync_scroll()
            draw_list = imgui.get_window_draw_list()
            for game_i, id in enumerate(self.sorted_games_ids):
                game = globals.games[id]
                imgui.table_next_column()
                self.draw_game_cell(game, game_i, draw_list, cell_width, img_height, cell_config)

            imgui.end_table()
        imgui.pop_style_var()

    def draw_games_kanban(self):
        # Configure table
        self.tick_list_columns()
        cell_width, cell_config = self.get_game_cell_config()
        column_width = cell_width + imgui.style.scrollbar_size
        padding = self.scaled(4)
        imgui.push_style_var(imgui.STYLE_CELL_PADDING, (padding, padding))
        column_count = len(Label.instances) + 1
        img_height = cell_width / globals.settings.grid_image_ratio
        if imgui.begin_table(
            "###game_kanban",
            column=column_count,
            flags=self.game_kanban_table_flags,
            inner_width=(column_width * column_count) + (padding * 2 * column_count),
            outer_size_width=-imgui.style.scrollbar_size - padding,
            outer_size_height=-imgui.get_frame_height_with_spacing()  # Bottombar
        ):
            # Setup columns
            not_labelled = len(Label.instances)
            for label in Label.instances:
                imgui.table_setup_column(f"{label.name}###game_kanban_{label.id}", imgui.TABLE_COLUMN_WIDTH_STRETCH)
            imgui.table_setup_column(f"Not Labelled###game_kanban_-1", imgui.TABLE_COLUMN_WIDTH_STRETCH)

            # Column headers
            imgui.table_setup_scroll_freeze(0, 1)  # Sticky column headers
            imgui.table_next_row(imgui.TABLE_ROW_HEADERS)
            for label_i, label in enumerate(Label.instances):
                imgui.table_set_column_index(label_i)
                imgui.table_header(label.name)
            imgui.table_set_column_index(not_labelled)
            imgui.table_header("Not Labelled")

            # Loop cells
            for label_i, label in (*enumerate(Label.instances), (not_labelled, None)):
                imgui.table_next_column()
                imgui.begin_child(f"###game_kanban_{label_i}", width=column_width, height=-padding)
                draw_list = imgui.get_window_draw_list()
                for id in self.sorted_games_ids:
                    game = globals.games[id]
                    if label_i == not_labelled:
                        if game.labels:
                            continue
                    elif label not in game.labels:
                        continue
                    imgui.spacing()
                    self.draw_game_cell(game, None, draw_list, cell_width, img_height, cell_config)
                imgui.end_child()

            imgui.end_table()
        imgui.pop_style_var()

    def draw_bottombar(self):
        new_display_mode = None

        for display_mode, mode_icon in (
            (DisplayMode.list,   icons.view_agenda_outline),
            (DisplayMode.grid,   icons.view_grid_outline),
            (DisplayMode.kanban, icons.view_week_outline)
        ):
            if globals.settings.display_mode is display_mode:
                imgui.push_style_color(imgui.COLOR_BUTTON, *imgui.style.colors[imgui.COLOR_BUTTON_HOVERED])
            if imgui.button(mode_icon):
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
        if not globals.popup_stack and not any_active_old and (self.input_chars or any(imgui.io.keys_down)):
            if imgui.is_key_pressed(glfw.KEY_BACKSPACE):
                self.add_box_text = self.add_box_text[:-1]
            if self.input_chars:
                self.repeat_chars = True
            imgui.set_keyboard_focus_here()
            any_active = True
        activated, value = imgui.input_text_with_hint("###bottombar", "Start typing to filter the list, press enter to add a game (thread link / search term)", self.add_box_text, flags=imgui.INPUT_TEXT_ENTER_RETURNS_TRUE)
        changed = value != self.add_box_text
        self.add_box_text = value
        activated = bool(activated and self.add_box_text)
        any_active = any_active or imgui.is_any_item_active()
        if any_active_old != any_active and imgui.is_key_pressed(glfw.KEY_ESCAPE):
            # Changed active state, and escape is pressed, so clear textbox
            self.add_box_text = ""
            changed = True
        def setter_extra(_=None):
            self.add_box_valid = len(utils.extract_thread_matches(self.add_box_text)) > 0
            self.require_sort = True
        if changed:
            setter_extra()
        if imgui.begin_popup_context_item(f"###bottombar_context"):
            # Right click = more options context menu
            utils.text_context(self, "add_box_text", setter_extra, no_icons=True)
            imgui.separator()
            if imgui.selectable(f"{icons.information_outline} More info", False)[0]:
                utils.push_popup(
                    msgbox.msgbox, "About the bottom bar",
                    "This is the filter/add bar. By typing inside it you can search your game list.\n"
                    "Pressing enter will search F95Zone for a matching thread and ask if you wish to\n"
                    "add it to your list.\n\n"
                    "When you instead paste a link to a F95Zone thread, the \"Add!\" button will show\n"
                    "up, allowing you to add that thread to your list. When a link is detected you\n"
                    "can also press enter on your keyboard to trigger the \"Add!\" button.",
                    MsgBox.info
                )
            imgui.end_popup()
        if self.add_box_valid:
            imgui.same_line()
            if imgui.button("Add!") or activated:
                async_thread.run(callbacks.add_games(*utils.extract_thread_matches(self.add_box_text)))
                self.add_box_text = ""
                self.add_box_valid = False
                self.require_sort = True
        elif activated:
            async def _search_and_add(query: str):
                if not await api.assert_login():
                    return
                results = await api.quick_search(query)
                if not results:
                    utils.push_popup(msgbox.msgbox, "No results", f"The search query \"{query}\" returned no results.", MsgBox.warn)
                    return
                def popup_content():
                    imgui.text("Click one of the results to add it, click Ok when you're finished.\n\n")
                    for result in results:
                        if result.id in globals.games:
                            imgui.push_disabled()
                        clicked = imgui.selectable(f"{result.title}###result_{result.id}", False, flags=imgui.SELECTABLE_DONT_CLOSE_POPUPS)[0]
                        if result.id in globals.games:
                            imgui.pop_disabled()
                        if clicked:
                            async_thread.run(callbacks.add_games(result))
                utils.push_popup(utils.popup, "Search results", popup_content, buttons=True, closable=True, outside=False)
            async_thread.run(_search_and_add(self.add_box_text))
            self.add_box_text = ""
            self.add_box_valid = False
            self.require_sort = True

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
                imgui.table_setup_column(f"###settings_{name}_left", imgui.TABLE_COLUMN_WIDTH_STRETCH)
                imgui.table_setup_column(f"###settings_{name}_right", imgui.TABLE_COLUMN_WIDTH_FIXED)
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
                game.image.render(width, height, *crop, rounding=globals.settings.style_corner_radius)
        else:
            # Normal button
            if imgui.button("Refresh!", width=width, height=height):
                utils.start_refresh_task(api.refresh())
            if imgui.begin_popup_context_item(f"###refresh_context"):
                # Right click = more options context menu
                if imgui.selectable(f"{icons.bell_badge_outline} Check notifs", False)[0]:
                    utils.start_refresh_task(api.check_notifs(login=True))
                if imgui.selectable(f"{icons.reload_alert} Full Refresh", False)[0]:
                    utils.start_refresh_task(api.refresh(full=True))
                imgui.separator()
                if imgui.selectable(f"{icons.information_outline} More info", False)[0]:
                    utils.push_popup(
                        msgbox.msgbox, "About refreshing",
                        "Refreshing is the process by which F95Checker goes through your games and checks\n"
                        "if they have received updates. To keep it fast and smooth this is done by detecting\n"
                        "changes in the title of the thread (more precisely it checks for redirects, so it doesn't\n"
                        "need to fetch the whole page).\n\n"
                        "This means that sometimes it might not be able to pick up some subtle changes and small\n"
                        "updates. To fix this it also runs a full refresh every week or so (each game has its own\n"
                        "timer).\n\n"
                        "So a full recheck of a game will happen every time the title changes, or every 7 days.\n"
                        "You can force full rechecks for single games or for the whole list with the right click\n"
                        "menu on the game and on the refresh button.",
                        MsgBox.info
                    )
                imgui.end_popup()

        imgui.begin_child("Settings")

        if draw_settings_section("Filter", collapsible=False):
            draw_settings_label(f"Total games count: {len(globals.games)}")
            imgui.text("")
            imgui.spacing()

            if len(self.filters) > 0 or self.add_box_text:
                draw_settings_label(f"Filtered games count: {len(self.sorted_games_ids)}")
                imgui.text("")
                imgui.spacing()

            draw_settings_label("Add filter:")
            changed, value = imgui.combo("###add_filter", 0, FilterMode._member_names_)
            if changed and value > 0:
                flt = Filter(FilterMode(value + 1))
                match flt.mode.value:
                    case FilterMode.Exe_State.value:
                        flt.match = ExeState[ExeState._member_names_[0]]
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
                self.require_sort = True

            for flt in self.filters:
                imgui.spacing()
                imgui.spacing()
                draw_settings_label(f"Filter by {flt.mode.name}:")
                if imgui.button(f"Remove###filter_{flt.id}_remove", width=right_width):
                    for i, search in enumerate(self.filters):
                        if search.id == flt.id:
                            self.filters.pop(i)
                    self.require_sort = True

                match flt.mode.value:
                    case FilterMode.Exe_State.value:
                        draw_settings_label("Executable state:")
                        changed, value = imgui.combo(f"###filter_{flt.id}_value", flt.match._index_, ExeState._member_names_)
                        if changed:
                            flt.match = ExeState[ExeState._member_names_[value]]
                            self.require_sort = True
                    case FilterMode.Installed.value:
                        draw_settings_label("Include outdated:")
                        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                        changed, value = imgui.checkbox(f"###filter_{flt.id}_value", flt.match)
                        if changed:
                            flt.match = value
                            self.require_sort = True
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
                                        self.require_sort = True
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
                            self.require_sort = True
                        imgui.spacing()
                    case FilterMode.Score.value:
                        draw_settings_label("Score value:")
                        changed, value = imgui.drag_float(f"###filter_{flt.id}_value", flt.match, change_speed=0.01, min_value=0, max_value=5, format="%.1f/5")
                        if changed:
                            flt.match = value
                            self.require_sort = True
                    case FilterMode.Status.value:
                        draw_settings_label("Status value:")
                        changed, value = imgui.combo(f"###filter_{flt.id}_value", flt.match._index_, Status._member_names_)
                        if changed:
                            flt.match = Status[Status._member_names_[value]]
                            self.require_sort = True
                    case FilterMode.Tag.value:
                        draw_settings_label("Tag value:")
                        if imgui.begin_combo(f"###filter_{flt.id}_value", flt.match.name):
                            for tag in Tag:
                                selected = tag is flt.match
                                pos = imgui.get_cursor_pos()
                                if imgui.selectable(f"###filter_{flt.id}_value_{tag.value}", selected)[0]:
                                    flt.match = tag
                                    self.require_sort = True
                                if selected:
                                    imgui.set_item_default_focus()
                                imgui.set_cursor_pos(pos)
                                self.draw_tag_widget(tag)
                            imgui.end_combo()
                    case FilterMode.Type.value:
                        draw_settings_label("Type value:")
                        if imgui.begin_combo(f"###filter_{flt.id}_value", flt.match.name):
                            for type in Type:
                                selected = type is flt.match
                                pos = imgui.get_cursor_pos()
                                if imgui.selectable(f"###filter_{flt.id}_value_{type.value}", selected)[0]:
                                    flt.match = type
                                    self.require_sort = True
                                if selected:
                                    imgui.set_item_default_focus()
                                imgui.set_cursor_pos(pos)
                                self.draw_type_widget(type)
                            imgui.end_combo()

                draw_settings_label("Invert filter:")
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                changed, value = imgui.checkbox(f"###filter_{flt.id}_invert", flt.invert)
                if changed:
                    flt.invert = value
                    self.require_sort = True

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

            if set.browser.unset:
                imgui.push_disabled()

            if set.browser.is_custom:
                draw_settings_label("Custom browser:")
                if imgui.button("Configure", width=right_width):
                    def popup_content():
                        imgui.text("Executable: ")
                        imgui.same_line()
                        pos = imgui.get_cursor_pos_x()
                        changed, set.browser_custom_executable = imgui.input_text("###browser_custom_executable", set.browser_custom_executable)
                        setter_extra = lambda _=None: async_thread.run(db.update_settings("browser_custom_executable"))
                        if changed:
                            setter_extra()
                        if imgui.begin_popup_context_item(f"###browser_custom_executable_context"):
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
                            utils.push_popup(filepicker.FilePicker(title="Select or drop browser executable", start_dir=set.browser_custom_executable, callback=callback).tick)
                        imgui.text("Arguments: ")
                        imgui.same_line()
                        imgui.set_cursor_pos_x(pos)
                        imgui.set_next_item_width(args_width)
                        changed, set.browser_custom_arguments = imgui.input_text("###browser_custom_arguments", set.browser_custom_arguments)
                        setter_extra = lambda _=None: async_thread.run(db.update_settings("browser_custom_arguments"))
                        if changed:
                            setter_extra()
                        if imgui.begin_popup_context_item(f"###browser_custom_arguments_context"):
                            utils.text_context(set, "browser_custom_arguments", setter_extra, no_icons=True)
                            imgui.end_popup()
                    utils.push_popup(utils.popup, "Configure custom browser", popup_content, buttons=True, closable=True, outside=False)
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

            if set.browser.unset:
                imgui.pop_disabled()

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Images"):
            draw_settings_label(
                "Fit images:",
                "Fit images instead of cropping. When cropping the images fill all the space they have available, cutting "
                "off the sides a bit. When fitting the images you see the whole image but it has some empty space at the sides."
            )
            draw_settings_checkbox("fit_images")

            draw_settings_label(
                "Keep game image:",
                "When a game is updated and the header image changes, F95Checker downloads it again replacing the old one. This "
                "setting makes it so the old image is kept and no new image is downloaded. This is useful in case you want "
                f"to have custom images for your games (you can edit the images manually at {globals.data_path / 'images'})."
            )
            draw_settings_checkbox("update_keep_image")

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
            changed, value = imgui.drag_int("###zoom_area", set.zoom_area, change_speed=0.1, min_value=1, max_value=200, format="%d%%")
            set.zoom_area = min(max(value, 1), 200)
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

            draw_settings_label(
                "Grid ratio:",
                "The aspect ratio to use for images in grid view. This is width:height, AKA how many times wider the image "
                "is compared to its height. Default is 3:1."
            )
            changed, value = imgui.drag_float("###grid_image_ratio", set.grid_image_ratio, change_speed=0.02, min_value=0.5, max_value=5, format="%.1f:1")
            set.grid_image_ratio = min(max(value, 0.5), 5)
            if changed:
                async_thread.run(db.update_settings("grid_image_ratio"))

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
                "Time format:",
                "The format expression to use for full timestamps. Uses the strftime specification. Default is '%d/%m/%Y %H:%M'."
            )
            changed, set.timestamp_format = imgui.input_text("###timestamp_format", set.timestamp_format)
            def setter_extra(_=None):
                async_thread.run(db.update_settings("timestamp_format"))
                for timestamp in Timestamp.instances:
                    timestamp.update()
            if changed:
                setter_extra()
            if imgui.begin_popup_context_item(f"###timestamp_format_context"):
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
                "The format expression to use for short datestamps. Uses the strftime specification. Default is '%d/%m/%Y'."
            )
            changed, set.datestamp_format = imgui.input_text("###datestamp_format", set.datestamp_format)
            def setter_extra(_=None):
                async_thread.run(db.update_settings("datestamp_format"))
                for datestamp in Datestamp.instances:
                    datestamp.update()
            if changed:
                setter_extra()
            if imgui.begin_popup_context_item(f"###datestamp_format_context"):
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
            buttons_offset = right_width - (2 * frame_height + imgui.style.item_spacing.x)
            for label in Label.instances:
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.set_next_item_width(imgui.get_content_region_available_width() + buttons_offset + imgui.style.cell_padding.x)
                changed, label.name = imgui.input_text_with_hint(f"###label_name_{label.id}", "Label name", label.name)
                setter_extra = lambda _=None: async_thread.run(db.update_label(label, "name"))
                if changed:
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
                if imgui.button(f"{icons.trash_can_outline}###label_remove_{label.id}", width=frame_height):
                    async_thread.run(db.remove_label(label))

            draw_settings_label("New label:")
            if imgui.button("Add", width=right_width):
                async_thread.run(db.add_label())

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
                    thread_links = type("_", (), dict(_=""))()
                    def popup_content():
                        nonlocal thread_links
                        imgui.text("Any kind of F95Zone thread link, preferably 1 per line. Will be parsed and cleaned,\nso don't worry about tidiness and paste like it's anarchy!")
                        _, thread_links._ = imgui.input_text_multiline(
                            f"###import_links",
                            value=thread_links._,
                            width=min(self.scaled(600), imgui.io.display_size.x * 0.6),
                            height=imgui.io.display_size.y * 0.6
                        )
                        if imgui.begin_popup_context_item(f"###import_links_context"):
                            utils.text_context(thread_links, "_", no_icons=True)
                            imgui.end_popup()
                    buttons={
                        f"{icons.check} Import": lambda: async_thread.run(callbacks.add_games(*utils.extract_thread_matches(thread_links._))),
                        f"{icons.cancel} Cancel": None
                    }
                    utils.push_popup(utils.popup, "Import thread links", popup_content, buttons, closable=True, outside=False)
                if imgui.button("F95 bookmarks", width=-offset):
                    utils.start_refresh_task(api.import_f95_bookmarks())
                if imgui.button("F95 watched threads", width=-offset):
                    utils.start_refresh_task(api.import_f95_watched_threads())
                if imgui.button("Browser bookmarks", width=-offset):
                    def callback(selected):
                        if selected:
                            async_thread.run(api.import_browser_bookmarks(selected))
                    buttons={
                        f"{icons.check} Ok": lambda: utils.push_popup(filepicker.FilePicker("Select or drop bookmark file", callback=callback).tick),
                        f"{icons.cancel} Cancel": None
                    }
                    utils.push_popup(msgbox.msgbox, "Bookmark file", "F95Checker can import your browser bookmarks using an exported bookmark HTML.\nExporting such a file may vary between browsers, but generally speaking you need to:\n - Open your browser's bookmark manager\n - Find an import / export section, menu or dropdown\n - Click export as HTML\n - Save the file in some place you can find easily\n\nOnce you have done this click Ok and select this file.", MsgBox.info, buttons)
                file_hover = imgui.is_item_hovered()
                if imgui.button("URL Shortcut file", width=-offset):
                    def callback(selected):
                        if selected:
                            async_thread.run(api.import_url_shortcut(selected))
                    utils.push_popup(filepicker.FilePicker("Select or drop shortcut file", callback=callback).tick),
                file_hover = file_hover or imgui.is_item_hovered()
                if file_hover:
                    self.draw_hover_text("You can also drag and drop .html and .url files into the window for this!", text=None, force=True)
                imgui.tree_pop()
            if imgui.tree_node("Export", flags=imgui.TREE_NODE_SPAN_AVAILABLE_WIDTH):
                offset = imgui.get_cursor_pos_x() - pos.x
                if imgui.button("Thread links", width=-offset):
                    thread_links = type("_", (), dict(_="\n".join(game.url for game in globals.games.values())))()
                    def popup_content():
                        imgui.input_text_multiline(
                            f"###export_links",
                            value=thread_links._,
                            width=min(self.scaled(600), imgui.io.display_size.x * 0.6),
                            height=imgui.io.display_size.y * 0.6,
                            flags=imgui.INPUT_TEXT_READ_ONLY
                        )
                        if imgui.begin_popup_context_item(f"###export_links_context"):
                            utils.text_context(thread_links, "_", editable=False)
                            imgui.end_popup()
                    utils.push_popup(utils.popup, "Export thread links", popup_content, buttons=True, closable=True, outside=False)
                imgui.tree_pop()
            if imgui.tree_node("Clear", flags=imgui.TREE_NODE_SPAN_AVAILABLE_WIDTH):
                offset = imgui.get_cursor_pos_x() - pos.x
                if imgui.button("All cookies", width=-offset):
                    buttons = {
                        f"{icons.check} Yes": lambda: async_thread.run(db.update_cookies({})),
                        f"{icons.cancel} No": None
                    }
                    utils.push_popup(msgbox.msgbox, "Clear cookies", "Are you sure you want to clear your session cookies?\nThis will invalidate your login session, but might help\nif you are having issues.", MsgBox.warn, buttons)
                imgui.tree_pop()
            imgui.end_group()
            imgui.spacing()

            draw_settings_label(
                "Ask path on add:",
                "When this is enabled you will be asked to select a game executable right after adding the game to F95Checker."
            )
            draw_settings_checkbox("select_executable_after_add")

            draw_settings_label(
                "Set exe dir:",
                "This setting indicates what folder will be shown by default when selecting the executable for a game. This can be useful if you keep all "
                f"your games in the same folder (as you should).\n\nCurrent value: {set.default_exe_dir or 'Unset'}"
            )
            if imgui.button("Choose", width=right_width):
                def select_callback(selected):
                    set.default_exe_dir = selected or ""
                    async_thread.run(db.update_settings("default_exe_dir"))
                utils.push_popup(filepicker.DirPicker("Selecte or drop default exe dir", start_dir=set.default_exe_dir, callback=select_callback).tick)

            draw_settings_label("Show remove button:")
            draw_settings_checkbox("show_remove_btn")

            draw_settings_label("Confirm when removing:")
            draw_settings_checkbox("confirm_on_remove")

            draw_settings_label(
                "RPC enabled:",
                f"The RPC allows other programs on your pc to interact with F95Checker via the xmlrpc on localhost:{globals.rpc_port}. "
                "Essentially this is what makes the web browser extension work. Disable this if you are having issues with the RPC, "
                "but do note that doing so will prevent the extension from working at all."
            )
            if draw_settings_checkbox("rpc_enabled"):
                if set.rpc_enabled:
                    rpc_thread.start()
                else:
                    rpc_thread.stop()

            imgui.end_table()
            imgui.spacing()

        if draw_settings_section("Refresh"):
            draw_settings_label("Check alerts and inbox:")
            draw_settings_checkbox("check_notifs")

            draw_settings_label("Refresh if completed:")
            draw_settings_checkbox("refresh_completed_games")

            draw_settings_label(
                "Workers:",
                "Each game that needs to be checked requires that a connection to F95Zone happens. Each worker can handle 1 "
                "connection at a time. Having more workers means more connections happen simultaneously, but having too many "
                "will freeze the program. In most cases 20 workers is a good compromise."
            )
            changed, value = imgui.drag_int("###refresh_workers", set.refresh_workers, change_speed=0.5, min_value=1, max_value=100)
            set.refresh_workers = min(max(value, 1), 100)
            if changed:
                async_thread.run(db.update_settings("refresh_workers"))

            draw_settings_label(
                "Timeout:",
                "To check for updates for a game F95Checker sends a web request to F95Zone. However this can sometimes go "
                "wrong. The timeout is the maximum amount of seconds that a request can try to connect for before it fails. "
                "A timeout 10-30 seconds is most typical."
            )
            changed, value = imgui.drag_int("###request_timeout", set.request_timeout, change_speed=0.6, min_value=1, max_value=120, format="%d sec")
            set.request_timeout = min(max(value, 1), 120)
            if changed:
                async_thread.run(db.update_settings("request_timeout"))

            draw_settings_label(
                "Retries:",
                "While refreshing, a lot of connections are made to F95Zone very quickly, so some might fail. This setting "
                "determines how many times a failed connection will be reattempted before failing completely. However these "
                "connection errors are often caused by misconfigured workers and timeout values, so try to tinker with those "
                "instead of the retries value. This setting should only be used if you know your connection is very unreliable. "
                "Otherwise 2 max retries are usually fine for stable connections."
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

            draw_settings_label(
                "Use parser processes:",
                "Parsing the game threads is an intensive task so when a full recheck is running the interface can stutter a lot. When "
                "this setting is enabled the thread parsing will be offloaded to dedicated processes that might be (very slightly) slower "
                "and less stable but that allow the interface to remain fully responsive. It is recommended you keep this enabled unless it "
                "is causing problems."
            )
            draw_settings_checkbox("use_parser_processes")

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
        self.refresh_icon = QtGui.QIcon(str(globals.self_path / 'resources/icons/refreshing.png'))
        self.msg_queue: list[TrayMsg] = []
        super().__init__(self.idle_icon)

        self.watermark = QtGui.QAction(f"F95Checker {globals.version_name}")
        self.watermark.triggered.connect(lambda *_: callbacks.open_webpage(globals.tool_page))

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
        if utils.is_refreshing():
            self.setIcon(self.refresh_icon)
        elif self.main_gui.bg_mode_paused and self.main_gui.hidden:
            self.setIcon(self.paused_icon)
        else:
            self.setIcon(self.idle_icon)

    def showing_menu(self, *_):
        self.menu_open = True

    def hiding_menu(self, *_):
        self.menu_open = False

    def update_menu(self, *_):
        if self.main_gui.hidden:
            if self.main_gui.bg_mode_paused:
                next_refresh = "Paused"
            elif self.main_gui.bg_mode_timer or self.main_gui.bg_mode_notifs_timer:
                next_refresh = dt.datetime.fromtimestamp(min(self.main_gui.bg_mode_timer or globals.settings.bg_refresh_interval, self.main_gui.bg_mode_notifs_timer or globals.settings.bg_notifs_interval)).strftime("%H:%M")
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
