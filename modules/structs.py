import dataclasses
import enum


class Browser(enum.Enum):
    none = 0
    chrome = 1
    firefox = 2
    brave = 3
    edge = 4
    opera = 5
    operagx = 6
    custom = 7


class Status(enum.Enum):
    none = 0
    completed = 1
    onhold = 2
    abandoned = 3


class SortMode(enum.Enum):
    manual = 0
    last_updated = 1
    time_added = 2
    alphabetical = 3
    status = 4
    last_played = 5
    rating = 6
    installed = 7
    played = 8


Tag = enum.Enum("Tag", " ".join([
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
    _: int = None
    browser_custom_arguments: str = None
    browser_custom_executable: str = None
    browser_html: bool = None
    browser_private: bool = None
    browser: Browser = None
    column_installed: bool = None
    column_last_played: bool = None
    column_last_updated: bool = None
    column_name: bool = None
    column_played: bool = None
    column_rating: bool = None
    column_status: bool = None
    column_time_added: bool = None
    column_version: bool = None
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
    status: Status = None
    url: str = None
    time_added: int = None
    last_updated: int = None
    last_checked: int = None
    last_played: int = None
    rating: int = None
    installed: str = None
    played: bool = None
    executable: str = None
    description: str = None
    changelog: str = None
    tags: list[Tag] = None
    notes: str = None
