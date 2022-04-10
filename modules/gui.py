from imgui.integrations.glfw import GlfwRenderer
from PyQt6 import QtCore, QtGui, QtWidgets
import OpenGL.GL as gl
from PIL import Image
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
    def __init__(self):
        self.visible = True
        self.prev_size = 0, 0
        self.window_flags = (
            imgui.WINDOW_NO_MOVE |
            imgui.WINDOW_NO_RESIZE |
            imgui.WINDOW_NO_COLLAPSE |
            imgui.WINDOW_NO_TITLE_BAR |
            imgui.WINDOW_NO_SCROLLBAR |
            imgui.WINDOW_NO_SCROLL_WITH_MOUSE
        )
        self.sidebar_size = 269
        self.game_list_column_count = 15
        self.game_list_table_flags = (
            imgui.TABLE_SCROLL_Y |
            imgui.TABLE_HIDEABLE |
            imgui.TABLE_SORTABLE |
            imgui.TABLE_REORDERABLE |
            imgui.TABLE_ROW_BACKGROUND |
            imgui.TABLE_SIZING_FIXED_FIT |
            imgui.TABLE_NO_HOST_EXTEND_Y
        )
        # Note: Since I am now heavily relying on ImGui for the
        # dislay options of the games list, and the right click
        # context menu on the column headers does not support
        # adding custom options, I add custom toggles by adding
        # "ghost columns", which are tiny, empty columns at the
        # beginning of the table, and are hidden by rendering
        # the table starting before the content region.
        self.ghost_columns_enabled_count = 0
        self.ghost_columns_flags = (
            imgui.TABLE_COLUMN_NO_SORT |
            imgui.TABLE_COLUMN_NO_REORDER |
            imgui.TABLE_COLUMN_NO_HEADER_WIDTH
        )
        self.require_sort = True
        self.sorted_games_ids = []
        self.prev_manual_sort = False

        self.qt_app = QtWidgets.QApplication(sys.argv)
        self.qt_loop = QtCore.QEventLoop()
        self.tray = TrayIcon(self)

        imgui.create_context()
        io = imgui.get_io()

        self.ini_file_name = str(globals.data_path / "imgui.ini").encode()
        io.ini_file_name = self.ini_file_name

        self.window = impl_glfw_init(1280, 720, "F95Checker")  # TODO: remember window size
        glfw.set_window_icon(self.window, 1, Image.open("resources/icons/icon.png"))
        self.impl = GlfwRenderer(self.window)
        glfw.set_window_iconify_callback(self.window, self.minimize)

        io.fonts.clear()
        win_w, win_h = glfw.get_window_size(self.window)
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        font_scaling_factor = max(float(fb_w) / win_w, float(fb_h) / win_h)
        io.font_global_scale = 1 / font_scaling_factor
        io.fonts.add_font_from_file_ttf(
            str(globals.self_path / "resources/fonts/Karla-Regular.ttf"),
            18 * font_scaling_factor,
            font_config=imgui.core.FontConfig(oversample_h=3, oversample_v=3)
        )
        io.fonts.add_font_from_file_ttf(
            str(globals.self_path / "resources/fonts/materialdesignicons-webfont.ttf"),
            18 * font_scaling_factor,
            font_config=imgui.core.FontConfig(merge_mode=True, glyph_offset_y=1),
            glyph_ranges=imgui.core.GlyphRanges([0xf0000, 0xf2000, 0])
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

                imgui.set_next_window_position(0, 0, imgui.ONCE)
                if (size := self.impl.io.display_size) != self.prev_size:
                    imgui.set_next_window_size(*size, imgui.ALWAYS)
                    self.prev_size = size

                with imgui.begin("F95Checker", closable=False, flags=self.window_flags):
                    with imgui.begin_child("Main", width=-self.sidebar_size, height=0, border=False):
                        if globals.settings.display_mode is DisplayMode.list:
                            self.draw_games_list()
                        elif globals.settings.display_mode is DisplayMode.grid:
                            self.draw_games_grid()
                        self.draw_bottombar()
                    imgui.same_line()
                    with imgui.begin_child("Sidebar", width=self.sidebar_size, height=0, border=False):
                        self.draw_sidebar()

                # imgui.show_demo_window()

                imgui.render()
                self.impl.render(imgui.get_draw_data())

            glfw.swap_buffers(self.window)  # Also waits idle time, must run always to avoid useless cycles

        self.impl.shutdown()
        glfw.terminate()

    def draw_games_list(self):
        style = imgui.get_style()
        ghost_column_size = (style.frame_padding.x + style.cell_padding.x * 2)
        offset = ghost_column_size * self.ghost_columns_enabled_count
        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() - offset)
        with imgui.begin_table(
            "GamesList",
            column=self.game_list_column_count,
            flags=self.game_list_table_flags,
            outer_size_width=imgui.get_content_region_available_width(),
            outer_size_height=-28
        ):
            # Setup
            imgui.table_setup_column("Manual Sort", self.ghost_columns_flags | imgui.TABLE_COLUMN_DEFAULT_HIDE)  # 0
            imgui.table_setup_column("Version", self.ghost_columns_flags)  # 1
            imgui.table_setup_column("Status", self.ghost_columns_flags)  # 2
            imgui.table_setup_column("##Separator", self.ghost_columns_flags | imgui.TABLE_COLUMN_NO_HIDE)  # 3
            self.ghost_columns_enabled_count = 1
            manual_sort = bool(imgui.table_get_column_flags(0) & imgui.TABLE_COLUMN_IS_ENABLED)
            version_enabled = bool(imgui.table_get_column_flags(1) & imgui.TABLE_COLUMN_IS_ENABLED)
            status_enabled = bool(imgui.table_get_column_flags(2) & imgui.TABLE_COLUMN_IS_ENABLED)
            self.ghost_columns_enabled_count += int(version_enabled)
            self.ghost_columns_enabled_count += int(status_enabled)
            self.ghost_columns_enabled_count += int(manual_sort)
            if manual_sort != self.prev_manual_sort:
                self.prev_manual_sort = manual_sort
                self.require_sort = True
            sort = imgui.TABLE_COLUMN_NO_SORT * int(manual_sort)
            imgui.table_setup_column("Play Button", imgui.TABLE_COLUMN_NO_SORT)  # 4
            imgui.table_setup_column("Engine", imgui.TABLE_COLUMN_DEFAULT_HIDE | sort)  # 5
            imgui.table_setup_column("Name", imgui.TABLE_COLUMN_WIDTH_STRETCH | imgui.TABLE_COLUMN_DEFAULT_SORT | sort)  # 6
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
                if i in (0, 1, 2, 3, 4, 14):
                    name = "##" + name  # Hide name for small columns
                elif i == 6:  # Name
                    if version_enabled:
                        name += "   -   Version"
                    if status_enabled:
                        name += "   -   Status"
                elif i == 11:
                    name = "󰈼"  # Played
                elif i == 12:
                    name = "󰅢"  # Installed
                imgui.table_header(name)

            # Sorting
            sort_specs = imgui.table_get_sort_specs()
            if sort_specs.specs_dirty or self.require_sort:
                if manual_sort:
                    self.sorted_games_ids = globals.settings.manual_sort_list
                    for _id in globals.games.keys():
                        if _id not in self.sorted_games_ids:
                            self.sorted_games_ids.append(_id)
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
                id = "##" + str(game.id)
                column_i = 2
                # Base row height
                imgui.table_set_column_index(column_i := column_i + 1)
                imgui.button("##ID" + id)
                # Play Button
                imgui.table_set_column_index(column_i := column_i + 1)
                if imgui.button("󰐊" + id):
                    pass  # TODO: game launching
                # Engine
                imgui.table_set_column_index(column_i := column_i + 1)
                imgui.text(game.engine.name)
                # Name
                imgui.table_set_column_index(column_i := column_i + 1)
                imgui.text(game.name)
                if version_enabled:
                    imgui.same_line()
                    imgui.text_disabled(game.version)
                if status_enabled:
                    imgui.same_line()
                    if game.status is Status.completed:
                        imgui.text_colored("󰄳", 0.00, 0.85, 0.00)
                    elif game.status is Status.onhold:
                        imgui.text_colored("󰏥", 0.00, 0.50, 0.95)
                    elif game.status is Status.abandoned:
                        imgui.text_colored("󰅙", 0.87, 0.20, 0.20)
                # Developer
                imgui.table_set_column_index(column_i := column_i + 1)
                # imgui.text(game.developer)  # TODO: fetch game developers
                imgui.text("Placeholder")
                # Last Updated
                imgui.table_set_column_index(column_i := column_i + 1)
                imgui.text(game.last_updated.display)
                # Last Played
                imgui.table_set_column_index(column_i := column_i + 1)
                imgui.text(game.last_played.display)
                # Added On
                imgui.table_set_column_index(column_i := column_i + 1)
                imgui.text(game.added_on.display)
                # Played
                imgui.table_set_column_index(column_i := column_i + 1)
                changed, game.played = imgui.checkbox("##󰈼" + id, game.played)
                if changed:
                    async_thread.run(db.update_game(id, "played"))
                # Installed
                imgui.table_set_column_index(column_i := column_i + 1)
                changed, installed = imgui.checkbox("##󰅢" + id, game.installed == game.version)
                if changed:
                    if installed:
                        game.installed = game.version
                    else:
                        game.installed = ""
                    async_thread.run(db.update_game(id, "installed"))
                # Rating
                imgui.table_set_column_index(column_i := column_i + 1)
                imgui.text("Placeholder")  # TODO: rating buttons
                # Open Thread
                imgui.table_set_column_index(column_i := column_i + 1)
                if imgui.button("󰏌" + id):
                    pass  # TODO: open game threads
                # Row hitbox
                imgui.same_line()
                imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() - style.frame_padding.y)
                imgui.selectable("##HitBox" + id, selected=False, flags=imgui.SELECTABLE_SPAN_ALL_COLUMNS, height=24)
                # TODO: left clickable for more info, right for context menu
                # Manual sort swap logic
                if manual_sort:
                    if imgui.is_item_active() and not imgui.is_item_hovered():
                        if imgui.get_mouse_drag_delta().y > 0:
                            swap_b = game_i + 1
                        else:
                            swap_b = game_i - 1
                        swap_a = game_i
            if swap_b is not None:
                self.sorted_games_ids[swap_a], self.sorted_games_ids[swap_b] = self.sorted_games_ids[swap_b], self.sorted_games_ids[swap_a]
                imgui.reset_mouse_drag_delta()

    def draw_bottombar(self):
        if imgui.button("󱇘"):
            print("aaa")
        imgui.same_line()
        if imgui.button("󱇙"):
            print("bbb")
        imgui.same_line()
        imgui.set_next_item_width(-48)
        imgui.input_text("##FilterAddBar", "", 999)
        imgui.same_line()
        if imgui.button("Add!"):
            print("ccc")

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
