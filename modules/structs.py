import dataclasses
import datetime
import enum

from modules.remote import imagehelper


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
    _None    = 0
    Chrome   = 1
    Firefox  = 2
    Brave    = 3
    Edge     = 4
    Opera    = 5
    Opera_GX = 6
    Custom   = 7

Browser.Chrome  .private = "-incognito"
Browser.Firefox .private = "-private-window"
Browser.Brave   .private = "-incognito"
Browser.Edge    .private = "-inprivate"
Browser.Opera   .private = "-private"
Browser.Opera_GX.private = "-private"


class DisplayMode(IntEnum):
    list = 1
    grid = 2


class Engine(EnumNameHack, IntEnum):
    ADRIFT        = 1
    Flash         = 2
    HTML          = 3
    Java          = 4
    Other         = 5
    QSP           = 6
    RAGS          = 7
    RPGM          = 8
    RenPy         = 9
    Tads          = 10
    Unity         = 11
    Unreal_Engine = 12
    WebGL         = 13
    WolfRPG       = 14

Engine.ADRIFT       .color = (33  / 255, 150 / 255, 243 / 255)
Engine.Flash        .color = (97  / 255, 97  / 255, 97  / 255)
Engine.HTML         .color = (104 / 255, 159 / 255, 56  / 255)
Engine.Java         .color = (82  / 255, 166 / 255, 176 / 255)
Engine.Other        .color = (139 / 255, 195 / 255, 74  / 255)
Engine.QSP          .color = (211 / 255, 47  / 255, 47  / 255)
Engine.RAGS         .color = (255 / 255, 152 / 255, 0   / 255)
Engine.RPGM         .color = (33  / 255, 150 / 255, 243 / 255)
Engine.RenPy        .color = (176 / 255, 105 / 255, 232 / 255)
Engine.Tads         .color = (33  / 255, 150 / 255, 243 / 255)
Engine.Unity        .color = (254 / 255, 89  / 255, 1   / 255)
Engine.Unreal_Engine.color = (13  / 255, 71  / 255, 161 / 255)
Engine.WebGL        .color = (254 / 255, 89  / 255, 1   / 255)
Engine.WolfRPG      .color = (76  / 255, 175 / 255, 80  / 255)


class Status(IntEnum):
    Normal    = 0
    Completed = 1
    OnHold    = 2
    Abandoned = 3


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
    Engine    = ()
    Status    = ()
    Rating    = ()
    Played    = ()
    Installed = ()
    Tag       = ()

FilterMode.Engine.by = Engine.ADRIFT
FilterMode.Engine.invert = False

FilterMode.Status.by = Status.Normal
FilterMode.Status.invert = False

FilterMode.Rating.by = 0
FilterMode.Rating.invert = False

FilterMode.Played.invert = False

FilterMode.Installed.invert = False

FilterMode.Tag.by = Tag._2d__game
FilterMode.Tag.invert = False


class MsgBox(IntEnum, EnumAutoValue):
    info  = ()
    warn  = ()
    error = ()


class Timestamp:
    def __init__(self, unix_time: int):
        self.value: int = unix_time
        if self.value == 0:
            self.display: str = "N/A"
        else:
            self.display: str = datetime.date.fromtimestamp(unix_time).strftime("%d/%m/%Y")


@dataclasses.dataclass
class Settings:
    browser_custom_arguments    : str
    browser_custom_executable   : str
    browser_html                : bool
    browser_private             : bool
    browser                     : Browser
    display_mode                : DisplayMode
    fit_images                  : bool
    grid_columns                : int
    grid_image_ratio            : float
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
    start_with_system           : bool
    style_accent                : str
    style_alt_bg                : str
    style_bg                    : str
    style_btn_border            : str
    style_btn_disabled          : str
    style_btn_hover             : str
    style_corner_radius         : int
    style_scaling               : float
    tray_refresh_interval       : int
    update_keep_image           : bool
    vsync_ratio                 : int
    zoom_amount                 : int
    zoom_enabled                : bool
    zoom_region                 : bool
    zoom_size                   : int


@dataclasses.dataclass
class Game:
    id                : int
    name              : str
    version           : str
    developer         : str
    engine            : Engine
    status            : Status
    url               : str
    added_on          : Timestamp
    last_updated      : Timestamp
    last_full_refresh : int
    last_played       : Timestamp
    rating            : int
    played            : bool
    installed         : str
    executable        : str
    description       : str
    changelog         : str
    tags              : list[Tag]
    notes             : str
    image             : imagehelper.ImageHelper
