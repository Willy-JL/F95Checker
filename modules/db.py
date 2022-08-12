import configparser
import aiosqlite
import sqlite3
import asyncio
import pathlib
import typing
import enum
import json
import time
import re

from modules.structs import Browser, DefaultStyle, DisplayMode, Game, MsgBox, SearchResult, Settings, Status, ThreadMatch, Timestamp, Type
from modules import globals, imagehelper, msgbox, utils

connection: aiosqlite.Connection = None


async def create_table(table_name: str, columns: dict[str, str]):
    await connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {', '.join([f'{column_name} {column_def}' for column_name, column_def in columns.items()])}
        )
    """)
    # Add missing and update existing columns for backwards compatibility
    cursor = await connection.execute(f"""
        PRAGMA table_info({table_name})
    """)
    key_column = None
    for column_name, column_def in columns.items():
        if "primary key" in column_def.lower():
            key_column = column_name
            break
    has_columns = [tuple(row) for row in await cursor.fetchall()]  # (index, name, type, can_be_null, default, idk)
    has_column_names = [column[1] for column in has_columns]
    has_column_defs = [(column[2], column[4]) for column in has_columns]  # (type, default)
    for column_name, column_def in columns.items():
        if column_name not in has_column_names:
            # Column is missing, add it
            await connection.execute(f"""
                ALTER TABLE {table_name}
                ADD COLUMN {column_name} {column_def}
            """)
        elif key_column is not None:  # Can only attempt default fix if key is present to transfer values
            has_column_def = has_column_defs[has_column_names.index(column_name)]  # (type, default)
            if not column_def.strip().lower().startswith(has_column_def[0].lower()):
                raise Exception(f"Existing database column '{column_name}' has incorrect type ({column_def[:column_def.find(' ')]} != {has_column_def[0]})")
            if " default " in column_def.lower() and not re.search(r"[Dd][Ee][Ff][Aa][Uu][Ll][Tt]\s+?" + re.escape(str(has_column_def[1])), column_def):
                # Default is different, recreate column and transfer values
                cursor = await connection.execute(f"""
                    SELECT {key_column}, {column_name}
                    FROM {table_name}
                """)
                rows = await cursor.fetchall()
                await connection.execute(f"""
                    ALTER TABLE {table_name}
                    DROP COLUMN {column_name}
                """)
                await connection.execute(f"""
                    ALTER TABLE {table_name}
                    ADD COLUMN {column_name} {column_def}
                """)
                for row in rows:
                    await connection.execute(f"""
                        UPDATE {table_name}
                        SET
                            {column_name} = ?
                        WHERE {key_column}=?
                    """, (row[column_name], row[key_column]))


async def connect():
    global connection

    migrate = not (globals.data_path / "db.sqlite3").is_file()
    connection = await aiosqlite.connect(globals.data_path / "db.sqlite3")
    connection.row_factory = aiosqlite.Row  # Return sqlite3.Row instead of tuple

    await create_table("settings", {
        "_":                           f'INTEGER PRIMARY KEY CHECK (_=0)',
        "browser_custom_arguments":    f'TEXT    DEFAULT ""',
        "browser_custom_executable":   f'TEXT    DEFAULT ""',
        "browser_html":                f'INTEGER DEFAULT {int(False)}',
        "browser_private":             f'INTEGER DEFAULT {int(False)}',
        "browser":                     f'INTEGER DEFAULT {Browser.get(0).hash}',
        "confirm_on_remove":           f'INTEGER DEFAULT {int(True)}',
        "display_mode":                f'INTEGER DEFAULT {DisplayMode.list}',
        "default_exe_dir":             f'TEXT    DEFAULT ""',
        "fit_images":                  f'INTEGER DEFAULT {int(False)}',
        "grid_columns":                f'INTEGER DEFAULT 3',
        "grid_image_ratio":            f'REAL    DEFAULT 3.0',
        "interface_scaling":           f'REAL    DEFAULT 1.0',
        "manual_sort_list":            f'TEXT    DEFAULT "[]"',
        "minimize_on_close":           f'INTEGER DEFAULT {int(False)}',
        "refresh_completed_games":     f'INTEGER DEFAULT {int(True)}',
        "refresh_workers":             f'INTEGER DEFAULT 20',
        "render_when_unfocused":       f'INTEGER DEFAULT {int(True)}',
        "request_timeout":             f'INTEGER DEFAULT 30',
        "scroll_amount":               f'REAL    DEFAULT 1.0',
        "scroll_smooth":               f'INTEGER DEFAULT {int(True)}',
        "scroll_smooth_speed":         f'REAL    DEFAULT 8.0',
        "select_executable_after_add": f'INTEGER DEFAULT {int(False)}',
        "show_remove_btn":             f'INTEGER DEFAULT {int(False)}',
        "start_in_tray":               f'INTEGER DEFAULT {int(False)}',
        "start_refresh":               f'INTEGER DEFAULT {int(False)}',
        "style_accent":                f'TEXT    DEFAULT "{DefaultStyle.accent}"',
        "style_alt_bg":                f'TEXT    DEFAULT "{DefaultStyle.alt_bg}"',
        "style_bg":                    f'TEXT    DEFAULT "{DefaultStyle.bg}"',
        "style_border":                f'TEXT    DEFAULT "{DefaultStyle.border}"',
        "style_corner_radius":         f'INTEGER DEFAULT {DefaultStyle.corner_radius}',
        "style_text":                  f'TEXT    DEFAULT "{DefaultStyle.text}"',
        "style_text_dim":              f'TEXT    DEFAULT "{DefaultStyle.text_dim}"',
        "tray_refresh_interval":       f'INTEGER DEFAULT 15',
        "update_keep_image":           f'INTEGER DEFAULT {int(False)}',
        "vsync_ratio":                 f'INTEGER DEFAULT 1',
        "zoom_amount":                 f'INTEGER DEFAULT 4',
        "zoom_enabled":                f'INTEGER DEFAULT {int(True)}',
        "zoom_region":                 f'INTEGER DEFAULT {int(True)}',
        "zoom_size":                   f'INTEGER DEFAULT 64'
    })
    await connection.execute("""
        INSERT INTO settings
        (_)
        VALUES
        (0)
        ON CONFLICT DO NOTHING
    """)

    await create_table("games", {
        "id":                          f'INTEGER PRIMARY KEY',
        "name":                        f'TEXT    DEFAULT ""',
        "version":                     f'TEXT    DEFAULT ""',
        "developer":                   f'TEXT    DEFAULT ""',
        "type":                        f'INTEGER DEFAULT {Type.Misc}',
        "status":                      f'INTEGER DEFAULT {Status.Not_Yet_Checked}',
        "url":                         f'TEXT    DEFAULT ""',
        "added_on":                    f'INTEGER DEFAULT 0',
        "last_updated":                f'INTEGER DEFAULT 0',
        "last_full_refresh":           f'INTEGER DEFAULT 0',
        "last_refresh_version":        f'TEXT    DEFAULT ""',
        "last_played":                 f'INTEGER DEFAULT 0',
        "rating":                      f'INTEGER DEFAULT 0',
        "played":                      f'INTEGER DEFAULT {int(False)}',
        "installed":                   f'TEXT    DEFAULT ""',
        "executable":                  f'TEXT    DEFAULT ""',
        "description":                 f'TEXT    DEFAULT ""',
        "changelog":                   f'TEXT    DEFAULT ""',
        "tags":                        f'TEXT    DEFAULT "[]"',
        "notes":                       f'TEXT    DEFAULT ""',
        "image_url":                   f'TEXT    DEFAULT ""'
    })

    await create_table("cookies", {
        "key":                         f'TEXT    PRIMARY KEY',
        "value":                       f'TEXT    DEFAULT ""'
    })

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
    match getattr(data_type, "__name__", None):
        case "list":
            value = json.loads(value)
            if hasattr(data_type, "__args__"):
                content_type = data_type.__args__[0]
                value = [content_type(x) for x in value]
        case "tuple":
            if isinstance(value, str) and getattr(data_type, "__args__", [None])[0] is float:
                value = utils.hex_to_rgba_0_1(value)
            else:
                value = json.loads(value)
                if hasattr(data_type, "__args__"):
                    content_type = data_type.__args__[0]
                    value = [content_type(x) for x in value]
                value = tuple(value)
        case _:
            value = data_type(value)
    return value


async def load_games(id: int = None):
    types = Game.__annotations__
    query = """
        SELECT *
        FROM games
    """
    if id is not None:
        query += f"""
            WHERE id={id}
        """
    cursor = await connection.execute(query)
    games = await cursor.fetchall()
    for game in games:
        game = dict(game)
        game = {key: sql_to_py(value, types[key]) for key, value in game.items() if key in types}
        game["image"] = imagehelper.ImageHelper(globals.images_path, glob=f"{game['id']}.*")
        globals.games[game["id"]] = Game(**game)


async def load():
    types = Settings.__annotations__
    cursor = await connection.execute("""
        SELECT *
        FROM settings
    """)
    settings = dict(await cursor.fetchone())
    settings = {key: sql_to_py(value, types[key]) for key, value in settings.items() if key in types}
    globals.settings = Settings(**settings)

    globals.games = {}
    await load_games()

    cursor = await connection.execute("""
        SELECT *
        FROM cookies
    """)
    cookies = await cursor.fetchall()
    globals.cookies = {cookie["key"]: cookie["value"] for cookie in cookies}


def py_to_sql(value: enum.Enum | Timestamp | bool | list | tuple | typing.Any):
    if hasattr(value, "value"):
        value = value.value
    elif hasattr(value, "hash"):
        value = value.hash
    elif isinstance(value, bool):
        value = int(value)
    elif isinstance(value, list):
        value = list(value)
        value = [item.value if hasattr(item, "value") else item for item in value]
        value = json.dumps(value)
    elif isinstance(value, tuple) and 3 <= len(value) <= 4:
        value = utils.rgba_0_1_to_hex(value)
    return value


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


async def remove_game(id: int):
    await connection.execute(f"""
        DELETE FROM games
        WHERE id={id}
    """)


async def add_game(thread: ThreadMatch | SearchResult):
    await connection.execute(f"""
        INSERT INTO games
        (id, name, version, status, url, added_on)
        VALUES
        (?,  ?,    ?,       ?,      ?,   ?       )
    """, (thread.id, thread.title or f"Unknown ({thread.id})", "Not Yet Checked", Status.Not_Yet_Checked.value, f"{globals.threads_page}{thread.id}", time.time()))


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


def legacy_json_to_dict(path: str | pathlib.Path):  # Pre v9.0
    with open(path, "rb") as f:
        config = json.load(f)
    if type(config.get("game_list")) is list and type(config.get("game_data")) is dict:  # Pre v8.0
        config.setdefault("games", {})
        for game in config["game_list"]:
            if not game:
                continue
            link = config["game_data"][game]["link"]
            if not link:
                continue
            if link.startswith("/"):
                link = globals.domain + link
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


def legacy_ini_to_dict(path: str | pathlib.Path):  # Pre v7.0
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
            link = globals.domain + link
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
                utils.push_popup(msgbox.msgbox, "Unsupported format", f"Could not migrate {str(path)}\nThe only supported formats are .json and .ini.", MsgBox.warn)
                return
        keys = []
        values = []

        if (options := config.get("options")) is not None:

            keys.append("browser")
            match options.get("browser"):
                case "chrome":
                    value = utils.hash("Google Chrome")
                case "firefox":
                    value = utils.hash("Mozilla Firefox")
                case "brave":
                    value = utils.hash("Brave")
                case "edge":
                    value = utils.hash("Microsoft Edge")
                case "opera":
                    value = utils.hash("Opera Stable")
                case "operagx":
                    value = utils.hash("Opera GX Stable")
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
                keys.append("tray_refresh_interval")
                values.append(bg_mode_delay_mins)

            if (refresh_completed_games := options.get("refresh_completed_games")) is not None:
                keys.append("refresh_completed_games")
                values.append(int(refresh_completed_games))

            if (keep_image_on_game_update := options.get("keep_image_on_game_update")) is not None:
                keys.append("update_keep_image")
                values.append(int(keep_image_on_game_update))

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

                keys.append("version")
                values.append(version := (game.get("version") or "Not Yet Checked"))

                keys.append("status")
                match game.get("status"):
                    case "none":
                        value = Status.Normal.value
                    case "completed":
                        value = Status.Completed.value
                    case "onhold":
                        value = Status.OnHold.value
                    case "abandoned":
                        value = Status.Abandoned.value
                    case _:
                        value = Status.Not_Yet_Checked.value
                values.append(value)

                if (installed := game.get("installed")) is not None:
                    keys.append("installed")
                    if installed:
                        values.append(version)
                    else:
                        values.append("")

                if (played := game.get("played")) is not None:
                    keys.append("played")
                    values.append(int(played))

                if (exe_path := game.get("exe_path")) is not None:
                    keys.append("executable")
                    values.append(exe_path)

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
        utils.push_popup(msgbox.msgbox, "Config migration error", f"Something went wrong transferring data from the previous version:\n\n{utils.get_traceback()}", MsgBox.error)
