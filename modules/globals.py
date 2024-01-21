from concurrent.futures import Future
from functools import partial
import os as _os
import pathlib
import shutil
import shlex
import sys
import re

version = None
release = None
build_number = None
version_name = None
rpc_port = None
rpc_url = None
frozen = None
self_path = None
debug = None
def _():
    global version, release, build_number, version_name, rpc_port, rpc_url, frozen, self_path, debug
    from main import version, release, build_number, version_name, rpc_port, rpc_url, frozen, self_path, debug

    # Fix frozen load paths
    if frozen:
        if sys.platform.startswith("linux"):
            library = self_path / f"lib/glfw/{_os.environ.get('XDG_SESSION_TYPE')}/libglfw.so"
            if library.is_file():
                _os.environ["PYGLFW_LIBRARY"] = str(library)
        elif sys.platform.startswith("darwin"):
            process = self_path / "lib/PyQt6/Qt6/lib/QtWebEngineCore.framework/Helpers/QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess"
            if process.is_file():
                _os.environ["QTWEBENGINEPROCESS_PATH"] = str(process)

    # Fix PIL image loading
    from PIL import ImageFile, PngImagePlugin
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    PngImagePlugin.MAX_TEXT_CHUNK *= 10

    # Optimize OpenGL
    import OpenGL
    for option in ("ERROR_LOGGING", "ERROR_CHECKING", "CONTEXT_CHECKING"):
        setattr(OpenGL, option, debug)
    if debug:
        import logging
        logging.basicConfig()
_()

from modules.structs import Browser, Game, OldGame, Os, Settings
from modules.gui import MainGUI

os = None
data_path = None
images_path = None
def _():
    global os, data_path, images_path
    home = pathlib.Path.home()
    if sys.platform.startswith("win"):
        os = Os.Windows
        data_path = "AppData/Roaming/f95checker"
    elif sys.platform.startswith("linux"):
        os = Os.Linux
        if (home / ".f95checker").exists() and not (home / ".config/f95checker").exists():
            (home / ".config").mkdir(parents=True, exist_ok=True)
            shutil.move(home / ".f95checker", home / ".config/f95checker")
        data_path = ".config/f95checker"
    elif sys.platform.startswith("darwin"):
        os = Os.MacOS
        data_path = "Library/Application Support/f95checker"
    else:
        print("Your system is not officially supported at the moment!\n"
            "You can let me know on the tool thread or on GitHub, or you can try porting yourself ;)")
        sys.exit(1)
    data_path = home / data_path
    data_path.mkdir(parents=True, exist_ok=True)
    images_path = data_path / "images"
    images_path.mkdir(parents=True, exist_ok=True)
_()

def _():
    if os is Os.Windows:
        import winreg
        for registry in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                browsers = winreg.OpenKey(registry, "SOFTWARE\\Clients\\StartMenuInternet")
                try:
                    i = 0
                    while True:
                        key = winreg.EnumKey(browsers, i)
                        try:
                            name = winreg.QueryValue(browsers, key)
                            args = shlex.split(winreg.QueryValue(browsers, key + "\\shell\\open\\command"))
                            if args and pathlib.Path(shutil.which(args[0])).exists():
                                Browser.add(name, args=args)
                        except Exception:
                            pass  # Non-standard key
                        i += 1
                except OSError:
                    pass  # Stop iteration
            except FileNotFoundError:
                pass  # Key doesn't exist
    elif os is Os.Linux:
        import configparser
        app_dir = pathlib.Path("/usr/share/applications")
        raw = (app_dir / "mimeinfo.cache").read_bytes()
        apps = []
        for match in re.finditer(rb"x-scheme-handler/https?=(.+)", raw):
            for app in match.group(1)[:-1].split(b";"):
                app = str(app, encoding="utf-8")
                if app not in apps:
                    apps.append(app)
        for app in apps:
            app_file = app_dir / app
            if not app_file.is_file():
                continue
            parser = configparser.RawConfigParser()
            parser.read(app_file)
            name = parser.get("Desktop Entry", "Name")
            args = [arg for arg in shlex.split(parser.get("Desktop Entry", "Exec")) if not (len(arg) == 2 and arg.startswith("%"))]
            if args and pathlib.Path(shutil.which(args[0])).exists():
                Browser.add(name, args=args)
    elif os is Os.MacOS:
        import plistlib
        app_dir = pathlib.Path("/Applications")
        empty = []
        matches = ["http", "https"]
        for app in app_dir.glob("*.app"):
            app_file = app / "Contents/Info.plist"
            if not app_file.is_file():
                continue
            parser = plistlib.loads(app_file.read_bytes())
            found = False
            for handler in parser.get("CFBundleURLTypes", empty):
                for scheme in handler.get("CFBundleURLSchemes", empty):
                    if scheme in matches:
                        name = parser["CFBundleName"]
                        args = [app / f"Contents/MacOS/{parser['CFBundleExecutable']}"]
                        if args and pathlib.Path(shutil.which(args[0])).exists():
                            Browser.add(name, args=args)
                        found = True
                        break
                if found:
                    break
_()

start_cmd = None
autostart = None
start_with_system = None
def _():
    global start_cmd, autostart, start_with_system
    if frozen:
        start_cmd = shlex.join([sys.executable])
    else:
        from main import __file__ as main_path
        start_cmd = shlex.join([sys.executable, main_path])

    if os is Os.Windows:
        import winreg
        autostart = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run\\F95Checker"
        try:
            current_user = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            value = winreg.QueryValue(current_user, autostart)
            start_with_system = value == start_cmd
        except Exception:
            start_with_system = False
    elif os is Os.Linux:
        import configparser
        autostart_dir = pathlib.Path.home() / ".config/autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        autostart = autostart_dir / "F95Checker.desktop"
        try:
            config = configparser.RawConfigParser()
            config.optionxform = lambda option: option
            config.read(autostart)
            value = config.get("Desktop Entry", "Exec")
            start_with_system = value == start_cmd
        except Exception:
            start_with_system = False
    elif os is Os.MacOS:
        import plistlib
        autostart_dir = pathlib.Path.home() / "Library/LaunchAgents"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        autostart = autostart_dir / "io.github.willy-jl.f95checker.plist"
        try:
            plist = plistlib.loads(autostart.read_bytes())
            value = shlex.join(plist["ProgramArguments"])
            start_with_system = value == start_cmd
        except Exception:
            start_with_system = False
_()

# Variables
refresh_total = 0
gui: MainGUI = None
refresh_progress = 0
last_update_check = 0.0
settings: Settings = None
refresh_task: Future = None
games: dict[int, Game] = None
cookies: dict[str, str] = None
popup_stack: list[partial] = []
updated_games: dict[int, OldGame] = {}
