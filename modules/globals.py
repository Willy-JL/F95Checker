from modules.gui import F95CheckerTray, F95CheckerGUI
from PyQt5.QtWidgets import QApplication
from modules.singleton import Singleton
from qasync import QSelectorEventLoop
from PyQt5.QtCore import QSettings
from aiohttp import ClientSession
from PyQt5.QtGui import QFont
from asyncio import Semaphore


version           : str                = None

app               : QApplication       = None
font_awesome      : QFont              = None
gui               : F95CheckerGUI      = None
http              : ClientSession      = None
image_bg_tasks    : set                = None
image_semaphore   : Semaphore          = None
loop              : QSelectorEventLoop = None
settings          : QSettings          = None
singleton         : Singleton          = None
tray              : F95CheckerTray     = None

config            : dict               = None
config_path       : str                = None
exec_type         : str                = None
mode              : str                = None
token             : str                = None
user_browsers     : dict               = None
user_os           : str                = None

bg_paused         : bool               = None
checked_updates   : bool               = None
checking_updates  : bool               = None
logged_in         : bool               = None
logging_in        : bool               = None
refreshing        : bool               = None
updated_games     : bool               = None
warned_connection : bool               = None

alerts_page       : str                = None
check_login_page  : str                = None
domain            : str                = None
inbox_page        : str                = None
login_endpoint    : str                = None
login_page        : str                = None
notif_endpoint    : str                = None
qsearch_endpoint  : str                = None
tool_page         : str                = None
two_step_endpoint : str                = None
