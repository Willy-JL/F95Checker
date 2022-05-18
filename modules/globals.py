import pathlib
import shutil
import sys
import os

version = "9.0"

frozen = getattr(sys, "frozen", False)

if frozen:
    self_path = pathlib.Path(sys.executable).parent
else:
    self_path = pathlib.Path(__file__).parent.parent

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
tool_page         = domain + "/threads/44173/"


from modules.structs import Browser, Game, Os, Settings
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

browsers = []
browsers.append(Browser._None.name)
if sys.platform.startswith("win"):
    pass
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
                    browsers.append(browser.name)
                    break
browsers.append(Browser.Custom.name)

# Variables
gui: MainGUI = None
browser_idx: int = 0
popup_stack: list = []
settings: Settings = None
games: dict[int, Game] = None
