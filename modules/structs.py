import datetime as dt
import dataclasses
import asyncio
import hashlib
import typing
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


class Timestamp:
    instances: list[typing.Self] = []
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
    instances: list[typing.Self] = []
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
    ("list", 1),
    ("grid", 2),
])


Status = IntEnumHack("Status", [
    ("Normal",    1),
    ("Completed", 2),
    ("OnHold",    3),
    ("Abandoned", 4),
    ("Unchecked", 5),
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
    "info",
    "warn",
    "error",
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
    unset: bool = None
    is_custom: bool = None
    private_arg: list = None
    instances: typing.ClassVar = {}
    avail_list: typing.ClassVar = []

    def __post_init__(self):
        if self.hash is None:
            self.hash = self.make_hash(self.name)
        self.hashed_name = f"{self.name}###{self.hash}"
        self.unset = self.hash == 0
        self.is_custom = self.hash == -1
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

Browser.add("None", 0)
Browser.add("Custom", -1)


@dataclasses.dataclass
class Settings:
    browser                     : Browser.get
    browser_custom_arguments    : str
    browser_custom_executable   : str
    browser_html                : bool
    browser_private             : bool
    check_notifs                : bool
    confirm_on_remove           : bool
    datestamp_format            : str
    default_exe_dir             : str
    display_mode                : DisplayMode
    fit_images                  : bool
    grid_columns                : int
    grid_image_ratio            : float
    ignore_semaphore_timeouts   : bool
    interface_scaling           : float
    last_successful_refresh     : Timestamp
    manual_sort_list            : list[int]
    max_retries                 : int
    minimize_on_close           : bool
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
    start_in_tray               : bool
    start_refresh               : bool
    style_accent                : tuple[float]
    style_alt_bg                : tuple[float]
    style_bg                    : tuple[float]
    style_border                : tuple[float]
    style_corner_radius         : int
    style_text                  : tuple[float]
    style_text_dim              : tuple[float]
    timestamp_format            : str
    tray_notifs_interval        : int
    tray_refresh_interval       : int
    update_keep_image           : bool
    use_parser_processes        : bool
    vsync_ratio                 : int
    zoom_area                   : int
    zoom_times                  : float
    zoom_enabled                : bool


from modules import colors, imagehelper

Type = IntEnumHack("Type", [
    ("Unchecked",  23),
    ("Misc",       1),
    ("ADRIFT",     2),
    ("CG",         30),
    ("Cheat Mod",  3),
    ("Collection", 7),
    ("Comics",     24),
    ("Flash",      4),
    ("GIF",        25),
    ("HTML",       5),
    ("Java",       6),
    ("Manga",      26),
    ("Mod",        8),
    ("Others",     9),
    ("Pinup",      27),
    ("QSP",        10),
    ("RAGS",       11),
    ("READ ME",    12),
    ("RenPy",      14),
    ("Request",    15),
    ("RPGM",       13),
    ("SiteRip",    28),
    ("Tads",       16),
    ("Tool",       17),
    ("Tutorial",   18),
    ("Unity",      19),
    ("Unreal Eng", 20),
    ("Video",      29),
    ("WebGL",      21),
    ("Wolf RPG",   22),
])

Type.Unchecked .color = colors.hex_to_rgba_0_1("#393939")
Type.Misc      .color = colors.hex_to_rgba_0_1("#B8B00C")
Type.ADRIFT    .color = colors.hex_to_rgba_0_1("#2196F3")
Type.CG        .color = colors.hex_to_rgba_0_1("#FFEB3B")
Type.Cheat_Mod .color = colors.hex_to_rgba_0_1("#D32F2F")
Type.Collection.color = colors.hex_to_rgba_0_1("#616161")
Type.Comics    .color = colors.hex_to_rgba_0_1("#FF9800")
Type.Flash     .color = colors.hex_to_rgba_0_1("#616161")
Type.GIF       .color = colors.hex_to_rgba_0_1("#03A9F4")
Type.HTML      .color = colors.hex_to_rgba_0_1("#689F38")
Type.Java      .color = colors.hex_to_rgba_0_1("#52A6B0")
Type.Manga     .color = colors.hex_to_rgba_0_1("#0FB2FC")
Type.Mod       .color = colors.hex_to_rgba_0_1("#BA4545")
Type.Others    .color = colors.hex_to_rgba_0_1("#8BC34A")
Type.Pinup     .color = colors.hex_to_rgba_0_1("#2196F3")
Type.QSP       .color = colors.hex_to_rgba_0_1("#D32F2F")
Type.RAGS      .color = colors.hex_to_rgba_0_1("#FF9800")
Type.READ_ME   .color = colors.hex_to_rgba_0_1("#DC143C")
Type.RenPy     .color = colors.hex_to_rgba_0_1("#B069E8")
Type.Request   .color = colors.hex_to_rgba_0_1("#D32F2F")
Type.RPGM      .color = colors.hex_to_rgba_0_1("#2196F3")
Type.SiteRip   .color = colors.hex_to_rgba_0_1("#8BC34A")
Type.Tads      .color = colors.hex_to_rgba_0_1("#2196F3")
Type.Tool      .color = colors.hex_to_rgba_0_1("#EC5555")
Type.Tutorial  .color = colors.hex_to_rgba_0_1("#EC5555")
Type.Unity     .color = colors.hex_to_rgba_0_1("#FE5901")
Type.Unreal_Eng.color = colors.hex_to_rgba_0_1("#0D47A1")
Type.Video     .color = colors.hex_to_rgba_0_1("#FF9800")
Type.WebGL     .color = colors.hex_to_rgba_0_1("#FE5901")
Type.Wolf_RPG  .color = colors.hex_to_rgba_0_1("#4CAF50")


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
