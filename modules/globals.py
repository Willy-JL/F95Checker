import pathlib
import sys

version = "9.0"

frozen = getattr(sys, "frozen", False)

if frozen:
    self_path = pathlib.Path(sys.executable).parent
else:
    self_path = pathlib.Path(__file__).parent.parent

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


from modules.gui import MainGUI
from modules.structs import *

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

# Will get initialized later
gui: MainGUI = None
settings: Settings = None
games: dict[int, Game] = None
