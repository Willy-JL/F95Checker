import asyncio
import configparser
import contextlib
import enum
import json
import pathlib
import re
import shutil
import sqlite3
import time
import types
import typing

import aiosqlite

from common.structs import (
    Browser,
    DefaultStyle,
    DisplayMode,
    Game,
    Label,
    MsgBox,
    ProxyType,
    SearchResult,
    Settings,
    Status,
    Tab,
    ThreadMatch,
    TimelineEvent,
    TimelineEventType,
    Timestamp,
    Type,
)
from common import parser
from external import (
    async_thread,
    error,
)
from modules import (
    api,
    colors,
    globals,
    msgbox,
    utils,
)

connection: aiosqlite.Connection = None


@contextlib.contextmanager
def setup():
    async_thread.wait(connect())
    async_thread.wait(load())
    loop = async_thread.run(save_loop())
    try:
        yield
    finally:
        loop.cancel()
        async_thread.wait(close())


async def get_table_info(table_name: str):
    cursor = await connection.execute(f"""
        PRAGMA table_info({table_name})
    """)
    has_columns = [tuple(row) for row in await cursor.fetchall()]  # (index, name, type, can_be_null, default, idk)
    has_column_names = [column[1] for column in has_columns]
    has_column_defs = [(column[2], column[4]) for column in has_columns]  # (type, default)
    return has_column_names, has_column_defs


async def create_table(table_name: str, columns: dict[str, str], renames: list[tuple[str, str]] = []):
    await connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {', '.join([f'{column_name} {column_def}' for column_name, column_def in columns.items()])}
        )
    """)
    has_column_names, has_column_defs = await get_table_info(table_name)

    # Rename columns
    for rename_old, rename_new in renames:
        if rename_old in has_column_names and rename_new not in has_column_names:
            await connection.execute(f"""
                ALTER TABLE {table_name}
                RENAME COLUMN {rename_old} TO {rename_new}
            """)
            has_column_names[has_column_names.index(rename_old)] = rename_new

    # Add columns
    added = False
    for column_name, column_def in columns.items():
        if column_name not in has_column_names:
            await connection.execute(f"""
                ALTER TABLE {table_name}
                ADD COLUMN {column_name} {column_def}
            """)
            added = True
    if added:
        has_column_names, has_column_defs = await get_table_info(table_name)

    # Remove columns
    removed = False
    for has_column_name in has_column_names:
        if has_column_name not in columns:
            await connection.execute(f"""
                ALTER TABLE {table_name}
                DROP COLUMN {has_column_name}
            """)
            removed = True
    if removed:
        has_column_names, has_column_defs = await get_table_info(table_name)

    # Update column defs
    recreated = False
    for column_name, column_def in columns.items():
        has_column_def = has_column_defs[has_column_names.index(column_name)]  # (type, default)
        type_changed = not column_def.strip().lower().startswith(has_column_def[0].lower())
        default_changed = " default " in column_def.lower() and not re.search(r"[Dd][Ee][Ff][Aa][Uu][Ll][Tt]\s+?" + re.escape(str(has_column_def[1])), column_def)
        if (type_changed or default_changed) and not recreated:
            # Recreate table and transfer values
            temp_column_list = ", ".join(columns.keys())
            temp_table_name = f"{table_name}_temp_{utils.rand_num_str()}"
            await connection.execute(f"""
                ALTER TABLE {table_name}
                RENAME TO {temp_table_name}
            """)
            await create_table(table_name, columns, renames)
            await connection.execute(f"""
                INSERT INTO {table_name}
                ({temp_column_list})
                SELECT
                {temp_column_list}
                FROM {temp_table_name}
            """)
            await connection.execute(f"""
                DROP TABLE {temp_table_name}
            """)
            recreated = True
        if type_changed and has_column_def[0].lower() == "integer" and column_def.strip().lower().startswith("text"):
            # Check if this is boolean to string
            cursor = await connection.execute(f"""
                SELECT {column_name}
                FROM {table_name}
            """)
            if all(value[0] in ("0", "1") for value in await cursor.fetchall()):
                # All 0 or 1, convert to boolean names
                await connection.execute(f"""
                    UPDATE {table_name}
                    SET
                        {column_name} = REPLACE({column_name}, '0', 'False')
                """)
                await connection.execute(f"""
                    UPDATE {table_name}
                    SET
                        {column_name} = REPLACE({column_name}, '1', 'True')
                """)


async def connect():
    global connection

    migrate = not (globals.data_path / "db.sqlite3").is_file()
    connection = await aiosqlite.connect(globals.data_path / "db.sqlite3")
    connection.row_factory = aiosqlite.Row  # Return sqlite3.Row instead of tuple

    await create_table(
        table_name="settings",
        columns={
            "_":                           f'INTEGER PRIMARY KEY CHECK (_=0)',
            "background_on_close":         f'INTEGER DEFAULT {int(False)}',
            "bg_notifs_interval":          f'INTEGER DEFAULT 15',
            "bg_refresh_interval":         f'INTEGER DEFAULT 30',
            "browser_custom_arguments":    f'TEXT    DEFAULT ""',
            "browser_custom_executable":   f'TEXT    DEFAULT ""',
            "browser_html":                f'INTEGER DEFAULT {int(False)}',
            "browser_private":             f'INTEGER DEFAULT {int(False)}',
            "browser":                     f'INTEGER DEFAULT {Browser.get(0).hash}',
            "cell_image_ratio":            f'REAL    DEFAULT 3.0',
            "check_notifs":                f'INTEGER DEFAULT {int(False)}',
            "compact_timeline":            f'INTEGER DEFAULT {int(False)}',
            "confirm_on_remove":           f'INTEGER DEFAULT {int(True)}',
            "copy_urls_as_bbcode":         f'INTEGER DEFAULT {int(False)}',
            "datestamp_format":            f'TEXT    DEFAULT "%b %d, %Y"',
            "default_exe_dir":             f'TEXT    DEFAULT "{{}}"',
            "default_tab_is_new":          f'INTEGER DEFAULT {int(False)}',
            "display_mode":                f'INTEGER DEFAULT {DisplayMode.list}',
            "display_tab":                 f'INTEGER DEFAULT NULL',
            "downloads_dir":               f'TEXT    DEFAULT "{{}}"',
            "ext_background_add":          f'INTEGER DEFAULT {int(True)}',
            "ext_highlight_tags":          f'INTEGER DEFAULT {int(True)}',
            "ext_icon_glow":               f'INTEGER DEFAULT {int(True)}',
            "filter_all_tabs":             f'INTEGER DEFAULT {int(False)}',
            "fit_images":                  f'INTEGER DEFAULT {int(False)}',
            "grid_columns":                f'INTEGER DEFAULT 3',
            "hidden_timeline_events":      f'TEXT    DEFAULT "[]"',
            "hide_empty_tabs":             f'INTEGER DEFAULT {int(False)}',
            "highlight_tags":              f'INTEGER DEFAULT {int(True)}',
            "ignore_semaphore_timeouts":   f'INTEGER DEFAULT {int(False)}',
            "independent_tab_views":       f'INTEGER DEFAULT {int(False)}',
            "insecure_ssl":                f'INTEGER DEFAULT {int(False)}',
            "interface_scaling":           f'REAL    DEFAULT 1.0',
            "last_successful_refresh":     f'INTEGER DEFAULT 0',
            "manual_sort_list":            f'TEXT    DEFAULT "[]"',
            "mark_installed_after_add":    f'INTEGER DEFAULT {int(False)}',
            "max_connections":             f'INTEGER DEFAULT 10',
            "max_retries":                 f'INTEGER DEFAULT 2',
            "proxy_type":                  f'INTEGER DEFAULT {ProxyType.Disabled}',
            "proxy_host":                  f'TEXT    DEFAULT ""',
            "proxy_port":                  f'INTEGER DEFAULT 8080',
            "proxy_username":              f'TEXT    DEFAULT ""',
            "proxy_password":              f'TEXT    DEFAULT ""',
            "quick_filters":               f'INTEGER DEFAULT {int(True)}',
            "refresh_archived_games":      f'INTEGER DEFAULT {int(True)}',
            "refresh_completed_games":     f'INTEGER DEFAULT {int(True)}',
            "render_when_unfocused":       f'INTEGER DEFAULT {int(True)}',
            "request_timeout":             f'INTEGER DEFAULT 30',
            "rpc_enabled":                 f'INTEGER DEFAULT {int(True)}',
            "rpdl_password":               f'TEXT    DEFAULT ""',
            "rpdl_token":                  f'TEXT    DEFAULT ""',
            "rpdl_username":               f'TEXT    DEFAULT ""',
            "scroll_amount":               f'REAL    DEFAULT 1.0',
            "scroll_smooth":               f'INTEGER DEFAULT {int(True)}',
            "scroll_smooth_speed":         f'REAL    DEFAULT 8.0',
            "select_executable_after_add": f'INTEGER DEFAULT {int(False)}',
            "show_remove_btn":             f'INTEGER DEFAULT {int(False)}',
            "software_webview":            f'INTEGER DEFAULT {int(False)}',
            "start_in_background":         f'INTEGER DEFAULT {int(False)}',
            "start_refresh":               f'INTEGER DEFAULT {int(False)}',
            "style_accent":                f'TEXT    DEFAULT "{DefaultStyle.accent}"',
            "style_alt_bg":                f'TEXT    DEFAULT "{DefaultStyle.alt_bg}"',
            "style_bg":                    f'TEXT    DEFAULT "{DefaultStyle.bg}"',
            "style_border":                f'TEXT    DEFAULT "{DefaultStyle.border}"',
            "style_corner_radius":         f'INTEGER DEFAULT {DefaultStyle.corner_radius}',
            "style_text":                  f'TEXT    DEFAULT "{DefaultStyle.text}"',
            "style_text_dim":              f'TEXT    DEFAULT "{DefaultStyle.text_dim}"',
            "tags_highlights":             f'TEXT    DEFAULT "{{}}"',
            "timestamp_format":            f'TEXT    DEFAULT "%d/%m/%Y %H:%M"',
            "vsync_ratio":                 f'INTEGER DEFAULT 1',
            "weighted_score":              f'INTEGER DEFAULT {int(False)}',
            "zoom_area":                   f'INTEGER DEFAULT 50',
            "zoom_enabled":                f'INTEGER DEFAULT {int(True)}',
            "zoom_times":                  f'REAL    DEFAULT 4.0',
        },
        renames=[
            ("grid_image_ratio",      "cell_image_ratio"),
            ("minimize_on_close",     "background_on_close"),
            ("start_in_tray",         "start_in_background"),
            ("tray_notifs_interval",  "bg_notifs_interval"),
            ("tray_refresh_interval", "bg_refresh_interval"),
            ("refresh_workers",       "max_connections"),
        ]
    )
    await connection.execute("""
        INSERT INTO settings
        (_)
        VALUES
        (0)
        ON CONFLICT DO NOTHING
    """)

    await create_table(
        table_name="games",
        columns={
            "id":                          f'INTEGER PRIMARY KEY',
            "custom":                      f'INTEGER DEFAULT NULL',
            "name":                        f'TEXT    DEFAULT ""',
            "version":                     f'TEXT    DEFAULT "Unchecked"',
            "developer":                   f'TEXT    DEFAULT ""',
            "type":                        f'INTEGER DEFAULT {Type.Unchecked}',
            "status":                      f'INTEGER DEFAULT {Status.Unchecked}',
            "url":                         f'TEXT    DEFAULT ""',
            "added_on":                    f'INTEGER DEFAULT 0',
            "last_updated":                f'INTEGER DEFAULT 0',
            "last_full_check":             f'INTEGER DEFAULT 0',
            "last_check_version":          f'TEXT    DEFAULT ""',
            "last_launched":               f'INTEGER DEFAULT 0',
            "score":                       f'REAL    DEFAULT 0',
            "votes":                       f'INTEGER DEFAULT 0',
            "rating":                      f'INTEGER DEFAULT 0',
            "finished":                    f'TEXT    DEFAULT ""',
            "installed":                   f'TEXT    DEFAULT ""',
            "updated":                     f'INTEGER DEFAULT NULL',
            "archived":                    f'INTEGER DEFAULT {int(False)}',
            "executables":                 f'TEXT    DEFAULT "[]"',
            "description":                 f'TEXT    DEFAULT ""',
            "changelog":                   f'TEXT    DEFAULT ""',
            "tags":                        f'TEXT    DEFAULT "[]"',
            "unknown_tags":                f'TEXT    DEFAULT "[]"',
            "unknown_tags_flag":           f'INTEGER DEFAULT {int(False)}',
            "labels":                      f'TEXT    DEFAULT "[]"',
            "tab":                         f'INTEGER DEFAULT NULL',
            "notes":                       f'TEXT    DEFAULT ""',
            "image_url":                   f'TEXT    DEFAULT ""',
            "previews_urls":               f'TEXT    DEFAULT "[]"',
            "downloads":                   f'TEXT    DEFAULT "[]"',
        },
        renames=[
            ("executable",           "executables"),
            ("last_full_refresh",    "last_full_check"),
            ("last_refresh_version", "last_check_version"),
            ("played",               "finished"),
            ("last_played",          "last_launched"),
        ]
    )

    await create_table(
        table_name="cookies",
        columns={
            "key":                         f'TEXT    PRIMARY KEY',
            "value":                       f'TEXT    DEFAULT ""',
        }
    )
    await create_table(
        table_name="labels",
        columns={
            "id":                          f'INTEGER PRIMARY KEY AUTOINCREMENT',
            "name":                        f'TEXT    DEFAULT ""',
            "color":                       f'TEXT    DEFAULT "#696969"',
        }
    )
    await create_table(
        table_name="tabs",
        columns={
            "id":                          f'INTEGER PRIMARY KEY AUTOINCREMENT',
            "name":                        f'TEXT    DEFAULT ""',
            "icon":                        f'TEXT    DEFAULT "{Tab.base_icon()}"',
            "color":                       f'TEXT    DEFAULT NULL',
        }
    )
    await create_table(
        table_name="timeline_events",
        columns={
            "game_id":                     f'INTEGER DEFAULT NULL',
            "timestamp":                   f'INTEGER DEFAULT 0',
            "arguments":                   f'TEXT    DEFAULT "[]"',
            "type":                        f'INTEGER DEFAULT 1',
        }
    )

    if migrate and ((path := globals.data_path / "f95checker.json").is_file() or (path := globals.data_path / "config.ini").is_file()):
        await migrate_legacy(path)


async def save():
    await connection.commit()


async def save_loop():
    while True:
        await asyncio.sleep(30)
        await save()


async def close():
    await save()
    await connection.close()


def sql_to_py(value: str | int | float, data_type: typing.Type):
    args = getattr(data_type, "__args__", None)
    match getattr(data_type, "__name__", None):
        case "dict":
            try:
                value = data_type(json.loads(value))
                if args:
                    key_type = args[0]
                    value_type = args[1]
                    value = data_type((key_type(int(k) if (type(k) is str and k.isdigit()) else k), value_type(v)) for k, v in value.items())
            except json.JSONDecodeError:
                value = data_type([("", value)]) if value else data_type()
        case "list" | "tuple":
            if isinstance(value, str) and args and args[0] is float and re.fullmatch(r'^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})', value):
                value = colors.hex_to_rgba_0_1(value)
            else:
                try:
                    value = data_type(json.loads(value))
                except json.JSONDecodeError:
                    value = data_type([value]) if value else data_type()
                if args:
                    content_type = args[0]
                    value = data_type(x for x in (content_type(x) for x in value) if x is not None)
        case _:
            if isinstance(data_type, types.UnionType):
                if (
                    isinstance(value, str) and args and
                    getattr(args[0], "__name__", None) == "tuple" and
                    getattr(args[0], "__args__", [None])[0] is float and
                    re.fullmatch(r'^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})', value)
                ):
                    value = colors.hex_to_rgba_0_1(value)
                elif args and not (args[-1] is types.NoneType and value is None):
                    value = args[0](value)
                else:
                    value = None
            else:
                value = data_type(value)
    return value


def row_to_cls(row: sqlite3.Row, cls: typing.Type):
    types = cls.__annotations__
    data = {key: sql_to_py(value, types[key]) for key, value in dict(row).items() if key in types}
    return cls(**data)


async def load_games(id: int = None):
    query = """
        SELECT *
        FROM games
    """
    if id is not None:
        query += f"""
            WHERE id={id}
        """
    cursor = await connection.execute(query)
    for game in await cursor.fetchall():
        globals.games[game["id"]] = row_to_cls(game, Game)


async def load():
    cursor = await connection.execute("""
        SELECT *
        FROM labels
    """)
    for label in await cursor.fetchall():
        Label.add(row_to_cls(label, Label))

    cursor = await connection.execute("""
        SELECT *
        FROM tabs
    """)
    for tab in await cursor.fetchall():
        Tab.add(row_to_cls(tab, Tab))

    # Settings need Tabs to be loaded
    cursor = await connection.execute("""
        SELECT *
        FROM settings
    """)
    globals.settings = row_to_cls(await cursor.fetchone(), Settings)

    # Games need Tabs and Labels to be loaded
    globals.games = {}
    await load_games()

    # TimelineEvents need Games to be loaded
    cursor = await connection.execute("""
        SELECT *
        FROM timeline_events
        ORDER BY timestamp DESC
    """)
    unknown_game_ids = set()
    for event in await cursor.fetchall():
        event = row_to_cls(event, TimelineEvent)
        if event.game_id not in globals.games:
            unknown_game_ids.add(event.game_id)
            continue
        globals.games[event.game_id].timeline_events.append(event)
    for unknown_game_id in unknown_game_ids:
        await delete_timeline_events(unknown_game_id)

    cursor = await connection.execute("""
        SELECT *
        FROM cookies
    """)
    globals.cookies = {cookie["key"]: cookie["value"] for cookie in await cursor.fetchall()}


def py_to_sql(value: enum.Enum | Timestamp | bool | list | tuple | typing.Any):
    if hasattr(value, "value"):
        value = value.value
    elif hasattr(value, "hash"):
        value = value.hash
    elif hasattr(value, "id"):
        value = value.id
    elif type(value) is bool:
        value = int(value)
    elif isinstance(value, dict):
        value = value.copy()
        value = {getattr(k, "value", getattr(k, "id", k)): getattr(v, "value", getattr(v, "id", v)) for k, v in value.items()}
        value = json.dumps(value)
    elif isinstance(value, list):
        value = value.copy()
        value = [getattr(item, "value", getattr(item, "id", item)) for item in value]
        value = json.dumps(value)
    elif isinstance(value, tuple):
        if 3 <= len(value) <= 4 and all(type(item) in (float, int) for item in value):
            value = colors.rgba_0_1_to_hex(value)
        else:
            value = [getattr(item, "value", getattr(item, "id", item)) for item in value]
            value = json.dumps(value)
    return value


async def update_game_id(game: Game, new_id):
    await connection.execute(f"""
        UPDATE games
        SET
            id={new_id}
        WHERE id={game.id}
    """)
    globals.games[new_id] = game
    if game.id != new_id:
        del globals.games[game.id]

    await connection.execute(f"""
        UPDATE timeline_events
        SET
            game_id={new_id}
        WHERE game_id={game.id}
    """)
    for event in game.timeline_events:
        event.game_id = new_id

    for i, img in enumerate(sorted(list(globals.images_path.glob(f"{game.id}.*")), key=lambda path: path.suffix != ".gif")):
        if i == 0:
            shutil.move(img, globals.images_path / f"{new_id}{img.suffix}")
        else:
            try:
                img.unlink()
            except Exception:
                pass
    game.id = new_id
    game.refresh_image()


async def update_game(game: Game, *keys: list[str]):
    values = []

    for key in keys:
        value = py_to_sql(getattr(game, key))
        values.append(value)

    await connection.execute(f"""
        UPDATE games
        SET
            {", ".join(f"{key} = ?" for key in keys)}
        WHERE id={game.id}
    """, tuple(values))


async def update_settings(*keys: list[str]):
    values = []

    for key in keys:
        value = py_to_sql(getattr(globals.settings, key))
        values.append(value)

    await connection.execute(f"""
        UPDATE settings
        SET
            {", ".join(f"{key} = ?" for key in keys)}
        WHERE _=0
    """, tuple(values))


async def delete_game(id: int):
    await connection.execute(f"""
        DELETE FROM games
        WHERE id={id}
    """)


async def create_game(thread: ThreadMatch | SearchResult = None, custom=False):
    if custom:
        game_id = utils.custom_id()
        await connection.execute(f"""
            INSERT INTO games
            (id, custom, name, added_on, last_updated)
            VALUES
            (?,  ?,      ?,    ?,        ?           )
        """, (game_id, True, f"Custom game ({game_id})", int(time.time()), parser.datestamp(time.time())))
        return game_id
    else:
        await connection.execute(f"""
            INSERT INTO games
            (id, custom, name, url, added_on)
            VALUES
            (?,  ?,      ?,    ?,   ?       )
        """, (thread.id, False, thread.title or f"Unknown ({thread.id})", f"{api.f95_threads_page}{thread.id}", int(time.time())))
        return thread.id


async def update_label(label: Label, *keys: list[str]):
    values = []

    for key in keys:
        value = py_to_sql(getattr(label, key))
        values.append(value)

    await connection.execute(f"""
        UPDATE labels
        SET
            {", ".join(f"{key} = ?" for key in keys)}
        WHERE id={label.id}
    """, tuple(values))


async def delete_label(label: Label):
    await connection.execute(f"""
        DELETE FROM labels
        WHERE id={label.id}
    """)
    for game in globals.games.values():
        if label in game.labels:
            game.remove_label(label)
    for flt in list(globals.gui.filters):
        if flt.match is label:
            globals.gui.filters.remove(flt)
    Label.remove(label)


async def create_label():
    cursor = await connection.execute(f"""
        INSERT INTO labels
        DEFAULT VALUES
    """)
    cursor = await connection.execute(f"""
        SELECT *
        FROM labels
        WHERE id={cursor.lastrowid}
    """)
    label = row_to_cls(await cursor.fetchone(), Label)
    Label.add(label)
    return label


async def update_tab(tab: Tab, *keys: list[str]):
    values = []

    for key in keys:
        value = py_to_sql(getattr(tab, key))
        values.append(value)

    await connection.execute(f"""
        UPDATE tabs
        SET
            {", ".join(f"{key} = ?" for key in keys)}
        WHERE id={tab.id}
    """, tuple(values))


async def delete_tab(tab: Tab):
    await connection.execute(f"""
        DELETE FROM tabs
        WHERE id={tab.id}
    """)
    for game in globals.games.values():
        if game.tab is tab:
            game.tab = None
    if globals.settings.display_tab is tab:
        globals.settings.display_tab = None
        await update_settings("display_tab")
    Tab.remove(tab)
    if globals.gui:
        globals.gui.recalculate_ids = True


async def create_tab():
    cursor = await connection.execute(f"""
        INSERT INTO tabs
        DEFAULT VALUES
    """)
    cursor = await connection.execute(f"""
        SELECT *
        FROM tabs
        WHERE id={cursor.lastrowid}
    """)
    tab = row_to_cls(await cursor.fetchone(), Tab)
    Tab.add(tab)
    return tab


async def create_timeline_event(game_id: int, timestamp: Timestamp, arguments: list[str], type: TimelineEventType):
    await connection.execute(f"""
        INSERT INTO timeline_events
        (game_id, timestamp, arguments, type)
        VALUES
        (?, ?, ?, ?)
    """, [py_to_sql(value) for value in (game_id, timestamp, arguments, type)])
    event = TimelineEvent(game_id, timestamp, arguments, type)
    globals.games[game_id].timeline_events.insert(0, event)


async def delete_timeline_events(game_id: int):
    await connection.execute(f"""
        DELETE FROM timeline_events
        WHERE game_id={game_id}
    """)


async def update_cookies(new_cookies: dict[str, str]):
    await connection.execute(f"""
        DELETE FROM cookies
    """)
    for key, value in new_cookies.items():
        await connection.execute("""
            INSERT INTO cookies
            (key, value)
            VALUES
            (?, ?)
            ON CONFLICT DO NOTHING
        """, (key, value))
    globals.cookies = new_cookies


def legacy_json_to_dict(path: pathlib.Path):  # Pre v9.0
    config = json.loads(path.read_bytes())
    if type(config.get("game_list")) is list and type(config.get("game_data")) is dict:  # Pre v8.0
        config.setdefault("games", {})
        for game in config["game_list"]:
            if not game:
                continue
            link = config["game_data"][game]["link"]
            if not link:
                continue
            if link.startswith("/"):
                link = api.f95_host + link
            match = utils.extract_thread_matches(link)
            if not match:
                continue
            id = str(match[0].id)
            config["games"].setdefault(id, {})
            config["games"][id].setdefault("name", game)
            config["games"][id].setdefault("link", link)
            for key, value in config["game_data"][game]:
                config["games"][id].setdefault(key, value)
    return config


def legacy_ini_to_dict(path: pathlib.Path):  # Pre v7.0
    old_config = configparser.RawConfigParser()
    old_config.read(path)
    config = {}
    config["options"] = {}
    config["options"]["browser"]            = old_config.get(       'options', 'browser',       fallback=''    )
    config["options"]["private_browser"]    = old_config.getboolean('options', 'private',       fallback=False )
    config["options"]["open_html"]          = old_config.getboolean('options', 'open_html',     fallback=False )
    config["options"]["start_refresh"]      = old_config.getboolean('options', 'start_refresh', fallback=False )
    config["options"]["bg_mode_delay_mins"] = old_config.getint(    'options', 'delay',         fallback=15    )
    config["style"] = {}
    config["style"]["accent"] = old_config.get('options', 'accent', fallback='#da1e2e')
    config["games"] = {}
    for game in old_config.get('games', 'game_list').split('/'):
        if not game:
            continue
        link = old_config.get(game, 'link', fallback='')
        if not link:
            continue
        if link.startswith("/"):
            link = api.f95_host + link
        match = utils.extract_thread_matches(link)
        if not match:
            continue
        id = str(match[0].id)
        config["games"].setdefault(id, {})
        config["games"][id].setdefault("name",         game                                                       )
        config["games"][id].setdefault("version",      old_config.get       (game, 'version',      fallback=''   ))
        config["games"][id].setdefault("installed",    old_config.getboolean(game, 'installed',    fallback=False))
        config["games"][id].setdefault("link",         link                                                       )
        config["games"][id].setdefault("add_time",     old_config.getfloat  (game, 'add_time',     fallback=0.0  ))
        config["games"][id].setdefault("updated_time", 0.0)
        config["games"][id].setdefault("changelog",    old_config.get       (game, 'changelog',    fallback=''   ))
    return config


async def migrate_legacy(config: str | pathlib.Path | dict):
    try:
        if isinstance(config, str):
            config = pathlib.Path(config)
        if isinstance(config, pathlib.Path):
            path = config
            if path.suffix == ".json":
                config = legacy_json_to_dict(path)
            elif path.suffix == ".ini":
                config = legacy_ini_to_dict(path)
            else:
                utils.push_popup(
                    msgbox.msgbox, "Unsupported format",
                    "Could not migrate this file:\n"
                    f"{str(path)}\n"
                    "\n"
                    "The only supported formats are .json and .ini.",
                    MsgBox.warn
                )
                return
        keys = []
        values = []

        if (options := config.get("options")) is not None:

            keys.append("browser")
            match options.get("browser"):
                case "chrome":
                    value = Browser.make_hash("Google Chrome")
                case "firefox":
                    value = Browser.make_hash("Mozilla Firefox")
                case "brave":
                    value = Browser.make_hash("Brave")
                case "edge":
                    value = Browser.make_hash("Microsoft Edge")
                case "opera":
                    value = Browser.make_hash("Opera Stable")
                case "operagx":
                    value = Browser.make_hash("Opera GX Stable")
                case _:
                    value = 0
            values.append(value)

            if (private_browser := options.get("private_browser")) is not None:
                keys.append("browser_private")
                values.append(int(private_browser))

            if (open_html := options.get("open_html")) is not None:
                keys.append("browser_html")
                values.append(int(open_html))

            if (start_refresh := options.get("start_refresh")) is not None:
                keys.append("start_refresh")
                values.append(int(start_refresh))

            if (bg_mode_delay_mins := options.get("bg_mode_delay_mins")) is not None:
                keys.append("bg_refresh_interval")
                values.append(bg_mode_delay_mins)

            if (refresh_completed_games := options.get("refresh_completed_games")) is not None:
                keys.append("refresh_completed_games")
                values.append(int(refresh_completed_games))

        if (style := config.get("style")) is not None:

            if (accent := style.get("accent")) is not None:
                keys.append("style_accent")
                values.append(accent)

            if (alt := style.get("alt")) is not None:
                keys.append("style_alt_bg")
                values.append(alt)

            if (back := style.get("back")) is not None:
                keys.append("style_bg")
                values.append(back)

            if (border := style.get("border")) is not None:
                keys.append("style_border")
                values.append(border)

            if (radius := style.get("radius")) is not None:
                keys.append("style_corner_radius")
                values.append(int(radius))

        if keys and values:
            await connection.execute(f"""
                UPDATE settings
                SET
                    {", ".join(f"{key} = ?" for key in keys)}
                WHERE _=0
            """, tuple(values))

        if (games := config.get("games")) is not None:
            for game in games.values():
                match = utils.extract_thread_matches(game["link"])
                if not match:
                    continue
                id = match[0].id
                keys = ["id"]
                values = [id]

                keys.append("name")
                values.append(game.get("name") or f"Unknown ({id})")

                if version := game.get("version"):
                    keys.append("version")
                    values.append(version)

                keys.append("status")
                values.append(Status.Unchecked.value)

                if (installed := game.get("installed")) is not None:
                    keys.append("installed")
                    if installed:
                        values.append(version)
                    else:
                        values.append("")

                if (played := game.get("played")) is not None:
                    keys.append("finished")
                    if played:
                        values.append(version)
                    else:
                        values.append("")

                if (exe_path := game.get("exe_path")) is not None:
                    keys.append("executables")
                    values.append(json.dumps([exe_path]))

                if (link := game.get("link")) is not None:
                    keys.append("url")
                    values.append(utils.clean_thread_url(link))

                if (add_time := game.get("add_time")) is not None:
                    keys.append("added_on")
                    values.append(int(add_time))

                if (updated_time := game.get("updated_time")) is not None:
                    keys.append("last_updated")
                    values.append(int(updated_time))

                if (changelog := game.get("changelog")) is not None:
                    keys.append("changelog")
                    values.append(changelog)

                if (notes := game.get("notes")) is not None:
                    keys.append("notes")
                    values.append(notes)

                try:
                    await connection.execute(f"""
                        INSERT INTO games
                        ({", ".join(keys)})
                        VALUES
                        ({", ".join("?" * len(values))})
                    """, tuple(values))
                except sqlite3.IntegrityError:
                    pass  # Duplicates

        if (advanced := config.get("advanced")) is not None:

            if (cookies := advanced.get("cookies")) is not None:
                await update_cookies(cookies)

        await save()
    except Exception:
        utils.push_popup(
            msgbox.msgbox, "Config migration error",
            "Something went wrong transferring data from the previous version:\n"
            f"{error.text()}",
            MsgBox.error,
            more=error.traceback()
        )
