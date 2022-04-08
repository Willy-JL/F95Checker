import dataclasses
import types
import enum


class IntFlagListed(enum.IntFlag):
    def __init__(self):
        super().__init__()
        self._values_ = [self]

    def __new__(cls, *args):
        value = 2 ** len(cls.__members__)
        obj = int.__new__(cls, value)
        obj._value_ = value
        return obj

    @classmethod
    def _create_pseudo_member_(cls, value):
        pseudo_member = super()._create_pseudo_member_(value)
        pseudo_member._values_ = enum._decompose(cls, pseudo_member)[0]
        return pseudo_member

    @types.DynamicClassAttribute
    def values(self):
        return self._values_


class IntEnumAuto(enum.IntEnum):
    def __new__(cls, *args):
        value = len(cls.__members__) + 1
        obj = int.__new__(cls)
        obj._value_ = value
        return obj


class Browser(IntEnumAuto):
    none = ()
    chrome = ()
    firefox = ()
    brave = ()
    edge = ()
    opera = ()
    operagx = ()
    custom = ()


class Column(IntFlagListed):
    play_button = ()
    engine = ()
    version = ()
    developer = ()
    status = ()
    last_updated = ()
    last_played = ()
    added_on = ()
    played = ()
    installed = ()
    rating = ()
    open_page = ()


class SortMode(IntEnumAuto):
    manual = ()
    last_updated = ()
    last_played = ()
    time_added = ()
    alphabetical = ()
    rating = ()


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


class Status(IntEnumAuto):
    none = ()
    completed = ()
    onhold = ()
    abandoned = ()


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


@dataclasses.dataclass
class Settings:
    browser_custom_arguments: str = None
    browser_custom_executable: str = None
    browser_html: bool = None
    browser_private: bool = None
    browser: Browser = None
    columns: Column = None
    refresh_completed_games: bool = None
    refresh_workers: int = None
    request_timeout: int = None
    select_executable_after_add: bool = None
    sort_mode: SortMode = None
    start_in_tray: bool = None
    start_refresh: bool = None
    start_with_system: bool = None
    style_accent: str = None
    style_alt_bg: str = None
    style_bg: str = None
    style_btn_border: str = None
    style_btn_disabled: str = None
    style_btn_hover: str = None
    style_corner_radius: int = None
    style_scaling: float = None
    tray_refresh_interval: int = None
    update_keep_executable: bool = None
    update_keep_image: bool = None


@dataclasses.dataclass
class Game:
    id: int = None
    name: str = None
    version: str = None
    developer: str = None
    engine: Engine = None
    status: Status = None
    url: str = None
    time_added: int = None
    last_updated: int = None
    last_full_refresh: int = None
    last_played: int = None
    rating: int = None
    installed: str = None
    played: bool = None
    executable: str = None
    description: str = None
    changelog: str = None
    tags: list[Tag] = None
    notes: str = None
