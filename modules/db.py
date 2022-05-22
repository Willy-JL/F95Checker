import configparser
import aiosqlite
import asyncio
import pathlib
import typing
import enum
import json

from modules.structs import Browser, DisplayMode, Game, MsgBox, Settings, Status, Timestamp, Type
from modules import globals, imagehelper, utils

connection: aiosqlite.Connection = None
available: bool = False
pending: int = 0


async def connect():
    global available, connection

    migrate = not (globals.data_path / "db.sqlite3").is_file()
    # connection = await aiosqlite.connect(globals.data_path / "db.sqlite3")
    connection = await aiosqlite.connect(":memory:")  # Temporary while things are not final
    connection.row_factory = aiosqlite.Row  # Return sqlite3.Row instead of tuple

    await connection.execute(f"""
        CREATE TABLE IF NOT EXISTS settings (
            _                           INTEGER PRIMARY KEY CHECK (_=0),
            browser_custom_arguments    TEXT    DEFAULT "",
            browser_custom_executable   TEXT    DEFAULT "",
            browser_html                INTEGER DEFAULT 0,
            browser_private             INTEGER DEFAULT 0,
            browser                     INTEGER DEFAULT {Browser._None},
            confirm_on_remove           INTEGER DEFAULT 1,
            display_mode                INTEGER DEFAULT {DisplayMode.list},
            default_exe_dir             TEXT    DEFAULT "",
            fit_images                  INTEGER DEFAULT 0,
            grid_columns                INTEGER DEFAULT 3,
            grid_image_ratio            REAL    DEFAULT 3.0,
            manual_sort_list            TEXT    DEFAULT "[]",
            minimize_on_close           INTEGER DEFAULT 0,
            refresh_completed_games     INTEGER DEFAULT 1,
            refresh_workers             INTEGER DEFAULT 20,
            request_timeout             INTEGER DEFAULT 30,
            scroll_amount               REAL    DEFAULT 1,
            scroll_smooth               INTEGER DEFAULT 1,
            scroll_smooth_speed         REAL    DEFAULT 8,
            select_executable_after_add INTEGER DEFAULT 0,
            start_in_tray               INTEGER DEFAULT 0,
            start_refresh               INTEGER DEFAULT 0,
            style_accent                TEXT    DEFAULT "#da1e2e",
            style_alt_bg                TEXT    DEFAULT "#141414",
            style_bg                    TEXT    DEFAULT "#181818",
            style_btn_border            TEXT    DEFAULT "#454545",
            style_btn_disabled          TEXT    DEFAULT "#232323",
            style_btn_hover             TEXT    DEFAULT "#747474",
            style_corner_radius         INTEGER DEFAULT 6,
            style_scaling               REAL    DEFAULT 1.0,
            tray_refresh_interval       INTEGER DEFAULT 15,
            update_keep_image           INTEGER DEFAULT 0,
            vsync_ratio                 INTEGER DEFAULT 1,
            zoom_amount                 INTEGER DEFAULT 4,
            zoom_enabled                INTEGER DEFAULT 1,
            zoom_region                 INTEGER DEFAULT 1,
            zoom_size                   INTEGER DEFAULT 64
        )
    """)
    await connection.execute("""
        INSERT INTO settings
        (_)
        VALUES
        (0)
        ON CONFLICT DO NOTHING
    """)

    await connection.execute(f"""
        CREATE TABLE IF NOT EXISTS games (
            id                INTEGER PRIMARY KEY,
            name              TEXT    DEFAULT "",
            version           TEXT    DEFAULT "",
            developer         TEXT    DEFAULT "",
            type              INTEGER DEFAULT {Type.Others},
            status            INTEGER DEFAULT {Status.Normal},
            url               TEXT    DEFAULT "",
            added_on          INTEGER DEFAULT 0,
            last_updated      INTEGER DEFAULT 0,
            last_full_refresh INTEGER DEFAULT 0,
            last_played       INTEGER DEFAULT 0,
            rating            INTEGER DEFAULT 0,
            played            INTEGER DEFAULT 0,
            installed         TEXT    DEFAULT "",
            executable        TEXT    DEFAULT "",
            description       TEXT    DEFAULT "",
            changelog         TEXT    DEFAULT "",
            tags              TEXT    DEFAULT "[]",
            notes             TEXT    DEFAULT ""
        )
    """)

    available = True

    if migrate:
        if (path := globals.data_path / "f95checker.json").is_file() or (path := globals.data_path / "config.ini").is_file():
            await migrate_legacy(path)


async def _wait_connection():
    while not available:
        await asyncio.sleep(0.1)


async def wait_connection():
    await asyncio.wait_for(_wait_connection(), timeout=5)


async def execute(request: str, *args):
    global pending
    await wait_connection()
    pending += 1
    try:
        return await connection.execute(request, *args)
    finally:
        pending -= 1


async def _wait_pending():
    while pending > 0:
        await asyncio.sleep(0.1)


async def wait_pending():
    await asyncio.wait_for(_wait_pending(), timeout=5)


async def close():
    global available
    available = False
    await wait_pending()
    await connection.commit()
    await connection.close()


# Committing should save to disk, but for some reason it only does so after closing
async def save():
    pass  # Temporary while things are not final
    # await close()
    # await connect()


async def save_loop():
    while True:
        await asyncio.sleep(30)
        await save()


def sql_to_py(value: str | int | float, data_type: typing.Type):
    if getattr(data_type, "__name__", None) == "list":
        value = json.loads(value)
        if hasattr(data_type, "__args__"):
            content_type = data_type.__args__[0]
            value = [content_type(x) for x in value]
    else:
        value = data_type(value)
    return value


async def load():
    types = Settings.__annotations__
    cursor = await execute("""
        SELECT *
        FROM settings
    """)
    settings = dict(await cursor.fetchone())
    settings = {key: sql_to_py(value, types[key]) for key, value in settings.items() if key in types}
    globals.settings = Settings(**settings)
    if globals.settings.browser.name not in globals.browsers:
        globals.settings.browser = Browser._None
    globals.browser_idx = globals.browsers.index(globals.settings.browser.name)

    globals.games = {}
    types = Game.__annotations__
    cursor = await execute("""
        SELECT *
        FROM games
    """)
    games = await cursor.fetchall()
    for game in games:
        game = dict(game)
        game = {key: sql_to_py(value, types[key]) for key, value in game.items() if key in types}
        game["image"] = imagehelper.ImageHelper(globals.images_path, glob=f"{game['id']}.*")
        globals.games[game["id"]] = Game(**game)


def py_to_sql(value: enum.Enum | Timestamp | bool | list | typing.Any):
    if hasattr(value, "value"):
        value = value.value
    elif isinstance(value, bool):
        value = int(value)
    elif isinstance(value, list):
        value = list(value)
        value = [item.value if hasattr(item, "value") else item for item in value]
        value = json.dumps(value)
    return value


async def update_game(game: Game, *keys: list[str]):
    values = []

    for key in keys:
        value = py_to_sql(getattr(game, key))
        values.append(value)

    await execute(f"""
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

    await execute(f"""
        UPDATE settings
        SET
            {", ".join(f"{key} = ?" for key in keys)}
        WHERE _=0
    """, tuple(values))


async def remove_game(id: int):
    await execute(f"""
        DELETE FROM games
        WHERE id={id}
    """)


def legacy_json_to_dict(path: str | pathlib.Path):  # Pre v9.0
    with open(path, encoding="utf-8") as f:
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
            id = utils.extract_thread_ids(link)
            if not id:
                continue
            id = str(id[0])
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
        id = utils.extract_thread_ids(link)
        if not id:
            continue
        id = str(id[0])
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
                utils.push_popup(globals.gui.draw_msgbox, "Unsupported format!", f"Could not migrate {str(path)}\n The only supported formats are .json and .ini!", MsgBox.warn)
                return
        keys = []
        values = []

        if options := config.get("options"):

            if browser := options.get("browser"):
                keys.append("browser")
                values.append({
                    "none":    Browser._None,
                    "chrome":  Browser.Chrome,
                    "firefox": Browser.Firefox,
                    "brave":   Browser.Brave,
                    "edge":    Browser.Edge,
                    "opera":   Browser.Opera,
                    "operagx": Browser.Opera_GX
                }[browser].value)

            if private_browser := options.get("private_browser"):
                keys.append("browser_private")
                values.append(int(private_browser))

            if open_html := options.get("open_html"):
                keys.append("browser_html")
                values.append(int(open_html))

            if start_refresh := options.get("start_refresh"):
                keys.append("start_refresh")
                values.append(int(start_refresh))

            if bg_mode_delay_mins := options.get("bg_mode_delay_mins"):
                keys.append("tray_refresh_interval")
                values.append(bg_mode_delay_mins)

            if refresh_completed_games := options.get("refresh_completed_games"):
                keys.append("refresh_completed_games")
                values.append(int(refresh_completed_games))

            if keep_image_on_game_update := options.get("keep_image_on_game_update"):
                keys.append("update_keep_image")
                values.append(int(keep_image_on_game_update))

        if style := config.get("style"):

            if back := style.get("back"):
                keys.append("style_bg")
                values.append(back)

            if alt := style.get("alt"):
                keys.append("style_alt_bg")
                values.append(alt)

            if accent := style.get("accent"):
                keys.append("style_accent")
                values.append(accent)

            if border := style.get("border"):
                keys.append("style_btn_border")
                values.append(border)

            if hover := style.get("hover"):
                keys.append("style_btn_hover")
                values.append(hover)

            if disabled := style.get("disabled"):
                keys.append("style_btn_disabled")
                values.append(disabled)

        await execute(f"""
            UPDATE settings
            SET
                {", ".join(f"{key} = ?" for key in keys)}
            WHERE _=0
        """, tuple(values))

        if games := config.get("games"):
            for game in games.values():
                id = utils.extract_thread_ids(game["link"])
                if not id:
                    continue
                id = id[0]
                keys = ["id"]
                values = [id]

                if name := game.get("name"):
                    keys.append("name")
                    values.append(name)

                if version := game.get("version"):
                    keys.append("version")
                    values.append(version)

                if status := game.get("status"):
                    keys.append("status")
                    values.append(Status[{
                        "none":      "Normal",
                        "completed": "Completed",
                        "onhold":    "OnHold",
                        "abandoned": "Abandoned"
                    }[status]].value)

                if installed := game.get("installed"):
                    keys.append("installed")
                    if installed and type(version) is str:
                        values.append(version)
                    else:
                        values.append("")

                if played := game.get("played"):
                    keys.append("played")
                    values.append(int(played))

                if exe_path := game.get("exe_path"):
                    keys.append("executable")
                    values.append(exe_path)

                if link := game.get("link"):
                    keys.append("url")
                    values.append(link)

                if add_time := game.get("add_time"):
                    keys.append("added_on")
                    values.append(int(add_time))

                if updated_time := game.get("updated_time"):
                    keys.append("last_updated")
                    values.append(int(updated_time))

                if changelog := game.get("changelog"):
                    keys.append("changelog")
                    values.append(changelog)

                if notes := game.get("notes"):
                    keys.append("notes")
                    values.append(notes)

                await execute(f"""
                    INSERT INTO games
                    ({", ".join(keys)})
                    VALUES
                    ({", ".join("?" * len(values))})
                """, tuple(values))
        await save()
    except Exception:
        utils.push_popup(globals.gui.draw_msgbox, "Oops!", f"Something went wrong migrating {str(path)}:\n\n{utils.get_traceback()}", MsgBox.error)
