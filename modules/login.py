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
    return {}


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
    window.connect("destroy", Gtk.main_quit)
    window.set_keep_above(stay_on_top)
    window.resize(*size)
    window.move(
        globals.gui.screen_pos[0] + (imgui.io.display_size.x / 2) - size[0] / 2,
        globals.gui.screen_pos[1] + (imgui.io.display_size.y / 2) - size[1] / 2
    )

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
