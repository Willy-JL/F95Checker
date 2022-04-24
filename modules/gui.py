from imgui.integrations.glfw import GlfwRenderer
from PyQt6 import QtCore, QtGui, QtWidgets
from PIL import Image, ImageSequence
import OpenGL.GL as gl
import configparser
import platform
import pathlib
import typing
import OpenGL
import numpy
import imgui
import glfw
import sys
import os

from modules import async_thread
from modules import sync_thread
from modules.structs import *
from modules import globals
from modules import db

io: imgui.core._IO = None
style: imgui.core.GuiStyle = None


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


class ImGuiImage:
    def __init__(self, path: str | pathlib.Path, glob: str = ""):
        self.glob: str = glob
        self.frame_count: int = 1
        self.loaded: bool = False
        self.loading: bool = False
        self.applied: bool = False
        self.missing: bool = False
        self.animated: bool = False
        self.prev_time: float = 0.0
        self.current_frame: int = -1
        self.width, self.height = 1, 1
        self.frame_elapsed: float = 0.0
        self.frame_durations: list = []
        self.data: bytes | list[bytes] = None
        self._texture_id: numpy.uint32 = None
        self.path: pathlib.Path = pathlib.Path(path)

    def reset(self):
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture_id)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, 0, 0, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, numpy.empty(0))
        self.applied = False

    @staticmethod
    def get_rgba_pixels(image: Image.Image):
        if image.mode == "RGB":
            return image.tobytes("raw", "RGBX")
        else:
            if image.mode != "RGBA":
                image = image.convert("RGBA")
            return image.tobytes("raw", "RGBA")

    def set_missing(self):
        self.width, self.height = imgui.calc_text_size("Image missing!")
        self.missing = True
        self.loaded = True
        self.loading = False

    def reload(self):
        self.reset()
        path = self.path
        if self.glob:
            paths = list(path.glob(self.glob))
            if not paths:
                self.set_missing()
                return
            path = paths[0]
        if path.is_file():
            self.missing = False
        else:
            self.set_missing()
            return
        image = Image.open(path)
        self.width, self.height = image.size
        if hasattr(image, "n_frames") and image.n_frames > 1:
            self.animated = True
            self.frame_count = image.n_frames
            self.data = []
            for frame in ImageSequence.Iterator(image):
                self.data.append(self.get_rgba_pixels(frame))
                self.frame_durations.append(frame.info["duration"] / 1250)
        else:
            self.data = self.get_rgba_pixels(image)
        self.loaded = True
        self.loading = False

    def apply(self, data: bytes):
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, self.width, self.height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)

    @property
    def texture_id(self):
        if self._texture_id is None:
            self._texture_id = gl.glGenTextures(1)
        if not self.loaded:
            if not self.loading:
                self.loading = True
                sync_thread.enqueue(self.reload)
        elif not self.missing:
            if self.animated:
                if self.prev_time != (new_time := imgui.get_time()):
                    self.prev_time = new_time
                    self.frame_elapsed += io.delta_time
                if self.frame_elapsed > self.frame_durations[max(self.current_frame, 0)]:
                    self.frame_elapsed = 0
                    self.applied = False
                if not self.applied:
                    self.current_frame += 1
                    if self.current_frame == self.frame_count:
                        self.current_frame = 0
                    self.apply(self.data[self.current_frame])
                    self.applied = True
            elif not self.applied:
                self.apply(self.data)
                self.applied = True
        return self._texture_id

    def render(self, width, height, *args, **kwargs):
        if self.missing:
            imgui.text_disabled("Image missing!")
        else:
            if imgui.is_rect_visible(width, height):
                if (rounding := kwargs.pop("rounding", None)) is not None:
                    if rounding is True:
                        rounding = globals.settings.style_corner_radius
                    pos = imgui.get_cursor_screen_pos()
                    pos2 = (pos.x + width, pos.y + height)
                    draw_list = imgui.get_window_draw_list()
                    draw_list.add_image_rounded(self.texture_id, tuple(pos), pos2, *args, rounding=rounding, **kwargs)
                    imgui.dummy(width, height)
                else:
                    imgui.image(self.texture_id, width, height, *args, **kwargs)
            else:
                imgui.dummy(width, height)

    def crop_to_ratio(self, ratio: int | float):
        img_ratio = self.width / self.height
        if img_ratio >= ratio:
            crop_h = self.height
            crop_w = crop_h * ratio
            crop_x = (self.width - crop_w) / 2
            crop_y = 0
            left = crop_x / self.width
            top = 0
            right = (crop_x + crop_w) / self.width
            bottom = 1
        else:
            crop_w = self.width
            crop_h = crop_w / ratio
            crop_y = (self.height - crop_h) / 2
            crop_x = 0
            left = 0
            top = crop_y / self.height
            right = 1
            bottom = (crop_y + crop_h) / self.height
        return (left, top), (right, bottom)


def push_disabled(block_interaction: bool = True):
    if block_interaction:
        imgui.internal.push_item_flag(imgui.internal.ITEM_DISABLED, True)
    imgui.push_style_var(imgui.STYLE_ALPHA, style.alpha *  0.5)


def pop_disabled(block_interaction: bool = True):
    if block_interaction:
        imgui.internal.pop_item_flag()
    imgui.pop_style_var()


def center_next_window():
    size = io.display_size
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


class FilePicker:
    flags = (
        imgui.WINDOW_NO_MOVE |
        imgui.WINDOW_NO_RESIZE |
        imgui.WINDOW_NO_COLLAPSE |
        imgui.WINDOW_NO_SAVED_SETTINGS |
        imgui.WINDOW_ALWAYS_AUTO_RESIZE
    )

    def __init__(self, title: str = "File picker", start_dir: str | pathlib.Path = None, callback: typing.Callable = None, custom_flags: int = 0):
        self.current: int = 0
        self.title: str = title
        self.active: bool = True
        self.dir_icon: str = "󰉋"
        self.file_icon: str = "󰈔"
        self.selected: str = None
        self.items: list[str] = []
        self.dir: pathlib.Path = None
        self.callback: typing.Callable = callback
        self.flags: int = custom_flags or self.flags
        self.goto(start_dir or os.getcwd())

    def goto(self, dir: str | pathlib.Path):
        dir = pathlib.Path(dir)
        if dir.is_file():
            dir = dir.parent
        if dir.is_dir():
            self.dir = dir
        elif self.dir is None:
            self.dir = pathlib.Path(os.getcwd())
        self.dir = self.dir.absolute()
        self.current = -1
        self.refresh()

    def refresh(self):
        self.items.clear()
        try:
            items = list(self.dir.iterdir())
            if len(items) > 0:
                items.sort(key=lambda item: item.name.lower())
                items.sort(key=lambda item: item.is_dir(), reverse=True)
                for item in items:
                    self.items.append((self.dir_icon if item.is_dir() else self.file_icon) + "  " + item.name)
            else:
                self.items.append("This folder is empty!")
        except Exception:
            self.items.append("Cannot open this folder!")

    def draw(self):
        if not self.active:
            return
        # Setup popup
        if not imgui.is_popup_open(self.title):
            imgui.open_popup(self.title)
        center_next_window()
        if imgui.begin_popup_modal(self.title, True, flags=self.flags)[0]:
            close_popup_clicking_outside()
            size = io.display_size

            imgui.begin_group()
            # Up buttons
            if imgui.button("󰁞"):
                self.goto(self.dir.parent)
            # Location bar
            imgui.same_line()
            imgui.set_next_item_width(size.x * 0.7)
            confirmed, dir = imgui.input_text("##location_bar", str(self.dir), 9999999, flags=imgui.INPUT_TEXT_ENTER_RETURNS_TRUE)
            if confirmed:
                self.goto(dir)
            # Refresh button
            imgui.same_line()
            if imgui.button("󰑐"):
                self.refresh()
            imgui.end_group()
            width = imgui.get_item_rect_size().x

            # Main list
            if imgui.begin_child(f"##list_frame", width=width, height=size.y * 0.65) or True:
                imgui.set_next_item_width(width)
                clicked, value = imgui.listbox(f"##file_list", self.current, self.items, len(self.items))
                if value != -1:
                    self.current = min(max(value, 0), len(self.items) - 1)
                    item = self.items[self.current]
                    is_dir = item[0] == self.dir_icon
                    is_file = item[0] == self.file_icon
                    if imgui.is_item_hovered() and imgui.is_mouse_double_clicked():
                        if is_dir:
                            self.goto(self.dir / item[3:])
                        elif is_file:
                            self.selected = str(self.dir / item[3:])
                            imgui.close_current_popup()
                else:
                    is_dir = False
                    is_file = False
            imgui.end_child()

            # Cancel button
            if imgui.button("󰜺 Cancel"):
                imgui.close_current_popup()
            # Ok button
            imgui.same_line()
            if not is_file:
                push_disabled()
            if imgui.button("󰄬 Ok"):
                self.selected = str(self.dir / item[3:])
                imgui.close_current_popup()
            if not is_file:
                pop_disabled()
            # Selected text
            if is_file:
                imgui.same_line()
                imgui.text(f"Selected:  {item[3:]}")

            imgui.end_popup()
        if not imgui.is_popup_open(self.title):
            if self.callback:
                self.callback(self.selected)
            self.active = False


class MainGUI():
    def __init__(self):
        global io, style
        # Constants
        self.sidebar_size: int = 269
        self.game_list_column_count: int = 15
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
            imgui.TABLE_REORDERABLE |
            imgui.TABLE_ROW_BACKGROUND |
            imgui.TABLE_SIZING_FIXED_FIT |
            imgui.TABLE_NO_HOST_EXTEND_Y
        )
        self.ghost_columns_flags: int = (
            imgui.TABLE_COLUMN_NO_SORT |
            imgui.TABLE_COLUMN_NO_REORDER |
            imgui.TABLE_COLUMN_NO_HEADER_WIDTH
        )
        self.game_grid_table_flags: int = (
            imgui.TABLE_SCROLL_Y |
            imgui.TABLE_PAD_OUTER_X |
            imgui.TABLE_NO_HOST_EXTEND_Y |
            imgui.TABLE_SIZING_FIXED_SAME |
            imgui.TABLE_NO_SAVED_SETTINGS
        )
        self.game_grid_cell_flags = (
            imgui.WINDOW_NO_SCROLLBAR |
            imgui.WINDOW_NO_SCROLL_WITH_MOUSE
        )
        self.game_hitbox_drag_drop_flags = (
            imgui.DRAG_DROP_ACCEPT_PEEK_ONLY |
            imgui.DRAG_DROP_SOURCE_ALLOW_NULL_ID |
            imgui.DRAG_DROP_SOURCE_NO_PREVIEW_TOOLTIP
        )
        self.popup_flags: int = (
            imgui.WINDOW_NO_MOVE |
            imgui.WINDOW_NO_RESIZE |
            imgui.WINDOW_NO_COLLAPSE |
            imgui.WINDOW_NO_SAVED_SETTINGS |
            imgui.WINDOW_ALWAYS_AUTO_RESIZE
        )
        self.watermark_text: str = f"F95Checker v{globals.version} by WillyJL"

        # Variables
        self.visible: bool = True
        self.status_text: str = ""
        self.prev_size: tuple = (0, 0)
        self.hovered_game: Game = None
        self.require_sort: bool = True
        self.prev_manual_sort: int = 0
        self.size_mult: int | float = 0
        self.sorted_games_ids: list = []
        self.drew_filepicker: bool = False
        self.game_hitbox_click: bool = False
        self.current_info_popup_game: Game = None
        self.ghost_columns_enabled_count: int = 0
        self.current_filepicker: FilePicker = None

        # Setup Qt objects
        self.qt_app = QtWidgets.QApplication(sys.argv)
        self.qt_loop = QtCore.QEventLoop()
        self.tray = TrayIcon(self)

        # Setup ImGui
        imgui.create_context()
        io = imgui.get_io()
        self.ini_file_name = str(globals.data_path / "imgui.ini").encode()
        io.ini_file_name = self.ini_file_name  # Cannot set directly because reference gets lost due to a bug
        try:
            # Get window size
            imgui.load_ini_settings_from_disk(self.ini_file_name.decode("utf-8"))
            ini = imgui.save_ini_settings_to_memory()
            start = ini.find("[Window][F95Checker]")
            assert start != -1
            end = ini.find("\n\n", start)
            assert end != -1
            config = configparser.RawConfigParser()
            config.read_string(ini[start:end])
            size = tuple(int(x) for x in config.get("Window][F95Checker", "Size").split(","))
        except Exception:
            size = (1280, 720)

        # Setup GLFW window
        self.window = impl_glfw_init(*size, "F95Checker")
        icon_path = globals.self_path / "resources/icons/icon.png"
        self.icon_texture = ImGuiImage(icon_path)
        glfw.set_window_icon(self.window, 1, Image.open(icon_path))
        self.impl = GlfwRenderer(self.window)
        glfw.set_window_iconify_callback(self.window, self.minimize)
        self.refresh_fonts()

        # Load style configuration
        style = imgui.get_style()
        style.item_spacing = (style.item_spacing.y, style.item_spacing.y)
        style.colors[imgui.COLOR_MODAL_WINDOW_DIM_BACKGROUND] = (0, 0, 0, 0.5)
        style.scrollbar_size = 12
        style.window_rounding = style.frame_rounding = style.tab_rounding  = \
        style.child_rounding = style.grab_rounding = style.popup_rounding  = \
        style.scrollbar_rounding = globals.settings.style_corner_radius

    def refresh_fonts(self):
        io.fonts.clear()
        win_w, win_h = glfw.get_window_size(self.window)
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        font_scaling_factor = max(fb_w / win_w, fb_h / win_h)
        io.font_global_scale = 1 / font_scaling_factor
        self.size_mult = globals.settings.style_scaling
        io.fonts.add_font_from_file_ttf(
            str(globals.self_path / "resources/fonts/Karla-Regular.ttf"),
            18 * font_scaling_factor * self.size_mult,
            font_config=imgui.core.FontConfig(oversample_h=3, oversample_v=3)
        )
        io.fonts.add_font_from_file_ttf(
            str(globals.self_path / "resources/fonts/materialdesignicons-webfont.ttf"),
            18 * font_scaling_factor * self.size_mult,
            font_config=imgui.core.FontConfig(merge_mode=True, glyph_offset_y=1),
            glyph_ranges=imgui.core.GlyphRanges([0xf0000, 0xf2000, 0])
        )
        self.big_font = io.fonts.add_font_from_file_ttf(
            str(globals.self_path / "resources/fonts/Karla-Regular.ttf"),
            28 * font_scaling_factor * self.size_mult,
            font_config=imgui.core.FontConfig(oversample_h=3, oversample_v=3)
        )
        self.impl.refresh_font_texture()

    def close(self, *args, **kwargs):
        glfw.set_window_should_close(self.window, True)

    def minimize(self, *args, **kwargs):
        glfw.hide_window(self.window)
        glfw.focus_window(self.window)
        self.visible = False

    def show(self, *args, **kwargs):
        glfw.show_window(self.window)
        self.visible = True

    def scaled(self, size: int | float):
        return size * self.size_mult

    def main_loop(self):
        while not glfw.window_should_close(self.window):
            self.qt_loop.processEvents()
            glfw.poll_events()
            self.impl.process_inputs()
            if self.visible:
                imgui.new_frame()
                self.drew_filepicker = False

                imgui.set_next_window_position(0, 0, imgui.ONCE)
                if (size := io.display_size) != self.prev_size:
                    imgui.set_next_window_size(*size, imgui.ALWAYS)

                imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0)
                if imgui.begin("F95Checker", closable=False, flags=self.window_flags) or True:
                    imgui.pop_style_var()
                    sidebar_size = self.scaled(self.sidebar_size)

                    if imgui.begin_child("##main_frame", width=-sidebar_size) or True:
                        self.hovered_game = None
                        if globals.settings.display_mode is DisplayMode.list:
                            self.draw_games_list()
                        elif globals.settings.display_mode is DisplayMode.grid:
                            self.draw_games_grid()
                        self.draw_bottombar()
                    imgui.end_child()

                    text = self.status_text or self.watermark_text
                    _3 = self.scaled(3)
                    _6 = self.scaled(6)
                    text_size = imgui.calc_text_size(text)
                    text_x = size.x - text_size.x - _6
                    text_y = size.y - text_size.y - _6

                    imgui.same_line(spacing=1)
                    if imgui.begin_child("##sidebar_frame", width=sidebar_size - 1, height=-text_size.y - _3) or True:
                        self.draw_sidebar()
                    imgui.end_child()

                    if not self.status_text:
                        imgui.set_cursor_screen_pos((text_x - _3, text_y))
                        if imgui.invisible_button("##watermark_btn", width=text_size.x + _6, height=text_size.y + _3):
                            imgui.open_popup("About F95Checker")
                    imgui.set_cursor_screen_pos((text_x, text_y))
                    imgui.text(text)

                    self.draw_game_info_popup()
                    self.draw_filepicker_popup()
                    self.draw_about_popup()
                imgui.end()

                if (size := io.display_size) != self.prev_size:
                    self.prev_size = size

                imgui.render()
                self.impl.render(imgui.get_draw_data())
            if self.size_mult != globals.settings.style_scaling:
                self.refresh_fonts()
                async_thread.run(db.update_settings("style_scaling"))  # Update here in case of crash
            glfw.swap_buffers(self.window)  # Also waits idle time, must run always to avoid useless cycles
        imgui.save_ini_settings_to_disk(self.ini_file_name.decode("utf-8"))
        self.impl.shutdown()
        glfw.terminate()

    def draw_help_marker(self, help_text: str, *args, **kwargs):
        imgui.text_disabled("(?)", *args, **kwargs)
        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.push_text_wrap_pos(min(imgui.get_font_size() * 35, io.display_size.x))
            imgui.text_unformatted(help_text)
            imgui.pop_text_wrap_pos()
            imgui.end_tooltip()

    def draw_game_more_info_button(self, game: Game, label: str = "", selectable: bool = False, *args, **kwargs):
        id = f"{label}##{game.id}_more_info"
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if clicked:
            self.current_info_popup_game = game

    def draw_game_play_button(self, game: Game, label: str = "", selectable: bool = False, *args, **kwargs):
        id = f"{label}##{game.id}_play_button"
        if not game.installed:
            push_disabled()
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if not game.installed:
            pop_disabled()
        if clicked:
            pass  # TODO: game launching

    def draw_game_engine_widget(self, game: Game, *args, **kwargs):
        col = (*EngineColors[game.engine.value], 1)
        imgui.push_style_color(imgui.COLOR_BUTTON, *col)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *col)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *col)
        imgui.small_button(f"{game.engine.name}##{game.id}_engine", *args, **kwargs)
        imgui.pop_style_color(3)

    def draw_game_version_text(self, game: Game, disabled: bool = False, *args, **kwargs):
        if game.installed and game.installed != game.version:
            text = f"Installed: {game.installed}  -  Latest: {game.version}"
        else:
            text = game.version
        if disabled:
            imgui.text_disabled(text, *args, **kwargs)
        else:
            imgui.text(text, *args, **kwargs)

    def draw_game_status_widget(self, game: Game, *args, **kwargs):
        if game.status is Status.Completed:
            imgui.text_colored("󰄳", 0.00, 0.85, 0.00, *args, **kwargs)
        elif game.status is Status.OnHold:
            imgui.text_colored("󰏥", 0.00, 0.50, 0.95, *args, **kwargs)
        elif game.status is Status.Abandoned:
            imgui.text_colored("󰅙", 0.87, 0.20, 0.20, *args, **kwargs)
        else:
            imgui.text("", *args, **kwargs)

    def draw_game_played_checkbox(self, game: Game, label: str = "", *args, **kwargs):
        changed, game.played = imgui.checkbox(f"{label}##{game.id}_played", game.played, *args, **kwargs)
        if changed:
            async_thread.run(db.update_game(game, "played"))
            self.require_sort = True

    def draw_game_installed_checkbox(self, game: Game, label: str = "", *args, **kwargs):
        changed, installed = imgui.checkbox(f"{label}##{game.id}_installed", game.installed == game.version, *args, **kwargs)
        if changed:
            if installed:
                game.installed = game.version
            else:
                game.installed = ""
            async_thread.run(db.update_game(game, "installed"))
            self.require_sort = True

    def draw_game_rating_widget(self, game: Game, *args, **kwargs):
        imgui.push_style_color(imgui.COLOR_BUTTON, 0, 0, 0, 0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0, 0, 0, 0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0, 0, 0, 0)
        imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (0, 0))
        imgui.push_style_var(imgui.STYLE_ITEM_SPACING, (0, 0))
        for i in range(1, 6):
            label = "󰓎"
            if i > game.rating:
                label = "󰓒"
            if imgui.small_button(f"{label}##{game.id}_rating_{i}", *args, **kwargs):
                game.rating = i
                async_thread.run(db.update_game(game, "rating"))
                self.require_sort = True
            imgui.same_line()
        imgui.pop_style_color(3)
        imgui.pop_style_var(2)
        imgui.dummy(0, 0)

    def draw_game_open_thread_button(self, game: Game, label: str = "", selectable: bool = False, *args, **kwargs):
        id = f"{label}##{game.id}_open_thread"
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if clicked:
            pass  # TODO: open game threads

    def draw_game_select_exe_button(self, game: Game, label: str = "", selectable: bool = False, *args, **kwargs):
        id = f"{label}##{game.id}_select_exe"
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if clicked:
            pass  # TODO: select exe

    def draw_game_unset_exe_button(self, game: Game, label: str = "", selectable: bool = False, *args, **kwargs):
        id = f"{label}##{game.id}_unset_exe"
        if not game.executable:
            push_disabled()
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if not game.executable:
            pop_disabled()
        if clicked:
            pass  # TODO: unset exe

    def draw_game_open_folder_button(self, game: Game, label: str = "", selectable: bool = False, *args, **kwargs):
        id = f"{label}##{game.id}_open_folder"
        if not game.executable:
            push_disabled()
        if selectable:
            clicked = imgui.selectable(id, False, *args, **kwargs)[0]
        else:
            clicked = imgui.button(id, *args, **kwargs)
        if not game.executable:
            pop_disabled()
        if clicked:
            pass  # TODO: open folder

    def draw_game_context_menu(self, game: Game):
        self.draw_game_more_info_button(game, label="󰋽 More Info", selectable=True)
        imgui.separator()
        self.draw_game_play_button(game, label="󰐊 Play", selectable=True)
        self.draw_game_open_thread_button(game, label="󰏌 Open Thread", selectable=True)
        imgui.separator()
        self.draw_game_select_exe_button(game, label="󰷏 Select Exe", selectable=True)
        self.draw_game_unset_exe_button(game, label="󰮞 Unset Exe", selectable=True)
        self.draw_game_open_folder_button(game, label="󱞋 Open Folder", selectable=True)
        imgui.separator()
        self.draw_game_played_checkbox(game, label="󰈼 Played")
        self.draw_game_installed_checkbox(game, label="󰅢 Installed")
        imgui.separator()
        self.draw_game_rating_widget(game)

    def draw_game_notes_widget(self, game: Game, *args, **kwargs):
        changed, new_notes = imgui.input_text_multiline(
            f"##{game.id}_notes",
            value=game.notes,
            buffer_length=9999999,
            width=imgui.get_content_region_available_width(),
            height=self.scaled(100),
            *args,
            **kwargs
        )
        if changed:
            game.notes = new_notes
            async_thread.run(db.update_game(game, "notes"))

    def draw_game_tags_widget(self, game: Game, *args, **kwargs):
        col = (0.3, 0.3, 0.3, 1)
        imgui.push_style_color(imgui.COLOR_BUTTON, *col)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *col)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *col)
        _20 = self.scaled(20)
        for tag in game.tags:
            if imgui.get_content_region_available_width() < imgui.calc_text_size(tag.name).x + _20:
                imgui.dummy(0, 0)
            imgui.small_button(tag.name, *args, **kwargs)
            imgui.same_line()
        imgui.dummy(0, 0)
        imgui.pop_style_color(3)

    def draw_game_info_popup(self):
        if not self.current_info_popup_game:
            return
        if not imgui.is_popup_open("Game info"):
            imgui.open_popup("Game info")
        size = io.display_size
        height = size.y * 0.9
        width = min(size.x * 0.9, height * self.scaled(0.9))
        imgui.set_next_window_size(width, height)
        center_next_window()
        if imgui.begin_popup_modal("Game info", True, flags=self.popup_flags)[0]:
            close_popup_clicking_outside()
            game = self.current_info_popup_game

            image = game.image
            aspect_ratio = image.height / image.width
            avail = imgui.get_content_region_available()
            width = min(avail.x, image.width)
            height = min(width * aspect_ratio, image.height)
            if height > (new_height := avail.y * self.scaled(0.3)):
                height = new_height
                width = height * (1 / aspect_ratio)
            if width < avail.x:
                imgui.set_cursor_pos_x((avail.x - width + style.scrollbar_size) / 2)
            image_pos = imgui.get_cursor_screen_pos()
            image.render(width, height, rounding=True, flags=imgui.DRAW_ROUND_CORNERS_ALL)
            if imgui.is_item_hovered() and globals.settings.zoom_enabled:
                size = globals.settings.zoom_size
                zoom = globals.settings.zoom_amount
                zoomed_size = size * zoom
                mouse_pos = io.mouse_pos
                ratio = image.width / width
                x = mouse_pos.x - image_pos.x - size * 0.5
                y = mouse_pos.y - image_pos.y - size * 0.5
                if x < 0:
                    x = 0
                elif x > (new_x := width - size):
                    x = new_x
                if y < 0:
                    y = 0
                elif y > (new_y := height - size):
                    y = new_y
                if globals.settings.zoom_region:
                    rect_x = x + image_pos.x
                    rect_y = y + image_pos.y
                    draw_list = imgui.get_window_draw_list()
                    draw_list.add_rect(rect_x, rect_y, rect_x + size, rect_y + size, imgui.get_color_u32_rgba(1, 1, 1, 1), thickness=2)
                x *= ratio
                y *= ratio
                size *= ratio
                left = x / image.width
                top = y / image.height
                right = (x + size) / image.width
                bottom = (y + size) / image.height
                imgui.begin_tooltip()
                image.render(zoomed_size, zoomed_size, (left, top), (right, bottom), rounding=True)
                imgui.end_tooltip()
            imgui.push_text_wrap_pos()


            imgui.push_font(self.big_font)
            imgui.text(game.name)
            imgui.pop_font()

            self.draw_game_play_button(game, label="󰐊 Play")
            imgui.same_line()
            self.draw_game_open_thread_button(game, label="󰏌 Open Thread")
            imgui.same_line()
            self.draw_game_played_checkbox(game, label="󰈼 Played")
            imgui.same_line(spacing=self.scaled(10))
            self.draw_game_installed_checkbox(game, label="󰅢 Installed")

            imgui.text_disabled("Personal Rating:")
            imgui.same_line()
            self.draw_game_rating_widget(game)

            imgui.text_disabled("Version:")
            imgui.same_line()
            self.draw_game_version_text(game)

            imgui.text_disabled("Status:")
            imgui.same_line()
            imgui.text(game.status.name)
            imgui.same_line()
            self.draw_game_status_widget(game)

            imgui.text_disabled("Developer:")
            imgui.same_line()
            imgui.text(game.developer)

            imgui.text_disabled("Engine:")
            imgui.same_line()
            self.draw_game_engine_widget(game)

            imgui.text_disabled("Last Updated:")
            imgui.same_line()
            imgui.text(game.last_updated.display)

            imgui.text_disabled("Last Played:")
            imgui.same_line()
            imgui.text(game.last_played.display)

            imgui.text_disabled("Added On:")
            imgui.same_line()
            imgui.text(game.added_on.display)

            imgui.text_disabled("Executable:")
            imgui.same_line()
            imgui.text(game.executable or "Not set")

            imgui.text_disabled("Manage Exe:")
            imgui.same_line()
            self.draw_game_select_exe_button(game, label="󰷏 Select Exe")
            imgui.same_line()
            self.draw_game_unset_exe_button(game, label="󰮞 Unset Exe")
            imgui.same_line()
            self.draw_game_open_folder_button(game, label="󱞋 Open Folder")

            imgui.text("")

            imgui.text_disabled("Notes:")
            self.draw_game_notes_widget(game)

            imgui.text("")

            imgui.text_disabled("Tags:")
            if game.tags:
                self.draw_game_tags_widget(game)
            else:
                imgui.text("This game has no tags!")

            imgui.text("")

            imgui.text_disabled("Description:")
            if game.description:
                imgui.text_unformatted(game.description)
            else:
                imgui.text_unformatted("Either this game doesn't have a description, or the thread is not formatted properly!")

            imgui.text("")

            imgui.text_disabled("Changelog:")
            if game.changelog:
                imgui.text_unformatted(game.changelog)
            else:
                imgui.text_unformatted("Either this game doesn't have a changelog, or the thread is not formatted properly!")

            imgui.pop_text_wrap_pos()
            imgui.end_popup()
        if not imgui.is_popup_open("Game info"):
            self.current_info_popup_game = None

    def draw_filepicker_popup(self):
        if self.current_filepicker and not self.drew_filepicker:
            self.current_filepicker.draw()
            if not self.current_filepicker.active:
                self.current_filepicker = None
            self.drew_filepicker = True

    def draw_about_popup(self):
        size = io.display_size
        imgui.set_next_window_size_constraints((0, 0), (size.x * 0.9, size.y * 0.9))
        center_next_window()
        if imgui.begin_popup_modal("About F95Checker", True, flags=self.popup_flags | imgui.WINDOW_ALWAYS_AUTO_RESIZE)[0]:
            close_popup_clicking_outside()
            _50 = self.scaled(50)
            _210 = self.scaled(210)
            imgui.begin_group()
            imgui.dummy(_50, _210)
            imgui.same_line()
            self.icon_texture.render(_210, _210, rounding=True)
            imgui.same_line()
            imgui.begin_group()
            imgui.push_font(self.big_font)
            imgui.text("F95Checker")
            imgui.pop_font()
            imgui.text(f"Version {globals.version}")
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
            imgui.dummy(_50, _210)
            imgui.end_group()
            imgui.spacing()
            width = imgui.get_item_rect_size().x
            btn_width = (width - 2 * style.item_spacing.x) / 3
            if imgui.button("󰏌 F95Zone Thread", width=btn_width):
                print("aaa")
            imgui.same_line()
            if imgui.button("󰊤 GitHub Repo", width=btn_width):
                print("aaa")
            imgui.same_line()
            if imgui.button("󰌹 Donate + Links", width=btn_width):
                print("aaa")
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
            imgui.push_font(self.big_font)
            size = imgui.calc_text_size("Cool People")
            imgui.set_cursor_pos_x((width - size.x) / 2)
            imgui.text("Cool People")
            imgui.pop_font()
            imgui.spacing()
            imgui.spacing()
            imgui.text("Supporters:")
            imgui.bullet_text("FaceCrap")
            imgui.spacing()
            imgui.spacing()
            imgui.text("Contributors:")
            imgui.bullet()
            imgui.text("GR3ee3N: Optimized build workflows and other PRs")
            imgui.bullet()
            imgui.text("batblue: Implemented fixes for MacOS support")
            imgui.bullet()
            imgui.text("ploper26: Suggested HEAD requests for refreshing")
            imgui.bullet()
            imgui.text("ascsd: Helped with brainstorming on some issues and gave some tips")
            imgui.spacing()
            imgui.spacing()
            imgui.text("Community:")
            for name in [
                "AtotehZ",
                "unroot",
                "abada25",
                "d_pedestrian",
                "yohudood",
                "GrammerCop",
                "SmurfyBlue",
                "bitogno",
                "MillenniumEarl",
                "DarK x Duke"
            ]:
                if imgui.get_content_region_available_width() < imgui.calc_text_size(name).x + self.scaled(20):
                    imgui.dummy(0, 0)
                imgui.bullet_text(name)
                imgui.same_line(spacing=16)
            imgui.pop_text_wrap_pos()
            imgui.end_popup()

    def sort_games(self, sort_specs: imgui.core._ImGuiTableSortSpecs, manual_sort: int | bool):
        if manual_sort != self.prev_manual_sort:
            self.prev_manual_sort = manual_sort
            self.require_sort = True
        if sort_specs.specs_dirty or self.require_sort:
            if manual_sort:
                changed = False
                for id in globals.settings.manual_sort_list:
                    if id not in globals.games:
                        globals.settings.manual_sort_list.remove(id)
                        changed = True
                for id in globals.games:
                    if id not in globals.settings.manual_sort_list:
                        globals.settings.manual_sort_list.append(id)
                        changed = True
                if changed:
                    async_thread.run(db.update_settings("manual_sort_list"))
                self.sorted_games_ids = globals.settings.manual_sort_list
            elif sort_specs.specs_count > 0:
                sort_spec = sort_specs.specs[0]
                match sort_spec.column_index:
                    case 5:  # Engine
                        key = lambda id: globals.games[id].engine.value
                    case 7:  # Developer
                        key = lambda id: globals.games[id].developer.lower()
                    case 8:  # Last Updated
                        key = lambda id: globals.games[id].last_updated.value
                    case 9:  # Last Played
                        key = lambda id: globals.games[id].last_played.value
                    case 10:  # Added On
                        key = lambda id: globals.games[id].added_on.value
                    case 11:  # Played
                        key = lambda id: globals.games[id].played
                    case 12:  # Installed
                        key = lambda id: globals.games[id].installed == globals.games[id].version
                    case 13:  # Rating
                        key = lambda id: globals.games[id].rating
                    case _:  # Name and all others
                        key = lambda id: globals.games[id].name.lower()
                ids = list(globals.games.keys())
                ids.sort(key=key, reverse=bool(sort_spec.sort_direction - 1))
                self.sorted_games_ids = ids
            sort_specs.specs_dirty = False
            self.require_sort = False

    def handle_game_hitbox_events(self, game: Game, game_i: int, manual_sort: bool):
        if imgui.is_item_hovered(imgui.HOVERED_ALLOW_WHEN_BLOCKED_BY_ACTIVE_ITEM):
            # Hover = image on refresh button
            self.hovered_game = game
            if imgui.is_item_clicked():
                self.game_hitbox_click = True
            if self.game_hitbox_click and not imgui.is_mouse_down():
                # Left click = open game info popup
                self.game_hitbox_click = False
                self.current_info_popup_game = game
        if manual_sort:
            # Left click drag = swap if in manual sort mode
            if imgui.begin_drag_drop_source(flags=self.game_hitbox_drag_drop_flags):
                self.game_hitbox_click = False
                payload = game_i + 1
                payload = payload.to_bytes(payload.bit_length(), sys.byteorder)
                imgui.set_drag_drop_payload("game_i", payload)
                imgui.end_drag_drop_source()
            if imgui.begin_drag_drop_target():
                if payload := imgui.accept_drag_drop_payload("game_i", flags=self.game_hitbox_drag_drop_flags):
                    payload = int.from_bytes(payload, sys.byteorder)
                    payload = payload - 1
                    lst = globals.settings.manual_sort_list
                    lst[game_i], lst[payload] = lst[payload], lst[game_i]
                    async_thread.run(db.update_settings("manual_sort_list"))
                imgui.end_drag_drop_target()
        if imgui.begin_popup_context_item(f"##{game.id}_context"):
            # Right click = context menu
            self.draw_game_context_menu(game)
            imgui.end_popup()

    def draw_games_list(self):
        ghost_column_size = (style.frame_padding.x + style.cell_padding.x * 2)
        offset = ghost_column_size * self.ghost_columns_enabled_count
        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() - offset)
        if imgui.begin_table(
            "##game_list",
            column=self.game_list_column_count,
            flags=self.game_list_table_flags,
            outer_size_height=-imgui.get_frame_height_with_spacing()  # Bottombar
        ):
            # Setup
            # Hack: custom toggles in table header right click menu by adding tiny empty "ghost" columns and hiding them
            # by starting the table render before the content region.
            imgui.table_setup_column("Manual Sort", self.ghost_columns_flags | imgui.TABLE_COLUMN_DEFAULT_HIDE)  # 0
            imgui.table_setup_column("Version", self.ghost_columns_flags)  # 1
            imgui.table_setup_column("Status", self.ghost_columns_flags)  # 2
            imgui.table_setup_column("##separator", self.ghost_columns_flags | imgui.TABLE_COLUMN_NO_HIDE)  # 3
            self.ghost_columns_enabled_count = 1
            manual_sort = imgui.table_get_column_flags(0) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            version_enabled = imgui.table_get_column_flags(1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            status_enabled = imgui.table_get_column_flags(2) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            self.ghost_columns_enabled_count += version_enabled
            self.ghost_columns_enabled_count += status_enabled
            self.ghost_columns_enabled_count += manual_sort
            can_sort = imgui.TABLE_COLUMN_NO_SORT * manual_sort
            imgui.table_setup_column("Play Button", imgui.TABLE_COLUMN_NO_SORT)  # 4
            imgui.table_setup_column("Engine", imgui.TABLE_COLUMN_DEFAULT_HIDE | can_sort)  # 5
            imgui.table_setup_column("Name", imgui.TABLE_COLUMN_WIDTH_STRETCH | imgui.TABLE_COLUMN_DEFAULT_SORT | imgui.TABLE_COLUMN_NO_HIDE | can_sort)  # 6
            imgui.table_setup_column("Developer", imgui.TABLE_COLUMN_DEFAULT_HIDE | can_sort)  # 7
            imgui.table_setup_column("Last Updated", imgui.TABLE_COLUMN_DEFAULT_HIDE | can_sort)  # 8
            imgui.table_setup_column("Last Played", imgui.TABLE_COLUMN_DEFAULT_HIDE | can_sort)  # 9
            imgui.table_setup_column("Added On", imgui.TABLE_COLUMN_DEFAULT_HIDE | can_sort)  # 10
            imgui.table_setup_column("Played", can_sort)  # 11
            imgui.table_setup_column("Installed", can_sort)  # 12
            imgui.table_setup_column("Rating", imgui.TABLE_COLUMN_DEFAULT_HIDE | can_sort)  # 13
            imgui.table_setup_column("Open Thread", imgui.TABLE_COLUMN_NO_SORT)  # 14
            imgui.table_setup_scroll_freeze(0, 1)  # Sticky column headers

            # Headers
            imgui.table_next_row(imgui.TABLE_ROW_HEADERS)
            for i in range(self.game_list_column_count):
                imgui.table_set_column_index(i)
                name = imgui.table_get_column_name(i)
                if i in (0, 1, 2, 4, 14):  # Hide name for small and ghost columns
                    name = "##" + name
                elif i == 6:  # Name
                    if version_enabled:
                        name += "   -   Version"
                    if status_enabled:
                        name += "   -   Status"
                elif i == 11:  # Played
                    name = "󰈼"
                elif i == 12:  # Installed
                    name = "󰅢"
                imgui.table_header(name)

            # Sorting
            sort_specs = imgui.table_get_sort_specs()
            self.sort_games(sort_specs, manual_sort)

            # Loop rows
            for game_i, id in enumerate(self.sorted_games_ids):
                game: Game = globals.games[id]
                imgui.table_next_row()
                column_i = 3
                # Base row height
                imgui.table_set_column_index(column_i)
                imgui.button(f"##{game.id}_id", width=0.1)
                # Play Button
                if imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED:
                    imgui.table_set_column_index(column_i)
                    self.draw_game_play_button(game, label="󰐊")
                # Engine
                if imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED:
                    imgui.table_set_column_index(column_i)
                    self.draw_game_engine_widget(game)
                # Name
                imgui.table_set_column_index(column_i := column_i + 1)
                imgui.text(game.name)
                if version_enabled:
                    imgui.same_line()
                    self.draw_game_version_text(game, disabled=True)
                if status_enabled:
                    imgui.same_line()
                    self.draw_game_status_widget(game)
                # Developer
                if imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED:
                    imgui.table_set_column_index(column_i)
                    imgui.text(game.developer)  # TODO: fetch game developers
                # Last Updated
                if imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED:
                    imgui.table_set_column_index(column_i)
                    imgui.text(game.last_updated.display)
                # Last Played
                if imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED:
                    imgui.table_set_column_index(column_i)
                    imgui.text(game.last_played.display)
                # Added On
                if imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED:
                    imgui.table_set_column_index(column_i)
                    imgui.text(game.added_on.display)
                # Played
                if imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED:
                    imgui.table_set_column_index(column_i)
                    self.draw_game_played_checkbox(game)
                # Installed
                if imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED:
                    imgui.table_set_column_index(column_i)
                    self.draw_game_installed_checkbox(game)
                # Rating
                if imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED:
                    imgui.table_set_column_index(column_i)
                    self.draw_game_rating_widget(game)
                # Open Thread
                if imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED:
                    imgui.table_set_column_index(column_i)
                    self.draw_game_open_thread_button(game, label="󰏌")
                # Row hitbox
                imgui.same_line()
                imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() - style.frame_padding.y)
                imgui.selectable(f"##{game.id}_hitbox", False, flags=imgui.SELECTABLE_SPAN_ALL_COLUMNS, height=imgui.get_frame_height())
                self.handle_game_hitbox_events(game, game_i, manual_sort)

            imgui.end_table()

    def draw_games_grid(self):
        # Hack: get sort specs for list mode in grid mode
        pos = imgui.get_cursor_pos_y()
        if imgui.begin_table(
            "##game_list",
            column=self.game_list_column_count,
            flags=self.game_list_table_flags,
            outer_size_height=1
        ):
            # Sorting
            sort_specs = imgui.table_get_sort_specs()
            manual_sort = imgui.table_get_column_flags(0) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            self.sort_games(sort_specs, manual_sort)
            imgui.end_table()
        imgui.set_cursor_pos_y(pos)

        count = 3
        imgui.push_style_var(imgui.STYLE_CELL_PADDING, (10, 10))
        if imgui.begin_table(
            "##game_grid",
            column=count,
            flags=self.game_grid_table_flags,
            outer_size_height=-imgui.get_frame_height_with_spacing()  # Bottombar
        ):
            # Setup
            imgui.push_style_color(imgui.COLOR_CHILD_BACKGROUND, *style.colors[imgui.COLOR_TABLE_ROW_BACKGROUND_ALT])
            for i in range(count):
                imgui.table_setup_column(f"##game_grid_{i}", imgui.TABLE_COLUMN_WIDTH_STRETCH)
            img_ratio = 3
            width = None
            img_height = None
            cell_height = None

            # Loop cells
            for game_i, id in enumerate(self.sorted_games_ids):
                game: Game = globals.games[id]
                imgui.table_next_column()

                # Setup pt2
                if width is None:
                    width = imgui.get_content_region_available_width()
                    img_height = width / img_ratio
                    spacing = style.item_spacing.y
                    cell_height = img_height + spacing + (imgui.get_text_line_height() + spacing) * 1

                # Cell
                if imgui.begin_child(f"##{game.id}_cell", width=width, height=cell_height, flags=self.game_grid_cell_flags) or True:
                    imgui.begin_group()
                    # Image
                    game.image.render(width, img_height, *game.image.crop_to_ratio(img_ratio), rounding=True, flags=imgui.DRAW_ROUND_CORNERS_TOP)
                    # Setup pt3
                    imgui.indent(style.item_spacing.x * 2)
                    # Name
                    imgui.text(game.name)
                    # Cell hitbox
                    imgui.dummy(*imgui.get_content_region_available())
                    imgui.end_group()
                    self.handle_game_hitbox_events(game, game_i, manual_sort)
                imgui.end_child()

            imgui.pop_style_color()
            imgui.end_table()
        imgui.pop_style_var()

    def draw_bottombar(self):
        new_display_mode = None

        if globals.settings.display_mode is DisplayMode.grid:
            push_disabled(block_interaction=False)
        if imgui.button("󱇘"):
            new_display_mode = DisplayMode.list
        if globals.settings.display_mode is DisplayMode.grid:
            pop_disabled(block_interaction=False)

        imgui.same_line()
        if globals.settings.display_mode is DisplayMode.list:
            push_disabled(block_interaction=False)
        if imgui.button("󱇙"):
            new_display_mode = DisplayMode.grid
        if globals.settings.display_mode is DisplayMode.list:
            pop_disabled(block_interaction=False)

        if new_display_mode is not None:
            globals.settings.display_mode = new_display_mode
            async_thread.run(db.update_settings("display_mode"))

        imgui.same_line()
        imgui.set_next_item_width(-(imgui.calc_text_size("Add!").x + 2 * style.frame_padding.x) - style.item_spacing.x)
        imgui.input_text("##filter_add_bar", "", 9999999)
        imgui.same_line()
        if imgui.button("Add!"):
            pass  # TODO: add button functionality

    def start_settings_section(self, name: str, right_width: int | float, collapsible: bool = True):
        if collapsible:
            header = imgui.collapsing_header(name)[0]
        else:
            header = True
        opened = header and imgui.begin_table(f"##{name}", column=2, flags=imgui.TABLE_NO_CLIP)
        if opened:
            imgui.table_setup_column(f"##{name}_left", imgui.TABLE_COLUMN_WIDTH_STRETCH)
            imgui.table_setup_column(f"##{name}_right", imgui.TABLE_COLUMN_WIDTH_FIXED)
            imgui.table_next_row()
            imgui.table_set_column_index(1)  # Right
            imgui.dummy(right_width, 1)
            imgui.push_item_width(right_width)
        return opened

    def draw_sidebar(self):
        set = globals.settings

        width = imgui.get_content_region_available_width()
        height = self.scaled(126)
        if self.hovered_game:
            game = self.hovered_game
            game.image.render(width, height, *game.image.crop_to_ratio(width / height), rounding=True, flags=imgui.DRAW_ROUND_CORNERS_ALL)
        else:
            if imgui.button("Refresh!", width=width, height=height):
                print("aaa")

        imgui.spacing()
        imgui.spacing()
        imgui.text(f"Total games count: {len(globals.games)}")
        imgui.spacing()
        imgui.spacing()

        right_width = self.scaled(100)
        checkbox_offset = right_width - imgui.get_frame_height()
        if imgui.begin_child("Settings") or True:

            if self.start_settings_section("Browser", right_width):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Browser:")
                imgui.same_line()
                self.draw_help_marker("All the options you select here ONLY affect how F95Checker opens links for you, it DOES NOT affect how this tool "
                                      "operates internally. F95Checker DOES NOT interact with your browsers in any meaningful way, it uses a separate "
                                      "session just for itself.")
                imgui.table_next_column()
                changed, value = imgui.combo("##browser", set.browser.value - 1, list(Browser.__members__.keys()))
                if changed:
                    set.browser = Browser(value + 1)
                    async_thread.run(db.update_settings("browser"))

                if set.browser is Browser.Custom:
                    imgui.table_next_row()
                    imgui.table_next_column()
                    imgui.text("Custom browser:")
                    imgui.table_next_column()
                    if imgui.button("Configure", width=right_width):
                        imgui.open_popup("Configure custom browser")
                    center_next_window()
                    if imgui.begin_popup_modal("Configure custom browser", True, flags=self.popup_flags)[0]:
                        close_popup_clicking_outside()
                        imgui.text("Executable: ")
                        imgui.same_line()
                        pos = imgui.get_cursor_pos_x()
                        changed, set.browser_custom_executable = imgui.input_text("##browser_custom_executable", set.browser_custom_executable, 9999999)
                        if changed:
                            async_thread.run(db.update_settings("browser_custom_executable"))
                        imgui.same_line()
                        clicked = imgui.button("󰷏")
                        imgui.same_line(spacing=0)
                        args_width = imgui.get_cursor_pos_x() - pos
                        imgui.dummy(0, 0)
                        if clicked:
                            def callback(selected: str):
                                if selected:
                                    set.browser_custom_executable = selected
                                    async_thread.run(db.update_settings("browser_custom_executable"))
                            self.current_filepicker = FilePicker(title="Select browser executable", start_dir=set.browser_custom_executable, callback=callback)
                        self.draw_filepicker_popup()
                        imgui.text("Arguments: ")
                        imgui.same_line()
                        imgui.set_cursor_pos_x(pos)
                        imgui.set_next_item_width(args_width)
                        changed, set.browser_custom_arguments = imgui.input_text("##browser_custom_arguments", set.browser_custom_arguments, 9999999)
                        if changed:
                            async_thread.run(db.update_settings("browser_custom_arguments"))
                        imgui.end_popup()
                else:
                    imgui.table_next_row()
                    imgui.table_next_column()
                    imgui.text("Use private mode:")
                    imgui.table_next_column()
                    imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                    changed, value = imgui.checkbox("##browser_private", set.browser_private)
                    if changed:
                        set.browser_private = value
                        async_thread.run(db.update_settings("browser_private"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Download pages:")
                imgui.same_line()
                self.draw_help_marker("With this enabled links will first be downloaded by F95Checker and then opened as simple HTML files in your "
                                      "browser. This might be useful if you use private mode because the page will load as if you were logged in, "
                                      "allowing you to see links and spoiler content without actually logging in.")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                changed, value = imgui.checkbox("##browser_html", set.browser_html)
                if changed:
                    set.browser_html = value
                    async_thread.run(db.update_settings("browser_html"))

                imgui.end_table()
                imgui.spacing()

            if self.start_settings_section("Refresh", right_width):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Refresh completed games:")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                changed, value = imgui.checkbox("##refresh_completed_games", set.refresh_completed_games)
                if changed:
                    set.refresh_completed_games = value
                    async_thread.run(db.update_settings("refresh_completed_games"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Refresh workers:")
                imgui.same_line()
                self.draw_help_marker("Each game that needs to be checked requires that a connection to F95Zone happens. Each worker can handle 1 "
                                      "connection at a time. Having more workers means more connections happen simultaneously, but having too many "
                                      "will freeze the program. In most cases 20 workers is a good compromise.")
                imgui.table_next_column()
                changed, value = imgui.input_int("##refresh_workers", set.refresh_workers)
                set.refresh_workers = min(max(value, 1), 100)
                if changed:
                    async_thread.run(db.update_settings("refresh_workers"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Request timeout:")
                imgui.same_line()
                self.draw_help_marker("To check for updates for a game F95Checker sends a web request to F95Zone. However this can sometimes go "
                                      "wrong. The timeout is the maximum amount of seconds that a request can try to connect for before it fails. "
                                      "A timeout 10-30 seconds is most typical.")
                imgui.table_next_column()
                changed, value = imgui.input_int("##request_timeout", set.request_timeout)
                set.request_timeout = min(max(value, 1), 120)
                if changed:
                    async_thread.run(db.update_settings("request_timeout"))

                imgui.end_table()
                imgui.spacing()

            if self.start_settings_section("Startup", right_width):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Refresh at startup:")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                changed, value = imgui.checkbox("##start_refresh", set.start_refresh)
                if changed:
                    set.start_refresh = value
                    async_thread.run(db.update_settings("start_refresh"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Start minimized:")
                imgui.same_line()
                self.draw_help_marker("F95Checker will start in background mode, minimized in the system tray.")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                changed, value = imgui.checkbox("##start_in_tray", set.start_in_tray)
                if changed:
                    set.start_in_tray = value
                    async_thread.run(db.update_settings("start_in_tray"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Start with system:")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                changed, value = imgui.checkbox("##start_with_system", set.start_with_system)
                if changed:
                    set.start_with_system = value
                    async_thread.run(db.update_settings("start_with_system"))

                imgui.end_table()
                imgui.spacing()

            if self.start_settings_section("Style", right_width):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Interface scaling:")
                imgui.table_next_column()
                changed, value = imgui.input_float("##style_scaling", set.style_scaling, step=0.05, step_fast=0.25)
                set.style_scaling = min(max(value, 0.25), 4)
                imgui.end_table()
                imgui.spacing()

            if self.start_settings_section("Zoom", right_width):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Zoom when hovering images:")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                changed, value = imgui.checkbox("##zoom_enabled", set.zoom_enabled)
                if changed:
                    set.zoom_enabled = value
                    async_thread.run(db.update_settings("zoom_enabled"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Zoom amount:")
                imgui.table_next_column()
                changed, value = imgui.input_int("##zoom_amount", set.zoom_amount)
                set.zoom_amount = min(max(value, 1), 20)
                if changed:
                    async_thread.run(db.update_settings("zoom_amount"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Zoom region size:")
                imgui.table_next_column()
                changed, value = imgui.input_int("##zoom_size", set.zoom_size)
                set.zoom_size = min(max(value, 16), 1024)
                if changed:
                    async_thread.run(db.update_settings("zoom_size"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Show zoom region:")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                changed, value = imgui.checkbox("##zoom_region", set.zoom_region)
                if changed:
                    set.zoom_region = value
                    async_thread.run(db.update_settings("zoom_region"))

                imgui.end_table()
                imgui.spacing()

            if self.start_settings_section("Misc", right_width):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("BG refresh mins:")
                imgui.same_line()
                self.draw_help_marker("When F95Checker is minimized in background mode it automatically refreshes periodically. This controls how "
                                      "often (in minutes) this happens.")
                imgui.table_next_column()
                changed, value = imgui.input_int("##tray_refresh_interval", set.tray_refresh_interval)
                set.tray_refresh_interval = min(max(value, 15), 720)
                if changed:
                    async_thread.run(db.update_settings("tray_refresh_interval"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Keep game image:")
                imgui.same_line()
                self.draw_help_marker("When a game receives an update F95Checker downloads the header image again in case it was updated. This "
                                      "setting makes it so the old image is kept and no new image is downloaded. This is useful in case you want "
                                      f"to have custom images for your games (you can edit the images manually at {globals.data_path / 'images'}).")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                changed, value = imgui.checkbox("##update_keep_image", set.update_keep_image)
                if changed:
                    set.update_keep_image = value
                    async_thread.run(db.update_settings("update_keep_image"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Ask path on add:")
                imgui.same_line()
                self.draw_help_marker("When this is enabled you will be asked to select a game executable right after adding the game to F95Checker.")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + checkbox_offset)
                changed, value = imgui.checkbox("##select_executable_after_add", set.select_executable_after_add)
                if changed:
                    set.select_executable_after_add = value
                    async_thread.run(db.update_settings("select_executable_after_add"))

                imgui.end_table()
                imgui.spacing()

            if self.start_settings_section("Minimize", right_width, collapsible=False):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Switch to BG mode:")
                imgui.table_next_column()
                if imgui.button("Minimize", width=right_width):
                    self.minimize()
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
        self.idle_icon = QtGui.QIcon('resources/icons/icon.png')
        self.paused_icon = QtGui.QIcon('resources/icons/paused.png')
        self.refresh_icon = QtGui.QIcon('resources/icons/refreshing.png')
        super().__init__(self.idle_icon)

        self.watermark = QtGui.QAction(f"F95Checker v{globals.version}")
        # self.watermark.triggered.connect(partial(browsers.open_webpage_sync_helper, globals.tool_page))

        self.show_gui = QtGui.QAction("Show GUI")
        self.show_gui.triggered.connect(self.main_gui.show)

        self.quit = QtGui.QAction("Quit")
        self.quit.triggered.connect(self.main_gui.close)

        self.menu = QtWidgets.QMenu()
        self.menu.addAction(self.watermark)
        self.menu.addAction(self.show_gui)
        self.menu.addAction(self.quit)
        self.setContextMenu(self.menu)

        self.activated.connect(self.activated_filter)

        self.show()

    def activated_filter(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason):
        if reason in self.show_gui_events:
            self.main_gui.show()
