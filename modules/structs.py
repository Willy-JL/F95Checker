from PyQt6.QtWidgets import QSystemTrayIcon
import dataclasses
import datetime
import asyncio
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
    def __init__(self, unix_time: int | float, format="%d/%m/%Y %H:%M"):
        self.format = format
        self.display = ""
        self.value = 0
        self.update(unix_time)

    def update(self, unix_time: int | float):
        self.value = int(unix_time)
        if self.value == 0:
            self.display = ""
        else:
            self.display = datetime.datetime.fromtimestamp(unix_time).strftime(self.format)


class Datestamp(Timestamp):
    def __init__(self, unix_time: int | float):
        super().__init__(unix_time, format="%d/%m/%Y")


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
    icon: QSystemTrayIcon.MessageIcon

    def __post_init__(self):
        # KDE Plasma for some reason doesn't dispatch clicks if the icon is not critical
        if os.environ.get("DESKTOP_SESSION") == "plasma" or \
        os.environ.get("XDG_SESSION_DESKTOP") == "KDE" or \
        os.environ.get("XDG_CURRENT_DESKTOP") == "KDE":
            self.icon = QSystemTrayIcon.MessageIcon.Critical


class EnumNameHack(enum.Enum):
    # Remove leading and trailing _
    # "_"  => " "
    # "__" => "-"
    def __init__(self, *args):
        self._name_ = self._name_.strip("_").replace("__", "-").replace("_", " ")
        super().__init__()


class IntEnum(enum.IntEnum):
    # Make a _members_ attribute with modified names
    def __init__(self, *args):
        cls = type(self)
        if not hasattr(cls, "_members_"):
            cls._members_ = {}
        cls._members_[self._name_] = self
        cls._members_list_ = list(cls._members_)
        super().__init__()


class EnumAutoValue(enum.Enum):
    # Automatically assign incrementing values
    # Ignores value assigned in class definition
    def __new__(cls, *args):
        value = len(cls.__members__) + 1
        obj = int.__new__(cls)
        obj._value_ = value
        return obj


class Os(IntEnum, EnumAutoValue):
    Windows = ()
    MacOS   = ()
    Linux   = ()


class DisplayMode(IntEnum):
    list = 1
    grid = 2


class Status(EnumNameHack, IntEnum):
    Normal          = 1
    Completed       = 2
    OnHold          = 3
    Abandoned       = 4
    Unchecked       = 5


class Tag(EnumNameHack, IntEnum):
    _2d__game                = 1
    _2dcg                    = 2
    _3d__game                = 3
    _3dcg                    = 4
    adventure                = 5
    ahegao                   = 6
    anal__sex                = 7
    animated                 = 8
    asset__addon             = 9
    asset__ai__shoujo        = 10
    asset__animal            = 11
    asset__animation         = 12
    asset__audio             = 13
    asset__bundle            = 14
    asset__character         = 15
    asset__clothing          = 16
    asset__environment       = 17
    asset__expression        = 18
    asset__hair              = 19
    asset__hdri              = 20
    asset__honey__select     = 21
    asset__honey__select2    = 22
    asset__koikatu           = 23
    asset__light             = 24
    asset__morph             = 25
    asset__plugin            = 26
    asset__pose              = 27
    asset__prop              = 28
    asset__script            = 29
    asset__shader            = 30
    asset__texture           = 31
    asset__utility           = 32
    asset__vehicle           = 33
    bdsm                     = 34
    bestiality               = 35
    big__ass                 = 36
    big__tits                = 37
    blackmail                = 38
    bukkake                  = 39
    censored                 = 40
    character__creation      = 41
    cheating                 = 42
    combat                   = 43
    corruption               = 44
    cosplay                  = 45
    creampie                 = 46
    dating__sim              = 47
    dilf                     = 48
    drugs                    = 49
    dystopian__setting       = 50
    exhibitionism            = 51
    fantasy                  = 52
    female__protagonist      = 54
    femaledomination         = 53
    footjob                  = 55
    furry                    = 56
    futa__trans              = 57
    futa__trans__protagonist = 58
    gay                      = 59
    graphic__violence        = 60
    groping                  = 61
    group__sex               = 62
    handjob                  = 63
    harem                    = 64
    horror                   = 65
    humiliation              = 66
    humor                    = 67
    incest                   = 68
    internal__view           = 69
    interracial              = 70
    japanese__game           = 71
    kinetic__novel           = 72
    lactation                = 73
    lesbian                  = 74
    loli                     = 75
    male__protagonist        = 77
    maledomination           = 76
    management               = 78
    masturbation             = 79
    milf                     = 80
    mind__control            = 81
    mobile__game             = 82
    monster                  = 83
    monster__girl            = 84
    multiple__endings        = 85
    multiple__penetration    = 86
    multiple__protagonist    = 87
    necrophilia              = 88
    no__sexual__content      = 89
    ntr                      = 90
    oral__sex                = 91
    paranormal               = 92
    parody                   = 93
    platformer               = 94
    point__click             = 95
    possession               = 96
    pov                      = 97
    pregnancy                = 98
    prostitution             = 99
    puzzle                   = 100
    rape                     = 101
    real__porn               = 102
    religion                 = 103
    romance                  = 104
    rpg                      = 105
    sandbox                  = 106
    scat                     = 107
    school__setting          = 108
    sci__fi                  = 109
    sex__toys                = 110
    sexual__harassment       = 111
    shooter                  = 112
    shota                    = 113
    side__scroller           = 114
    simulator                = 115
    sissification            = 116
    slave                    = 117
    sleep__sex               = 118
    spanking                 = 119
    strategy                 = 120
    stripping                = 121
    superpowers              = 122
    swinging                 = 123
    teasing                  = 124
    tentacles                = 125
    text__based              = 126
    titfuck                  = 127
    trainer                  = 128
    transformation           = 129
    trap                     = 130
    turn__based__combat      = 131
    twins                    = 132
    urination                = 133
    vaginal__sex             = 134
    virgin                   = 135
    virtual__reality         = 136
    voiced                   = 137
    vore                     = 138
    voyeurism                = 139


class MsgBox(IntEnum, EnumAutoValue):
    info  = ()
    warn  = ()
    error = ()


class FilterMode(EnumNameHack, IntEnum, EnumAutoValue):
    Choose    = ()
    Installed = ()
    Played    = ()
    Rating    = ()
    Status    = ()
    Tag       = ()
    Type      = ()
    Updated   = ()


@dataclasses.dataclass
class Filter:
    mode: FilterMode
    invert = False
    match = None
    include_outdated = True

    def __post_init__(self):
        self.id = id(self)


from modules import imagehelper, utils

@dataclasses.dataclass
class Browser:
    name: str
    hash: int = None
    args: list[str] = None
    hashed_name: str = None
    unset: bool = None
    is_custom: bool = None
    private_arg: list = None

    def __post_init__(self):
        cls = type(self)
        if self.hash is None:
            self.hash = utils.hash(self.name)
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
    def add(cls, *args, **kwargs):
        self = cls(*args, **kwargs)
        if not hasattr(cls, "available"):
            cls.available: dict[str, cls] = {}
        if not hasattr(cls, "avail_list"):
            cls.avail_list: list[str] = []
        if self.hashed_name in cls.available:
            return
        cls.available[self.hashed_name] = self
        cls.avail_list.append(self.hashed_name)
        for browser in cls.available.values():
            browser.index = cls.avail_list.index(browser.hashed_name)

    @classmethod
    def get(cls, hash):
        for browser in cls.available.values():
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
    default_exe_dir             : str
    display_mode                : DisplayMode
    fit_images                  : bool
    grid_columns                : int
    grid_image_ratio            : float
    interface_scaling           : float
    last_successful_refresh     : Timestamp
    manual_sort_list            : list
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
    tray_refresh_interval       : int
    tray_notifs_interval        : int
    update_keep_image           : bool
    vsync_ratio                 : int
    zoom_amount                 : int
    zoom_enabled                : bool
    zoom_region                 : bool
    zoom_size                   : int


class Type(EnumNameHack, IntEnum):
    Unchecked     = 23
    Misc          = 1
    ADRIFT        = 2
    CG            = 30
    Cheat_Mod     = 3
    Collection    = 7
    Comics        = 24
    Flash         = 4
    GIF           = 25
    HTML          = 5
    Java          = 6
    Manga         = 26
    Mod           = 8
    Others        = 9
    Pinup         = 27
    QSP           = 10
    RAGS          = 11
    READ_ME       = 12
    RenPy         = 14
    Request       = 15
    RPGM          = 13
    SiteRip       = 28
    Tads          = 16
    Tool          = 17
    Tutorial      = 18
    Unity         = 19
    Unreal_Eng    = 20
    Video         = 29
    WebGL         = 21
    Wolf_RPG      = 22

Type.Unchecked .color = utils.hex_to_rgba_0_1("#393939")
Type.Misc      .color = utils.hex_to_rgba_0_1("#B8B00C")
Type.ADRIFT    .color = utils.hex_to_rgba_0_1("#2196F3")
Type.CG        .color = utils.hex_to_rgba_0_1("#FFEB3B")
Type.Cheat_Mod .color = utils.hex_to_rgba_0_1("#D32F2F")
Type.Collection.color = utils.hex_to_rgba_0_1("#616161")
Type.Comics    .color = utils.hex_to_rgba_0_1("#FF9800")
Type.Flash     .color = utils.hex_to_rgba_0_1("#616161")
Type.GIF       .color = utils.hex_to_rgba_0_1("#03A9F4")
Type.HTML      .color = utils.hex_to_rgba_0_1("#689F38")
Type.Java      .color = utils.hex_to_rgba_0_1("#52A6B0")
Type.Manga     .color = utils.hex_to_rgba_0_1("#0FB2FC")
Type.Mod       .color = utils.hex_to_rgba_0_1("#BA4545")
Type.Others    .color = utils.hex_to_rgba_0_1("#8BC34A")
Type.Pinup     .color = utils.hex_to_rgba_0_1("#2196F3")
Type.QSP       .color = utils.hex_to_rgba_0_1("#D32F2F")
Type.RAGS      .color = utils.hex_to_rgba_0_1("#FF9800")
Type.READ_ME   .color = utils.hex_to_rgba_0_1("#DC143C")
Type.RenPy     .color = utils.hex_to_rgba_0_1("#B069E8")
Type.Request   .color = utils.hex_to_rgba_0_1("#D32F2F")
Type.RPGM      .color = utils.hex_to_rgba_0_1("#2196F3")
Type.SiteRip   .color = utils.hex_to_rgba_0_1("#8BC34A")
Type.Tads      .color = utils.hex_to_rgba_0_1("#2196F3")
Type.Tool      .color = utils.hex_to_rgba_0_1("#EC5555")
Type.Tutorial  .color = utils.hex_to_rgba_0_1("#EC5555")
Type.Unity     .color = utils.hex_to_rgba_0_1("#FE5901")
Type.Unreal_Eng.color = utils.hex_to_rgba_0_1("#0D47A1")
Type.Video     .color = utils.hex_to_rgba_0_1("#FF9800")
Type.WebGL     .color = utils.hex_to_rgba_0_1("#FE5901")
Type.Wolf_RPG  .color = utils.hex_to_rgba_0_1("#4CAF50")


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
    rating               : int
    played               : bool
    installed            : str
    executable           : str
    description          : str
    changelog            : str
    tags                 : list[Tag]
    notes                : str
    image                : imagehelper.ImageHelper
    image_url            : str


@dataclasses.dataclass
class OldGame:
    id                   : int
    name                 : str
    version              : str
    status               : Status
