from PyQt6 import QtCore, QtGui, QtWebEngineCore, QtWebEngineWidgets, QtWidgets
import pathlib
import json
import sys


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


def getlogin(url):
    app = QtWidgets.QApplication(sys.argv)
    weblogin = QCookieWebEngineView()
    weblogin.setWindowTitle("Please login...")
    weblogin.resize(500, 720)
    def check_login(*_):
        if "xf_user" in weblogin.cookies:
            weblogin.close()
    weblogin.loadFinished.connect(check_login)
    weblogin.load(QtCore.QUrl(url))
    weblogin.show()
    app.exec()
    print(json.dumps(weblogin.cookies))
