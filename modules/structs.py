import multiprocessing.queues
import multiprocessing
import datetime as dt
import dataclasses
import collections
import functools
import aiofiles
import operator
import asyncio
import weakref
import hashlib
import pathlib
import typing
import queue
import enum
import json
import time
import os


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


class Popup(functools.partial):
    next_uuid = 0
    def __init__(self, *_, **__):
        from modules import utils
        self.open = True
        cls = type(self)
        uuid = cls.next_uuid
        cls.next_uuid += 1
        self.uuid = f"{uuid}_{str(time.time()).split('.')[-1]}_{utils.rand_num_str()}"

    def __call__(self, *args, **kwargs):
        if not self.open:
            return 0, True
        opened, closed = super().__call__(*args, popup_uuid=self.uuid, **kwargs)
        if closed:
            self.open = False
        return opened, closed


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


class MultiProcessPipe(multiprocessing.queues.Queue):
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


class AsyncProcessPipe:
    class process_exit(Exception):
        pass

    def __call__(self, proc: asyncio.subprocess.Process):
        self.proc = proc
        self.daemon = DaemonProcess(proc)
        return self

    async def get_async(self, poll_rate=0.1):
        while self.proc.returncode is None:
            try:
                return json.loads(await self.proc.stdout.readline())
            except json.JSONDecodeError:
                pass
        raise self.process_exit()

    def __enter__(self):
        self.daemon.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.daemon.__exit__()
        if exc_type is self.process_exit:
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
    accent        = "#007AF2"
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
class TorrentResult:
    id: int
    title: str
    size: int | str
    seeders: int | str
    leechers:int | str
    date: int | str

    def __post_init__(self):
        from modules import globals
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if self.size < 1024:
                break
            self.size /= 1024
        self.size = f"{self.size:.1f}{unit}"
        self.seeders = str(self.seeders)
        self.leechers = str(self.leechers)
        self.date = dt.datetime.fromtimestamp(self.date).strftime(globals.settings.datestamp_format)


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


class TupleDict(collections.UserDict):
    """Dict with a tuple key and a single non-iterable value"""
    def get_value(self, key: typing.Hashable):
        value = [v for k, v in self.items() if key in k]
        return value[0] if value else None

    def get_key(self, value: typing.Hashable, full_list=False):
        for keys, v in self.items():
            if value == v:
                return keys if full_list else keys[0]
        return None


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


Screen = IntEnumHack("Screen", [
    "Tracker",
    "Reminders",
    "Favorites"
])


Status = IntEnumHack("Status", [
    ("Normal",    (1, {"color" : (0.95, 0.95, 0.95), "icon": "lightning_bolt_circle"})),
    ("Completed", (2, {"color" : (0.00, 0.87, 0.00), "icon": "checkbox_marked_circle"})),
    ("OnHold",    (3, {"color" : (0.00, 0.50, 0.95), "icon": "pause_circle"})),
    ("Abandoned", (4, {"color" : (0.87, 0.20, 0.20), "icon": "close_circle"})),
    ("Unchecked", (5, {"color" : (0.50, 0.50, 0.50), "icon": "alert_circle"})),
    ("Custom",    (6, {"color" : (0.95, 0.50, 0.00), "icon": "dots_horizontal_circle"})),
])


status_equivalence_dict = TupleDict({
    ("normal",):    Status.Normal,
    ("completed",): Status.Completed,
    ("onhold",):    Status.OnHold,
    ("abandoned",): Status.Abandoned,
    ("unchecked",): Status.Unchecked,
    ("custom",):    Status.Custom,
})


Tag = IntEnumHack("Tag", [
    ("2d-game",                1),
    ("2dcg",                   2),
    ("3d-game",                3),
    ("3dcg",                   4),
    ("adventure",              5),
    ("ahegao",                 6),
    ("ai-cg",                  140),
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
    ("netorare",               90),
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

CLEAR_TAGS = [
    "2d game",
    "2dcg",
    "3d game",
    "3dcg",
    "adventure",
    "ahegao",
    "ai cg",
    "anal sex",
    "animated",
    "asset-addon",
    "asset-ai-shoujo",
    "asset-animal",
    "asset-animation",
    "asset-audio",
    "asset-bundle",
    "asset-character",
    "asset-clothing",
    "asset-environment",
    "asset-expression",
    "asset-hair",
    "asset-hdri",
    "asset-honey-select",
    "asset-honey-select2",
    "asset-koikatu",
    "asset-light",
    "asset-morph",
    "asset-plugin",
    "asset-pose",
    "asset-prop",
    "asset-script",
    "asset-shader",
    "asset-texture",
    "asset-utility",
    "asset-vehicle",
    "bdsm",
    "bestiality",
    "big ass",
    "big tits",
    "blackmail",
    "bukkake",
    "censored",
    "character creation",
    "cheating",
    "combat",
    "corruption",
    "cosplay",
    "creampie",
    "dating sim",
    "dilf",
    "drugs",
    "dystopian setting",
    "exhibitionism",
    "fantasy",
    "female protagonist",
    "femaledomination",
    "footjob",
    "furry",
    "futa/trans protagonist",
    "futa/trans",
    "gay",
    "graphic violence",
    "groping",
    "group sex",
    "handjob",
    "harem",
    "horror",
    "humiliation",
    "humor",
    "incest",
    "internal view",
    "interracial",
    "japanese game",
    "kinetic novel",
    "lactation",
    "lesbian",
    "loli",
    "male protagonist",
    "maledomination",
    "management",
    "masturbation",
    "milf",
    "mind control",
    "mobile game",
    "monster girl",
    "monster",
    "multiple endings",
    "multiple penetration",
    "multiple protagonist",
    "necrophilia",
    "no sexual content",
    "netorare",
    "oral sex",
    "paranormal",
    "parody",
    "platformer",
    "point & click",
    "possession",
    "pov",
    "pregnancy",
    "prostitution",
    "puzzle",
    "rape",
    "real porn",
    "religion",
    "romance",
    "rpg",
    "sandbox",
    "scat",
    "school setting",
    "sci-fi",
    "sex toys",
    "sexual harassment",
    "shooter",
    "shota",
    "side-scroller",
    "simulator",
    "sissification",
    "slave",
    "sleep sex",
    "spanking",
    "strategy",
    "stripping",
    "superpowers",
    "swinging",
    "teasing",
    "tentacles",
    "text based",
    "titfuck",
    "trainer",
    "transformation",
    "trap",
    "turn based combat",
    "twins",
    "urination",
    "vaginal sex",
    "virgin",
    "virtual reality",
    "voiced",
    "vore",
    "voyeurism"
]


ExeState = IntEnumHack("ExeState", [
    "Invalid",
    "Selected",
    "Unset",
])


exe_equivalence_dict = TupleDict({
    ("invalid",):   ExeState.Invalid,
    ("selected",):  ExeState.Selected,
    ("unset",):     ExeState.Unset,
})


MsgBox = IntEnumHack("MsgBox", [
    ("info",  (1, {"color": (0.10, 0.69, 0.95), "icon": "information"})),
    ("warn",  (2, {"color": (0.95, 0.69, 0.10), "icon": "alert_rhombus"})),
    ("error", (3, {"color": (0.95, 0.22, 0.22), "icon": "alert_octagon"})),
])


FilterMode = IntEnumHack("FilterMode", [
    "Archived",
    "Custom",
    "Developer",
    "ExeState",
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


mode_equivalance_dict = TupleDict({
    ("archived",    "a"            ):   FilterMode.Archived,
    ("custom",      "c"            ):   FilterMode.Custom,
    ("developer",   "d",      "dev"):   FilterMode.Developer,
    ("exe",         "e",           ):   FilterMode.ExeState,
    ("installed",   "i",     "inst"):   FilterMode.Installed,
    ("label",       "l"            ):   FilterMode.Label,
    ("played",      "p"            ):   FilterMode.Played,
    ("rating",      "r"            ):   FilterMode.Rating,
    ("score",       "s"            ):   FilterMode.Score,
    ("status",      "st"           ):   FilterMode.Status,
    ("tag",         "t"            ):   FilterMode.Tag,
    ("type",        "tp"           ):   FilterMode.Type,
    ("updated",     "u",      "upd"):   FilterMode.Updated,
})


Category = IntEnumHack("Category", [
    "Games",
    "Media",
    "Misc",
])


@dataclasses.dataclass
class Filter:
    mode: FilterMode
    value: typing.Any
    raw_mode: str = ""
    raw_value: str = ""
    inverted: bool = False
    signop: typing.Callable = None

    def __init__(self, mode, value, quick: bool = False):
        if quick:
            self.mode = mode
            self.value = value
            self.raw_mode = mode_equivalance_dict.get_key(mode)
        else:
            self.raw_mode = mode
            self._extract_special_characters(value)
            self.mode = mode_equivalance_dict.get_value(self.raw_mode)
        match self.mode:
            case FilterMode.Archived:
                if quick:
                    self.raw_value = "yes"
                else:
                    self._convert_value_to_bool()
            case FilterMode.Custom:
                if quick:
                    self.raw_value = True
                else:
                    self._convert_value_to_bool()
            case FilterMode.Developer:
                if quick:
                    self.raw_value = f"'{value}'"
                else:
                    pass
            case FilterMode.ExeState:
                if quick:
                    self.raw_value = exe_equivalence_dict.get_key(value)
                else:
                    self.value = exe_equivalence_dict.get_value(self.value)
            case FilterMode.Installed:
                if quick:
                    self.raw_value = "yes"
                else:
                    self._convert_value_to_bool()
            case FilterMode.Label:
                if quick:
                    self.raw_value = f"'{value}'"
                else:
                    pass
            case FilterMode.Played:
                if quick:
                    self.raw_value = "yes"
                else:
                    self._convert_value_to_bool()
            case FilterMode.Rating:
                if quick:
                    pass
                else:
                    self._convert_value_to_float()
            case FilterMode.Score:
                if quick:
                    pass
                else:
                    self._convert_value_to_float()
            case FilterMode.Status:
                if quick:
                    self.raw_value = status_equivalence_dict.get_key(value)
                else:
                    self.value = status_equivalence_dict.get_value(self.value)
            case FilterMode.Tag:
                if quick:
                    self.raw_value = value
                else:
                    pass
            case FilterMode.Type:
                if quick:
                    self.raw_value = type_equivalence_dict.get_key(value)
                else:
                    self.value = type_equivalence_dict.get_value(self.value)
            case FilterMode.Updated:
                if quick:
                    self.raw_value = "yes"
                else:
                    self._convert_value_to_bool()
            case _:
                raise TypeError

    def _extract_special_characters(self, raw_value):
        self.value = str(raw_value)
        self.value = self.value.strip("'").strip('"')
        self.raw_value = self.value
        if self.raw_mode.startswith("-"):
            self.inverted = True
            self.raw_mode = self.raw_mode[1:]
        if self.value.startswith(">="):
            self.signop = operator.ge
            self.value = self.value[2:]
        elif self.value.startswith("<="):
            self.signop = operator.le
            self.value = self.value[2:]
        elif self.value.startswith(">"):
            self.signop = operator.gt
            self.value = self.value[1:]
        elif self.value.startswith("<"):
            self.signop = operator.lt
            self.value = self.value[1:]

    def _convert_value_to_bool(self):
        if self.value in ["yes", "y", "+"]:
            self.value = True
        elif self.value in ["no", "n", "-"]:
            self.value = False
        else:
            raise TypeError

    def _convert_value_to_float(self):
        try:
            self.value = float(self.value)
        except Exception:
            raise TypeError

    def __str__(self):
        return f"{self.raw_mode}:{self.raw_value}"

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
    copy_urls_as_bbcode         : bool
    cycle_images                : bool
    cycle_length                : int
    cycle_on_hover              : bool
    cycle_random_order          : bool
    datestamp_format            : str
    default_exe_dir             : str
    display_mode                : DisplayMode
    ext_highlight_tags          : bool
    ext_tags_critical           : list[str]
    ext_tags_negative           : list[str]
    ext_tags_positive           : list[str]
    fit_images                  : bool
    fit_additional_images       : bool
    grid_columns                : int
    ignore_semaphore_timeouts   : bool
    interface_scaling           : float
    last_successful_refresh     : Timestamp
    manual_sort_list            : list[int]
    manual_sort_list_reminders  : list[int]
    manual_sort_list_favorites  : list[int]
    mark_installed_after_add    : bool
    max_retries                 : int
    quick_filters               : bool
    refresh_completed_games     : bool
    refresh_workers             : int
    reminders_in_filtered       : bool
    favorites_in_filtered       : bool
    render_when_unfocused       : bool
    request_timeout             : int
    rpc_enabled                 : bool
    rpdl_username               : str
    rpdl_password               : str
    rpdl_token                  : str
    scroll_amount               : float
    scroll_smooth               : bool
    scroll_smooth_speed         : float
    select_executable_after_add : bool
    separate_sections_sorting   : bool
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
    use_parser_processes        : bool
    vsync_ratio                 : int
    zoom_area                   : int
    zoom_times                  : float
    zoom_enabled                : bool


from modules import (
    imagehelper,
    colors,
)

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

type_equivalence_dict = TupleDict({
    ("adrift",):     Type.ADRIFT,
    ("flash",):      Type.Flash,
    ("html",):       Type.HTML,
    ("java",):       Type.Java,
    ("others",):     Type.Others,
    ("qsp",):        Type.QSP,
    ("rags",):       Type.RAGS,
    ("renpy",):      Type.RenPy,
    ("rpgm",):       Type.RPGM,
    ("tads",):       Type.Tads,
    ("unity",):      Type.Unity,
    ("unreal",):     Type.Unreal_Eng,
    ("webgl",):      Type.WebGL,
    ("wolf",):       Type.Wolf_RPG,
    ("cg",):         Type.CG,
    ("collection",): Type.Collection,
    ("comics",):     Type.Comics,
    ("gif",):        Type.GIF,
    ("manga",):      Type.Manga,
    ("pinup",):      Type.Pinup,
    ("rip",):        Type.SiteRip,
    ("video",):      Type.Video,
    ("cheatmod",):   Type.Cheat_Mod,
    ("mod",):        Type.Mod,
    ("readme",):     Type.READ_ME,
    ("request",):    Type.Request,
    ("tool",):       Type.Tool,
    ("tutorial",):   Type.Tutorial,
    ("misc",):       Type.Misc,
    ("unchecked",):  Type.Unchecked,
})

@dataclasses.dataclass
class Game:
    id                 : int
    custom             : bool | None
    name               : str
    version            : str
    developer          : str
    type               : Type
    status             : Status
    url                : str
    added_on           : Datestamp
    last_updated       : Datestamp
    last_full_check    : int
    last_check_version : str
    last_played        : Datestamp
    score              : float
    rating             : int
    played             : bool
    installed          : str
    updated            : bool | None
    archived           : bool
    reminder           : bool
    favorite           : bool
    executables        : list[str]
    description        : str
    changelog          : str
    tags               : tuple[Tag]
    labels             : list[Label.get]
    notes              : str
    banner_url         : str
    attachment_urls    : list[str]
    downloads          : tuple[tuple[str, list[tuple[str, str]]]]
    highest_file_index : int = 0
    selected           : bool = False
    images_path        : pathlib.Path = None
    banner             : imagehelper.ImageHelper = None
    additional_images  : list[imagehelper.ImageHelper] = None
    executables_valids : list[bool] = None
    executables_valid  : bool = None
    _did_init          : bool = False

    def __post_init__(self):
        self._did_init = True
        if self.custom is None:
            self.custom = bool(self.status is Status.Custom)
        if self.updated is None:
            self.updated = bool(self.installed) and self.installed != self.version
        if self.banner_url == "-":
            self.banner_url = "missing"
        self.init_images()
        self.validate_executables()

    def init_images(self):
        from modules import globals
        self.images_path = globals.images_path / str(self.id)
        self.images_path.mkdir(parents=True, exist_ok=True)
        self.banner = imagehelper.ImageHelper(self.images_path, glob=f"banner.*")
        self.additional_images = []
        for item in self.images_path.iterdir():
            if item.is_file() and item.stem != "banner":
                try:
                    filename = int(item.stem)
                except ValueError:
                    continue
                image = imagehelper.ImageHelper(self.images_path, glob=f"{filename}.*")
                self.additional_images.append(image)
        if self.additional_images:
            self.sort_images()
            self.highest_file_index = int(self.additional_images[-1].resolved_path.stem)

    def sort_images(self):
        self.additional_images.sort(key=lambda helper: int(helper.resolved_path.stem))

    def add_image(self, b: bytes):
        self.highest_file_index += 1
        filename = str(self.highest_file_index)
        self.set_image_sync(b, filename=filename)
        image = imagehelper.ImageHelper(self.images_path, glob=f"{filename}.*")
        self.additional_images.append(image)

    async def add_image_async(self, b: bytes):
        self.highest_file_index += 1
        filename = str(self.highest_file_index)
        await self.set_image_async(b, filename=filename)
        image = imagehelper.ImageHelper(self.images_path, glob=f"{filename}.*")
        self.additional_images.append(image)

    def delete_image(self, filename: str = "banner", all=False):
        try:
            for file in self.images_path.glob(f"{filename}.*") if not all else self.images_path.iterdir():
                    file.unlink()
        except Exception:
            pass

    def image_banner_swap(self, image_id: int):
        if self.banner.invalid or self.banner.missing:
            self.delete_image()
            image = self.additional_images[image_id]
            os.replace(image.resolved_path.absolute(), image.resolved_path.with_stem("banner"))
            del self.additional_images[image_id]
        else:
            image = self.additional_images[image_id]
            image_filename = image.resolved_path.stem
            banner = next(self.images_path.glob("banner.*"))
            os.rename(banner.absolute(), banner.with_name("bannertemp"))
            temp_banner = self.images_path / "bannertemp"
            os.rename(image.resolved_path.absolute(), image.resolved_path.with_stem("banner"))
            os.rename(temp_banner.absolute(), temp_banner.with_name(f"{image_filename}{banner.suffix}"))
            image.loaded = False
            image.resolve()
        self.refresh_banner()

    def refresh_banner(self):
        self.banner.glob = f"banner.*"
        self.banner.loaded = False
        self.banner.resolve()

    async def set_image_async(self, data: bytes, filename: str = "banner"):
        from modules import globals, utils
        self.delete_image(filename)
        if data:
            async with aiofiles.open(self.images_path / f"{filename}.{utils.image_ext(data)}", "wb") as f:
                await f.write(data)
        self.refresh_banner()

    def set_image_sync(self, data: bytes, filename: str = "banner"):
        from modules import globals, utils
        self.delete_image(filename)
        if data:
            (self.images_path / f"{filename}.{utils.image_ext(data)}").write_bytes(data)
        self.refresh_banner()

    def apply_new_image_order(self):
        if not self.additional_images:
            pass
        # adding underscore to avoid name conflicts during rename
        for new_index, helper in enumerate(self.additional_images):
            new_index += 1
            old_path = helper.resolved_path
            if new_index != int(old_path.stem):
                os.rename(old_path, old_path.with_stem(f"_{new_index}"))
        for root, _, files in os.walk(self.images_path):
            for file in files:
                if file.startswith("_"):
                    org_fp = os.path.join(root, file)
                    new_fp = os.path.join(root, file[1:])
                    os.rename(org_fp, new_fp)

    def validate_executables(self):
        from modules import globals, utils
        self.executables_valids = [utils.is_uri(executable) or os.path.isfile(executable) for executable in self.executables]
        self.executables_valid = all(self.executables_valids)
        if globals.gui:
            globals.gui.require_sort = True

    def add_executable(self, executable: str):
        if executable in self.executables:
            return
        self.executables.append(executable)
        from modules import async_thread, db
        async_thread.run(db.update_game(self, "executables"))
        self.validate_executables()

    def remove_executable(self, executable: str):
        self.executables.remove(executable)
        from modules import async_thread, db
        async_thread.run(db.update_game(self, "executables"))
        self.validate_executables()

    def clear_executables(self):
        self.executables.clear()
        from modules import async_thread, db
        async_thread.run(db.update_game(self, "executables"))
        self.validate_executables()

    def add_label(self, label: Label):
        if label not in self.labels:
            self.labels.append(label)
        self.labels.sort(key=lambda label: Label.instances.index(label))
        from modules import globals, async_thread, db
        async_thread.run(db.update_game(self, "labels"))
        if globals.gui:
            globals.gui.require_sort = True

    def remove_label(self, label: Label):
        while label in self.labels:
            self.labels.remove(label)
        from modules import globals, async_thread, db
        async_thread.run(db.update_game(self, "labels"))
        if globals.gui:
            globals.gui.require_sort = True

    def __setattr__(self, name: str, value: typing.Any):
        if self._did_init and name in [
            "custom",
            "name",
            "version",
            "developer",
            "type",
            "status",
            "url",
            "added_on",
            "last_updated",
            "last_full_check",
            "last_check_version",
            "last_played",
            "score",
            "rating",
            "played",
            "installed",
            "updated",
            "archived",
            "reminder",
            "favorite",
            "executables",
            "description",
            "changelog",
            "tags",
            "labels",
            "notes",
            "banner_url",
            "attachment_urls",
            "downloads"
        ]:
            if isinstance(attr := getattr(self, name), Timestamp):
                attr.update(value)
            else:
                super().__setattr__(name, value)
            from modules import globals, async_thread, db
            async_thread.run(db.update_game(self, name))
            if globals.gui:
                globals.gui.require_sort = True
            return
        super().__setattr__(name, value)
        if name == "selected":
            from modules import globals
            if globals.gui:
                if value:
                    globals.gui.last_selected_game = self
                globals.gui.selected_games_count = len(list(filter(lambda game: game.selected, globals.games.values())))


@dataclasses.dataclass
class OldGame:
    id                   : int
    name                 : str
    version              : str
    status               : Status
