from PyQt6 import QtCore, QtGui, QtWidgets, QtWebEngineCore, QtWebEngineWidgets
import json
import sys
import os
import io

title = "F95Checker: Login to F95Zone"
size = (500, 720)
stay_on_top = True


def did_login(cookies):
    return "xf_user" in cookies


def run(*, debug: bool, icon_path: str, start_page: str, parent_geometry: list[int, int, int, int], col_bg: str, col_accent: str, col_text: str):
    # Subprocess for login webview, Qt WebEngine didn't
    # like running alongside another OpenGL application

    # Linux had issues with blank login pages and broken contexts, these helped out
    # and might also prevent further problems on other platforms
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"--no-sandbox --disable-gpu {'--enable-logging --log-level=0' if debug else '--disable-logging'}"
    os.environ["QMLSCENE_DEVICE"] = "softwarecontext"
    QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

    # Redirect stdout to stderr so output is not polluted
    original_stdout_fd = sys.stdout.fileno()
    saved_stdout_fd = os.dup(original_stdout_fd)
    sys.stdout.close()
    os.dup2(sys.stderr.fileno(), original_stdout_fd)
    sys.stdout = io.TextIOWrapper(os.fdopen(original_stdout_fd, 'wb'))

    # Show login window
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QWidget()
    window.setWindowTitle(title)
    window.setWindowIcon(QtGui.QIcon(icon_path))
    window.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
    window.resize(*size)
    window.move(
        int(parent_geometry[0] + (parent_geometry[2] / 2) - size[0] / 2),
        int(parent_geometry[1] + (parent_geometry[3] / 2) - size[1] / 2)
    )
    window.setLayout(QtWidgets.QGridLayout())
    window.layout().setContentsMargins(0, 0, 0, 0)
    window.layout().setSpacing(0)
    window.setStyleSheet(f"""
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

    loading = False
    def load_started(*_):
        nonlocal loading
        loading = True
        progress.setValue(1)
        progress.repaint()
    def load_progress(value):
        progress.setValue(max(1, value))
        progress.repaint()
    def load_finished(*_):
        nonlocal loading
        loading = False
        progress.setValue(0)
        progress.repaint()
    webview.loadStarted.connect(load_started)
    webview.loadProgress.connect(load_progress)
    webview.loadFinished.connect(load_finished)
    def reload(*_):
        if loading:
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
    window.show()
    app.exec()

    # Restore stdout and pass cookies
    sys.stdout.close()
    os.dup2(saved_stdout_fd, original_stdout_fd)
    sys.stdout = io.TextIOWrapper(os.fdopen(original_stdout_fd, 'wb'))
    sys.stdout.write(json.dumps(cookies))
