from imgui.integrations.glfw import GlfwRenderer
from PyQt6 import QtCore, QtGui, QtWidgets
import OpenGL.GL as gl
from PIL import Image
import configparser
import pathlib
import pygame
import numpy
import imgui
import glfw
import sys

from modules import async_thread
from modules import filepicker
from modules.structs import *
from modules import globals
from modules import db


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
    def __init__(self, path: str | pathlib.Path):
        self.loaded = False
        self.applied = False
        self.data = None
        self.path = path
        self.width, self.height = 1, 1
        self.texture_id = None

    def reset(self):
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, 0, 0, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, numpy.empty(0))
        self.applied = False

    def load(self):
        image = pygame.image.load(self.path)
        surface = pygame.transform.flip(image, False, True)
        self.width, self.height = surface.get_size()
        self.data = pygame.image.tostring(surface, "RGBA", 1)
        self.loaded = True

    def apply(self):
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, self.width, self.height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, self.data)
        self.applied = True

    def render(self, *args, **kwargs):
        if self.texture_id is None:
            self.texture_id = gl.glGenTextures(1)
        if not self.loaded:
            self.reset()
            self.load()
        elif not self.applied:
            self.apply()
        imgui.image(self.texture_id, *args, **kwargs)


class MainGUI():
    # Constants
    sidebar_size = 269
    game_list_column_count = 15
    window_flags = (
        imgui.WINDOW_NO_MOVE |
        imgui.WINDOW_NO_RESIZE |
        imgui.WINDOW_NO_COLLAPSE |
        imgui.WINDOW_NO_TITLE_BAR |
        imgui.WINDOW_NO_SCROLLBAR |
        imgui.WINDOW_NO_SCROLL_WITH_MOUSE
    )
    game_list_table_flags = (
        imgui.TABLE_SCROLL_Y |
        imgui.TABLE_HIDEABLE |
        imgui.TABLE_SORTABLE |
        imgui.TABLE_REORDERABLE |
        imgui.TABLE_ROW_BACKGROUND |
        imgui.TABLE_SIZING_FIXED_FIT |
        imgui.TABLE_NO_HOST_EXTEND_Y
    )
    ghost_columns_flags = (
        imgui.TABLE_COLUMN_NO_SORT |
        imgui.TABLE_COLUMN_NO_REORDER |
        imgui.TABLE_COLUMN_NO_HEADER_WIDTH
    )
    game_grid_table_flags = (
        imgui.TABLE_SCROLL_Y |
        imgui.TABLE_SIZING_FIXED_FIT |
        imgui.TABLE_NO_HOST_EXTEND_Y
    )
    popup_flags = (
        imgui.WINDOW_NO_MOVE |
        imgui.WINDOW_NO_RESIZE |
        imgui.WINDOW_NO_COLLAPSE |
        imgui.WINDOW_NO_TITLE_BAR
    )

    def __init__(self):
        # Variables
        self.visible = True
        self.prev_size = 0, 0
        self.status_text = ""
        self.require_sort = True
        self.prev_manual_sort = 0
        self.sorted_games_ids = []
        self.current_filepicker = None
        self.current_info_popup_game = 0
        self.game_list_hitbox_click = False
        self.ghost_columns_enabled_count = 0

        # Setup Qt objects
        self.qt_app = QtWidgets.QApplication(sys.argv)
        self.qt_loop = QtCore.QEventLoop()
        self.tray = TrayIcon(self)

        # Setup ImGui
        imgui.create_context()
        self.io = imgui.get_io()
        self.ini_file_name = str(globals.data_path / "imgui.ini").encode()
        self.io.ini_file_name = self.ini_file_name  # Cannot set directly because reference gets lost due to a bug
        try:
            imgui.load_ini_settings_from_disk(self.ini_file_name.decode("utf-8"))
            ini = imgui.save_ini_settings_to_memory()
            start = ini.find("[Window][F95Checker]")
            end = ini.find("\n[", start)
            config = configparser.RawConfigParser()
            config.read_string(ini[start:end])
            size = tuple(int(x) for x in config.get("Window][F95Checker", "Size").split(","))
            assert type(size) is tuple and len(size) == 2
            assert type(size[0]) is int and type(size[1]) is int
        except Exception:
            size = 1280, 720
        self.style = imgui.get_style()

        # Setup GLFW window
        self.window = impl_glfw_init(*size, "F95Checker")
        glfw.set_window_icon(self.window, 1, Image.open("resources/icons/icon.png"))
        self.impl = GlfwRenderer(self.window)
        glfw.set_window_iconify_callback(self.window, self.minimize)
        self.refresh_fonts()

    def refresh_fonts(self):
        self.io.fonts.clear()
        win_w, win_h = glfw.get_window_size(self.window)
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        font_scaling_factor = max(float(fb_w) / win_w, float(fb_h) / win_h)
        self.io.font_global_scale = 1 / font_scaling_factor
        self.io.fonts.add_font_from_file_ttf(
            str(globals.self_path / "resources/fonts/Karla-Regular.ttf"),
            18 * font_scaling_factor,
            font_config=imgui.core.FontConfig(oversample_h=3, oversample_v=3)
        )
        self.io.fonts.add_font_from_file_ttf(
            str(globals.self_path / "resources/fonts/materialdesignicons-webfont.ttf"),
            18 * font_scaling_factor,
            font_config=imgui.core.FontConfig(merge_mode=True, glyph_offset_y=1),
            glyph_ranges=imgui.core.GlyphRanges([0xf0000, 0xf2000, 0])
        )
        self.big_font = self.io.fonts.add_font_from_file_ttf(
            str(globals.self_path / "resources/fonts/Karla-Regular.ttf"),
            28 * font_scaling_factor,
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

    def main_loop(self):
        while not glfw.window_should_close(self.window):
            self.qt_loop.processEvents()
            glfw.poll_events()
            self.impl.process_inputs()
            if self.visible:
                imgui.new_frame()
                imgui.push_style_color(imgui.COLOR_MODAL_WINDOW_DIM_BACKGROUND, 0, 0, 0, 0.5)

                imgui.set_next_window_position(0, 0, imgui.ONCE)
                if (size := self.io.display_size) != self.prev_size:
                    imgui.set_next_window_size(*size, imgui.ALWAYS)

                if imgui.begin("F95Checker", closable=False, flags=self.window_flags) or True:

                    if imgui.begin_child("Main", width=-self.sidebar_size, height=0, border=False) or True:
                        if globals.settings.display_mode is DisplayMode.list:
                            self.draw_games_list()
                        elif globals.settings.display_mode is DisplayMode.grid:
                            self.draw_games_grid()
                        self.draw_bottombar()
                    imgui.end_child()

                    text = self.status_text or f"F95Checker v{globals.version} by WillyJL"
                    text_size = imgui.calc_text_size(text)
                    text_pos = size.x - text_size.x - 6, size.y - text_size.y - 6

                    imgui.same_line(spacing=1)
                    if imgui.begin_child("Sidebar", width=self.sidebar_size - 1, height=-text_size.y, border=False) or True:
                        self.draw_sidebar()
                    imgui.end_child()

                    imgui.set_cursor_screen_pos(text_pos)
                    if imgui.invisible_button("##status_text", *text_size):
                        print("aaa")
                    imgui.set_cursor_screen_pos(text_pos)
                    imgui.text(text)
                imgui.end()

                if (size := self.io.display_size) != self.prev_size:
                    self.prev_size = size

                imgui.pop_style_color()
                imgui.render()
                self.impl.render(imgui.get_draw_data())
            glfw.swap_buffers(self.window)  # Also waits idle time, must run always to avoid useless cycles
        self.impl.shutdown()
        glfw.terminate()

    def draw_help_marker(self, help_text: str, *args, **kwargs):
        imgui.text_disabled("(?)", *args, **kwargs)
        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.push_text_wrap_pos(imgui.get_font_size() * 35)
            imgui.text_unformatted(help_text)
            imgui.pop_text_wrap_pos()
            imgui.end_tooltip()

    def draw_game_play_button(self, game: Game, label:str = "", selectable=False, *args, **kwargs):
        id = f"{label}##{game.id}_play_button"
        if selectable:
            if imgui.selectable(id, False, *args, **kwargs)[0]:
                pass
        else:
            if imgui.button(id, *args, **kwargs):
                pass  # TODO: game launching

    def draw_game_engine_widget(self, game: Game, *args, **kwargs):
        col = (*EngineColors[game.engine.value], 1)
        imgui.push_style_color(imgui.COLOR_BUTTON, *col)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *col)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *col)
        imgui.small_button(f"{game.engine.name}##{game.id}_engine", *args, **kwargs)
        imgui.pop_style_color(3)

    def draw_game_status_widget(self, game: Game, *args, **kwargs):
        if game.status is Status.Completed:
            imgui.text_colored("󰄳", 0.00, 0.85, 0.00, *args, **kwargs)
        elif game.status is Status.OnHold:
            imgui.text_colored("󰏥", 0.00, 0.50, 0.95, *args, **kwargs)
        elif game.status is Status.Abandoned:
            imgui.text_colored("󰅙", 0.87, 0.20, 0.20, *args, **kwargs)
        else:
            imgui.text("", *args, **kwargs)

    def draw_game_played_checkbox(self, game: Game, label:str = "", *args, **kwargs):
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
        imgui.text("")

    def draw_game_open_thread_button(self, game: Game, label: str = "", selectable=False, *args, **kwargs):
        id = f"{label}##{game.id}_open_thread"
        if selectable:
            if imgui.selectable(id, False, *args, **kwargs)[0]:
                pass
        else:
            if imgui.button(id, *args, **kwargs):
                pass  # TODO: open game threads

    def draw_game_notes_widget(self, game: Game, *args, **kwargs):
        changed, new_notes = imgui.input_text_multiline(
            f"##{game.id}_notes",
            value=game.notes,
            buffer_length=9999999,
            width=imgui.get_content_region_available_width(),
            height=100,
            *args,
            **kwargs
        )
        if changed:
            game.notes = new_notes
            async_thread.run(db.update_game(game, "notes"))

    def draw_game_tags_widget(self, game: Game, *args, **kwargs):
        imgui.text("")
        col = (0.3, 0.3, 0.3, 1)
        imgui.push_style_color(imgui.COLOR_BUTTON, *col)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *col)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *col)
        for tag in game.tags:
            imgui.same_line()
            if imgui.get_content_region_available_width() < imgui.calc_text_size(tag.name).x + 20:
                imgui.text("")
            imgui.small_button(tag.name, *args, **kwargs)
        imgui.pop_style_color(3)

    def draw_game_info_popup(self):
        size = self.io.display_size
        height = size.y * 0.9
        width = min(size.x * 0.9, height * 0.9)
        imgui.set_next_window_size(width, height)
        imgui.set_next_window_position((size.x - width) / 2, (size.y - height) / 2)

        if imgui.begin_popup("GameInfo", flags=self.popup_flags):
            game = self.current_info_popup_game

            image = game.image
            aspect_ratio = image.height / image.width
            avail = imgui.get_content_region_available()
            width = min(avail.x, image.width)
            height = min(width * aspect_ratio, image.height)
            if height > (new_height := avail.y * 0.3):
                height = new_height
                width = height * (1 / aspect_ratio)
            if width < avail.x:
                imgui.set_cursor_pos_x((avail.x - width + self.style.scrollbar_size) / 2)
            image_pos = imgui.get_cursor_screen_pos()
            image.render(width, height)
            if imgui.is_item_hovered() and globals.settings.zoom_enabled:
                size = globals.settings.zoom_size
                zoom = globals.settings.zoom_amount
                zoomed_size = size * zoom
                mouse_pos = self.io.mouse_pos
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
                image.render(zoomed_size, zoomed_size, (left, top), (right, bottom))
                imgui.end_tooltip()
            imgui.push_text_wrap_pos()


            with imgui.font(self.big_font):
                imgui.text(game.name)

            self.draw_game_play_button(game, label="󰐊 Play")
            imgui.same_line()
            self.draw_game_open_thread_button(game, label="󰏌 Open Thread")
            imgui.same_line()
            self.draw_game_played_checkbox(game, label="󰈼 Played")
            imgui.same_line()
            imgui.spacing()
            imgui.same_line()
            self.draw_game_installed_checkbox(game, label="󰅢 Installed")

            imgui.text_disabled("Personal Rating:")
            imgui.same_line()
            self.draw_game_rating_widget(game)

            imgui.text_disabled("Version:")
            imgui.same_line()
            imgui.text(game.version)

            imgui.text_disabled("Status:")
            imgui.same_line()
            imgui.text(game.status.name)
            imgui.same_line()
            self.draw_game_status_widget(game)

            imgui.text_disabled("Develoer:")
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

    def draw_games_list(self):
        ghost_column_size = (self.style.frame_padding.x + self.style.cell_padding.x * 2)
        offset = ghost_column_size * self.ghost_columns_enabled_count
        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() - offset)
        if imgui.begin_table(
            "GamesList",
            column=self.game_list_column_count,
            flags=self.game_list_table_flags,
            outer_size_height=-28
        ):
            # Setup
            imgui.table_setup_column("Manual Sort", self.ghost_columns_flags | imgui.TABLE_COLUMN_DEFAULT_HIDE)  # 0
            imgui.table_setup_column("Version", self.ghost_columns_flags)  # 1
            imgui.table_setup_column("Status", self.ghost_columns_flags)  # 2
            imgui.table_setup_column("##Separator", self.ghost_columns_flags | imgui.TABLE_COLUMN_NO_HIDE)  # 3
            # Note: Since I am now heavily relying on ImGui for the dislay options of the games list, and the right click
            # context menu on the column headers does not support adding custom options, I add custom toggles by adding
            # "ghost columns", which are tiny, empty columns at the beginning of the table, and are hidden by rendering
            # the table starting before the content region.
            self.ghost_columns_enabled_count = 1
            manual_sort = imgui.table_get_column_flags(0) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            version_enabled = imgui.table_get_column_flags(1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            status_enabled = imgui.table_get_column_flags(2) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            self.ghost_columns_enabled_count += version_enabled
            self.ghost_columns_enabled_count += status_enabled
            self.ghost_columns_enabled_count += manual_sort
            if manual_sort != self.prev_manual_sort:
                self.prev_manual_sort = manual_sort
                self.require_sort = True
            sort = imgui.TABLE_COLUMN_NO_SORT * manual_sort
            imgui.table_setup_column("Play Button", imgui.TABLE_COLUMN_NO_SORT)  # 4
            imgui.table_setup_column("Engine", imgui.TABLE_COLUMN_DEFAULT_HIDE | sort)  # 5
            imgui.table_setup_column("Name", imgui.TABLE_COLUMN_WIDTH_STRETCH | imgui.TABLE_COLUMN_DEFAULT_SORT | imgui.TABLE_COLUMN_NO_HIDE | sort)  # 6
            imgui.table_setup_column("Developer", imgui.TABLE_COLUMN_DEFAULT_HIDE | sort)  # 7
            imgui.table_setup_column("Last Updated", imgui.TABLE_COLUMN_DEFAULT_HIDE | sort)  # 8
            imgui.table_setup_column("Last Played", imgui.TABLE_COLUMN_DEFAULT_HIDE | sort)  # 9
            imgui.table_setup_column("Added On", imgui.TABLE_COLUMN_DEFAULT_HIDE | sort)  # 10
            imgui.table_setup_column("Played", sort)  # 11
            imgui.table_setup_column("Installed", sort)  # 12
            imgui.table_setup_column("Rating", imgui.TABLE_COLUMN_DEFAULT_HIDE | sort)  # 13
            imgui.table_setup_column("Open Thread", imgui.TABLE_COLUMN_NO_SORT)  # 14
            imgui.table_setup_scroll_freez(0, 1)  # Sticky column headers

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

            # Loop rows
            swap_b = None
            for game_i, id in enumerate(self.sorted_games_ids):
                game: Game = globals.games[id]
                imgui.table_next_row()
                column_i = 3
                # Base row height
                imgui.table_set_column_index(column_i)
                imgui.button(f"##{game.id}_id")
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
                    imgui.text_disabled(game.version)
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
                imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() - self.style.frame_padding.y)
                imgui.selectable(f"##{game.id}_hitbox", False, flags=imgui.SELECTABLE_SPAN_ALL_COLUMNS, height=24)
                # Row click callbacks
                if imgui.begin_popup_context_item(f"##{game.id}_context"):
                    self.draw_game_play_button(game, label="󰐊 Play", selectable=True)
                    self.draw_game_open_thread_button(game, label="󰏌 Open Thread", selectable=True)
                    imgui.spacing()
                    self.draw_game_played_checkbox(game, label="󰈼 Played")
                    self.draw_game_installed_checkbox(game, label="󰅢 Installed")
                    self.draw_game_rating_widget(game)
                    imgui.end_popup()
                if imgui.is_item_focused():
                    if imgui.is_item_clicked():
                        self.game_list_hitbox_click = True
                    if imgui.is_item_active():
                        if not imgui.is_item_hovered():
                            self.game_list_hitbox_click = False
                            if manual_sort:
                                # Drag = swap if in manual sort mode
                                if imgui.get_mouse_drag_delta().y > 0 and game_i != len(self.sorted_games_ids) - 1:
                                    swap_b = game_i + 1
                                elif game_i != 0:
                                    swap_b = game_i - 1
                                swap_a = game_i
                    elif self.game_list_hitbox_click:
                        # Click = open game info popup
                        self.game_list_hitbox_click = False
                        self.current_info_popup_game = game
                        imgui.open_popup("GameInfo")
            # Draw info popup outside loop but in same ImGui context
            self.draw_game_info_popup()
            # Apply swap
            if swap_b is not None:
                imgui.reset_mouse_drag_delta()
                manual_sort_list = globals.settings.manual_sort_list
                manual_sort_list[swap_a], manual_sort_list[swap_b] = manual_sort_list[swap_b], manual_sort_list[swap_a]
                async_thread.run(db.update_settings("manual_sort_list"))
            imgui.end_table()

    def draw_games_grid(self):
        imgui.text("Placeholder")
        if imgui.begin_table(
            "GamesGrid",
            column=4,
            flags=self.game_grid_table_flags,
            outer_size_height=-28
        ):
            imgui.end_table()

    def draw_bottombar(self):
        new_display_mode = None

        if globals.settings.display_mode is DisplayMode.grid:
            imgui.push_style_var(imgui.STYLE_ALPHA, imgui.get_style().alpha *  0.5)
        if imgui.button("󱇘##list_mode"):
            new_display_mode = DisplayMode.list
        if globals.settings.display_mode is DisplayMode.grid:
            imgui.pop_style_var()

        imgui.same_line()
        if globals.settings.display_mode is DisplayMode.list:
            imgui.push_style_var(imgui.STYLE_ALPHA, imgui.get_style().alpha *  0.5)
        if imgui.button("󱇙##grid_mode"):
            new_display_mode = DisplayMode.grid
        if globals.settings.display_mode is DisplayMode.list:
            imgui.pop_style_var()

        if new_display_mode is not None:
            globals.settings.display_mode = new_display_mode
            async_thread.run(db.update_settings("display_mode"))

        imgui.same_line()
        imgui.set_next_item_width(-48)
        imgui.input_text("##filter_add_bar", "", 9999999)
        imgui.same_line()
        if imgui.button("Add!"):
            pass  # TODO: add button functionality

    def start_settings_section(self, name, collapsible=True):
        if collapsible:
            header = imgui.collapsing_header(f"{name}##{name}_header")[0]
        else:
            header = True
        opened = header and imgui.begin_table(f"##{name}_settings", column=2, flags=imgui.TABLE_NO_CLIP)
        if opened:
            imgui.table_setup_column(f"##{name}_setting_name", imgui.TABLE_COLUMN_WIDTH_STRETCH)
            imgui.table_setup_column(f"##{name}_setting_value", imgui.TABLE_COLUMN_WIDTH_FIXED)
            imgui.table_next_row()
            imgui.table_set_column_index(1)
            imgui.invisible_button(f"##{name}_padding", 100, 1)
            imgui.push_item_width(100)
        return opened

    def draw_sidebar(self):
        if imgui.button("Refresh!", height=126, width=-0.1):
            print("aaa")

        imgui.spacing()
        imgui.spacing()
        imgui.text(f"Total games count: {len(globals.games)}")
        imgui.spacing()
        imgui.spacing()

        if imgui.begin_child("Settings", width=0, height=0, border=False) or True:
            set = globals.settings

            if self.start_settings_section("Browser"):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Browser:")
                imgui.same_line()
                self.draw_help_marker("All the options you select here ONLY affect how F95Checker opens links for you, it DOES NOT affect how this tool operates internally. F95Checker DOES NOT interact with your browsers in any meaningful way, it uses a separate session just for itself.")
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
                    if imgui.button("Configure##browser_custom_popup", width=-0.1):
                        imgui.open_popup("browser_custom_settings")
                    size = self.io.display_size
                    imgui.set_next_window_position(size.x / 2, size.y / 2, pivot_x=0.5, pivot_y=0.5)
                    if imgui.begin_popup("browser_custom_settings", flags=self.popup_flags):
                        imgui.text("Executable: ")
                        args_width = 0
                        imgui.same_line()
                        pos = imgui.get_cursor_pos_x()
                        changed, set.browser_custom_executable = imgui.input_text("##browser_custom_executable", set.browser_custom_executable, 9999999)
                        args_width += imgui.calculate_item_width()
                        if changed:
                            async_thread.run(db.update_settings("browser_custom_executable"))
                        imgui.same_line()
                        clicked = imgui.button("󰷏")
                        args_width += 26
                        if clicked:
                            self.current_filepicker = filepicker.FilePicker(title="Select browser executable", start_dir=set.browser_custom_executable)
                        if self.current_filepicker:
                            selected = self.current_filepicker.tick()
                            if selected is not None:
                                set.browser_custom_executable = selected or set.browser_custom_executable
                                async_thread.run(db.update_settings("browser_custom_executable"))
                                self.current_filepicker = None
                        imgui.text("Arguments: ")
                        imgui.same_line()
                        imgui.set_cursor_pos_x(pos)
                        imgui.set_next_item_width(args_width + self.style.item_spacing.x)
                        changed, set.browser_custom_arguments = imgui.input_text("##browser_custom_arguments", set.browser_custom_arguments, 9999999)
                        if changed:
                            async_thread.run(db.update_settings("browser_custom_arguments"))
                        imgui.end_popup()
                else:
                    imgui.table_next_row()
                    imgui.table_next_column()
                    imgui.text("Use private mode:")
                    imgui.table_next_column()
                    imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + 76)
                    changed, value = imgui.checkbox("##browser_private", set.browser_private)
                    if changed:
                        set.browser_private = value
                        async_thread.run(db.update_settings("browser_private"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Download pages:")
                imgui.same_line()
                self.draw_help_marker("With this enabled links will first be downloaded by F95Checker and then opened as simple HTML files in your browser. This might be useful if you use private mode because the page will load as if you were logged in, allowing you to see links and spoiler content without actually logging in.")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + 76)
                changed, value = imgui.checkbox("##browser_html", set.browser_html)
                if changed:
                    set.browser_html = value
                    async_thread.run(db.update_settings("browser_html"))

                imgui.end_table()
                imgui.spacing()

            if self.start_settings_section("Refresh"):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Refresh completed games:")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + 76)
                changed, value = imgui.checkbox("##refresh_completed_games", set.refresh_completed_games)
                if changed:
                    set.refresh_completed_games = value
                    async_thread.run(db.update_settings("refresh_completed_games"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Refresh workers:")
                imgui.same_line()
                self.draw_help_marker("Each game that needs to be checked requires that a connection to F95Zone happens. Each worker can handle 1 connection at a time. Having more workers means more connections happen simultaneously, but having too many will freeze the program. In most cases 20 workers is a good compromise.")
                imgui.table_next_column()
                changed, value = imgui.input_int("##refresh_workers", set.refresh_workers)
                set.refresh_workers = min(max(value, 1), 100)
                if changed:
                    async_thread.run(db.update_settings("refresh_workers"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Request timeout:")
                imgui.same_line()
                self.draw_help_marker("To check for updates for a game F95Checker sends a web request to F95Zone. However this can sometimes go wrong. The timeout is the maximum amount of seconds that a request can try to connect for before it fails. A timeout 10-30 seconds is most typical.")
                imgui.table_next_column()
                changed, value = imgui.input_int("##request_timeout", set.request_timeout)
                set.request_timeout = min(max(value, 1), 120)
                if changed:
                    async_thread.run(db.update_settings("request_timeout"))

                imgui.end_table()
                imgui.spacing()

            if self.start_settings_section("Startup"):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Refresh at startup:")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + 76)
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
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + 76)
                changed, value = imgui.checkbox("##start_in_tray", set.start_in_tray)
                if changed:
                    set.start_in_tray = value
                    async_thread.run(db.update_settings("start_in_tray"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Start with system:")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + 76)
                changed, value = imgui.checkbox("##start_with_system", set.start_with_system)
                if changed:
                    set.start_with_system = value
                    async_thread.run(db.update_settings("start_with_system"))

                imgui.end_table()
                imgui.spacing()

            if self.start_settings_section("Zoom"):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Zoom when hovering images:")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + 76)
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
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + 76)
                changed, value = imgui.checkbox("##zoom_region", set.zoom_region)
                if changed:
                    set.zoom_region = value
                    async_thread.run(db.update_settings("zoom_region"))

                imgui.end_table()
                imgui.spacing()

            if self.start_settings_section("Misc"):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("BG refresh mins:")
                imgui.same_line()
                self.draw_help_marker("When F95Checker is minimized in background mode it automatically refreshes periodically. This controls how often (in minutes) this happens.")
                imgui.table_next_column()
                changed, value = imgui.input_int("##tray_refresh_interval", set.tray_refresh_interval)
                set.tray_refresh_interval = min(max(value, 15), 720)
                if changed:
                    async_thread.run(db.update_settings("tray_refresh_interval"))

                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Keep game image:")
                imgui.same_line()
                self.draw_help_marker(f"When a game receives an update F95Checker downloads the header image again in case it was updated. This setting makes it so the old image is kept and no new image is downloaded. This is useful in case you want to have custom images for your games (you can edit the images manually at {globals.data_path / 'images'}).")
                imgui.table_next_column()
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + 76)
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
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + 76)
                changed, value = imgui.checkbox("##select_executable_after_add", set.select_executable_after_add)
                if changed:
                    set.select_executable_after_add = value
                    async_thread.run(db.update_settings("select_executable_after_add"))

                imgui.end_table()
                imgui.spacing()

            if self.start_settings_section("Minimize", collapsible=False):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text("Switch to BG mode:")
                imgui.table_next_column()
                if imgui.button("Minimize##minimize", width=-0.1):
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
