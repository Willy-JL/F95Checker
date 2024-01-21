from PyQt6 import QtCore, QtGui, QtWidgets, QtNetwork, QtWebChannel, QtWebEngineCore, QtWebEngineWidgets
import pathlib
import json
import sys
import os

# Qt WebEngine doesn't like running alongside other OpenGL
# applications so we need to run a dedicated multiprocess


def config_qt_flags(debug: bool):
    # Linux had issues with blank login pages and broken contexts, these helped out
    # and might also prevent further problems on other platforms
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join((
        "--no-sandbox",
        "--disable-gpu",
        *((
            "--enable-logging",
            "--log-level=0",
        ) if debug else (
            "--disable-logging",
        )),
    ))
    os.environ["QMLSCENE_DEVICE"] = "softwarecontext"
    QtWidgets.QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)


def kwargs():
    from modules import (
        globals,
        colors,
        icons,
    )
    return dict(
        debug=globals.debug,
        icon=str(globals.gui.icon_path),
        icon_font=str(icons.font_path),
        extension=str(globals.self_path / "extension/integrated.js"),
        col_bg=colors.rgba_0_1_to_hex(globals.settings.style_bg)[:-2],
        col_accent=colors.rgba_0_1_to_hex(globals.settings.style_accent)[:-2],
        col_text=colors.rgba_0_1_to_hex(globals.settings.style_text)[:-2]
    )


def create(
    *,
    title: str = None,
    buttons: bool = True,
    size: tuple[int, int] = None,
    pos: tuple[int, int] = None,
    debug: bool,
    icon: str,
    icon_font: str,
    extension: str,
    col_bg: str,
    col_accent: str,
    col_text: str
):
    config_qt_flags(debug)
    app = QtWidgets.QApplication(sys.argv)
    icon_font = QtGui.QFontDatabase.applicationFontFamilies(QtGui.QFontDatabase.addApplicationFont(icon_font))[0]
    app.window = QtWidgets.QWidget()
    icon = QtGui.QIcon(icon)
    app.window.setWindowIcon(icon)
    if size:
        app.window.resize(*size)
    if pos:
        app.window.move(*pos)
    app.window.setLayout(QtWidgets.QVBoxLayout(app.window))
    app.window.layout().setContentsMargins(0, 0, 0, 0)
    app.window.layout().setSpacing(0)

    app.window.controls = QtWidgets.QWidget()
    app.window.controls.setObjectName("controls")
    app.window.controls.setLayout(QtWidgets.QVBoxLayout(app.window.controls))
    app.window.controls.layout().setContentsMargins(0, 0, 0, 0)
    app.window.controls.layout().setSpacing(0)
    app.window.controls.buttons = QtWidgets.QWidget()
    app.window.controls.buttons.setLayout(QtWidgets.QHBoxLayout(app.window.controls.buttons))
    app.window.controls.buttons.layout().setContentsMargins(0, 0, 0, 0)
    app.window.controls.buttons.layout().setSpacing(0)
    app.window.controls.buttons.back = QtWidgets.QPushButton("󰁍", app.window.controls.buttons)
    app.window.controls.buttons.forward = QtWidgets.QPushButton("󰁔", app.window.controls.buttons)
    app.window.controls.buttons.reload = QtWidgets.QPushButton("󰑐", app.window.controls.buttons)
    app.window.controls.buttons.url = QtWidgets.QLineEdit(app.window.controls.buttons)
    app.window.controls.buttons.extension = QtWidgets.QPushButton(icon, "", app.window.controls.buttons)
    app.window.controls.buttons.layout().addWidget(app.window.controls.buttons.back)
    app.window.controls.buttons.layout().addWidget(app.window.controls.buttons.forward)
    app.window.controls.buttons.layout().addWidget(app.window.controls.buttons.reload)
    app.window.controls.buttons.layout().addWidget(app.window.controls.buttons.url)
    app.window.controls.buttons.layout().addWidget(app.window.controls.buttons.extension)
    if buttons:
        app.window.controls.layout().addWidget(app.window.controls.buttons)
    app.window.controls.progress = QtWidgets.QProgressBar(app.window.controls)
    app.window.controls.progress.setTextVisible(False)
    app.window.controls.progress.setFixedHeight(2)
    app.window.controls.progress.setMaximum(100)
    app.window.controls.layout().addWidget(app.window.controls.progress)

    app.window.webview = QtWebEngineWidgets.QWebEngineView(QtWebEngineCore.QWebEngineProfile(app.window), app.window)
    app.window.webview.page = app.window.webview.page()
    app.window.webview.history = app.window.webview.page.history()
    app.window.webview.profile = app.window.webview.page.profile()
    app.window.webview.settings = app.window.webview.page.settings()
    app.window.webview.cookieStore = app.window.webview.profile.cookieStore()

    app.window.webview.settings.setAttribute(QtWebEngineCore.QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    app.window.webview.settings.setAttribute(QtWebEngineCore.QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

    if title:
        app.window.setWindowTitle(title)
    else:
        def title_changed(title: str):
            app.window.setWindowTitle(title)
        app.window.webview.titleChanged.connect(title_changed)

    if extension:
        qwebchanneljsfile = QtCore.QFile(":/qtwebchannel/qwebchannel.js")
        qwebchanneljsfile.open(QtCore.QFile.OpenModeFlag.ReadOnly)
        qwebchanneljs = qwebchanneljsfile.readAll().data().decode('utf-8')
        qwebchanneljsfile.close()
        extension = qwebchanneljs + pathlib.Path(extension).read_text()
        from modules import async_thread
        import aiohttp
        async_thread.setup()
        class RPCProxy(QtCore.QObject):
            def __init__(self):
                super().__init__()
                self.session = aiohttp.ClientSession(loop=async_thread.loop, cookie_jar=aiohttp.DummyCookieJar())
            @QtCore.pyqtSlot(QtCore.QVariant, QtCore.QVariant, QtCore.QVariant, result=QtCore.QVariant)
            def handle(self, method, path, body):
                import main
                if body and not isinstance(body, bytes):
                    body = body.encode()
                async def _handle():
                    async with self.session.request(method, main.rpc_url + path, data=body) as req:
                        return {"status": req.status, "body": (await req.read()).decode()}
                return async_thread.wait(_handle())
        app.window.webview.rpcproxy = RPCProxy()
        app.window.webview.channel = QtWebChannel.QWebChannel(app.window.webview)
        app.window.webview.channel.registerObject('rpcproxy', app.window.webview.rpcproxy)
        app.window.webview.page.setWebChannel(app.window.webview.channel)
        app.window.webview.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        def custom_context_menu_requested(pos: QtCore.QPoint):
            menu = app.window.webview.createStandardContextMenu()
            data = app.window.webview.lastContextMenuRequest()
            if (url := data.linkUrl().url()):
                if "f95zone.to/threads/" in url:
                    add = QtGui.QAction(icon, "Add this link to F95Checker", menu)
                    add.triggered.connect(lambda _: app.window.webview.page.runJavaScript(f"addGame({url!r});"))
                    menu.addAction(add)
            elif "f95zone.to/threads/" in (url := app.window.webview.url().url()):
                add = QtGui.QAction(icon, "Add this page to F95Checker", menu)
                add.triggered.connect(lambda _: app.window.webview.page.runJavaScript(f"addGame({url!r});"))
                menu.addAction(add)
            menu.exec(app.window.webview.mapToGlobal(pos))
        app.window.webview.customContextMenuRequested.connect(custom_context_menu_requested)
        app.window.controls.buttons.extension.clicked.connect(lambda _: app.window.webview.page.runJavaScript(f"addGame({app.window.webview.url().url()!r});"))
    else:
        app.window.controls.buttons.extension.setVisible(False)

    loading = False
    def load_started():
        nonlocal loading
        loading = True
        app.window.controls.buttons.back.setEnabled(app.window.webview.history.canGoBack())
        app.window.controls.buttons.forward.setEnabled(app.window.webview.history.canGoForward())
        app.window.controls.buttons.reload.setText("󰅖")
        app.window.controls.progress.setValue(1)
        app.window.controls.progress.repaint()
        if extension:
            app.window.webview.page.runJavaScript(extension)
    def load_progress(value: int):
        app.window.controls.buttons.back.setEnabled(app.window.webview.history.canGoBack())
        app.window.controls.buttons.forward.setEnabled(app.window.webview.history.canGoForward())
        app.window.controls.buttons.reload.setText("󰅖")
        app.window.controls.progress.setValue(max(1, value))
        app.window.controls.progress.repaint()
        if extension:
            app.window.webview.page.runJavaScript(extension)
    def load_finished(_=None):
        nonlocal loading
        loading = False
        app.window.controls.buttons.back.setEnabled(app.window.webview.history.canGoBack())
        app.window.controls.buttons.forward.setEnabled(app.window.webview.history.canGoForward())
        app.window.controls.buttons.reload.setText("󰑐")
        app.window.controls.progress.setValue(0)
        app.window.controls.progress.repaint()
        if extension:
            app.window.webview.page.runJavaScript(extension + "\nupdateIcons();")
    app.window.webview.loadStarted.connect(load_started)
    app.window.webview.loadProgress.connect(load_progress)
    app.window.webview.loadFinished.connect(load_finished)
    def reload(_):
        if loading:
            app.window.webview.stop()
            load_finished()
        else:
            app.window.webview.reload()
            load_started()
    app.window.controls.buttons.back.clicked.connect(lambda checked=None: app.window.webview.back())
    app.window.controls.buttons.forward.clicked.connect(lambda checked=None: app.window.webview.forward())
    app.window.controls.buttons.reload.clicked.connect(reload)
    def url_changed(url: QtCore.QUrl):
        app.window.controls.buttons.url.setText(url.url())
        app.window.controls.buttons.url.setCursorPosition(0)
    def return_pressed():
        app.window.webview.setUrl(QtCore.QUrl(app.window.controls.buttons.url.text()))
    app.window.webview.urlChanged.connect(url_changed)
    app.window.controls.buttons.url.returnPressed.connect(return_pressed)

    def download_requested(download: QtWebEngineCore.QWebEngineDownloadRequest):
        old_path = pathlib.Path(download.downloadDirectory()) / download.downloadFileName()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(app.window.webview, "Save File", str(old_path), "*" + old_path.suffix)
        if path:
            new_path = pathlib.Path(path)
            download.setDownloadDirectory(str(new_path.parent))
            download.setDownloadFileName(new_path.name)
            download.accept()
    app.window.webview.profile.downloadRequested.connect(download_requested)
    def new_window_requested(request: QtWebEngineCore.QWebEngineNewWindowRequest):
        app.window.webview.setUrl(request.requestedUrl())
    app.window.webview.page.newWindowRequested.connect(new_window_requested)

    app.window.setStyleSheet(f"""
        #controls * {{
            background: {col_bg};
            color: {col_text};
            font-size: 14pt;
            border-radius: 0px;
            border: 0px;
            margin: 0px;
            padding: 0px;
        }}
        #controls QProgressBar::chunk {{
            background: {col_accent};
        }}
        #controls QPushButton {{
            font-family: '{icon_font}';
            padding: 5px;
            padding-bottom: 3px;
        }}
        #controls QPushButton:disabled {{
            color: #99{col_text[1:]};
        }}
        #controls QLineEdit {{
            font-size: 12px;
            padding: 5px;
            padding-bottom: 3px;
        }}
    """)
    app.window.webview.page.setBackgroundColor(QtGui.QColor(col_bg))

    app.window.layout().addWidget(app.window.controls, stretch=0)
    app.window.layout().addWidget(app.window.webview, stretch=1)
    return app


def open(url: str, *, cookies: dict[str, str] = {}, **kwargs):
    app = create(**kwargs)
    url = QtCore.QUrl(url)
    for key, value in cookies.items():
        app.window.webview.cookieStore.setCookie(QtNetwork.QNetworkCookie(QtCore.QByteArray(key.encode()), QtCore.QByteArray(value.encode())), url)
    app.window.webview.setUrl(url)
    app.window.show()
    app.exec()


def cookies(url: str, **kwargs):
    app = create(**kwargs | dict(buttons=False, extension=False))
    url = QtCore.QUrl(url)
    def on_cookie_add(cookie: QtNetwork.QNetworkCookie):
        name = cookie.name().data().decode('utf-8')
        value = cookie.value().data().decode('utf-8')
        print(json.dumps([name, value]), flush=True)
    app.window.webview.cookieStore.cookieAdded.connect(on_cookie_add)
    app.window.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
    app.window.webview.setUrl(url)
    app.window.show()
    app.exec()


def redirect(url: str, click_selector: str = None, *, cookies: dict[str, str] = {}, **kwargs):
    app = create(**kwargs | dict(buttons=False, extension=False))
    url = QtCore.QUrl(url)
    for key, value in cookies.items():
        app.window.webview.cookieStore.setCookie(QtNetwork.QNetworkCookie(QtCore.QByteArray(key.encode()), QtCore.QByteArray(value.encode())), url)
    def url_changed(new: QtCore.QUrl):
        if new != url and not new.url().startswith(url.url()):
            print(json.dumps(new.url()), flush=True)
    app.window.webview.urlChanged.connect(url_changed)
    if click_selector:
        def load_progress(_):
            app.window.webview.page.runJavaScript(f"""
                redirectClickElement = document.querySelector({click_selector!r});
                if (redirectClickElement) {{
                    redirectClickElement.click();
                }}
            """)
        app.window.webview.loadProgress.connect(load_progress)
    app.window.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
    app.window.webview.setUrl(url)
    app.window.show()
    app.exec()
