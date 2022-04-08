from imgui.integrations.glfw import GlfwRenderer
from PyQt6 import QtCore, QtGui, QtWidgets
import OpenGL.GL as gl
from PIL import Image
import imgui
import glfw
import sys

from modules.structs import *
from modules import globals


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
        self.size = 1280, 720
        self.window_flags = (
            imgui.WINDOW_NO_MOVE |
            imgui.WINDOW_NO_RESIZE |
            imgui.WINDOW_NO_COLLAPSE |
            imgui.WINDOW_NO_TITLE_BAR |
            imgui.WINDOW_NO_SCROLLBAR |
            imgui.WINDOW_NO_SAVED_SETTINGS |
            imgui.WINDOW_NO_SCROLL_WITH_MOUSE
        )

        self.qt_app = QtWidgets.QApplication(sys.argv)
        self.qt_loop = QtCore.QEventLoop()
        self.tray = TrayIcon(self)

        imgui.create_context()
        self.window = impl_glfw_init(*self.size, "F95Checker")
        glfw.set_window_icon(self.window, 1, Image.open("resources/icons/icon.png"))
        self.impl = GlfwRenderer(self.window)
        io = imgui.get_io()
        io.font_global_scale = 1
        ranges = imgui.core.GlyphRanges([
            0xf0000,
            0xf2000,
            0
        ])
        config = imgui.core.FontConfig(merge_mode=True, glyph_offset_x=-2, glyph_offset_y=3, glyph_extra_spacing_x=-3)
        io.fonts.add_font_from_file_ttf(
            str(globals.self_path / "resources/fonts/materialdesignicons-webfont.ttf"),
            16,
            font_config=config,
            glyph_ranges=ranges
        )
        self.impl.refresh_font_texture()
        glfw.set_window_iconify_callback(self.window, self.minimize)

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
                io = imgui.get_io()

                imgui.set_next_window_position(0, 0, imgui.ONCE)
                size = self.impl.io.display_size
                if size != self.prev_size:
                    imgui.set_next_window_size(*size, imgui.ALWAYS)
                    self.prev_size = size
                window_flags = self.window_flags
                if io.key_alt:
                    window_flags |= imgui.WINDOW_MENU_BAR

                with imgui.begin("F95Checker", closable=False, flags=window_flags):
                    with imgui.begin_child("Main", width=-269, height=0, border=False):
                        self.draw_games_list()
                        # self.draw_games_grid()
                    imgui.same_line()
                    with imgui.begin_child("Sidebar", width=269, height=0, border=False):
                        # imgui.text(f"FPS: {io.framerate}")
                        self.draw_sidebar()

                imgui.render()
                self.impl.render(imgui.get_draw_data())

            glfw.swap_buffers(self.window)  # Also waits idle time, must run always to avoid useless cycles

        self.impl.shutdown()
        glfw.terminate()

    def draw_games_list(self):
        columns = globals.settings.columns
        with imgui.begin_table("Games", columns.bit_count(), imgui.TABLE_SIZING_FIXED_FIT):
            if Column.play_button in columns:
                imgui.table_setup_column("Play")
            if Column.engine in columns:
                imgui.table_setup_column("Engine")
            imgui.table_setup_column("Name", imgui.TABLE_COLUMN_WIDTH_STRETCH)
            if Column.developer in columns:
                imgui.table_setup_column("Developer")
            if Column.last_updated in columns:
                imgui.table_setup_column("Last Updated")
            if Column.last_played in columns:
                imgui.table_setup_column("Last Played")
            if Column.added_on in columns:
                imgui.table_setup_column("Added On")
            if Column.played in columns:
                imgui.table_setup_column("Played")
            if Column.installed in columns:
                imgui.table_setup_column("Installed")
            if Column.rating in columns:
                imgui.table_setup_column("Rating")
            if Column.open_page in columns:
                imgui.table_setup_column("Open")
            imgui.table_headers_row()
            for game in globals.games.values():
                imgui.table_next_row()
                # i = 0
                if Column.play_button in columns:
                    imgui.table_next_column()
                    if imgui.button("󰐊"):
                        pass
                if Column.engine in columns:
                    imgui.table_next_column()
                    pass
                imgui.table_next_column()
                imgui.text(game.name)
                if Column.version in columns:
                    imgui.same_line()
                    imgui.text_disabled(game.version)
                if Column.status in columns:
                    imgui.same_line()
                    if game.status is Status.completed:
                        imgui.text_colored("󰄳", 0.00, 0.85, 0.00)
                    elif game.status is Status.onhold:
                        imgui.text_colored("󰏥", 0.00, 0.50, 0.95)
                    elif game.status is Status.abandoned:
                        imgui.text_colored("󰅙", 0.87, 0.20, 0.20)
                if Column.developer in columns:
                    imgui.table_next_column()
                    imgui.text(game.developer)
                if Column.last_updated in columns:
                    imgui.table_next_column()
                    pass
                if Column.last_played in columns:
                    imgui.table_next_column()
                    pass
                if Column.added_on in columns:
                    imgui.table_next_column()
                    pass
                if Column.played in columns:
                    imgui.table_next_column()
                    imgui.checkbox("a", True)
                if Column.installed in columns:
                    imgui.table_next_column()
                    imgui.checkbox("b", True)
                if Column.rating in columns:
                    imgui.table_next_column()
                    pass
                if Column.open_page in columns:
                    imgui.table_next_column()
                    if imgui.button("B"):
                        pass

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
