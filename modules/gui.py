from imgui.integrations.glfw import GlfwRenderer
from PyQt6 import QtCore, QtGui, QtWidgets
import OpenGL.GL as gl
from PIL import Image
import configparser
import platform
import OpenGL
import imgui
import glfw
import sys

from modules import async_thread
from modules.structs import *
from modules.widgets import *
from modules import globals
from modules import db

imgui.io = None
imgui.style = None


class MainGUI():
    def __init__(self):
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
        self.game_grid_cell_flags: int = (
            imgui.WINDOW_NO_SCROLLBAR |
            imgui.WINDOW_NO_SCROLL_WITH_MOUSE
        )
        self.game_hitbox_drag_drop_flags: int = (
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
        imgui.io = imgui.get_io()
        self.ini_file_name = str(globals.data_path / "imgui.ini").encode()
        imgui.io.ini_file_name = self.ini_file_name  # Cannot set directly because reference gets lost due to a bug
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
        self.window: glfw._GLFWwindow = impl_glfw_init(*size, "F95Checker")
        icon_path = globals.self_path / "resources/icons/icon.png"
        self.icon_texture = ImGuiImage(icon_path)
        glfw.set_window_icon(self.window, 1, Image.open(icon_path))
        self.impl = GlfwRenderer(self.window)
        glfw.set_window_iconify_callback(self.window, self.minimize)
        self.refresh_fonts()

        # Load style configuration
        imgui.style = imgui.get_style()
        imgui.style.item_spacing = (imgui.style.item_spacing.y, imgui.style.item_spacing.y)
        imgui.style.colors[imgui.COLOR_MODAL_WINDOW_DIM_BACKGROUND] = (0, 0, 0, 0.5)
        imgui.style.scrollbar_size = 12
        imgui.style.window_rounding = imgui.style.frame_rounding = imgui.style.tab_rounding  = \
        imgui.style.child_rounding = imgui.style.grab_rounding = imgui.style.popup_rounding  = \
        imgui.style.scrollbar_rounding = globals.settings.style_corner_radius

    def refresh_fonts(self):
        imgui.io.fonts.clear()
        win_w, win_h = glfw.get_window_size(self.window)
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        font_scaling_factor = max(fb_w / win_w, fb_h / win_h)
        imgui.io.font_global_scale = 1 / font_scaling_factor
        self.size_mult = globals.settings.style_scaling
        imgui.io.fonts.add_font_from_file_ttf(
            str(globals.self_path / "resources/fonts/Karla-Regular.ttf"),
            18 * font_scaling_factor * self.size_mult,
            font_config=imgui.core.FontConfig(oversample_h=3, oversample_v=3)
        )
        imgui.io.fonts.add_font_from_file_ttf(
            str(globals.self_path / "resources/fonts/materialdesignicons-webfont.ttf"),
            18 * font_scaling_factor * self.size_mult,
            font_config=imgui.core.FontConfig(merge_mode=True, glyph_offset_y=1),
            glyph_ranges=imgui.core.GlyphRanges([0xf0000, 0xf2000, 0])
        )
        self.big_font = imgui.io.fonts.add_font_from_file_ttf(
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
                if (size := imgui.io.display_size) != self.prev_size:
                    imgui.set_next_window_size(*size, imgui.ALWAYS)

                imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0)
                imgui.begin("F95Checker", closable=False, flags=self.window_flags)
                imgui.pop_style_var()
                sidebar_size = self.scaled(self.sidebar_size)

                imgui.begin_child("##main_frame", width=-sidebar_size)
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
                imgui.begin_child("##sidebar_frame", width=sidebar_size - 1, height=-text_size.y - _3)
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

                if (size := imgui.io.display_size) != self.prev_size:
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
            imgui.push_text_wrap_pos(min(imgui.get_font_size() * 35, imgui.io.display_size.x))
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

    def get_game_version_text(self, game: Game):
        if game.installed and game.installed != game.version:
            return f"Installed: {game.installed}  -  Latest: {game.version}"
        else:
            return game.version

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
        size = imgui.io.display_size
        height = size.y * 0.9
        width = min(size.x * 0.9, height * self.scaled(0.9))
        imgui.set_next_window_size(width, height)
        center_next_window()
        if imgui.begin_popup_modal("Game info", True, flags=self.popup_flags)[0]:
            close_popup_clicking_outside()
            game = self.current_info_popup_game

            # Image
            image = game.image
            aspect_ratio = image.height / image.width
            avail = imgui.get_content_region_available()
            width = min(avail.x, image.width)
            height = min(width * aspect_ratio, image.height)
            if height > (new_height := avail.y * self.scaled(0.4)):
                height = new_height
                width = height * (1 / aspect_ratio)
            if width < avail.x:
                imgui.set_cursor_pos_x((avail.x - width + imgui.style.scrollbar_size) / 2)
            image_pos = imgui.get_cursor_screen_pos()
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
                    size = globals.settings.zoom_size
                    zoom = globals.settings.zoom_amount
                    zoomed_size = size * zoom
                    mouse_pos = imgui.io.mouse_pos
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
                    image.render(zoomed_size, zoomed_size, (left, top), (right, bottom), rounding=globals.settings.style_corner_radius)
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
            imgui.text(self.get_game_version_text(game))

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
        size = imgui.io.display_size
        imgui.set_next_window_size_constraints((0, 0), (size.x * 0.9, size.y * 0.9))
        center_next_window()
        if imgui.begin_popup_modal("About F95Checker", True, flags=self.popup_flags | imgui.WINDOW_ALWAYS_AUTO_RESIZE)[0]:
            close_popup_clicking_outside()
            _50 = self.scaled(50)
            _210 = self.scaled(210)
            imgui.begin_group()
            imgui.dummy(_50, _210)
            imgui.same_line()
            self.icon_texture.render(_210, _210, rounding=globals.settings.style_corner_radius)
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
            btn_width = (width - 2 * imgui.style.item_spacing.x) / 3
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
        ghost_column_size = (imgui.style.frame_padding.x + imgui.style.cell_padding.x * 2)
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
            manual_sort     = imgui.table_get_column_flags(0) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            version_enabled = imgui.table_get_column_flags(1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            status_enabled  = imgui.table_get_column_flags(2) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            self.ghost_columns_enabled_count += version_enabled
            self.ghost_columns_enabled_count += status_enabled
            self.ghost_columns_enabled_count += manual_sort
            can_sort = imgui.TABLE_COLUMN_NO_SORT * manual_sort
            # Regular columns
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

            # Enabled columns
            column_i = 3
            play_button  = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and column_i
            engine       = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and column_i
            name = column_i = column_i + 1  # Name is always enabled
            developer    = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and column_i
            last_updated = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and column_i
            last_played  = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and column_i
            added_on     = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and column_i
            played       = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and column_i
            installed    = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and column_i
            rating       = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and column_i
            open_thread  = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and column_i

            # Headers
            imgui.table_next_row(imgui.TABLE_ROW_HEADERS)
            for i in range(self.game_list_column_count):
                imgui.table_set_column_index(i)
                column_name = imgui.table_get_column_name(i)
                if i in (0, 1, 2, 4, 14):  # Hide name for small and ghost columns
                    column_name = "##" + column_name
                elif i == 6:  # Name
                    if version_enabled:
                        column_name += "   -   Version"
                    if status_enabled:
                        column_name += "   -   Status"
                elif i == 11:  # Played
                    column_name = "󰈼"
                elif i == 12:  # Installed
                    column_name = "󰅢"
                imgui.table_header(column_name)

            # Sorting
            sort_specs = imgui.table_get_sort_specs()
            self.sort_games(sort_specs, manual_sort)

            # Loop rows
            frame_height = imgui.get_frame_height()
            for game_i, id in enumerate(self.sorted_games_ids):
                game: Game = globals.games[id]
                imgui.table_next_row()
                # Base row height
                imgui.table_set_column_index(3)
                if not imgui.is_rect_visible(imgui.io.display_size.x, frame_height):
                    # Skip if outside view
                    imgui.dummy(0, frame_height)
                    continue
                imgui.button(f"##{game.id}_id", width=0.1)  # Button because it aligns the following text calls to center vertically
                # Play Button
                if play_button:
                    imgui.table_set_column_index(play_button)
                    self.draw_game_play_button(game, label="󰐊")
                # Engine
                if engine:
                    imgui.table_set_column_index(engine)
                    self.draw_game_engine_widget(game)
                # Name
                imgui.table_set_column_index(name)
                imgui.text(game.name)
                if version_enabled:
                    imgui.same_line()
                    imgui.text_disabled(self.get_game_version_text(game))
                if status_enabled:
                    imgui.same_line()
                    self.draw_game_status_widget(game)
                # Developer
                if developer:
                    imgui.table_set_column_index(developer)
                    imgui.text(game.developer)  # TODO: fetch game developers
                # Last Updated
                if last_updated:
                    imgui.table_set_column_index(last_updated)
                    imgui.text(game.last_updated.display)
                # Last Played
                if last_played:
                    imgui.table_set_column_index(last_played)
                    imgui.text(game.last_played.display)
                # Added On
                if added_on:
                    imgui.table_set_column_index(added_on)
                    imgui.text(game.added_on.display)
                # Played
                if played:
                    imgui.table_set_column_index(played)
                    self.draw_game_played_checkbox(game)
                # Installed
                if installed:
                    imgui.table_set_column_index(installed)
                    self.draw_game_installed_checkbox(game)
                # Rating
                if rating:
                    imgui.table_set_column_index(rating)
                    self.draw_game_rating_widget(game)
                # Open Thread
                if open_thread:
                    imgui.table_set_column_index(open_thread)
                    self.draw_game_open_thread_button(game, label="󰏌")
                # Row hitbox
                imgui.same_line()
                imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() - imgui.style.frame_padding.y)
                imgui.selectable(f"##{game.id}_hitbox", False, flags=imgui.SELECTABLE_SPAN_ALL_COLUMNS, height=frame_height)
                self.handle_game_hitbox_events(game, game_i, manual_sort)

            imgui.end_table()

    def draw_games_grid(self):
        # Hack: get sort and column specs for list mode in grid mode
        pos = imgui.get_cursor_pos_y()
        if imgui.begin_table(
            "##game_list",
            column=self.game_list_column_count,
            flags=self.game_list_table_flags,
            outer_size_height=1
        ):
            # Sorting
            sort_specs = imgui.table_get_sort_specs()
            manual_sort     = imgui.table_get_column_flags(0) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            self.sort_games(sort_specs, manual_sort)
            # Enabled attributes
            version_enabled = imgui.table_get_column_flags(1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            status_enabled  = imgui.table_get_column_flags(2) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            column_i = 3
            play_button     = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            engine          = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            column_i += 1  # Name
            developer       = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            last_updated    = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            last_played     = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            added_on        = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            played          = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            installed       = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            rating          = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            open_thread     = imgui.table_get_column_flags(column_i := column_i + 1) & imgui.TABLE_COLUMN_IS_ENABLED and 1
            button_row = play_button or open_thread or played or installed
            data_rows = engine + developer + last_updated + last_played + added_on + rating
            imgui.end_table()
        imgui.set_cursor_pos_y(pos)

        column_count = globals.settings.grid_columns
        padding = self.scaled(10)
        imgui.push_style_var(imgui.STYLE_CELL_PADDING, (padding, padding))
        min_width = (
            imgui.style.item_spacing.x * 10 +  # Padding * (2 left + 2 right + 3 between items + idk)
            imgui.style.frame_padding.x * 4 +  # Button padding * 2 sides * 2 buttons
            imgui.style.item_inner_spacing.x * 2 +  # Checkbox and label spacing * 2 checkboxes
            imgui.get_frame_height() * 2 +  # Checkbox height = width * 2 checkboxes
            imgui.calc_text_size("󰐊 Play󰏌 Thread󰈼󰅢").x  # Text
        )
        avail = imgui.get_content_region_available_width()
        while column_count > 1 and (avail - (column_count + 1) * padding) / column_count < min_width:
            column_count -= 1
        if imgui.begin_table(
            "##game_grid",
            column=column_count,
            flags=self.game_grid_table_flags,
            outer_size_height=-imgui.get_frame_height_with_spacing()  # Bottombar
        ):
            # Setup
            for i in range(column_count):
                imgui.table_setup_column(f"##game_grid_{i}", imgui.TABLE_COLUMN_WIDTH_STRETCH)
            img_ratio = globals.settings.grid_image_ratio
            width = None
            height = None
            _24 = self.scaled(24)
            draw_list = imgui.get_window_draw_list()
            bg_col = imgui.get_color_u32_rgba(*imgui.style.colors[imgui.COLOR_TABLE_ROW_BACKGROUND_ALT])
            rounding = globals.settings.style_corner_radius
            indent = imgui.style.item_spacing.x * 2
            frame_height = imgui.get_frame_height()
            data_height = data_rows * imgui.get_text_line_height_with_spacing()

            # Loop cells
            for game_i, id in enumerate(self.sorted_games_ids):
                game: Game = globals.games[id]
                imgui.table_next_column()

                # Setup pt2
                if width is None:
                    width = imgui.get_content_region_available_width()
                    height = width / img_ratio

                # Cell
                pos = imgui.get_cursor_pos()
                imgui.begin_group()
                # Image
                game.image.render(width, height, *game.image.crop_to_ratio(img_ratio), rounding=rounding, flags=imgui.DRAW_ROUND_CORNERS_TOP)
                # Setup pt3
                imgui.indent(indent)
                imgui.push_text_wrap_pos()
                imgui.spacing()

                # Name
                name = game.name
                did_wrap = imgui.calc_text_size(name).x > imgui.get_content_region_available_width()
                imgui.text(name)
                if version_enabled:
                    imgui.same_line()
                    version = self.get_game_version_text(game)
                    if did_wrap or imgui.calc_text_size(version).x > imgui.get_content_region_available_width() - _24:
                        imgui.dummy(0, 0)
                    imgui.text_disabled(version)
                if status_enabled:
                    imgui.same_line()
                    self.draw_game_status_widget(game)
                if button_row:
                    if imgui.is_rect_visible(width, frame_height):
                        # Play Button
                        did_newline = False
                        if play_button:
                            if did_newline:
                                imgui.same_line()
                            self.draw_game_play_button(game, label="󰐊 Play")
                            did_newline = True
                        # Open Thread
                        if open_thread:
                            if did_newline:
                                imgui.same_line()
                            self.draw_game_open_thread_button(game, label="󰏌 Thread")
                            did_newline = True
                        # Played
                        if played:
                            if did_newline:
                                imgui.same_line()
                            self.draw_game_played_checkbox(game, label="󰈼")
                            did_newline = True
                        # Installed
                        if installed:
                            if did_newline:
                                imgui.same_line()
                            self.draw_game_installed_checkbox(game, label="󰅢")
                            did_newline = True
                    else:
                        # Skip if outside view
                        imgui.dummy(0, frame_height)
                if data_rows:
                    if imgui.is_rect_visible(width, data_height):
                        # Engine
                        if engine:
                            imgui.text_disabled("Engine:")
                            imgui.same_line()
                            self.draw_game_engine_widget(game)
                        # Developer
                        if developer:
                            imgui.text_disabled("Developer:")
                            imgui.same_line()
                            imgui.text(game.developer)  # TODO: fetch game developers
                        # Last Updated
                        if last_updated:
                            imgui.text_disabled("Last Updated:")
                            imgui.same_line()
                            imgui.text(game.last_updated.display)
                        # Last Played
                        if last_played:
                            imgui.text_disabled("Last Played:")
                            imgui.same_line()
                            imgui.text(game.last_played.display)
                        # Added On
                        if added_on:
                            imgui.text_disabled("Added On:")
                            imgui.same_line()
                            imgui.text(game.added_on.display)
                        # Rating
                        if rating:
                            imgui.text_disabled("Rating:")
                            imgui.same_line()
                            self.draw_game_rating_widget(game)
                    else:
                        # Skip if outside view
                        imgui.dummy(0, data_height)
                # Cell hitbox
                imgui.pop_text_wrap_pos()
                imgui.spacing()
                imgui.spacing()
                imgui.end_group()
                imgui.set_cursor_pos(pos)
                cell_height = imgui.get_item_rect_size().y
                if imgui.is_rect_visible(width, cell_height):
                    # Skip if outside view
                    imgui.invisible_button(f"##{game.id}_hitbox", width, cell_height)
                    self.handle_game_hitbox_events(game, game_i, manual_sort)
                    pos = imgui.get_item_rect_min()
                    pos2 = imgui.get_item_rect_max()
                    draw_list.add_rect_filled(*pos, *pos2, bg_col, rounding=rounding, flags=imgui.DRAW_ROUND_CORNERS_ALL)

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
        imgui.set_next_item_width(-(imgui.calc_text_size("Add!").x + 2 * imgui.style.frame_padding.x) - imgui.style.item_spacing.x)
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
            game.image.render(width, height, *game.image.crop_to_ratio(width / height), rounding=globals.settings.style_corner_radius)
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
        imgui.begin_child("Settings")

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

        if self.start_settings_section("Grid view", right_width):
            imgui.table_next_row()
            imgui.table_next_column()
            imgui.text("Max columns:")
            imgui.same_line()
            self.draw_help_marker("How many games will show in each row in grid view. It is a maximum value because when there is insufficient "
                                    "space to show all these columns, the number will be internally reduced to render each grid cell properly.")
            imgui.table_next_column()
            changed, value = imgui.input_int("##grid_columns", set.grid_columns)
            set.grid_columns = min(max(value, 1), 10)
            if changed:
                async_thread.run(db.update_settings("grid_columns"))

            imgui.table_next_row()
            imgui.table_next_column()
            imgui.text("Image ratio:")
            imgui.same_line()
            self.draw_help_marker("The aspect ratio to use for images in grid view. This is width / height, AKA how many times wider the image "
                                    "is compared to its height. A ratio of 3 would for example mean 3:1 in common aspect ratio terms. Default is 3.")
            imgui.table_next_column()
            changed, value = imgui.input_float("##grid_image_ratio", set.grid_image_ratio, step=0.1, step_fast=0.5)
            set.grid_image_ratio = min(max(value, 0.5), 5)
            if changed:
                async_thread.run(db.update_settings("grid_image_ratio"))

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

            imgui.table_next_row()
            imgui.table_next_column()
            imgui.text("Corner radius:")
            imgui.table_next_column()
            changed, value = imgui.input_int("##style_corner_radius", set.style_corner_radius)
            set.style_corner_radius = min(max(value, 0), 6)
            if changed:
                imgui.style.window_rounding = imgui.style.frame_rounding = imgui.style.tab_rounding = \
                imgui.style.child_rounding = imgui.style.grab_rounding = imgui.style.popup_rounding = \
                imgui.style.scrollbar_rounding = globals.settings.style_corner_radius
                async_thread.run(db.update_settings("style_corner_radius"))

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
