import imgui

from modules.structs import Os
from modules import globals

title = "F95Checker: Login to F95Zone"
size = (500, 720)
stay_on_top = True
start_page = globals.login_page


def did_login(cookies):
    return "xf_user" in cookies


def run_windows():
    from PyQt6 import QtCore, QtGui, QtWidgets
    import os

    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --disable-gpu --enable-logging --log-level=0"
    QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    from PyQt6 import QtWebEngineCore, QtWebEngineWidgets
    app = QtWidgets.QApplication([])

    window = QtWidgets.QWidget()
    window.setWindowTitle(title)
    # TODO: window icon
    # TODO: always on top flag
    window.resize(*size)
    # TODO: move to middle of main window
    window.setLayout(QtWidgets.QGridLayout())
    window.layout().setContentsMargins(0, 0, 0, 0)
    window.layout().setSpacing(0)
    window.setStyleSheet("""
        QProgressBar {
            background: #0A0A0A;
            border-radius: 0px;
        }
        QProgressBar::chunk {
            background: #D4202E;
            border-radius: 0px;
        }
        QLabel {
            color: #FFFFFF;
            font-size: 8pt;
        }
    """)  # TODO: use accent color

    progress = QtWidgets.QProgressBar(window)
    progress.setTextVisible(False)
    progress.setFixedHeight(10)
    progress.setMaximum(100)
    label = QtWidgets.QLabel(text="Click to reload")

    webview = QtWebEngineWidgets.QWebEngineView(window)
    profile = QtWebEngineCore.QWebEngineProfile(webview)
    webpage = QtWebEngineCore.QWebEnginePage(profile, webview)
    webview.setPage(webpage)
    cookie_store = profile.cookieStore()
    cookie_store.deleteAllCookies()
    cookie_store.deleteSessionCookies()
    cookies = {}
    login = [False]
    def on_cookie_add(cookie):
        name = cookie.name().data().decode('utf-8')
        value = cookie.value().data().decode('utf-8')
        cookies[name] = value
        if did_login(cookies):
            login[0] = True
            window.close()
    cookie_store.cookieAdded.connect(on_cookie_add)
    webview.setUrl(QtCore.QUrl(start_page))

    loading = [False]
    def load_started(*_):
        loading[0] = True
        progress.setValue(1)
        progress.repaint()
    def load_progress(value):
        progress.setValue(max(1, value))
        progress.repaint()
    def load_finished(*_):
        loading[0] = False
        progress.setValue(0)
        progress.repaint()
    webview.loadStarted.connect(load_started)
    webview.loadProgress.connect(load_progress)
    webview.loadFinished.connect(load_finished)
    def reload(*_):
        if loading[0]:
            webview.stop()
            load_finished()
        else:
            webview.reload()
            load_started()
    progress.mousePressEvent = reload
    label.mousePressEvent = reload

    window.layout().addWidget(progress, 0, 0)
    window.layout().addWidget(label, 0, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
    window.layout().addWidget(webview, 1, 0)
    window.show()
    app.exec()  # TODO: fix crash
    return cookies


def run_unix():
    import ctypes.util
    import gi

    def get_gtk_version(name):
        lib = ctypes.util.find_library(name)
        if not lib:
            raise ModuleNotFoundError(f"A required library file could not be found for {repr(name)}")
        ver = lib.rsplit("-", 1)[1].rsplit(".so", 1)[0].rsplit(".dylib", 1)[0].rsplit(".dll", 1)[0]
        if ver.count(".") < 1:
            ver += ".0"
        return ver

    gi.require_version("Gtk", get_gtk_version("gtk-3"))
    gi.require_version("WebKit2", get_gtk_version("webkit2gtk-4"))
    from gi.repository import Gtk, WebKit2

    window = Gtk.Window(title=title)
    # TODO: window icon
    window.connect("destroy", Gtk.main_quit)
    window.set_keep_above(stay_on_top)
    window.resize(*size)
    window.move(
        globals.gui.screen_pos[0] + (imgui.io.display_size.x / 2) - size[0] / 2,
        globals.gui.screen_pos[1] + (imgui.io.display_size.y / 2) - size[1] / 2
    )

    # TODO: add progressbar

    webview = WebKit2.WebView()
    cookies = {}
    def on_cookies_changed(cookie_manager):
        def cookies_callback(cookie_manager, cookie_task):
            cookies.update({cookie.get_name(): cookie.get_value() for cookie in cookie_manager.get_cookies_finish(cookie_task)})
            if did_login(cookies):
                window.destroy()
        cookie_manager.get_cookies(webview.get_uri(), None, cookies_callback)
    webview.get_context().get_cookie_manager().connect("changed", on_cookies_changed)
    webview.load_uri(start_page)

    window.add(webview)
    window.show_all()
    Gtk.main()
    return cookies


def run():
    if globals.os is Os.Windows:
        run = run_windows
    else:
        run = run_unix
    return run()
