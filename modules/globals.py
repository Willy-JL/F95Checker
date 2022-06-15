from concurrent.futures import Future
import configparser
import plistlib
import pathlib
import shutil
import shlex
import sys
import os

version = "9.0"

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

domain = "https://f95zone.to"
check_login_page  = domain + "/account/"
login_page        = domain + "/login/"
login_endpoint    = domain + "/login/login"
two_step_endpoint = domain + "/login/two-step"
notif_endpoint    = domain + "/conversations/popup"
qsearch_endpoint  = domain + "/quicksearch"
alerts_page       = domain + "/account/alerts/"
inbox_page        = domain + "/conversations/"
bookmarks_page    = domain + "/account/bookmarks/"
watched_page      = domain + "/watched/threads/"
threads_page      = domain + "/threads/"
tool_page         = domain + "/threads/44173/"
github_page       = "https://github.com/Willy-JL/F95Checker"
developer_page    = "https://linktr.ee/WillyJL"


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

Browser._avail_.append(Browser._None.name)
if sys.platform.startswith("win"):
    import winreg
    local_machine = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
    current_user = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
    start_menu_internet = "SOFTWARE\\Clients\\StartMenuInternet"
    open_command = "shell\\open\\command"
    for browser in list(Browser):
        browser.path = ""
        match browser.value:
            case Browser.Chrome.value:
                candidates = ["Google Chrome"]
            case Browser.Firefox.value:
                candidates = ["Firefox-308046B0AF4A39CB"]
            case Browser.Brave.value:
                candidates = ["Brave"]
            case Browser.Edge.value:
                candidates = ["Microsoft Edge"]
            case Browser.Opera.value:
                candidates = ["OperaStable"]
            case Browser.Opera_GX.value:
                candidates = ["Opera GXStable"]
            case _:
                candidates = None
        if candidates:
            for candidate in candidates:
                reg_key = f"{start_menu_internet}\\{candidate}\\{open_command}"
                try:
                    path = winreg.QueryValue(local_machine, reg_key)
                    browser.path = path
                    Browser._avail_.append(browser.name)
                    break
                except Exception:
                    pass
                try:
                    path = winreg.QueryValue(current_user, reg_key)
                    browser.path = path
                    Browser._avail_.append(browser.name)
                    break
                except Exception:
                    pass
        if browser.path and browser.path[0] == '"' and browser.path [-1] == '"':
            browser.path = browser.path[1:-1]
else:
    for browser in list(Browser):
        browser.path = ""
        if os is Os.Linux:
            match browser.value:
                case Browser.Chrome.value:
                    candidates = ["chromium-stable", "chromium-browser", "chromium", "google-chrome-stable", "chrome-stable", "chrome-browser", "google-chrome", "chrome"]
                case Browser.Firefox.value:
                    candidates = ["firefox-stable", "firefox"]
                case Browser.Brave.value:
                    candidates = ["brave-stable", "brave-browser", "brave"]
                case Browser.Edge.value:
                    candidates = ["microsoft-edge-stable", "microsoft-edge", "edge-stable", "edge-browser", "edge"]
                case Browser.Opera.value:
                    candidates = ["opera-stable", "opera-browser", "opera"]
                case Browser.Opera_GX.value:
                    candidates = None  # OperaGX is not yet available for linux
                case _:
                    candidates = None
        elif os is Os.MacOS:
            match browser.value:
                case Browser.Chrome.value:
                    candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
                case Browser.Firefox.value:
                    candidates = ["/Applications/Firefox.app/Contents/MacOS/firefox"]
                case Browser.Brave.value:
                    candidates = ["/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"]
                case Browser.Edge.value:
                    candidates = None  # Edge is not yet available for macos
                case Browser.Opera.value:
                    candidates = ["/Applications/Opera.app/Contents/MacOS/Opera"]
                case Browser.Opera_GX.value:
                    candidates = ["/Applications/Opera GX.app/Contents/MacOS/Opera"]
                case _:
                    candidates = None
        if candidates:
            for candidate in candidates:
                if path := shutil.which(candidate):
                    browser.path = path
                    Browser._avail_.append(browser.name)
                    break
Browser._avail_.append(Browser.Custom.name)

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
    autostart = autostart_dir / "com.github.f95checker.plist"
    try:
        with autostart.open("rb") as fp:
            plist = plistlib.load(fp)
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
settings: Settings = None
refresh_task: Future = None
games: dict[int, Game] = None
cookies: dict[str, str] = None
updated_games: dict[int, OldGame] = {}
