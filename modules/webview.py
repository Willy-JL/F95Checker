from PyQt6 import QtCore, QtGui, QtWidgets, QtNetwork, QtWebEngineCore, QtWebEngineWidgets
import multiprocessing
import sys
import os

# Qt WebEngine doesn't like running alongside other OpenGL
# applications so we need to run a dedicated multiprocess


def config_qt_flags(debug: bool):
    # Linux had issues with blank login pages and broken contexts, these helped out
    # and might also prevent further problems on other platforms
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"--no-sandbox --disable-gpu {'--enable-logging --log-level=0' if debug else '--disable-logging'}"
    os.environ["QMLSCENE_DEVICE"] = "softwarecontext"
    QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)


def kwargs():
    from modules import globals, colors
    return dict(
        debug=globals.debug,
        icon=str(globals.gui.icon_path),
        col_bg=colors.rgba_0_1_to_hex(globals.settings.style_bg)[:-2],
        col_accent=colors.rgba_0_1_to_hex(globals.settings.style_accent)[:-2],
        col_text=colors.rgba_0_1_to_hex(globals.settings.style_text)[:-2]
    )


def create(*, title: str = None, size: tuple[int, int] = None, pos: tuple[int, int] = None, debug: bool, icon: str, col_bg: str, col_accent: str, col_text: str):
    config_qt_flags(debug)
    app = QtWidgets.QApplication(sys.argv)
    app.window = QtWidgets.QWidget()
    app.window.setWindowIcon(QtGui.QIcon(icon))
    if size:
        app.window.resize(*size)
    if pos:
        app.window.move(*pos)
    app.window.setLayout(QtWidgets.QGridLayout())
    app.window.layout().setContentsMargins(0, 0, 0, 0)
    app.window.layout().setSpacing(0)
    app.window.setStyleSheet(f"""
        QProgressBar {{
            background: {col_bg};
            border-radius: 0px;
        }}
        QProgressBar::chunk {{
            background: {col_accent};
            border-radius: 0px;
        }}
        QLabel {{
            color: {col_text};
            font-size: 8pt;
        }}
    """)

    app.window.progress = QtWidgets.QProgressBar(app.window)
    app.window.progress.setTextVisible(False)
    app.window.progress.setFixedHeight(10)
    app.window.progress.setMaximum(100)
    app.window.label = QtWidgets.QLabel(text="Click to reload")

    app.window.profile = QtWebEngineCore.QWebEngineProfile(app.window)
    app.window.webview = QtWebEngineWidgets.QWebEngineView(app.window.profile, app.window)

    if title:
        app.window.setWindowTitle(title)
    else:
        def title_changed(title: str):
            app.window.setWindowTitle(title)
        app.window.webview.titleChanged.connect(title_changed)
    loading = False
    def load_started():
        nonlocal loading
        loading = True
        app.window.progress.setValue(1)
        app.window.progress.repaint()
    def load_progress(value: int):
        app.window.progress.setValue(max(1, value))
        app.window.progress.repaint()
    def load_finished(ok: bool = None):
        nonlocal loading
        loading = False
        app.window.progress.setValue(0)
        app.window.progress.repaint()
    app.window.webview.loadStarted.connect(load_started)
    app.window.webview.loadProgress.connect(load_progress)
    app.window.webview.loadFinished.connect(load_finished)
    def reload(*_):
        if loading:
            app.window.webview.stop()
            load_finished()
        else:
            app.window.webview.reload()
            load_started()
    app.window.progress.mousePressEvent = reload
    app.window.label.mousePressEvent = reload

    app.window.layout().addWidget(app.window.label, 0, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
    app.window.layout().addWidget(app.window.progress, 0, 0)
    app.window.layout().addWidget(app.window.webview, 1, 0)
    return app


def open(url: str, *, cookies: dict[str, str] = {}, **kwargs):
    app = create(**kwargs)
    url = QtCore.QUrl(url)
    cookie_store = app.window.profile.cookieStore()
    for key, value in cookies.items():
        cookie_store.setCookie(QtNetwork.QNetworkCookie(QtCore.QByteArray(key.encode()), QtCore.QByteArray(value.encode())), url)
    app.window.webview.setUrl(url)
    app.window.show()
    app.exec()


def cookies(url: str, pipe: multiprocessing.Queue, **kwargs):
    app = create(**kwargs)
    url = QtCore.QUrl(url)
    cookie_store = app.window.profile.cookieStore()
    def on_cookie_add(cookie):
        name = cookie.name().data().decode('utf-8')
        value = cookie.value().data().decode('utf-8')
        pipe.put_nowait((name, value))
    cookie_store.cookieAdded.connect(on_cookie_add)
    app.window.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
    app.window.webview.setUrl(url)
    app.window.show()
    app.exec()
