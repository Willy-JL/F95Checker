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
            import main
            icon = pathlib.Path(main.__file__).parent / icon
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
    weblogin = QCookieWebEngineView()
    weblogin.setWindowTitle("Please login...")
    weblogin.resize(500, 720)
    def check_login(*_):
        if "xf_user" in weblogin.cookies:
            weblogin.close()
    weblogin.loadFinished.connect(check_login)
    weblogin.show()
    weblogin.setUrl(QtCore.QUrl(url))
    app.exec()

    # Restore stdout and pass cookies
    sys.stdout.close()
    os.dup2(saved_stdout_fd, original_stdout_fd)
    sys.stdout = io.TextIOWrapper(os.fdopen(original_stdout_fd, 'wb'))
    sys.stdout.write(json.dumps(weblogin.cookies))
