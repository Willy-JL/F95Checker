import multiprocessing.queues
import multiprocessing
import datetime as dt
import dataclasses
import asyncio
import weakref
import hashlib
import typing
import queue
import enum
import os


class ContextLimiter:
    count = 0

    def __init__(self, value=1):
        self.avail = value

    async def __aenter__(self):
        self.count += 1
        while self.avail < 1:
            await asyncio.sleep(0.1)
        self.avail -= 1

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.avail += 1
        self.count -= 1


class CounterContext:
    count = 0

    def __enter__(self):
        self.count += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.count -= 1

    async def __aenter__(self):
        self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__exit__(exc_type, exc_val, exc_tb)


class DaemonProcess:
    def __init__(self, proc):
        self.finalize = weakref.finalize(proc, self.kill, proc)

    @staticmethod
    def kill(proc):
        # Multiprocessing
        if getattr(proc, "exitcode", False) is None:
            proc.kill()
        # Asyncio subprocess
        elif getattr(proc, "returncode", False) is None:
            proc.kill()
        # Standard subprocess
        elif getattr(proc, "poll", lambda: False)() is None:
            proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.finalize()


class ProcessPipe(multiprocessing.queues.Queue):
    def __init__(self):
        super().__init__(0, ctx=multiprocessing.get_context())

    def __call__(self, proc: multiprocessing.Process):
        self.proc = proc
        self.daemon = DaemonProcess(proc)
        return self

    async def get_async(self, poll_rate=0.1):
        while self.proc.is_alive():
            try:
                return self.get_nowait()
            except queue.Empty:
                await asyncio.sleep(poll_rate)
        return self.get_nowait()

    def __enter__(self):
        self.proc.start()
        self.daemon.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.daemon.__exit__()
        if exc_type is queue.Empty:
            return True


class Timestamp:
    instances = []
    def __init__(self, unix_time: int | float):
        self.update(unix_time)
        type(self).instances.append(self)

    def update(self, unix_time: int | float = None):
        if unix_time is not None:
            self.value = int(unix_time)
        self._display = None

    @property
    def format(self):
        from modules import globals
        return globals.settings.timestamp_format

    @property
    def display(self):
        if self._display is None:
            if self.value == 0:
                self._display = ""
            else:
                try:
                    self._display = dt.datetime.fromtimestamp(self.value).strftime(self.format)
                except Exception:
                    self._display = "Bad format!"
        return self._display


class Datestamp(Timestamp):
    instances = []
    def __init__(self, unix_time: int | float):
        self.update(unix_time)
        type(self).instances.append(self)

    @property
    def format(self):
        from modules import globals
        return globals.settings.datestamp_format


class DefaultStyle:
    accent        = "#d4202e"
    alt_bg        = "#101010"
    bg            = "#0a0a0a"
    border        = "#454545"
    corner_radius = 6
    text          = "#ffffff"
    text_dim      = "#808080"


@dataclasses.dataclass
class ThreadMatch:
    title: str
    id: int


@dataclasses.dataclass
class SearchResult:
    title: str
    url: str
    id: int


@dataclasses.dataclass
class SortSpec:
    index: int
    reverse: bool


@dataclasses.dataclass
class TrayMsg:
    title: str
    msg: str
    icon: "PyQt6.QtWidgets.QSystemTrayIcon.MessageIcon"

    def __post_init__(self):
        # KDE Plasma for some reason doesn't dispatch clicks if the icon is not critical
        if os.environ.get("DESKTOP_SESSION") == "plasma" or \
        os.environ.get("XDG_SESSION_DESKTOP") == "KDE" or \
        os.environ.get("XDG_CURRENT_DESKTOP") == "KDE":
            from PyQt6.QtWidgets import QSystemTrayIcon
            self.icon = QSystemTrayIcon.MessageIcon.Critical


class IntEnumHack(enum.IntEnum):
    def __new__(cls, value, attrs: dict = None):
        self = int.__new__(cls, value)
        self._value_ = value
        # Add additional attributes
        if isinstance(attrs, dict):
            for key, value in attrs.items():
                setattr(self, key, value)
        return self
    def __init__(self, *args, **kwargs):
        cls = type(self)
        # Add index for use with _member_names_
        self._index_ = len(cls._member_names_)  # self is added later, so the length is up to the previous item, so not len() - 1
        # Replace spaces with _, - with __ and add _ in front if starting with a number. Allows using Enum._1_special__name in code for "1 special-name"
        new_name = "_" * self._name_[0].isdigit() + self._name_.replace(" ", "_").replace("-", "__")
        if new_name != self._name_:
            setattr(cls, new_name, self)


Os = IntEnumHack("Os", [
    "Windows",
    "Linux",
    "MacOS",
])


DisplayMode = IntEnumHack("DisplayMode", [
    ("list",   (1, {"icon": "view_agenda_outline"})),
    ("grid",   (2, {"icon": "view_grid_outline"})),
    ("kanban", (3, {"icon": "view_week_outline"})),
])


Status = IntEnumHack("Status", [
    ("Normal",    (1, {"color" : (0.96, 0.96, 0.96), "icon": "lightning_bolt_circle"})),
    ("Completed", (2, {"color" : (0.00, 0.85, 0.00), "icon": "checkbox_marked_circle"})),
    ("OnHold",    (3, {"color" : (0.00, 0.50, 0.95), "icon": "pause_circle"})),
    ("Abandoned", (4, {"color" : (0.87, 0.20, 0.20), "icon": "close_circle"})),
    ("Unchecked", (5, {"color" : (0.50, 0.50, 0.50), "icon": "alert_circle"})),
])


Tag = IntEnumHack("Tag", [
    ("2d-game",                1),
    ("2dcg",                   2),
    ("3d-game",                3),
    ("3dcg",                   4),
    ("adventure",              5),
    ("ahegao",                 6),
    ("anal-sex",               7),
    ("animated",               8),
    ("asset-addon",            9),
    ("asset-ai-shoujo",        10),
    ("asset-animal",           11),
    ("asset-animation",        12),
    ("asset-audio",            13),
    ("asset-bundle",           14),
    ("asset-character",        15),
    ("asset-clothing",         16),
    ("asset-environment",      17),
    ("asset-expression",       18),
    ("asset-hair",             19),
    ("asset-hdri",             20),
    ("asset-honey-select",     21),
    ("asset-honey-select2",    22),
    ("asset-koikatu",          23),
    ("asset-light",            24),
    ("asset-morph",            25),
    ("asset-plugin",           26),
    ("asset-pose",             27),
    ("asset-prop",             28),
    ("asset-script",           29),
    ("asset-shader",           30),
    ("asset-texture",          31),
    ("asset-utility",          32),
    ("asset-vehicle",          33),
    ("bdsm",                   34),
    ("bestiality",             35),
    ("big-ass",                36),
    ("big-tits",               37),
    ("blackmail",              38),
    ("bukkake",                39),
    ("censored",               40),
    ("character-creation",     41),
    ("cheating",               42),
    ("combat",                 43),
    ("corruption",             44),
    ("cosplay",                45),
    ("creampie",               46),
    ("dating-sim",             47),
    ("dilf",                   48),
    ("drugs",                  49),
    ("dystopian-setting",      50),
    ("exhibitionism",          51),
    ("fantasy",                52),
    ("female-protagonist",     54),
    ("femaledomination",       53),
    ("footjob",                55),
    ("furry",                  56),
    ("futa-trans",             57),
    ("futa-trans-protagonist", 58),
    ("gay",                    59),
    ("graphic-violence",       60),
    ("groping",                61),
    ("group-sex",              62),
    ("handjob",                63),
    ("harem",                  64),
    ("horror",                 65),
    ("humiliation",            66),
    ("humor",                  67),
    ("incest",                 68),
    ("internal-view",          69),
    ("interracial",            70),
    ("japanese-game",          71),
    ("kinetic-novel",          72),
    ("lactation",              73),
    ("lesbian",                74),
    ("loli",                   75),
    ("male-protagonist",       77),
    ("maledomination",         76),
    ("management",             78),
    ("masturbation",           79),
    ("milf",                   80),
    ("mind-control",           81),
    ("mobile-game",            82),
    ("monster",                83),
    ("monster-girl",           84),
    ("multiple-endings",       85),
    ("multiple-penetration",   86),
    ("multiple-protagonist",   87),
    ("necrophilia",            88),
    ("no-sexual-content",      89),
    ("ntr",                    90),
    ("oral-sex",               91),
    ("paranormal",             92),
    ("parody",                 93),
    ("platformer",             94),
    ("point-click",            95),
    ("possession",             96),
    ("pov",                    97),
    ("pregnancy",              98),
    ("prostitution",           99),
    ("puzzle",                 100),
    ("rape",                   101),
    ("real-porn",              102),
    ("religion",               103),
    ("romance",                104),
    ("rpg",                    105),
    ("sandbox",                106),
    ("scat",                   107),
    ("school-setting",         108),
    ("sci-fi",                 109),
    ("sex-toys",               110),
    ("sexual-harassment",      111),
    ("shooter",                112),
    ("shota",                  113),
    ("side-scroller",          114),
    ("simulator",              115),
    ("sissification",          116),
    ("slave",                  117),
    ("sleep-sex",              118),
    ("spanking",               119),
    ("strategy",               120),
    ("stripping",              121),
    ("superpowers",            122),
    ("swinging",               123),
    ("teasing",                124),
    ("tentacles",              125),
    ("text-based",             126),
    ("titfuck",                127),
    ("trainer",                128),
    ("transformation",         129),
    ("trap",                   130),
    ("turn-based-combat",      131),
    ("twins",                  132),
    ("urination",              133),
    ("vaginal-sex",            134),
    ("virgin",                 135),
    ("virtual-reality",        136),
    ("voiced",                 137),
    ("vore",                   138),
    ("voyeurism",              139),
])


ExeState = IntEnumHack("ExeState", [
    "Invalid",
    "Selected",
    "Unset",
])


MsgBox = IntEnumHack("MsgBox", [
    ("info",  (1, {"color": (0.10, 0.69, 0.95), "icon": "information"})),
    ("warn",  (2, {"color": (0.95, 0.69, 0.10), "icon": "alert_rhombus"})),
    ("error", (3, {"color": (0.95, 0.22, 0.22), "icon": "alert_octagon"})),
])


FilterMode = IntEnumHack("FilterMode", [
    "Choose",
    "Exe State",
    "Installed",
    "Label",
    "Played",
    "Rating",
    "Score",
    "Status",
    "Tag",
    "Type",
    "Updated",
])


Category = IntEnumHack("Category", [
    "Games",
    "Media",
    "Misc",
])


@dataclasses.dataclass
class Filter:
    mode: FilterMode
    invert = False
    match = None

    def __post_init__(self):
        self.id = id(self)


@dataclasses.dataclass
class Label:
    id: int
    name: str
    color: tuple[float]
    instances: typing.ClassVar = []

    @property
    def short_name(self):
        return "".join(word[:1] for word in self.name.split(" "))

    @classmethod
    def add(cls, *args, **kwargs):
        if args and isinstance(obj := args[0], cls):
            self = obj
        else:
            self = cls(*args, **kwargs)
        if self in cls.instances:
            return
        cls.instances.append(self)

    @classmethod
    def get(cls, id: int):
        for label in cls.instances:
            if label.id == id:
                return label

    @classmethod
    def remove(cls, self):
        while self in cls.instances:
            cls.instances.remove(self)


@dataclasses.dataclass
class Browser:
    name: str
    hash: int = None
    args: list[str] = None
    hashed_name: str = None
    integrated: bool = None
    custom: bool = None
    private_arg: list = None
    instances: typing.ClassVar = {}
    avail_list: typing.ClassVar = []

    def __post_init__(self):
        if self.hash is None:
            self.hash = self.make_hash(self.name)
        self.hashed_name = f"{self.name}###{self.hash}"
        self.integrated = self.hash == 0
        self.custom = self.hash == -1
        private_args = {
            "Opera":   "-private",
            "Chrom":   "-incognito",
            "Brave":   "-incognito",
            "Edge":    "-inprivate",
            "fox":     "-private-window"
        }
        self.private_arg = []
        for search, arg in private_args.items():
            if search in self.name:
                self.private_arg.append(arg)
                break

    @classmethod
    def make_hash(cls, name: str):
        return int(hashlib.md5(name.encode()).hexdigest()[-12:], 16)

    @classmethod
    def add(cls, *args, **kwargs):
        if args and isinstance(obj := args[0], cls):
            self = obj
        else:
            self = cls(*args, **kwargs)
        if self.hashed_name in cls.instances:
            return
        cls.instances[self.hashed_name] = self
        cls.avail_list.append(self.hashed_name)
        for browser in cls.instances.values():
            browser.index = cls.avail_list.index(browser.hashed_name)

    @classmethod
    def get(cls, hash):
        for browser in cls.instances.values():
            if browser.hash == hash or browser.hashed_name == hash:
                return browser
        return cls.get(0)

Browser.add("Integrated", 0)
Browser.add("Custom", -1)


@dataclasses.dataclass
class Settings:
    background_on_close         : bool
    bg_notifs_interval          : int
    bg_refresh_interval         : int
    browser                     : Browser.get
    browser_custom_arguments    : str
    browser_custom_executable   : str
    browser_html                : bool
    browser_private             : bool
    cell_image_ratio            : float
    check_notifs                : bool
    confirm_on_remove           : bool
    datestamp_format            : str
    default_exe_dir             : str
    display_mode                : DisplayMode
    fit_images                  : bool
    grid_columns                : int
    ignore_semaphore_timeouts   : bool
    interface_scaling           : float
    last_successful_refresh     : Timestamp
    manual_sort_list            : list[int]
    max_retries                 : int
    quick_filters               : bool
    refresh_completed_games     : bool
    refresh_workers             : int
    render_when_unfocused       : bool
    request_timeout             : int
    rpc_enabled                 : bool
    scroll_amount               : float
    scroll_smooth               : bool
    scroll_smooth_speed         : float
    select_executable_after_add : bool
    show_remove_btn             : bool
    start_in_background         : bool
    start_refresh               : bool
    style_accent                : tuple[float]
    style_alt_bg                : tuple[float]
    style_bg                    : tuple[float]
    style_border                : tuple[float]
    style_corner_radius         : int
    style_text                  : tuple[float]
    style_text_dim              : tuple[float]
    timestamp_format            : str
    update_keep_image           : bool
    use_parser_processes        : bool
    vsync_ratio                 : int
    zoom_area                   : int
    zoom_times                  : float
    zoom_enabled                : bool


from modules import colors, imagehelper

Type = IntEnumHack("Type", [
    ("ADRIFT",     (2,  {"color": colors.hex_to_rgba_0_1("#2196F3"), "category": Category.Games})),
    ("Flash",      (4,  {"color": colors.hex_to_rgba_0_1("#616161"), "category": Category.Games})),
    ("HTML",       (5,  {"color": colors.hex_to_rgba_0_1("#689F38"), "category": Category.Games})),
    ("Java",       (6,  {"color": colors.hex_to_rgba_0_1("#52A6B0"), "category": Category.Games})),
    ("Others",     (9,  {"color": colors.hex_to_rgba_0_1("#8BC34A"), "category": Category.Games})),
    ("QSP",        (10, {"color": colors.hex_to_rgba_0_1("#D32F2F"), "category": Category.Games})),
    ("RAGS",       (11, {"color": colors.hex_to_rgba_0_1("#FF9800"), "category": Category.Games})),
    ("RenPy",      (14, {"color": colors.hex_to_rgba_0_1("#B069E8"), "category": Category.Games})),
    ("RPGM",       (13, {"color": colors.hex_to_rgba_0_1("#2196F3"), "category": Category.Games})),
    ("Tads",       (16, {"color": colors.hex_to_rgba_0_1("#2196F3"), "category": Category.Games})),
    ("Unity",      (19, {"color": colors.hex_to_rgba_0_1("#FE5901"), "category": Category.Games})),
    ("Unreal Eng", (20, {"color": colors.hex_to_rgba_0_1("#0D47A1"), "category": Category.Games})),
    ("WebGL",      (21, {"color": colors.hex_to_rgba_0_1("#FE5901"), "category": Category.Games})),
    ("Wolf RPG",   (22, {"color": colors.hex_to_rgba_0_1("#4CAF50"), "category": Category.Games})),
    ("CG",         (30, {"color": colors.hex_to_rgba_0_1("#DFCB37"), "category": Category.Media})),
    ("Collection", (7,  {"color": colors.hex_to_rgba_0_1("#616161"), "category": Category.Media})),
    ("Comics",     (24, {"color": colors.hex_to_rgba_0_1("#FF9800"), "category": Category.Media})),
    ("GIF",        (25, {"color": colors.hex_to_rgba_0_1("#03A9F4"), "category": Category.Media})),
    ("Manga",      (26, {"color": colors.hex_to_rgba_0_1("#0FB2FC"), "category": Category.Media})),
    ("Pinup",      (27, {"color": colors.hex_to_rgba_0_1("#2196F3"), "category": Category.Media})),
    ("SiteRip",    (28, {"color": colors.hex_to_rgba_0_1("#8BC34A"), "category": Category.Media})),
    ("Video",      (29, {"color": colors.hex_to_rgba_0_1("#FF9800"), "category": Category.Media})),
    ("Cheat Mod",  (3,  {"color": colors.hex_to_rgba_0_1("#D32F2F"), "category": Category.Misc})),
    ("Mod",        (8,  {"color": colors.hex_to_rgba_0_1("#BA4545"), "category": Category.Misc})),
    ("READ ME",    (12, {"color": colors.hex_to_rgba_0_1("#DC143C"), "category": Category.Misc})),
    ("Request",    (15, {"color": colors.hex_to_rgba_0_1("#D32F2F"), "category": Category.Misc})),
    ("Tool",       (17, {"color": colors.hex_to_rgba_0_1("#EC5555"), "category": Category.Misc})),
    ("Tutorial",   (18, {"color": colors.hex_to_rgba_0_1("#EC5555"), "category": Category.Misc})),
    ("Misc",       (1,  {"color": colors.hex_to_rgba_0_1("#B8B00C"), "category": Category.Misc})),
    ("Unchecked",  (23, {"color": colors.hex_to_rgba_0_1("#393939"), "category": Category.Misc})),
])


@dataclasses.dataclass
class Game:
    id                   : int
    name                 : str
    version              : str
    developer            : str
    type                 : Type
    status               : Status
    url                  : str
    added_on             : Datestamp
    last_updated         : Datestamp
    last_full_refresh    : int
    last_refresh_version : str
    last_played          : Datestamp
    score                : float
    rating               : int
    played               : bool
    installed            : str
    executables          : list[str]
    description          : str
    changelog            : str
    tags                 : list[Tag]
    labels               : list[Label.get]
    notes                : str
    image_url            : str
    downloads            : list[tuple[str, list[tuple[str, str]]]]
    image                : imagehelper.ImageHelper = None
    executables_valids   : list[bool] = None
    executables_valid    : bool = None
    _init_done           : bool = False

    def __post_init__(self):
        from modules import globals
        self.image = imagehelper.ImageHelper(globals.images_path, glob=f"{self.id}.*")
        self.validate_executables()

    def validate_executables(self):
        from modules import globals
        self.executables_valids = [os.path.isfile(executable) for executable in self.executables]
        self.executables_valid = all(self.executables_valids)
        if globals.gui:
            globals.gui.require_sort = True

    def add_executable(self, executable: str):
        if executable in self.executables:
            return
        self.executables.append(executable)
        self.validate_executables()

    def remove_executable(self, executable: str):
        self.executables.remove(executable)
        self.validate_executables()

    def clear_executables(self):
        self.executables.clear()
        self.validate_executables()


@dataclasses.dataclass
class OldGame:
    id                   : int
    name                 : str
    version              : str
    status               : Status
