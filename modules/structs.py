import dataclasses
import datetime
import enum

from modules import imagehelper, utils


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


class Browser(EnumNameHack, IntEnum):
    _None    = 1
    Chrome   = 2
    Firefox  = 3
    Brave    = 4
    Edge     = 5
    Opera    = 6
    Opera_GX = 7
    Custom   = 8

Browser.Chrome  .private = "-incognito"
Browser.Firefox .private = "-private-window"
Browser.Brave   .private = "-incognito"
Browser.Edge    .private = "-inprivate"
Browser.Opera   .private = "-private"
Browser.Opera_GX.private = "-private"


class DisplayMode(IntEnum):
    list = 1
    grid = 2


class Type(EnumNameHack, IntEnum):
    Others        = 1
    ADRIFT        = 2
    Cheat_Mod     = 3
    Collection    = 4
    Flash         = 5
    HTML          = 6
    Java          = 7
    Mod           = 8
    QSP           = 9
    RAGS          = 10
    READ_ME       = 11
    RPGM          = 12
    RenPy         = 13
    Request       = 14
    Tads          = 15
    Tool          = 16
    Tutorial      = 17
    Unity         = 18
    Unreal_Engine = 19
    WebGL         = 20
    Wolf_RPG      = 21

Type.Others       .color = utils.hex_to_rgba_0_1("#8BC34A")
Type.ADRIFT       .color = utils.hex_to_rgba_0_1("#2196F3")
Type.Cheat_Mod    .color = utils.hex_to_rgba_0_1("#D32F2F")
Type.Collection   .color = utils.hex_to_rgba_0_1("#616161")
Type.Flash        .color = utils.hex_to_rgba_0_1("#616161")
Type.HTML         .color = utils.hex_to_rgba_0_1("#689F38")
Type.Java         .color = utils.hex_to_rgba_0_1("#52A6B0")
Type.Mod          .color = utils.hex_to_rgba_0_1("#BA4545")
Type.QSP          .color = utils.hex_to_rgba_0_1("#D32F2F")
Type.RAGS         .color = utils.hex_to_rgba_0_1("#FF9800")
Type.READ_ME      .color = utils.hex_to_rgba_0_1("#DC143C")
Type.RPGM         .color = utils.hex_to_rgba_0_1("#2196F3")
Type.RenPy        .color = utils.hex_to_rgba_0_1("#B069E8")
Type.Request      .color = utils.hex_to_rgba_0_1("#D32F2F")
Type.Tads         .color = utils.hex_to_rgba_0_1("#2196F3")
Type.Tool         .color = utils.hex_to_rgba_0_1("#EC5555")
Type.Tutorial     .color = utils.hex_to_rgba_0_1("#EC5555")
Type.Unity        .color = utils.hex_to_rgba_0_1("#FE5901")
Type.Unreal_Engine.color = utils.hex_to_rgba_0_1("#0D47A1")
Type.WebGL        .color = utils.hex_to_rgba_0_1("#FE5901")
Type.Wolf_RPG     .color = utils.hex_to_rgba_0_1("#4CAF50")


class Status(IntEnum):
    Normal    = 1
    Completed = 2
    OnHold    = 3
    Abandoned = 4


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
    femaledomination         = 53
    female__protagonist      = 54
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
    maledomination           = 76
    male__protagonist        = 77
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


class FilterMode(EnumNameHack, IntEnum, EnumAutoValue):
    _None     = ()
    Installed = ()
    Played    = ()
    Rating    = ()
    Status    = ()
    Tag       = ()
    Type      = ()

FilterMode.Type.by = Type.Others
FilterMode.Type.invert = False

FilterMode.Status.by = Status.Normal
FilterMode.Status.invert = False

FilterMode.Rating.by = 0
FilterMode.Rating.invert = False

FilterMode.Played.invert = False

FilterMode.Installed.invert = False
FilterMode.Installed.include_outdated = True

FilterMode.Tag.by = Tag._2d__game
FilterMode.Tag.invert = False


class MsgBox(IntEnum, EnumAutoValue):
    info  = ()
    warn  = ()
    error = ()


class Timestamp:
    def __init__(self, unix_time: int | float, format="%d/%m/%Y"):
        self.format = format
        self.display = ""
        self.value = 0
        self.update(unix_time)

    def update(self, unix_time: int | float):
        self.value = int(unix_time)
        if self.value == 0:
            self.display = ""
        else:
            self.display = datetime.date.fromtimestamp(unix_time).strftime(self.format)


@dataclasses.dataclass
class Settings:
    browser_custom_arguments    : str
    browser_custom_executable   : str
    browser_html                : bool
    browser_private             : bool
    browser                     : Browser
    confirm_on_remove           : bool
    display_mode                : DisplayMode
    default_exe_dir             : str
    fit_images                  : bool
    grid_columns                : int
    grid_image_ratio            : float
    interface_scaling           : float
    manual_sort_list            : list
    minimize_on_close           : bool
    refresh_completed_games     : bool
    refresh_workers             : int
    request_timeout             : int
    scroll_amount               : float
    scroll_smooth               : bool
    scroll_smooth_speed         : float
    select_executable_after_add : bool
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
    update_keep_image           : bool
    vsync_ratio                 : int
    zoom_amount                 : int
    zoom_enabled                : bool
    zoom_region                 : bool
    zoom_size                   : int


class DefaultStyle:
    accent        = "#d4202e"
    alt_bg        = "#101010"
    bg            = "#0a0a0a"
    border        = "#454545"
    corner_radius = 6
    text          = "#ffffff"
    text_dim      = "#808080"


@dataclasses.dataclass
class Game:
    id                   : int
    name                 : str
    version              : str
    developer            : str
    type                 : Type
    status               : Status
    url                  : str
    added_on             : Timestamp
    last_updated         : Timestamp
    last_full_refresh    : int
    last_refresh_version : str
    last_played          : Timestamp
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
