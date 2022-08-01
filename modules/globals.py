from concurrent.futures import Future
import configparser
import plistlib
import pathlib
import shutil
import shlex
import sys
import os
import re

version = "9.2"
is_release = False

rpc_port = 57095

frozen = getattr(sys, "frozen", False)

if frozen:
    self_path = pathlib.Path(sys.executable).parent
else:
    import main
    self_path = pathlib.Path(main.__file__).parent

if frozen and sys.platform.startswith("linux"):
    library = self_path / f"lib/glfw/{os.environ.get('XDG_SESSION_TYPE')}/libglfw.so"
    if library.is_file():
        os.environ["PYGLFW_LIBRARY"] = str(library)

host = "f95zone.to"
domain = "https://" + host
check_login_page  = domain +"/account/"
login_page        = domain +"/login/"
login_endpoint    = domain +"/login/login"
two_step_endpoint = domain +"/login/two-step"
notif_endpoint    = domain +"/conversations/popup"
qsearch_endpoint  = domain +"/quicksearch"
alerts_page       = domain +"/account/alerts/"
inbox_page        = domain +"/conversations/"
bookmarks_page    = domain +"/account/bookmarks/"
watched_page      = domain +"/watched/threads/"
threads_page      = domain +"/threads/"
tool_page         = domain +"/threads/44173/"
github_page       = "https://github.com/Willy-JL/F95Checker"
developer_page    = "https://linktr.ee/WillyJL"
update_endpoint   = "https://api.github.com/repos/Willy-JL/F95Checker/releases/latest"


from modules.structs import Browser, Game, OldGame, Os, Settings
from modules.gui import MainGUI

if sys.platform.startswith("win"):
    os = Os.Windows
    data_path = "AppData/Roaming/f95checker"
elif sys.platform.startswith("linux"):
    os = Os.Linux
    data_path = ".f95checker"
elif sys.platform.startswith("darwin"):
    os = Os.MacOS
    data_path = "Library/Application Support/f95checker"
else:
    print("Your system is not officially supported at the moment!\n"
          "You can let me know on the tool thread or on GitHub, or you can try porting yourself ;)")
    sys.exit(1)
data_path = pathlib.Path.home() / data_path
data_path.mkdir(parents=True, exist_ok=True)
images_path = data_path / "images"
images_path.mkdir(parents=True, exist_ok=True)

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
            pass  # Key diesn't exist
elif os is Os.Linux:
    app_dir = pathlib.Path("/usr/share/applications")
    with open(app_dir / "mimeinfo.cache", "rb") as f:
        raw = f.read()
    apps = []
    for match in re.finditer(br"x-scheme-handler/https?=(.+)", raw):
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
    app_dir = pathlib.Path("/Applications")
    empty = []
    matches = ["http", "https"]
    for app in app_dir.glob("*.app"):
        app_file = app / "Contents/Info.plist"
        if not app_file.is_file():
            continue
        with open(app_file, "rb") as f:
            parser = plistlib.load(f)
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

if frozen:
    start_cmd = shlex.join([sys.executable])
else:
    import main
    start_cmd = shlex.join([sys.executable, main.__file__])

if os is Os.Windows:
    autostart = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run\\F95Checker"
    import winreg
    current_user = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
    try:
        value = winreg.QueryValue(current_user, autostart)
        start_with_system = value == start_cmd
    except Exception:
        start_with_system = False
elif os is Os.Linux:
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
    autostart_dir = pathlib.Path.home() / "Library/LaunchAgents"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    autostart = autostart_dir / "io.github.willy-jl.f95checker.plist"
    try:
        with autostart.open("rb") as f:
            plist = plistlib.load(f)
        value = shlex.join(plist["ProgramArguments"])
        start_with_system = value == start_cmd
    except Exception:
        start_with_system = False

# Variables
token: str = ""
popup_stack = []
refresh_total = 0
gui: MainGUI = None
refresh_progress = 0
last_update_check = 0.0
settings: Settings = None
refresh_task: Future = None
games: dict[int, Game] = None
cookies: dict[str, str] = None
updated_games: dict[int, OldGame] = {}
