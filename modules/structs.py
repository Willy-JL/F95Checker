import multiprocessing.queues
import multiprocessing
import datetime as dt
import dataclasses
import functools
import aiofiles
import asyncio
import weakref
import pathlib
import hashlib
import typing
import queue
import json
import time
import os

from modules.tags import Tag
from modules.intenumhack import IntEnumHack

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


Os = IntEnumHack("Os", [
    ("Windows", 1),
    ("Linux",   2),
    ("MacOS",   3),
])


DisplayMode = IntEnumHack("DisplayMode", [
    ("list",   (1, {"icon": "view_agenda_outline"})),
    ("grid",   (2, {"icon": "view_grid_outline"})),
    ("kanban", (3, {"icon": "view_week_outline"})),
])


Status = IntEnumHack("Status", [
    ("Normal",    (1, {"color" : (0.95, 0.95, 0.95), "icon": "lightning_bolt_circle"})),
    ("Completed", (2, {"color" : (0.00, 0.87, 0.00), "icon": "checkbox_marked_circle"})),
    ("OnHold",    (3, {"color" : (0.00, 0.50, 0.95), "icon": "pause_circle"})),
    ("Abandoned", (4, {"color" : (0.87, 0.20, 0.20), "icon": "close_circle"})),
    ("Unchecked", (5, {"color" : (0.50, 0.50, 0.50), "icon": "alert_circle"})),
    ("Custom",    (6, {"color" : (0.95, 0.50, 0.00), "icon": "dots_horizontal_circle"})),
])


TagHighlight = IntEnumHack("TagHighlight", [
    ("Positive", (1, {"color": (0.0, 0.6, 0.0, 1.0)})),
    ("Negative", (2, {"color": (0.6, 0.0, 0.0, 1.0)})),
    ("Critical", (3, {"color": (0.0, 0.0, 0.0, 1.0)})),
])


ExeState = IntEnumHack("ExeState", [
    ("Invalid",  1),
    ("Selected", 2),
    ("Unset",    3),
])


MsgBox = IntEnumHack("MsgBox", [
    ("info",  (1, {"color": (0.10, 0.69, 0.95), "icon": "information"})),
    ("warn",  (2, {"color": (0.95, 0.69, 0.10), "icon": "alert_rhombus"})),
    ("error", (3, {"color": (0.95, 0.22, 0.22), "icon": "alert_octagon"})),
])


FilterMode = IntEnumHack("FilterMode", [
    ("Choose",    1),
    ("Archived",  2),
    ("Custom",    13),
    ("Exe State", 3),
    ("Finished",  6),
    ("Installed", 4),
    ("Label",     5),
    ("Rating",    7),
    ("Score",     8),
    ("Status",    9),
    ("Tag",       10),
    ("Type",      11),
    ("Updated",   12),
])


Category = IntEnumHack("Category", [
    ("Games", 1),
    ("Media", 2),
    ("Misc",  3),
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
        for self in cls.instances:
            if self.id == id:
                return self

    @classmethod
    def remove(cls, self):
        while self in cls.instances:
            cls.instances.remove(self)


@dataclasses.dataclass
class Tab:
    id: int
    name: str
    icon: str
    color: tuple[float] | None
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
        for self in cls.instances:
            if self.id == id:
                return self

    @classmethod
    def remove(cls, self):
        while self in cls.instances:
            cls.instances.remove(self)

    @classmethod
    @property
    def base_icon(cls):
        from modules import icons
        return icons.heart_box

    @classmethod
    @property
    def first_tab_label(cls):
        from modules import globals, icons
        if globals.settings.default_tab_is_new:
            return f"{icons.alert_decagram} New"
        else:
            return f"{icons.heart_box} Default"

    def __hash__(self):
        return hash(self.id)


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
    datestamp_format            : str
    default_exe_dir             : dict[Os, str]
    default_tab_is_new          : bool
    display_mode                : DisplayMode
    display_tab                 : Tab.get
    ext_background_add          : bool
    ext_highlight_tags          : bool
    ext_icon_glow               : bool
    filter_all_tabs             : bool
    fit_images                  : bool
    grid_columns                : int
    hide_empty_tabs             : bool
    highlight_tags              : bool
    ignore_semaphore_timeouts   : bool
    independent_tab_views       : bool
    interface_scaling           : float
    last_successful_refresh     : Timestamp
    manual_sort_list            : list[int]
    mark_installed_after_add    : bool
    max_retries                 : int
    quick_filters               : bool
    refresh_completed_games     : bool
    refresh_workers             : int
    render_when_unfocused       : bool
    request_timeout             : int
    rpc_enabled                 : bool
    rpdl_password               : str
    rpdl_token                  : str
    rpdl_username               : str
    scroll_amount               : float
    scroll_smooth               : bool
    scroll_smooth_speed         : float
    select_executable_after_add : bool
    show_remove_btn             : bool
    software_webview            : bool
    start_in_background         : bool
    start_refresh               : bool
    style_accent                : tuple[float]
    style_alt_bg                : tuple[float]
    style_bg                    : tuple[float]
    style_border                : tuple[float]
    style_corner_radius         : int
    style_text                  : tuple[float]
    style_text_dim              : tuple[float]
    tags_highlights             : dict[Tag, TagHighlight]
    timestamp_format            : str
    use_parser_processes        : bool
    vsync_ratio                 : int
    weighted_score              : bool
    zoom_area                   : int
    zoom_enabled                : bool
    zoom_times                  : float

    def __post_init__(self):
        if "" in self.default_exe_dir:
            from modules import globals
            self.default_exe_dir[globals.os] = self.default_exe_dir[""]
            del self.default_exe_dir[""]


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
    votes              : int
    rating             : int
    finished           : str
    installed          : str
    updated            : bool | None
    archived           : bool
    executables        : list[str]
    description        : str
    changelog          : str
    tags               : tuple[Tag]
    labels             : list[Label.get]
    tab                : Tab.get
    notes              : str
    image_url          : str
    downloads          : tuple[tuple[str, list[tuple[str, str]]]]
    selected           : bool = False
    image              : imagehelper.ImageHelper = None
    executables_valids : list[bool] = None
    executables_valid  : bool = None
    _did_init          : bool = False

    def __post_init__(self):
        self._did_init = True
        if self.custom is None:
            self.custom = bool(self.status is Status.Custom)
        if self.id < 0:
            self.custom = True
        if self.updated is None:
            self.updated = bool(self.installed) and self.installed != self.version
        if self.image_url == "-":
            self.image_url = "missing"
        if self.finished == "True" and self.installed != "True" and self.version != "True":
            self.finished = (self.installed or self.version)
        elif self.finished == "False" and self.installed != "False" and self.version != "False":
            self.finished = ""
        from modules import globals
        self.image = imagehelper.ImageHelper(globals.images_path, glob=f"{self.id}.*")
        self.validate_executables()

    def delete_images(self):
        from modules import globals
        for img in globals.images_path.glob(f"{self.id}.*"):
            try:
                img.unlink()
            except Exception:
                pass

    def refresh_image(self):
        self.image.glob = f"{self.id}.*"
        self.image.loaded = False
        self.image.resolve()

    async def set_image_async(self, data: bytes):
        from modules import globals, utils
        self.delete_images()
        if data:
            async with aiofiles.open(globals.images_path / f"{self.id}.{utils.image_ext(data)}", "wb") as f:
                await f.write(data)
        self.refresh_image()

    def set_image_sync(self, data: bytes):
        from modules import globals, utils
        self.delete_images()
        if data:
            (globals.images_path / f"{self.id}.{utils.image_ext(data)}").write_bytes(data)
        self.refresh_image()

    def validate_executables(self):
        from modules import globals, utils
        if globals.settings.default_exe_dir.get(globals.os):
            changed = False
            executables_valids = []
            base = pathlib.Path(globals.settings.default_exe_dir.get(globals.os))
            for i, executable in enumerate(self.executables):
                if utils.is_uri(executable):
                    executables_valids.append(True)
                    continue
                exe = pathlib.Path(executable)
                if exe.is_absolute():
                    if base in exe.parents:
                        self.executables[i] = exe.relative_to(base).as_posix()
                        changed = True
                    executables_valids.append(exe.is_file())
                else:
                    executables_valids.append((base / exe).is_file())
            self.executables_valids = executables_valids
            if changed:
                from modules import async_thread, db
                async_thread.run(db.update_game(self, "executables"))
        else:
            self.executables_valids = [utils.is_uri(executable) or os.path.isfile(executable) for executable in self.executables]
        self.executables_valid = all(self.executables_valids)
        if globals.gui:
            globals.gui.recalculate_ids = True

    def add_executable(self, executable: str):
        from modules import globals, utils
        if not utils.is_uri(executable):
            exe = pathlib.Path(executable)
            if globals.settings.default_exe_dir.get(globals.os):
                base = pathlib.Path(globals.settings.default_exe_dir.get(globals.os))
                if base in exe.parents:
                    exe = exe.relative_to(base)
            executable = exe.as_posix()
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
            globals.gui.recalculate_ids = True

    def remove_label(self, label: Label):
        while label in self.labels:
            self.labels.remove(label)
        from modules import globals, async_thread, db
        async_thread.run(db.update_game(self, "labels"))
        if globals.gui:
            globals.gui.recalculate_ids = True

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
            "votes",
            "rating",
            "finished",
            "installed",
            "updated",
            "archived",
            "executables",
            "description",
            "changelog",
            "tags",
            "labels",
            "tab",
            "notes",
            "image_url",
            "downloads"
        ]:
            if isinstance(attr := getattr(self, name), Timestamp):
                attr.update(value)
            else:
                super().__setattr__(name, value)
            from modules import globals, async_thread, db
            async_thread.run(db.update_game(self, name))
            if globals.gui:
                globals.gui.recalculate_ids = True
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
