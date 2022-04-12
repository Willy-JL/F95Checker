from imgui.integrations.glfw import GlfwRenderer
from PyQt6 import QtCore, QtGui, QtWidgets
import OpenGL.GL as gl
from PIL import Image
import configparser
import pathlib
import numpy
import imgui
import glfw
import sys

from modules import async_thread
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
        self.require_sort = True
        self.sorted_games_ids = []
        self.prev_manual_sort = 0
        self.current_info_popup_game = 0
        self.game_list_hitbox_click = False
        self.current_info_popup_image = None
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
            size = (int(x) for x in config.get("Window][F95Checker", "Size").split(","))
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
        self.impl.refresh_font_texture()

    def load_image(self, path: str | pathlib.Path):
        img = Image.open(path)
        if img.mode != "RGB":
            img = img.convert(mode="RGB")
        img_data = img.getdata()
        img_array = numpy.array(img_data, numpy.uint8)
        texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGB, img.width, img.height, 0, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, img_array)
        return GLImage(texture_id, img.width, img.height)

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

                imgui.set_next_window_position(0, 0, imgui.ONCE)
                if (size := self.impl.io.display_size) != self.prev_size:
                    imgui.set_next_window_size(*size, imgui.ALWAYS)
                    self.prev_size = size

                if imgui.begin("F95Checker", closable=False, flags=self.window_flags) or True:
                    if imgui.begin_child("Main", width=-self.sidebar_size, height=0, border=False) or True:
                        if globals.settings.display_mode is DisplayMode.list:
                            self.draw_games_list()
                        elif globals.settings.display_mode is DisplayMode.grid:
                            self.draw_games_grid()
                        self.draw_bottombar()
                    imgui.end_child()
                    imgui.same_line()
                    if imgui.begin_child("Sidebar", width=self.sidebar_size, height=0, border=False) or True:
                        self.draw_sidebar()
                    imgui.end_child()
                imgui.end()

                imgui.render()
                self.impl.render(imgui.get_draw_data())
            glfw.swap_buffers(self.window)  # Also waits idle time, must run always to avoid useless cycles
        self.impl.shutdown()
        glfw.terminate()

    def draw_game_play_button(self, game: Game, label:str = ""):
        if imgui.button(f"{label}##{game.id}_play_button"):
            pass  # TODO: game launching

    def draw_game_engine_widget(self, game: Game):
        col = (*EngineColors[game.engine.value], 1)
        imgui.push_style_color(imgui.COLOR_BUTTON, *col)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *col)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *col)
        imgui.small_button(f"{game.engine.name}##{game.id}_engine")
        imgui.pop_style_color(3)

    def draw_game_status_widget(self, game: Game):
        if game.status is Status.Completed:
            imgui.text_colored("󰄳", 0.00, 0.85, 0.00)
        elif game.status is Status.OnHold:
            imgui.text_colored("󰏥", 0.00, 0.50, 0.95)
        elif game.status is Status.Abandoned:
            imgui.text_colored("󰅙", 0.87, 0.20, 0.20)
        else:
            imgui.text("")

    def draw_game_played_checkbox(self, game: Game, label:str = ""):
        changed, game.played = imgui.checkbox(f"{label}##{game.id}_played", game.played)
        if changed:
            async_thread.run(db.update_game(game, "played"))
            self.require_sort = True

    def draw_game_installed_checkbox(self, game: Game, label: str = ""):
        changed, installed = imgui.checkbox(f"{label}##{game.id}_installed", game.installed == game.version)
        if changed:
            if installed:
                game.installed = game.version
            else:
                game.installed = ""
            async_thread.run(db.update_game(game, "installed"))
            self.require_sort = True

    def draw_game_rating_widget(self, game: Game):
        imgui.push_style_color(imgui.COLOR_BUTTON, 0, 0, 0, 0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0, 0, 0, 0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0, 0, 0, 0)
        imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (0, 0))
        imgui.push_style_var(imgui.STYLE_ITEM_SPACING, (0, 0))
        for i in range(1, 6):
            label = "󰓎"
            if i > game.rating:
                label = "󰓒"
            if imgui.small_button(f"{label}##{game.id}_rating_{i}"):
                game.rating = i
                async_thread.run(db.update_game(game, "rating"))
                self.require_sort = True
            imgui.same_line()
        imgui.pop_style_color(3)
        imgui.pop_style_var(2)
        imgui.text("")

    def draw_game_open_thread_button(self, game: Game, label: str = ""):
        if imgui.button(f"{label}##{game.id}_open_thread"):
            pass  # TODO: open game threads

    def draw_game_notes_widget(self, game: Game):
        changed, new_notes = imgui.input_text_multiline(
            f"##{game.id}_notes",
            value=game.notes,
            buffer_length=9999999,
            width=imgui.get_content_region_available_width(),
            height=0
        )
        if changed:
            game.notes = new_notes
            async_thread.run(db.update_game(game, "notes"))

    def draw_game_tags_widget(self, game: Game):
        imgui.text("")
        col = (0.3, 0.3, 0.3, 1)
        imgui.push_style_color(imgui.COLOR_BUTTON, *col)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *col)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *col)
        for tag in game.tags:
            imgui.same_line()
            if imgui.get_content_region_available_width() < imgui.calc_text_size(tag.name).x + 20:
                imgui.text("")
            imgui.small_button(tag.name)
        imgui.pop_style_color(3)

    def draw_game_info_popup(self):
        avail = self.io.display_size
        imgui.set_next_window_position(avail.x / 2, avail.y / 2, imgui.ALWAYS, 0.5, 0.5)
        imgui.set_next_window_size(min(avail.x * 0.9, 600), min(avail.y * 0.9, 800))
        if imgui.begin_popup("GameInfo", flags=self.popup_flags):
            game = self.current_info_popup_game
            imgui.push_text_wrap_pos()

            image = self.current_info_popup_image
            aspect_ratio = image.height / image.width
            avail = imgui.get_content_region_available()
            width = avail.x
            height = width * aspect_ratio
            if height > (new_height := avail.y * 0.3):
                height = new_height
                width = height * (1 / aspect_ratio)
                imgui.set_cursor_pos_x((avail.x - width + self.style.scrollbar_size) / 2)
            imgui.image(image.texture_id, width, height)


            imgui.text(game.name)  # FIXME: title text style

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
                if imgui.is_item_focused():
                    if imgui.is_item_clicked():
                        self.game_list_hitbox_click = True
                    if imgui.is_item_active():
                        if manual_sort and not imgui.is_item_hovered():
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
                        self.current_info_popup_image = self.load_image(globals.data_path / f"images/{game.id}.jpg")
                        imgui.open_popup("GameInfo")
            # Draw info popup outside loop but in same ImGui context
            self.draw_game_info_popup()
            # Apply swap
            if swap_b is not None:
                imgui.reset_mouse_drag_delta()
                self.game_list_hitbox_click = False
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
            imgui.push_style_color(imgui.COLOR_BUTTON, 0, 0, 0, 0)
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0, 0, 0, 0)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0, 0, 0, 0)
        if imgui.button("󱇘##list_mode"):
            new_display_mode = DisplayMode.list
        if globals.settings.display_mode is DisplayMode.grid:
            imgui.pop_style_color(3)

        imgui.same_line()
        if globals.settings.display_mode is DisplayMode.list:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0, 0, 0, 0)
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0, 0, 0, 0)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0, 0, 0, 0)
        if imgui.button("󱇙##grid_mode"):
            new_display_mode = DisplayMode.grid
        if globals.settings.display_mode is DisplayMode.list:
            imgui.pop_style_color(3)

        if new_display_mode is not None:
            globals.settings.display_mode = new_display_mode
            async_thread.run(db.update_settings("display_mode"))

        imgui.same_line()
        imgui.set_next_item_width(-48)
        imgui.input_text("##filter_add_bar", "", 999)
        imgui.same_line()
        if imgui.button("Add!"):
            pass  # TODO: add button functionality

    def draw_sidebar(self):
        if imgui.button("Refresh!"):
            print("aaa")
        for x in range(1, 7):
            imgui.checkbox(f"some setting {x}", x % 2 == 0)
        for x in range(1, 6):
            imgui.text(f"some button {x}")
            imgui.same_line()
            imgui.button(f"{x}")
        if imgui.button("Minimize"):
            self.minimize()


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
