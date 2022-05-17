import dataclasses
import datetime
import enum

from modules.remote import imagehelper


class IntEnumAuto(enum.IntEnum):
    def __new__(cls, *args):
        value = len(cls.__members__) + 1
        obj = int.__new__(cls)
        obj._value_ = value
        return obj


class Os(IntEnumAuto):
    Windows = ()
    MacOS   = ()
    Linux   = ()


Browser = IntEnumAuto("Browser", " ".join([
    "None",
    "Chrome",
    "Firefox",
    "Brave",
    "Edge",
    "Opera",
    "OperaGX",
    "Custom"
]))


class DisplayMode(IntEnumAuto):
    list = ()
    grid = ()


Engine = IntEnumAuto("Engine", " ".join([
    "ADRIFT",
    "Flash",
    "HTML",
    "Java",
    "Other",
    "QSP",
    "RAGS",
    "RPGM",
    "RenPy",
    "Tads",
    "Unity",
    "UnrealEngine",
    "WebGL",
    "WolfRPG"
]))


EngineColors = {
    Engine.ADRIFT       .value: (33  / 255, 150 / 255, 243 / 255),
    Engine.Flash        .value: (97  / 255, 97  / 255, 97  / 255),
    Engine.HTML         .value: (104 / 255, 159 / 255, 56  / 255),
    Engine.Java         .value: (82  / 255, 166 / 255, 176 / 255),
    Engine.Other        .value: (139 / 255, 195 / 255, 74  / 255),
    Engine.QSP          .value: (211 / 255, 47  / 255, 47  / 255),
    Engine.RAGS         .value: (255 / 255, 152 / 255, 0   / 255),
    Engine.RPGM         .value: (33  / 255, 150 / 255, 243 / 255),
    Engine.RenPy        .value: (176 / 255, 105 / 255, 232 / 255),
    Engine.Tads         .value: (33  / 255, 150 / 255, 243 / 255),
    Engine.Unity        .value: (254 / 255, 89  / 255, 1   / 255),
    Engine.UnrealEngine .value: (13  / 255, 71  / 255, 161 / 255),
    Engine.WebGL        .value: (254 / 255, 89  / 255, 1   / 255),
    Engine.WolfRPG      .value: (76  / 255, 175 / 255, 80  / 255)
}


class Status(IntEnumAuto):
    Normal    = ()
    Completed = ()
    OnHold    = ()
    Abandoned = ()


class Timestamp:
    def __init__(self, unix_time: int):
        self.value: int = unix_time
        if self.value == 0:
            self.display: str = "N/A"
        else:
            self.display: str = datetime.date.fromtimestamp(unix_time).strftime("%d/%m/%Y")


Tag = IntEnumAuto("Tag", " ".join([
    "2d-game",
    "2dcg",
    "3d-game",
    "3dcg",
    "adventure",
    "ahegao",
    "anal-sex",
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
    "big-ass",
    "big-tits",
    "blackmail",
    "bukkake",
    "censored",
    "character-creation",
    "cheating",
    "combat",
    "corruption",
    "cosplay",
    "creampie",
    "dating-sim",
    "dilf",
    "drugs",
    "dystopian-setting",
    "exhibitionism",
    "fantasy",
    "femaledomination",
    "female-protagonist",
    "footjob",
    "furry",
    "futa-trans",
    "futa-trans-protagonist",
    "gay",
    "graphic-violence",
    "groping",
    "group-sex",
    "handjob",
    "harem",
    "horror",
    "humiliation",
    "humor",
    "incest",
    "internal-view",
    "interracial",
    "japanese-game",
    "kinetic-novel",
    "lactation",
    "lesbian",
    "loli",
    "maledomination",
    "male-protagonist",
    "management",
    "masturbation",
    "milf",
    "mind-control",
    "mobile-game",
    "monster",
    "monster-girl",
    "multiple-endings",
    "multiple-penetration",
    "multiple-protagonist",
    "necrophilia",
    "no-sexual-content",
    "ntr",
    "oral-sex",
    "paranormal",
    "parody",
    "platformer",
    "point-click",
    "possession",
    "pov",
    "pregnancy",
    "prostitution",
    "puzzle",
    "rape",
    "real-porn",
    "religion",
    "romance",
    "rpg",
    "sandbox",
    "scat",
    "school-setting",
    "sci-fi",
    "sex-toys",
    "sexual-harassment",
    "shooter",
    "shota",
    "side-scroller",
    "simulator",
    "sissification",
    "slave",
    "sleep-sex",
    "spanking",
    "strategy",
    "stripping",
    "superpowers",
    "swinging",
    "teasing",
    "tentacles",
    "text-based",
    "titfuck",
    "trainer",
    "transformation",
    "trap",
    "turn-based-combat",
    "twins",
    "urination",
    "vaginal-sex",
    "virgin",
    "virtual-reality",
    "voiced",
    "vore",
    "voyeurism"
]))


FilterMode = IntEnumAuto("FilterMode", " ".join([
    "None",
    "Engine",
    "Status",
    "Rating",
    "Played",
    "Installed",
    "Tag"
]))

FilterMode.Engine.by = Engine.ADRIFT
FilterMode.Engine.invert = False

FilterMode.Status.by = Status.Normal
FilterMode.Status.invert = False

FilterMode.Rating.by = 0
FilterMode.Rating.invert = False

FilterMode.Played.invert = False

FilterMode.Installed.invert = False

FilterMode.Tag.by = Tag["2d-game"]
FilterMode.Tag.invert = False


class MsgBox(IntEnumAuto):
    info  = ()
    warn  = ()
    error = ()


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
