from PyQt6 import QtCore, QtGui, QtWebEngineCore, QtWebEngineWidgets, QtWidgets
import pathlib
import json
import sys
import os
import io


class QCookieWebEngineView(QtWebEngineWidgets.QWebEngineView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.alive = True

        self.profile = QtWebEngineCore.QWebEngineProfile(self)
        self.webpage = QtWebEngineCore.QWebEnginePage(self.profile, self)
        self.setPage(self.webpage)

        icon = "resources/icons/icon.png"
        if getattr(sys, "frozen", False):
            icon = pathlib.Path(sys.executable).parent / icon
        else:
            from main import __file__ as main_path
            icon = pathlib.Path(main_path).parent / icon
        self.setWindowIcon(QtGui.QIcon(str(icon)))

        self.cookies = {}
        self.profile.cookieStore().deleteAllCookies()
        self.profile.cookieStore().deleteSessionCookies()
        self.profile.cookieStore().cookieAdded.connect(self.onCookieAdd)

    def onCookieAdd(self, cookie):
        name = cookie.name().data().decode('utf-8')
        value = cookie.value().data().decode('utf-8')
        self.cookies[name] = value

    def closeEvent(self, event):
        self.alive = False
        return super().closeEvent(event)


def asklogin(url: str):
    # Subprocess for login webview, Qt WebEngine didn't
    # like running alongside another OpenGL application

    # Linux had issues with blank login pages and these helped out,
    # hese options might also prevent further problems on other platforms
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --disable-gpu --enable-logging --log-level=0"

    # Redirect stdout to avoid cookie pollution
    original_stdout_fd = sys.stdout.fileno()
    saved_stdout_fd = os.dup(original_stdout_fd)
    sys.stdout.close()
    os.dup2(sys.stderr.fileno(), original_stdout_fd)
    sys.stdout = io.TextIOWrapper(os.fdopen(original_stdout_fd, 'wb'))

    # Show login window
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QWidget()
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
            font-size: 5pt;
        }
    """)
    progress = QtWidgets.QProgressBar(window)
    progress.setTextVisible(False)
    progress.setFixedHeight(10)
    progress.setMaximum(100)
    window.layout().addWidget(progress, 0, 0)
    label = QtWidgets.QLabel(text="Click to reload")
    window.layout().addWidget(label, 0, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
    webview = QCookieWebEngineView(window)
    window.setWindowTitle("Login to F95Zone")
    window.resize(500, 720)
    loading = [False]
    def load_started(*_):
        loading[0] = True
        progress.setValue(1)
        progress.repaint()
        window.setWindowTitle("Login to F95Zone  |  Loading...")
    def load_progress(value):
        progress.setValue(max(1, value))
        progress.repaint()
        if "xf_user" in webview.cookies:
            window.close()
    def load_finished(*_):
        loading[0] = False
        progress.setValue(0)
        progress.repaint()
        window.setWindowTitle("Login to F95Zone")
    webview.loadStarted.connect(load_started)
    webview.loadProgress.connect(load_progress)
    webview.loadFinished.connect(load_finished)
    window.layout().addWidget(webview, 1, 0)
    def reload(*_):
        if loading[0]:
            webview.stop()
            load_finished()
        else:
            webview.reload()
            load_started()
    progress.mousePressEvent = reload
    label.mousePressEvent = reload
    window.show()
    webview.setUrl(QtCore.QUrl(url))
    app.exec()

    # Restore stdout and pass cookies
    sys.stdout.close()
    os.dup2(saved_stdout_fd, original_stdout_fd)
    sys.stdout = io.TextIOWrapper(os.fdopen(original_stdout_fd, 'wb'))
    sys.stdout.write(json.dumps(webview.cookies))
