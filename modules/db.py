from modules.structs import *
from modules import globals
from modules import utils
import aiosqlite
import asyncio
import pathlib
import json

connection: aiosqlite.Connection = None
available: bool = False
pending: int = 0


async def connect():
    global available, connection

    migrate = not (globals.data_path / "db.sqlite3").is_file()
    connection = await aiosqlite.connect(globals.data_path / "db.sqlite3")
    connection.row_factory = aiosqlite.Row  # Return sqlite3.Row instead of tuple

    await connection.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            _                           INTEGER PRIMARY KEY CHECK (_=0),
            browser_custom_arguments    TEXT    DEFAULT "",
            browser_custom_executable   TEXT    DEFAULT "",
            browser_html                INTEGER DEFAULT 0,
            browser_private             INTEGER DEFAULT 0,
            browser                     INTEGER DEFAULT 0,
            column_developer            INTEGER DEFAULT 0,
            column_engine               INTEGER DEFAULT 0,
            column_installed            INTEGER DEFAULT 1,
            column_last_played          INTEGER DEFAULT 0,
            column_last_updated         INTEGER DEFAULT 0,
            column_name                 INTEGER DEFAULT 1,
            column_played               INTEGER DEFAULT 1,
            column_rating               INTEGER DEFAULT 0,
            column_status               INTEGER DEFAULT 1,
            column_time_added           INTEGER DEFAULT 0,
            column_version              INTEGER DEFAULT 1,
            refresh_completed_games     INTEGER DEFAULT 1,
            refresh_workers             INTEGER DEFAULT 20,
            request_timeout             INTEGER DEFAULT 30,
            select_executable_after_add INTEGER DEFAULT 0,
            sort_mode                   INTEGER DEFAULT 1,
            start_in_tray               INTEGER DEFAULT 0,
            start_refresh               INTEGER DEFAULT 0,
            start_with_system           INTEGER DEFAULT 0,
            style_accent                TEXT    DEFAULT "#da1e2e",
            style_alt_bg                TEXT    DEFAULT "#141414",
            style_bg                    TEXT    DEFAULT "#181818",
            style_btn_border            TEXT    DEFAULT "#454545",
            style_btn_disabled          TEXT    DEFAULT "#232323",
            style_btn_hover             TEXT    DEFAULT "#747474",
            style_corner_radius         INTEGER DEFAULT 6,
            style_scaling               REAL    DEFAULT 1.0,
            tray_refresh_interval       INTEGER DEFAULT 15,
            update_keep_executable      INTEGER DEFAULT 0,
            update_keep_image           INTEGER DEFAULT 0
        )
    """)
    await connection.execute("""
        INSERT INTO settings
        (_)
        VALUES
        (0)
        ON CONFLICT DO NOTHING
    """)

    await connection.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id                INTEGER PRIMARY KEY,
            name              TEXT    DEFAULT "",
            version           TEXT    DEFAULT "",
            developer         TEXT    DEFAULT "",
            engine            INTEGER DEFAULT 0,
            status            INTEGER DEFAULT 0,
            url               TEXT    DEFAULT "",
            time_added        INTEGER DEFAULT 0,
            last_updated      INTEGER DEFAULT 0,
            last_full_refresh INTEGER DEFAULT 0,
            last_played       INTEGER DEFAULT 0,
            rating            INTEGER DEFAULT 0,
            installed         TEXT    DEFAULT "",
            played            INTEGER DEFAULT 0,
            executable        TEXT    DEFAULT "",
            description       TEXT    DEFAULT "",
            changelog         TEXT    DEFAULT "",
            tags              TEXT    DEFAULT "[]",
            notes             TEXT    DEFAULT ""
        )
    """)

    available = True

    if migrate:
        if (path := globals.data_path / "f95checker.json").is_file():
            await migrate_legacy_json(path)
        elif (path := globals.data_path / "config.ini").is_file():
            await migrate_legacy_ini(path)


async def _wait_connection():
    while not available:
        await asyncio.sleep(0.1)


async def wait_connection():
    await asyncio.wait_for(_wait_connection(), timeout=30)


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
    await asyncio.wait_for(_wait_pending(), timeout=30)


async def close():
    global available
    available = False
    await wait_pending()
    await connection.commit()
    await connection.close()


# Committing should save to disk, but for some reason it only does so after closing
async def save():
    await close()
    await connect()


async def load():
    globals.settings = Settings()
    cursor = await execute("""
        SELECT *
        FROM settings
    """)
    settings = await cursor.fetchone()
    for key in settings.keys():
        data_type = Settings.__annotations__.get(key)
        if data_type:
            value = data_type(settings[key])
            setattr(globals.settings, key, value)

    globals.games = {}
    cursor = await execute("""
        SELECT *
        FROM games
    """)
    games = await cursor.fetchall()
    for game in games:
        globals.games[game["id"]] = Game()
        for key in game.keys():
            data_type = Game.__annotations__[key]
            if data_type == list[Tag]:
                value = [Tag(x) for x in json.loads(game[key])]
            else:
                value = data_type(game[key])
            setattr(globals.games[game["id"]], key, value)


async def migrate_legacy_json(path: str | pathlib.Path):  # Pre v9.0
    try:
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
        await migrate_legacy(config)
    except Exception as exc:
        print(exc)


async def migrate_legacy_ini(path: str | pathlib.Path):  # Pre v7.0
    try:
        from configparser import RawConfigParser
        old_config = RawConfigParser()
        old_config.read(path)
        config = {}
        config["options"] = {}
        config["options"]["browser"]            = old_config.get(       'options', 'browser',       fallback=''    )
        config["options"]["private_browser"]    = old_config.getboolean('options', 'private',       fallback=False )
        config["options"]["open_html"]          = old_config.getboolean('options', 'open_html',     fallback=False )
        config["options"]["start_refresh"]      = old_config.getboolean('options', 'start_refresh', fallback=False )
        config["options"]["auto_sort"]          = old_config.get(       'options', 'auto_sort',     fallback='none')
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
        await migrate_legacy(config)
    except Exception as exc:
        print(exc)


async def migrate_legacy(config: dict):
    keys = []
    values = []

    if options := config.get("options"):

        if browser := options.get("browser"):
            keys.append("browser")
            values.append(Browser[browser].value)

        if private_browser := options.get("private_browser"):
            keys.append("browser_private")
            values.append(int(private_browser))

        if open_html := options.get("open_html"):
            keys.append("browser_html")
            values.append(int(open_html))

        if start_refresh := options.get("start_refresh"):
            keys.append("start_refresh")
            values.append(int(start_refresh))

        if auto_sort := options.get("auto_sort"):
            keys.append("sort_mode")
            values.append(SortMode[{
                "none": "manual",
                "last_updated": "last_updated",
                "first_added": "time_added",
                "alphabetical": "alphabetical"
            }[auto_sort]].value)

        if bg_mode_delay_mins := options.get("bg_mode_delay_mins"):
            keys.append("tray_refresh_interval")
            values.append(bg_mode_delay_mins)

        if refresh_completed_games := options.get("refresh_completed_games"):
            keys.append("refresh_completed_games")
            values.append(int(refresh_completed_games))

        if keep_image_on_game_update := options.get("keep_image_on_game_update"):
            keys.append("update_keep_image")
            values.append(int(keep_image_on_game_update))

        if keep_exe_path_on_game_update := options.get("keep_exe_path_on_game_update"):
            keys.append("update_keep_executable")
            values.append(int(keep_exe_path_on_game_update))

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
        for id, game in games.items():
            keys = ["id"]
            values = [int(id)]

            if name := game.get("name"):
                keys.append("name")
                values.append(name)

            if version := game.get("version"):
                keys.append("version")
                values.append(version)

            if status := game.get("status"):
                keys.append("status")
                values.append(Status[status].value)

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
                keys.append("time_added")
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
