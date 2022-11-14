from PyQt6 import QtCore, QtGui, QtWidgets, QtWebEngineCore, QtWebEngineWidgets
import imgui
import glfw

from modules import globals, utils

title = "F95Checker: Login to F95Zone"
size = (500, 720)
stay_on_top = True
start_page = globals.login_page


def did_login(cookies):
    return "xf_user" in cookies


def run():
    window = QtWidgets.QWidget()
    window.setWindowTitle(title)
    window.setWindowIcon(QtGui.QIcon(str(globals.gui.icon_path)))
    window.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
    window.resize(*size)
    window.move(
        int(globals.gui.screen_pos[0] + (imgui.io.display_size.x / 2) - size[0] / 2),
        int(globals.gui.screen_pos[1] + (imgui.io.display_size.y / 2) - size[1] / 2)
    )
    window.setLayout(QtWidgets.QGridLayout())
    window.layout().setContentsMargins(0, 0, 0, 0)
    window.layout().setSpacing(0)
    window.setStyleSheet(f"""
        QProgressBar {{
            background: {utils.rgba_0_1_to_hex(globals.settings.style_bg)[:-2]};
            border-radius: 0px;
        }}
        QProgressBar::chunk {{
            background: {utils.rgba_0_1_to_hex(globals.settings.style_accent)[:-2]};
            border-radius: 0px;
        }}
        QLabel {{
            color: {utils.rgba_0_1_to_hex(globals.settings.style_text)[:-2]};
            font-size: 8pt;
        }}
    """)

    progress = QtWidgets.QProgressBar(window)
    progress.setTextVisible(False)
    progress.setFixedHeight(10)
    progress.setMaximum(100)
    label = QtWidgets.QLabel(text="Click to reload")

    profile = QtWebEngineCore.QWebEngineProfile(window)
    webview = QtWebEngineWidgets.QWebEngineView(profile, window)
    cookies = {}
    def on_cookie_add(cookie):
        name = cookie.name().data().decode('utf-8')
        value = cookie.value().data().decode('utf-8')
        cookies[name] = value
        if did_login(cookies):
            try:
                window.close()
            except RuntimeError:
                pass
    profile.cookieStore().cookieAdded.connect(on_cookie_add)
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

    window.layout().addWidget(label, 0, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
    window.layout().addWidget(progress, 0, 0)
    window.layout().addWidget(webview, 1, 0)
    alive = [True]
    _closeEvent = window.closeEvent
    def closeEvent(*args, **kwargs):
        alive[0] = False
        return _closeEvent(*args, **kwargs)
    window.closeEvent = closeEvent
    window.show()
    while alive[0]:
        globals.gui.qt_app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.WaitForMoreEvents)
    glfw.make_context_current(globals.gui.window)
    return cookies
